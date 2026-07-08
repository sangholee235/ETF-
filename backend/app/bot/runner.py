"""한 번의 적립 tick 을 오케스트레이션한다.

장중 여러 번(스케줄러가 10분 간격) 호출될 수 있다 — '하루 1회'가 아니라
'하루 한도(daily_budget_krw)를 오늘 얼마나 썼는지'로 관리한다(state.today_*).
그래서 아침에 예산이 남았거나(1주도 못 사서), 낮에 입금이 들어오거나,
가격이 떨어져 이제 살 수 있게 되면 다음 실행에서 자동으로 이어서 산다.

순서:
1. 직전 미체결 주문 체결 확인 -> 상태 갱신
2. 오늘 남은 한도부터 확인(API 호출 없음) — 0이면 아래 API 호출 없이 바로 종료
3. 오늘 '남은' 예산으로 그리디 매수 계획 수립 (목표비중 그대로, 여러 종목 가능)
4. 가드레일 검증 (킬스위치/장운영시간/누적한도)
5. 계획된 주문들을 순서대로 시장가 실행 (DRY_RUN/LIVE) — 매 건마다 계획을
   즉시 반영해 다음 판단에 쓰므로, 실행은 시장가로 해야 순서가 안 꼬인다.
6. 오늘 쓴 금액 기록 + 상태/로그 저장
"""

from __future__ import annotations

from datetime import date

from tossapi import TossClient, TossApiError

from . import executor, guardrails
from .config import BotConfig
from .portfolio import plan_daily_buys
from .state import BotState
from .strategy import Decision


def run_once(client: TossClient | None = None, broker: str | None = None,
             manual: bool = False) -> dict:
    # manual 은 더 이상 게이트를 안 바꾼다 — 자동/수동 모두 '오늘 남은 한도' 기준으로
    # 동일하게 동작한다(하루 여러 번 가능). API 호환을 위해 파라미터만 유지.
    from brokers import get_broker
    cfg = BotConfig.load(broker)
    state = BotState.load(broker)
    client = client or get_broker(broker)

    # 1. 직전 주문 체결 확인 (LIVE, 이전 방식으로 남아있는 미체결이 있으면)
    executor.confirm_previous_fill(client, cfg, state)

    # 살아있는 미체결 주문이 있으면 중복 주문 방지 (먼저 취소 유도). 시장가라 평소엔 거의 없음.
    if not cfg.dry_run and _has_open_order(client):
        log = executor.execute(client, cfg, state,
                               _skip("대기 중(미체결) 주문이 있습니다 — 먼저 취소 후 다시 시도하세요"))
        state.add_log(log); state.save()
        return _summary(cfg, state, [log])

    has_target = any(p.get("symbol") and float(p.get("weight", 0)) > 0 for p in cfg.portfolio)
    if not has_target:
        log = executor.execute(client, cfg, state, _skip("적립할 ETF가 없음 — ETF와 목표비중을 추가하세요"))
        state.add_log(log); state.save()
        return _summary(cfg, state, [log])

    # 2. 오늘 남은 한도부터 먼저 확인(API 호출 없음, cfg/state만 봄) — 0이면 보유현황·
    #    가격 조회 같은 API 호출 자체를 안 하고 바로 끝낸다. cfg 는 매번 파일에서 새로
    #    읽으므로(캐시 없음), 장중에 한도를 늘리면 다음 체크에서 바로 반영된다.
    remaining_today = state.today_remaining_budget(cfg.daily_budget_krw)
    if remaining_today <= 0:
        log = executor.execute(client, cfg, state,
                               _skip("오늘 하루 한도를 이미 다 썼습니다 — 내일 다시 시도"))
        state.add_log(log); state.save()
        return _summary(cfg, state, [log])

    # 2b. 오늘 이미 현금 부족으로 SKIP한 적 있으면 조용히 종료 (로그 없음).
    #     입금이 들어오면 내일 아침에 자동으로 재시도한다.
    today = date.today().isoformat()
    if state.cash_exhausted_date == today:
        return _summary(cfg, state, [])

    # 3. 오늘 매수 계획 수립: '오늘 남은' 한도(이미 오늘 쓴 만큼 차감) 안에서 그리디하게
    bp = _buying_power(client)
    current_values = _holdings_values(client, cfg) or {}
    prices = _portfolio_prices(client, cfg)
    budget = min(remaining_today, bp) if bp is not None else remaining_today
    plan = plan_daily_buys(cfg, current_values, prices, budget) if budget > 0 else []

    if not plan:
        cash_short = budget <= 0 or not prices
        missing = _missing_price_symbols(cfg, prices)
        if missing and not cash_short:
            # 일부 종목만 시세 조회 실패 — '균형 도달'이 아니라 일시적 조회 실패이므로
            # 억제(cash_exhausted_date)하지 않고 다음 확인 때 바로 재시도한다.
            reason = f"시세 조회 실패: {', '.join(missing)} — 다음 확인 때 재시도"
        else:
            reason = ("매수가능금액/오늘 남은 한도로 1주도 못 삽니다" if cash_short
                      else "오늘 살 게 없음 — 이미 목표 비중 도달")
            if cash_short:
                state.cash_exhausted_date = today
        log = executor.execute(client, cfg, state, _skip(reason))
        state.add_log(log); state.save()
        return _summary(cfg, state, [log])

    # 4. 가드레일 (킬스위치/장운영시간/누적한도) — 계획 총액 기준 1회 체크
    total_cost = sum(item["estCost"] for item in plan)
    guard = guardrails.check(client, cfg, state, total_cost, buying_power=bp)
    if not guard.ok:
        log = executor.execute(client, cfg, state, _skip(guard.reason))
        state.add_log(log); state.save()
        return _summary(cfg, state, [log])

    # 5. 계획 순서대로 시장가 매수 실행 (그리디라 지정가 대기 없이 즉시 체결 확정 필요)
    #    주문 직전 재확인(kt00010 profa_100ord_alowq)은 필드 해석이 신용거래
    #    맥락이라 정상 계좌의 매수까지 잘못 막는 문제가 있어 되돌림 — 예수금
    #    기준 매수가능금액으로 바로 시도하고, 거부되면 executor 가 그 사유를
    #    실행기록에 정상적으로 남긴다(다음 아이템은 계속 진행).
    logs = []
    spent = 0
    for i, item in enumerate(plan):
        qty = item["quantity"]
        d = Decision(
            "MARKET_BUY", qty, None,
            f"그리디 리밸런싱: {item['symbol']} {qty}주 (목표비중 맞춤, {item['price']:,}원 기준)",
            item["price"] * qty, item["symbol"],
        )
        log = executor.execute(client, cfg, state, d, seq=i)
        if log.action == "MARKET_BUY":
            _apply_optimistic_fill(state, log, item["price"], qty)
            spent += item["price"] * qty
        state.add_log(log)
        logs.append(log)

    # 6. 오늘 쓴 금액 기록 (다음 실행에서 '오늘 남은 한도' 계산에 반영됨)
    if spent > 0:
        state.record_today_spend(spent)
        state.cash_exhausted_date = None  # 매수 성공 시 현금부족 억제 해제
    state.last_trade_date = date.today().isoformat()
    state.save()
    return _summary(cfg, state, logs)


def _has_open_order(client) -> bool:
    """살아있는 미체결 주문이 있는지 (수동 재시도 시 중복 주문 방지)."""
    try:
        return bool(client.get_orders("OPEN").get("orders"))
    except (TossApiError, KeyError, ValueError, TypeError, AttributeError, NotImplementedError):
        return False


def _buying_power(client) -> int | None:
    """매수가능금액(원). 못 읽으면 None."""
    try:
        return int(float(client.get_buying_power("KRW")["cashBuyingPower"]))
    except (TossApiError, KeyError, ValueError, TypeError):
        return None


def _current(client: TossClient, symbol: str) -> int | None:
    try:
        p = client.get_price(symbol)
        return int(float(p["lastPrice"])) if p and p.get("lastPrice") else None
    except (TossApiError, KeyError, ValueError):
        return None


def _portfolio_prices(client, cfg) -> dict:
    """포트폴리오 종목들의 현재가. 조회 실패한 종목은 제외(그 종목은 이번엔 후보에서 빠짐)."""
    out: dict[str, int] = {}
    for p in cfg.portfolio:
        sym = p.get("symbol")
        if not sym or float(p.get("weight", 0)) <= 0:
            continue
        try:
            out[sym] = int(float(client.get_price(sym)["lastPrice"]))
        except (TossApiError, KeyError, ValueError, TypeError):
            continue
    return out


def _holdings_values(client, cfg) -> dict | None:
    """포트폴리오 종목의 현재 실제 보유 평가금액(원). 못 읽으면 None(0원 기준 폴백)."""
    syms = {p.get("symbol") for p in cfg.portfolio if p.get("symbol")}
    if not syms:
        return None
    try:
        holdings = client.get_holdings()
    except (TossApiError, KeyError, ValueError, TypeError):
        return None
    out: dict[str, float] = {s: 0.0 for s in syms}
    for it in holdings.get("items", []) or []:
        sym = it.get("symbol")
        if sym in out:
            try:
                out[sym] = float(it.get("marketValue", {}).get("amount") or 0)
            except (ValueError, TypeError):
                pass
    return out


def _missing_price_symbols(cfg: BotConfig, prices: dict) -> list[str]:
    """목표비중이 있는데 이번 tick에 시세 조회가 실패해 후보에서 빠진 종목들.
    (plan_daily_buys 는 prices 에 없는 종목을 조용히 건너뛰므로, 이걸 구분 못 하면
    '이미 목표 비중 도달'로 오인 표시된다 — 실제로는 그냥 그 종목만 안 본 것)"""
    return [p["symbol"] for p in cfg.portfolio
            if p.get("symbol") and float(p.get("weight", 0)) > 0 and p["symbol"] not in prices]


def _skip(reason: str) -> Decision:
    return Decision("SKIP", 0, None, reason, 0, "")


def _apply_optimistic_fill(state: BotState, log, price: int, qty: int) -> None:
    """시장가 매수는 사실상 즉시 체결되므로, 계획 가격 기준으로 바로 통계 반영.
    (다음 판단에 바로 반영돼야 그리디 루프가 의미 있음 — 정밀 평단은 다음 tick 의
    confirm_previous_fill/체결내역 조회가 실제값으로 보정)"""
    log.filled = True
    amount = int(price * qty)
    state.total_filled_qty += qty
    state.total_invested_krw += amount
    state.consecutive_misses = 0
    inv = state.portfolio_invested or {}
    inv[log.symbol] = int(inv.get(log.symbol, 0)) + amount
    state.portfolio_invested = inv


def _summary(cfg: BotConfig, state: BotState, logs: list) -> dict:
    buys = [lg for lg in logs if lg.action in ("LIMIT_BUY", "MARKET_BUY")]
    if buys:
        total = sum((lg.price or 0) * lg.quantity for lg in buys)
        decision = {
            "action": "MARKET_BUY",
            "reason": f"{len(buys)}개 종목 매수: " + ", ".join(f"{lg.symbol} {lg.quantity}주" for lg in buys),
            "price": total,
        }
    else:
        last = logs[-1]
        decision = {"action": last.action, "price": last.price, "reason": last.reason}
    return {
        "mode": "DRY_RUN" if cfg.dry_run else "LIVE",
        "enabled": cfg.enabled,
        "symbol": logs[-1].symbol if logs else None,
        "decision": decision,
        "filled": all(lg.filled for lg in buys) if buys else logs[-1].filled,
        "consecutiveMisses": state.consecutive_misses,
        "totalInvestedKrw": state.total_invested_krw,
        "totalFilledQty": state.total_filled_qty,
        "totalBudgetKrw": cfg.total_budget_krw,
    }

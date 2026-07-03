"""한 번의 적립 tick 을 오케스트레이션한다.

순서:
1. 직전 미체결 주문 체결 확인 -> 상태 갱신
2. 오늘 하루 예산으로 그리디 매수 계획 수립 (목표비중 그대로, 여러 종목 가능)
3. 가드레일 검증 (킬스위치/장운영시간/하루1회/누적한도)
4. 계획된 주문들을 순서대로 시장가 실행 (DRY_RUN/LIVE) — 매 건마다 계획을
   즉시 반영해 다음 판단에 쓰므로, 실행은 시장가로 해야 순서가 안 꼬인다.
5. 상태/로그 저장
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
    from brokers import get_broker
    cfg = BotConfig.load(broker)
    state = BotState.load(broker)
    client = client or get_broker(broker)

    # 1. 직전 주문 체결 확인 (LIVE, 이전 방식으로 남아있는 미체결이 있으면)
    executor.confirm_previous_fill(client, cfg, state)

    # 수동 적립: 살아있는 미체결 주문이 있으면 중복 주문 방지 (먼저 취소 유도)
    if manual and not cfg.dry_run and _has_open_order(client):
        log = executor.execute(client, cfg, state,
                               _skip("대기 중(미체결) 주문이 있습니다 — 먼저 취소 후 다시 시도하세요"))
        state.add_log(log); state.save()
        return _summary(cfg, state, [log])

    has_target = any(p.get("symbol") and float(p.get("weight", 0)) > 0 for p in cfg.portfolio)
    if not has_target:
        log = executor.execute(client, cfg, state, _skip("적립할 ETF가 없음 — ETF와 목표비중을 추가하세요"))
        state.add_log(log); state.save()
        return _summary(cfg, state, [log])

    # 2. 오늘 매수 계획 수립: 하루 한도 안에서 목표비중대로 그리디하게 여러 종목
    bp = _buying_power(client)
    current_values = _holdings_values(client, cfg) or {}
    prices = _portfolio_prices(client, cfg)
    budget = min(cfg.daily_budget_krw, bp) if bp is not None else cfg.daily_budget_krw
    plan = plan_daily_buys(cfg, current_values, prices, budget) if budget > 0 else []

    if not plan:
        reason = ("매수가능금액/하루 한도로 1주도 못 삽니다" if budget <= 0 or not prices
                  else "오늘 살 게 없음 — 이미 목표 비중 도달했거나 예산 부족")
        log = executor.execute(client, cfg, state, _skip(reason))
        state.add_log(log); state.save()
        return _summary(cfg, state, [log])

    # 3. 가드레일 (킬스위치/장운영시간/하루1회/누적한도) — 계획 총액 기준 1회 체크
    total_cost = sum(item["estCost"] for item in plan)
    guard = guardrails.check(client, cfg, state, total_cost, buying_power=bp, allow_daily_repeat=manual)
    if not guard.ok:
        log = executor.execute(client, cfg, state, _skip(guard.reason))
        state.add_log(log); state.save()
        return _summary(cfg, state, [log])

    # 4. 계획 순서대로 시장가 매수 실행 (그리디라 지정가 대기 없이 즉시 체결 확정 필요)
    logs = []
    for i, item in enumerate(plan):
        d = Decision(
            "MARKET_BUY", item["quantity"], None,
            f"그리디 리밸런싱: {item['symbol']} {item['quantity']}주 (목표비중 맞춤, {item['price']:,}원 기준)",
            item["estCost"], item["symbol"],
        )
        log = executor.execute(client, cfg, state, d, seq=i)
        if log.action == "MARKET_BUY":
            _apply_optimistic_fill(state, log, item["price"], item["quantity"])
        state.add_log(log)
        logs.append(log)

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
        "symbol": cfg.symbol,
        "decision": decision,
        "filled": all(lg.filled for lg in buys) if buys else logs[-1].filled,
        "consecutiveMisses": state.consecutive_misses,
        "totalInvestedKrw": state.total_invested_krw,
        "totalFilledQty": state.total_filled_qty,
        "totalBudgetKrw": cfg.total_budget_krw,
    }

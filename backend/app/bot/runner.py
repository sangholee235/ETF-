"""한 번의 적립 tick 을 오케스트레이션한다.

순서:
1. 직전 미체결 주문 체결 확인 -> 상태 갱신
2. 전략 결정 (무슨 주문 낼지)
3. 가드레일 검증
4. 실행 (DRY_RUN/LIVE)
5. 상태/로그 저장
"""

from __future__ import annotations

from datetime import date

from tossapi import TossClient, TossApiError

from . import executor, guardrails
from .config import BotConfig
from .state import BotState
from .strategy import decide


def run_once(client: TossClient | None = None, broker: str | None = None) -> dict:
    from brokers import get_broker
    cfg = BotConfig.load(broker)
    state = BotState.load(broker)
    client = client or get_broker(broker)

    # 1. 직전 주문 체결 확인 (LIVE)
    executor.confirm_previous_fill(client, cfg, state)

    # 2. 대상 종목 선택 — 목표 비중 대비 가장 부족한 ETF (단일 종목도 100% 1개로 표현)
    #    돈이 부족하면: 살 수 있는 ETF 중 가장 부족한 걸 산다. 하나도 못 사면 SKIP.
    from .portfolio import select_target
    has_target = any(p.get("symbol") and (float(p.get("weight", 0)) > 0 or float(p.get("target", 0)) > 0)
                     for p in cfg.portfolio)
    if not has_target:
        log = executor.execute(client, cfg, state,
                               _skip(_blank(), "적립할 ETF가 없음 — ETF와 목표비중을 추가하세요"))
        state.add_log(log); state.save()
        return _summary(cfg, state, log)

    bp = _buying_power(client)
    affordable = _affordable_symbols(client, cfg, bp)
    current_values = _holdings_values(client, cfg)   # 실제 보유 평가금액 기준 비중
    pick = select_target(cfg, state, affordable, current_values)
    if pick is None:
        if affordable is not None and len(affordable) == 0:
            reason = "매수가능금액으로 살 수 있는 ETF가 없음 — 입금 필요"
        elif affordable is not None and len(affordable) > 0:
            reason = "살 수 있는 ETF는 이미 목표 비중 도달 — 목표 미달 ETF는 매수가능금액 부족(현금 모아 매수)"
        else:
            reason = "모든 ETF가 목표 비중 도달"
        log = executor.execute(client, cfg, state, _skip(_blank(), reason))
        state.add_log(log); state.save()
        return _summary(cfg, state, log)
    target_symbol = pick[0]

    # 3. 전략 결정 (하루 적립 금액과 현금 중 작은 금액 안에서 살 수 있는 만큼)
    d = decide(client, cfg, state, symbol=target_symbol, max_spend=bp)

    # 4. 가드레일
    guard = guardrails.check(client, cfg, state, d.est_cost)
    if not guard.ok:
        log = executor.execute(client, cfg, state, _skip(d, guard.reason))
        state.add_log(log)
        state.save()
        return _summary(cfg, state, log)

    # 5. 실행
    log = executor.execute(client, cfg, state, d)

    # 6. 상태 갱신
    state.last_trade_date = date.today().isoformat()
    state.last_client_order_id = log.client_order_id
    if log.action in ("LIMIT_BUY", "MARKET_BUY"):
        if cfg.dry_run:
            _simulate_dry_fill(client, cfg, state, log)
        elif log.order_id:
            state.last_open_order_id = log.order_id
    state.add_log(log)
    state.save()
    return _summary(cfg, state, log)


def _buying_power(client) -> int | None:
    """매수가능금액(원). 못 읽으면 None."""
    try:
        return int(float(client.get_buying_power("KRW")["cashBuyingPower"]))
    except (TossApiError, KeyError, ValueError, TypeError):
        return None


def _affordable_symbols(client, cfg, bp: int | None) -> set[str] | None:
    """하루 적립 금액과 현금 중 작은 금액으로 '1주 이상' 살 수 있는 종목 집합.
    매수가능금액을 못 읽으면 None(필터 안 함)."""
    if bp is None:
        return None
    cap = min(cfg.daily_budget_krw, bp)
    out: set[str] = set()
    for p in cfg.portfolio:
        sym = p.get("symbol")
        if not sym or (float(p.get("weight", 0)) <= 0 and float(p.get("target", 0)) <= 0):
            continue
        try:
            price = int(float(client.get_price(sym)["lastPrice"]))
        except (TossApiError, KeyError, ValueError, TypeError):
            continue
        if price <= cap:           # 1주라도 살 수 있으면 후보
            out.add(sym)
    return out


def _holdings_values(client, cfg) -> dict | None:
    """포트폴리오 종목의 현재 실제 보유 평가금액(원). 못 읽으면 None(누적투입 기준 폴백)."""
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


def _skip(d, reason: str):
    from .strategy import Decision
    return Decision("SKIP", 0, None, reason, 0, getattr(d, "symbol", ""))


def _blank():
    from .strategy import Decision
    return Decision("SKIP", 0, None, "", 0, "")


def _simulate_dry_fill(client: TossClient, cfg: BotConfig, state: BotState, log) -> None:
    """DRY_RUN: 현재가가 지정가 이하이면 '체결됐을 것'으로 간주해 통계 갱신."""
    if log.action == "MARKET_BUY":
        filled = True
        price = log.price or _current(client, log.symbol) or 0
    else:
        cur = _current(client, log.symbol)
        filled = cur is not None and log.price is not None and cur <= log.price
        price = log.price or 0
    log.filled = filled
    if filled:
        amount = int(price * log.quantity)
        state.total_filled_qty += log.quantity
        state.total_invested_krw += amount
        state.consecutive_misses = 0
        inv = state.portfolio_invested or {}
        inv[log.symbol] = int(inv.get(log.symbol, 0)) + amount
        state.portfolio_invested = inv
    else:
        state.consecutive_misses += 1


def _current(client: TossClient, symbol: str) -> int | None:
    try:
        p = client.get_price(symbol)
        return int(float(p["lastPrice"])) if p and p.get("lastPrice") else None
    except (TossApiError, KeyError, ValueError):
        return None


def _summary(cfg: BotConfig, state: BotState, log) -> dict:
    return {
        "mode": "DRY_RUN" if cfg.dry_run else "LIVE",
        "enabled": cfg.enabled,
        "symbol": cfg.symbol,
        "decision": {"action": log.action, "price": log.price, "reason": log.reason},
        "filled": log.filled,
        "consecutiveMisses": state.consecutive_misses,
        "totalInvestedKrw": state.total_invested_krw,
        "totalFilledQty": state.total_filled_qty,
        "totalBudgetKrw": cfg.total_budget_krw,
    }

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


def run_once(client: TossClient | None = None) -> dict:
    cfg = BotConfig.load()
    state = BotState.load()
    client = client or TossClient()

    # 1. 직전 주문 체결 확인 (LIVE)
    executor.confirm_previous_fill(client, cfg, state)

    # 2. 대상 종목 선택 (포트폴리오 모드면 가장 부족한 ETF)
    target_symbol = None
    if cfg.portfolio_mode:
        from .portfolio import select_underweight
        pick = select_underweight(cfg, state)
        if pick is None:
            log = executor.execute(client, cfg, state, _skip(_blank(), "포트폴리오가 비어 있음"))
            state.add_log(log)
            state.save()
            return _summary(cfg, state, log)
        target_symbol = pick[0]

    # 3. 전략 결정
    d = decide(client, cfg, state, symbol=target_symbol)

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

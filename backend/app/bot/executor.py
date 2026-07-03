"""주문 실행기. DRY_RUN 이면 실주문 없이 로그만, LIVE 면 멱등키 붙여 실제 주문."""

from __future__ import annotations

from datetime import date, datetime, timezone, timedelta

from tossapi import TossClient, TossApiError

from .config import BotConfig
from .state import BotState, OrderLog
from .strategy import Decision

_KST = timezone(timedelta(hours=9))


def execute(client: TossClient, cfg: BotConfig, state: BotState, d: Decision, seq: int = 0) -> OrderLog:
    today = date.today().isoformat()
    now = datetime.now(_KST).isoformat()
    mode = "DRY_RUN" if cfg.dry_run else "LIVE"
    sym = d.symbol or cfg.symbol

    if d.action == "SKIP":
        return OrderLog(now, today, mode, "SKIP", d.reason, sym)

    # 멱등키: 날짜+시각(초)+심볼+순번 (장중 여러 번 실행돼 같은 날 같은 종목이 반복될 수 있어
    # 순번만으론 다른 실행끼리 겹칠 수 있음 → 실행 시각까지 포함해 유일성 보장)
    hhmmss = datetime.now(_KST).strftime("%H%M%S")
    client_order_id = f"acc-{sym}-{today}-{hhmmss}-{seq}".replace("_", "-")

    log = OrderLog(
        ts=now, trade_date=today, mode=mode, action=d.action, reason=d.reason,
        symbol=sym, quantity=d.quantity, price=d.price,
        client_order_id=client_order_id,
    )

    if cfg.dry_run:
        log.reason = "[DRY] " + d.reason
        return log

    # --- LIVE: 실제 주문 ---
    try:
        if d.action == "LIMIT_BUY":
            res = client.create_order(
                sym, side="BUY", order_type="LIMIT",
                quantity=d.quantity, price=d.price,
                time_in_force="DAY", client_order_id=client_order_id,
            )
        else:  # MARKET_BUY
            res = client.create_order(
                sym, side="BUY", order_type="MARKET",
                quantity=d.quantity, client_order_id=client_order_id,
            )
        log.order_id = res.get("orderId")
    except TossApiError as e:
        log.action = "SKIP"
        log.reason = f"주문 실패: {e.code} {e.message}"
    return log


def confirm_previous_fill(client: TossClient, cfg: BotConfig, state: BotState) -> None:
    """직전 미체결 주문의 체결 여부를 확인해 상태(연속미체결/투입금)를 갱신한다."""
    oid = state.last_open_order_id
    if not oid or cfg.dry_run:
        return
    try:
        order = client.get_order(oid)
    except TossApiError:
        return

    exe = order.get("execution", {})
    filled_qty = int(float(exe.get("filledQuantity", "0") or 0))
    status = order.get("status")

    filled = filled_qty > 0 and status in ("FILLED", "PARTIAL_FILLED")
    if filled:
        avg = float(exe.get("averageFilledPrice") or 0)
        amount = int(avg * filled_qty)
        state.total_filled_qty += filled_qty
        state.total_invested_krw += amount
        state.consecutive_misses = 0
        # 포트폴리오 모드: 체결된 종목의 누적 투입을 기록해야 비중 추종이 동작
        sym = order.get("symbol")
        if sym:
            inv = state.portfolio_invested or {}
            inv[sym] = int(inv.get(sym, 0)) + amount
            state.portfolio_invested = inv
    else:
        state.consecutive_misses += 1

    # 해당 주문 로그의 체결 플래그 갱신 (실행 기록 '체결' 칸이 '-'로 남지 않게)
    for lg in reversed(state.logs):
        if lg.get("order_id") == oid:
            lg["filled"] = filled
            break

    state.last_open_order_id = None

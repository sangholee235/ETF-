"""가드레일: 전략과 무관한 결정론적 안전 규칙. 봇이 뭘 하든 여기서 막는다."""

from __future__ import annotations

from dataclasses import dataclass

from tossapi import TossClient, TossApiError

from .config import BotConfig
from .state import BotState


@dataclass
class GuardResult:
    ok: bool
    reason: str = ""


def check(client: TossClient, cfg: BotConfig, state: BotState, est_cost: int) -> GuardResult:
    """매수 직전 검증. ok=False 면 주문 차단."""

    if not cfg.enabled:
        return GuardResult(False, "봇이 비활성(킬스위치) 상태")

    # 누적 투입 한도 (0 = 무제한)
    if cfg.total_budget_krw > 0 and state.total_invested_krw + est_cost > cfg.total_budget_krw:
        return GuardResult(
            False,
            f"누적 투입 한도 초과 ({state.total_invested_krw}+{est_cost} > {cfg.total_budget_krw})",
        )

    # 하루 한도 (1회 매수금액이 일일 한도 초과 방지)
    if est_cost > cfg.daily_budget_krw:
        return GuardResult(
            False, f"1회 매수금액이 일일 한도 초과 ({est_cost} > {cfg.daily_budget_krw})"
        )

    # 하루 1회만
    if state.already_traded_today():
        return GuardResult(False, "오늘 이미 매수 시도함")

    # 장 운영시간
    if cfg.require_market_open and not _is_market_open(client):
        return GuardResult(False, "장 운영시간 아님")

    # 매수가능금액 (DRY_RUN 이어도 실제 잔고로 검증)
    try:
        bp = client.get_buying_power("KRW")
        if int(float(bp["cashBuyingPower"])) < est_cost:
            return GuardResult(
                False, f"매수가능금액 부족 ({bp['cashBuyingPower']} < {est_cost})"
            )
    except TossApiError as e:
        return GuardResult(False, f"매수가능금액 조회 실패: {e.code}")

    return GuardResult(True)


def _is_market_open(client: TossClient) -> bool:
    """국내 통합장(정규장) 운영 중인지. 조회 실패 시 보수적으로 False."""
    from datetime import datetime, timezone, timedelta

    try:
        cal = client.get_kr_market_calendar()
    except TossApiError:
        return False
    today = cal.get("today", {})
    integrated = today.get("integrated")
    if not integrated:
        return False
    reg = integrated.get("regularMarket")
    if not reg:
        return False
    now = datetime.now(timezone(timedelta(hours=9)))
    try:
        start = datetime.fromisoformat(reg["startTime"])
        end = datetime.fromisoformat(reg["endTime"])
    except (KeyError, ValueError):
        return False
    return start <= now <= end

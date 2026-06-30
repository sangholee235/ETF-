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


def check(client: TossClient, cfg: BotConfig, state: BotState, est_cost: int,
          buying_power: int | None = None, allow_daily_repeat: bool = False) -> GuardResult:
    """매수 직전 검증. ok=False 면 주문 차단.
    buying_power 를 미리 넘기면 매수가능금액을 중복 조회하지 않는다(미리보기용).
    allow_daily_repeat=True 면 '하루 1회' 가드를 건너뛴다(수동 적립: 미체결→취소 후 재시도용)."""

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

    # 하루 1회만 (수동 적립은 우회 — 미체결/취소 후 재시도 허용)
    if not allow_daily_repeat and state.already_traded_today():
        return GuardResult(False, "오늘 이미 매수 시도함")

    # 장 운영시간
    if cfg.require_market_open and not _is_market_open(client):
        return GuardResult(False, "장 운영시간 아님")

    # 매수가능금액 (DRY_RUN 이어도 실제 잔고로 검증)
    if buying_power is None:
        try:
            bp = client.get_buying_power("KRW")
            buying_power = int(float(bp["cashBuyingPower"]))
        except TossApiError as e:
            return GuardResult(False, f"매수가능금액 조회 실패: {e.code}")
        except Exception as e:  # 브로커 미구현/일시오류 → 500 대신 차단 사유로
            return GuardResult(False, f"매수가능금액 조회 실패: {e}")
    if buying_power < est_cost:
        return GuardResult(False, f"매수가능금액 부족 ({buying_power} < {est_cost})")

    return GuardResult(True)


def _is_market_open(client: TossClient) -> bool:
    """국내 통합장(정규장) 운영 중인지.
    캘린더 TR 미지원(키움 등)이면 KST 평일 09:00~15:30 기준으로 폴백."""
    from datetime import datetime, timezone, timedelta

    try:
        cal = client.get_kr_market_calendar()
    except TossApiError:
        return False
    except Exception:  # 브로커가 캘린더 미지원 → 시간대 폴백
        return _market_open_by_clock()
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


def _market_open_by_clock() -> bool:
    """캘린더 없이 시각만으로 정규장 추정: KST 평일 09:00~15:30."""
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone(timedelta(hours=9)))
    if now.weekday() >= 5:  # 토/일
        return False
    minutes = now.hour * 60 + now.minute
    return 9 * 60 <= minutes <= 15 * 60 + 30

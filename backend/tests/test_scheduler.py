"""스케줄러의 장중 주기적 체크 시점 판단 테스트."""

from datetime import datetime

from app.bot.scheduler import _KST, _should_check


def _dt(hh, mm, weekend=False):
    # 2026-07-06 은 월요일, 2026-07-04 는 토요일(검증됨: datetime(2026,7,6).weekday()==0)
    day = 4 if weekend else 6
    return datetime(2026, 7, day, hh, mm, tzinfo=_KST)


def test_fires_at_market_open_plus_5():
    assert _should_check(_dt(9, 5)) is True


def test_fires_every_10_min_during_market_hours():
    assert _should_check(_dt(9, 15)) is True
    assert _should_check(_dt(10, 45)) is True
    assert _should_check(_dt(9, 12)) is False  # 10분 배수 아님


def test_does_not_fire_before_open_or_after_close_buffer():
    assert _should_check(_dt(9, 0)) is False   # 아직 버퍼 전
    assert _should_check(_dt(15, 25)) is False  # 마감 버퍼 이후


def test_does_not_fire_on_weekend():
    assert _should_check(_dt(9, 5, weekend=True)) is False

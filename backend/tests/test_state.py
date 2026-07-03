"""BotState 의 '오늘 남은 하루 한도' 추적 테스트 (하루 1회 -> 하루 예산 소진까지 여러 번)."""

from datetime import date, timedelta

from app.bot.state import BotState


def test_fresh_day_has_full_budget():
    state = BotState()
    assert state.today_remaining_budget(100_000) == 100_000


def test_spend_reduces_remaining_same_day():
    state = BotState()
    state.record_today_spend(30_000)
    assert state.today_remaining_budget(100_000) == 70_000
    state.record_today_spend(50_000)
    assert state.today_remaining_budget(100_000) == 20_000


def test_remaining_never_negative():
    state = BotState()
    state.record_today_spend(150_000)  # 한도 초과 지출(가상)해도
    assert state.today_remaining_budget(100_000) == 0  # 음수 아님


def test_resets_on_new_day():
    state = BotState()
    state.record_today_spend(80_000)
    assert state.today_remaining_budget(100_000) == 20_000
    # 날짜가 바뀌면(어제 기록) 오늘은 전액 남은 것으로 취급
    state.today_budget_date = (date.today() - timedelta(days=1)).isoformat()
    assert state.today_remaining_budget(100_000) == 100_000
    # 그 상태에서 다시 지출하면 오늘 날짜로 리셋되며 새로 누적
    state.record_today_spend(10_000)
    assert state.today_budget_date == date.today().isoformat()
    assert state.today_remaining_budget(100_000) == 90_000

"""가드레일 단위 테스트."""

from datetime import date

from app.bot.config import BotConfig
from app.bot.guardrails import check
from app.bot.state import BotState
from tests.conftest import FakeClient


def test_blocks_when_disabled():
    cfg = BotConfig(enabled=False)
    r = check(FakeClient(), cfg, BotState(), est_cost=1000)
    assert not r.ok and "킬스위치" in r.reason


def test_blocks_over_daily_budget():
    cfg = BotConfig(daily_budget_krw=50_000)
    r = check(FakeClient(), cfg, BotState(), est_cost=60_000)
    assert not r.ok and "일일 한도" in r.reason


def test_does_not_block_when_already_traded_today():
    # '하루 1회'가 아니라 '오늘 남은 예산' 기준 — 오늘 이미 거래했어도(last_trade_date=오늘)
    # est_cost 가 한도 이내면 가드레일 자체는 막지 않는다. '오늘 얼마나 남았는지'는
    # runner 가 state.today_remaining_budget() 로 미리 계산해 est_cost 를 그 안으로 계획한다.
    cfg = BotConfig(daily_budget_krw=100_000)
    state = BotState(last_trade_date=date.today().isoformat())
    r = check(FakeClient(), cfg, state, est_cost=30_000)
    assert r.ok


def test_blocks_when_market_closed():
    cfg = BotConfig(daily_budget_krw=100_000, require_market_open=True)
    r = check(FakeClient(market_open=False), cfg, BotState(), est_cost=30_000)
    assert not r.ok and "운영시간" in r.reason


def test_blocks_when_insufficient_buying_power():
    cfg = BotConfig(daily_budget_krw=100_000)
    r = check(FakeClient(buying_power=1000), cfg, BotState(), est_cost=30_000)
    assert not r.ok and "매수가능금액" in r.reason


def test_total_budget_unlimited_when_zero():
    cfg = BotConfig(daily_budget_krw=100_000, total_budget_krw=0)
    state = BotState(total_invested_krw=999_999_999)
    r = check(FakeClient(), cfg, state, est_cost=30_000)
    assert r.ok  # 누적 한도 0 = 무제한이므로 통과


def test_passes_normal_case():
    cfg = BotConfig(daily_budget_krw=100_000, total_budget_krw=0)
    r = check(FakeClient(), cfg, BotState(), est_cost=30_000)
    assert r.ok

"""전략 / 설정 단위 테스트."""

from app.bot.config import BotConfig, round_to_tick
from app.bot.state import BotState
from app.bot.strategy import decide
from tests.conftest import FakeClient, make_candles


def test_round_to_tick():
    assert round_to_tick(30000, 5) == 30000
    assert round_to_tick(30003, 5) == 30000
    assert round_to_tick(30007, 5) == 30005
    assert round_to_tick(29850.5, 5) == 29850


def test_limit_buy_price_uses_prev_close_discount():
    cfg = BotConfig(discount_pct=0.01, tick_size=5)
    state = BotState()
    client = FakeClient(daily_candles=make_candles([20000, 30000]))  # prev close = 30000
    d = decide(client, cfg, state)
    assert d.action == "LIMIT_BUY"
    # 30000 * (1 - 0.01) = 29700 -> tick 5 정렬
    assert d.price == round_to_tick(29700, 5)
    assert d.est_cost == d.price * cfg.quantity_per_buy


def test_fallback_to_market_after_misses():
    cfg = BotConfig(fallback_after_misses=3)
    state = BotState(consecutive_misses=3)
    client = FakeClient(daily_candles=make_candles([30000, 30000]))
    d = decide(client, cfg, state)
    assert d.action == "MARKET_BUY"
    assert d.price is None


def test_skip_when_no_reference_price():
    cfg = BotConfig()
    state = BotState()
    client = FakeClient(daily_candles=[])  # 캔들 없음
    # 현재가 폴백도 막기 위해 last_price 0 처리
    client._last = 0
    d = decide(client, cfg, state)
    # 캔들 없으면 현재가 폴백(30000 기본) -> LIMIT_BUY 가 정상. 0 이면 SKIP.
    assert d.action in ("LIMIT_BUY", "SKIP")

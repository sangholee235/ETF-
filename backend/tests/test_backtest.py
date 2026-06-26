"""백테스트 로직 단위 테스트."""

from app.bot.backtest import run_backtest, run_sweep
from tests.conftest import FakeClient, make_candles


def test_daily_strategy_buys_every_day():
    closes = [100, 110, 120, 130]  # 4일
    client = FakeClient(daily_candles=make_candles(closes))
    res = run_backtest(client, "TEST", days=10, quantity=1, tick_size=1)
    # 단순 적립: 첫날 제외 매일 종가 매수 -> 3주
    assert res["strategyDaily"]["shares"] == 3
    # 투입 = 110+120+130 = 360, 평가 = 3 * 130 = 390
    assert res["strategyDaily"]["invested"] == 360
    assert res["strategyDaily"]["marketValue"] == 390


def test_limit_strategy_fills_only_when_low_below_limit():
    # close 는 오르지만, 저가가 지정가까지 내려오는 날만 체결
    closes = [100, 110, 120, 130]
    lows = [100, 90, 120, 90]  # 2,4일차만 크게 하락
    client = FakeClient(daily_candles=make_candles(closes, lows))
    # discount 0 -> 지정가 = 전일종가. 저가<=전일종가인 날만 체결
    res = run_backtest(client, "TEST", days=10, discount_pct=0.0,
                       fallback_after_misses=99, quantity=1, tick_size=1)
    limit = res["strategyLimit"]
    # 2일차: 전일종가100, 저가90<=100 체결 / 3일차: 전일110, 저가120>110 미체결
    # 4일차: 전일120, 저가90<=120 체결 -> 2주
    assert limit["shares"] == 2


def test_returns_period_and_comparison_keys():
    client = FakeClient(daily_candles=make_candles([100, 101, 102]))
    res = run_backtest(client, "TEST", days=10, tick_size=1)
    assert res["period"]["days"] == 3
    assert res["lowerAvgPrice"] in ("limit", "daily")
    assert "returnPct" in res["strategyLimit"]


def test_commission_increases_cost():
    closes = [100, 110, 120, 130]
    client = FakeClient(daily_candles=make_candles(closes))
    base = run_backtest(client, "TEST", days=10, quantity=1, tick_size=1, commission_pct=0.0)
    fee = run_backtest(client, "TEST", days=10, quantity=1, tick_size=1, commission_pct=0.01)
    # 수수료 1% 면 투입금이 더 크고 평단도 더 높아야 함
    assert fee["strategyDaily"]["invested"] > base["strategyDaily"]["invested"]
    assert fee["strategyDaily"]["avgPrice"] > base["strategyDaily"]["avgPrice"]


def test_sweep_returns_sorted_results():
    closes = [100, 105, 95, 110, 90, 120]
    lows = [100, 95, 90, 100, 85, 110]
    client = FakeClient(daily_candles=make_candles(closes, lows))
    res = run_sweep(client, "TEST", days=20, quantity=1, tick_size=1)
    assert res["results"]  # 적어도 한 조합 체결
    avgs = [r["avgPrice"] for r in res["results"]]
    assert avgs == sorted(avgs)  # 평단 오름차순 정렬
    assert "baselineDaily" in res

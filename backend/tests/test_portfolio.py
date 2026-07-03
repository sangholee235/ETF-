"""포트폴리오 종목 선택 테스트."""

from app.bot.config import BotConfig
from app.bot.portfolio import plan_daily_buys, select_underweight, select_waterfall, waterfall_status
from app.bot.state import BotState


def _cfg():
    return BotConfig(portfolio_mode=True, portfolio=[
        {"symbol": "069500", "name": "KODEX200", "weight": 60},
        {"symbol": "360750", "name": "S&P500", "weight": 40},
    ])


def test_empty_portfolio_returns_none():
    assert select_underweight(BotConfig(portfolio=[]), BotState()) is None


def test_picks_highest_weight_when_no_holdings():
    # 투입 0 이면 목표 비중이 큰 쪽을 먼저 채움
    sym, _ = select_underweight(_cfg(), BotState())
    assert sym == "069500"


def test_picks_underweight_symbol():
    # 069500 에 이미 많이 투입됨 -> 부족한 360750 선택
    state = BotState(portfolio_invested={"069500": 1_000_000, "360750": 0})
    sym, _ = select_underweight(_cfg(), state)
    assert sym == "360750"


def test_affordable_filter_picks_buyable_one():
    # 가장 부족한 건 069500(투입0)이지만, 살 수 있는 건 360750 뿐이면 360750 선택
    state = BotState(portfolio_invested={"069500": 0, "360750": 0})
    sym, _ = select_underweight(_cfg(), state, affordable={"360750"})
    assert sym == "360750"


def test_affordable_none_returns_none():
    # 살 수 있는 게 하나도 없으면 None (SKIP)
    assert select_underweight(_cfg(), BotState(), affordable=set()) is None


def test_wait_mode_waits_when_top_unaffordable():
    # 기다림 모드: 가장 부족한 A(069500)를 못 사면, 차순위 B 살 수 있어도 None(기다림)
    cfg = BotConfig(wait_for_underweight=True, portfolio=[
        {"symbol": "069500", "name": "A", "weight": 60},
        {"symbol": "360750", "name": "B", "weight": 40},
    ])
    assert select_underweight(cfg, BotState(), affordable={"360750"}) is None
    # 끄면(기본) 차순위 B라도 산다
    cfg2 = BotConfig(wait_for_underweight=False, portfolio=cfg.portfolio)
    sym, _ = select_underweight(cfg2, BotState(), affordable={"360750"})
    assert sym == "360750"


def test_does_not_overbuy_affordable_when_over_target():
    # 싼 B만 살 수 있는데 B가 이미 목표 비중 초과면 -> None (안 사고 기다림)
    state = BotState(portfolio_invested={"069500": 0, "360750": 500_000})  # B 100% > 목표40%
    assert select_underweight(_cfg(), state, affordable={"360750"}) is None
    # 같은 상태에서 A(부족)를 살 수 있으면 A 선택
    sym, _ = select_underweight(_cfg(), state, affordable={"069500"})
    assert sym == "069500"


def _wcfg():
    return BotConfig(fill_mode="waterfall", portfolio=[
        {"symbol": "069500", "name": "A", "target": 100000},
        {"symbol": "360750", "name": "B", "target": 50000},
    ])


def test_waterfall_fills_first_then_next():
    # 1순위(A) 미달 -> A 선택
    sym, _ = select_waterfall(_wcfg(), BotState(portfolio_invested={}))
    assert sym == "069500"
    # A 목표 채움 -> 2순위(B)로 내려감
    sym2, _ = select_waterfall(_wcfg(), BotState(portfolio_invested={"069500": 100000}))
    assert sym2 == "360750"


def test_waterfall_skips_unaffordable_to_next():
    # A 미달이지만 못 사면(affordable에 B만) B 선택
    sym, _ = select_waterfall(_wcfg(), BotState(), affordable={"360750"})
    assert sym == "360750"


def test_waterfall_status_done_active_wait():
    st = BotState(portfolio_invested={"069500": 100000, "360750": 10000})
    s = {r["symbol"]: r["status"] for r in waterfall_status(_wcfg(), st)}
    assert s["069500"] == "done" and s["360750"] == "active"


def test_converges_to_target():
    # 목표 60/40 에 근접하면, 살짝 부족한 쪽 선택
    state = BotState(portfolio_invested={"069500": 590_000, "360750": 410_000})
    sym, _ = select_underweight(_cfg(), state)
    assert sym == "069500"  # 59% < 60% 목표 -> 069500 이 더 부족


# ---------- plan_daily_buys (그리디 하루 예산 분배) ----------

def test_plan_empty_portfolio_returns_empty():
    assert plan_daily_buys(BotConfig(portfolio=[]), {}, {}, 100_000) == []


def test_plan_cold_start_splits_by_weight_not_dump():
    # 콜드스타트(투입 0)라도 예산 전체를 한 종목에 몰빵하지 않고 비중대로 나눠 산다
    cfg = _cfg()  # 069500:60, 360750:40
    prices = {"069500": 10_000, "360750": 10_000}
    plan = plan_daily_buys(cfg, {}, prices, 100_000)
    total = sum(i["estCost"] for i in plan)
    a = sum(i["estCost"] for i in plan if i["symbol"] == "069500")
    b = sum(i["estCost"] for i in plan if i["symbol"] == "360750")
    assert total == 100_000          # 예산을 다 씀(현금 안 놀림)
    assert len(plan) > 1             # 한 건에 몰빵하지 않음
    assert a / total == 0.6 and b / total == 0.4   # 정확히 목표비중대로 수렴


def test_plan_does_not_overshoot_small_deficit_with_big_budget():
    # 1%p 만 모자란데 예산이 커도, 균형 맞추는 데 필요한 만큼만 사고 그 이상은
    # 다른(이제 상대적으로 더 부족해진) 종목으로 넘어간다 — 한 종목 몰빵 없음
    cfg = BotConfig(portfolio=[
        {"symbol": "A", "name": "A", "weight": 50},
        {"symbol": "B", "name": "B", "weight": 50},
    ])
    prices = {"A": 1_000, "B": 1_000}
    # 총 100만원 중 A 49%(49만) / B 51%(51만) -> A 가 1%p 모자람. 필요금액=정확히 2만원
    current = {"A": 490_000, "B": 510_000}
    plan = plan_daily_buys(cfg, current, prices, 500_000)
    first = plan[0]
    assert first["symbol"] == "A"
    assert first["estCost"] == 20_000   # 딱 필요한 만큼만(오버슈팅 없음), 500,000 전부를 여기 쏟지 않음
    assert len(plan) > 1                # 나머지 예산은 다른 종목으로 계속 분배됨


def test_plan_stops_when_budget_too_small_for_any_share():
    cfg = _cfg()
    prices = {"069500": 100_000, "360750": 100_000}
    plan = plan_daily_buys(cfg, {}, prices, 50_000)   # 1주(10만원)도 못 사는 예산
    assert plan == []

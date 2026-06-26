"""포트폴리오 종목 선택 테스트."""

from app.bot.config import BotConfig
from app.bot.portfolio import select_underweight
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


def test_converges_to_target():
    # 목표 60/40 에 근접하면, 살짝 부족한 쪽 선택
    state = BotState(portfolio_invested={"069500": 590_000, "360750": 410_000})
    sym, _ = select_underweight(_cfg(), state)
    assert sym == "069500"  # 59% < 60% 목표 -> 069500 이 더 부족

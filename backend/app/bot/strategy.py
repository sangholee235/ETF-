"""매수전용 적립 전략: 전일종가 -X% 지정가, N일 미체결이면 시장가.

예측하지 않는다. 가격 기준값만 계산해서 '어떤 주문을 낼지' 결정한다.
"""

from __future__ import annotations

from dataclasses import dataclass

from tossapi import TossClient, TossApiError

from .config import BotConfig, round_to_tick
from .state import BotState


@dataclass
class Decision:
    action: str          # LIMIT_BUY | MARKET_BUY | SKIP
    quantity: int
    price: int | None    # 지정가 (MARKET 이면 None)
    reason: str
    est_cost: int        # 예상 비용 (가드레일/한도용)
    symbol: str = ""     # 대상 종목 (포트폴리오 모드에서 override)


def decide(client: TossClient, cfg: BotConfig, state: BotState,
           symbol: str | None = None, max_spend: int | None = None) -> Decision:
    """하루 적립 금액(daily_budget_krw) 안에서 살 수 있는 만큼 매수.
    max_spend(매수가능금액)가 있으면 둘 중 작은 금액으로 한도."""
    sym = symbol or cfg.symbol

    ref_price = _reference_price(client, sym)
    if ref_price is None or ref_price <= 0:
        return Decision("SKIP", 0, None, "기준가 조회 실패", 0, sym)

    cap = cfg.daily_budget_krw
    if max_spend is not None:
        cap = min(cap, max_spend)
    qty = int(cap // ref_price)
    if qty < 1:
        return Decision("SKIP", 0, None,
                        f"하루 적립 금액/현금({cap:,}원)으로 1주({ref_price:,}원)도 못 삽니다", 0, sym)

    # N일 연속 미체결 -> 시장가로 강제 매수 (상승장 누락 방지)
    if state.consecutive_misses >= cfg.fallback_after_misses:
        est = ref_price * qty
        return Decision(
            "MARKET_BUY", qty, None,
            f"{state.consecutive_misses}일 연속 미체결 -> 시장가 {qty}주 적립", est, sym,
        )

    # 평소: 전일종가 -discount% 아래 지정가, 하루 금액 안에서 살 수 있는 만큼.
    # 할인은 항상 0% 이상(음수 입력은 0으로) → 기준가 위로는 절대 안 올림.
    disc = max(0.0, cfg.discount_pct)
    limit = round_to_tick(ref_price * (1 - disc), cfg.tick_size)
    est = limit * qty
    return Decision(
        "LIMIT_BUY", qty, limit,
        f"기준가 {ref_price} 대비 -{disc*100:.1f}% = {limit} 지정가 {qty}주", est, sym,
    )


def _reference_price(client: TossClient, symbol: str) -> int | None:
    """기준가 = 전일(직전) 일봉 종가. 실패 시 현재가로 폴백."""
    try:
        page = client.get_candles(symbol, interval="1d", count=2)
        candles = page.get("candles", [])
        if candles:
            return int(float(candles[0]["closePrice"]))
    except (TossApiError, KeyError, ValueError):
        pass
    try:
        p = client.get_price(symbol)
        if p and p.get("lastPrice"):
            return int(float(p["lastPrice"]))
    except (TossApiError, KeyError, ValueError):
        pass
    return None

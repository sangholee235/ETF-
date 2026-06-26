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
           symbol: str | None = None) -> Decision:
    qty = cfg.quantity_per_buy
    sym = symbol or cfg.symbol

    ref_price = _reference_price(client, sym)
    if ref_price is None:
        return Decision("SKIP", 0, None, "기준가 조회 실패", 0, sym)

    # N일 연속 미체결 -> 시장가로 강제 매수 (상승장 누락 방지)
    if state.consecutive_misses >= cfg.fallback_after_misses:
        est = ref_price * qty
        return Decision(
            "MARKET_BUY", qty, None,
            f"{state.consecutive_misses}일 연속 미체결 -> 시장가 적립", est, sym,
        )

    # 평소: 전일종가 -discount% 아래 지정가
    limit = round_to_tick(ref_price * (1 - cfg.discount_pct), cfg.tick_size)
    est = limit * qty
    return Decision(
        "LIMIT_BUY", qty, limit,
        f"기준가 {ref_price} 대비 -{cfg.discount_pct*100:.1f}% = {limit} 지정가", est, sym,
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

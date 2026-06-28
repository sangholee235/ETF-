"""테스트 공용: 외부 API 없이 동작하는 FakeClient."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class FakeClient:
    """TossClient 인터페이스 일부를 흉내내는 가짜 클라이언트."""

    def __init__(
        self,
        daily_candles: list[dict] | None = None,
        buying_power: int = 10_000_000,
        market_open: bool = True,
        last_price: int = 30000,
    ):
        self._daily = daily_candles or []
        self._bp = buying_power
        self._open = market_open
        self._last = last_price

    def get_candles(self, symbol, interval="1d", count=100, before=None, adjusted=True):
        # 최신순으로 반환 (실제 API 와 동일하게 candles[0] 이 최신)
        return {"candles": list(reversed(self._daily))[:count], "nextBefore": None}

    def get_price(self, symbol):
        return {"symbol": symbol, "lastPrice": str(self._last), "currency": "KRW"}

    def get_buying_power(self, currency="KRW"):
        return {"currency": currency, "cashBuyingPower": str(self._bp)}

    def get_kr_market_calendar(self, date=None):
        # 실행 시각과 무관하게 결정적이도록 '오늘(KST) 하루 전체'를 운영시간으로 본다.
        from datetime import datetime, timezone, timedelta

        today = datetime.now(timezone(timedelta(hours=9))).date().isoformat()
        if not self._open:
            return {"today": {"date": today, "integrated": None}}
        return {
            "today": {
                "date": today,
                "integrated": {
                    "regularMarket": {
                        "startTime": f"{today}T00:00:00+09:00",
                        "endTime": f"{today}T23:59:59+09:00",
                    }
                },
            }
        }


def make_candles(closes: list[int], lows: list[int] | None = None) -> list[dict]:
    """오래된→최신 순 일봉 생성. lows 미지정 시 close 와 동일."""
    lows = lows or closes
    out = []
    for i, (c, lo) in enumerate(zip(closes, lows)):
        out.append({
            "timestamp": f"2026-06-{i + 1:02d}T09:00:00+09:00",
            "openPrice": str(c), "highPrice": str(c),
            "lowPrice": str(lo), "closePrice": str(c),
            "volume": "1000", "currency": "KRW",
        })
    return out

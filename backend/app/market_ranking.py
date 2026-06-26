"""주요 종목 랭킹.

토스 API 는 '시장 전체 순위'를 제공하지 않으므로, 큐레이션한 유니버스에 대해
현재가(prices) + 전일종가(candles)로 등락률·거래량을 직접 계산해 정렬한다.
rate limit 보호를 위해 결과를 60초 캐시한다.
"""

from __future__ import annotations

import time

from tossapi import TossApiError, TossClient

# 큐레이션 유니버스 (대형주 + 주요 ETF)
UNIVERSE = [
    "005930", "000660", "373220", "207940", "005380", "000270", "068270",
    "035420", "035720", "105560", "005490", "006400", "012330", "051910",
    "066570", "055550", "069500", "360750", "133690", "229200",
]

_CACHE_TTL = 60.0
_cache: dict = {"ts": 0.0, "data": None}


def get_ranking(client: TossClient) -> list[dict]:
    now = time.monotonic()
    if _cache["data"] is not None and now - _cache["ts"] < _CACHE_TTL:
        return _cache["data"]

    symbols = ",".join(UNIVERSE)
    prices = {p["symbol"]: p for p in client.get_prices(symbols)}
    try:
        stocks = {s["symbol"]: s for s in client.get_stocks(symbols)}
    except TossApiError:
        stocks = {}

    rows: list[dict] = []
    for sym in UNIVERSE:
        p = prices.get(sym)
        if not p or not p.get("lastPrice"):
            continue
        last = float(p["lastPrice"])
        prev_close = None
        volume = None
        try:
            page = client.get_candles(sym, interval="1d", count=2)
            candles = page.get("candles", [])
            if candles:
                volume = float(candles[0].get("volume") or 0)
            if len(candles) >= 2:
                prev_close = float(candles[1]["closePrice"])
        except (TossApiError, KeyError, ValueError):
            pass

        change_pct = ((last - prev_close) / prev_close * 100) if prev_close else None
        info = stocks.get(sym, {})
        shares = info.get("sharesOutstanding")
        market_cap = last * float(shares) if shares else None
        value = last * volume if volume else None  # 거래대금
        rows.append({
            "symbol": sym,
            "name": info.get("name", sym),
            "market": info.get("market"),
            "lastPrice": last,
            "changePct": round(change_pct, 2) if change_pct is not None else None,
            "volume": volume,
            "value": value,             # 거래대금 (현재가 × 거래량)
            "marketCap": market_cap,    # 시가총액 (현재가 × 발행주식수)
            "currency": p.get("currency", "KRW"),
        })

    _cache["data"] = rows
    _cache["ts"] = now
    return rows


# ---- 상단 지수 바 (지수 ETF 프록시 + 미니 스파크라인) ----
INDEX_PROXIES = [
    {"symbol": "069500", "label": "코스피", "proxy": "KODEX200"},
    {"symbol": "229200", "label": "코스닥", "proxy": "코스닥150"},
    {"symbol": "360750", "label": "S&P500", "proxy": "TIGER"},
    {"symbol": "133690", "label": "나스닥100", "proxy": "TIGER"},
]

_summary_cache: dict = {"ts": 0.0, "data": None}


def get_market_summary(client: TossClient) -> list[dict]:
    now = time.monotonic()
    if _summary_cache["data"] is not None and now - _summary_cache["ts"] < _CACHE_TTL:
        return _summary_cache["data"]

    out = []
    for idx in INDEX_PROXIES:
        try:
            page = client.get_candles(idx["symbol"], interval="1d", count=30)
            candles = list(reversed(page.get("candles", [])))  # 오래된→최신
            closes = [float(c["closePrice"]) for c in candles]
        except (TossApiError, KeyError, ValueError):
            closes = []
        last = closes[-1] if closes else None
        prev = closes[-2] if len(closes) >= 2 else None
        change = ((last - prev) / prev * 100) if (last and prev) else None
        out.append({
            **idx,
            "lastPrice": last,
            "changePct": round(change, 2) if change is not None else None,
            "spark": closes[-30:],
        })
    _summary_cache["data"] = out
    _summary_cache["ts"] = now
    return out

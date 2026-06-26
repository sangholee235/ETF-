"""적립 전략 백테스트.

같은 기간 동안 두 전략을 비교한다:
  A. 적립봇 전략: 전일종가 -discount% 지정가, 당일 저가<=지정가면 체결,
                  N일 연속 미체결이면 시장가(종가) 강제 매수.
  B. 단순 적립: 매일 종가에 시장가 매수 (기준선).

각 전략의 투입금/보유수량/평단/최종평가액/수익률을 계산한다.
일봉의 저가(low)로 지정가 체결 여부를 정확히 판정하므로 단타보다 신뢰도 높음.
"""

from __future__ import annotations

from tossapi import TossClient, TossApiError

from .config import round_to_tick


def _fetch_daily(client: TossClient, symbol: str, days: int) -> list[dict]:
    """일봉을 오래된→최신 순으로 최대 days 개 수집 (페이지네이션)."""
    out: list[dict] = []
    before: str | None = None
    seen: set[str] = set()
    while len(out) < days:
        page = client.get_candles(symbol, interval="1d", count=200, before=before)
        candles = page.get("candles", [])
        if not candles:
            break
        for c in candles:
            ts = c["timestamp"]
            if ts not in seen:
                seen.add(ts)
                out.append(c)
        nxt = page.get("nextBefore")
        if not nxt or len(candles) < 200:
            break
        before = nxt
    out.sort(key=lambda c: c["timestamp"])
    return out[-days:]


def _simulate_limit(candles, discount_pct, fallback_after_misses, quantity, tick_size,
                    commission_pct=0.0):
    """지정가 적립 전략 시뮬레이션. (shares, cost, buys, market_fallbacks) 반환.

    cost 는 매수 수수료(commission_pct, 소수비율) 포함.
    """
    fee = 1 + commission_pct
    shares = 0
    cost = 0.0
    buys = 0
    market = 0
    misses = 0
    for i in range(1, len(candles)):
        prev_close = float(candles[i - 1]["closePrice"])
        low = float(candles[i]["lowPrice"])
        close = float(candles[i]["closePrice"])
        if misses >= fallback_after_misses:
            shares += quantity
            cost += close * quantity * fee
            buys += 1
            market += 1
            misses = 0
        else:
            limit = round_to_tick(prev_close * (1 - discount_pct), tick_size)
            if low <= limit:
                shares += quantity
                cost += limit * quantity * fee
                buys += 1
                misses = 0
            else:
                misses += 1
    return shares, cost, buys, market


def run_sweep(
    client: TossClient,
    symbol: str,
    days: int = 120,
    discounts: list[float] | None = None,
    fallbacks: list[int] | None = None,
    quantity: int = 1,
    tick_size: int = 5,
    commission_pct: float = 0.0,
) -> dict:
    """여러 (할인%, 전환일) 조합을 한 번에 백테스트해 평단 기준 정렬."""
    discounts = discounts or [0.0, 0.003, 0.005, 0.01, 0.02]
    fallbacks = fallbacks or [3, 5, 10]
    candles = _fetch_daily(client, symbol, days)
    if len(candles) < 2:
        raise TossApiError(0, code="insufficient-data", message="백테스트할 일봉이 부족합니다.")
    last_close = float(candles[-1]["closePrice"])

    rows = []
    for disc in discounts:
        for fb in fallbacks:
            shares, cost, buys, market = _simulate_limit(
                candles, disc, fb, quantity, tick_size, commission_pct)
            if not shares:
                continue
            avg = cost / shares
            value = shares * last_close
            rows.append({
                "discountPct": round(disc * 100, 2),
                "fallback": fb,
                "shares": shares,
                "buys": buys,
                "marketFallbacks": market,
                "avgPrice": round(avg, 2),
                "returnPct": round((value - cost) / cost * 100, 2) if cost else 0,
            })
    rows.sort(key=lambda r: r["avgPrice"])  # 평단 낮은 순(좋은 순)

    # 단순 매일 적립 기준선
    b_shares = (len(candles) - 1) * quantity
    b_cost = sum(float(c["closePrice"]) for c in candles[1:]) * quantity * (1 + commission_pct)
    baseline = {
        "avgPrice": round(b_cost / b_shares, 2) if b_shares else 0,
        "returnPct": round((b_shares * last_close - b_cost) / b_cost * 100, 2) if b_cost else 0,
    }

    return {
        "symbol": symbol,
        "period": {"from": candles[0]["timestamp"][:10], "to": candles[-1]["timestamp"][:10], "days": len(candles)},
        "lastClose": round(last_close),
        "baselineDaily": baseline,
        "results": rows,
    }


def run_backtest(
    client: TossClient,
    symbol: str,
    days: int = 120,
    discount_pct: float = 0.005,
    fallback_after_misses: int = 5,
    quantity: int = 1,
    tick_size: int = 5,
    commission_pct: float = 0.0,
) -> dict:
    candles = _fetch_daily(client, symbol, days)
    if len(candles) < 2:
        raise TossApiError(0, code="insufficient-data", message="백테스트할 일봉이 부족합니다.")
    fee = 1 + commission_pct

    # 전략 A
    a_shares = 0
    a_cost = 0.0
    a_buys = 0
    a_market_buys = 0
    misses = 0
    # 전략 B
    b_shares = 0
    b_cost = 0.0

    series: list[dict] = []  # 일자별 평단/종가 추이 (차트용)

    for i in range(1, len(candles)):
        prev_close = float(candles[i - 1]["closePrice"])
        low = float(candles[i]["lowPrice"])
        close = float(candles[i]["closePrice"])

        # B: 매일 종가 매수
        b_shares += quantity
        b_cost += close * quantity * fee

        # A: 지정가 또는 시장가 폴백
        if misses >= fallback_after_misses:
            a_shares += quantity
            a_cost += close * quantity * fee
            a_buys += 1
            a_market_buys += 1
            misses = 0
        else:
            limit = round_to_tick(prev_close * (1 - discount_pct), tick_size)
            if low <= limit:
                a_shares += quantity
                a_cost += limit * quantity * fee
                a_buys += 1
                misses = 0
            else:
                misses += 1

        series.append({
            "date": candles[i]["timestamp"][:10],
            "price": round(close),
            "limitAvg": round(a_cost / a_shares, 2) if a_shares else None,
            "dailyAvg": round(b_cost / b_shares, 2) if b_shares else None,
        })

    last_close = float(candles[-1]["closePrice"])

    def summarize(shares: int, cost: float) -> dict:
        value = shares * last_close
        avg = cost / shares if shares else 0.0
        ret = (value - cost) / cost if cost else 0.0
        return {
            "shares": shares,
            "invested": round(cost),
            "avgPrice": round(avg, 2),
            "marketValue": round(value),
            "profit": round(value - cost),
            "returnPct": round(ret * 100, 2),
        }

    a = summarize(a_shares, a_cost)
    b = summarize(b_shares, b_cost)
    a["buys"] = a_buys
    a["marketFallbacks"] = a_market_buys
    a["tradingDays"] = len(candles) - 1
    b["buys"] = len(candles) - 1

    return {
        "symbol": symbol,
        "period": {
            "from": candles[0]["timestamp"][:10],
            "to": candles[-1]["timestamp"][:10],
            "days": len(candles),
        },
        "params": {
            "discountPct": discount_pct * 100,
            "fallbackAfterMisses": fallback_after_misses,
            "quantity": quantity,
        },
        "lastClose": round(last_close),
        "strategyLimit": a,      # 적립봇 전략
        "strategyDaily": b,      # 단순 매일 적립
        # 평단이 더 낮은 쪽이 유리 (같은 수량 가정이 아니므로 평단으로 비교)
        "lowerAvgPrice": "limit" if a["avgPrice"] and a["avgPrice"] < b["avgPrice"] else "daily",
        "series": series,        # 일자별 평단/종가 추이 (차트용)
    }

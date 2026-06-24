"""시세 / 종목정보 / 시장정보 라우터 (조회 전용)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from tossapi import TossClient, TossApiError

from ..deps import get_client, to_http

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/prices")
def prices(symbols: str = Query(..., description="콤마 구분 심볼"),
           client: TossClient = Depends(get_client)):
    try:
        return client.get_prices(symbols)
    except TossApiError as e:
        raise to_http(e)


@router.get("/orderbook")
def orderbook(symbol: str, client: TossClient = Depends(get_client)):
    try:
        return client.get_orderbook(symbol)
    except TossApiError as e:
        raise to_http(e)


@router.get("/trades")
def trades(symbol: str, count: int = 50, client: TossClient = Depends(get_client)):
    try:
        return client.get_trades(symbol, count)
    except TossApiError as e:
        raise to_http(e)


@router.get("/candles")
def candles(symbol: str, interval: str = "1d", count: int = 100,
            before: str | None = None, adjusted: bool = True,
            client: TossClient = Depends(get_client)):
    try:
        return client.get_candles(symbol, interval, count, before, adjusted)
    except TossApiError as e:
        raise to_http(e)


@router.get("/stocks")
def stocks(symbols: str, client: TossClient = Depends(get_client)):
    try:
        return client.get_stocks(symbols)
    except TossApiError as e:
        raise to_http(e)


@router.get("/price-limits")
def price_limits(symbol: str, client: TossClient = Depends(get_client)):
    try:
        return client.get_price_limits(symbol)
    except TossApiError as e:
        raise to_http(e)

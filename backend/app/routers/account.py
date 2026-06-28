"""계좌 / 자산 / 주문전 정보 라우터 (조회 전용)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from tossapi import TossClient, TossApiError

from ..deps import client_dep, to_http

router = APIRouter(prefix="/api/account", tags=["account"])


@router.get("/accounts")
def accounts(client: TossClient = Depends(client_dep)):
    try:
        return client.get_accounts()
    except TossApiError as e:
        raise to_http(e)


@router.get("/holdings")
def holdings(symbol: str | None = None, client: TossClient = Depends(client_dep)):
    try:
        return client.get_holdings(symbol)
    except TossApiError as e:
        raise to_http(e)


@router.get("/buying-power")
def buying_power(currency: str = "KRW", client: TossClient = Depends(client_dep)):
    try:
        return client.get_buying_power(currency)
    except TossApiError as e:
        raise to_http(e)


@router.get("/sellable-quantity")
def sellable_quantity(symbol: str, client: TossClient = Depends(client_dep)):
    try:
        return client.get_sellable_quantity(symbol)
    except TossApiError as e:
        raise to_http(e)


@router.get("/commissions")
def commissions(client: TossClient = Depends(client_dep)):
    try:
        return client.get_commissions()
    except TossApiError as e:
        raise to_http(e)

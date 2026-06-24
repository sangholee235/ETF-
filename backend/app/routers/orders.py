"""주문 라우터. 실제 매매는 계좌에 직접 영향 — 추후 가드레일 추가 예정.

현재는 조회만 노출하고, 생성/정정/취소는 주석으로 막아둔다 (2단계에서 활성화).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from tossapi import TossClient, TossApiError

from ..deps import get_client, to_http

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.get("")
def list_orders(status: str = "OPEN", symbol: str | None = None,
                client: TossClient = Depends(get_client)):
    try:
        return client.get_orders(status=status, symbol=symbol)
    except TossApiError as e:
        raise to_http(e)


@router.get("/{order_id}")
def get_order(order_id: str, client: TossClient = Depends(get_client)):
    try:
        return client.get_order(order_id)
    except TossApiError as e:
        raise to_http(e)


# --- 실주문 (2단계에서 가드레일과 함께 활성화) ---
# from pydantic import BaseModel
# class CreateOrderBody(BaseModel):
#     symbol: str; side: str; orderType: str = "LIMIT"
#     quantity: str | None = None; price: str | None = None
# @router.post("")
# def create_order(body: CreateOrderBody, client: TossClient = Depends(get_client)):
#     ...

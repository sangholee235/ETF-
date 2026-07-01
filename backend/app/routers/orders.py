"""주문 라우터. 실제 매매는 계좌에 직접 영향 — 추후 가드레일 추가 예정.

현재는 조회만 노출하고, 생성/정정/취소는 주석으로 막아둔다 (2단계에서 활성화).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from tossapi import TossClient, TossApiError

from ..deps import client_dep, to_http

router = APIRouter(prefix="/api/orders", tags=["orders"])


class BuyOrder(BaseModel):
    symbol: str
    quantity: int
    price: int | None = None        # 지정가(원). 시장가면 None
    orderType: str = "LIMIT"        # LIMIT | MARKET


@router.post("")
def place_buy(body: BuyOrder, client: TossClient = Depends(client_dep)):
    """수동 매수 주문 (매수 전용). 대시보드에서 가격 직접 지정해 매수할 때 사용."""
    if body.quantity < 1:
        raise HTTPException(status_code=400, detail="수량은 1주 이상이어야 합니다.")
    try:
        return client.create_order(
            body.symbol, side="BUY", order_type=body.orderType,
            quantity=body.quantity, price=body.price, time_in_force="DAY",
        )
    except TossApiError as e:
        raise to_http(e)
    except (RuntimeError, ValueError, NotImplementedError) as e:
        raise HTTPException(status_code=400, detail=str(e) or "주문 실패")


@router.get("")
def list_orders(status: str = "OPEN", symbol: str | None = None,
                client: TossClient = Depends(client_dep)):
    try:
        return client.get_orders(status=status, symbol=symbol)
    except TossApiError as e:
        raise to_http(e)


@router.get("/{order_id}")
def get_order(order_id: str, client: TossClient = Depends(client_dep)):
    try:
        return client.get_order(order_id)
    except TossApiError as e:
        raise to_http(e)


@router.post("/{order_id}/cancel")
def cancel_order(order_id: str, client: TossClient = Depends(client_dep)):
    """미체결 주문 취소 (잔량 전부). 토스/키움 공통."""
    try:
        return client.cancel_order(order_id)
    except TossApiError as e:
        raise to_http(e)
    except (NotImplementedError, RuntimeError) as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e) or "취소를 지원하지 않습니다.")


# --- 실주문 (2단계에서 가드레일과 함께 활성화) ---
# from pydantic import BaseModel
# class CreateOrderBody(BaseModel):
#     symbol: str; side: str; orderType: str = "LIMIT"
#     quantity: str | None = None; price: str | None = None
# @router.post("")
# def create_order(body: CreateOrderBody, client: TossClient = Depends(client_dep)):
#     ...

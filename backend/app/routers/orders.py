from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.core.db import SessionDep
from app.schemas.order import OrderResponse
from app.services import orders as order_service

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("/{order_id}")
async def get_order(order_id: UUID, session: SessionDep) -> OrderResponse:
    order = await order_service.get_order(session, order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    return OrderResponse.model_validate(order)

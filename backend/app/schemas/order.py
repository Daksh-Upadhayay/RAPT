from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.enums import OrderStatus


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    item_name: str
    status: OrderStatus
    tracking_number: str | None
    # Decimal (serialized as a JSON string, e.g. "49.99") so money never goes through float
    amount: Decimal
    order_date: date
    expected_delivery: date | None

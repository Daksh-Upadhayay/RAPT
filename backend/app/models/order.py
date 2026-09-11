import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import OrderStatus
from app.models.base import (
    Base,
    check_in,
    same_tenant_fk,
    tenant_id_column,
    tenant_key,
    uuid_pk,
)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        check_in("status", OrderStatus),
        tenant_key("orders"),
        same_tenant_fk("customer_id", "customers"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_id_column()
    customer_id: Mapped[uuid.UUID] = mapped_column(index=True)
    item_name: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    tracking_number: Mapped[str | None] = mapped_column(Text)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    order_date: Mapped[date] = mapped_column(Date)
    expected_delivery: Mapped[date | None] = mapped_column(Date)

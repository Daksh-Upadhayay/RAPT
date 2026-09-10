import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import OrderStatus
from app.models.base import Base, check_in, uuid_pk


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (check_in("status", OrderStatus),)

    id: Mapped[uuid.UUID] = uuid_pk()
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), index=True)
    item_name: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    tracking_number: Mapped[str | None] = mapped_column(Text)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    order_date: Mapped[date] = mapped_column(Date)
    expected_delivery: Mapped[date | None] = mapped_column(Date)

import uuid
from datetime import datetime

from sqlalchemy import Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    created_at_column,
    tenant_id_column,
    tenant_key,
    uuid_pk,
)


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        tenant_key("customers"),
        UniqueConstraint("tenant_id", "email", name="uq_customers_tenant_id_email"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_id_column()
    name: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(Text)  # unique per tenant
    created_at: Mapped[datetime] = created_at_column()

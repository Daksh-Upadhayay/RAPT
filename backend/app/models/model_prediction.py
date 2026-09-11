import uuid
from datetime import datetime

from sqlalchemy import Float, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import ModelName
from app.models.base import (
    Base,
    check_in,
    created_at_column,
    same_tenant_fk,
    tenant_id_column,
    uuid_pk,
)


class ModelPrediction(Base):
    __tablename__ = "model_predictions"
    __table_args__ = (same_tenant_fk("ticket_id", "tickets"), check_in("model_name", ModelName),)

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_id_column()
    ticket_id: Mapped[uuid.UUID] = mapped_column(index=True)
    model_name: Mapped[str] = mapped_column(Text)
    model_version: Mapped[str] = mapped_column(Text)
    prediction: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = created_at_column()

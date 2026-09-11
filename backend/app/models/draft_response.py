import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    created_at_column,
    same_tenant_fk,
    tenant_id_column,
    uuid_pk,
)


class DraftResponse(Base):
    __tablename__ = "draft_responses"
    __table_args__ = (same_tenant_fk("ticket_id", "tickets"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_id_column()
    ticket_id: Mapped[uuid.UUID] = mapped_column(index=True)
    draft_text: Mapped[str] = mapped_column(Text)
    # approved/edited_text/reviewer_id/reviewed_at stay null until a human reviews it
    approved: Mapped[bool | None] = mapped_column(Boolean)
    edited_text: Mapped[str | None] = mapped_column(Text)
    reviewer_id: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_column()

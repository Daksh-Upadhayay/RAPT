import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import TicketCategory, TicketStatus, TicketUrgency
from app.models.agent_log import AgentLog
from app.models.base import Base, check_in, created_at_column, uuid_pk
from app.models.draft_response import DraftResponse
from app.models.order import Order


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        check_in("category", TicketCategory),
        check_in("urgency", TicketUrgency),
        check_in("status", TicketStatus),
        check_in("corrected_category", TicketCategory),
        check_in("corrected_urgency", TicketUrgency),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), index=True)
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id"), index=True)
    subject: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    # category/urgency are null until the Triage Agent runs
    category: Mapped[str | None] = mapped_column(Text)
    urgency: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default=TicketStatus.NEW.value, index=True)
    # null until the Escalation Agent runs; escalated tickets still go through review
    needs_escalation: Mapped[bool | None] = mapped_column(Boolean)
    escalation_reason: Mapped[str | None] = mapped_column(Text)
    # A reviewer's correction of the Triage Agent (Phase 6). category/urgency keep the
    # model's labels; each corrected_* is null unless the reviewer chose a different value.
    corrected_category: Mapped[str | None] = mapped_column(Text)
    corrected_urgency: Mapped[str | None] = mapped_column(Text)
    corrected_by: Mapped[str | None] = mapped_column(Text)
    corrected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # lazy="raise": async sessions can't lazy-load, so every load must be explicit
    order: Mapped[Order | None] = relationship(lazy="raise")
    agent_logs: Mapped[list[AgentLog]] = relationship(lazy="raise", order_by=AgentLog.created_at)
    draft_responses: Mapped[list[DraftResponse]] = relationship(
        lazy="raise", order_by=DraftResponse.created_at
    )

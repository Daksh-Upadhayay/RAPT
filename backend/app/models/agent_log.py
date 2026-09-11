import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import AgentName
from app.models.base import (
    Base,
    check_in,
    created_at_column,
    same_tenant_fk,
    tenant_id_column,
    uuid_pk,
)


class AgentLog(Base):
    __tablename__ = "agent_logs"
    __table_args__ = (same_tenant_fk("ticket_id", "tickets"), check_in("agent_name", AgentName),)

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_id_column()
    ticket_id: Mapped[uuid.UUID] = mapped_column(index=True)
    agent_name: Mapped[str] = mapped_column(Text)
    input: Mapped[dict[str, Any]] = mapped_column(JSONB)
    output: Mapped[dict[str, Any]] = mapped_column(JSONB)
    tool_calls: Mapped[list[Any] | None] = mapped_column(JSONB)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = created_at_column()

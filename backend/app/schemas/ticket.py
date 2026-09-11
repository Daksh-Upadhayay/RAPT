from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import AgentName, TicketCategory, TicketStatus, TicketUrgency
from app.schemas.order import OrderResponse


class TicketCreate(BaseModel):
    customer_id: UUID
    subject: str = Field(min_length=1)
    body: str = Field(min_length=1)
    order_id: UUID | None = None


class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    order_id: UUID | None
    subject: str
    body: str
    category: TicketCategory | None
    urgency: TicketUrgency | None
    status: TicketStatus
    needs_escalation: bool | None
    escalation_reason: str | None
    # Reviewer's correction of the triage (null = no correction); see models/ticket.py
    corrected_category: TicketCategory | None
    corrected_urgency: TicketUrgency | None
    corrected_by: str | None
    corrected_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AgentLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_name: AgentName
    input: dict[str, Any]
    output: dict[str, Any]
    tool_calls: list[Any] | None
    duration_ms: int | None
    created_at: datetime


class DraftResponseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    draft_text: str
    approved: bool | None
    edited_text: str | None
    reviewer_id: str | None
    reviewed_at: datetime | None
    created_at: datetime


class TicketDetailResponse(TicketResponse):
    order: OrderResponse | None
    draft_responses: list[DraftResponseRead]
    agent_logs: list[AgentLogResponse]

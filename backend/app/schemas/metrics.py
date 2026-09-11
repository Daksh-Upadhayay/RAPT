from datetime import date
from typing import Literal

from pydantic import BaseModel

from app.core.enums import TicketCategory, TicketStatus


class CategoryCount(BaseModel):
    category: TicketCategory
    count: int


class DailyEscalation(BaseModel):
    date: date  # UTC day the tickets were created
    processed: int  # tickets the Escalation Agent decided on
    escalated: int
    rate: float | None  # escalated / processed; null on days with nothing processed


class ReviewOutcome(BaseModel):
    """Reviewed drafts by outcome, split by whether the ticket was flagged for escalation."""

    outcome: Literal["approved_as_is", "edited"]
    escalated: int
    not_escalated: int


class CategoryResolution(BaseModel):
    category: TicketCategory
    resolved: int
    avg_resolution_seconds: float | None  # ticket created -> draft approved; null if none resolved


class MetricsSummary(BaseModel):
    total_tickets: int
    tickets_by_status: dict[TicketStatus, int]
    tickets_by_category: list[CategoryCount]  # triaged tickets only
    escalation_rate: float | None  # escalated / tickets the Escalation Agent decided on
    escalation_by_day: list[DailyEscalation]  # one row per day of the window, oldest first
    drafts_reviewed: int
    approval_rate: float | None  # approved as-is / reviewed
    review_outcomes: list[ReviewOutcome]
    avg_resolution_seconds: float | None
    resolution_by_category: list[CategoryResolution]

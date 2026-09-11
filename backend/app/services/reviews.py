"""Human-in-the-loop review: nothing is sent to a customer without a reviewer approving it."""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import case, func, nulls_last, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import TicketStatus, TicketUrgency
from app.models import DraftResponse, Ticket
from app.schemas.review import TriageCorrectionRequest


class TicketNotFound(Exception):
    pass


class ReviewConflict(Exception):
    """The ticket isn't in a reviewable state (not awaiting review, or no pending draft)."""


async def review_queue(session: AsyncSession) -> Sequence[Ticket]:
    """Tickets awaiting review: escalated first, then by urgency (a reviewer's correction
    wins over the model's), then oldest first."""
    urgency_rank = case(
        {TicketUrgency.HIGH.value: 0, TicketUrgency.MEDIUM.value: 1, TicketUrgency.LOW.value: 2},
        value=func.coalesce(Ticket.corrected_urgency, Ticket.urgency),
        else_=3,
    )
    stmt = (
        select(Ticket)
        .where(Ticket.status == TicketStatus.AWAITING_REVIEW)
        .order_by(nulls_last(Ticket.needs_escalation.desc()), urgency_rank, Ticket.created_at)
    )
    return (await session.scalars(stmt)).all()


async def _pending_draft(session: AsyncSession, ticket_id: UUID) -> tuple[Ticket, DraftResponse]:
    ticket = await session.get(Ticket, ticket_id)
    if ticket is None:
        raise TicketNotFound
    if ticket.status != TicketStatus.AWAITING_REVIEW:
        raise ReviewConflict(f"Ticket is {ticket.status}, not awaiting review")
    # After a rerun the newest draft is the one under review
    draft = await session.scalar(
        select(DraftResponse)
        .where(DraftResponse.ticket_id == ticket_id)
        .order_by(DraftResponse.created_at.desc())
        .limit(1)
    )
    if draft is None or draft.approved is not None:
        raise ReviewConflict("Ticket has no draft awaiting review; rerun the agents to create one")
    return ticket, draft


async def approve(session: AsyncSession, ticket_id: UUID, reviewer_id: str, edited_text: str | None = None) -> None:
    """Approve the latest draft as-is, or with the reviewer's edits, and resolve the ticket."""
    ticket, draft = await _pending_draft(session, ticket_id)
    draft.approved = True
    draft.edited_text = edited_text
    draft.reviewer_id = reviewer_id
    draft.reviewed_at = datetime.now(UTC)
    ticket.status = TicketStatus.RESOLVED
    await session.commit()


class NotTriaged(Exception):
    """The Triage Agent hasn't labelled the ticket yet, so there is nothing to correct."""


async def correct_triage(session: AsyncSession, ticket_id: UUID, data: TriageCorrectionRequest) -> None:
    """Record the reviewer's category/urgency, replacing any earlier correction.

    A value equal to the model's label is stored as null: only disagreements are
    corrections, and only they become training rows (scripts/export_feedback.py).
    """
    ticket = await session.get(Ticket, ticket_id)
    if ticket is None:
        raise TicketNotFound
    if ticket.category is None or ticket.urgency is None:
        raise NotTriaged
    category = data.corrected_category if data.corrected_category != ticket.category else None
    urgency = data.corrected_urgency if data.corrected_urgency != ticket.urgency else None
    ticket.corrected_category, ticket.corrected_urgency = category, urgency
    corrected = category is not None or urgency is not None
    ticket.corrected_by = data.reviewer_id if corrected else None
    ticket.corrected_at = datetime.now(UTC) if corrected else None
    await session.commit()

from datetime import UTC, date, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Customer, DraftResponse, Ticket
from app.services import metrics as metrics_service

TODAY = date(2026, 9, 10)


def at(day: date, hour: int = 12) -> datetime:
    return datetime(day.year, day.month, day.day, hour, tzinfo=UTC)


async def add_ticket(
    session: AsyncSession,
    customer: Customer,
    *,
    created: datetime,
    status: str = "awaiting_review",
    category: str | None = "refund_request",
    escalated: bool | None = False,
    review: tuple[timedelta, str | None] | None = None,  # (time to approval, edited text)
) -> Ticket:
    ticket = Ticket(
        customer_id=customer.id,
        subject="s",
        body="b",
        status=status,
        category=category,
        needs_escalation=escalated,
        created_at=created,
    )
    session.add(ticket)
    await session.flush()
    draft = DraftResponse(ticket_id=ticket.id, draft_text="draft")
    if review is not None:
        delay, edited = review
        draft.approved, draft.edited_text, draft.reviewer_id, draft.reviewed_at = True, edited, "r1", created + delay
    session.add(draft)
    await session.commit()
    return ticket


async def test_empty_database_gives_zeroes_and_nulls(session: AsyncSession) -> None:
    summary = await metrics_service.summary(session, days=3, today=TODAY)

    assert summary.total_tickets == 0
    assert set(summary.tickets_by_status.values()) == {0}
    assert all(c.count == 0 for c in summary.tickets_by_category)
    assert summary.escalation_rate is None
    assert summary.approval_rate is None
    assert summary.avg_resolution_seconds is None
    assert [d.date for d in summary.escalation_by_day] == [date(2026, 9, 8), date(2026, 9, 9), TODAY]
    assert all(d.rate is None for d in summary.escalation_by_day)


async def test_summary_aggregates(session: AsyncSession, customer: Customer) -> None:
    yesterday = TODAY - timedelta(days=1)
    # Resolved: as-is in 1 h, edited in 3 h (escalated), as-is in 2 h (damaged_item)
    await add_ticket(session, customer, created=at(yesterday), status="resolved", review=(timedelta(hours=1), None))
    await add_ticket(
        session, customer, created=at(TODAY), status="resolved", escalated=True, review=(timedelta(hours=3), "fixed")
    )
    await add_ticket(
        session, customer, created=at(TODAY), status="resolved", category="damaged_item", review=(timedelta(hours=2), None)
    )
    # Awaiting review, escalated; and one still running (not triaged or decided yet)
    await add_ticket(session, customer, created=at(TODAY), escalated=True)
    await add_ticket(session, customer, created=at(TODAY), status="in_progress", category=None, escalated=None)

    s = await metrics_service.summary(session, days=2, today=TODAY)

    assert s.total_tickets == 5
    assert s.tickets_by_status == {"new": 0, "in_progress": 1, "awaiting_review": 1, "resolved": 3}
    counts = {c.category: c.count for c in s.tickets_by_category}
    assert counts["refund_request"] == 3 and counts["damaged_item"] == 1 and counts["cancellation"] == 0
    assert s.escalation_rate == pytest.approx(2 / 4)  # the running ticket isn't decided yet
    assert [(d.date, d.processed, d.escalated) for d in s.escalation_by_day] == [(yesterday, 1, 0), (TODAY, 3, 2)]
    assert s.escalation_by_day[1].rate == pytest.approx(2 / 3)

    assert s.drafts_reviewed == 3
    assert s.approval_rate == pytest.approx(2 / 3)
    outcomes = {o.outcome: (o.escalated, o.not_escalated) for o in s.review_outcomes}
    assert outcomes == {"approved_as_is": (0, 2), "edited": (1, 0)}

    assert s.avg_resolution_seconds == pytest.approx(2 * 3600)
    resolution = {r.category: (r.resolved, r.avg_resolution_seconds) for r in s.resolution_by_category}
    assert resolution["refund_request"] == (2, pytest.approx(2 * 3600))
    assert resolution["damaged_item"] == (1, pytest.approx(2 * 3600))
    assert resolution["cancellation"] == (0, None)


async def test_only_the_approved_draft_counts_after_a_rerun(session: AsyncSession, customer: Customer) -> None:
    ticket = await add_ticket(session, customer, created=at(TODAY), status="resolved", review=(timedelta(hours=1), None))
    session.add(DraftResponse(ticket_id=ticket.id, draft_text="older draft, never reviewed"))
    await session.commit()

    s = await metrics_service.summary(session, days=1, today=TODAY)

    assert s.drafts_reviewed == 1


async def test_endpoint_returns_summary(client: AsyncClient) -> None:
    resp = await client.get("/metrics/summary", params={"days": 7})

    assert resp.status_code == 200
    assert len(resp.json()["escalation_by_day"]) == 7
    assert (await client.get("/metrics/summary", params={"days": 0})).status_code == 422

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Customer, DraftResponse, Ticket


async def add_ticket(session: AsyncSession, customer: Customer, **fields) -> Ticket:
    ticket = Ticket(customer_id=customer.id, subject="Help", body="Please help", **fields)
    session.add(ticket)
    await session.commit()
    return ticket


async def add_draft(session: AsyncSession, ticket: Ticket, text: str = "Draft reply") -> DraftResponse:
    draft = DraftResponse(ticket_id=ticket.id, draft_text=text)
    session.add(draft)
    await session.commit()
    return draft


async def test_queue_lists_awaiting_review_escalated_then_by_urgency(
    client: AsyncClient, session: AsyncSession, customer: Customer
) -> None:
    low = await add_ticket(session, customer, status="awaiting_review", urgency="low", needs_escalation=False)
    high = await add_ticket(session, customer, status="awaiting_review", urgency="high", needs_escalation=False)
    escalated = await add_ticket(session, customer, status="awaiting_review", urgency="low", needs_escalation=True)
    await add_ticket(session, customer, status="resolved", urgency="high")
    await add_ticket(session, customer, status="new")

    resp = await client.get("/reviews/queue")

    assert resp.status_code == 200
    assert [t["id"] for t in resp.json()] == [str(escalated.id), str(high.id), str(low.id)]


async def test_approve_resolves_ticket_and_approves_latest_draft(
    client: AsyncClient, session: AsyncSession, customer: Customer
) -> None:
    ticket = await add_ticket(session, customer, status="awaiting_review")
    await add_draft(session, ticket, "Older draft")
    await add_draft(session, ticket, "Latest draft")

    resp = await client.post(f"/reviews/{ticket.id}/approve", json={"reviewer_id": "agent-7"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "resolved"
    older, latest = data["draft_responses"]
    assert older["approved"] is None
    assert latest["approved"] is True
    assert latest["reviewer_id"] == "agent-7"
    assert latest["edited_text"] is None
    assert latest["reviewed_at"] is not None


async def test_edit_stores_the_reviewers_text(client: AsyncClient, session: AsyncSession, customer: Customer) -> None:
    ticket = await add_ticket(session, customer, status="awaiting_review")
    await add_draft(session, ticket)

    resp = await client.post(
        f"/reviews/{ticket.id}/edit", json={"edited_text": "Better reply", "reviewer_id": "agent-7"}
    )

    assert resp.status_code == 200
    (draft,) = resp.json()["draft_responses"]
    assert draft["approved"] is True
    assert draft["edited_text"] == "Better reply"


@pytest.mark.parametrize(
    ("ticket_fields", "with_draft"),
    [
        ({"status": "resolved"}, True),  # already reviewed
        ({"status": "in_progress"}, True),  # agents still running
        ({"status": "awaiting_review"}, False),  # failed run left no draft
    ],
)
async def test_cannot_review_ticket_that_is_not_reviewable(
    client: AsyncClient, session: AsyncSession, customer: Customer, ticket_fields: dict, with_draft: bool
) -> None:
    ticket = await add_ticket(session, customer, **ticket_fields)
    if with_draft:
        await add_draft(session, ticket)

    resp = await client.post(f"/reviews/{ticket.id}/approve", json={"reviewer_id": "agent-7"})

    assert resp.status_code == 409


async def test_review_validation_and_unknown_ticket(client: AsyncClient) -> None:
    unknown = "00000000-0000-0000-0000-000000000000"
    assert (await client.post(f"/reviews/{unknown}/approve", json={"reviewer_id": "a"})).status_code == 404
    resp = await client.post(f"/reviews/{unknown}/edit", json={"edited_text": "", "reviewer_id": "a"})
    assert resp.status_code == 422

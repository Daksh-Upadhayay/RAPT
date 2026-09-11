import httpx
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

    resp = await client.post(f"/reviews/{ticket.id}/approve")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "resolved"
    older, latest = data["draft_responses"]
    assert older["approved"] is None
    assert latest["approved"] is True
    assert latest["reviewer_id"] == "ada@acme.example"  # the signed-in user
    assert latest["edited_text"] is None
    assert latest["reviewed_at"] is not None


async def test_edit_stores_the_reviewers_text(client: AsyncClient, session: AsyncSession, customer: Customer) -> None:
    ticket = await add_ticket(session, customer, status="awaiting_review")
    await add_draft(session, ticket)

    resp = await client.post(
        f"/reviews/{ticket.id}/edit", json={"edited_text": "Better reply"}
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

    resp = await client.post(f"/reviews/{ticket.id}/approve")

    assert resp.status_code == 409


async def test_review_validation_and_unknown_ticket(client: AsyncClient) -> None:
    unknown = "00000000-0000-0000-0000-000000000000"
    assert (await client.post(f"/reviews/{unknown}/approve")).status_code == 404
    resp = await client.post(f"/reviews/{unknown}/edit", json={"edited_text": ""})
    assert resp.status_code == 422


# --- triage corrections (Phase 6) ----------------------------------------------------

TRIAGED = {"status": "awaiting_review", "category": "order_status", "urgency": "low"}


async def correct(client: AsyncClient, ticket_id, **body) -> httpx.Response:
    return await client.put(f"/reviews/{ticket_id}/triage", json=body)


async def test_correction_is_stored_next_to_the_model_labels(
    client: AsyncClient, session: AsyncSession, customer: Customer
) -> None:
    ticket = await add_ticket(session, customer, **TRIAGED)

    resp = await correct(client, ticket.id, corrected_category="delivery_delay", corrected_urgency="medium")

    assert resp.status_code == 200
    data = resp.json()
    assert (data["category"], data["urgency"]) == ("order_status", "low")  # model's labels kept
    assert (data["corrected_category"], data["corrected_urgency"]) == ("delivery_delay", "medium")
    assert data["corrected_by"] == "ada@acme.example"
    assert data["corrected_at"] is not None


async def test_agreeing_with_the_model_is_not_a_correction(
    client: AsyncClient, session: AsyncSession, customer: Customer
) -> None:
    ticket = await add_ticket(session, customer, **TRIAGED)

    data = (await correct(client, ticket.id, corrected_category="order_status", corrected_urgency="high")).json()

    assert data["corrected_category"] is None  # same as the model
    assert data["corrected_urgency"] == "high"


async def test_clearing_a_correction(client: AsyncClient, session: AsyncSession, customer: Customer) -> None:
    ticket = await add_ticket(session, customer, **TRIAGED)
    await correct(client, ticket.id, corrected_category="cancellation")

    data = (await correct(client, ticket.id)).json()

    assert data["corrected_category"] is None
    assert data["corrected_by"] is None
    assert data["corrected_at"] is None


async def test_correction_allowed_after_approval(client: AsyncClient, session: AsyncSession, customer: Customer) -> None:
    ticket = await add_ticket(session, customer, **(TRIAGED | {"status": "resolved"}))

    assert (await correct(client, ticket.id, corrected_urgency="high")).status_code == 200


async def test_correction_errors(client: AsyncClient, session: AsyncSession, customer: Customer) -> None:
    untriaged = await add_ticket(session, customer, status="in_progress")
    assert (await correct(client, untriaged.id, corrected_category="cancellation")).status_code == 409
    assert (await correct(client, "00000000-0000-0000-0000-000000000000")).status_code == 404
    triaged = await add_ticket(session, customer, **TRIAGED)
    assert (await correct(client, triaged.id, corrected_category="not_a_category")).status_code == 422
    resp = await client.put(f"/reviews/{triaged.id}/triage", json={"corrected_urgency": "high", "reviewer_id": "someone"})
    assert resp.status_code == 422  # the reviewer is the signed-in user, never a body field


async def test_queue_orders_by_corrected_urgency(client: AsyncClient, session: AsyncSession, customer: Customer) -> None:
    medium = await add_ticket(session, customer, **(TRIAGED | {"urgency": "medium", "needs_escalation": False}))
    raised = await add_ticket(session, customer, **(TRIAGED | {"needs_escalation": False}))
    await correct(client, raised.id, corrected_urgency="high")

    ids = [t["id"] for t in (await client.get("/reviews/queue")).json()]

    assert ids == [str(raised.id), str(medium.id)]

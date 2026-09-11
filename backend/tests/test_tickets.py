import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import AgentName, TicketCategory, TicketStatus, TicketUrgency
from app.models import AgentLog, Customer, DraftResponse, Order, Ticket


async def make_ticket(session: AsyncSession, customer: Customer, **fields) -> Ticket:
    ticket = Ticket(customer_id=customer.id, **({"subject": "Help", "body": "Where is my order?"} | fields))
    session.add(ticket)
    await session.commit()
    return ticket


# --- POST /tickets ---


async def test_create_ticket_returns_new_untriaged_ticket(client: AsyncClient, customer: Customer) -> None:
    resp = await client.post(
        "/tickets",
        json={"customer_id": str(customer.id), "subject": "Late package", "body": "It hasn't arrived."},
    )

    assert resp.status_code == 201
    data = resp.json()
    assert uuid.UUID(data["id"])
    assert data["customer_id"] == str(customer.id)
    assert data["order_id"] is None
    assert data["subject"] == "Late package"
    assert data["body"] == "It hasn't arrived."
    assert data["status"] == "new"
    assert data["category"] is None
    assert data["urgency"] is None
    assert data["needs_escalation"] is None
    assert data["escalation_reason"] is None


async def test_create_ticket_with_linked_order(client: AsyncClient, customer: Customer, order: Order) -> None:
    resp = await client.post(
        "/tickets",
        json={"customer_id": str(customer.id), "order_id": str(order.id), "subject": "Refund", "body": "Please."},
    )

    assert resp.status_code == 201
    assert resp.json()["order_id"] == str(order.id)


async def test_create_ticket_unknown_customer_returns_422(client: AsyncClient) -> None:
    resp = await client.post("/tickets", json={"customer_id": str(uuid.uuid4()), "subject": "Hi", "body": "Hello"})

    assert resp.status_code == 422
    assert "Customer" in resp.json()["detail"]


async def test_create_ticket_unknown_order_returns_422(client: AsyncClient, customer: Customer) -> None:
    resp = await client.post(
        "/tickets",
        json={"customer_id": str(customer.id), "order_id": str(uuid.uuid4()), "subject": "Hi", "body": "Hello"},
    )

    assert resp.status_code == 422
    assert "Order" in resp.json()["detail"]


async def test_create_ticket_rejects_order_of_another_customer(
    client: AsyncClient, session: AsyncSession, order: Order
) -> None:
    other = Customer(name="Grace Hopper", email="grace@example.com")
    session.add(other)
    await session.commit()

    resp = await client.post(
        "/tickets",
        json={"customer_id": str(other.id), "order_id": str(order.id), "subject": "Hi", "body": "Hello"},
    )

    assert resp.status_code == 422
    assert "does not belong" in resp.json()["detail"]


@pytest.mark.parametrize(
    "overrides",
    [{"subject": ""}, {"body": ""}, {"customer_id": None}, {"customer_id": "not-a-uuid"}],
)
async def test_create_ticket_validates_payload(client: AsyncClient, customer: Customer, overrides: dict) -> None:
    payload = {"customer_id": str(customer.id), "subject": "Hi", "body": "Hello"} | overrides

    resp = await client.post("/tickets", json=payload)

    assert resp.status_code == 422


# --- GET /tickets/{id} ---


async def test_created_ticket_can_be_fetched(client: AsyncClient, customer: Customer, order: Order) -> None:
    created = await client.post(
        "/tickets",
        json={"customer_id": str(customer.id), "order_id": str(order.id), "subject": "Refund", "body": "Please."},
    )

    resp = await client.get(f"/tickets/{created.json()['id']}")

    assert resp.status_code == 200
    data = resp.json()
    # The agent run (see test_agents.py) fills in triage/draft fields; the rest is as created
    for field in ("id", "customer_id", "order_id", "subject", "body", "created_at"):
        assert data[field] == created.json()[field]
    assert data["order"]["id"] == str(order.id)
    assert data["order"]["amount"] == "149.99"


async def test_ticket_detail_includes_drafts_and_logs_in_order(
    client: AsyncClient, session: AsyncSession, customer: Customer
) -> None:
    ticket = await make_ticket(session, customer)
    t0 = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)
    session.add_all(
        [
            AgentLog(
                ticket_id=ticket.id,
                agent_name=AgentName.KNOWLEDGE,
                input={"body": "..."},
                output={"doc_ids": []},
                created_at=t0 + timedelta(seconds=1),
            ),
            AgentLog(
                ticket_id=ticket.id,
                agent_name=AgentName.TRIAGE,
                input={"body": "..."},
                output={"category": "order_status"},
                duration_ms=12,
                created_at=t0,
            ),
            DraftResponse(ticket_id=ticket.id, draft_text="Your order is on its way."),
        ]
    )
    await session.commit()

    resp = await client.get(f"/tickets/{ticket.id}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["order"] is None
    assert [log["agent_name"] for log in data["agent_logs"]] == ["triage", "knowledge"]
    assert data["agent_logs"][0]["duration_ms"] == 12
    assert len(data["draft_responses"]) == 1
    assert data["draft_responses"][0]["draft_text"] == "Your order is on its way."
    assert data["draft_responses"][0]["approved"] is None


async def test_get_ticket_not_found(client: AsyncClient) -> None:
    resp = await client.get(f"/tickets/{uuid.uuid4()}")

    assert resp.status_code == 404


async def test_get_ticket_invalid_id(client: AsyncClient) -> None:
    resp = await client.get("/tickets/not-a-uuid")

    assert resp.status_code == 422


# --- GET /tickets ---


async def test_list_tickets_newest_first(client: AsyncClient, session: AsyncSession, customer: Customer) -> None:
    first = await make_ticket(session, customer, subject="first")
    second = await make_ticket(session, customer, subject="second")

    resp = await client.get("/tickets")

    assert resp.status_code == 200
    assert [t["id"] for t in resp.json()] == [str(second.id), str(first.id)]


async def test_list_tickets_empty(client: AsyncClient) -> None:
    resp = await client.get("/tickets")

    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_tickets_filters(client: AsyncClient, session: AsyncSession, customer: Customer) -> None:
    refund_high = await make_ticket(
        session,
        customer,
        category=TicketCategory.REFUND_REQUEST,
        urgency=TicketUrgency.HIGH,
        status=TicketStatus.AWAITING_REVIEW,
    )
    refund_low = await make_ticket(
        session,
        customer,
        category=TicketCategory.REFUND_REQUEST,
        urgency=TicketUrgency.LOW,
        status=TicketStatus.RESOLVED,
    )
    untriaged = await make_ticket(session, customer)

    async def ids(query: str) -> set[str]:
        resp = await client.get(f"/tickets?{query}")
        assert resp.status_code == 200
        return {t["id"] for t in resp.json()}

    assert await ids("status=new") == {str(untriaged.id)}
    assert await ids("status=awaiting_review") == {str(refund_high.id)}
    assert await ids("category=refund_request") == {str(refund_high.id), str(refund_low.id)}
    assert await ids("urgency=low") == {str(refund_low.id)}
    assert await ids("category=refund_request&urgency=high") == {str(refund_high.id)}
    assert await ids("category=cancellation") == set()


@pytest.mark.parametrize("query", ["status=escalated", "category=billing", "urgency=critical"])
async def test_list_tickets_rejects_unknown_filter_values(client: AsyncClient, query: str) -> None:
    resp = await client.get(f"/tickets?{query}")

    assert resp.status_code == 422

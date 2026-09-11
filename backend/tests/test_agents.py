"""End-to-end agent runs: POST /tickets -> background LangGraph run -> trace, draft, review queue.

The drafter is a fake (conftest.FakeDrafter); the classifiers, knowledge search and
database are real.
"""

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.drafter import DraftError, DraftResult, get_drafter
from app.main import app
from app.models import Customer, ModelPrediction, Order, Ticket
from app.schemas.knowledge_base import KnowledgeBaseCreate
from app.services import knowledge_base as kb_service
from tests.conftest import FakeDrafter


async def create_ticket(client: AsyncClient, customer: Customer, body: str, order: Order | None = None) -> dict:
    payload = {"customer_id": str(customer.id), "subject": "Help", "body": body}
    if order is not None:
        payload["order_id"] = str(order.id)
    resp = await client.post("/tickets", json=payload)
    assert resp.status_code == 201
    return resp.json()


async def trace_agents(client: AsyncClient, ticket_id: str) -> list[str]:
    resp = await client.get(f"/tickets/{ticket_id}/agent-trace")
    assert resp.status_code == 200
    return [log["agent_name"] for log in resp.json()]


async def test_ticket_with_order_runs_all_five_agents(
    client: AsyncClient, session: AsyncSession, customer: Customer, order: Order, drafter: FakeDrafter
) -> None:
    created = await create_ticket(client, customer, "Where is my order? Tracking hasn't moved in a week.", order)
    assert created["status"] == "new"  # the response comes back before the run

    detail = (await client.get(f"/tickets/{created['id']}")).json()
    assert detail["status"] == "awaiting_review"
    assert detail["category"] is not None and detail["urgency"] is not None
    assert detail["needs_escalation"] is not None
    assert [d["draft_text"] for d in detail["draft_responses"]] == [drafter.text]
    assert await trace_agents(client, created["id"]) == ["triage", "knowledge", "order_lookup", "draft", "escalation"]

    predictions = await session.scalar(
        select(func.count()).select_from(ModelPrediction).where(ModelPrediction.ticket_id == created["id"])
    )
    assert predictions == 2
    # The draft is grounded in the order record
    (_, user_prompt), = drafter.calls
    assert "Wireless Headphones" in user_prompt and "1Z999AA10123456784" in user_prompt


async def test_ticket_without_order_skips_order_lookup(client: AsyncClient, customer: Customer) -> None:
    created = await create_ticket(client, customer, "Does the blender come with a warranty?")

    assert await trace_agents(client, created["id"]) == ["triage", "knowledge", "draft", "escalation"]


async def test_knowledge_agent_passes_matching_entries_to_the_draft(
    client: AsyncClient, session: AsyncSession, customer: Customer, drafter: FakeDrafter
) -> None:
    for title, content in [
        ("Damaged items", "If an item arrives broken or cracked, send photos and we replace it."),
        ("Store hours", "Our warehouse team works Monday to Friday."),
    ]:
        await kb_service.create_entry(session, KnowledgeBaseCreate(title=title, content=content))

    created = await create_ticket(client, customer, "My mirror arrived shattered in the box.")

    knowledge_log = (await client.get(f"/tickets/{created['id']}/agent-trace")).json()[1]
    assert knowledge_log["output"]["retrieved"][0]["title"] == "Damaged items"
    assert 'title="Damaged items"' in drafter.calls[0][1]


async def test_refund_over_threshold_is_escalated(client: AsyncClient, customer: Customer, order: Order) -> None:
    created = await create_ticket(client, customer, "I returned the headphones, please refund my money.", order)

    detail = (await client.get(f"/tickets/{created['id']}")).json()
    assert detail["category"] == "refund_request"
    assert detail["needs_escalation"] is True
    assert "Refund request on a $149.99 order (over $100)" in detail["escalation_reason"]


class FailingDrafter:
    async def draft(self, system: str, user: str) -> DraftResult:
        raise DraftError("Claude API error 529: overloaded")


async def test_failed_run_still_reaches_review_flagged_for_escalation(
    client: AsyncClient, session: AsyncSession, customer: Customer
) -> None:
    app.dependency_overrides[get_drafter] = FailingDrafter

    created = await create_ticket(client, customer, "Where is my parcel?")

    detail = (await client.get(f"/tickets/{created['id']}")).json()
    assert detail["status"] == "awaiting_review"
    assert detail["needs_escalation"] is True
    assert "DraftError" in detail["escalation_reason"]
    assert detail["draft_responses"] == []
    trace = (await client.get(f"/tickets/{created['id']}/agent-trace")).json()
    assert [log["agent_name"] for log in trace] == ["triage", "knowledge", "draft"]
    assert "overloaded" in trace[-1]["output"]["error"]


async def test_rerun_adds_a_new_run(client: AsyncClient, customer: Customer) -> None:
    created = await create_ticket(client, customer, "Can I cancel my order?")

    resp = await client.post(f"/tickets/{created['id']}/rerun")

    assert resp.status_code == 202
    detail = (await client.get(f"/tickets/{created['id']}")).json()
    assert detail["status"] == "awaiting_review"
    assert len(detail["draft_responses"]) == 2
    assert len(await trace_agents(client, created["id"])) == 8


async def test_rerun_refused_while_a_run_is_in_progress(
    client: AsyncClient, session: AsyncSession, customer: Customer
) -> None:
    ticket = Ticket(customer_id=customer.id, subject="Hi", body="Hello", status="in_progress")
    session.add(ticket)
    await session.commit()

    resp = await client.post(f"/tickets/{ticket.id}/rerun")

    assert resp.status_code == 409


async def test_agent_trace_and_rerun_unknown_ticket(client: AsyncClient) -> None:
    unknown = "00000000-0000-0000-0000-000000000000"
    assert (await client.get(f"/tickets/{unknown}/agent-trace")).status_code == 404
    assert (await client.post(f"/tickets/{unknown}/rerun")).status_code == 404

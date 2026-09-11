"""Tenant isolation: through the API, in search, and in the database itself."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError, ProgrammingError

from app.core.tenancy import NoTenantInScope, tenant_of, tenant_session
from app.models import (
    AgentLog,
    Customer,
    DraftResponse,
    KnowledgeBaseEntry,
    Order,
    Ticket,
)
from app.schemas.knowledge_base import KnowledgeBaseCreate
from app.services import knowledge_base as kb_service
from scripts import tenants as tenant_cli
from tests.conftest import make_user


@pytest.fixture
async def theirs(session_factory, other_tenant):
    """Another tenant's customer, order, triaged ticket (awaiting review, with a draft and
    a trace row) and knowledge-base entry."""
    async with tenant_session(session_factory, other_tenant.id) as s:
        customer = Customer(name="Grace Hopper", email="grace@globex.example")
        s.add(customer)
        await s.flush()
        order = Order(customer_id=customer.id, item_name="Tent", status="delayed", amount=Decimal(250), order_date=date(2026, 9, 1))
        s.add(order)
        await s.flush()
        ticket = Ticket(
            customer_id=customer.id,
            order_id=order.id,
            subject="Where is my tent?",
            body="It is late.",
            status="awaiting_review",
            category="delivery_delay",
            urgency="medium",
            needs_escalation=False,
        )
        s.add(ticket)
        await s.flush()
        s.add_all(
            [
                DraftResponse(ticket_id=ticket.id, draft_text="Their draft"),
                AgentLog(ticket_id=ticket.id, agent_name="triage", input={}, output={}),
            ]
        )
        await s.commit()
    async with tenant_session(session_factory, other_tenant.id) as s:
        await kb_service.create_entry(s, KnowledgeBaseCreate(title="Globex returns", content="Tents can be returned in 60 days."))
    return {"customer": customer, "order": order, "ticket": ticket}


async def test_another_tenants_records_read_as_not_found(client, theirs) -> None:
    t = theirs["ticket"].id
    assert (await client.get(f"/tickets/{t}")).status_code == 404
    assert (await client.get(f"/tickets/{t}/agent-trace")).status_code == 404
    assert (await client.get(f"/orders/{theirs['order'].id}")).status_code == 404
    assert (await client.get(f"/customers/{theirs['customer'].id}")).status_code == 404
    assert (await client.get(f"/customers/{theirs['customer'].id}/orders")).status_code == 404


async def test_another_tenants_records_cannot_be_changed(client, theirs, session_factory, other_tenant) -> None:
    t = theirs["ticket"].id
    assert (await client.post(f"/reviews/{t}/approve")).status_code == 404
    assert (await client.post(f"/reviews/{t}/edit", json={"edited_text": "hijacked"})).status_code == 404
    assert (await client.put(f"/reviews/{t}/triage", json={"corrected_urgency": "high"})).status_code == 404
    assert (await client.post(f"/tickets/{t}/rerun")).status_code == 404

    async with tenant_session(session_factory, other_tenant.id) as s:
        ticket = await s.get(Ticket, t)
        assert ticket.status == "awaiting_review" and ticket.corrected_urgency is None


async def test_lists_and_metrics_only_show_your_tenant(client, theirs, customer) -> None:
    assert (await client.get("/tickets")).json() == []
    assert (await client.get("/reviews/queue")).json() == []
    assert [c["name"] for c in (await client.get("/customers", params={"search": "grace"})).json()] == []
    assert [c["name"] for c in (await client.get("/customers")).json()] == ["Ada Lovelace"]
    assert (await client.get("/knowledge-base")).json() == []
    assert (await client.get("/metrics/summary")).json()["total_tickets"] == 0


async def test_cannot_file_a_ticket_against_another_tenants_customer_or_order(client, theirs, customer) -> None:
    other_customer = await client.post(
        "/tickets", json={"customer_id": str(theirs["customer"].id), "subject": "Hi", "body": "Hello"}
    )
    other_order = await client.post(
        "/tickets",
        json={"customer_id": str(customer.id), "order_id": str(theirs["order"].id), "subject": "Hi", "body": "Hello"},
    )
    assert other_customer.status_code == other_order.status_code == 422


async def test_tenant_id_in_a_body_is_rejected(client, customer, other_tenant) -> None:
    resp = await client.post(
        "/tickets",
        json={"customer_id": str(customer.id), "subject": "Hi", "body": "Hello", "tenant_id": str(other_tenant.id)},
    )
    assert resp.status_code == 422


async def test_vector_search_never_crosses_tenants(session_factory, session, other_tenant, theirs) -> None:
    same = KnowledgeBaseCreate(title="Returns", content="Tents can be returned in 60 days.")
    await kb_service.create_entry(session, same)

    docs = await kb_service.search(session, "can I return my tent", k=10)

    mine = (await session.scalars(select(KnowledgeBaseEntry.id))).all()
    assert [d.title for d in docs] == ["Returns"]
    assert {d.id for d in docs} == {str(i) for i in mine}


# --- the database layer (row-level security, same-tenant keys) ---------------------------


async def test_rls_hides_other_tenants_even_without_a_filter(session, theirs, customer) -> None:
    # Raw SQL with no WHERE: only this tenant's rows come back
    assert (await session.execute(text("SELECT count(*) FROM customers"))).scalar_one() == 1
    assert (await session.execute(text("SELECT count(*) FROM tickets"))).scalar_one() == 0
    assert (await session.execute(text("SELECT count(*) FROM knowledge_base"))).scalar_one() == 0


async def test_no_tenant_in_scope_sees_nothing_and_cannot_insert(session_factory, theirs) -> None:
    async with session_factory() as s:  # the API role, but no tenant set
        assert (await s.execute(text("SELECT count(*) FROM tickets"))).scalar_one() == 0
        with pytest.raises(NoTenantInScope):
            tenant_of(s)
        s.add(Customer(name="Nobody", email="no@one.example"))
        # Fails closed: the RLS check (or, for the owner, NOT NULL) rejects a NULL tenant
        with pytest.raises((IntegrityError, ProgrammingError)):
            await s.commit()


async def test_rls_blocks_writing_into_another_tenant(session, other_tenant) -> None:
    session.add(Customer(tenant_id=other_tenant.id, name="Spy", email="spy@example.com"))
    with pytest.raises((ProgrammingError, DBAPIError), match="row-level security"):
        await session.commit()


async def test_same_tenant_foreign_keys_hold_even_for_the_owner(admin_factory, tenant, theirs) -> None:
    # The owner bypasses RLS; the composite foreign key still refuses the cross-tenant link
    async with admin_factory() as s:
        s.add(Ticket(tenant_id=tenant.id, customer_id=theirs["customer"].id, subject="x", body="y"))
        with pytest.raises(IntegrityError, match="fk_tickets_tenant_id_customers"):
            await s.commit()


async def test_background_run_writes_into_the_tickets_tenant(client, customer, session) -> None:
    created = (await client.post("/tickets", json={"customer_id": str(customer.id), "subject": "Late", "body": "Still waiting."})).json()

    logs = (await session.scalars(select(AgentLog).where(AgentLog.ticket_id == created["id"]))).all()
    assert logs and {log.tenant_id for log in logs} == {tenant_of(session)}
    assert await session.scalar(select(func.count()).select_from(DraftResponse)) == 1


# --- operator CLI ----------------------------------------------------------------------


async def test_cli_creates_tenants_and_users_who_can_sign_in(admin_factory, anon_client) -> None:
    await tenant_cli.create_tenant(admin_factory, "Initech", "initech")
    password = await tenant_cli.create_user(admin_factory, "initech", "Bob@Initech.example", "Bob", "reviewer")

    resp = await anon_client.post("/auth/login", json={"email": "bob@initech.example", "password": password})

    assert resp.status_code == 200
    assert resp.json()["tenant_name"] == "Initech"
    with pytest.raises(tenant_cli.CliError):
        await tenant_cli.create_tenant(admin_factory, "Dupe", "initech")
    with pytest.raises(tenant_cli.CliError):
        await tenant_cli.create_tenant(admin_factory, "Bad", "Not A Slug")


async def test_cli_reset_password_replaces_the_old_one(admin_factory, anon_client, tenant) -> None:
    account = await make_user(admin_factory, tenant, "eve@acme.example")
    new_password = await tenant_cli.reset_password(admin_factory, account.email)

    old = await anon_client.post("/auth/login", json={"email": account.email, "password": "correct horse battery staple"})
    new = await anon_client.post("/auth/login", json={"email": account.email, "password": new_password})

    assert (old.status_code, new.status_code) == (401, 200)


async def test_cli_delete_tenant_removes_only_that_tenant(admin_factory, session, customer, theirs, other_tenant) -> None:
    counts = await tenant_cli.delete_tenant(admin_factory, "globex")

    assert counts["tickets"] == 1 and counts["knowledge_base"] == 1 and counts["customers"] == 1
    async with admin_factory() as s:
        assert await s.get(type(other_tenant), other_tenant.id) is None
    assert (await session.execute(text("SELECT count(*) FROM customers"))).scalar_one() == 1  # ours untouched

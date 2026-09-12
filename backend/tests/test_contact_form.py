"""Phase 10b: a business's customers send tickets through the public contact form."""

from sqlalchemy import select, update

from app.core.enums import UserRole
from app.models import Customer, Tenant, Ticket
from app.routers.public import visitor_limiter
from tests.conftest import make_user

MESSAGE = {"name": "Jo Bloggs", "email": "Jo@Example.com", "subject": "Parcel late", "message": "My order hasn't arrived yet. Where is it?"}


async def enable(admin_factory, tenant, on: bool = True) -> None:
    async with admin_factory() as s:
        await s.execute(update(Tenant).where(Tenant.id == tenant.id).values(contact_form_enabled=on))
        await s.commit()


async def test_form_is_off_until_an_admin_turns_it_on(anon_client, client, tenant) -> None:
    assert (await anon_client.get("/public/contact/acme")).status_code == 404
    assert (await anon_client.post("/public/contact/acme", json=MESSAGE)).status_code == 404

    resp = await client.patch("/settings", json={"contact_form_enabled": True})

    assert resp.json() == {"name": "Acme Homewares", "slug": "acme", "contact_form_enabled": True}
    assert (await anon_client.get("/public/contact/acme")).json() == {"business_name": "Acme Homewares"}


async def test_a_customer_message_becomes_a_reviewed_ticket(anon_client, client, admin_factory, tenant, session, drafter) -> None:
    await enable(admin_factory, tenant)

    resp = await anon_client.post("/public/contact/ACME", json=MESSAGE)  # slug case doesn't matter

    assert resp.status_code == 202
    receipt = resp.json()
    assert receipt["business_name"] == "Acme Homewares" and len(receipt["reference"]) == 8
    ticket = (await session.scalars(select(Ticket))).one()
    assert (ticket.channel, ticket.subject) == ("contact_form", "Parcel late")
    assert str(ticket.id).upper().startswith(receipt["reference"])
    customer = await session.get(Customer, ticket.customer_id)
    assert (customer.name, customer.email) == ("Jo Bloggs", "jo@example.com")
    # The agents ran and the staff see it in their queue
    assert drafter.tenants == ["acme"]
    queue = (await client.get("/reviews/queue")).json()
    assert [(t["subject"], t["channel"]) for t in queue] == [("Parcel late", "contact_form")]


async def test_a_returning_customer_is_matched_by_email(anon_client, admin_factory, tenant, session) -> None:
    await enable(admin_factory, tenant)
    await anon_client.post("/public/contact/acme", json=MESSAGE)
    await anon_client.post("/public/contact/acme", json={**MESSAGE, "subject": "Another question"})

    assert len((await session.scalars(select(Customer))).all()) == 1
    assert len((await session.scalars(select(Ticket))).all()) == 2


async def test_honeypot_looks_like_success_but_stores_nothing(anon_client, admin_factory, tenant, session) -> None:
    await enable(admin_factory, tenant)

    resp = await anon_client.post("/public/contact/acme", json={**MESSAGE, "website": "http://spam.example"})

    assert resp.status_code == 202 and len(resp.json()["reference"]) == 8
    assert (await session.scalars(select(Ticket))).all() == []


async def test_visitors_are_rate_limited(anon_client, admin_factory, tenant) -> None:
    await enable(admin_factory, tenant)
    for _ in range(visitor_limiter.limit):
        assert (await anon_client.post("/public/contact/acme", json=MESSAGE)).status_code == 202

    assert (await anon_client.post("/public/contact/acme", json=MESSAGE)).status_code == 429


async def test_messages_are_validated(anon_client, admin_factory, tenant) -> None:
    await enable(admin_factory, tenant)
    for bad in ({**MESSAGE, "email": "nope"}, {**MESSAGE, "message": "short"}, {**MESSAGE, "message": "x" * 5001}, {**MESSAGE, "tenant_id": "x"}):
        assert (await anon_client.post("/public/contact/acme", json=bad)).status_code == 422


async def test_messages_land_only_in_that_business(anon_client, admin_factory, tenant, other_tenant, api) -> None:
    await enable(admin_factory, tenant)
    outsider = await make_user(admin_factory, other_tenant, "boss@globex.example")

    await anon_client.post("/public/contact/acme", json=MESSAGE)

    async with api(outsider) as oc:
        assert (await oc.get("/reviews/queue")).json() == []
    assert (await anon_client.get("/public/contact/globex")).status_code == 404  # its form is off


async def test_only_admins_change_settings(api, admin_factory, tenant) -> None:
    reviewer = await make_user(admin_factory, tenant, "rev@acme.example", UserRole.REVIEWER)
    async with api(reviewer) as rc:
        assert (await rc.get("/settings")).status_code == 403
        assert (await rc.patch("/settings", json={"contact_form_enabled": True})).status_code == 403

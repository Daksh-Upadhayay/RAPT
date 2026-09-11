from datetime import date
from decimal import Decimal
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Customer, Order


async def add_customers(session: AsyncSession) -> None:
    session.add_all(
        [
            Customer(name="Grace Hopper", email="grace@navy.example"),
            Customer(name="Alan Turing", email="alan@bletchley.example"),
            Customer(name="Barbara Liskov", email="liskov_100%@mit.example"),
        ]
    )
    await session.commit()


async def test_search_matches_name_or_email_case_insensitively(client: AsyncClient, session: AsyncSession) -> None:
    await add_customers(session)

    by_name = await client.get("/customers", params={"search": "hopper"})
    by_email = await client.get("/customers", params={"search": "BLETCHLEY"})

    assert [c["name"] for c in by_name.json()] == ["Grace Hopper"]
    assert [c["name"] for c in by_email.json()] == ["Alan Turing"]
    assert set(by_name.json()[0]) == {"id", "name", "email"}


async def test_search_treats_like_wildcards_literally(client: AsyncClient, session: AsyncSession) -> None:
    await add_customers(session)

    resp = await client.get("/customers", params={"search": "_100%"})

    assert [c["name"] for c in resp.json()] == ["Barbara Liskov"]


async def test_without_search_lists_first_customers_by_name(client: AsyncClient, session: AsyncSession) -> None:
    await add_customers(session)

    resp = await client.get("/customers", params={"limit": 2})

    assert [c["name"] for c in resp.json()] == ["Alan Turing", "Barbara Liskov"]


async def test_customer_orders_newest_first_and_only_theirs(
    client: AsyncClient, session: AsyncSession, customer: Customer, order: Order
) -> None:
    other = Customer(name="Someone Else", email="else@example.com")
    session.add(other)
    await session.flush()
    older = Order(
        customer_id=customer.id, item_name="Mug", status="delivered", amount=Decimal("9.50"), order_date=date(2026, 1, 5)
    )
    session.add_all(
        [older, Order(customer_id=other.id, item_name="Lamp", status="shipped", amount=Decimal(20), order_date=date(2026, 9, 9))]
    )
    await session.commit()

    resp = await client.get(f"/customers/{customer.id}/orders")

    assert resp.status_code == 200
    assert [o["id"] for o in resp.json()] == [str(order.id), str(older.id)]


async def test_get_customer(client: AsyncClient, customer: Customer) -> None:
    resp = await client.get(f"/customers/{customer.id}")

    assert resp.status_code == 200
    assert resp.json() == {"id": str(customer.id), "name": "Ada Lovelace", "email": "ada@example.com"}


async def test_unknown_customer_is_404(client: AsyncClient) -> None:
    assert (await client.get(f"/customers/{uuid4()}")).status_code == 404
    assert (await client.get(f"/customers/{uuid4()}/orders")).status_code == 404


async def test_create_customer_for_a_first_ticket(client) -> None:
    resp = await client.post("/customers", json={"name": "Jo Bloggs", "email": "Jo@Example.com"})

    assert resp.status_code == 201
    assert resp.json()["email"] == "jo@example.com"
    again = await client.post("/customers", json={"name": "Jo", "email": "jo@example.com"})
    assert again.status_code == 409
    assert (await client.post("/customers", json={"name": "Bad", "email": "not-an-email"})).status_code == 422

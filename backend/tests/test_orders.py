import uuid

from httpx import AsyncClient

from app.models import Order


async def test_get_order(client: AsyncClient, order: Order) -> None:
    resp = await client.get(f"/orders/{order.id}")

    assert resp.status_code == 200
    assert resp.json() == {
        "id": str(order.id),
        "customer_id": str(order.customer_id),
        "item_name": "Wireless Headphones",
        "status": "shipped",
        "tracking_number": "1Z999AA10123456784",
        "amount": "149.99",
        "order_date": "2026-09-01",
        "expected_delivery": "2026-09-08",
    }


async def test_get_order_not_found(client: AsyncClient) -> None:
    resp = await client.get(f"/orders/{uuid.uuid4()}")

    assert resp.status_code == 404


async def test_get_order_invalid_id(client: AsyncClient) -> None:
    resp = await client.get("/orders/not-a-uuid")

    assert resp.status_code == 422

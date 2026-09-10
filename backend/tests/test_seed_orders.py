from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import OrderStatus
from app.models import Customer, Order
from scripts.seed_orders import ExistingDataError, seed

TODAY = date(2026, 9, 10)


async def test_seed_inserts_customers_and_orders(session: AsyncSession) -> None:
    n_customers, orders = await seed(session, n_customers=30, seed=1, today=TODAY)

    assert n_customers == 30
    assert await session.scalar(select(func.count()).select_from(Customer)) == 30
    assert await session.scalar(select(func.count()).select_from(Order)) == len(orders)
    assert 30 <= len(orders) <= 150  # 1-5 orders per customer
    emails = (await session.scalars(select(Customer.email))).all()
    assert len(set(emails)) == len(emails)


async def test_seeded_orders_are_internally_consistent(session: AsyncSession) -> None:
    _, orders = await seed(session, n_customers=100, seed=2, today=TODAY)

    assert {o.status for o in orders} == set(OrderStatus)
    for o in orders:
        assert o.amount > 0
        assert o.order_date <= TODAY
        match o.status:
            case OrderStatus.PROCESSING:
                assert o.tracking_number is None
                assert o.expected_delivery > TODAY
            case OrderStatus.SHIPPED:
                assert o.tracking_number is not None
                assert o.expected_delivery > TODAY
            case OrderStatus.DELIVERED | OrderStatus.DELAYED:
                assert o.tracking_number is not None
                assert o.expected_delivery < TODAY
            case OrderStatus.CANCELLED:
                assert o.tracking_number is None
                assert o.expected_delivery is None
    # both sides of the $100 refund-escalation threshold are represented
    assert any(o.amount > 100 for o in orders)
    assert any(o.amount <= 100 for o in orders)


async def test_seed_is_reproducible(session: AsyncSession) -> None:
    _, first = await seed(session, n_customers=10, seed=3, today=TODAY)
    _, second = await seed(session, n_customers=10, seed=3, today=TODAY, reset=True)

    def fingerprint(orders: list[Order]) -> list[tuple]:
        return [(o.item_name, o.status, o.amount, o.order_date) for o in orders]

    assert fingerprint(first) == fingerprint(second)


async def test_seed_refuses_to_run_on_existing_data(session: AsyncSession, customer: Customer) -> None:
    with pytest.raises(ExistingDataError):
        await seed(session, n_customers=5, today=TODAY)


async def test_seed_reset_replaces_existing_data(session: AsyncSession, customer: Customer) -> None:
    await seed(session, n_customers=5, today=TODAY, reset=True)

    emails = (await session.scalars(select(Customer.email))).all()
    assert len(emails) == 5
    assert customer.email not in emails

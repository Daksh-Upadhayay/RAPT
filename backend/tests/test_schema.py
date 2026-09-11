"""Database-level checks: migrations and the constraints they create."""

from datetime import date
from decimal import Decimal

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Customer, Order, Ticket


def test_migrations_downgrade_and_upgrade_cleanly(alembic_cfg: Config) -> None:
    command.downgrade(alembic_cfg, "base")
    command.upgrade(alembic_cfg, "head")


@pytest.mark.parametrize(
    "fields",
    [{"status": "escalated"}, {"category": "billing"}, {"urgency": "critical"}],
)
async def test_ticket_check_constraints(session: AsyncSession, customer: Customer, fields: dict) -> None:
    session.add(Ticket(customer_id=customer.id, subject="Hi", body="Hello", **fields))

    with pytest.raises(IntegrityError, match="ck_tickets_"):
        await session.commit()


async def test_order_status_check_constraint(session: AsyncSession, customer: Customer) -> None:
    session.add(
        Order(
            customer_id=customer.id,
            item_name="Mug",
            status="lost",
            amount=Decimal("9.99"),
            order_date=date(2026, 9, 1),
        )
    )

    with pytest.raises(IntegrityError, match="ck_orders_status_valid"):
        await session.commit()


async def test_customer_email_is_unique_within_a_tenant(session: AsyncSession, customer: Customer) -> None:
    session.add(Customer(name="Imposter", email=customer.email))

    with pytest.raises(IntegrityError, match="uq_customers_tenant_id_email"):
        await session.commit()

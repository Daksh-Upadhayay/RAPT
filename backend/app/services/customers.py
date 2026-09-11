from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Customer, Order


class CustomerNotFound(Exception):
    pass


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def search_customers(session: AsyncSession, search: str | None, limit: int) -> Sequence[Customer]:
    """Customers whose name or email contains `search` (case-insensitive), by name."""
    stmt = select(Customer).order_by(Customer.name, Customer.email).limit(limit)
    if search:
        pattern = f"%{_escape_like(search)}%"
        stmt = stmt.where(or_(Customer.name.ilike(pattern), Customer.email.ilike(pattern)))
    return (await session.scalars(stmt)).all()


async def get_customer(session: AsyncSession, customer_id: UUID) -> Customer | None:
    return await session.get(Customer, customer_id)


async def customer_orders(session: AsyncSession, customer_id: UUID) -> Sequence[Order]:
    """The customer's orders, newest first."""
    if await session.get(Customer, customer_id) is None:
        raise CustomerNotFound
    stmt = select(Order).where(Order.customer_id == customer_id).order_by(Order.order_date.desc())
    return (await session.scalars(stmt)).all()

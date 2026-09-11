from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenancy import get_scoped
from app.models import Order


async def get_order(session: AsyncSession, order_id: UUID) -> Order | None:
    return await get_scoped(session, Order, order_id)

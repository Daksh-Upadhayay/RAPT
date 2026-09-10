from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Order


async def get_order(session: AsyncSession, order_id: UUID) -> Order | None:
    return await session.get(Order, order_id)

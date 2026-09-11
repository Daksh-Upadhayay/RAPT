from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import TicketCategory, TicketStatus, TicketUrgency
from app.core.tenancy import get_scoped, tenant_of
from app.models import Customer, Order, Ticket
from app.schemas.ticket import TicketCreate


class InvalidTicketReference(Exception):
    """The ticket references a customer/order that doesn't exist or doesn't match."""


async def create_ticket(session: AsyncSession, data: TicketCreate) -> Ticket:
    # Scoped lookups: another tenant's customer or order reads as not found
    if await get_scoped(session, Customer, data.customer_id) is None:
        raise InvalidTicketReference(f"Customer {data.customer_id} not found")
    if data.order_id is not None:
        order = await get_scoped(session, Order, data.order_id)
        if order is None:
            raise InvalidTicketReference(f"Order {data.order_id} not found")
        if order.customer_id != data.customer_id:
            raise InvalidTicketReference(f"Order {data.order_id} does not belong to customer {data.customer_id}")

    ticket = Ticket(**data.model_dump())
    session.add(ticket)
    await session.commit()
    await session.refresh(ticket)
    return ticket


async def list_tickets(
    session: AsyncSession,
    status: TicketStatus | None = None,
    category: TicketCategory | None = None,
    urgency: TicketUrgency | None = None,
) -> Sequence[Ticket]:
    stmt = select(Ticket).where(Ticket.tenant_id == tenant_of(session)).order_by(Ticket.created_at.desc())
    if status is not None:
        stmt = stmt.where(Ticket.status == status)
    if category is not None:
        stmt = stmt.where(Ticket.category == category)
    if urgency is not None:
        stmt = stmt.where(Ticket.urgency == urgency)
    return (await session.scalars(stmt)).all()


async def get_ticket_detail(session: AsyncSession, ticket_id: UUID) -> Ticket | None:
    stmt = (
        select(Ticket)
        .where(Ticket.id == ticket_id, Ticket.tenant_id == tenant_of(session))
        .options(
            selectinload(Ticket.order),
            selectinload(Ticket.agent_logs),
            selectinload(Ticket.draft_responses),
        )
    )
    return await session.scalar(stmt)

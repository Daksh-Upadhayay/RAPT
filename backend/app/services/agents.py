from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import TicketStatus
from app.core.tenancy import get_scoped, tenant_of
from app.models import AgentLog, Ticket


class TicketNotFound(Exception):
    pass


class RunInProgress(Exception):
    """An agent run for this ticket hasn't finished yet."""


async def get_agent_trace(session: AsyncSession, ticket_id: UUID) -> Sequence[AgentLog]:
    if await get_scoped(session, Ticket, ticket_id) is None:
        raise TicketNotFound
    stmt = (
        select(AgentLog)
        .where(AgentLog.tenant_id == tenant_of(session), AgentLog.ticket_id == ticket_id)
        .order_by(AgentLog.created_at)
    )
    return (await session.scalars(stmt)).all()


async def prepare_rerun(session: AsyncSession, ticket_id: UUID) -> Ticket:
    """Mark the ticket in_progress before scheduling a rerun, so a second request while
    the first is still running gets a 409 instead of starting a parallel run."""
    ticket = await get_scoped(session, Ticket, ticket_id)
    if ticket is None:
        raise TicketNotFound
    if ticket.status == TicketStatus.IN_PROGRESS:
        raise RunInProgress
    ticket.status = TicketStatus.IN_PROGRESS
    await session.commit()
    await session.refresh(ticket)
    return ticket

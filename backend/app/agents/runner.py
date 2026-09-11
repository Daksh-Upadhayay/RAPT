"""Runs the agent graph for one ticket, as a FastAPI background task.

Status flow: new -> in_progress (run starts) -> awaiting_review (run ends).

If a node fails, its agent_logs row records the error, and the ticket still goes to
awaiting_review with needs_escalation set and the failure as the reason. It stays in the
review queue for a human, who can rerun it, instead of silently stalling in_progress.
"""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.drafter import Drafter
from app.agents.graph import agent_graph
from app.agents.nodes import AgentContext
from app.agents.state import TicketState
from app.core.enums import TicketStatus
from app.models import Ticket

logger = logging.getLogger(__name__)


async def run_agent_graph(
    ticket_id: uuid.UUID, session_factory: async_sessionmaker[AsyncSession], drafter: Drafter
) -> None:
    async with session_factory() as session:
        ticket = await session.get(Ticket, ticket_id)
        if ticket is None:
            logger.warning("Agent run skipped: ticket %s not found", ticket_id)
            return
        ticket.status = TicketStatus.IN_PROGRESS
        await session.commit()
        state = TicketState(
            ticket_id=str(ticket.id),
            subject=ticket.subject,
            body=ticket.body,
            order_id=str(ticket.order_id) if ticket.order_id else None,
        )

        try:
            await agent_graph.ainvoke(state, context=AgentContext(session=session, drafter=drafter))
            ticket = await session.get_one(Ticket, ticket_id)
        except Exception as exc:
            logger.exception("Agent run failed for ticket %s", ticket_id)
            await session.rollback()
            ticket = await session.get_one(Ticket, ticket_id, populate_existing=True)
            ticket.needs_escalation = True
            ticket.escalation_reason = f"Agent pipeline failed ({type(exc).__name__}: {exc}); review manually or rerun"
        ticket.status = TicketStatus.AWAITING_REVIEW
        await session.commit()

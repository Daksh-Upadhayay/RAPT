"""Resume agent runs a restart interrupted (Phase 8).

Runs are FastAPI background tasks inside the API process; if it stops mid-run, the ticket
stays `new` or `in_progress` and nobody would ever see it. On startup the API runs those
tickets again, one at a time. With a single API instance any such ticket is orphaned by
definition; several instances would need a lease (e.g. a claimed_at column) first.
"""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.drafter import Drafter
from app.agents.runner import run_agent_graph

logger = logging.getLogger(__name__)


async def resume_unfinished_runs(session_factory: async_sessionmaker[AsyncSession], drafter: Drafter) -> int:
    async with session_factory() as session:
        rows = (await session.execute(text("SELECT ticket_id, tenant_id FROM unfinished_agent_runs()"))).all()
    for ticket_id, tenant_id in rows:
        logger.info("Resuming the interrupted agent run for ticket %s", ticket_id)
        try:
            await run_agent_graph(ticket_id, tenant_id, session_factory, drafter)
        except Exception:  # one bad ticket must not stop the others
            logger.exception("Could not resume the agent run for ticket %s", ticket_id)
    return len(rows)

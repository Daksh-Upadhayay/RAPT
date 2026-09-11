from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from app.agents.drafter import Drafter, get_drafter
from app.agents.runner import run_agent_graph
from app.core.db import SessionDep, SessionFactoryDep
from app.schemas.ticket import AgentLogResponse, TicketResponse
from app.services import agents as agent_service

router = APIRouter(prefix="/tickets", tags=["agents"])


@router.get("/{ticket_id}/agent-trace")
async def get_agent_trace(ticket_id: UUID, session: SessionDep) -> list[AgentLogResponse]:
    """Every agent_logs row for the ticket, oldest first (reruns append new rows)."""
    try:
        logs = await agent_service.get_agent_trace(session, ticket_id)
    except agent_service.TicketNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found") from exc
    return [AgentLogResponse.model_validate(log) for log in logs]


@router.post("/{ticket_id}/rerun", status_code=status.HTTP_202_ACCEPTED)
async def rerun(
    ticket_id: UUID,
    session: SessionDep,
    background: BackgroundTasks,
    session_factory: SessionFactoryDep,
    drafter: Annotated[Drafter, Depends(get_drafter)],
) -> TicketResponse:
    """Re-run the whole agent graph: new predictions, draft and trace rows are added."""
    try:
        ticket = await agent_service.prepare_rerun(session, ticket_id)
    except agent_service.TicketNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found") from exc
    except agent_service.RunInProgress as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "An agent run for this ticket is already in progress") from exc
    background.add_task(run_agent_graph, ticket.id, session_factory, drafter)
    return TicketResponse.model_validate(ticket)

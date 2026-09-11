from uuid import UUID

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from app.agents.drafter import Drafter, get_drafter
from app.agents.runner import run_agent_graph
from app.core.db import SessionFactoryDep
from app.core.deps import CurrentUserDep, SessionDep
from app.core.enums import TicketCategory, TicketStatus, TicketUrgency
from app.schemas.ticket import TicketCreate, TicketDetailResponse, TicketResponse
from app.services import tickets as ticket_service

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_ticket(
    data: TicketCreate,
    user: CurrentUserDep,
    session: SessionDep,
    background: BackgroundTasks,
    session_factory: SessionFactoryDep,
    drafter: Annotated[Drafter, Depends(get_drafter)],
) -> TicketResponse:
    """Save the ticket (status `new`) and return; the agent graph runs in the background."""
    try:
        ticket = await ticket_service.create_ticket(session, data)
    except ticket_service.InvalidTicketReference as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    background.add_task(run_agent_graph, ticket.id, user.tenant_id, session_factory, drafter)
    return TicketResponse.model_validate(ticket)


@router.get("")
async def list_tickets(
    session: SessionDep,
    status: TicketStatus | None = None,
    category: TicketCategory | None = None,
    urgency: TicketUrgency | None = None,
) -> list[TicketResponse]:
    tickets = await ticket_service.list_tickets(session, status, category, urgency)
    return [TicketResponse.model_validate(t) for t in tickets]


@router.get("/{ticket_id}")
async def get_ticket(ticket_id: UUID, session: SessionDep) -> TicketDetailResponse:
    ticket = await ticket_service.get_ticket_detail(session, ticket_id)
    if ticket is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
    return TicketDetailResponse.model_validate(ticket)

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.core.db import SessionDep
from app.core.enums import TicketCategory, TicketStatus, TicketUrgency
from app.schemas.ticket import TicketCreate, TicketDetailResponse, TicketResponse
from app.services import tickets as ticket_service

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_ticket(data: TicketCreate, session: SessionDep) -> TicketResponse:
    try:
        ticket = await ticket_service.create_ticket(session, data)
    except ticket_service.InvalidTicketReference as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
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

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.core.db import SessionDep
from app.schemas.review import ReviewApproveRequest, ReviewEditRequest
from app.schemas.ticket import TicketDetailResponse, TicketResponse
from app.services import reviews as review_service
from app.services import tickets as ticket_service

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.get("/queue")
async def review_queue(session: SessionDep) -> list[TicketResponse]:
    """Tickets with status awaiting_review: escalated first, then by urgency, then oldest."""
    return [TicketResponse.model_validate(t) for t in await review_service.review_queue(session)]


async def _approve(session, ticket_id: UUID, reviewer_id: str, edited_text: str | None) -> TicketDetailResponse:
    try:
        await review_service.approve(session, ticket_id, reviewer_id, edited_text)
    except review_service.TicketNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found") from exc
    except review_service.ReviewConflict as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return TicketDetailResponse.model_validate(await ticket_service.get_ticket_detail(session, ticket_id))


@router.post("/{ticket_id}/approve")
async def approve(ticket_id: UUID, data: ReviewApproveRequest, session: SessionDep) -> TicketDetailResponse:
    """Approve the latest draft as written; the ticket becomes resolved."""
    return await _approve(session, ticket_id, data.reviewer_id, edited_text=None)


@router.post("/{ticket_id}/edit")
async def edit(ticket_id: UUID, data: ReviewEditRequest, session: SessionDep) -> TicketDetailResponse:
    """Approve the latest draft with the reviewer's edits; the ticket becomes resolved."""
    return await _approve(session, ticket_id, data.reviewer_id, edited_text=data.edited_text)

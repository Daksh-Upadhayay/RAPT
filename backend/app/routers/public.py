"""Public endpoints: no account needed (Phase 10b). Only the contact form lives here."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from app.agents.drafter import Drafter, get_drafter
from app.agents.runner import run_agent_graph
from app.core.db import SessionFactoryDep
from app.core.ratelimit import SlidingWindowLimiter
from app.schemas.public import ContactFormInfo, ContactReceipt, ContactRequest
from app.services import contact as contact_service

router = APIRouter(prefix="/public", tags=["public"])

UNAVAILABLE = "This contact form isn't available."
# Per visitor per business, and per business overall: a flood can't bury a queue or
# burn through the free LLM quota
visitor_limiter = SlidingWindowLimiter(limit=5, window_seconds=3600)
business_limiter = SlidingWindowLimiter(limit=100, window_seconds=3600)


@router.get("/contact/{slug}")
async def contact_form(slug: str, factory: SessionFactoryDep) -> ContactFormInfo:
    tenant = await contact_service.find_tenant(factory, slug)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, UNAVAILABLE)
    return ContactFormInfo(business_name=tenant.name)


@router.post("/contact/{slug}", status_code=status.HTTP_202_ACCEPTED)
async def send_message(
    slug: str,
    data: ContactRequest,
    request: Request,
    background: BackgroundTasks,
    factory: SessionFactoryDep,
    drafter: Annotated[Drafter, Depends(get_drafter)],
) -> ContactReceipt:
    """Create a ticket from a customer's message; the business reviews the reply."""
    tenant = await contact_service.find_tenant(factory, slug)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, UNAVAILABLE)
    if data.website:  # honeypot filled: answer like a success, store nothing
        return ContactReceipt(reference=contact_service.fake_reference(), business_name=tenant.name)

    ip = request.client.host if request.client else "unknown"
    if not (visitor_limiter.allow(f"{tenant.id}:{ip}") and business_limiter.allow(str(tenant.id))):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many messages. Please try again in an hour.")

    ticket = await contact_service.submit(factory, tenant, data)
    background.add_task(run_agent_graph, ticket.id, tenant.id, factory, drafter)
    return ContactReceipt(reference=str(ticket.id)[:8].upper(), business_name=tenant.name)

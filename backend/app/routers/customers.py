"""Customer lookup for the Submit Ticket page (05-frontend.md): the form needs a
customer_id, and offers that customer's orders to link."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.core.deps import SessionDep
from app.schemas.customer import CustomerCreate, CustomerResponse
from app.schemas.order import OrderResponse
from app.services import customers as customer_service

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("")
async def search_customers(
    session: SessionDep,
    search: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[CustomerResponse]:
    """Customers whose name or email contains `search`; the first `limit` by name without it."""
    customers = await customer_service.search_customers(session, search, limit)
    return [CustomerResponse.model_validate(c) for c in customers]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_customer(data: CustomerCreate, session: SessionDep) -> CustomerResponse:
    """Add a customer (e.g. while filing their first ticket)."""
    try:
        customer = await customer_service.create_customer(session, data.name, data.email)
    except customer_service.CustomerExists as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "A customer with that email already exists. Search for them instead.") from exc
    return CustomerResponse.model_validate(customer)


@router.get("/{customer_id}")
async def get_customer(customer_id: UUID, session: SessionDep) -> CustomerResponse:
    customer = await customer_service.get_customer(session, customer_id)
    if customer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer not found")
    return CustomerResponse.model_validate(customer)


@router.get("/{customer_id}/orders")
async def customer_orders(customer_id: UUID, session: SessionDep) -> list[OrderResponse]:
    try:
        orders = await customer_service.customer_orders(session, customer_id)
    except customer_service.CustomerNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer not found") from exc
    return [OrderResponse.model_validate(o) for o in orders]

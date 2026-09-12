"""The public contact form: a business's customers send a ticket without an account.

The only cross-tenant step is finding the business by slug (contact_form_tenant(), which
answers only when its form is switched on). Everything after runs in that tenant's
scope, like any request: the customer is found or added by email, the ticket is stored
with channel `contact_form`, and the agents run in the background.
"""

import secrets
import uuid
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.enums import TicketChannel
from app.core.tenancy import tenant_of, tenant_session
from app.models import Customer, Ticket
from app.schemas.public import ContactRequest


@dataclass(frozen=True)
class ContactTenant:
    id: uuid.UUID
    name: str


async def find_tenant(factory: async_sessionmaker[AsyncSession], slug: str) -> ContactTenant | None:
    """The business behind /contact/<slug>, if its form is on (else None, like unknown)."""
    async with factory() as session:
        row = (await session.execute(text("SELECT tenant_id, name FROM contact_form_tenant(:slug)"), {"slug": slug})).first()
    return ContactTenant(row.tenant_id, row.name) if row else None


def fake_reference() -> str:
    """For honeypot hits: looks like a real receipt, so a bot learns nothing."""
    return secrets.token_hex(4)


async def _customer(session: AsyncSession, name: str, email: str) -> Customer:
    customer = await session.scalar(
        select(Customer).where(Customer.tenant_id == tenant_of(session), Customer.email == email)
    )
    if customer is None:
        customer = Customer(name=name, email=email)
        session.add(customer)
        await session.flush()
    return customer


async def submit(factory: async_sessionmaker[AsyncSession], tenant: ContactTenant, data: ContactRequest) -> Ticket:
    async with tenant_session(factory, tenant.id) as session:
        customer = await _customer(session, data.name.strip(), data.email.strip().lower())
        ticket = Ticket(
            customer_id=customer.id,
            subject=data.subject.strip(),
            body=data.message.strip(),
            channel=TicketChannel.CONTACT_FORM,
        )
        session.add(ticket)
        await session.commit()
        await session.refresh(ticket)
        return ticket

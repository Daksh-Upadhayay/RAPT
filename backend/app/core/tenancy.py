"""Tenant scoping for database sessions (Phase 7).

A session opened with `tenant_session(factory, tenant_id)` carries the tenant in
`session.info`. At the start of every transaction (the agent pipeline commits after
each step, so there are many per session) it runs `set_config('app.tenant_id', ...,
true)`. Two things read that setting:

- the row-level security policies on every tenant table (the API's database role is
  subject to them), so a query can only see and write its own tenant's rows;
- the `tenant_id` column default, so inserted rows land in the session's tenant without
  the caller setting it, and an insert with no tenant in scope fails (NOT NULL).

Services also filter by `tenant_of(session)` explicitly: the owner connection used by
scripts bypasses RLS, and the explicit filter keeps them correct too.
"""

import uuid

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session

TENANT_KEY = "tenant_id"

# SQL for the current transaction's tenant; NULLIF turns an unset setting ('') into NULL,
# which matches no row and fails a NOT NULL insert.
CURRENT_TENANT_SQL = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"


class NoTenantInScope(RuntimeError):
    """A tenant-scoped operation ran on a session opened without a tenant."""


@event.listens_for(Session, "after_begin")
def _scope_transaction(session: Session, transaction, connection) -> None:
    tenant_id = session.info.get(TENANT_KEY)
    if tenant_id is not None:
        connection.execute(text("SELECT set_config('app.tenant_id', :tenant_id, true)"), {"tenant_id": str(tenant_id)})


def tenant_session(factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID) -> AsyncSession:
    """A session whose every transaction is scoped to `tenant_id`."""
    return factory(info={TENANT_KEY: tenant_id})


def tenant_of(session: AsyncSession) -> uuid.UUID:
    tenant_id = session.info.get(TENANT_KEY)
    if tenant_id is None:
        raise NoTenantInScope("this operation needs a tenant-scoped session (app.core.tenancy.tenant_session)")
    return tenant_id


async def get_scoped[M](session: AsyncSession, model: type[M], id_: uuid.UUID) -> M | None:
    """`session.get`, but only returns a row of the session's tenant."""
    obj = await session.get(model, id_)
    return obj if obj is not None and obj.tenant_id == tenant_of(session) else None

"""The owner connection, for the operator CLI, seed and ML scripts (never the API).

It bypasses row-level security, so everything using it works inside an explicit tenant
(`--tenant <slug>`): sessions are tenant-scoped (inserts default to that tenant) and the
services filter by tenant themselves.
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.tenancy import tenant_session
from app.models import Tenant


class UnknownTenant(LookupError):
    pass


@asynccontextmanager
async def admin_factory(url: str | None = None) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine: AsyncEngine = create_async_engine(url or settings.admin_database_url)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


async def tenant_id_for(factory: async_sessionmaker[AsyncSession], slug: str) -> uuid.UUID:
    async with factory() as session:
        tenant_id = await session.scalar(select(Tenant.id).where(Tenant.slug == slug))
    if tenant_id is None:
        raise UnknownTenant(f"No tenant with slug {slug!r} (list them: python -m scripts.tenants list)")
    return tenant_id


@asynccontextmanager
async def admin_tenant_session(slug: str) -> AsyncIterator[AsyncSession]:
    """A session on the owner connection, scoped to the tenant with this slug."""
    async with admin_factory() as factory:
        tenant_id = await tenant_id_for(factory, slug)
        async with tenant_session(factory, tenant_id) as session:
            yield session

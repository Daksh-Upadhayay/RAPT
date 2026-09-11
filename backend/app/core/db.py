from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# The API's engine: connects as the restricted role, so row-level security applies.
# Request sessions come from app.core.deps.get_session (tenant-scoped, authenticated).
engine = create_async_engine(settings.database_url)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Opens the API's sessions: request sessions (via app.core.deps) and background agent
    runs, which outlive the request. A dependency so tests can point it at the test
    database."""
    return SessionLocal


SessionFactoryDep = Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)]

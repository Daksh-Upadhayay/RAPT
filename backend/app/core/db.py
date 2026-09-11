from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(settings.database_url)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """For work that outlives the request (background agent runs), which can't use the
    request's session. A dependency so tests can point it at the test database."""
    return SessionLocal


SessionFactoryDep = Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)]

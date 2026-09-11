"""Test fixtures. Tests run against a real Postgres database (settings.test_database_url),
which is reset and migrated with Alembic once per test session."""

import asyncio
from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.agents.drafter import DraftResult, get_drafter
from app.core.db import get_session, get_session_factory
from app.core.enums import OrderStatus
from app.main import app
from app.models import Base, Customer, Order

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def alembic_config() -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", settings.test_database_url)
    return cfg


async def reset_schema() -> None:
    engine = create_async_engine(settings.test_database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> None:
    # Build the test schema from an empty database using the real migrations
    asyncio.run(reset_schema())
    command.upgrade(alembic_config(), "head")


@pytest.fixture
def alembic_cfg() -> Config:
    return alembic_config()


@pytest.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    # NullPool: pytest-asyncio gives each test its own event loop, and asyncpg
    # connections can't be shared across loops
    engine = create_async_engine(settings.test_database_url, poolclass=NullPool)
    yield async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
        await conn.execute(text(f"TRUNCATE {tables} CASCADE"))
    await engine.dispose()


@pytest.fixture
async def session(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


class FakeDrafter:
    """Stands in for Claude: records the prompts and returns a fixed draft (no network)."""

    def __init__(self, text: str = "Hi, thanks for reaching out. Customer Support") -> None:
        self.text = text
        self.calls: list[tuple[str, str]] = []

    async def draft(self, system: str, user: str) -> DraftResult:
        self.calls.append((system, user))
        return DraftResult(text=self.text, mode="fake", model="fake-model")


@pytest.fixture
def drafter() -> FakeDrafter:
    return FakeDrafter()


@pytest.fixture
async def client(
    session_factory: async_sessionmaker[AsyncSession], drafter: FakeDrafter
) -> AsyncIterator[AsyncClient]:
    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    # Background agent runs: test database + fake drafter. ASGITransport waits for
    # background tasks, so a run has finished by the time the request returns.
    app.dependency_overrides[get_session_factory] = lambda: session_factory
    app.dependency_overrides[get_drafter] = lambda: drafter
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
async def customer(session: AsyncSession) -> Customer:
    customer = Customer(name="Ada Lovelace", email="ada@example.com")
    session.add(customer)
    await session.commit()
    return customer


@pytest.fixture
async def order(session: AsyncSession, customer: Customer) -> Order:
    order = Order(
        customer_id=customer.id,
        item_name="Wireless Headphones",
        status=OrderStatus.SHIPPED,
        tracking_number="1Z999AA10123456784",
        amount=Decimal("149.99"),
        order_date=date(2026, 9, 1),
        expected_delivery=date(2026, 9, 8),
    )
    session.add(order)
    await session.commit()
    return order

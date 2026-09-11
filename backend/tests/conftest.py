"""Test fixtures. Tests run against a real Postgres database, reset and migrated with Alembic
once per session.

Two connections, like production: the owner (`admin_factory`: migrations, setup, cleanup)
and the restricted API role (`session_factory`), which row-level security applies to. The
`client` is signed in as a user of the `tenant` fixture through a real session cookie.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from alembic import command
from app.agents.drafter import DraftResult, get_drafter
from app.core.config import settings
from app.core.db import get_session_factory
from app.core.enums import OrderStatus, UserRole
from app.core.security import SESSION_COOKIE, create_token, hash_password
from app.core.tenancy import tenant_session
from app.main import app
from app.models import Base, Customer, Order, Tenant, User
from app.routers.auth import email_limiter, ip_limiter

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"
PASSWORD = "correct horse battery staple"
BASE_URL = "https://test"  # https, so the Secure session cookie is sent back
CSRF = {"X-RAPT-CSRF": "1"}


def alembic_config() -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", settings.test_admin_database_url)
    return cfg


async def reset_schema() -> None:
    engine = create_async_engine(settings.test_admin_database_url, poolclass=NullPool)
    role = settings.app_db_role
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        # The API's restricted role (created once per cluster; see backend/README.md)
        await conn.execute(
            text(
                f"DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{role}') THEN "
                f"CREATE ROLE {role} LOGIN NOSUPERUSER NOBYPASSRLS; END IF; END $$"
            )
        )
    await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> None:
    # Build the test schema from an empty database using the real migrations
    asyncio.run(reset_schema())
    command.upgrade(alembic_config(), "head")


@pytest.fixture
def alembic_cfg() -> Config:
    return alembic_config()


@pytest.fixture(autouse=True)
def reset_login_limits() -> None:
    email_limiter.clear()
    ip_limiter.clear()


@pytest.fixture
async def admin_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Owner connection (bypasses RLS). Empties every table after the test."""
    # NullPool: pytest-asyncio gives each test its own event loop, and asyncpg
    # connections can't be shared across loops
    engine = create_async_engine(settings.test_admin_database_url, poolclass=NullPool)
    yield async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
        await conn.execute(text(f"TRUNCATE {tables} CASCADE"))
    await engine.dispose()


@pytest.fixture
async def session_factory(admin_factory) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """The API's restricted role: row-level security applies."""
    engine = create_async_engine(settings.test_database_url, poolclass=NullPool)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@dataclass(frozen=True)
class Account:
    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    role: str

    def cookies(self) -> dict[str, str]:
        return {SESSION_COOKIE: create_token(self.id, self.tenant_id, self.role)}


async def make_tenant(admin_factory, name: str, slug: str) -> Tenant:
    async with admin_factory() as session:
        tenant = Tenant(name=name, slug=slug)
        session.add(tenant)
        await session.commit()
        return tenant


async def make_user(admin_factory, tenant: Tenant, email: str, role: UserRole = UserRole.ADMIN, password: str = PASSWORD) -> Account:
    async with admin_factory() as session:
        user = User(tenant_id=tenant.id, email=email, name=email.split("@")[0].title(), password_hash=hash_password(password), role=role)
        session.add(user)
        await session.commit()
        return Account(user.id, tenant.id, user.email, user.role)


@pytest.fixture
async def tenant(admin_factory) -> Tenant:
    return await make_tenant(admin_factory, "Acme Homewares", "acme")


@pytest.fixture
async def other_tenant(admin_factory) -> Tenant:
    return await make_tenant(admin_factory, "Globex Outdoor", "globex")


@pytest.fixture
async def user(admin_factory, tenant: Tenant) -> Account:
    return await make_user(admin_factory, tenant, "ada@acme.example")


@pytest.fixture
async def session(session_factory, tenant: Tenant) -> AsyncIterator[AsyncSession]:
    """A session scoped to `tenant`, on the restricted role (like a request's session)."""
    async with tenant_session(session_factory, tenant.id) as session:
        yield session


class FakeDrafter:
    """Stands in for the LLM: records the prompts and returns a fixed draft (no network)."""

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
def api(session_factory, drafter: FakeDrafter):
    """Point the app at the test database and the fake drafter; yields a client maker."""
    # Background agent runs: test database + fake drafter. ASGITransport waits for
    # background tasks, so a run has finished by the time the request returns.
    app.dependency_overrides[get_session_factory] = lambda: session_factory
    app.dependency_overrides[get_drafter] = lambda: drafter

    def make(account: Account | None = None, csrf: bool = True) -> AsyncClient:
        return AsyncClient(
            transport=ASGITransport(app=app),
            base_url=BASE_URL,
            cookies=account.cookies() if account else None,
            headers=CSRF if csrf else None,
        )

    yield make
    app.dependency_overrides.clear()


@pytest.fixture
async def client(api, user: Account) -> AsyncIterator[AsyncClient]:
    """Signed in as `user` (an admin of `tenant`)."""
    async with api(user) as client:
        yield client


@pytest.fixture
async def anon_client(api) -> AsyncIterator[AsyncClient]:
    async with api() as client:
        yield client


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

"""Prepare the database on every deploy (Phase 10): run by the `migrate` container.

1. Create the API's restricted role (APP_DB_ROLE, default rapt_app) if it's missing, and
   set its password from APP_DB_PASSWORD. It has no superuser or BYPASSRLS, so row-level
   security applies to everything the API does.
2. Apply migrations as the owner (ADMIN_DATABASE_URL); they grant the role its access.

Safe to rerun: both steps are idempotent.
"""

import asyncio
import os
import re

from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command
from app.core.config import settings

ROLE_NAME = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


async def ensure_app_role(password: str) -> None:
    role = settings.app_db_role
    if not ROLE_NAME.match(role):
        raise SystemExit(f"APP_DB_ROLE {role!r} isn't a plain lowercase identifier")
    engine = create_async_engine(settings.admin_database_url)
    try:
        async with engine.begin() as conn:
            exists = await conn.scalar(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": role})
            if not exists:
                await conn.execute(text(f"CREATE ROLE {role} LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE"))
            # Password as a literal (DDL takes no bind parameters); quotes escaped
            quoted = password.replace("'", "''")
            await conn.execute(text(f"ALTER ROLE {role} WITH LOGIN PASSWORD '{quoted}'"))
    finally:
        await engine.dispose()
    print(f"Role {role} ready")


def migrate() -> None:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", settings.admin_database_url)
    command.upgrade(cfg, "head")


def main() -> None:
    password = os.environ.get("APP_DB_PASSWORD")
    if not password:
        raise SystemExit("APP_DB_PASSWORD is not set")
    asyncio.run(ensure_app_role(password))
    migrate()
    print("Database ready")


if __name__ == "__main__":
    main()

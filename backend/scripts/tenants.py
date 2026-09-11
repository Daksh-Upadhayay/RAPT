"""Operator CLI: tenants and users. Accounts are invite-only (Phase 7), so this is how a
business gets onto RAPT. Uses the owner connection (ADMIN_DATABASE_URL).

Usage (from backend/):
    uv run python -m scripts.tenants list
    uv run python -m scripts.tenants create-tenant --name "Acme Homewares" --slug acme
    uv run python -m scripts.tenants create-user --tenant acme --email ops@acme.com --name "Ada" --role admin
    uv run python -m scripts.tenants reset-password --email ops@acme.com
    uv run python -m scripts.tenants deactivate-user --email ops@acme.com

create-user and reset-password print a one-time password: hand it to the person over a
private channel. Resetting a password signs that user out everywhere.
"""

import argparse
import asyncio
import re
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.admin_db import UnknownTenant, admin_factory, tenant_id_for
from app.core.enums import UserRole
from app.core.security import generate_password, hash_password
from app.models import Tenant, Ticket, User

SLUG = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?$")


class CliError(Exception):
    pass


async def list_tenants(factory) -> list[str]:
    async with factory() as session:
        rows = await session.execute(
            select(Tenant.slug, Tenant.name, func.count(func.distinct(User.id)), func.count(func.distinct(Ticket.id)))
            .outerjoin(User, User.tenant_id == Tenant.id)
            .outerjoin(Ticket, Ticket.tenant_id == Tenant.id)
            .group_by(Tenant.id)
            .order_by(Tenant.slug)
        )
        return [f"{slug:<20} {name:<30} {users} users, {tickets} tickets" for slug, name, users, tickets in rows]


async def create_tenant(factory, name: str, slug: str) -> Tenant:
    if not SLUG.match(slug):
        raise CliError("slug: 1-40 lowercase letters, digits or hyphens, not starting or ending with a hyphen")
    async with factory() as session:
        tenant = Tenant(name=name.strip(), slug=slug)
        session.add(tenant)
        try:
            await session.commit()
        except IntegrityError as exc:
            raise CliError(f"a tenant with slug {slug!r} already exists") from exc
        return tenant


async def create_user(factory, tenant_slug: str, email: str, name: str, role: UserRole) -> str:
    tenant_id = await tenant_id_for(factory, tenant_slug)
    password = generate_password()
    async with factory() as session:
        session.add(
            User(tenant_id=tenant_id, email=email.strip().lower(), name=name.strip(), password_hash=hash_password(password), role=role)
        )
        try:
            await session.commit()
        except IntegrityError as exc:
            raise CliError(f"a user with email {email!r} already exists") from exc
    return password


async def _user(session, email: str) -> User:
    user = await session.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None:
        raise CliError(f"no user with email {email!r}")
    return user


async def reset_password(factory, email: str) -> str:
    password = generate_password()
    async with factory() as session:
        user = await _user(session, email)
        user.password_hash = hash_password(password)
        user.password_changed_at = datetime.now(UTC)  # existing sessions stop working
        user.is_active = True
        await session.commit()
    return password


async def deactivate_user(factory, email: str) -> None:
    async with factory() as session:
        user = await _user(session, email)
        user.is_active = False
        await session.commit()


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    p = sub.add_parser("create-tenant")
    p.add_argument("--name", required=True)
    p.add_argument("--slug", required=True)
    p = sub.add_parser("create-user")
    p.add_argument("--tenant", required=True, help="tenant slug")
    p.add_argument("--email", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--role", choices=[r.value for r in UserRole], default=UserRole.REVIEWER.value)
    for command in ("reset-password", "deactivate-user"):
        sub.add_parser(command).add_argument("--email", required=True)
    args = parser.parse_args()

    async with admin_factory() as factory:
        try:
            match args.command:
                case "list":
                    print("\n".join(await list_tenants(factory)) or "No tenants yet.")
                case "create-tenant":
                    tenant = await create_tenant(factory, args.name, args.slug)
                    print(f"Created tenant {tenant.slug} ({tenant.id})")
                case "create-user":
                    password = await create_user(factory, args.tenant, args.email, args.name, UserRole(args.role))
                    print(f"Created {args.role} {args.email.lower()} in {args.tenant}. One-time password: {password}")
                case "reset-password":
                    print(f"New password for {args.email.lower()}: {await reset_password(factory, args.email)}")
                case "deactivate-user":
                    await deactivate_user(factory, args.email)
                    print(f"Deactivated {args.email.lower()}")
        except (CliError, UnknownTenant) as exc:
            raise SystemExit(f"Error: {exc}") from exc


if __name__ == "__main__":
    asyncio.run(main())

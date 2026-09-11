"""A tenant's users, managed by its admins (Phase 9). Row-level security keeps every
query inside the admin's tenant; these functions add the business rules."""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import UserRole
from app.core.security import generate_password, hash_password
from app.core.tenancy import get_scoped, tenant_of
from app.models import User


class MemberNotFound(Exception):
    pass


class EmailTaken(Exception):
    pass


class SelfChange(Exception):
    """An admin tried to demote or deactivate themselves (they could lock the tenant out)."""


async def list_members(session: AsyncSession) -> Sequence[User]:
    stmt = select(User).where(User.tenant_id == tenant_of(session)).order_by(User.is_active.desc(), User.name)
    return (await session.scalars(stmt)).all()


async def invite(session: AsyncSession, email: str, name: str, role: UserRole) -> tuple[User, str]:
    password = generate_password()
    user = User(email=email.strip().lower(), name=name.strip(), role=role, password_hash=hash_password(password))
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:  # emails are unique across all tenants (login has no tenant field)
        await session.rollback()
        raise EmailTaken from exc
    await session.refresh(user)
    return user, password


async def _member(session: AsyncSession, member_id: UUID) -> User:
    user = await get_scoped(session, User, member_id)
    if user is None:
        raise MemberNotFound
    return user


async def update_member(session: AsyncSession, member_id: UUID, acting_admin: UUID, role: UserRole | None, is_active: bool | None) -> User:
    user = await _member(session, member_id)
    if user.id == acting_admin and (role not in (None, UserRole.ADMIN) or is_active is False):
        raise SelfChange
    if role is not None:
        user.role = role
    if is_active is not None:
        user.is_active = is_active
    await session.commit()
    await session.refresh(user)
    return user


async def reset_password(session: AsyncSession, member_id: UUID) -> tuple[User, str]:
    user = await _member(session, member_id)
    password = generate_password()
    user.password_hash = hash_password(password)
    user.password_changed_at = datetime.now(UTC)  # signs them out everywhere
    await session.commit()
    await session.refresh(user)
    return user, password

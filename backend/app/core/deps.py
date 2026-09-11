"""Request dependencies: who is calling, and a database session scoped to their tenant.

The tenant comes only from the signed session cookie (a JWT), never from a request body,
path or query. Every route that takes `SessionDep` is therefore authenticated and
tenant-scoped.
"""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionFactoryDep
from app.core.enums import UserRole
from app.core.security import SESSION_COOKIE, InvalidToken, decode_token
from app.core.tenancy import tenant_session
from app.models import Tenant, User


@dataclass(frozen=True)
class CurrentUser:
    id: uuid.UUID
    tenant_id: uuid.UUID
    tenant_name: str
    email: str
    name: str
    role: UserRole


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail)


async def get_current_user(request: Request, factory: SessionFactoryDep) -> CurrentUser:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise _unauthorized("Sign in to continue.")
    try:
        claims = decode_token(token)
    except InvalidToken as exc:
        raise _unauthorized("Your session has ended. Sign in again.") from exc

    # Read the user inside their own tenant: RLS hides a user the token misattributes
    async with tenant_session(factory, claims.tenant_id) as session:
        row = (
            await session.execute(
                select(User, Tenant.name).join(Tenant, Tenant.id == User.tenant_id).where(User.id == claims.user_id)
            )
        ).first()
    if row is None:
        raise _unauthorized("Your session has ended. Sign in again.")
    user, tenant_name = row
    # Tokens issued before a password reset (or for a deactivated user) no longer work
    if not user.is_active or user.tenant_id != claims.tenant_id or claims.issued_at < user.password_changed_at:
        raise _unauthorized("Your session has ended. Sign in again.")
    return CurrentUser(
        id=user.id, tenant_id=user.tenant_id, tenant_name=tenant_name, email=user.email, name=user.name, role=UserRole(user.role)
    )


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


async def require_admin(user: CurrentUserDep) -> CurrentUser:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only a tenant admin can do this.")
    return user


AdminDep = Annotated[CurrentUser, Depends(require_admin)]


async def get_session(user: CurrentUserDep, factory: SessionFactoryDep) -> AsyncIterator[AsyncSession]:
    """A session whose every transaction is scoped to the caller's tenant."""
    async with tenant_session(factory, user.tenant_id) as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]

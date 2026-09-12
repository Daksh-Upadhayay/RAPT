"""Sign in / out. Accounts are invite-only: the operator creates them (scripts/tenants.py)."""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select, text, update

from app.core.config import settings
from app.core.db import SessionFactoryDep
from app.core.deps import CurrentUser, CurrentUserDep
from app.core.enums import UserRole
from app.core.ratelimit import SlidingWindowLimiter
from app.core.security import SESSION_COOKIE, create_token, verify_password
from app.core.tenancy import tenant_session
from app.models import Tenant, User
from app.schemas.auth import LoginRequest, MeResponse

router = APIRouter(prefix="/auth", tags=["auth"])

WINDOW_SECONDS = settings.login_window_minutes * 60
# Per email (guessing one account's password) and per client IP (spraying many accounts)
email_limiter = SlidingWindowLimiter(settings.login_attempts_per_window, WINDOW_SECONDS)
ip_limiter = SlidingWindowLimiter(settings.login_attempts_per_window * 5, WINDOW_SECONDS)


def _me(user: CurrentUser) -> MeResponse:
    return MeResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        tenant_id=user.tenant_id,
        tenant_name=user.tenant_name,
        tenant_slug=user.tenant_slug,
    )


@router.post("/login")
async def login(data: LoginRequest, request: Request, response: Response, factory: SessionFactoryDep) -> MeResponse:
    email = data.email.strip().lower()
    ip = request.client.host if request.client else "unknown"
    if not (email_limiter.allow(email) and ip_limiter.allow(ip)):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many sign-in attempts. Wait a few minutes and try again.")

    # The one lookup that crosses tenants, through a function that returns only this
    async with factory() as session:
        found = (await session.execute(text("SELECT * FROM auth_find_user(:email)"), {"email": email})).first()
    # Always verify a hash, so unknown emails take as long as wrong passwords
    if not verify_password(found.password_hash if found else None, data.password) or not found.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "That email and password don't match an active account.")

    async with tenant_session(factory, found.tenant_id) as session:
        await session.execute(update(User).where(User.id == found.id).values(last_login_at=datetime.now(UTC)))
        user = (
            await session.execute(select(User, Tenant.name, Tenant.slug).join(Tenant, Tenant.id == User.tenant_id).where(User.id == found.id))
        ).one()
        await session.commit()
    account, tenant_name, tenant_slug = user

    email_limiter.reset(email)
    response.set_cookie(
        SESSION_COOKIE,
        create_token(account.id, account.tenant_id, account.role),
        max_age=settings.jwt_ttl_hours * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return MeResponse(
        id=account.id,
        email=account.email,
        name=account.name,
        role=UserRole(account.role),
        tenant_id=account.tenant_id,
        tenant_name=tenant_name,
        tenant_slug=tenant_slug,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", secure=settings.cookie_secure, httponly=True, samesite="lax")


@router.get("/me")
async def me(user: CurrentUserDep) -> MeResponse:
    return _me(user)

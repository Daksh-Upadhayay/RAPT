"""Passwords (argon2id) and session tokens (HS256 JWTs)."""

import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import cache

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import settings

logger = logging.getLogger(__name__)

_hasher = PasswordHasher()  # argon2id with the library's current recommended parameters
# Verified when an email doesn't exist, so a login takes as long either way
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))

JWT_ALGORITHM = "HS256"
SESSION_COOKIE = "rapt_session"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def generate_password() -> str:
    """A one-time password for the operator CLI to hand to a new user."""
    return secrets.token_urlsafe(12)


@cache
def _secret() -> str:
    if settings.jwt_secret is not None:
        return settings.jwt_secret.get_secret_value()
    # Dev convenience only: sessions stop working whenever the server restarts
    logger.warning("JWT_SECRET is not set: using a random secret for this process. Set it in .env.")
    return secrets.token_urlsafe(48)


@dataclass(frozen=True)
class TokenClaims:
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    role: str
    issued_at: datetime


def create_token(user_id: uuid.UUID, tenant_id: uuid.UUID, role: str, now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "role": role,
        # Sub-second precision (JWT allows it): a token issued in the same second as a
        # password reset must still count as older than the reset
        "iat": now.timestamp(),
        "exp": int((now + timedelta(hours=settings.jwt_ttl_hours)).timestamp()),
    }
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


class InvalidToken(Exception):
    pass


def decode_token(token: str) -> TokenClaims:
    """Verify signature and expiry; raises InvalidToken on anything wrong."""
    try:
        payload = jwt.decode(token, _secret(), algorithms=[JWT_ALGORITHM], options={"require": ["sub", "exp", "iat"]})
        return TokenClaims(
            user_id=uuid.UUID(payload["sub"]),
            tenant_id=uuid.UUID(payload["tenant_id"]),
            role=str(payload["role"]),
            issued_at=datetime.fromtimestamp(payload["iat"], UTC),
        )
    except (jwt.PyJWTError, KeyError, ValueError, TypeError) as exc:
        raise InvalidToken(str(exc)) from exc

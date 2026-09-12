import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import UserRole
from app.models.base import Base, check_in, created_at_column, tenant_id_column, uuid_pk


class Tenant(Base):
    """A business using RAPT. Every other row belongs to exactly one tenant."""

    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(Text)
    slug: Mapped[str] = mapped_column(Text, unique=True)
    # The public contact form at /contact/<slug> (off until an admin turns it on)
    contact_form_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_at: Mapped[datetime] = created_at_column()


class User(Base):
    """A person who signs in: one tenant each, invite-only (created by the operator CLI)."""

    __tablename__ = "users"
    __table_args__ = (check_in("role", UserRole),)

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_id_column()
    # Unique across tenants: the login form has no tenant field
    email: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    # Tokens issued before this are rejected (password reset signs everyone out)
    password_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_column()

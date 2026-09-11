from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import UserRole


class TeamMember(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    name: str
    role: UserRole
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime


class InviteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    name: str = Field(min_length=1, max_length=120)
    role: UserRole = UserRole.REVIEWER


class MemberUpdate(BaseModel):
    """Change a member's role and/or whether they can sign in."""

    model_config = ConfigDict(extra="forbid")

    role: UserRole | None = None
    is_active: bool | None = None


class PasswordIssued(BaseModel):
    """A one-time password, shown once: the admin passes it on (there's no email service)."""

    member: TeamMember
    one_time_password: str

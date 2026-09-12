from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import UserRole


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=200)


class MeResponse(BaseModel):
    """The signed-in user and their tenant."""

    id: UUID
    email: str
    name: str
    role: UserRole
    tenant_id: UUID
    tenant_name: str
    tenant_slug: str  # for the public contact form link

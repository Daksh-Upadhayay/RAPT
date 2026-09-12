from pydantic import BaseModel, ConfigDict, Field

EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class ContactFormInfo(BaseModel):
    """What the public contact page shows before anything is sent."""

    business_name: str


class ContactRequest(BaseModel):
    """A message from a business's customer. No account; spam defences in the service."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=320, pattern=EMAIL)
    subject: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=10, max_length=5000)
    # Honeypot: hidden from people, so anything here was typed by a bot
    website: str = Field(default="", max_length=200)


class ContactReceipt(BaseModel):
    reference: str  # short, for the customer to quote; not the ticket id
    business_name: str


class TenantSettings(BaseModel):
    name: str
    slug: str
    contact_form_enabled: bool


class TenantSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contact_form_enabled: bool

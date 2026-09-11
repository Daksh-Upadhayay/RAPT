from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import TicketCategory, TicketUrgency


# Request bodies forbid unknown fields: a tenant_id (or anything else) in a body is a 422,
# never silently used. The reviewer is the signed-in user.


class ReviewEditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edited_text: str = Field(min_length=1)


class TriageCorrectionRequest(BaseModel):
    """The reviewer's view of the triage; replaces any earlier correction. A value equal
    to the model's label, or null, means "no correction" for that field."""

    model_config = ConfigDict(extra="forbid")

    corrected_category: TicketCategory | None = None
    corrected_urgency: TicketUrgency | None = None

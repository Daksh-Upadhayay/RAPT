from pydantic import BaseModel, Field

from app.core.enums import TicketCategory, TicketUrgency


class ReviewApproveRequest(BaseModel):
    reviewer_id: str = Field(min_length=1)  # placeholder identity until there is auth


class ReviewEditRequest(BaseModel):
    edited_text: str = Field(min_length=1)
    reviewer_id: str = Field(min_length=1)


class TriageCorrectionRequest(BaseModel):
    """The reviewer's view of the triage; replaces any earlier correction. A value equal
    to the model's label, or null, means "no correction" for that field."""

    corrected_category: TicketCategory | None = None
    corrected_urgency: TicketUrgency | None = None
    reviewer_id: str = Field(min_length=1)

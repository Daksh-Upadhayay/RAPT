from pydantic import BaseModel, Field

from app.core.enums import TicketCategory, TicketUrgency


class CategoryPrediction(BaseModel):
    label: TicketCategory
    confidence: float = Field(ge=0, le=1)
    model_version: str


class UrgencyPrediction(BaseModel):
    label: TicketUrgency
    confidence: float = Field(ge=0, le=1)
    model_version: str

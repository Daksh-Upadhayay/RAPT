from pydantic import BaseModel, Field


class ReviewApproveRequest(BaseModel):
    reviewer_id: str = Field(min_length=1)  # placeholder identity until there is auth


class ReviewEditRequest(BaseModel):
    edited_text: str = Field(min_length=1)
    reviewer_id: str = Field(min_length=1)

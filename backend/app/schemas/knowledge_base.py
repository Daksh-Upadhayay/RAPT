from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeBaseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)


class KnowledgeBaseResponse(BaseModel):
    """An entry as the API returns it; the embedding stays internal."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    content: str
    created_at: datetime


class RetrievedDoc(BaseModel):
    """Knowledge Agent tool output (03-agent-architecture.md)."""

    id: str
    title: str
    content: str
    similarity: float  # cosine similarity to the query, -1..1 (higher = closer)

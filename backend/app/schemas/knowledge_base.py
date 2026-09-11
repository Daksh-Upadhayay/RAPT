from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import DocumentSource, DocumentStatus


class KnowledgeBaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)


class KnowledgeBaseResponse(BaseModel):
    """An entry as the API returns it; the embedding stays internal."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID | None  # the document it's a section of, if any
    position: int | None
    title: str
    content: str
    created_at: datetime


class KnowledgeBaseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)


class KnowledgePasteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=500_000)


class KnowledgeDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    source: DocumentSource
    filename: str | None
    status: DocumentStatus
    error: str | None
    section_count: int
    uploaded_by: str
    created_at: datetime


class KnowledgeDocumentDetail(KnowledgeDocumentResponse):
    sections: list[KnowledgeBaseResponse]


class KnowledgeUploadResult(BaseModel):
    """One uploaded file: its new document, or why it wasn't added."""

    filename: str
    document: KnowledgeDocumentResponse | None
    error: str | None


class KnowledgeSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=5000)
    k: int = Field(default=3, ge=1, le=10)


class RetrievedDoc(BaseModel):
    """Knowledge Agent tool output (03-agent-architecture.md)."""

    id: str
    title: str
    content: str
    similarity: float  # cosine similarity to the query, -1..1 (higher = closer)

import uuid
from datetime import datetime

from sqlalchemy import Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import DocumentSource, DocumentStatus
from app.models.base import Base, check_in, created_at_column, tenant_id_column, tenant_key, uuid_pk


class KnowledgeDocument(Base):
    """A help document a tenant uploaded or pasted (Phase 9). Its text is split into
    sections, each stored as a knowledge_base entry pointing back here."""

    __tablename__ = "kb_documents"
    __table_args__ = (
        check_in("status", DocumentStatus),
        check_in("source", DocumentSource),
        tenant_key("kb_documents"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_id_column()
    title: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    filename: Mapped[str | None] = mapped_column(Text)
    # Extracted text, with headings as Markdown "#" lines: what the sections come from
    content: Mapped[str] = mapped_column(Text)
    # sha256 of the extracted text: the same document can't be added twice
    content_hash: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default=DocumentStatus.PROCESSING.value)
    error: Mapped[str | None] = mapped_column(Text)
    section_count: Mapped[int] = mapped_column(Integer, server_default="0")
    uploaded_by: Mapped[str] = mapped_column(Text)  # the admin's email
    created_at: Mapped[datetime] = created_at_column()

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import EMBEDDING_DIM
from app.models.base import Base, created_at_column, tenant_id_column, uuid_pk


class KnowledgeBaseEntry(Base):
    __tablename__ = "knowledge_base"
    __table_args__ = (
        # Approximate nearest-neighbour index for cosine distance (the `<=>` operator).
        # Overkill for a few dozen rows, where Postgres just scans, but it keeps search
        # fast as the knowledge base grows.
        Index(
            "ix_knowledge_base_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    # Search always filters by tenant: retrieval never crosses tenants (Phase 7)
    tenant_id: Mapped[uuid.UUID] = tenant_id_column()
    title: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    # Embedding of "title. content", unit length (see app/ml/embeddings.py). Accepts a
    # numpy array on write; pgvector returns a list of floats on read.
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    created_at: Mapped[datetime] = created_at_column()

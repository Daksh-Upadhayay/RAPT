"""knowledge base + pgvector

Revision ID: a3f9c1d27e45
Revises: 0d42cc71042e
Create Date: 2026-09-11 09:00:00.000000

The vector dimension (384) matches EMBEDDING_DIM / sentence-transformers/all-MiniLM-L6-v2.
A different embedding model needs a new migration and a re-embed of every row.
"""
from typing import Sequence, Union

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3f9c1d27e45"
down_revision: Union[str, Sequence[str], None] = "0d42cc71042e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "knowledge_base",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(dim=384), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_base")),
    )
    op.create_index(
        "ix_knowledge_base_embedding",
        "knowledge_base",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_knowledge_base_embedding", table_name="knowledge_base", postgresql_using="hnsw")
    op.drop_table("knowledge_base")
    op.execute("DROP EXTENSION IF EXISTS vector")

"""knowledge documents, team management grants (Phase 9)

Revision ID: a8d3f6b2c9e4
Revises: f2c5a8d1e7b3
Create Date: 2026-09-12 15:00:00.000000

- kb_documents: uploaded/pasted help documents; knowledge_base entries point to the
  document they came from (same-tenant FK, cascade on delete), in order
- row-level security + grants for kb_documents, like every tenant table
- the API role may now create users and change their name, role, active flag and
  password (the Team page), still only inside its tenant (RLS)
- unfinished_kb_documents(): documents a restart left `processing`, reprocessed at startup
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.core.config import settings

revision: str = "a8d3f6b2c9e4"
down_revision: Union[str, Sequence[str], None] = "f2c5a8d1e7b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CURRENT_TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"


def _grant(sql: str) -> None:
    role = settings.app_db_role
    op.execute(f"DO $$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname = '{role}') THEN {sql.format(role=role)}; END IF; END $$")


def upgrade() -> None:
    op.create_table(
        "kb_documents",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), server_default=sa.text(CURRENT_TENANT), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="processing", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("section_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("uploaded_by", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('processing', 'ready', 'failed')", name=op.f("ck_kb_documents_status_valid")),
        sa.CheckConstraint("source IN ('upload', 'paste')", name=op.f("ck_kb_documents_source_valid")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_kb_documents_tenant_id_tenants")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_kb_documents")),
        sa.UniqueConstraint("tenant_id", "id", name="uq_kb_documents_tenant_id_id"),
    )
    op.create_index(op.f("ix_kb_documents_tenant_id"), "kb_documents", ["tenant_id"])
    op.execute("ALTER TABLE kb_documents ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON kb_documents USING (tenant_id = {CURRENT_TENANT}) WITH CHECK (tenant_id = {CURRENT_TENANT})"
    )

    op.add_column("knowledge_base", sa.Column("document_id", sa.UUID(), nullable=True))
    op.add_column("knowledge_base", sa.Column("position", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_knowledge_base_document_id"), "knowledge_base", ["document_id"])
    op.create_foreign_key(
        op.f("fk_knowledge_base_tenant_id_kb_documents"),
        "knowledge_base",
        "kb_documents",
        ["tenant_id", "document_id"],
        ["tenant_id", "id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint("uq_knowledge_base_document_id_position", "knowledge_base", ["document_id", "position"])

    op.execute(
        """
        CREATE FUNCTION unfinished_kb_documents()
        RETURNS TABLE (document_id uuid, tenant_id uuid)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
            SELECT id, tenant_id FROM kb_documents WHERE status = 'processing' ORDER BY created_at
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION unfinished_kb_documents() FROM PUBLIC")

    _grant("GRANT SELECT, INSERT, UPDATE, DELETE ON kb_documents TO {role}")
    _grant("GRANT EXECUTE ON FUNCTION unfinished_kb_documents() TO {role}")
    _grant("GRANT INSERT, UPDATE (name, role, is_active, password_hash, password_changed_at) ON users TO {role}")


def downgrade() -> None:
    _grant("REVOKE INSERT, UPDATE (name, role, is_active, password_hash, password_changed_at) ON users FROM {role}")
    op.execute("DROP FUNCTION unfinished_kb_documents()")
    op.drop_constraint("uq_knowledge_base_document_id_position", "knowledge_base", type_="unique")
    op.drop_constraint(op.f("fk_knowledge_base_tenant_id_kb_documents"), "knowledge_base", type_="foreignkey")
    op.drop_index(op.f("ix_knowledge_base_document_id"), table_name="knowledge_base")
    op.drop_column("knowledge_base", "position")
    op.drop_column("knowledge_base", "document_id")
    op.execute("DROP POLICY tenant_isolation ON kb_documents")
    op.drop_index(op.f("ix_kb_documents_tenant_id"), table_name="kb_documents")
    op.drop_table("kb_documents")

"""public contact form: tenants.contact_form_enabled, tickets.channel (Phase 10b)

Revision ID: b5e1c7a4d902
Revises: a8d3f6b2c9e4
Create Date: 2026-09-12 18:00:00.000000

A business's customers can send a ticket through a public page, /contact/<slug>, with
no account. contact_form_enabled switches it on per tenant; tickets.channel records
where a ticket came from. contact_form_tenant(slug) is the one lookup the public page
needs before any tenant is in scope: it returns only the id and display name, and only
when the form is on.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.core.config import settings

revision: str = "b5e1c7a4d902"
down_revision: str | Sequence[str] | None = "a8d3f6b2c9e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _grant(sql: str) -> None:
    role = settings.app_db_role
    op.execute(f"DO $$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname = '{role}') THEN {sql.format(role=role)}; END IF; END $$")


def upgrade() -> None:
    op.add_column("tenants", sa.Column("contact_form_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("tickets", sa.Column("channel", sa.Text(), server_default="staff", nullable=False))
    op.create_check_constraint(op.f("ck_tickets_channel_valid"), "tickets", "channel IN ('staff', 'contact_form')")
    op.execute(
        """
        CREATE FUNCTION contact_form_tenant(p_slug text)
        RETURNS TABLE (tenant_id uuid, name text)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
            SELECT id, name FROM tenants WHERE slug = lower(p_slug) AND contact_form_enabled
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION contact_form_tenant(text) FROM PUBLIC")
    _grant("GRANT EXECUTE ON FUNCTION contact_form_tenant(text) TO {role}")
    _grant("GRANT UPDATE (contact_form_enabled) ON tenants TO {role}")


def downgrade() -> None:
    _grant("REVOKE UPDATE (contact_form_enabled) ON tenants FROM {role}")
    op.execute("DROP FUNCTION contact_form_tenant(text)")
    op.drop_constraint(op.f("ck_tickets_channel_valid"), "tickets", type_="check")
    op.drop_column("tickets", "channel")
    op.drop_column("tenants", "contact_form_enabled")

"""unfinished_agent_runs(): tickets whose agent run never finished (Phase 8)

Revision ID: f2c5a8d1e7b3
Revises: e4b8d2a9c6f1
Create Date: 2026-09-12 12:00:00.000000

Background runs live in the API process, so a restart mid-run leaves tickets `new` or
`in_progress` forever. At startup the API finds them with this function and runs them
again. It crosses tenants (the API role otherwise can't), so it returns only ticket and
tenant ids.
"""
from collections.abc import Sequence

from alembic import op
from app.core.config import settings

revision: str = "f2c5a8d1e7b3"
down_revision: str | Sequence[str] | None = "e4b8d2a9c6f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION unfinished_agent_runs()
        RETURNS TABLE (ticket_id uuid, tenant_id uuid)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
            SELECT id, tenant_id FROM tickets WHERE status IN ('new', 'in_progress') ORDER BY created_at
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION unfinished_agent_runs() FROM PUBLIC")
    role = settings.app_db_role
    op.execute(
        f"DO $$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname = '{role}') THEN "
        f"GRANT EXECUTE ON FUNCTION unfinished_agent_runs() TO {role}; END IF; END $$"
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION unfinished_agent_runs()")

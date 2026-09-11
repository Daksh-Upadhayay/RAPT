"""multi-tenancy: tenants, users, tenant_id everywhere, row-level security (Phase 7)

Revision ID: e4b8d2a9c6f1
Revises: c7e2b9d4f1a8
Create Date: 2026-09-12 09:00:00.000000

- tenants + users (invite-only accounts; one tenant per user)
- tenant_id NOT NULL on every business table, backfilled into a "dev" tenant. Its
  default is the transaction's tenant (app.tenant_id), set by app.core.tenancy.
- same-tenant foreign keys: (tenant_id, x_id) -> parent(tenant_id, id), so no row can
  reference another tenant's row
- row-level security: the API's restricted role (settings.app_db_role) only sees rows
  whose tenant_id equals app.tenant_id. The table owner (migrations, operator CLI,
  scripts) is not bound by it; RLS is deliberately not FORCEd.
- auth_find_user(email): the one cross-tenant lookup (login), as SECURITY DEFINER
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.core.config import settings

revision: str = "e4b8d2a9c6f1"
down_revision: str | Sequence[str] | None = "c7e2b9d4f1a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CURRENT_TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"
# Business tables, parents before children
TENANT_TABLES = ["customers", "orders", "tickets", "agent_logs", "draft_responses", "model_predictions", "knowledge_base"]
# (table, column, parent) for the same-tenant foreign keys, and the old single-column FK they replace
REFERENCES = [
    ("orders", "customer_id", "customers", "fk_orders_customer_id_customers"),
    ("tickets", "customer_id", "customers", "fk_tickets_customer_id_customers"),
    ("tickets", "order_id", "orders", "fk_tickets_order_id_orders"),
    ("agent_logs", "ticket_id", "tickets", "fk_agent_logs_ticket_id_tickets"),
    ("draft_responses", "ticket_id", "tickets", "fk_draft_responses_ticket_id_tickets"),
    ("model_predictions", "ticket_id", "tickets", "fk_model_predictions_ticket_id_tickets"),
]
PARENTS = ["customers", "orders", "tickets"]


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "tenants",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenants")),
        sa.UniqueConstraint("slug", name=op.f("uq_tenants_slug")),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), server_default=sa.text(CURRENT_TENANT), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("role IN ('admin', 'reviewer')", name=op.f("ck_users_role_valid")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_users_tenant_id_tenants")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_index(op.f("ix_users_tenant_id"), "users", ["tenant_id"])

    # Existing rows (seed data, dev tickets) move into a tenant that is never deployed
    dev_id = op.get_bind().execute(
        sa.text("INSERT INTO tenants (name, slug) VALUES ('Development', 'dev') RETURNING id")
    ).scalar_one()

    for table in TENANT_TABLES:
        op.add_column(table, sa.Column("tenant_id", sa.UUID(), nullable=True))
        op.execute(sa.text(f"UPDATE {table} SET tenant_id = :dev").bindparams(dev=dev_id))
        op.alter_column(table, "tenant_id", nullable=False, server_default=sa.text(CURRENT_TENANT))
        op.create_foreign_key(op.f(f"fk_{table}_tenant_id_tenants"), table, "tenants", ["tenant_id"], ["id"])
        op.create_index(op.f(f"ix_{table}_tenant_id"), table, ["tenant_id"])

    for table in PARENTS:
        op.create_unique_constraint(f"uq_{table}_tenant_id_id", table, ["tenant_id", "id"])
    for table, column, parent, old_fk in REFERENCES:
        op.drop_constraint(old_fk, table, type_="foreignkey")
        op.create_foreign_key(
            op.f(f"fk_{table}_tenant_id_{parent}"), table, parent, ["tenant_id", column], ["tenant_id", "id"]
        )

    op.drop_constraint("uq_customers_email", "customers", type_="unique")
    op.create_unique_constraint("uq_customers_tenant_id_email", "customers", ["tenant_id", "email"])
    op.drop_index("ix_tickets_status", table_name="tickets")
    op.create_index("ix_tickets_tenant_id_status", "tickets", ["tenant_id", "status"])

    # Row-level security for the API role
    for table in [*TENANT_TABLES, "users"]:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING (tenant_id = {CURRENT_TENANT}) WITH CHECK (tenant_id = {CURRENT_TENANT})"
        )
    op.execute("ALTER TABLE tenants ENABLE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY tenant_isolation ON tenants USING (id = {CURRENT_TENANT})")

    # Login must find a user by email before any tenant is known: one narrow function,
    # running as the owner, returning only what login needs
    op.execute(
        """
        CREATE FUNCTION auth_find_user(p_email text)
        RETURNS TABLE (id uuid, tenant_id uuid, password_hash text, role text, is_active boolean)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
            SELECT id, tenant_id, password_hash, role, is_active FROM users WHERE email = lower(p_email)
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION auth_find_user(text) FROM PUBLIC")

    role = settings.app_db_role
    tables = ", ".join(TENANT_TABLES)
    op.execute(
        f"""
        DO $$ BEGIN
          IF EXISTS (SELECT FROM pg_roles WHERE rolname = '{role}') THEN
            GRANT USAGE ON SCHEMA public TO {role};
            GRANT SELECT, INSERT, UPDATE, DELETE ON {tables} TO {role};
            GRANT SELECT ON tenants TO {role};
            GRANT SELECT, UPDATE (last_login_at) ON users TO {role};
            GRANT EXECUTE ON FUNCTION auth_find_user(text) TO {role};
          ELSE
            RAISE NOTICE 'role {role} does not exist: create it, then rerun the grants (see backend/README.md)';
          END IF;
        END $$
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    role = settings.app_db_role
    op.execute(
        f"""
        DO $$ BEGIN
          IF EXISTS (SELECT FROM pg_roles WHERE rolname = '{role}') THEN
            REVOKE ALL ON {", ".join(TENANT_TABLES)}, tenants, users FROM {role};
          END IF;
        END $$
        """
    )
    op.execute("DROP FUNCTION auth_find_user(text)")
    for table in [*TENANT_TABLES, "users", "tenants"]:
        op.execute(f"DROP POLICY tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_tickets_tenant_id_status", table_name="tickets")
    op.create_index("ix_tickets_status", "tickets", ["status"])
    op.drop_constraint("uq_customers_tenant_id_email", "customers", type_="unique")
    op.create_unique_constraint("uq_customers_email", "customers", ["email"])

    for table, column, parent, old_fk in reversed(REFERENCES):
        op.drop_constraint(op.f(f"fk_{table}_tenant_id_{parent}"), table, type_="foreignkey")
        op.create_foreign_key(old_fk, table, parent, [column], ["id"])
    for table in reversed(PARENTS):
        op.drop_constraint(f"uq_{table}_tenant_id_id", table, type_="unique")
    for table in reversed(TENANT_TABLES):
        op.drop_index(op.f(f"ix_{table}_tenant_id"), table_name=table)
        op.drop_constraint(op.f(f"fk_{table}_tenant_id_tenants"), table, type_="foreignkey")
        op.drop_column(table, "tenant_id")

    op.drop_index(op.f("ix_users_tenant_id"), table_name="users")
    op.drop_table("users")
    op.drop_table("tenants")

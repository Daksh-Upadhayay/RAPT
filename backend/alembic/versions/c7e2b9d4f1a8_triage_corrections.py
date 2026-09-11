"""triage corrections on tickets (Phase 6 feedback loop)

Revision ID: c7e2b9d4f1a8
Revises: a3f9c1d27e45
Create Date: 2026-09-11 20:00:00.000000

A reviewer who disagrees with the Triage Agent records the right category and/or
urgency. The AI's own labels stay in category/urgency, so model and human can be
compared; scripts/export_feedback.py turns corrections into training rows.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7e2b9d4f1a8"
down_revision: Union[str, Sequence[str], None] = "a3f9c1d27e45"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CATEGORIES = "'order_status', 'refund_request', 'damaged_item', 'delivery_delay', 'product_question', 'cancellation'"
URGENCIES = "'low', 'medium', 'high'"


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("tickets", sa.Column("corrected_category", sa.Text(), nullable=True))
    op.add_column("tickets", sa.Column("corrected_urgency", sa.Text(), nullable=True))
    op.add_column("tickets", sa.Column("corrected_by", sa.Text(), nullable=True))
    op.add_column("tickets", sa.Column("corrected_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        op.f("ck_tickets_corrected_category_valid"), "tickets", f"corrected_category IN ({CATEGORIES})"
    )
    op.create_check_constraint(op.f("ck_tickets_corrected_urgency_valid"), "tickets", f"corrected_urgency IN ({URGENCIES})")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(op.f("ck_tickets_corrected_urgency_valid"), "tickets", type_="check")
    op.drop_constraint(op.f("ck_tickets_corrected_category_valid"), "tickets", type_="check")
    op.drop_column("tickets", "corrected_at")
    op.drop_column("tickets", "corrected_by")
    op.drop_column("tickets", "corrected_urgency")
    op.drop_column("tickets", "corrected_category")

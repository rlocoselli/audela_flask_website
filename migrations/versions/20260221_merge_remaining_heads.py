"""merge remaining alembic heads

Revision ID: 20260221_merge_remaining_heads
Revises: 20260221_add_finance_accounting_periods, 7811fe58d1ac
Create Date: 2026-02-21
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260221_merge_remaining_heads"
down_revision = ("20260221_add_finance_accounting_periods", "7811fe58d1ac")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass

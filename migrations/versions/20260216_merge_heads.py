"""merge heads (reports branch + files branch)

Revision ID: 20260216_merge_heads
Revises: 20260213_add_file_assets_and_folders, 880c1112df41
Create Date: 2026-02-16

This merge resolves the dual head situation introduced when the "create_user_table"
revision was branched from 20260208_add_reports.
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260216_merge_heads"
down_revision = ("20260213_add_file_assets_and_folders", "880c1112df41")
branch_labels = None
depends_on = None


def upgrade():
    # merge revision – no schema changes
    pass


def downgrade():
    # merge revision – no schema changes
    pass

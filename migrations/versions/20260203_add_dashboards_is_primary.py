"""add dashboards.is_primary

Revision ID: 20260203_add_dashboards_is_primary
Revises: 51e678d6b231
Create Date: 2026-02-03 20:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260203_add_dashboards_is_primary'
down_revision = '51e678d6b231'
branch_labels = None
depends_on = None


def upgrade():
    # Add is_primary flag to dashboards with default false
    op.add_column('dashboards', sa.Column('is_primary', sa.Boolean(), nullable=False, server_default=sa.text('0')))
    # remove server_default for cleanliness (optional)
    try:
        op.alter_column('dashboards', 'is_primary', server_default=None)
    except Exception:
        pass


def downgrade():
    op.drop_column('dashboards', 'is_primary')

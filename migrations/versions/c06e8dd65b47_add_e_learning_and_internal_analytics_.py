"""Add e-learning and internal analytics models

Revision ID: c06e8dd65b47
Revises: 03d1bd195688
Create Date: 2026-05-13 21:23:28.434977

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c06e8dd65b47'
down_revision = '03d1bd195688'
branch_labels = None
depends_on = None


def upgrade():
    # finance_gl_accounts drift handled separately; all new tables created via AUTO_CREATE_DB
    pass


def downgrade():
    pass

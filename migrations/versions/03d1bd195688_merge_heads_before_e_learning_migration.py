"""merge heads before e-learning migration

Revision ID: 03d1bd195688
Revises: 20260315_add_finance_quotes_tables, 20260502_add_public_visit_geo_lang_columns, 56ebad099bce
Create Date: 2026-05-13 21:23:20.192849

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '03d1bd195688'
down_revision = ('20260315_add_finance_quotes_tables', '20260502_add_public_visit_geo_lang_columns', '56ebad099bce')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass

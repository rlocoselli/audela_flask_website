"""ensure data_sources has base_url/method columns

Revision ID: 20260307_ensure_data_sources_columns
Revises: 20260307_add_credit_memo_template_creator
Create Date: 2026-03-07
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260307_ensure_data_sources_columns"
down_revision = "20260307_add_credit_memo_template_creator"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def _column_names(bind, table_name: str) -> set[str]:
    return {c["name"] for c in sa.inspect(bind).get_columns(table_name)}


def upgrade():
    bind = op.get_bind()
    if not _table_exists(bind, "data_sources"):
        return

    cols = _column_names(bind, "data_sources")
    with op.batch_alter_table("data_sources", schema=None) as batch_op:
        if "base_url" not in cols:
            batch_op.add_column(sa.Column("base_url", sa.String(length=300), nullable=True))
        if "method" not in cols:
            batch_op.add_column(sa.Column("method", sa.String(length=300), nullable=True))


def downgrade():
    bind = op.get_bind()
    if not _table_exists(bind, "data_sources"):
        return

    cols = _column_names(bind, "data_sources")
    with op.batch_alter_table("data_sources", schema=None) as batch_op:
        if "method" in cols:
            batch_op.drop_column("method")
        if "base_url" in cols:
            batch_op.drop_column("base_url")

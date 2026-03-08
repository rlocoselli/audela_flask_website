"""add approval_date to core credit entities

Revision ID: 20260308_add_credit_approval_dates
Revises: 20260307_ensure_data_sources_columns
Create Date: 2026-03-08
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260308_add_credit_approval_dates"
down_revision = "20260307_ensure_data_sources_columns"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def _column_names(bind, table_name: str) -> set[str]:
    return {c["name"] for c in sa.inspect(bind).get_columns(table_name)}


def _index_names(bind, table_name: str) -> set[str]:
    return {i["name"] for i in sa.inspect(bind).get_indexes(table_name)}


def _add_approval_date(bind, table_name: str, index_name: str) -> None:
    if not _table_exists(bind, table_name):
        return

    cols = _column_names(bind, table_name)
    idx = _index_names(bind, table_name)
    with op.batch_alter_table(table_name, schema=None) as batch_op:
        if "approval_date" not in cols:
            batch_op.add_column(sa.Column("approval_date", sa.DateTime(), nullable=True))
        if index_name not in idx:
            batch_op.create_index(index_name, ["approval_date"], unique=False)


def _drop_approval_date(bind, table_name: str, index_name: str) -> None:
    if not _table_exists(bind, table_name):
        return

    cols = _column_names(bind, table_name)
    idx = _index_names(bind, table_name)
    with op.batch_alter_table(table_name, schema=None) as batch_op:
        if index_name in idx:
            batch_op.drop_index(index_name)
        if "approval_date" in cols:
            batch_op.drop_column("approval_date")


def upgrade():
    bind = op.get_bind()

    _add_approval_date(bind, "credit_deals", "ix_credit_deals_approval_date")
    _add_approval_date(bind, "credit_facilities", "ix_credit_facilities_approval_date")
    _add_approval_date(bind, "credit_financial_statements", "ix_credit_financial_statements_approval_date")
    _add_approval_date(bind, "credit_memos", "ix_credit_memos_approval_date")


def downgrade():
    bind = op.get_bind()

    _drop_approval_date(bind, "credit_memos", "ix_credit_memos_approval_date")
    _drop_approval_date(bind, "credit_financial_statements", "ix_credit_financial_statements_approval_date")
    _drop_approval_date(bind, "credit_facilities", "ix_credit_facilities_approval_date")
    _drop_approval_date(bind, "credit_deals", "ix_credit_deals_approval_date")

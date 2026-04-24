"""add credit chart of accounts tables

Revision ID: 20260421_add_credit_chart_of_accounts
Revises: 20260305_add_credit_module_tables
Create Date: 2026-04-21
"""

from alembic import context, op
import sqlalchemy as sa

revision = "20260421_add_credit_chart_of_accounts"
down_revision = "20260305_add_credit_module_tables"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return table_name in insp.get_table_names()


def _create_table_if_missing(table_name: str, *columns_and_constraints) -> None:
    if not _table_exists(table_name):
        op.create_table(table_name, *columns_and_constraints)


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str], unique: bool = False) -> None:
    if not _table_exists(table_name):
        return
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing = [i["name"] for i in insp.get_indexes(table_name)]
    if index_name not in existing:
        op.create_index(index_name, table_name, columns, unique=unique)


def upgrade():
    _create_table_if_missing(
        "credit_chart_of_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sector_id", sa.Integer(), nullable=True),
        sa.Column("is_template", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sector_id"], ["credit_sectors.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    _create_index_if_missing("ix_credit_chart_of_accounts_tenant_id", "credit_chart_of_accounts", ["tenant_id"])
    _create_index_if_missing("ix_credit_chart_of_accounts_sector_id", "credit_chart_of_accounts", ["sector_id"])

    _create_table_if_missing(
        "credit_account_lines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chart_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=True),
        sa.Column("label", sa.String(length=240), nullable=False),
        sa.Column("line_type", sa.String(length=32), nullable=False, server_default="data"),
        sa.Column("formula_expr", sa.String(length=512), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("indent_level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_ratio", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("ratio_code", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["chart_id"], ["credit_chart_of_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    _create_index_if_missing("ix_credit_account_lines_chart_id", "credit_account_lines", ["chart_id"])

    _create_table_if_missing(
        "credit_spreading_line_values",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("statement_id", sa.Integer(), nullable=False),
        sa.Column("line_id", sa.Integer(), nullable=False),
        sa.Column("value", sa.Numeric(20, 4), nullable=True),
        sa.ForeignKeyConstraint(["statement_id"], ["credit_financial_statements.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["line_id"], ["credit_account_lines.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("statement_id", "line_id", name="uq_spreading_line_values_stmt_line"),
    )
    _create_index_if_missing("ix_credit_spreading_line_values_statement_id", "credit_spreading_line_values", ["statement_id"])
    _create_index_if_missing("ix_credit_spreading_line_values_line_id", "credit_spreading_line_values", ["line_id"])


def downgrade():
    if _table_exists("credit_spreading_line_values"):
        op.drop_table("credit_spreading_line_values")
    if _table_exists("credit_account_lines"):
        op.drop_table("credit_account_lines")
    if _table_exists("credit_chart_of_accounts"):
        op.drop_table("credit_chart_of_accounts")

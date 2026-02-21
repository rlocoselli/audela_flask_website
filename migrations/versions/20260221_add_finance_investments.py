"""add finance investments

Revision ID: 20260221_add_finance_investments
Revises: 20260220_add_project_workspaces
Create Date: 2026-02-21

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260221_add_finance_investments"
down_revision = "20260220_add_project_workspaces"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "finance_investments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("finance_companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False, server_default="stock_exchange"),
        sa.Column("instrument_code", sa.String(length=64), nullable=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("finance_accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("currency_code", sa.String(length=8), sa.ForeignKey("finance_currencies.code"), nullable=True),
        sa.Column("invested_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("current_value", sa.Numeric(18, 2), nullable=True),
        sa.Column("started_on", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="active"),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_index(op.f("ix_finance_investments_tenant_id"), "finance_investments", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_finance_investments_company_id"), "finance_investments", ["company_id"], unique=False)
    op.create_index(op.f("ix_finance_investments_account_id"), "finance_investments", ["account_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_finance_investments_account_id"), table_name="finance_investments")
    op.drop_index(op.f("ix_finance_investments_company_id"), table_name="finance_investments")
    op.drop_index(op.f("ix_finance_investments_tenant_id"), table_name="finance_investments")
    op.drop_table("finance_investments")

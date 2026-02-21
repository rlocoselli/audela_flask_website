"""add finance accounting periods

Revision ID: 20260221_add_finance_accounting_periods
Revises: 20260221_add_finance_investments
Create Date: 2026-02-21
"""

from alembic import op
import sqlalchemy as sa


revision = "20260221_add_finance_accounting_periods"
down_revision = "20260221_add_finance_investments"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "finance_accounting_periods",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("is_closed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("closed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("reopened_at", sa.DateTime(), nullable=True),
        sa.Column("reopened_by_user_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["finance_companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "company_id", "period_start", "period_end", name="uq_fin_acc_period_scope"),
    )
    op.create_index("ix_fin_acc_period_scope", "finance_accounting_periods", ["tenant_id", "company_id", "period_start", "period_end"])
    op.create_index(op.f("ix_finance_accounting_periods_tenant_id"), "finance_accounting_periods", ["tenant_id"])
    op.create_index(op.f("ix_finance_accounting_periods_company_id"), "finance_accounting_periods", ["company_id"])


def downgrade():
    op.drop_index(op.f("ix_finance_accounting_periods_company_id"), table_name="finance_accounting_periods")
    op.drop_index(op.f("ix_finance_accounting_periods_tenant_id"), table_name="finance_accounting_periods")
    op.drop_index("ix_fin_acc_period_scope", table_name="finance_accounting_periods")
    op.drop_table("finance_accounting_periods")

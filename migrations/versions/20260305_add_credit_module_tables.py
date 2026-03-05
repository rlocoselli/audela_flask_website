"""add credit module tables

Revision ID: 20260305_add_credit_module_tables
Revises: 20260221_merge_remaining_heads
Create Date: 2026-03-05
"""

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260305_add_credit_module_tables"
down_revision = "20260221_merge_remaining_heads"
branch_labels = None
depends_on = None


def upgrade():
    dialect_name = context.get_context().dialect.name
    use_sqlite_safe_types = dialect_name == "sqlite"
    json_type = sa.JSON() if use_sqlite_safe_types else postgresql.JSONB(astext_type=sa.Text())

    op.create_table(
        "credit_borrowers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("sector", sa.String(length=120), nullable=True),
        sa.Column("country", sa.String(length=80), nullable=True),
        sa.Column("internal_rating", sa.String(length=16), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_credit_borrowers_tenant_id", "credit_borrowers", ["tenant_id"])
    op.create_index("ix_credit_borrowers_name", "credit_borrowers", ["name"])

    op.create_table(
        "credit_deals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("borrower_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("purpose", sa.String(length=255), nullable=True),
        sa.Column("requested_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="EUR"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="in_review"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["borrower_id"], ["credit_borrowers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_credit_deals_tenant_id", "credit_deals", ["tenant_id"])
    op.create_index("ix_credit_deals_borrower_id", "credit_deals", ["borrower_id"])
    op.create_index("ix_credit_deals_code", "credit_deals", ["code"])
    op.create_index("ix_credit_deals_status", "credit_deals", ["status"])

    op.create_table(
        "credit_facilities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("deal_id", sa.Integer(), nullable=False),
        sa.Column("facility_type", sa.String(length=64), nullable=False, server_default="term_loan"),
        sa.Column("approved_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("tenor_months", sa.Integer(), nullable=True),
        sa.Column("interest_rate", sa.Numeric(9, 4), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["deal_id"], ["credit_deals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_credit_facilities_tenant_id", "credit_facilities", ["tenant_id"])
    op.create_index("ix_credit_facilities_deal_id", "credit_facilities", ["deal_id"])
    op.create_index("ix_credit_facilities_status", "credit_facilities", ["status"])

    op.create_table(
        "credit_collaterals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("borrower_id", sa.Integer(), nullable=False),
        sa.Column("deal_id", sa.Integer(), nullable=True),
        sa.Column("collateral_type", sa.String(length=80), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("market_value", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("haircut_pct", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["borrower_id"], ["credit_borrowers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["deal_id"], ["credit_deals.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_credit_collaterals_tenant_id", "credit_collaterals", ["tenant_id"])
    op.create_index("ix_credit_collaterals_borrower_id", "credit_collaterals", ["borrower_id"])
    op.create_index("ix_credit_collaterals_deal_id", "credit_collaterals", ["deal_id"])

    op.create_table(
        "credit_guarantors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("borrower_id", sa.Integer(), nullable=False),
        sa.Column("deal_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("guarantee_type", sa.String(length=80), nullable=False, server_default="personal"),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["borrower_id"], ["credit_borrowers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["deal_id"], ["credit_deals.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_credit_guarantors_tenant_id", "credit_guarantors", ["tenant_id"])
    op.create_index("ix_credit_guarantors_borrower_id", "credit_guarantors", ["borrower_id"])
    op.create_index("ix_credit_guarantors_deal_id", "credit_guarantors", ["deal_id"])

    op.create_table(
        "credit_financial_statements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("borrower_id", sa.Integer(), nullable=False),
        sa.Column("period_label", sa.String(length=32), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("revenue", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("ebitda", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("total_debt", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("cash", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("net_income", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("spreading_status", sa.String(length=32), nullable=False, server_default="in_progress"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["borrower_id"], ["credit_borrowers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_credit_financial_statements_tenant_id", "credit_financial_statements", ["tenant_id"])
    op.create_index("ix_credit_financial_statements_borrower_id", "credit_financial_statements", ["borrower_id"])

    op.create_table(
        "credit_ratio_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("borrower_id", sa.Integer(), nullable=False),
        sa.Column("statement_id", sa.Integer(), nullable=True),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("dscr", sa.Numeric(9, 4), nullable=True),
        sa.Column("leverage", sa.Numeric(9, 4), nullable=True),
        sa.Column("liquidity", sa.Numeric(9, 4), nullable=True),
        sa.Column("risk_grade", sa.String(length=16), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["borrower_id"], ["credit_borrowers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["statement_id"], ["credit_financial_statements.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_credit_ratio_snapshots_tenant_id", "credit_ratio_snapshots", ["tenant_id"])
    op.create_index("ix_credit_ratio_snapshots_borrower_id", "credit_ratio_snapshots", ["borrower_id"])
    op.create_index("ix_credit_ratio_snapshots_statement_id", "credit_ratio_snapshots", ["statement_id"])
    op.create_index("ix_credit_ratio_snapshots_snapshot_date", "credit_ratio_snapshots", ["snapshot_date"])

    op.create_table(
        "credit_memos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("deal_id", sa.Integer(), nullable=True),
        sa.Column("borrower_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("recommendation", sa.String(length=64), nullable=False, server_default="review"),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("ai_generated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("ai_prompt", sa.Text(), nullable=True),
        sa.Column("ai_response_json", json_type, nullable=True),
        sa.Column("prepared_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["borrower_id"], ["credit_borrowers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["deal_id"], ["credit_deals.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["prepared_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_credit_memos_tenant_id", "credit_memos", ["tenant_id"])
    op.create_index("ix_credit_memos_deal_id", "credit_memos", ["deal_id"])
    op.create_index("ix_credit_memos_borrower_id", "credit_memos", ["borrower_id"])
    op.create_index("ix_credit_memos_prepared_by_user_id", "credit_memos", ["prepared_by_user_id"])

    op.create_table(
        "credit_approvals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("memo_id", sa.Integer(), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=False, server_default="analyst_review"),
        sa.Column("decision", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["memo_id"], ["credit_memos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_credit_approvals_tenant_id", "credit_approvals", ["tenant_id"])
    op.create_index("ix_credit_approvals_memo_id", "credit_approvals", ["memo_id"])

    op.create_table(
        "credit_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("borrower_id", sa.Integer(), nullable=True),
        sa.Column("deal_id", sa.Integer(), nullable=True),
        sa.Column("memo_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("doc_type", sa.String(length=64), nullable=False, server_default="supporting"),
        sa.Column("file_path", sa.String(length=500), nullable=True),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["borrower_id"], ["credit_borrowers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["deal_id"], ["credit_deals.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["memo_id"], ["credit_memos.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_credit_documents_tenant_id", "credit_documents", ["tenant_id"])
    op.create_index("ix_credit_documents_borrower_id", "credit_documents", ["borrower_id"])
    op.create_index("ix_credit_documents_deal_id", "credit_documents", ["deal_id"])
    op.create_index("ix_credit_documents_memo_id", "credit_documents", ["memo_id"])


def downgrade():
    op.drop_index("ix_credit_documents_memo_id", table_name="credit_documents")
    op.drop_index("ix_credit_documents_deal_id", table_name="credit_documents")
    op.drop_index("ix_credit_documents_borrower_id", table_name="credit_documents")
    op.drop_index("ix_credit_documents_tenant_id", table_name="credit_documents")
    op.drop_table("credit_documents")

    op.drop_index("ix_credit_approvals_memo_id", table_name="credit_approvals")
    op.drop_index("ix_credit_approvals_tenant_id", table_name="credit_approvals")
    op.drop_table("credit_approvals")

    op.drop_index("ix_credit_memos_prepared_by_user_id", table_name="credit_memos")
    op.drop_index("ix_credit_memos_borrower_id", table_name="credit_memos")
    op.drop_index("ix_credit_memos_deal_id", table_name="credit_memos")
    op.drop_index("ix_credit_memos_tenant_id", table_name="credit_memos")
    op.drop_table("credit_memos")

    op.drop_index("ix_credit_ratio_snapshots_snapshot_date", table_name="credit_ratio_snapshots")
    op.drop_index("ix_credit_ratio_snapshots_statement_id", table_name="credit_ratio_snapshots")
    op.drop_index("ix_credit_ratio_snapshots_borrower_id", table_name="credit_ratio_snapshots")
    op.drop_index("ix_credit_ratio_snapshots_tenant_id", table_name="credit_ratio_snapshots")
    op.drop_table("credit_ratio_snapshots")

    op.drop_index("ix_credit_financial_statements_borrower_id", table_name="credit_financial_statements")
    op.drop_index("ix_credit_financial_statements_tenant_id", table_name="credit_financial_statements")
    op.drop_table("credit_financial_statements")

    op.drop_index("ix_credit_guarantors_deal_id", table_name="credit_guarantors")
    op.drop_index("ix_credit_guarantors_borrower_id", table_name="credit_guarantors")
    op.drop_index("ix_credit_guarantors_tenant_id", table_name="credit_guarantors")
    op.drop_table("credit_guarantors")

    op.drop_index("ix_credit_collaterals_deal_id", table_name="credit_collaterals")
    op.drop_index("ix_credit_collaterals_borrower_id", table_name="credit_collaterals")
    op.drop_index("ix_credit_collaterals_tenant_id", table_name="credit_collaterals")
    op.drop_table("credit_collaterals")

    op.drop_index("ix_credit_facilities_status", table_name="credit_facilities")
    op.drop_index("ix_credit_facilities_deal_id", table_name="credit_facilities")
    op.drop_index("ix_credit_facilities_tenant_id", table_name="credit_facilities")
    op.drop_table("credit_facilities")

    op.drop_index("ix_credit_deals_status", table_name="credit_deals")
    op.drop_index("ix_credit_deals_code", table_name="credit_deals")
    op.drop_index("ix_credit_deals_borrower_id", table_name="credit_deals")
    op.drop_index("ix_credit_deals_tenant_id", table_name="credit_deals")
    op.drop_table("credit_deals")

    op.drop_index("ix_credit_borrowers_name", table_name="credit_borrowers")
    op.drop_index("ix_credit_borrowers_tenant_id", table_name="credit_borrowers")
    op.drop_table("credit_borrowers")

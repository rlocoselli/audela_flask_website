"""add finance tables

Revision ID: 20260215_add_finance_tables
Revises: 20260213_add_file_assets_and_folders
Create Date: 2026-02-15

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260215_add_finance_tables"
down_revision = "20260213_add_file_assets_and_folders"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "finance_companies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("base_currency", sa.String(length=8), nullable=False, server_default="EUR"),
        sa.Column("country", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_fin_company_slug_per_tenant"),
    )
    op.create_index(op.f("ix_finance_companies_tenant_id"), "finance_companies", ["tenant_id"], unique=False)

    op.create_table(
        "finance_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("finance_companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("account_type", sa.String(length=32), nullable=False, server_default="bank"),
        sa.Column("side", sa.String(length=16), nullable=False, server_default="asset"),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="EUR"),
        sa.Column("balance", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("limit_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("is_interest_bearing", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("annual_rate", sa.Numeric(9, 6), nullable=True),
        sa.Column("rate_type", sa.String(length=16), nullable=False, server_default="fixed"),
        sa.Column("repricing_date", sa.Date(), nullable=True),
        sa.Column("maturity_date", sa.Date(), nullable=True),
        sa.Column("counterparty", sa.String(length=160), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(op.f("ix_finance_accounts_tenant_id"), "finance_accounts", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_finance_accounts_company_id"), "finance_accounts", ["company_id"], unique=False)

    op.create_table(
        "finance_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("finance_companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("finance_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("txn_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("counterparty", sa.String(length=160), nullable=True),
        sa.Column("reference", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(op.f("ix_finance_transactions_tenant_id"), "finance_transactions", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_finance_transactions_company_id"), "finance_transactions", ["company_id"], unique=False)
    op.create_index(op.f("ix_finance_transactions_account_id"), "finance_transactions", ["account_id"], unique=False)
    op.create_index(
        "ix_fin_txn_tenant_company_date",
        "finance_transactions",
        ["tenant_id", "company_id", "txn_date"],
        unique=False,
    )

    op.create_table(
        "finance_report_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("finance_companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("report_type", sa.String(length=32), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(op.f("ix_finance_report_snapshots_tenant_id"), "finance_report_snapshots", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_finance_report_snapshots_company_id"), "finance_report_snapshots", ["company_id"], unique=False)
    op.create_index(
        "ix_fin_snap_tenant_company_type_date",
        "finance_report_snapshots",
        ["tenant_id", "company_id", "report_type", "as_of"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_fin_snap_tenant_company_type_date", table_name="finance_report_snapshots")
    op.drop_index(op.f("ix_finance_report_snapshots_company_id"), table_name="finance_report_snapshots")
    op.drop_index(op.f("ix_finance_report_snapshots_tenant_id"), table_name="finance_report_snapshots")
    op.drop_table("finance_report_snapshots")

    op.drop_index("ix_fin_txn_tenant_company_date", table_name="finance_transactions")
    op.drop_index(op.f("ix_finance_transactions_account_id"), table_name="finance_transactions")
    op.drop_index(op.f("ix_finance_transactions_company_id"), table_name="finance_transactions")
    op.drop_index(op.f("ix_finance_transactions_tenant_id"), table_name="finance_transactions")
    op.drop_table("finance_transactions")

    op.drop_index(op.f("ix_finance_accounts_company_id"), table_name="finance_accounts")
    op.drop_index(op.f("ix_finance_accounts_tenant_id"), table_name="finance_accounts")
    op.drop_table("finance_accounts")

    op.drop_index(op.f("ix_finance_companies_tenant_id"), table_name="finance_companies")
    op.drop_table("finance_companies")

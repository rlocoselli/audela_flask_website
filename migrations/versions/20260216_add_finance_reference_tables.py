"""add finance reference tables

Revision ID: 20260216_add_finance_reference_tables
Revises: 20260215_add_finance_tables
Create Date: 2026-02-16

"""

from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = "20260216_add_finance_reference_tables"
down_revision = "20260215_add_finance_tables"
branch_labels = None
depends_on = None


def upgrade():
    # Reference: currencies
    op.create_table(
        "finance_currencies",
        sa.Column("code", sa.String(length=8), primary_key=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("symbol", sa.String(length=8), nullable=True),
        sa.Column("decimals", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # Seed a small set of common currencies
    op.bulk_insert(
        sa.table(
            "finance_currencies",
            sa.column("code", sa.String),
            sa.column("name", sa.String),
            sa.column("symbol", sa.String),
            sa.column("decimals", sa.Integer),
            sa.column("created_at", sa.DateTime),
            sa.column("updated_at", sa.DateTime),
        ),
        [
            {"code": "EUR", "name": "Euro", "symbol": "€", "decimals": 2, "created_at": datetime.utcnow(), "updated_at": datetime.utcnow()},
            {"code": "USD", "name": "US Dollar", "symbol": "$", "decimals": 2, "created_at": datetime.utcnow(), "updated_at": datetime.utcnow()},
            {"code": "GBP", "name": "Pound Sterling", "symbol": "£", "decimals": 2, "created_at": datetime.utcnow(), "updated_at": datetime.utcnow()},
            {"code": "BRL", "name": "Brazilian Real", "symbol": "R$", "decimals": 2, "created_at": datetime.utcnow(), "updated_at": datetime.utcnow()},
            {"code": "CHF", "name": "Swiss Franc", "symbol": "CHF", "decimals": 2, "created_at": datetime.utcnow(), "updated_at": datetime.utcnow()},
            {"code": "JPY", "name": "Japanese Yen", "symbol": "¥", "decimals": 0, "created_at": datetime.utcnow(), "updated_at": datetime.utcnow()},
        ],
    )

    # Reference: counterparties
    op.create_table(
        "finance_counterparties",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("finance_companies.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False, server_default="other"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "company_id", "name", name="uq_fin_counterparty_per_company"),
    )
    op.create_index(op.f("ix_finance_counterparties_tenant_id"), "finance_counterparties", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_finance_counterparties_company_id"), "finance_counterparties", ["company_id"], unique=False)

    # Statement import audit
    op.create_table(
        "finance_statement_imports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("finance_companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("finance_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False, server_default="local"),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("imported_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(op.f("ix_finance_statement_imports_tenant_id"), "finance_statement_imports", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_finance_statement_imports_company_id"), "finance_statement_imports", ["company_id"], unique=False)
    op.create_index(op.f("ix_finance_statement_imports_account_id"), "finance_statement_imports", ["account_id"], unique=False)

    # Add FKs / columns to existing finance tables (batch mode for SQLite compatibility)
    with op.batch_alter_table("finance_companies") as batch:
        batch.create_foreign_key(
            "fk_fin_companies_base_currency",
            "finance_currencies",
            ["base_currency"],
            ["code"],
        )

    with op.batch_alter_table("finance_accounts") as batch:
        batch.add_column(sa.Column("counterparty_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_fin_accounts_currency",
            "finance_currencies",
            ["currency"],
            ["code"],
        )
        batch.create_foreign_key(
            "fk_fin_accounts_counterparty",
            "finance_counterparties",
            ["counterparty_id"],
            ["id"],
            ondelete="SET NULL",
        )

    op.create_index(op.f("ix_finance_accounts_counterparty_id"), "finance_accounts", ["counterparty_id"], unique=False)

    with op.batch_alter_table("finance_transactions") as batch:
        batch.add_column(sa.Column("counterparty_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_fin_txns_counterparty",
            "finance_counterparties",
            ["counterparty_id"],
            ["id"],
            ondelete="SET NULL",
        )

    op.create_index(op.f("ix_finance_transactions_counterparty_id"), "finance_transactions", ["counterparty_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_finance_transactions_counterparty_id"), table_name="finance_transactions")
    with op.batch_alter_table("finance_transactions") as batch:
        batch.drop_constraint("fk_fin_txns_counterparty", type_="foreignkey")
        batch.drop_column("counterparty_id")

    op.drop_index(op.f("ix_finance_accounts_counterparty_id"), table_name="finance_accounts")
    with op.batch_alter_table("finance_accounts") as batch:
        batch.drop_constraint("fk_fin_accounts_counterparty", type_="foreignkey")
        batch.drop_constraint("fk_fin_accounts_currency", type_="foreignkey")
        batch.drop_column("counterparty_id")

    with op.batch_alter_table("finance_companies") as batch:
        batch.drop_constraint("fk_fin_companies_base_currency", type_="foreignkey")

    op.drop_table("finance_statement_imports")
    op.drop_table("finance_counterparties")
    op.drop_table("finance_currencies")

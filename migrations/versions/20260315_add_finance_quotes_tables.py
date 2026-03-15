"""add finance quotes tables

Revision ID: 20260315_add_finance_quotes_tables
Revises: 20260313_add_finance_brazil_tax_fields
Create Date: 2026-03-15
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260315_add_finance_quotes_tables"
down_revision = "20260313_add_finance_brazil_tax_fields"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def _index_exists(bind, table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(ix.get("name") == index_name for ix in inspector.get_indexes(table_name))


def upgrade():
    bind = op.get_bind()

    if not _table_exists(bind, "finance_quotes"):
        op.create_table(
            "finance_quotes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("finance_companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("quote_number", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
            sa.Column("issue_date", sa.Date(), nullable=False),
            sa.Column("valid_until", sa.Date(), nullable=True),
            sa.Column("currency", sa.String(length=8), sa.ForeignKey("finance_currencies.code"), nullable=False, server_default="EUR"),
            sa.Column("counterparty_id", sa.Integer(), sa.ForeignKey("finance_counterparties.id", ondelete="SET NULL"), nullable=True),
            sa.Column("fiscal_country", sa.String(length=8), nullable=False, server_default="EU"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("total_net", sa.Numeric(precision=18, scale=2), nullable=False, server_default="0"),
            sa.Column("total_tax", sa.Numeric(precision=18, scale=2), nullable=False, server_default="0"),
            sa.Column("total_gross", sa.Numeric(precision=18, scale=2), nullable=False, server_default="0"),
            sa.Column("signer_name", sa.String(length=160), nullable=True),
            sa.Column("signature_data_url", sa.Text(), nullable=True),
            sa.Column("signed_at", sa.DateTime(), nullable=True),
            sa.Column("signed_ip", sa.String(length=64), nullable=True),
            sa.Column("signed_user_agent", sa.String(length=255), nullable=True),
            sa.Column("converted_invoice_id", sa.Integer(), sa.ForeignKey("finance_invoices.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("tenant_id", "company_id", "quote_number", name="uq_fin_quote_number"),
        )

    if _table_exists(bind, "finance_quotes"):
        if not _index_exists(bind, "finance_quotes", "ix_fin_quote_tenant_company_date"):
            op.create_index(
                "ix_fin_quote_tenant_company_date",
                "finance_quotes",
                ["tenant_id", "company_id", "issue_date"],
                unique=False,
            )
        if not _index_exists(bind, "finance_quotes", "ix_finance_quotes_tenant_id"):
            op.create_index(op.f("ix_finance_quotes_tenant_id"), "finance_quotes", ["tenant_id"], unique=False)
        if not _index_exists(bind, "finance_quotes", "ix_finance_quotes_company_id"):
            op.create_index(op.f("ix_finance_quotes_company_id"), "finance_quotes", ["company_id"], unique=False)
        if not _index_exists(bind, "finance_quotes", "ix_finance_quotes_counterparty_id"):
            op.create_index(op.f("ix_finance_quotes_counterparty_id"), "finance_quotes", ["counterparty_id"], unique=False)
        if not _index_exists(bind, "finance_quotes", "ix_finance_quotes_converted_invoice_id"):
            op.create_index(op.f("ix_finance_quotes_converted_invoice_id"), "finance_quotes", ["converted_invoice_id"], unique=False)

    if not _table_exists(bind, "finance_quote_lines"):
        op.create_table(
            "finance_quote_lines",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("finance_companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("quote_id", sa.Integer(), sa.ForeignKey("finance_quotes.id", ondelete="CASCADE"), nullable=False),
            sa.Column("description", sa.String(length=255), nullable=False),
            sa.Column("quantity", sa.Numeric(precision=18, scale=4), nullable=False, server_default="1"),
            sa.Column("unit_price", sa.Numeric(precision=18, scale=4), nullable=False, server_default="0"),
            sa.Column("vat_rate", sa.Numeric(precision=9, scale=4), nullable=False, server_default="0"),
            sa.Column("icms_rate", sa.Numeric(precision=9, scale=4), nullable=False, server_default="0"),
            sa.Column("ipi_rate", sa.Numeric(precision=9, scale=4), nullable=False, server_default="0"),
            sa.Column("pis_rate", sa.Numeric(precision=9, scale=4), nullable=False, server_default="0"),
            sa.Column("cofins_rate", sa.Numeric(precision=9, scale=4), nullable=False, server_default="0"),
            sa.Column("ncm_code", sa.String(length=16), nullable=True),
            sa.Column("cfop_code", sa.String(length=8), nullable=True),
            sa.Column("cest_code", sa.String(length=16), nullable=True),
            sa.Column("cst_icms", sa.String(length=4), nullable=True),
            sa.Column("cst_ipi", sa.String(length=4), nullable=True),
            sa.Column("cst_pis", sa.String(length=4), nullable=True),
            sa.Column("cst_cofins", sa.String(length=4), nullable=True),
            sa.Column("net_amount", sa.Numeric(precision=18, scale=2), nullable=False, server_default="0"),
            sa.Column("tax_amount", sa.Numeric(precision=18, scale=2), nullable=False, server_default="0"),
            sa.Column("gross_amount", sa.Numeric(precision=18, scale=2), nullable=False, server_default="0"),
            sa.Column("icms_amount", sa.Numeric(precision=18, scale=2), nullable=False, server_default="0"),
            sa.Column("ipi_amount", sa.Numeric(precision=18, scale=2), nullable=False, server_default="0"),
            sa.Column("pis_amount", sa.Numeric(precision=18, scale=2), nullable=False, server_default="0"),
            sa.Column("cofins_amount", sa.Numeric(precision=18, scale=2), nullable=False, server_default="0"),
        )

    if _table_exists(bind, "finance_quote_lines"):
        if not _index_exists(bind, "finance_quote_lines", "ix_finance_quote_lines_tenant_id"):
            op.create_index(op.f("ix_finance_quote_lines_tenant_id"), "finance_quote_lines", ["tenant_id"], unique=False)
        if not _index_exists(bind, "finance_quote_lines", "ix_finance_quote_lines_company_id"):
            op.create_index(op.f("ix_finance_quote_lines_company_id"), "finance_quote_lines", ["company_id"], unique=False)
        if not _index_exists(bind, "finance_quote_lines", "ix_finance_quote_lines_quote_id"):
            op.create_index(op.f("ix_finance_quote_lines_quote_id"), "finance_quote_lines", ["quote_id"], unique=False)


def downgrade():
    bind = op.get_bind()

    if _table_exists(bind, "finance_quote_lines"):
        for ix_name in (
            op.f("ix_finance_quote_lines_quote_id"),
            op.f("ix_finance_quote_lines_company_id"),
            op.f("ix_finance_quote_lines_tenant_id"),
        ):
            if _index_exists(bind, "finance_quote_lines", ix_name):
                op.drop_index(ix_name, table_name="finance_quote_lines")
        op.drop_table("finance_quote_lines")

    if _table_exists(bind, "finance_quotes"):
        for ix_name in (
            op.f("ix_finance_quotes_converted_invoice_id"),
            op.f("ix_finance_quotes_counterparty_id"),
            op.f("ix_finance_quotes_company_id"),
            op.f("ix_finance_quotes_tenant_id"),
            "ix_fin_quote_tenant_company_date",
        ):
            if _index_exists(bind, "finance_quotes", ix_name):
                op.drop_index(ix_name, table_name="finance_quotes")
        op.drop_table("finance_quotes")

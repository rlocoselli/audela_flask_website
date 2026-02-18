"""E-invoice (PDF+XML), alerts settings, and compliance exports

Revision ID: 20260218_einvoice_alerts_regulation
Revises: 20260216_add_finance_reference_tables
Create Date: 2026-02-18

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260218_einvoice_alerts_regulation"
down_revision = "20260216_add_finance_reference_tables"
branch_labels = None
depends_on = None


def upgrade():
    # --- finance_companies: add optional legal/invoicing fields
    with op.batch_alter_table("finance_companies") as batch:
        batch.add_column(sa.Column("country_code", sa.String(length=2), nullable=True))
        batch.add_column(sa.Column("vat_number", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("siret", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("registration_number", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("address_line1", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("address_line2", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("postal_code", sa.String(length=32), nullable=True))
        batch.add_column(sa.Column("city", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("state", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("email", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("phone", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("iban", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("bic", sa.String(length=64), nullable=True))

    # --- finance_counterparties: missing columns expected by the model + e-invoicing fields
    with op.batch_alter_table("finance_counterparties") as batch:
        batch.add_column(sa.Column("default_currency", sa.String(length=8), nullable=True))
        batch.add_column(sa.Column("country_code", sa.String(length=2), nullable=True))
        batch.add_column(sa.Column("vat_number", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("tax_id", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("address_line1", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("address_line2", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("postal_code", sa.String(length=32), nullable=True))
        batch.add_column(sa.Column("city", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("state", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("email", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("phone", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("sdi_code", sa.String(length=16), nullable=True))
        batch.add_column(sa.Column("pec_email", sa.String(length=255), nullable=True))

    # --- finance_statement_imports: columns used by routes/models
    with op.batch_alter_table("finance_statement_imports") as batch:
        batch.add_column(sa.Column("imported_rows", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("skipped_rows", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("payload_json", sa.JSON(), nullable=True))

    # --- finance_liabilities: optional schedule helpers
    with op.batch_alter_table("finance_liabilities") as batch:
        batch.add_column(sa.Column("installment_amount", sa.Numeric(18, 2), nullable=True))
        batch.add_column(sa.Column("next_payment_date", sa.Date(), nullable=True))

    # --- finance_settings
    op.create_table(
        "finance_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("finance_companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "company_id", "key", name="uq_finance_settings_key"),
    )

    # --- invoices
    op.create_table(
        "finance_invoices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("finance_companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("counterparty_id", sa.Integer(), sa.ForeignKey("finance_counterparties.id", ondelete="SET NULL"), nullable=True),
        sa.Column("settlement_account_id", sa.Integer(), sa.ForeignKey("finance_accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("invoice_number", sa.String(length=64), nullable=False),
        sa.Column("invoice_type", sa.String(length=16), nullable=False, server_default="sale"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="EUR"),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("total_net", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("total_tax", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("total_gross", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "company_id", "invoice_number", name="uq_finance_invoice_number"),
    )
    op.create_index("ix_finance_invoices_dates", "finance_invoices", ["tenant_id", "company_id", "issue_date", "due_date"])

    op.create_table(
        "finance_invoice_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("finance_companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("finance_invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("vat_rate", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("net_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("gross_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("finance_invoice_lines")
    op.drop_index("ix_finance_invoices_dates", table_name="finance_invoices")
    op.drop_table("finance_invoices")
    op.drop_table("finance_settings")

    with op.batch_alter_table("finance_liabilities") as batch:
        batch.drop_column("next_payment_date")
        batch.drop_column("installment_amount")

    with op.batch_alter_table("finance_statement_imports") as batch:
        batch.drop_column("payload_json")
        batch.drop_column("skipped_rows")
        batch.drop_column("imported_rows")

    with op.batch_alter_table("finance_counterparties") as batch:
        batch.drop_column("pec_email")
        batch.drop_column("sdi_code")
        batch.drop_column("phone")
        batch.drop_column("email")
        batch.drop_column("state")
        batch.drop_column("city")
        batch.drop_column("postal_code")
        batch.drop_column("address_line2")
        batch.drop_column("address_line1")
        batch.drop_column("tax_id")
        batch.drop_column("vat_number")
        batch.drop_column("country_code")
        batch.drop_column("default_currency")

    with op.batch_alter_table("finance_companies") as batch:
        batch.drop_column("bic")
        batch.drop_column("iban")
        batch.drop_column("phone")
        batch.drop_column("email")
        batch.drop_column("state")
        batch.drop_column("city")
        batch.drop_column("postal_code")
        batch.drop_column("address_line2")
        batch.drop_column("address_line1")
        batch.drop_column("registration_number")
        batch.drop_column("siret")
        batch.drop_column("vat_number")
        batch.drop_column("country_code")
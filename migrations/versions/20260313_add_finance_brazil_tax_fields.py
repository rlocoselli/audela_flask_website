"""add finance brazil tax fields

Revision ID: 20260313_add_finance_brazil_tax_fields
Revises: 20260313_add_finance_invoice_filter_indexes
Create Date: 2026-03-13
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260313_add_finance_brazil_tax_fields"
down_revision = "20260313_add_finance_invoice_filter_indexes"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def _column_names(bind, table_name: str) -> set[str]:
    return {col["name"] for col in sa.inspect(bind).get_columns(table_name)}


def upgrade():
    bind = op.get_bind()

    if _table_exists(bind, "finance_invoices"):
        cols = _column_names(bind, "finance_invoices")
        with op.batch_alter_table("finance_invoices", schema=None) as batch_op:
            if "fiscal_country" not in cols:
                batch_op.add_column(sa.Column("fiscal_country", sa.String(length=8), nullable=False, server_default="EU"))
            if "document_model" not in cols:
                batch_op.add_column(sa.Column("document_model", sa.String(length=8), nullable=False, server_default="55"))
            if "document_series" not in cols:
                batch_op.add_column(sa.Column("document_series", sa.String(length=8), nullable=False, server_default="1"))
            if "sefaz_environment" not in cols:
                batch_op.add_column(sa.Column("sefaz_environment", sa.String(length=16), nullable=False, server_default="homologation"))
            if "natureza_operacao" not in cols:
                batch_op.add_column(sa.Column("natureza_operacao", sa.String(length=120), nullable=True))
            if "operation_destination" not in cols:
                batch_op.add_column(sa.Column("operation_destination", sa.String(length=8), nullable=False, server_default="1"))
            if "payment_indicator" not in cols:
                batch_op.add_column(sa.Column("payment_indicator", sa.String(length=8), nullable=False, server_default="0"))
            if "presence_indicator" not in cols:
                batch_op.add_column(sa.Column("presence_indicator", sa.String(length=8), nullable=False, server_default="1"))
            if "final_consumer" not in cols:
                batch_op.add_column(sa.Column("final_consumer", sa.Boolean(), nullable=False, server_default=sa.true()))
            if "invoice_purpose" not in cols:
                batch_op.add_column(sa.Column("invoice_purpose", sa.String(length=8), nullable=False, server_default="1"))
            if "emission_type" not in cols:
                batch_op.add_column(sa.Column("emission_type", sa.String(length=8), nullable=False, server_default="1"))
            if "cnf_code" not in cols:
                batch_op.add_column(sa.Column("cnf_code", sa.String(length=16), nullable=True))
            if "needs_sefaz_validation" not in cols:
                batch_op.add_column(sa.Column("needs_sefaz_validation", sa.Boolean(), nullable=False, server_default=sa.false()))

    if _table_exists(bind, "finance_invoice_lines"):
        cols = _column_names(bind, "finance_invoice_lines")
        with op.batch_alter_table("finance_invoice_lines", schema=None) as batch_op:
            if "icms_rate" not in cols:
                batch_op.add_column(sa.Column("icms_rate", sa.Numeric(precision=9, scale=4), nullable=False, server_default="0"))
            if "ipi_rate" not in cols:
                batch_op.add_column(sa.Column("ipi_rate", sa.Numeric(precision=9, scale=4), nullable=False, server_default="0"))
            if "pis_rate" not in cols:
                batch_op.add_column(sa.Column("pis_rate", sa.Numeric(precision=9, scale=4), nullable=False, server_default="0"))
            if "cofins_rate" not in cols:
                batch_op.add_column(sa.Column("cofins_rate", sa.Numeric(precision=9, scale=4), nullable=False, server_default="0"))
            if "ncm_code" not in cols:
                batch_op.add_column(sa.Column("ncm_code", sa.String(length=16), nullable=True))
            if "cfop_code" not in cols:
                batch_op.add_column(sa.Column("cfop_code", sa.String(length=8), nullable=True))
            if "cest_code" not in cols:
                batch_op.add_column(sa.Column("cest_code", sa.String(length=16), nullable=True))
            if "cst_icms" not in cols:
                batch_op.add_column(sa.Column("cst_icms", sa.String(length=4), nullable=True))
            if "cst_ipi" not in cols:
                batch_op.add_column(sa.Column("cst_ipi", sa.String(length=4), nullable=True))
            if "cst_pis" not in cols:
                batch_op.add_column(sa.Column("cst_pis", sa.String(length=4), nullable=True))
            if "cst_cofins" not in cols:
                batch_op.add_column(sa.Column("cst_cofins", sa.String(length=4), nullable=True))
            if "icms_amount" not in cols:
                batch_op.add_column(sa.Column("icms_amount", sa.Numeric(precision=18, scale=2), nullable=False, server_default="0"))
            if "ipi_amount" not in cols:
                batch_op.add_column(sa.Column("ipi_amount", sa.Numeric(precision=18, scale=2), nullable=False, server_default="0"))
            if "pis_amount" not in cols:
                batch_op.add_column(sa.Column("pis_amount", sa.Numeric(precision=18, scale=2), nullable=False, server_default="0"))
            if "cofins_amount" not in cols:
                batch_op.add_column(sa.Column("cofins_amount", sa.Numeric(precision=18, scale=2), nullable=False, server_default="0"))

    if _table_exists(bind, "finance_products"):
        cols = _column_names(bind, "finance_products")
        with op.batch_alter_table("finance_products", schema=None) as batch_op:
            if "br_icms_rate" not in cols:
                batch_op.add_column(sa.Column("br_icms_rate", sa.Numeric(precision=9, scale=4), nullable=False, server_default="0"))
            if "br_ipi_rate" not in cols:
                batch_op.add_column(sa.Column("br_ipi_rate", sa.Numeric(precision=9, scale=4), nullable=False, server_default="0"))
            if "br_pis_rate" not in cols:
                batch_op.add_column(sa.Column("br_pis_rate", sa.Numeric(precision=9, scale=4), nullable=False, server_default="0"))
            if "br_cofins_rate" not in cols:
                batch_op.add_column(sa.Column("br_cofins_rate", sa.Numeric(precision=9, scale=4), nullable=False, server_default="0"))
            if "br_ncm_code" not in cols:
                batch_op.add_column(sa.Column("br_ncm_code", sa.String(length=16), nullable=True))
            if "br_cfop_code" not in cols:
                batch_op.add_column(sa.Column("br_cfop_code", sa.String(length=8), nullable=True))
            if "br_cest_code" not in cols:
                batch_op.add_column(sa.Column("br_cest_code", sa.String(length=16), nullable=True))
            if "br_cst_icms" not in cols:
                batch_op.add_column(sa.Column("br_cst_icms", sa.String(length=4), nullable=True))
            if "br_cst_ipi" not in cols:
                batch_op.add_column(sa.Column("br_cst_ipi", sa.String(length=4), nullable=True))
            if "br_cst_pis" not in cols:
                batch_op.add_column(sa.Column("br_cst_pis", sa.String(length=4), nullable=True))
            if "br_cst_cofins" not in cols:
                batch_op.add_column(sa.Column("br_cst_cofins", sa.String(length=4), nullable=True))


def downgrade():
    bind = op.get_bind()

    if _table_exists(bind, "finance_products"):
        cols = _column_names(bind, "finance_products")
        with op.batch_alter_table("finance_products", schema=None) as batch_op:
            for name in (
                "br_cst_cofins",
                "br_cst_pis",
                "br_cst_ipi",
                "br_cst_icms",
                "br_cest_code",
                "br_cfop_code",
                "br_ncm_code",
                "br_cofins_rate",
                "br_pis_rate",
                "br_ipi_rate",
                "br_icms_rate",
            ):
                if name in cols:
                    batch_op.drop_column(name)

    if _table_exists(bind, "finance_invoice_lines"):
        cols = _column_names(bind, "finance_invoice_lines")
        with op.batch_alter_table("finance_invoice_lines", schema=None) as batch_op:
            for name in (
                "cofins_amount",
                "pis_amount",
                "ipi_amount",
                "icms_amount",
                "cst_cofins",
                "cst_pis",
                "cst_ipi",
                "cst_icms",
                "cest_code",
                "cfop_code",
                "ncm_code",
                "cofins_rate",
                "pis_rate",
                "ipi_rate",
                "icms_rate",
            ):
                if name in cols:
                    batch_op.drop_column(name)

    if _table_exists(bind, "finance_invoices"):
        cols = _column_names(bind, "finance_invoices")
        with op.batch_alter_table("finance_invoices", schema=None) as batch_op:
            for name in (
                "needs_sefaz_validation",
                "cnf_code",
                "emission_type",
                "invoice_purpose",
                "final_consumer",
                "presence_indicator",
                "payment_indicator",
                "operation_destination",
                "natureza_operacao",
                "sefaz_environment",
                "document_series",
                "document_model",
                "fiscal_country",
            ):
                if name in cols:
                    batch_op.drop_column(name)

"""add finance invoice filter indexes

Revision ID: 20260313_add_finance_invoice_filter_indexes
Revises: 20260308_add_credit_facility_utilizations
Create Date: 2026-03-13
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260313_add_finance_invoice_filter_indexes"
down_revision = "20260308_add_credit_facility_utilizations"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def _index_names(bind, table_name: str) -> set[str]:
    return {i["name"] for i in sa.inspect(bind).get_indexes(table_name)}


def upgrade():
    bind = op.get_bind()
    if not _table_exists(bind, "finance_invoices"):
        return

    idx = _index_names(bind, "finance_invoices")
    with op.batch_alter_table("finance_invoices", schema=None) as batch_op:
        if "ix_fin_invoice_tenant_company_status_issue" not in idx:
            batch_op.create_index(
                "ix_fin_invoice_tenant_company_status_issue",
                ["tenant_id", "company_id", "status", "issue_date"],
                unique=False,
            )
        if "ix_fin_invoice_tenant_company_type_issue" not in idx:
            batch_op.create_index(
                "ix_fin_invoice_tenant_company_type_issue",
                ["tenant_id", "company_id", "invoice_type", "issue_date"],
                unique=False,
            )
        if "ix_fin_invoice_tenant_company_due_date" not in idx:
            batch_op.create_index(
                "ix_fin_invoice_tenant_company_due_date",
                ["tenant_id", "company_id", "due_date"],
                unique=False,
            )


def downgrade():
    bind = op.get_bind()
    if not _table_exists(bind, "finance_invoices"):
        return

    idx = _index_names(bind, "finance_invoices")
    with op.batch_alter_table("finance_invoices", schema=None) as batch_op:
        for name in (
            "ix_fin_invoice_tenant_company_due_date",
            "ix_fin_invoice_tenant_company_type_issue",
            "ix_fin_invoice_tenant_company_status_issue",
        ):
            if name in idx:
                batch_op.drop_index(name)

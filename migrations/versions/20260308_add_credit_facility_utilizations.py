"""add credit facility utilizations table

Revision ID: 20260308_add_credit_facility_utilizations
Revises: 20260308_add_credit_covenants
Create Date: 2026-03-08
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260308_add_credit_facility_utilizations"
down_revision = "20260308_add_credit_covenants"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def _index_names(bind, table_name: str) -> set[str]:
    return {i["name"] for i in sa.inspect(bind).get_indexes(table_name)}


def upgrade():
    bind = op.get_bind()

    if not _table_exists(bind, "credit_facility_utilizations"):
        op.create_table(
            "credit_facility_utilizations",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("borrower_id", sa.Integer(), nullable=False),
            sa.Column("deal_id", sa.Integer(), nullable=True),
            sa.Column("facility_id", sa.Integer(), nullable=True),
            sa.Column("utilization_type", sa.String(length=32), nullable=False, server_default="drawdown"),
            sa.Column("amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("currency", sa.String(length=8), nullable=False, server_default="EUR"),
            sa.Column("value_date", sa.Date(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="posted"),
            sa.Column("reference", sa.String(length=120), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["borrower_id"], ["credit_borrowers.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["deal_id"], ["credit_deals.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["facility_id"], ["credit_facilities.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    idx = _index_names(bind, "credit_facility_utilizations")
    with op.batch_alter_table("credit_facility_utilizations", schema=None) as batch_op:
        if "ix_credit_facility_utilizations_tenant_id" not in idx:
            batch_op.create_index("ix_credit_facility_utilizations_tenant_id", ["tenant_id"], unique=False)
        if "ix_credit_facility_utilizations_borrower_id" not in idx:
            batch_op.create_index("ix_credit_facility_utilizations_borrower_id", ["borrower_id"], unique=False)
        if "ix_credit_facility_utilizations_deal_id" not in idx:
            batch_op.create_index("ix_credit_facility_utilizations_deal_id", ["deal_id"], unique=False)
        if "ix_credit_facility_utilizations_facility_id" not in idx:
            batch_op.create_index("ix_credit_facility_utilizations_facility_id", ["facility_id"], unique=False)
        if "ix_credit_facility_utilizations_utilization_type" not in idx:
            batch_op.create_index("ix_credit_facility_utilizations_utilization_type", ["utilization_type"], unique=False)
        if "ix_credit_facility_utilizations_value_date" not in idx:
            batch_op.create_index("ix_credit_facility_utilizations_value_date", ["value_date"], unique=False)
        if "ix_credit_facility_utilizations_status" not in idx:
            batch_op.create_index("ix_credit_facility_utilizations_status", ["status"], unique=False)


def downgrade():
    bind = op.get_bind()
    if not _table_exists(bind, "credit_facility_utilizations"):
        return

    idx = _index_names(bind, "credit_facility_utilizations")
    with op.batch_alter_table("credit_facility_utilizations", schema=None) as batch_op:
        for name in (
            "ix_credit_facility_utilizations_status",
            "ix_credit_facility_utilizations_value_date",
            "ix_credit_facility_utilizations_utilization_type",
            "ix_credit_facility_utilizations_facility_id",
            "ix_credit_facility_utilizations_deal_id",
            "ix_credit_facility_utilizations_borrower_id",
            "ix_credit_facility_utilizations_tenant_id",
        ):
            if name in idx:
                batch_op.drop_index(name)

    op.drop_table("credit_facility_utilizations")

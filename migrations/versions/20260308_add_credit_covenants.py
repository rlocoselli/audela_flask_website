"""add credit covenants table

Revision ID: 20260308_add_credit_covenants
Revises: 20260308_add_credit_approval_dates
Create Date: 2026-03-08
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260308_add_credit_covenants"
down_revision = "20260308_add_credit_approval_dates"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def _index_names(bind, table_name: str) -> set[str]:
    return {i["name"] for i in sa.inspect(bind).get_indexes(table_name)}


def upgrade():
    bind = op.get_bind()

    if not _table_exists(bind, "credit_covenants"):
        op.create_table(
            "credit_covenants",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("borrower_id", sa.Integer(), nullable=False),
            sa.Column("deal_id", sa.Integer(), nullable=True),
            sa.Column("facility_id", sa.Integer(), nullable=True),
            sa.Column("name", sa.String(length=180), nullable=False),
            sa.Column("scope_level", sa.String(length=32), nullable=False, server_default="deal"),
            sa.Column("metric", sa.String(length=120), nullable=True),
            sa.Column("operator", sa.String(length=16), nullable=False, server_default=">="),
            sa.Column("threshold_value", sa.Numeric(18, 4), nullable=True),
            sa.Column("frequency", sa.String(length=32), nullable=False, server_default="quarterly"),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("due_date", sa.Date(), nullable=True),
            sa.Column("last_test_date", sa.Date(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["borrower_id"], ["credit_borrowers.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["deal_id"], ["credit_deals.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["facility_id"], ["credit_facilities.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    idx = _index_names(bind, "credit_covenants")
    with op.batch_alter_table("credit_covenants", schema=None) as batch_op:
        if "ix_credit_covenants_tenant_id" not in idx:
            batch_op.create_index("ix_credit_covenants_tenant_id", ["tenant_id"], unique=False)
        if "ix_credit_covenants_borrower_id" not in idx:
            batch_op.create_index("ix_credit_covenants_borrower_id", ["borrower_id"], unique=False)
        if "ix_credit_covenants_deal_id" not in idx:
            batch_op.create_index("ix_credit_covenants_deal_id", ["deal_id"], unique=False)
        if "ix_credit_covenants_facility_id" not in idx:
            batch_op.create_index("ix_credit_covenants_facility_id", ["facility_id"], unique=False)
        if "ix_credit_covenants_scope_level" not in idx:
            batch_op.create_index("ix_credit_covenants_scope_level", ["scope_level"], unique=False)
        if "ix_credit_covenants_status" not in idx:
            batch_op.create_index("ix_credit_covenants_status", ["status"], unique=False)
        if "ix_credit_covenants_due_date" not in idx:
            batch_op.create_index("ix_credit_covenants_due_date", ["due_date"], unique=False)
        if "ix_credit_covenants_last_test_date" not in idx:
            batch_op.create_index("ix_credit_covenants_last_test_date", ["last_test_date"], unique=False)


def downgrade():
    bind = op.get_bind()
    if not _table_exists(bind, "credit_covenants"):
        return

    idx = _index_names(bind, "credit_covenants")
    with op.batch_alter_table("credit_covenants", schema=None) as batch_op:
        for name in (
            "ix_credit_covenants_last_test_date",
            "ix_credit_covenants_due_date",
            "ix_credit_covenants_status",
            "ix_credit_covenants_scope_level",
            "ix_credit_covenants_facility_id",
            "ix_credit_covenants_deal_id",
            "ix_credit_covenants_borrower_id",
            "ix_credit_covenants_tenant_id",
        ):
            if name in idx:
                batch_op.drop_index(name)

    op.drop_table("credit_covenants")

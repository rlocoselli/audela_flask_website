"""add credit approval workflow tables

Revision ID: 20260306_add_credit_approval_workflow
Revises: 20260306_add_credit_reference_i18n_columns
Create Date: 2026-03-06
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260306_add_credit_approval_workflow"
down_revision = "20260306_add_credit_reference_i18n_columns"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def _column_names(bind, table_name: str) -> set[str]:
    return {c["name"] for c in sa.inspect(bind).get_columns(table_name)}


def _index_names(bind, table_name: str) -> set[str]:
    return {i["name"] for i in sa.inspect(bind).get_indexes(table_name)}


def upgrade():
    bind = op.get_bind()

    if not _table_exists(bind, "credit_analyst_groups"):
        op.create_table(
            "credit_analyst_groups",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("description", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "name", name="uq_credit_analyst_group_tenant_name"),
        )
    if "ix_credit_analyst_groups_tenant_id" not in _index_names(bind, "credit_analyst_groups"):
        op.create_index("ix_credit_analyst_groups_tenant_id", "credit_analyst_groups", ["tenant_id"])

    if not _table_exists(bind, "credit_analyst_group_members"):
        op.create_table(
            "credit_analyst_group_members",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("group_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("function_name", sa.String(length=64), nullable=False, server_default="analyst"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["group_id"], ["credit_analyst_groups.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("group_id", "user_id", "function_name", name="uq_credit_group_member_function"),
        )
    if "ix_credit_analyst_group_members_group_id" not in _index_names(bind, "credit_analyst_group_members"):
        op.create_index("ix_credit_analyst_group_members_group_id", "credit_analyst_group_members", ["group_id"])
    if "ix_credit_analyst_group_members_user_id" not in _index_names(bind, "credit_analyst_group_members"):
        op.create_index("ix_credit_analyst_group_members_user_id", "credit_analyst_group_members", ["user_id"])

    if not _table_exists(bind, "credit_approval_workflow_steps"):
        op.create_table(
            "credit_approval_workflow_steps",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("step_order", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("stage", sa.String(length=64), nullable=False, server_default="analyst_review"),
            sa.Column("step_name", sa.String(length=120), nullable=False, server_default=""),
            sa.Column("group_id", sa.Integer(), nullable=True),
            sa.Column("function_name", sa.String(length=64), nullable=True),
            sa.Column("sla_days", sa.Integer(), nullable=True),
            sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["group_id"], ["credit_analyst_groups.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
    if "ix_credit_approval_workflow_steps_tenant_id" not in _index_names(bind, "credit_approval_workflow_steps"):
        op.create_index("ix_credit_approval_workflow_steps_tenant_id", "credit_approval_workflow_steps", ["tenant_id"])
    if "ix_credit_approval_workflow_steps_step_order" not in _index_names(bind, "credit_approval_workflow_steps"):
        op.create_index("ix_credit_approval_workflow_steps_step_order", "credit_approval_workflow_steps", ["step_order"])
    if "ix_credit_approval_workflow_steps_group_id" not in _index_names(bind, "credit_approval_workflow_steps"):
        op.create_index("ix_credit_approval_workflow_steps_group_id", "credit_approval_workflow_steps", ["group_id"])

    approval_columns = _column_names(bind, "credit_approvals")
    if "workflow_step_id" not in approval_columns:
        with op.batch_alter_table("credit_approvals", schema=None) as batch_op:
            batch_op.add_column(sa.Column("workflow_step_id", sa.Integer(), nullable=True))
            batch_op.create_index("ix_credit_approvals_workflow_step_id", ["workflow_step_id"], unique=False)
            batch_op.create_foreign_key(
                "fk_credit_approvals_workflow_step_id",
                "credit_approval_workflow_steps",
                ["workflow_step_id"],
                ["id"],
                ondelete="SET NULL",
            )

    approval_columns = _column_names(bind, "credit_approvals")
    if "analyst_group_id" not in approval_columns:
        with op.batch_alter_table("credit_approvals", schema=None) as batch_op:
            batch_op.add_column(sa.Column("analyst_group_id", sa.Integer(), nullable=True))
            batch_op.create_index("ix_credit_approvals_analyst_group_id", ["analyst_group_id"], unique=False)
            batch_op.create_foreign_key(
                "fk_credit_approvals_analyst_group_id",
                "credit_analyst_groups",
                ["analyst_group_id"],
                ["id"],
                ondelete="SET NULL",
            )

    approval_columns = _column_names(bind, "credit_approvals")
    if "analyst_function" not in approval_columns:
        with op.batch_alter_table("credit_approvals", schema=None) as batch_op:
            batch_op.add_column(sa.Column("analyst_function", sa.String(length=64), nullable=True))


def downgrade():
    bind = op.get_bind()

    if _table_exists(bind, "credit_approvals") and "analyst_function" in _column_names(bind, "credit_approvals"):
        with op.batch_alter_table("credit_approvals", schema=None) as batch_op:
            batch_op.drop_column("analyst_function")

    if _table_exists(bind, "credit_approvals") and "analyst_group_id" in _column_names(bind, "credit_approvals"):
        with op.batch_alter_table("credit_approvals", schema=None) as batch_op:
            batch_op.drop_constraint("fk_credit_approvals_analyst_group_id", type_="foreignkey")
            batch_op.drop_index("ix_credit_approvals_analyst_group_id")
            batch_op.drop_column("analyst_group_id")

    if _table_exists(bind, "credit_approvals") and "workflow_step_id" in _column_names(bind, "credit_approvals"):
        with op.batch_alter_table("credit_approvals", schema=None) as batch_op:
            batch_op.drop_constraint("fk_credit_approvals_workflow_step_id", type_="foreignkey")
            batch_op.drop_index("ix_credit_approvals_workflow_step_id")
            batch_op.drop_column("workflow_step_id")

    if _table_exists(bind, "credit_approval_workflow_steps"):
        if "ix_credit_approval_workflow_steps_group_id" in _index_names(bind, "credit_approval_workflow_steps"):
            op.drop_index("ix_credit_approval_workflow_steps_group_id", table_name="credit_approval_workflow_steps")
        if "ix_credit_approval_workflow_steps_step_order" in _index_names(bind, "credit_approval_workflow_steps"):
            op.drop_index("ix_credit_approval_workflow_steps_step_order", table_name="credit_approval_workflow_steps")
        if "ix_credit_approval_workflow_steps_tenant_id" in _index_names(bind, "credit_approval_workflow_steps"):
            op.drop_index("ix_credit_approval_workflow_steps_tenant_id", table_name="credit_approval_workflow_steps")
        op.drop_table("credit_approval_workflow_steps")

    if _table_exists(bind, "credit_analyst_group_members"):
        if "ix_credit_analyst_group_members_user_id" in _index_names(bind, "credit_analyst_group_members"):
            op.drop_index("ix_credit_analyst_group_members_user_id", table_name="credit_analyst_group_members")
        if "ix_credit_analyst_group_members_group_id" in _index_names(bind, "credit_analyst_group_members"):
            op.drop_index("ix_credit_analyst_group_members_group_id", table_name="credit_analyst_group_members")
        op.drop_table("credit_analyst_group_members")

    if _table_exists(bind, "credit_analyst_groups"):
        if "ix_credit_analyst_groups_tenant_id" in _index_names(bind, "credit_analyst_groups"):
            op.drop_index("ix_credit_analyst_groups_tenant_id", table_name="credit_analyst_groups")
        op.drop_table("credit_analyst_groups")

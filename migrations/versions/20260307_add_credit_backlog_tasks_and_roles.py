"""add credit backlog task table and credit system roles

Revision ID: 20260307_add_credit_backlog_tasks_and_roles
Revises: 20260306_add_credit_function_register_and_financial_import
Create Date: 2026-03-07
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260307_add_credit_backlog_tasks_and_roles"
down_revision = "20260306_add_credit_function_register_and_financial_import"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def _column_names(bind, table_name: str) -> set[str]:
    return {c["name"] for c in sa.inspect(bind).get_columns(table_name)}


def _index_names(bind, table_name: str) -> set[str]:
    return {i["name"] for i in sa.inspect(bind).get_indexes(table_name)}


def _seed_role(bind, code: str, description: str) -> None:
    roles = sa.table(
        "roles",
        sa.column("id", sa.Integer),
        sa.column("code", sa.String),
        sa.column("description", sa.String),
    )
    existing = bind.execute(sa.select(roles.c.id).where(roles.c.code == code).limit(1)).first()
    if existing:
        return
    bind.execute(sa.insert(roles).values(code=code, description=description))


def upgrade():
    bind = op.get_bind()

    for code, description in [
        ("credit_admin", "Administration credit et workflow"),
        ("credit_analyst", "Analyste credit"),
        ("credit_approver", "Approbateur credit"),
        ("credit_viewer", "Lecture seule credit"),
    ]:
        _seed_role(bind, code, description)

    if not _table_exists(bind, "credit_backlog_tasks"):
        op.create_table(
            "credit_backlog_tasks",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("memo_id", sa.Integer(), nullable=True),
            sa.Column("deal_id", sa.Integer(), nullable=True),
            sa.Column("borrower_id", sa.Integer(), nullable=True),
            sa.Column("workflow_step_id", sa.Integer(), nullable=True),
            sa.Column("title", sa.String(length=180), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="todo"),
            sa.Column("priority", sa.String(length=16), nullable=False, server_default="normal"),
            sa.Column("due_date", sa.Date(), nullable=True),
            sa.Column("assigned_user_id", sa.Integer(), nullable=True),
            sa.Column("assigned_group_id", sa.Integer(), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["assigned_group_id"], ["credit_analyst_groups.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["assigned_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["borrower_id"], ["credit_borrowers.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["deal_id"], ["credit_deals.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["memo_id"], ["credit_memos.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["workflow_step_id"], ["credit_approval_workflow_steps.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )

    for idx_name, cols in [
        ("ix_credit_backlog_tasks_tenant_id", ["tenant_id"]),
        ("ix_credit_backlog_tasks_memo_id", ["memo_id"]),
        ("ix_credit_backlog_tasks_deal_id", ["deal_id"]),
        ("ix_credit_backlog_tasks_borrower_id", ["borrower_id"]),
        ("ix_credit_backlog_tasks_workflow_step_id", ["workflow_step_id"]),
        ("ix_credit_backlog_tasks_assigned_user_id", ["assigned_user_id"]),
        ("ix_credit_backlog_tasks_assigned_group_id", ["assigned_group_id"]),
        ("ix_credit_backlog_tasks_created_by_user_id", ["created_by_user_id"]),
        ("ix_credit_backlog_tasks_status", ["status"]),
        ("ix_credit_backlog_tasks_priority", ["priority"]),
    ]:
        if idx_name not in _index_names(bind, "credit_backlog_tasks"):
            op.create_index(idx_name, "credit_backlog_tasks", cols)


def downgrade():
    bind = op.get_bind()

    if _table_exists(bind, "credit_backlog_tasks"):
        for idx_name in [
            "ix_credit_backlog_tasks_priority",
            "ix_credit_backlog_tasks_status",
            "ix_credit_backlog_tasks_created_by_user_id",
            "ix_credit_backlog_tasks_assigned_group_id",
            "ix_credit_backlog_tasks_assigned_user_id",
            "ix_credit_backlog_tasks_workflow_step_id",
            "ix_credit_backlog_tasks_borrower_id",
            "ix_credit_backlog_tasks_deal_id",
            "ix_credit_backlog_tasks_memo_id",
            "ix_credit_backlog_tasks_tenant_id",
        ]:
            if idx_name in _index_names(bind, "credit_backlog_tasks"):
                op.drop_index(idx_name, table_name="credit_backlog_tasks")
        op.drop_table("credit_backlog_tasks")

    roles = sa.table(
        "roles",
        sa.column("code", sa.String),
    )
    bind.execute(
        sa.delete(roles).where(
            roles.c.code.in_([
                "credit_admin",
                "credit_analyst",
                "credit_approver",
                "credit_viewer",
            ])
        )
    )

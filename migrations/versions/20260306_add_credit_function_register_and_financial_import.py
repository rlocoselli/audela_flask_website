"""add credit function register and financial import columns

Revision ID: 20260306_add_credit_function_register_and_financial_import
Revises: 20260306_add_credit_approval_workflow
Create Date: 2026-03-06
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260306_add_credit_function_register_and_financial_import"
down_revision = "20260306_add_credit_approval_workflow"
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

    if not _table_exists(bind, "credit_analyst_functions"):
        op.create_table(
            "credit_analyst_functions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("code", sa.String(length=64), nullable=False),
            sa.Column("label", sa.String(length=120), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "code", name="uq_credit_analyst_function_tenant_code"),
        )
    if "ix_credit_analyst_functions_tenant_id" not in _index_names(bind, "credit_analyst_functions"):
        op.create_index("ix_credit_analyst_functions_tenant_id", "credit_analyst_functions", ["tenant_id"])

    members_cols = _column_names(bind, "credit_analyst_group_members")
    if "function_id" not in members_cols:
        with op.batch_alter_table("credit_analyst_group_members", schema=None) as batch_op:
            batch_op.add_column(sa.Column("function_id", sa.Integer(), nullable=True))
            batch_op.create_index("ix_credit_analyst_group_members_function_id", ["function_id"], unique=False)
            batch_op.create_foreign_key(
                "fk_credit_analyst_group_members_function_id",
                "credit_analyst_functions",
                ["function_id"],
                ["id"],
                ondelete="SET NULL",
            )

    steps_cols = _column_names(bind, "credit_approval_workflow_steps")
    if "function_id" not in steps_cols:
        with op.batch_alter_table("credit_approval_workflow_steps", schema=None) as batch_op:
            batch_op.add_column(sa.Column("function_id", sa.Integer(), nullable=True))
            batch_op.create_index("ix_credit_approval_workflow_steps_function_id", ["function_id"], unique=False)
            batch_op.create_foreign_key(
                "fk_credit_approval_workflow_steps_function_id",
                "credit_analyst_functions",
                ["function_id"],
                ["id"],
                ondelete="SET NULL",
            )

    approvals_cols = _column_names(bind, "credit_approvals")
    if "analyst_function_id" not in approvals_cols:
        with op.batch_alter_table("credit_approvals", schema=None) as batch_op:
            batch_op.add_column(sa.Column("analyst_function_id", sa.Integer(), nullable=True))
            batch_op.create_index("ix_credit_approvals_analyst_function_id", ["analyst_function_id"], unique=False)
            batch_op.create_foreign_key(
                "fk_credit_approvals_analyst_function_id",
                "credit_analyst_functions",
                ["analyst_function_id"],
                ["id"],
                ondelete="SET NULL",
            )

    fin_cols = _column_names(bind, "credit_financial_statements")
    if "imported_by_user_id" not in fin_cols:
        with op.batch_alter_table("credit_financial_statements", schema=None) as batch_op:
            batch_op.add_column(sa.Column("imported_by_user_id", sa.Integer(), nullable=True))
            batch_op.create_index("ix_credit_financial_statements_imported_by_user_id", ["imported_by_user_id"], unique=False)
            batch_op.create_foreign_key(
                "fk_credit_financial_statements_imported_by_user_id",
                "users",
                ["imported_by_user_id"],
                ["id"],
                ondelete="SET NULL",
            )

    fin_cols = _column_names(bind, "credit_financial_statements")
    if "analyst_user_id" not in fin_cols:
        with op.batch_alter_table("credit_financial_statements", schema=None) as batch_op:
            batch_op.add_column(sa.Column("analyst_user_id", sa.Integer(), nullable=True))
            batch_op.create_index("ix_credit_financial_statements_analyst_user_id", ["analyst_user_id"], unique=False)
            batch_op.create_foreign_key(
                "fk_credit_financial_statements_analyst_user_id",
                "users",
                ["analyst_user_id"],
                ["id"],
                ondelete="SET NULL",
            )

    fin_cols = _column_names(bind, "credit_financial_statements")
    if "analyst_function_id" not in fin_cols:
        with op.batch_alter_table("credit_financial_statements", schema=None) as batch_op:
            batch_op.add_column(sa.Column("analyst_function_id", sa.Integer(), nullable=True))
            batch_op.create_index("ix_credit_financial_statements_analyst_function_id", ["analyst_function_id"], unique=False)
            batch_op.create_foreign_key(
                "fk_credit_financial_statements_analyst_function_id",
                "credit_analyst_functions",
                ["analyst_function_id"],
                ["id"],
                ondelete="SET NULL",
            )

    fin_cols = _column_names(bind, "credit_financial_statements")
    if "import_source" not in fin_cols:
        with op.batch_alter_table("credit_financial_statements", schema=None) as batch_op:
            batch_op.add_column(sa.Column("import_source", sa.String(length=120), nullable=True))


def downgrade():
    bind = op.get_bind()

    if _table_exists(bind, "credit_financial_statements") and "import_source" in _column_names(bind, "credit_financial_statements"):
        with op.batch_alter_table("credit_financial_statements", schema=None) as batch_op:
            batch_op.drop_column("import_source")

    if _table_exists(bind, "credit_financial_statements") and "analyst_function_id" in _column_names(bind, "credit_financial_statements"):
        with op.batch_alter_table("credit_financial_statements", schema=None) as batch_op:
            batch_op.drop_constraint("fk_credit_financial_statements_analyst_function_id", type_="foreignkey")
            batch_op.drop_index("ix_credit_financial_statements_analyst_function_id")
            batch_op.drop_column("analyst_function_id")

    if _table_exists(bind, "credit_financial_statements") and "analyst_user_id" in _column_names(bind, "credit_financial_statements"):
        with op.batch_alter_table("credit_financial_statements", schema=None) as batch_op:
            batch_op.drop_constraint("fk_credit_financial_statements_analyst_user_id", type_="foreignkey")
            batch_op.drop_index("ix_credit_financial_statements_analyst_user_id")
            batch_op.drop_column("analyst_user_id")

    if _table_exists(bind, "credit_financial_statements") and "imported_by_user_id" in _column_names(bind, "credit_financial_statements"):
        with op.batch_alter_table("credit_financial_statements", schema=None) as batch_op:
            batch_op.drop_constraint("fk_credit_financial_statements_imported_by_user_id", type_="foreignkey")
            batch_op.drop_index("ix_credit_financial_statements_imported_by_user_id")
            batch_op.drop_column("imported_by_user_id")

    if _table_exists(bind, "credit_approvals") and "analyst_function_id" in _column_names(bind, "credit_approvals"):
        with op.batch_alter_table("credit_approvals", schema=None) as batch_op:
            batch_op.drop_constraint("fk_credit_approvals_analyst_function_id", type_="foreignkey")
            batch_op.drop_index("ix_credit_approvals_analyst_function_id")
            batch_op.drop_column("analyst_function_id")

    if _table_exists(bind, "credit_approval_workflow_steps") and "function_id" in _column_names(bind, "credit_approval_workflow_steps"):
        with op.batch_alter_table("credit_approval_workflow_steps", schema=None) as batch_op:
            batch_op.drop_constraint("fk_credit_approval_workflow_steps_function_id", type_="foreignkey")
            batch_op.drop_index("ix_credit_approval_workflow_steps_function_id")
            batch_op.drop_column("function_id")

    if _table_exists(bind, "credit_analyst_group_members") and "function_id" in _column_names(bind, "credit_analyst_group_members"):
        with op.batch_alter_table("credit_analyst_group_members", schema=None) as batch_op:
            batch_op.drop_constraint("fk_credit_analyst_group_members_function_id", type_="foreignkey")
            batch_op.drop_index("ix_credit_analyst_group_members_function_id")
            batch_op.drop_column("function_id")

    if _table_exists(bind, "credit_analyst_functions"):
        if "ix_credit_analyst_functions_tenant_id" in _index_names(bind, "credit_analyst_functions"):
            op.drop_index("ix_credit_analyst_functions_tenant_id", table_name="credit_analyst_functions")
        op.drop_table("credit_analyst_functions")

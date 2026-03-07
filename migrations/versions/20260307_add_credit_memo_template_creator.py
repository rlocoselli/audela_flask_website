"""add credit memo template creator tables

Revision ID: 20260307_add_credit_memo_template_creator
Revises: 20260307_add_credit_backlog_tasks_and_roles
Create Date: 2026-03-07
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260307_add_credit_memo_template_creator"
down_revision = "20260307_add_credit_backlog_tasks_and_roles"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def _index_names(bind, table_name: str) -> set[str]:
    return {i["name"] for i in sa.inspect(bind).get_indexes(table_name)}


def upgrade():
    bind = op.get_bind()

    if not _table_exists(bind, "credit_memo_templates"):
        op.create_table(
            "credit_memo_templates",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=180), nullable=False),
            sa.Column("memo_type", sa.String(length=64), nullable=False, server_default="full_credit_memo"),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
            sa.Column("base_template_id", sa.Integer(), nullable=True),
            sa.Column("published_version_no", sa.Integer(), nullable=True),
            sa.Column("is_locked", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("theme_json", sa.JSON(), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
            sa.Column("approved_by_user_id", sa.Integer(), nullable=True),
            sa.Column("published_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["base_template_id"], ["credit_memo_templates.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )

    for idx_name, cols in [
        ("ix_credit_memo_templates_tenant_id", ["tenant_id"]),
        ("ix_credit_memo_templates_memo_type", ["memo_type"]),
        ("ix_credit_memo_templates_status", ["status"]),
    ]:
        if idx_name not in _index_names(bind, "credit_memo_templates"):
            op.create_index(idx_name, "credit_memo_templates", cols)

    if not _table_exists(bind, "credit_memo_template_versions"):
        op.create_table(
            "credit_memo_template_versions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("template_id", sa.Integer(), nullable=False),
            sa.Column("version_no", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
            sa.Column("definition_json", sa.JSON(), nullable=True),
            sa.Column("validation_json", sa.JSON(), nullable=True),
            sa.Column("change_notes", sa.Text(), nullable=True),
            sa.Column("effective_date", sa.Date(), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
            sa.Column("approved_by_user_id", sa.Integer(), nullable=True),
            sa.Column("published_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["template_id"], ["credit_memo_templates.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("template_id", "version_no", name="uq_credit_memo_template_version"),
        )

    for idx_name, cols in [
        ("ix_credit_memo_template_versions_tenant_id", ["tenant_id"]),
        ("ix_credit_memo_template_versions_template_id", ["template_id"]),
        ("ix_credit_memo_template_versions_status", ["status"]),
    ]:
        if idx_name not in _index_names(bind, "credit_memo_template_versions"):
            op.create_index(idx_name, "credit_memo_template_versions", cols)


def downgrade():
    bind = op.get_bind()

    if _table_exists(bind, "credit_memo_template_versions"):
        for idx_name in [
            "ix_credit_memo_template_versions_status",
            "ix_credit_memo_template_versions_template_id",
            "ix_credit_memo_template_versions_tenant_id",
        ]:
            if idx_name in _index_names(bind, "credit_memo_template_versions"):
                op.drop_index(idx_name, table_name="credit_memo_template_versions")
        op.drop_table("credit_memo_template_versions")

    if _table_exists(bind, "credit_memo_templates"):
        for idx_name in [
            "ix_credit_memo_templates_status",
            "ix_credit_memo_templates_memo_type",
            "ix_credit_memo_templates_tenant_id",
        ]:
            if idx_name in _index_names(bind, "credit_memo_templates"):
                op.drop_index(idx_name, table_name="credit_memo_templates")
        op.drop_table("credit_memo_templates")

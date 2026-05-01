"""add public page visits table

Revision ID: 20260502_add_public_page_visits
Revises: 20260421_add_credit_chart_of_accounts
Create Date: 2026-05-02
"""

from alembic import op
import sqlalchemy as sa


revision = "20260502_add_public_page_visits"
down_revision = "20260421_add_credit_chart_of_accounts"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return table_name in insp.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if table_name not in insp.get_table_names():
        return False
    return any(col.get("name") == column_name for col in insp.get_columns(table_name))


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str], unique: bool = False) -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if table_name not in insp.get_table_names():
        return

    existing = [idx["name"] for idx in insp.get_indexes(table_name)]
    if index_name in existing:
        return

    existing_columns = {col.get("name") for col in insp.get_columns(table_name)}
    if not all(col in existing_columns for col in columns):
        return

    op.create_index(index_name, table_name, columns, unique=unique)


def upgrade():
    if not _table_exists("public_page_visits"):
        op.create_table(
            "public_page_visits",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("endpoint", sa.String(length=120), nullable=True),
            sa.Column("path", sa.String(length=255), nullable=False),
            sa.Column("visitor_id", sa.String(length=64), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("ip_hash", sa.String(length=64), nullable=True),
            sa.Column("country_code", sa.String(length=8), nullable=True),
            sa.Column("language_code", sa.String(length=12), nullable=True),
            sa.Column("referrer", sa.String(length=255), nullable=True),
            sa.Column("user_agent", sa.String(length=255), nullable=True),
            sa.Column("utm_source", sa.String(length=120), nullable=True),
            sa.Column("utm_medium", sa.String(length=120), nullable=True),
            sa.Column("utm_campaign", sa.String(length=120), nullable=True),
            sa.Column("is_home", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
    else:
        if not _column_exists("public_page_visits", "country_code"):
            with op.batch_alter_table("public_page_visits", schema=None) as batch_op:
                batch_op.add_column(sa.Column("country_code", sa.String(length=8), nullable=True))
        if not _column_exists("public_page_visits", "language_code"):
            with op.batch_alter_table("public_page_visits", schema=None) as batch_op:
                batch_op.add_column(sa.Column("language_code", sa.String(length=12), nullable=True))

    _create_index_if_missing("ix_public_page_visits_endpoint", "public_page_visits", ["endpoint"])
    _create_index_if_missing("ix_public_page_visits_path", "public_page_visits", ["path"])
    _create_index_if_missing("ix_public_page_visits_visitor_id", "public_page_visits", ["visitor_id"])
    _create_index_if_missing("ix_public_page_visits_user_id", "public_page_visits", ["user_id"])
    _create_index_if_missing("ix_public_page_visits_ip_hash", "public_page_visits", ["ip_hash"])
    _create_index_if_missing("ix_public_page_visits_country_code", "public_page_visits", ["country_code"])
    _create_index_if_missing("ix_public_page_visits_language_code", "public_page_visits", ["language_code"])
    _create_index_if_missing("ix_public_page_visits_is_home", "public_page_visits", ["is_home"])
    _create_index_if_missing("ix_public_page_visits_created_at", "public_page_visits", ["created_at"])


def downgrade():
    if _table_exists("public_page_visits"):
        op.drop_table("public_page_visits")

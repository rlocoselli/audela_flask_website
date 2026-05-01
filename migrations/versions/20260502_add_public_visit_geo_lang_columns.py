"""ensure public visit country/language columns

Revision ID: 20260502_add_public_visit_geo_lang_columns
Revises: 20260502_add_public_page_visits
Create Date: 2026-05-02
"""

from alembic import op
import sqlalchemy as sa


revision = "20260502_add_public_visit_geo_lang_columns"
down_revision = "20260502_add_public_page_visits"
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


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if table_name not in insp.get_table_names():
        return False
    return any(idx.get("name") == index_name for idx in insp.get_indexes(table_name))


def upgrade():
    if not _table_exists("public_page_visits"):
        return

    if not _column_exists("public_page_visits", "country_code"):
        with op.batch_alter_table("public_page_visits", schema=None) as batch_op:
            batch_op.add_column(sa.Column("country_code", sa.String(length=8), nullable=True))

    if not _column_exists("public_page_visits", "language_code"):
        with op.batch_alter_table("public_page_visits", schema=None) as batch_op:
            batch_op.add_column(sa.Column("language_code", sa.String(length=12), nullable=True))

    if not _index_exists("public_page_visits", "ix_public_page_visits_country_code"):
        op.create_index("ix_public_page_visits_country_code", "public_page_visits", ["country_code"], unique=False)

    if not _index_exists("public_page_visits", "ix_public_page_visits_language_code"):
        op.create_index("ix_public_page_visits_language_code", "public_page_visits", ["language_code"], unique=False)


def downgrade():
    if not _table_exists("public_page_visits"):
        return

    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_indexes = {idx.get("name") for idx in insp.get_indexes("public_page_visits")}
    existing_columns = {col.get("name") for col in insp.get_columns("public_page_visits")}

    with op.batch_alter_table("public_page_visits", schema=None) as batch_op:
        if "ix_public_page_visits_country_code" in existing_indexes:
            batch_op.drop_index("ix_public_page_visits_country_code")
        if "ix_public_page_visits_language_code" in existing_indexes:
            batch_op.drop_index("ix_public_page_visits_language_code")
        if "country_code" in existing_columns:
            batch_op.drop_column("country_code")
        if "language_code" in existing_columns:
            batch_op.drop_column("language_code")

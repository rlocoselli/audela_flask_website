"""add multilingual columns to credit reference tables

Revision ID: 20260306_add_credit_reference_i18n_columns
Revises: 20260305_add_credit_reference_tables
Create Date: 2026-03-06
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260306_add_credit_reference_i18n_columns"
down_revision = "20260305_add_credit_reference_tables"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def _column_names(bind, table_name: str) -> set[str]:
    return {c["name"] for c in sa.inspect(bind).get_columns(table_name)}


def _add_column_if_missing(bind, table_name: str, column: sa.Column) -> None:
    if not _table_exists(bind, table_name):
        return
    if column.name in _column_names(bind, table_name):
        return
    with op.batch_alter_table(table_name, schema=None) as batch_op:
        batch_op.add_column(column)


def _drop_column_if_exists(bind, table_name: str, column_name: str) -> None:
    if not _table_exists(bind, table_name):
        return
    if column_name not in _column_names(bind, table_name):
        return
    with op.batch_alter_table(table_name, schema=None) as batch_op:
        batch_op.drop_column(column_name)


def _backfill_from_column(bind, table_name: str, target_column: str, source_column: str) -> None:
    if not _table_exists(bind, table_name):
        return
    columns = _column_names(bind, table_name)
    if target_column not in columns or source_column not in columns:
        return
    bind.execute(
        sa.text(
            f"UPDATE {table_name} "
            f"SET {target_column} = COALESCE({target_column}, {source_column}) "
            f"WHERE {target_column} IS NULL AND {source_column} IS NOT NULL"
        )
    )


def upgrade():
    bind = op.get_bind()

    for lang in ("fr", "en", "pt", "es", "it", "de"):
        _add_column_if_missing(bind, "credit_countries", sa.Column(f"name_{lang}", sa.String(length=120), nullable=True))
        _add_column_if_missing(bind, "credit_sectors", sa.Column(f"name_{lang}", sa.String(length=120), nullable=True))
        _add_column_if_missing(bind, "credit_ratings", sa.Column(f"label_{lang}", sa.String(length=120), nullable=True))
        _add_column_if_missing(bind, "credit_facility_types", sa.Column(f"label_{lang}", sa.String(length=120), nullable=True))
        _add_column_if_missing(bind, "credit_collateral_types", sa.Column(f"label_{lang}", sa.String(length=120), nullable=True))
        _add_column_if_missing(bind, "credit_guarantee_types", sa.Column(f"label_{lang}", sa.String(length=120), nullable=True))

    for lang in ("fr", "en", "pt", "es", "it", "de"):
        _backfill_from_column(bind, "credit_countries", f"name_{lang}", "name")
        _backfill_from_column(bind, "credit_sectors", f"name_{lang}", "name")
        _backfill_from_column(bind, "credit_ratings", f"label_{lang}", "code")
        _backfill_from_column(bind, "credit_facility_types", f"label_{lang}", "label")
        _backfill_from_column(bind, "credit_collateral_types", f"label_{lang}", "label")
        _backfill_from_column(bind, "credit_guarantee_types", f"label_{lang}", "label")


def downgrade():
    bind = op.get_bind()

    for lang in ("fr", "en", "pt", "es", "it", "de"):
        _drop_column_if_exists(bind, "credit_guarantee_types", f"label_{lang}")
        _drop_column_if_exists(bind, "credit_collateral_types", f"label_{lang}")
        _drop_column_if_exists(bind, "credit_facility_types", f"label_{lang}")
        _drop_column_if_exists(bind, "credit_ratings", f"label_{lang}")
        _drop_column_if_exists(bind, "credit_sectors", f"name_{lang}")
        _drop_column_if_exists(bind, "credit_countries", f"name_{lang}")

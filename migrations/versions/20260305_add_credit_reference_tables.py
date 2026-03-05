"""add credit reference tables and foreign keys

Revision ID: 20260305_add_credit_reference_tables
Revises: 20260305_add_credit_module_tables
Create Date: 2026-03-05
"""

from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = "20260305_add_credit_reference_tables"
down_revision = "20260305_add_credit_module_tables"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def _column_names(bind, table_name: str) -> set[str]:
    return {c["name"] for c in sa.inspect(bind).get_columns(table_name)}


def _index_names(bind, table_name: str) -> set[str]:
    return {i["name"] for i in sa.inspect(bind).get_indexes(table_name)}


def _table_empty(bind, table_name: str) -> bool:
    row = bind.execute(sa.text(f"SELECT 1 FROM {table_name} LIMIT 1")).fetchone()
    return row is None


def upgrade():
    bind = op.get_bind()

    if not _table_exists(bind, "credit_countries"):
        op.create_table(
            "credit_countries",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("iso_code", sa.String(length=2), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("iso_code"),
            sa.UniqueConstraint("name"),
        )
    if "ix_credit_countries_iso_code" not in _index_names(bind, "credit_countries"):
        op.create_index("ix_credit_countries_iso_code", "credit_countries", ["iso_code"])

    if not _table_exists(bind, "credit_sectors"):
        op.create_table(
            "credit_sectors",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("code", sa.String(length=32), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("code"),
            sa.UniqueConstraint("name"),
        )
    if "ix_credit_sectors_code" not in _index_names(bind, "credit_sectors"):
        op.create_index("ix_credit_sectors_code", "credit_sectors", ["code"])

    if not _table_exists(bind, "credit_ratings"):
        op.create_table(
            "credit_ratings",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("code", sa.String(length=16), nullable=False),
            sa.Column("rank_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("code"),
        )
    if "ix_credit_ratings_code" not in _index_names(bind, "credit_ratings"):
        op.create_index("ix_credit_ratings_code", "credit_ratings", ["code"])

    if not _table_exists(bind, "credit_facility_types"):
        op.create_table(
            "credit_facility_types",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("code", sa.String(length=32), nullable=False),
            sa.Column("label", sa.String(length=120), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("code"),
        )
    if "ix_credit_facility_types_code" not in _index_names(bind, "credit_facility_types"):
        op.create_index("ix_credit_facility_types_code", "credit_facility_types", ["code"])

    if not _table_exists(bind, "credit_collateral_types"):
        op.create_table(
            "credit_collateral_types",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("code", sa.String(length=32), nullable=False),
            sa.Column("label", sa.String(length=120), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("code"),
        )
    if "ix_credit_collateral_types_code" not in _index_names(bind, "credit_collateral_types"):
        op.create_index("ix_credit_collateral_types_code", "credit_collateral_types", ["code"])

    if not _table_exists(bind, "credit_guarantee_types"):
        op.create_table(
            "credit_guarantee_types",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("code", sa.String(length=32), nullable=False),
            sa.Column("label", sa.String(length=120), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("code"),
        )
    if "ix_credit_guarantee_types_code" not in _index_names(bind, "credit_guarantee_types"):
        op.create_index("ix_credit_guarantee_types_code", "credit_guarantee_types", ["code"])

    borrower_columns = _column_names(bind, "credit_borrowers")
    if "sector_id" not in borrower_columns:
        with op.batch_alter_table("credit_borrowers", schema=None) as batch_op:
            batch_op.add_column(sa.Column("sector_id", sa.Integer(), nullable=True))
            batch_op.create_index("ix_credit_borrowers_sector_id", ["sector_id"], unique=False)
            batch_op.create_foreign_key("fk_credit_borrowers_sector_id", "credit_sectors", ["sector_id"], ["id"], ondelete="SET NULL")
    borrower_columns = _column_names(bind, "credit_borrowers")
    if "country_id" not in borrower_columns:
        with op.batch_alter_table("credit_borrowers", schema=None) as batch_op:
            batch_op.add_column(sa.Column("country_id", sa.Integer(), nullable=True))
            batch_op.create_index("ix_credit_borrowers_country_id", ["country_id"], unique=False)
            batch_op.create_foreign_key("fk_credit_borrowers_country_id", "credit_countries", ["country_id"], ["id"], ondelete="SET NULL")
    borrower_columns = _column_names(bind, "credit_borrowers")
    if "rating_id" not in borrower_columns:
        with op.batch_alter_table("credit_borrowers", schema=None) as batch_op:
            batch_op.add_column(sa.Column("rating_id", sa.Integer(), nullable=True))
            batch_op.create_index("ix_credit_borrowers_rating_id", ["rating_id"], unique=False)
            batch_op.create_foreign_key("fk_credit_borrowers_rating_id", "credit_ratings", ["rating_id"], ["id"], ondelete="SET NULL")

    facilities_columns = _column_names(bind, "credit_facilities")
    if "facility_type_id" not in facilities_columns:
        with op.batch_alter_table("credit_facilities", schema=None) as batch_op:
            batch_op.add_column(sa.Column("facility_type_id", sa.Integer(), nullable=True))
            batch_op.create_index("ix_credit_facilities_facility_type_id", ["facility_type_id"], unique=False)
            batch_op.create_foreign_key("fk_credit_facilities_facility_type_id", "credit_facility_types", ["facility_type_id"], ["id"], ondelete="SET NULL")

    collateral_columns = _column_names(bind, "credit_collaterals")
    if "collateral_type_id" not in collateral_columns:
        with op.batch_alter_table("credit_collaterals", schema=None) as batch_op:
            batch_op.add_column(sa.Column("collateral_type_id", sa.Integer(), nullable=True))
            batch_op.create_index("ix_credit_collaterals_collateral_type_id", ["collateral_type_id"], unique=False)
            batch_op.create_foreign_key("fk_credit_collaterals_collateral_type_id", "credit_collateral_types", ["collateral_type_id"], ["id"], ondelete="SET NULL")

    guarantors_columns = _column_names(bind, "credit_guarantors")
    if "guarantee_type_id" not in guarantors_columns:
        with op.batch_alter_table("credit_guarantors", schema=None) as batch_op:
            batch_op.add_column(sa.Column("guarantee_type_id", sa.Integer(), nullable=True))
            batch_op.create_index("ix_credit_guarantors_guarantee_type_id", ["guarantee_type_id"], unique=False)
            batch_op.create_foreign_key("fk_credit_guarantors_guarantee_type_id", "credit_guarantee_types", ["guarantee_type_id"], ["id"], ondelete="SET NULL")

    countries_tbl = sa.table(
        "credit_countries",
        sa.column("iso_code", sa.String),
        sa.column("name", sa.String),
        sa.column("created_at", sa.DateTime),
    )
    sectors_tbl = sa.table(
        "credit_sectors",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("created_at", sa.DateTime),
    )
    ratings_tbl = sa.table(
        "credit_ratings",
        sa.column("code", sa.String),
        sa.column("rank_order", sa.Integer),
        sa.column("created_at", sa.DateTime),
    )
    facility_types_tbl = sa.table(
        "credit_facility_types",
        sa.column("code", sa.String),
        sa.column("label", sa.String),
        sa.column("created_at", sa.DateTime),
    )
    collateral_types_tbl = sa.table(
        "credit_collateral_types",
        sa.column("code", sa.String),
        sa.column("label", sa.String),
        sa.column("created_at", sa.DateTime),
    )
    guarantee_types_tbl = sa.table(
        "credit_guarantee_types",
        sa.column("code", sa.String),
        sa.column("label", sa.String),
        sa.column("created_at", sa.DateTime),
    )

    if _table_empty(bind, "credit_countries"):
        op.bulk_insert(
            countries_tbl,
            [
                {"iso_code": "FR", "name": "France", "created_at": datetime.utcnow()},
                {"iso_code": "PT", "name": "Portugal", "created_at": datetime.utcnow()},
                {"iso_code": "ES", "name": "Spain", "created_at": datetime.utcnow()},
                {"iso_code": "IT", "name": "Italy", "created_at": datetime.utcnow()},
                {"iso_code": "DE", "name": "Germany", "created_at": datetime.utcnow()},
                {"iso_code": "BE", "name": "Belgium", "created_at": datetime.utcnow()},
                {"iso_code": "CH", "name": "Switzerland", "created_at": datetime.utcnow()},
                {"iso_code": "LU", "name": "Luxembourg", "created_at": datetime.utcnow()},
                {"iso_code": "MA", "name": "Morocco", "created_at": datetime.utcnow()},
                {"iso_code": "SN", "name": "Senegal", "created_at": datetime.utcnow()},
            ],
        )

    if _table_empty(bind, "credit_sectors"):
        op.bulk_insert(
            sectors_tbl,
            [
                {"code": "agri_food", "name": "Agri-food", "created_at": datetime.utcnow()},
                {"code": "transport", "name": "Transport", "created_at": datetime.utcnow()},
                {"code": "hospitality", "name": "Hospitality", "created_at": datetime.utcnow()},
                {"code": "manufacturing", "name": "Manufacturing", "created_at": datetime.utcnow()},
                {"code": "retail", "name": "Retail", "created_at": datetime.utcnow()},
                {"code": "energy", "name": "Energy", "created_at": datetime.utcnow()},
                {"code": "healthcare", "name": "Healthcare", "created_at": datetime.utcnow()},
                {"code": "construction", "name": "Construction", "created_at": datetime.utcnow()},
                {"code": "services", "name": "Services", "created_at": datetime.utcnow()},
                {"code": "technology", "name": "Technology", "created_at": datetime.utcnow()},
            ],
        )

    if _table_empty(bind, "credit_ratings"):
        op.bulk_insert(
            ratings_tbl,
            [
                {"code": "AAA", "rank_order": 1, "created_at": datetime.utcnow()},
                {"code": "AA", "rank_order": 2, "created_at": datetime.utcnow()},
                {"code": "A", "rank_order": 3, "created_at": datetime.utcnow()},
                {"code": "BBB", "rank_order": 4, "created_at": datetime.utcnow()},
                {"code": "BB", "rank_order": 5, "created_at": datetime.utcnow()},
                {"code": "B", "rank_order": 6, "created_at": datetime.utcnow()},
                {"code": "CCC", "rank_order": 7, "created_at": datetime.utcnow()},
            ],
        )

    if _table_empty(bind, "credit_facility_types"):
        op.bulk_insert(
            facility_types_tbl,
            [
                {"code": "term_loan", "label": "Term loan", "created_at": datetime.utcnow()},
                {"code": "revolving_line", "label": "Revolving line", "created_at": datetime.utcnow()},
                {"code": "bridge_loan", "label": "Bridge loan", "created_at": datetime.utcnow()},
                {"code": "capex_lease", "label": "Capex lease", "created_at": datetime.utcnow()},
                {"code": "overdraft", "label": "Overdraft", "created_at": datetime.utcnow()},
            ],
        )

    if _table_empty(bind, "credit_collateral_types"):
        op.bulk_insert(
            collateral_types_tbl,
            [
                {"code": "real_estate", "label": "Real estate", "created_at": datetime.utcnow()},
                {"code": "receivables", "label": "Receivables", "created_at": datetime.utcnow()},
                {"code": "equipment", "label": "Equipment", "created_at": datetime.utcnow()},
                {"code": "cash_pledge", "label": "Cash pledge", "created_at": datetime.utcnow()},
                {"code": "inventory", "label": "Inventory", "created_at": datetime.utcnow()},
                {"code": "other", "label": "Other", "created_at": datetime.utcnow()},
            ],
        )

    if _table_empty(bind, "credit_guarantee_types"):
        op.bulk_insert(
            guarantee_types_tbl,
            [
                {"code": "personal", "label": "Personal guarantee", "created_at": datetime.utcnow()},
                {"code": "corporate", "label": "Corporate guarantee", "created_at": datetime.utcnow()},
                {"code": "joint", "label": "Joint guarantee", "created_at": datetime.utcnow()},
                {"code": "limited", "label": "Limited guarantee", "created_at": datetime.utcnow()},
            ],
        )


def downgrade():
    with op.batch_alter_table("credit_guarantors", schema=None) as batch_op:
        batch_op.drop_constraint("fk_credit_guarantors_guarantee_type_id", type_="foreignkey")
        batch_op.drop_index("ix_credit_guarantors_guarantee_type_id")
        batch_op.drop_column("guarantee_type_id")

    with op.batch_alter_table("credit_collaterals", schema=None) as batch_op:
        batch_op.drop_constraint("fk_credit_collaterals_collateral_type_id", type_="foreignkey")
        batch_op.drop_index("ix_credit_collaterals_collateral_type_id")
        batch_op.drop_column("collateral_type_id")

    with op.batch_alter_table("credit_facilities", schema=None) as batch_op:
        batch_op.drop_constraint("fk_credit_facilities_facility_type_id", type_="foreignkey")
        batch_op.drop_index("ix_credit_facilities_facility_type_id")
        batch_op.drop_column("facility_type_id")

    with op.batch_alter_table("credit_borrowers", schema=None) as batch_op:
        batch_op.drop_constraint("fk_credit_borrowers_rating_id", type_="foreignkey")
        batch_op.drop_constraint("fk_credit_borrowers_country_id", type_="foreignkey")
        batch_op.drop_constraint("fk_credit_borrowers_sector_id", type_="foreignkey")
        batch_op.drop_index("ix_credit_borrowers_rating_id")
        batch_op.drop_index("ix_credit_borrowers_country_id")
        batch_op.drop_index("ix_credit_borrowers_sector_id")
        batch_op.drop_column("rating_id")
        batch_op.drop_column("country_id")
        batch_op.drop_column("sector_id")

    op.drop_index("ix_credit_guarantee_types_code", table_name="credit_guarantee_types")
    op.drop_table("credit_guarantee_types")

    op.drop_index("ix_credit_collateral_types_code", table_name="credit_collateral_types")
    op.drop_table("credit_collateral_types")

    op.drop_index("ix_credit_facility_types_code", table_name="credit_facility_types")
    op.drop_table("credit_facility_types")

    op.drop_index("ix_credit_ratings_code", table_name="credit_ratings")
    op.drop_table("credit_ratings")

    op.drop_index("ix_credit_sectors_code", table_name="credit_sectors")
    op.drop_table("credit_sectors")

    op.drop_index("ix_credit_countries_iso_code", table_name="credit_countries")
    op.drop_table("credit_countries")

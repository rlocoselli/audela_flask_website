"""Add shared_link_uuid to ELearningCertificate

Revision ID: 6a05fa798085
Revises: 20260514_add_quiz_scoring_rules
Create Date: 2026-05-15 07:13:48.787135

"""
from alembic import op
import sqlalchemy as sa
import uuid


# revision identifiers, used by Alembic.
revision = '6a05fa798085'
down_revision = '20260514_add_quiz_scoring_rules'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    columns = {col["name"] for col in inspector.get_columns("e_learning_certificates")}

    # Add column if missing (safe for partially migrated environments).
    if "shared_link_uuid" not in columns:
        with op.batch_alter_table("e_learning_certificates", schema=None) as batch_op:
            batch_op.add_column(sa.Column("shared_link_uuid", sa.String(length=36), nullable=True))

    # Backfill NULL values (existing rows).
    result = connection.execute(
        sa.text("SELECT id FROM e_learning_certificates WHERE shared_link_uuid IS NULL")
    )
    for row in result:
        connection.execute(
            sa.text(
                "UPDATE e_learning_certificates SET shared_link_uuid = :uuid WHERE id = :id"
            ),
            {"uuid": str(uuid.uuid4()), "id": row[0]},
        )

    # Create unique index only if missing.
    indexes = {idx["name"] for idx in inspector.get_indexes("e_learning_certificates")}
    index_name = "ix_e_learning_certificates_shared_link_uuid"
    if index_name not in indexes:
        with op.batch_alter_table("e_learning_certificates", schema=None) as batch_op:
            batch_op.create_index(index_name, ["shared_link_uuid"], unique=True)

    # Enforce NOT NULL after backfill.
    with op.batch_alter_table("e_learning_certificates", schema=None) as batch_op:
        batch_op.alter_column("shared_link_uuid", existing_type=sa.String(length=36), nullable=False)


def downgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    columns = {col["name"] for col in inspector.get_columns("e_learning_certificates")}
    indexes = {idx["name"] for idx in inspector.get_indexes("e_learning_certificates")}
    index_name = "ix_e_learning_certificates_shared_link_uuid"

    with op.batch_alter_table("e_learning_certificates", schema=None) as batch_op:
        if index_name in indexes:
            batch_op.drop_index(index_name)
        if "shared_link_uuid" in columns:
            batch_op.drop_column("shared_link_uuid")

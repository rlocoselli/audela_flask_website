"""add file folders and file assets (uploads)

Revision ID: 20260213_add_file_assets_and_folders
Revises: 20260208_add_reports
Create Date: 2026-02-13

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260213_add_file_assets_and_folders'
down_revision = '20260208_add_reports'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'file_folders',
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_id'], ['file_folders.id'], ondelete='CASCADE'),
    )

    op.create_table(
        'file_assets',
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('folder_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=True),
        sa.Column('source_type', sa.String(length=32), nullable=False, server_default='upload'),
        sa.Column('file_format', sa.String(length=32), nullable=False),
        sa.Column('storage_path', sa.String(length=500), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=True),
        sa.Column('sha256', sa.String(length=64), nullable=True),
        sa.Column('config_encrypted', sa.LargeBinary(), nullable=True),
        sa.Column('schema_json', sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['folder_id'], ['file_folders.id'], ondelete='SET NULL'),
    )


def downgrade():
    op.drop_table('file_assets')
    op.drop_table('file_folders')

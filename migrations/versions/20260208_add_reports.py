"""add reports and report_blocks

Revision ID: 20260208_add_reports
Revises: 20260203_add_dashboards_is_primary
Create Date: 2026-02-08

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260208_add_reports'
down_revision = '20260203_add_dashboards_is_primary'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'reports',
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('layout_json', sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_id'], ['data_sources.id'], ondelete='RESTRICT'),
    )

    op.create_table(
        'report_blocks',
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('report_id', sa.Integer(), nullable=False),
        sa.Column('block_type', sa.String(length=32), nullable=False, server_default='text'),
        sa.Column('question_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(length=200), nullable=True),
        sa.Column('config_json', sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['report_id'], ['reports.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['question_id'], ['questions.id'], ondelete='SET NULL'),
    )

    # indexes
    op.create_index('ix_reports_tenant_id', 'reports', ['tenant_id'])
    op.create_index('ix_report_blocks_tenant_id', 'report_blocks', ['tenant_id'])

    # clean server defaults
    try:
        op.alter_column('reports', 'layout_json', server_default=None)
        op.alter_column('report_blocks', 'config_json', server_default=None)
        op.alter_column('report_blocks', 'block_type', server_default=None)
    except Exception:
        pass


def downgrade():
    try:
        op.drop_index('ix_report_blocks_tenant_id', table_name='report_blocks')
    except Exception:
        pass
    try:
        op.drop_index('ix_reports_tenant_id', table_name='reports')
    except Exception:
        pass

    op.drop_table('report_blocks')
    op.drop_table('reports')

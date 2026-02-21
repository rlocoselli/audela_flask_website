"""add project workspaces table

Revision ID: 20260220_add_project_workspaces
Revises: 20260220_add_subscription_billing
Create Date: 2026-02-20 17:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260220_add_project_workspaces'
down_revision = '20260220_add_subscription_billing'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table('project_workspaces'):
        op.create_table(
            'project_workspaces',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('tenant_id', sa.Integer(), nullable=False),
            sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
            sa.Column('state_json', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['updated_by_user_id'], ['users.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('tenant_id', name='uq_project_workspaces_tenant_id')
        )

    # Safe for PostgreSQL deployments (current target) and avoids duplicate-index failures.
    op.execute(sa.text('CREATE UNIQUE INDEX IF NOT EXISTS ix_project_workspaces_tenant_id ON project_workspaces (tenant_id)'))


def downgrade():
    op.drop_index('ix_project_workspaces_tenant_id', table_name='project_workspaces')
    op.drop_table('project_workspaces')

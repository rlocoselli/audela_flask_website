"""Add subscription and billing tables

Revision ID: 20260220_add_subscription_billing
Revises: 20260218_einvoice_alerts_regulation
Create Date: 2024-02-20 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260220_add_subscription_billing'
down_revision = '20260218_einvoice_alerts_regulation'
branch_labels = None
depends_on = None


def upgrade():
    # Create subscription_plans table
    op.create_table(
        'subscription_plans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('price_monthly', sa.Numeric(10, 2), nullable=False, comment='Prix mensuel en EUR'),
        sa.Column('price_yearly', sa.Numeric(10, 2), nullable=True, comment='Prix annuel en EUR'),
        sa.Column('trial_days', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('has_finance', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('has_bi', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('max_users', sa.Integer(), nullable=False, server_default='1', comment='-1 = illimité'),
        sa.Column('max_companies', sa.Integer(), nullable=False, server_default='1', comment='-1 = illimité'),
        sa.Column('max_transactions_per_month', sa.Integer(), nullable=False, server_default='100', comment='-1 = illimité'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('features_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )
    op.create_index('ix_subscription_plans_is_active', 'subscription_plans', ['is_active'])
    
    # Create tenant_subscriptions table
    op.create_table(
        'tenant_subscriptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('plan_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='trial'),
        sa.Column('trial_start', sa.DateTime(), nullable=True),
        sa.Column('trial_end', sa.DateTime(), nullable=True),
        sa.Column('subscription_start', sa.DateTime(), nullable=True),
        sa.Column('subscription_end', sa.DateTime(), nullable=True),
        sa.Column('billing_cycle', sa.String(20), nullable=True),
        sa.Column('current_users_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('current_companies_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('transactions_this_month', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('stripe_customer_id', sa.String(100), nullable=True),
        sa.Column('stripe_subscription_id', sa.String(100), nullable=True),
        sa.Column('stripe_price_id', sa.String(100), nullable=True),
        sa.Column('last_payment_date', sa.DateTime(), nullable=True),
        sa.Column('next_billing_date', sa.DateTime(), nullable=True),
        sa.Column('cancel_at_period_end', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('cancelled_at', sa.DateTime(), nullable=True),
        sa.Column('cancellation_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['plan_id'], ['subscription_plans.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_tenant_subscriptions_tenant_id', 'tenant_subscriptions', ['tenant_id'])
    op.create_index('ix_tenant_subscriptions_status', 'tenant_subscriptions', ['status'])
    op.create_index('ix_tenant_subscriptions_stripe_customer_id', 'tenant_subscriptions', ['stripe_customer_id'])
    
    # Create email_verification_tokens table
    op.create_table(
        'email_verification_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(100), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token')
    )
    op.create_index('ix_email_verification_tokens_user_id', 'email_verification_tokens', ['user_id'])
    op.create_index('ix_email_verification_tokens_token', 'email_verification_tokens', ['token'])
    
    # Create user_invitations table
    op.create_table(
        'user_invitations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('token', sa.String(100), nullable=False),
        sa.Column('role_codes', postgresql.ARRAY(sa.String(50)), nullable=True),
        sa.Column('invited_by_user_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('accepted_at', sa.DateTime(), nullable=True),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invited_by_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token')
    )
    op.create_index('ix_user_invitations_tenant_id', 'user_invitations', ['tenant_id'])
    op.create_index('ix_user_invitations_email', 'user_invitations', ['email'])
    op.create_index('ix_user_invitations_token', 'user_invitations', ['token'])
    op.create_index('ix_user_invitations_status', 'user_invitations', ['status'])
    
    # Create billing_events table
    op.create_table(
        'billing_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('amount', sa.Numeric(10, 2), nullable=True),
        sa.Column('currency', sa.String(3), nullable=True, server_default='EUR'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('stripe_event_id', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_billing_events_tenant_id', 'billing_events', ['tenant_id'])
    op.create_index('ix_billing_events_event_type', 'billing_events', ['event_type'])
    op.create_index('ix_billing_events_created_at', 'billing_events', ['created_at'])
    
    # Seed default subscription plans
    op.execute("""
        INSERT INTO subscription_plans (code, name, description, price_monthly, price_yearly, trial_days, has_finance, has_bi, max_users, max_companies, max_transactions_per_month, display_order)
        VALUES 
        ('free', 'Gratuit', 'Plan d''essai gratuit de 30 jours', 0, 0, 30, false, false, 1, 1, 100, 1),
        ('finance_starter', 'Finance Starter', 'Gestion financière pour petites entreprises', 29, 290, 30, true, false, 3, 3, 1000, 2),
        ('finance_pro', 'Finance Pro', 'Gestion financière avancée', 79, 790, 30, true, false, 10, 10, 5000, 3),
        ('bi_starter', 'BI Starter', 'Business Intelligence basique', 39, 390, 30, false, true, 3, 5, 1000, 4),
        ('bi_pro', 'BI Pro', 'Business Intelligence avancé', 99, 990, 30, false, true, 10, 20, 10000, 5),
        ('enterprise', 'Enterprise', 'Toutes les fonctionnalités', 199, 1990, 30, true, true, -1, -1, -1, 6)
    """)


def downgrade():
    op.drop_index('ix_billing_events_created_at', 'billing_events')
    op.drop_index('ix_billing_events_event_type', 'billing_events')
    op.drop_index('ix_billing_events_tenant_id', 'billing_events')
    op.drop_table('billing_events')
    
    op.drop_index('ix_user_invitations_status', 'user_invitations')
    op.drop_index('ix_user_invitations_token', 'user_invitations')
    op.drop_index('ix_user_invitations_email', 'user_invitations')
    op.drop_index('ix_user_invitations_tenant_id', 'user_invitations')
    op.drop_table('user_invitations')
    
    op.drop_index('ix_email_verification_tokens_token', 'email_verification_tokens')
    op.drop_index('ix_email_verification_tokens_user_id', 'email_verification_tokens')
    op.drop_table('email_verification_tokens')
    
    op.drop_index('ix_tenant_subscriptions_stripe_customer_id', 'tenant_subscriptions')
    op.drop_index('ix_tenant_subscriptions_status', 'tenant_subscriptions')
    op.drop_index('ix_tenant_subscriptions_tenant_id', 'tenant_subscriptions')
    op.drop_table('tenant_subscriptions')
    
    op.drop_index('ix_subscription_plans_is_active', 'subscription_plans')
    op.drop_table('subscription_plans')

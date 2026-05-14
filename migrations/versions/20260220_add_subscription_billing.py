"""Add subscription and billing tables

Revision ID: 20260220_add_subscription_billing
Revises: 20260218_einvoice_alerts_regulation
Create Date: 2024-02-20 10:00:00.000000

"""
from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260220_add_subscription_billing'
down_revision = '20260218_einvoice_alerts_regulation'
branch_labels = None
depends_on = None


def _table_exists(bind, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def _index_exists(bind, table_name: str, index_name: str) -> bool:
    if not _table_exists(bind, table_name):
        return False
    return any(i["name"] == index_name for i in sa.inspect(bind).get_indexes(table_name))


def _seed_subscription_plans(bind) -> None:
    if not _table_exists(bind, "subscription_plans"):
        return

    plans = sa.table(
        "subscription_plans",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("price_monthly", sa.Numeric),
        sa.column("price_yearly", sa.Numeric),
        sa.column("trial_days", sa.Integer),
        sa.column("has_finance", sa.Boolean),
        sa.column("has_bi", sa.Boolean),
        sa.column("max_users", sa.Integer),
        sa.column("max_companies", sa.Integer),
        sa.column("max_transactions_per_month", sa.Integer),
        sa.column("display_order", sa.Integer),
    )

    existing_codes = {
        row[0]
        for row in bind.execute(sa.select(plans.c.code))
    }

    defaults = [
        {
            "code": "free",
            "name": "Gratuit",
            "description": "Plan d'essai gratuit de 30 jours",
            "price_monthly": 0,
            "price_yearly": 0,
            "trial_days": 30,
            "has_finance": False,
            "has_bi": False,
            "max_users": 1,
            "max_companies": 1,
            "max_transactions_per_month": 100,
            "display_order": 1,
        },
        {
            "code": "finance_starter",
            "name": "Finance Starter",
            "description": "Gestion financiere pour petites entreprises",
            "price_monthly": 29,
            "price_yearly": 290,
            "trial_days": 30,
            "has_finance": True,
            "has_bi": False,
            "max_users": 3,
            "max_companies": 3,
            "max_transactions_per_month": 1000,
            "display_order": 2,
        },
        {
            "code": "finance_pro",
            "name": "Finance Pro",
            "description": "Gestion financiere avancee",
            "price_monthly": 79,
            "price_yearly": 790,
            "trial_days": 30,
            "has_finance": True,
            "has_bi": False,
            "max_users": 10,
            "max_companies": 10,
            "max_transactions_per_month": 5000,
            "display_order": 3,
        },
        {
            "code": "bi_starter",
            "name": "BI Starter",
            "description": "Business Intelligence basique",
            "price_monthly": 39,
            "price_yearly": 390,
            "trial_days": 30,
            "has_finance": False,
            "has_bi": True,
            "max_users": 3,
            "max_companies": 5,
            "max_transactions_per_month": 1000,
            "display_order": 4,
        },
        {
            "code": "bi_pro",
            "name": "BI Pro",
            "description": "Business Intelligence avance",
            "price_monthly": 99,
            "price_yearly": 990,
            "trial_days": 30,
            "has_finance": False,
            "has_bi": True,
            "max_users": 10,
            "max_companies": 20,
            "max_transactions_per_month": 10000,
            "display_order": 5,
        },
        {
            "code": "enterprise",
            "name": "Enterprise",
            "description": "Toutes les fonctionnalites",
            "price_monthly": 199,
            "price_yearly": 1990,
            "trial_days": 30,
            "has_finance": True,
            "has_bi": True,
            "max_users": -1,
            "max_companies": -1,
            "max_transactions_per_month": -1,
            "display_order": 6,
        },
    ]

    for row in defaults:
        if row["code"] not in existing_codes:
            bind.execute(sa.insert(plans).values(**row))


def upgrade():
    bind = op.get_bind()
    dialect_name = context.get_context().dialect.name
    use_sqlite_safe_types = dialect_name == 'sqlite'
    json_type = sa.JSON() if use_sqlite_safe_types else postgresql.JSONB(astext_type=sa.Text())
    role_codes_type = sa.JSON() if use_sqlite_safe_types else postgresql.ARRAY(sa.String(50))

    # Create subscription_plans table
    if not _table_exists(bind, 'subscription_plans'):
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
            sa.Column('features_json', json_type, nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('code')
        )
    if not _index_exists(bind, 'subscription_plans', 'ix_subscription_plans_is_active'):
        op.create_index('ix_subscription_plans_is_active', 'subscription_plans', ['is_active'])
    
    # Create tenant_subscriptions table
    if not _table_exists(bind, 'tenant_subscriptions'):
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
    if not _index_exists(bind, 'tenant_subscriptions', 'ix_tenant_subscriptions_tenant_id'):
        op.create_index('ix_tenant_subscriptions_tenant_id', 'tenant_subscriptions', ['tenant_id'])
    if not _index_exists(bind, 'tenant_subscriptions', 'ix_tenant_subscriptions_status'):
        op.create_index('ix_tenant_subscriptions_status', 'tenant_subscriptions', ['status'])
    if not _index_exists(bind, 'tenant_subscriptions', 'ix_tenant_subscriptions_stripe_customer_id'):
        op.create_index('ix_tenant_subscriptions_stripe_customer_id', 'tenant_subscriptions', ['stripe_customer_id'])
    
    # Create email_verification_tokens table
    if not _table_exists(bind, 'email_verification_tokens'):
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
    if not _index_exists(bind, 'email_verification_tokens', 'ix_email_verification_tokens_user_id'):
        op.create_index('ix_email_verification_tokens_user_id', 'email_verification_tokens', ['user_id'])
    if not _index_exists(bind, 'email_verification_tokens', 'ix_email_verification_tokens_token'):
        op.create_index('ix_email_verification_tokens_token', 'email_verification_tokens', ['token'])
    
    # Create user_invitations table
    if not _table_exists(bind, 'user_invitations'):
        op.create_table(
        'user_invitations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('token', sa.String(100), nullable=False),
        sa.Column('role_codes', role_codes_type, nullable=True),
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
    if not _index_exists(bind, 'user_invitations', 'ix_user_invitations_tenant_id'):
        op.create_index('ix_user_invitations_tenant_id', 'user_invitations', ['tenant_id'])
    if not _index_exists(bind, 'user_invitations', 'ix_user_invitations_email'):
        op.create_index('ix_user_invitations_email', 'user_invitations', ['email'])
    if not _index_exists(bind, 'user_invitations', 'ix_user_invitations_token'):
        op.create_index('ix_user_invitations_token', 'user_invitations', ['token'])
    if not _index_exists(bind, 'user_invitations', 'ix_user_invitations_status'):
        op.create_index('ix_user_invitations_status', 'user_invitations', ['status'])
    
    # Create billing_events table
    if not _table_exists(bind, 'billing_events'):
        op.create_table(
        'billing_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('amount', sa.Numeric(10, 2), nullable=True),
        sa.Column('currency', sa.String(3), nullable=True, server_default='EUR'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('metadata_json', json_type, nullable=True),
        sa.Column('stripe_event_id', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )
    if not _index_exists(bind, 'billing_events', 'ix_billing_events_tenant_id'):
        op.create_index('ix_billing_events_tenant_id', 'billing_events', ['tenant_id'])
    if not _index_exists(bind, 'billing_events', 'ix_billing_events_event_type'):
        op.create_index('ix_billing_events_event_type', 'billing_events', ['event_type'])
    if not _index_exists(bind, 'billing_events', 'ix_billing_events_created_at'):
        op.create_index('ix_billing_events_created_at', 'billing_events', ['created_at'])

    # Seed default subscription plans idempotently.
    _seed_subscription_plans(bind)


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

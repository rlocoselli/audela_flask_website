"""Add finance models: daily balances, adjustments, products, GoCardless integration

Revision ID: 7811fe58d1ac
Revises: 20260218_einvoice_alerts_regulation
Create Date: 2026-02-18 11:38:33.640827

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7811fe58d1ac'
down_revision = '20260218_einvoice_alerts_regulation'
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_index(table_name: str, index_name: str) -> bool:
    indexes = sa.inspect(op.get_bind()).get_indexes(table_name)
    return any(index.get("name") == index_name for index in indexes)


def _create_index_if_missing(index_name: str, table_name: str, columns, unique: bool = False):
    if _has_table(table_name) and not _has_index(table_name, index_name):
        op.create_index(index_name, table_name, columns, unique=unique)


def upgrade():
    # Create finance_products table
    if not _has_table('finance_products'):
        op.create_table('finance_products',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=32), nullable=True),
        sa.Column('name', sa.String(length=160), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('product_type', sa.String(length=24), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=True),
        sa.Column('unit_price', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('currency_code', sa.String(length=8), nullable=False),
        sa.Column('vat_rate', sa.Numeric(precision=9, scale=4), nullable=False),
        sa.Column('vat_applies', sa.Boolean(), nullable=False),
        sa.Column('vat_reverse_charge', sa.Boolean(), nullable=False),
        sa.Column('tax_exempt_reason', sa.String(length=255), nullable=True),
        sa.Column('gl_account_id', sa.Integer(), nullable=True),
        sa.Column('vat_gl_account_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('notes', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['category_id'], ['finance_categories.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['company_id'], ['finance_companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['currency_code'], ['finance_currencies.code'], ),
        sa.ForeignKeyConstraint(['gl_account_id'], ['finance_gl_accounts.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['vat_gl_account_id'], ['finance_gl_accounts.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
        )
    _create_index_if_missing(op.f('ix_finance_products_code'), 'finance_products', ['code'], unique=False)
    _create_index_if_missing(op.f('ix_finance_products_category_id'), 'finance_products', ['category_id'], unique=False)
    _create_index_if_missing(op.f('ix_finance_products_gl_account_id'), 'finance_products', ['gl_account_id'], unique=False)
    _create_index_if_missing(op.f('ix_finance_products_tenant_id'), 'finance_products', ['tenant_id'], unique=False)

    # Create finance_daily_balances table
    if not _has_table('finance_daily_balances'):
        op.create_table('finance_daily_balances',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tenant_id', sa.Integer(), nullable=False),
    sa.Column('company_id', sa.Integer(), nullable=False),
    sa.Column('account_id', sa.Integer(), nullable=False),
    sa.Column('balance_date', sa.Date(), nullable=False),
    sa.Column('opening_balance', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('closing_balance', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('daily_inflow', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('daily_outflow', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('transaction_count', sa.Integer(), nullable=False),
    sa.Column('is_reconciled', sa.Boolean(), nullable=False),
    sa.Column('reconciled_at', sa.DateTime(), nullable=True),
    sa.Column('reconciliation_notes', sa.String(length=500), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['account_id'], ['finance_accounts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['company_id'], ['finance_companies.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    _create_index_if_missing(op.f('ix_finance_daily_balances_account_id'), 'finance_daily_balances', ['account_id'], unique=False)
    _create_index_if_missing(op.f('ix_finance_daily_balances_balance_date'), 'finance_daily_balances', ['balance_date'], unique=False)
    _create_index_if_missing(op.f('ix_finance_daily_balances_tenant_id'), 'finance_daily_balances', ['tenant_id'], unique=False)
    _create_index_if_missing('ix_fin_daily_balance_account_date', 'finance_daily_balances', ['account_id', 'balance_date'], unique=False)

    # Create finance_adjustments table
    if not _has_table('finance_adjustments'):
        op.create_table('finance_adjustments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tenant_id', sa.Integer(), nullable=False),
    sa.Column('company_id', sa.Integer(), nullable=False),
    sa.Column('account_id', sa.Integer(), nullable=False),
    sa.Column('adjustment_date', sa.Date(), nullable=False),
    sa.Column('amount', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('reason', sa.String(length=64), nullable=False),
    sa.Column('description', sa.String(length=300), nullable=True),
    sa.Column('gl_account_id', sa.Integer(), nullable=True),
    sa.Column('category_id', sa.Integer(), nullable=True),
    sa.Column('counterparty_id', sa.Integer(), nullable=True),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('approved_by_user_id', sa.Integer(), nullable=True),
    sa.Column('approved_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['account_id'], ['finance_accounts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['category_id'], ['finance_categories.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['company_id'], ['finance_companies.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['counterparty_id'], ['finance_counterparties.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['gl_account_id'], ['finance_gl_accounts.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    _create_index_if_missing(op.f('ix_finance_adjustments_account_id'), 'finance_adjustments', ['account_id'], unique=False)
    _create_index_if_missing(op.f('ix_finance_adjustments_category_id'), 'finance_adjustments', ['category_id'], unique=False)
    _create_index_if_missing(op.f('ix_finance_adjustments_counterparty_id'), 'finance_adjustments', ['counterparty_id'], unique=False)
    _create_index_if_missing(op.f('ix_finance_adjustments_gl_account_id'), 'finance_adjustments', ['gl_account_id'], unique=False)
    _create_index_if_missing(op.f('ix_finance_adjustments_tenant_id'), 'finance_adjustments', ['tenant_id'], unique=False)

    # Create finance_adjustment_logs table
    if not _has_table('finance_adjustment_logs'):
        op.create_table('finance_adjustment_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tenant_id', sa.Integer(), nullable=False),
    sa.Column('adjustment_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('action', sa.String(length=32), nullable=False),
    sa.Column('previous_values', sa.JSON(), nullable=True),
    sa.Column('new_values', sa.JSON(), nullable=True),
    sa.Column('change_reason', sa.String(length=300), nullable=True),
    sa.Column('ip_address', sa.String(length=45), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['adjustment_id'], ['finance_adjustments.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    _create_index_if_missing(op.f('ix_finance_adjustment_logs_adjustment_id'), 'finance_adjustment_logs', ['adjustment_id'], unique=False)
    _create_index_if_missing(op.f('ix_finance_adjustment_logs_tenant_id'), 'finance_adjustment_logs', ['tenant_id'], unique=False)

    # Create finance_counterparty_attributes table
    if not _has_table('finance_counterparty_attributes'):
        op.create_table('finance_counterparty_attributes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tenant_id', sa.Integer(), nullable=False),
    sa.Column('counterparty_id', sa.Integer(), nullable=False),
    sa.Column('attribute_name', sa.String(length=64), nullable=False),
    sa.Column('attribute_value', sa.String(length=500), nullable=False),
    sa.Column('attribute_type', sa.String(length=32), nullable=False),
    sa.Column('is_custom', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['counterparty_id'], ['finance_counterparties.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    _create_index_if_missing(op.f('ix_finance_counterparty_attributes_counterparty_id'), 'finance_counterparty_attributes', ['counterparty_id'], unique=False)
    _create_index_if_missing(op.f('ix_finance_counterparty_attributes_tenant_id'), 'finance_counterparty_attributes', ['tenant_id'], unique=False)

    # Create finance_gocardless_connections table
    if not _has_table('finance_gocardless_connections'):
        op.create_table('finance_gocardless_connections',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tenant_id', sa.Integer(), nullable=False),
    sa.Column('company_id', sa.Integer(), nullable=False),
    sa.Column('account_id', sa.Integer(), nullable=False),
    sa.Column('gocardless_access_token', sa.LargeBinary(), nullable=True),
    sa.Column('gocardless_secret_id', sa.String(length=120), nullable=True),
    sa.Column('institution_id', sa.String(length=120), nullable=True),
    sa.Column('gocardless_account_id', sa.String(length=120), nullable=True),
    sa.Column('gocardless_account_name', sa.String(length=200), nullable=True),
    sa.Column('iban', sa.String(length=64), nullable=True),
    sa.Column('sync_enabled', sa.Boolean(), nullable=False),
    sa.Column('last_sync_date', sa.DateTime(), nullable=True),
    sa.Column('last_sync_status', sa.String(length=32), nullable=True),
    sa.Column('sync_days_back', sa.Integer(), nullable=False),
    sa.Column('auto_import_enabled', sa.Boolean(), nullable=False),
    sa.Column('auto_create_counterparty', sa.Boolean(), nullable=False),
    sa.Column('auto_categorize', sa.Boolean(), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('status_reason', sa.String(length=300), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['account_id'], ['finance_accounts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['company_id'], ['finance_companies.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    _create_index_if_missing(op.f('ix_finance_gocardless_connections_account_id'), 'finance_gocardless_connections', ['account_id'], unique=False)
    _create_index_if_missing(op.f('ix_finance_gocardless_connections_company_id'), 'finance_gocardless_connections', ['company_id'], unique=False)
    _create_index_if_missing(op.f('ix_finance_gocardless_connections_tenant_id'), 'finance_gocardless_connections', ['tenant_id'], unique=False)

    # Create finance_gocardless_sync_logs table
    if not _has_table('finance_gocardless_sync_logs'):
        op.create_table('finance_gocardless_sync_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tenant_id', sa.Integer(), nullable=False),
    sa.Column('connection_id', sa.Integer(), nullable=False),
    sa.Column('sync_start_date', sa.DateTime(), nullable=False),
    sa.Column('sync_end_date', sa.DateTime(), nullable=True),
    sa.Column('transactions_imported', sa.Integer(), nullable=False),
    sa.Column('transactions_skipped', sa.Integer(), nullable=False),
    sa.Column('transactions_failed', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('error_message', sa.String(length=500), nullable=True),
    sa.Column('sync_metadata', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['connection_id'], ['finance_gocardless_connections.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    _create_index_if_missing(op.f('ix_finance_gocardless_sync_logs_connection_id'), 'finance_gocardless_sync_logs', ['connection_id'], unique=False)
    _create_index_if_missing(op.f('ix_finance_gocardless_sync_logs_tenant_id'), 'finance_gocardless_sync_logs', ['tenant_id'], unique=False)


def downgrade():
    # Drop tables in reverse order (due to foreign key constraints)
    op.drop_table('finance_gocardless_sync_logs')
    op.drop_table('finance_gocardless_connections')
    op.drop_table('finance_counterparty_attributes')
    op.drop_table('finance_adjustment_logs')
    op.drop_table('finance_adjustments')
    op.drop_table('finance_daily_balances')
    op.drop_table('finance_products')

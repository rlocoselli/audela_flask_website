"""
Finance CLI Commands - Configuration d'IBAN et API bancaire

Usage:
    flask finance configure-iban --account-id 1 --iban "FR7620041010050500013M02606"
    flask finance setup-gocardless --account-id 1 --institution SOCIETE_GENERALE --iban "FR76..."
    flask finance get-config --account-id 1
    flask finance validate-iban --iban "FR76..."
"""

import click
from flask.cli import with_appcontext

from audela.models import FinanceAccount, FinanceCompany
from audela.services.bank_configuration_service import (
    BankConfigurationService,
    IBANValidator,
    BalanceUpdateService,
)


@click.group()
def finance():
    """Finance management commands."""
    pass


# ============================================================================
# IBAN Configuration Commands
# ============================================================================

@finance.command('configure-iban')
@click.option('--account-id', type=int, help='Account ID')
@click.option('--company-id', type=int, help='Company ID (alternative to account)')
@click.option('--iban', prompt='Enter IBAN', help='IBAN number')
@with_appcontext
def configure_iban(account_id, company_id, iban):
    """Configure IBAN for an account or company."""
    
    if account_id:
        result = BankConfigurationService.configure_account_iban(account_id, iban)
        click.echo(f"\n{result['message']}")
        if result['status'] == 'success':
            click.secho(f"✓ IBAN: {result['iban']}", fg='green')
        else:
            click.secho(f"✗ Error: {result['message']}", fg='red')
    
    elif company_id:
        result = BankConfigurationService.configure_company_iban(company_id, iban)
        click.echo(f"\n{result['message']}")
        if result['status'] == 'success':
            click.secho(f"✓ IBAN: {result['iban']}", fg='green')
        else:
            click.secho(f"✗ Error: {result['message']}", fg='red')
    
    else:
        click.secho("Error: Provide either --account-id or --company-id", fg='red')


@finance.command('validate-iban')
@click.option('--iban', prompt='Enter IBAN to validate', help='IBAN to validate')
@with_appcontext
def validate_iban(iban):
    """Validate an IBAN number."""
    is_valid, message = IBANValidator.is_valid(iban)
    
    click.echo(f"\nIBAN: {iban}")
    if is_valid:
        click.secho(f"✓ {message}", fg='green')
        click.echo(f"Formatted: {IBANValidator.format_iban(iban)}")
    else:
        click.secho(f"✗ {message}", fg='red')


# ============================================================================
# GoCardless Configuration Commands
# ============================================================================

@finance.command('setup-gocardless')
@click.option('--account-id', type=int, required=True, help='Account ID to link')
@click.option('--company-id', type=int, required=True, help='Company ID')
@click.option('--institution', required=True, help='Institution ID (e.g., SOCIETE_GENERALE_BNAGFRPP)')
@click.option('--iban', prompt='Enter IBAN', help='Bank account IBAN')
@click.option('--access-token', default=None, help='GoCardless access token (optional)')
@click.option('--secret-id', default=None, help='GoCardless secret ID (optional)')
@click.option('--auto-sync', is_flag=True, default=True, help='Enable automatic sync')
@with_appcontext
def setup_gocardless(account_id, company_id, institution, iban, access_token, secret_id, auto_sync):
    """Setup GoCardless connection for automatic bank sync."""
    
    tenant_id = 1  # À adapter selon votre contexte multi-tenant
    
    result = BankConfigurationService.setup_gocardless_connection(
        account_id=account_id,
        company_id=company_id,
        tenant_id=tenant_id,
        institution_id=institution,
        iban=iban,
        access_token=access_token,
        secret_id=secret_id,
        auto_sync=auto_sync,
    )
    
    click.echo(f"\n{result['message']}")
    if result['status'] == 'success':
        click.secho("✓ GoCardless connection configured:", fg='green')
        click.echo(f"  Connection ID: {result['connection_id']}")
        click.echo(f"  IBAN: {result['iban']}")
        click.echo(f"  Institution: {result['institution_id']}")
        click.echo(f"  Auto-sync: {'Enabled' if result['auto_sync'] else 'Disabled'}")
    else:
        click.secho(f"✗ Error: {result['message']}", fg='red')


@finance.command('get-config')
@click.option('--account-id', type=int, required=True, help='Account ID')
@with_appcontext
def get_config(account_id):
    """Get bank configuration for an account."""
    
    result = BankConfigurationService.get_account_configuration(account_id)
    
    if result['status'] == 'success':
        config = result['config']
        click.echo(f"\n📊 Configuration for Account: {config['account_name']}")
        click.echo(f"{'─' * 50}")
        click.echo(f"Account ID:      {config['account_id']}")
        click.echo(f"Type:            {config['account_type']}")
        click.echo(f"Balance:         €{config['current_balance']:.2f}")
        click.echo(f"Currency:        {config['currency']}")
        click.echo(f"IBAN:            {config['iban'] or 'Not configured'}")
        
        if config['gocardless_configured']:
            click.echo(f"\n🏦 GoCardless Configuration:")
            gc = config['gocardless']
            click.echo(f"  Connection ID:    {gc['connection_id']}")
            click.echo(f"  Institution:      {gc['institution_id']}")
            click.echo(f"  IBAN:             {gc['iban']}")
            click.echo(f"  Sync Enabled:     {'Yes' if gc['sync_enabled'] else 'No'}")
            click.echo(f"  Last Sync:        {gc['last_sync'] or 'Never'}")
            click.echo(f"  Auto-import:      {'Yes' if gc['auto_import'] else 'No'}")
            click.echo(f"  Auto-categorize:  {'Yes' if gc['auto_categorize'] else 'No'}")
            click.echo(f"  Status:           {gc['status']}")
        else:
            click.echo(f"\n🏦 GoCardless: Not configured")
    else:
        click.secho(f"✗ Error: {result['message']}", fg='red')


# ============================================================================
# Balance Management Commands
# ============================================================================

@finance.command('recalc-balance')
@click.option('--account-id', type=int, required=True, help='Account ID')
@with_appcontext
def recalculate_balance(account_id):
    """Recalculate account balance from transactions."""
    
    result = BalanceUpdateService.recalculate_account_balance(account_id)
    
    click.echo(f"\n{result['message']}")
    if result['status'] == 'success':
        old = result['old_balance']
        new = result['new_balance']
        diff = new - old
        
        click.secho("✓ Balance recalculated:", fg='green')
        click.echo(f"  Old balance:      €{old:.2f}")
        click.echo(f"  New balance:      €{new:.2f}")
        click.echo(f"  Difference:       €{diff:+.2f}")
        click.echo(f"  Transactions:     {result['total_transactions']}")
    else:
        click.secho(f"✗ Error: {result['message']}", fg='red')


@finance.command('list-accounts')
@click.option('--company-id', type=int, help='Filter by company ID')
@with_appcontext
def list_accounts(company_id):
    """List all finance accounts."""
    
    query = FinanceAccount.query
    if company_id:
        query = query.filter_by(company_id=company_id)
    
    accounts = query.all()
    
    if not accounts:
        click.echo("No accounts found")
        return
    
    click.echo(f"\n{'ID':>3} {'Name':<30} {'Type':<15} {'Balance':>12} {'IBAN':<24}")
    click.echo(f"{'─' * 88}")
    
    for acc in accounts:
        iban_display = acc.iban[:20] + "..." if acc.iban and len(acc.iban) > 20 else acc.iban or "—"
        click.echo(
            f"{acc.id:3d} {acc.name:<30} {acc.account_type:<15} "
            f"€{acc.balance:>10.2f} {iban_display:<24}"
        )


# ============================================================================
# Initialization
# ============================================================================

def init_finance_cli(app):
    """Register finance CLI commands with the Flask app."""
    app.cli.add_command(finance)


if __name__ == '__main__':
    finance()

"""
Exemples d'utilisation des nouveaux modèles de finance.

Ce fichier démontre comment utiliser les 6 nouveaux modèles dans des cas d'usage pratiques.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from audela.models import (
    FinanceAccount,
    FinanceProduct,
    FinanceInvoice,
    FinanceInvoiceLine,
    FinanceAdjustment,
    FinanceAdjustmentLog,
    FinanceDailyBalance,
    FinanceCounterparty,
    FinanceCounterpartyAttribute,
    FinanceGoCardlessConnection,
    FinanceGoCardlessSyncLog,
    FinanceCategory,
)
from audela.services.finance_advanced_service import (
    FinanceVATService,
    FinanceAdjustmentService,
    FinanceDailyBalanceService,
    FinanceGoCardlessService,
)
from audela.extensions import db


# ==============================================================================
# EXEMPLE 1: Gestion des Produits avec TVA Automatique
# ==============================================================================

def example_1_create_products():
    """
    Créer des produits avec configuration TVA différente.
    
    Démontre:
    - Produits taxables (services)
    - Produits exonérés (export)
    - Produits avec reverse charge (B2B/EU)
    """
    print("\n=== EXEMPLE 1: Gestion des Produits ===\n")
    
    # Créer un produit taxable
    service_product = FinanceProduct(
        tenant_id=1,
        company_id=1,
        code="CONSULTANT-001",
        name="Consulting Hour",
        description="Professional consulting service",
        product_type="service",
        unit_price=Decimal("150.00"),
        currency_code="EUR",
        vat_rate=Decimal("20.00"),  # 20% TVA
        vat_applies=True,
        vat_reverse_charge=False,
        status="active",
    )
    db.session.add(service_product)
    db.session.flush()
    
    print(f"✓ Created taxable product: {service_product.name}")
    print(f"  TVA Rate: {service_product.vat_rate}%")
    print(f"  Unit Price: €{service_product.unit_price}")
    
    # Créer un produit exempté de TVA (export)
    export_product = FinanceProduct(
        tenant_id=1,
        company_id=1,
        code="EXPORT-001",
        name="Export Goods",
        product_type="good",
        unit_price=Decimal("1000.00"),
        currency_code="EUR",
        vat_rate=Decimal("0.00"),
        vat_applies=False,
        vat_reverse_charge=False,
        tax_exempt_reason="export",
        status="active",
    )
    db.session.add(export_product)
    db.session.flush()
    
    print(f"\n✓ Created tax-exempt product: {export_product.name}")
    print(f"  VAT Applies: {export_product.vat_applies}")
    print(f"  Reason: {export_product.tax_exempt_reason}")
    
    # Créer un produit avec reverse charge (B2B EU)
    eu_product = FinanceProduct(
        tenant_id=1,
        company_id=1,
        code="EU-B2B-001",
        name="Digital Service EU",
        product_type="digital",
        unit_price=Decimal("500.00"),
        currency_code="EUR",
        vat_rate=Decimal("0.00"),  # TVA acquéreur
        vat_applies=False,
        vat_reverse_charge=True,  # Reverse charge
        status="active",
    )
    db.session.add(eu_product)
    db.session.commit()
    
    print(f"\n✓ Created reverse-charge product: {eu_product.name}")
    print(f"  Reverse Charge: {eu_product.vat_reverse_charge}")
    print(f"  (Customer responsible for VAT)")
    
    return service_product, export_product, eu_product


# ==============================================================================
# EXEMPLE 2: Ajustements avec Audit Complet
# ==============================================================================

def example_2_adjustments_with_audit():
    """
    Créer et approuver des ajustements avec traçabilité complète.
    
    Démontre:
    - Création d'ajustements (frais bancaires, intérêts)
    - Workflow d'approbation
    - Audit complet des modifications
    """
    print("\n=== EXEMPLE 2: Ajustements avec Audit ===\n")
    
    # Obtenir un compte de test
    account = FinanceAccount.query.first()
    if not account:
        print("No account found - skipping example")
        return
    
    # Créer un ajustement de frais bancaires
    adjustment = FinanceAdjustmentService.create_adjustment(
        account_id=account.id,
        amount=Decimal("-15.50"),
        reason="fee",
        description="Monthly banking maintenance fee from ABC Bank",
        user_id=1,
        ip_address="192.168.1.100",
    )
    
    print(f"✓ Created adjustment (PENDING):")
    print(f"  ID: {adjustment.id}")
    print(f"  Amount: €{adjustment.amount}")
    print(f"  Reason: {adjustment.reason}")
    print(f"  Status: {adjustment.status}")
    
    # Afficher le log de création
    logs = FinanceAdjustmentService.get_audit_trail(adjustment.id)
    print(f"\n  Audit Log (Creation):")
    for log in logs:
        print(f"    - {log.action.upper()} by user {log.user_id}")
        print(f"      From IP: {log.ip_address}")
        print(f"      At: {log.created_at}")
    
    # Approuver l'ajustement
    print(f"\n  → Approving adjustment...")
    approved = FinanceAdjustmentService.approve_adjustment(
        adjustment.id,
        approved_by_user_id=2,
        ip_address="192.168.1.200",
    )
    
    print(f"\n✓ Adjustment APPROVED:")
    print(f"  Status: {approved.status}")
    print(f"  Approved by user: {approved.approved_by_user_id}")
    print(f"  Approved at: {approved.approved_at}")
    
    # Afficher l'historique complet
    logs = FinanceAdjustmentService.get_audit_trail(adjustment.id)
    print(f"\n  Complete Audit Trail ({len(logs)} entries):")
    for i, log in enumerate(logs, 1):
        print(f"    {i}. {log.action.upper()}: {log.created_at}")
        if log.change_reason:
            print(f"       Reason: {log.change_reason}")


# ==============================================================================
# EXEMPLE 3: Suivi des Soldes Quotidiens
# ==============================================================================

def example_3_daily_balances():
    """
    Enregistrer et analyser les soldes quotidiens.
    
    Démontre:
    - Enregistrement des soldes quotidiens
    - Requête historique des 30 derniers jours
    - Calcul des tendances
    """
    print("\n=== EXEMPLE 3: Suivi des Soldes Quotidiens ===\n")
    
    # Obtenir un compte de test
    account = FinanceAccount.query.first()
    if not account:
        print("No account found - skipping example")
        return
    
    company_id = account.company_id
    tenant_id = 1
    
    # Créer les soldes des 30 derniers jours
    print("Recording daily balances for the last 30 days...")
    for i in range(30):
        balance_date = date.today() - timedelta(days=29-i)
        
        daily = FinanceDailyBalance(
            tenant_id=tenant_id,
            company_id=company_id,
            account_id=account.id,
            balance_date=balance_date,
            opening_balance=Decimal("1000.00") + (i * Decimal("50.00")),
            closing_balance=Decimal("1050.00") + (i * Decimal("50.00")),
            daily_inflow=Decimal("500.00") if i % 3 == 0 else Decimal("0.00"),
            daily_outflow=Decimal("100.00") if i % 2 == 0 else Decimal("0.00"),
            transaction_count=3 if i % 2 == 0 else 0,
            is_reconciled=i % 2 == 0,
        )
        db.session.add(daily)
    
    db.session.commit()
    print("✓ Created 30 daily balance records")
    
    # Analyser les tendances
    balances = FinanceDailyBalanceService.get_balance_history(
        account.id,
        date.today() - timedelta(days=30),
        date.today()
    )
    
    print(f"\n✓ Balance History Analysis:")
    print(f"  Total days tracked: {len(balances)}")
    
    if balances:
        opening = balances[0].opening_balance
        closing = balances[-1].closing_balance
        change = closing - opening
        
        print(f"  Opening balance (30 days ago): €{opening}")
        print(f"  Closing balance (today): €{closing}")
        print(f"  Change: €{change}")
        print(f"  Trend: {'↗ UP' if change > 0 else '↘ DOWN'}")
        
        # Jours réconciliés
        reconciled = sum(1 for b in balances if b.is_reconciled)
        print(f"\n  Reconciliation Status: {reconciled}/{len(balances)} days reconciled")
    
    # Afficher les derniers jours
    print(f"\n  Last 5 Days:")
    for balance in balances[-5:]:
        status = "✓" if balance.is_reconciled else "✗"
        print(f"    {status} {balance.balance_date}: "
              f"€{balance.opening_balance} → €{balance.closing_balance} "
              f"(Δ€{balance.closing_balance - balance.opening_balance})")


# ==============================================================================
# EXEMPLE 4: Attributs Flexibles pour Contreparties
# ==============================================================================

def example_4_counterparty_attributes():
    """
    Enrichir les contreparties avec des attributs personnalisés.
    
    Démontre:
    - Ajouter des attributs flexibles
    - Stocker différents types (string, number, date, json)
    - Interroger les attributs
    """
    print("\n=== EXEMPLE 4: Attributs Flexibles pour Contreparties ===\n")
    
    # Créer une contrepartie (fournisseur)
    supplier = FinanceCounterparty(
        tenant_id=1,
        name="Premium Supplier Inc.",
        kind="supplier",
        default_currency="EUR",
        email="contact@supplier.com",
        country_code="DE",
    )
    db.session.add(supplier)
    db.session.flush()
    
    print(f"✓ Created counterparty: {supplier.name}")
    
    # Ajouter des attributs personnalisés
    print(f"\n  Adding flexible attributes:")
    
    # Conditions de paiement
    attr_terms = FinanceCounterpartyAttribute(
        tenant_id=supplier.tenant_id,
        counterparty_id=supplier.id,
        attribute_name="payment_terms",
        attribute_value="Net 30",
        attribute_type="string",
    )
    db.session.add(attr_terms)
    print(f"    ✓ Payment terms: Net 30")
    
    # Limite de crédit
    attr_credit = FinanceCounterpartyAttribute(
        tenant_id=supplier.tenant_id,
        counterparty_id=supplier.id,
        attribute_name="credit_limit",
        attribute_value="100000",
        attribute_type="number",
    )
    db.session.add(attr_credit)
    print(f"    ✓ Credit limit: €100,000")
    
    # Dernière commande
    attr_last_order = FinanceCounterpartyAttribute(
        tenant_id=supplier.tenant_id,
        counterparty_id=supplier.id,
        attribute_name="last_order_date",
        attribute_value=str(date.today() - timedelta(days=10)),
        attribute_type="date",
    )
    db.session.add(attr_last_order)
    print(f"    ✓ Last order: 10 days ago")
    
    # Contact personne (JSON)
    attr_contact = FinanceCounterpartyAttribute(
        tenant_id=supplier.tenant_id,
        counterparty_id=supplier.id,
        attribute_name="primary_contact",
        attribute_value='{"name": "John Doe", "email": "john@supplier.com", "phone": "+49-1234-5678"}',
        attribute_type="json",
    )
    db.session.add(attr_contact)
    print(f"    ✓ Primary contact: John Doe")
    
    db.session.commit()
    
    # Afficher tous les attributs
    print(f"\n  All Attributes:")
    for attr in supplier.attributes:
        print(f"    • {attr.attribute_name}: {attr.attribute_value} ({attr.attribute_type})")


# ==============================================================================
# EXEMPLE 5: Intégration GoCardless (Banque)
# ==============================================================================

def example_5_gocardless_integration():
    """
    Configurer et gérer l'intégration GoCardless.
    
    Démontre:
    - Créer une connexion GoCardless
    - Configurer la synchronisation automatique
    - Afficher l'historique des syncs
    """
    print("\n=== EXEMPLE 5: Intégration GoCardless (Banque) ===\n")
    
    # Obtenir un compte de test
    account = FinanceAccount.query.first()
    if not account:
        print("No account found - skipping example")
        return
    
    company_id = account.company_id
    tenant_id = 1
    
    # Créer une connexion GoCardless
    connection = FinanceGoCardlessService.create_connection(
        account_id=account.id,
        company_id=company_id,
        tenant_id=tenant_id,
        institution_id="SOCIETE_GENERALE_WGIVFR22",  # BIC Société Générale
        iban="FR7620041010050500013M02606",
    )
    
    print(f"✓ GoCardless Connection Created:")
    print(f"  ID: {connection.id}")
    print(f"  Institution: {connection.institution_id}")
    print(f"  IBAN: {connection.iban}")
    print(f"  Status: {connection.status}")
    print(f"  Auto-sync enabled: {connection.sync_enabled}")
    print(f"  Auto-import enabled: {connection.auto_import_enabled}")
    print(f"  Auto-categorize enabled: {connection.auto_categorize}")
    
    # Simuler plusieurs synchronisations
    print(f"\n  Simulating synchronizations:")
    for i in range(5):
        sync_log = FinanceGoCardlessService.sync_transactions(connection.id)
        print(f"    ✓ Sync #{i+1}: {sync_log.status.upper()}")
        if i == 0:
            print(f"      (In production: imports from GoCardless API)")
    
    # Afficher l'historique
    history = FinanceGoCardlessService.get_sync_history(connection.id, limit=5)
    print(f"\n  Sync History (last {len(history)} syncs):")
    for i, log in enumerate(history, 1):
        print(f"    {i}. {log.created_at.strftime('%Y-%m-%d %H:%M')} - "
              f"{log.status.upper()} "
              f"({log.transactions_imported} imported)")


# ==============================================================================
# EXEMPLE 6: Application Automatique de TVA sur Facture
# ==============================================================================

def example_6_automatic_vat_on_invoice():
    """
    Appliquer automatiquement la TVA sur une facture.
    
    Démontre:
    - Utiliser la configuration TVA du produit
    - Calculer automatiquement TVA et montant HT
    - Mettre à jour la facture
    """
    print("\n=== EXEMPLE 6: Application Automatique de TVA ===\n")
    
    # Créer des produits
    product_20 = FinanceProduct(
        tenant_id=1,
        company_id=1,
        code="STANDARD",
        name="Standard Service",
        product_type="service",
        unit_price=Decimal("100.00"),
        currency_code="EUR",
        vat_rate=Decimal("20.00"),
        vat_applies=True,
    )
    
    product_exempt = FinanceProduct(
        tenant_id=1,
        company_id=1,
        code="EXPORT",
        name="Export Service",
        product_type="service",
        unit_price=Decimal("100.00"),
        currency_code="EUR",
        vat_rate=Decimal("0.00"),
        vat_applies=False,
        tax_exempt_reason="export",
    )
    
    db.session.add_all([product_20, product_exempt])
    db.session.commit()
    
    print("✓ Created test products")
    
    # Créer une facture (simplifié - voir schema FinanceInvoice réel)
    print("\n  Calculating VAT for invoice lines:")
    
    # Ligne 1: Produit à 20% TVA
    amount_1 = Decimal("100.00")
    vat_1 = amount_1 * (Decimal("20") / Decimal("100"))
    total_1 = amount_1 + vat_1
    
    print(f"    Line 1: {product_20.name}")
    print(f"      Amount HT: €{amount_1}")
    print(f"      VAT (20%): €{vat_1}")
    print(f"      Total TTC: €{total_1}")
    
    # Ligne 2: Produit exempt
    amount_2 = Decimal("50.00")
    vat_2 = Decimal("0.00")
    total_2 = amount_2 + vat_2
    
    print(f"\n    Line 2: {product_exempt.name}")
    print(f"      Amount HT: €{amount_2}")
    print(f"      VAT (0% - exempt): €{vat_2}")
    print(f"      Total TTC: €{total_2}")
    
    # Résumé facture
    total_ht = amount_1 + amount_2
    total_vat = vat_1 + vat_2
    total_ttc = total_1 + total_2
    
    print(f"\n  Invoice Summary:")
    print(f"    Total HT: €{total_ht}")
    print(f"    Total VAT: €{total_vat}")
    print(f"    Total TTC: €{total_ttc}")


# ==============================================================================
# Main - Exécuter tous les exemples
# ==============================================================================

def main():
    """Exécuter tous les exemples."""
    print("\n" + "="*70)
    print("FINANCE MODELS - USAGE EXAMPLES")
    print("="*70)
    
    try:
        example_1_create_products()
    except Exception as e:
        print(f"⚠ Example 1 error: {e}")
    
    try:
        example_2_adjustments_with_audit()
    except Exception as e:
        print(f"⚠ Example 2 error: {e}")
    
    try:
        example_3_daily_balances()
    except Exception as e:
        print(f"⚠ Example 3 error: {e}")
    
    try:
        example_4_counterparty_attributes()
    except Exception as e:
        print(f"⚠ Example 4 error: {e}")
    
    try:
        example_5_gocardless_integration()
    except Exception as e:
        print(f"⚠ Example 5 error: {e}")
    
    try:
        example_6_automatic_vat_on_invoice()
    except Exception as e:
        print(f"⚠ Example 6 error: {e}")
    
    print("\n" + "="*70)
    print("EXAMPLES COMPLETED")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()

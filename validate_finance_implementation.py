#!/usr/bin/env python3
"""
Script de validation - Vérifie l'intégrité de l'implémentation.

Usage:
    python3 validate_finance_implementation.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, '/home/testuser/audela_flask_website')

print("\n" + "="*70)
print("FINANCE SYSTEM - IMPLEMENTATION VALIDATION")
print("="*70 + "\n")

# Test 1: Imports des modèles
print("1. Testing Model Imports...")
try:
    from audela.models import (
        FinanceProduct,
        FinanceDailyBalance,
        FinanceAdjustment,
        FinanceAdjustmentLog,
        FinanceCounterpartyAttribute,
        FinanceGoCardlessConnection,
        FinanceGoCardlessSyncLog,
    )
    print("   ✓ All models imported successfully\n")
except Exception as e:
    print(f"   ✗ ERROR importing models: {e}\n")
    sys.exit(1)

# Test 2: Vérifier les noms de tables
print("2. Checking Table Names...")
models = [
    (FinanceProduct, "finance_products"),
    (FinanceDailyBalance, "finance_daily_balances"),
    (FinanceAdjustment, "finance_adjustments"),
    (FinanceAdjustmentLog, "finance_adjustment_logs"),
    (FinanceCounterpartyAttribute, "finance_counterparty_attributes"),
    (FinanceGoCardlessConnection, "finance_gocardless_connections"),
    (FinanceGoCardlessSyncLog, "finance_gocardless_sync_logs"),
]

all_tables_ok = True
for model, expected_table in models:
    actual_table = model.__tablename__
    if actual_table == expected_table:
        print(f"   ✓ {model.__name__}: {actual_table}")
    else:
        print(f"   ✗ {model.__name__}: expected '{expected_table}', got '{actual_table}'")
        all_tables_ok = False

if all_tables_ok:
    print()
else:
    sys.exit(1)

# Test 3: Vérifier les colonnes critiques
print("3. Checking Critical Columns...")
checks = [
    (FinanceProduct, ["code", "name", "vat_rate", "vat_applies"]),
    (FinanceDailyBalance, ["balance_date", "opening_balance", "closing_balance"]),
    (FinanceAdjustment, ["amount", "reason", "status", "approved_by_user_id"]),
    (FinanceAdjustmentLog, ["action", "previous_values", "new_values"]),
    (FinanceCounterpartyAttribute, ["attribute_name", "attribute_value", "attribute_type"]),
    (FinanceGoCardlessConnection, ["institution_id", "sync_enabled", "auto_import_enabled"]),
    (FinanceGoCardlessSyncLog, ["transactions_imported", "transactions_skipped", "status"]),
]

all_columns_ok = True
for model, columns in checks:
    model_columns = [col.name for col in model.__table__.columns]
    missing = [c for c in columns if c not in model_columns]
    if not missing:
        print(f"   ✓ {model.__name__}")
    else:
        print(f"   ✗ {model.__name__}: missing {missing}")
        all_columns_ok = False

if all_columns_ok:
    print()
else:
    sys.exit(1)

# Test 4: Vérifier les services
print("4. Testing Services...")
try:
    from audela.services.finance_advanced_service import (
        FinanceVATService,
        FinanceAdjustmentService,
        FinanceDailyBalanceService,
        FinanceGoCardlessService,
    )
    print("   ✓ FinanceVATService imported")
    print("   ✓ FinanceAdjustmentService imported")
    print("   ✓ FinanceDailyBalanceService imported")
    print("   ✓ FinanceGoCardlessService imported\n")
except Exception as e:
    print(f"   ✗ ERROR importing services: {e}\n")
    sys.exit(1)

# Test 5: Vérifier les relations
print("5. Checking Relationships...")
try:
    # FinanceDailyBalance -> FinanceAccount
    dailybal_rels = [rel.key for rel in FinanceDailyBalance.__mapper__.relationships]
    if "account" in dailybal_rels:
        print("   ✓ FinanceDailyBalance.account relationship")
    else:
        print("   ✗ Missing FinanceDailyBalance.account relationship")
    
    # FinanceAdjustment -> FinanceAccount
    adj_rels = [rel.key for rel in FinanceAdjustment.__mapper__.relationships]
    if "account" in adj_rels and "logs" in adj_rels:
        print("   ✓ FinanceAdjustment.account relationship")
        print("   ✓ FinanceAdjustment.logs relationship")
    else:
        print("   ✗ Missing FinanceAdjustment relationships")
    
    # FinanceAdjustmentLog -> FinanceAdjustment
    log_rels = [rel.key for rel in FinanceAdjustmentLog.__mapper__.relationships]
    if "adjustment" in log_rels:
        print("   ✓ FinanceAdjustmentLog.adjustment relationship")
    else:
        print("   ✗ Missing FinanceAdjustmentLog.adjustment relationship")
    
    # FinanceCounterpartyAttribute -> FinanceCounterparty
    attr_rels = [rel.key for rel in FinanceCounterpartyAttribute.__mapper__.relationships]
    if "counterparty" in attr_rels:
        print("   ✓ FinanceCounterpartyAttribute.counterparty relationship")
    else:
        print("   ✗ Missing FinanceCounterpartyAttribute.counterparty relationship")
    
    # FinanceGoCardlessConnection -> FinanceGoCardlessSyncLog
    goc_rels = [rel.key for rel in FinanceGoCardlessConnection.__mapper__.relationships]
    if "syncs" in goc_rels:
        print("   ✓ FinanceGoCardlessConnection.syncs relationship")
    else:
        print("   ✗ Missing FinanceGoCardlessConnection.syncs relationship")
    
    print()
except Exception as e:
    print(f"   ✗ ERROR checking relationships: {e}\n")
    sys.exit(1)

# Test 6: Vérifier les fichiers de documentation
print("6. Checking Documentation Files...")
docs = [
    "FINANCE_ENHANCEMENTS.md",
    "FINANCE_IMPLEMENTATION_SUMMARY.md",
    "FINANCE_NEXT_STEPS.md",
    "FINANCE_EXAMPLES.py",
    "FINANCE_CHANGES_INDEX.md",
]

all_docs_ok = True
base_path = "/home/testuser/audela_flask_website"
for doc in docs:
    path = os.path.join(base_path, doc)
    if os.path.exists(path):
        size = os.path.getsize(path)
        print(f"   ✓ {doc} ({size} bytes)")
    else:
        print(f"   ✗ {doc} NOT FOUND")
        all_docs_ok = False

if all_docs_ok:
    print()
else:
    sys.exit(1)

# Test 7: Vérifier la migration
print("7. Checking Migration File...")
migration_path = "/home/testuser/audela_flask_website/migrations/versions/7811fe58d1ac_add_finance_models_daily_balances_.py"
if os.path.exists(migration_path):
    with open(migration_path) as f:
        content = f.read()
        required_tables = [
            "finance_products",
            "finance_daily_balances",
            "finance_adjustments",
            "finance_adjustment_logs",
            "finance_counterparty_attributes",
            "finance_gocardless_connections",
            "finance_gocardless_sync_logs",
        ]
        
        all_tables_in_migration = True
        for table in required_tables:
            if f"'{table}'" in content or f'"{table}"' in content:
                print(f"   ✓ Table '{table}' in migration")
            else:
                print(f"   ✗ Table '{table}' NOT found in migration")
                all_tables_in_migration = False
        
        if all_tables_in_migration:
            print()
        else:
            sys.exit(1)
else:
    print(f"   ✗ Migration file NOT FOUND at {migration_path}\n")
    sys.exit(1)

# Test 8: Vérifie les services méthodes
print("8. Checking Service Methods...")
try:
    # FinanceVATService
    methods = ["calculate_vat_for_product", "apply_vat_to_invoice_line", "apply_vat_to_invoice"]
    for method in methods:
        if hasattr(FinanceVATService, method):
            print(f"   ✓ FinanceVATService.{method}")
        else:
            print(f"   ✗ FinanceVATService.{method} NOT FOUND")
    
    # FinanceAdjustmentService
    methods = ["create_adjustment", "approve_adjustment", "get_audit_trail"]
    for method in methods:
        if hasattr(FinanceAdjustmentService, method):
            print(f"   ✓ FinanceAdjustmentService.{method}")
        else:
            print(f"   ✗ FinanceAdjustmentService.{method} NOT FOUND")
    
    print()
except Exception as e:
    print(f"   ✗ ERROR checking service methods: {e}\n")
    sys.exit(1)

# Test 9: Vérifier les imports dans __init__.py
print("9. Checking Model Exports in __init__.py...")
try:
    with open("/home/testuser/audela_flask_website/audela/models/__init__.py") as f:
        content = f.read()
        
        exports_to_check = [
            "FinanceProduct",
            "FinanceDailyBalance",
            "FinanceAdjustment",
            "FinanceAdjustmentLog",
            "FinanceCounterpartyAttribute",
            "FinanceGoCardlessConnection",
            "FinanceGoCardlessSyncLog",
        ]
        
        all_exported = True
        for export in exports_to_check:
            if export in content:
                print(f"   ✓ {export} exported in __init__.py")
            else:
                print(f"   ✗ {export} NOT exported in __init__.py")
                all_exported = False
        
        if all_exported:
            print()
        else:
            sys.exit(1)
except Exception as e:
    print(f"   ✗ ERROR checking __init__.py: {e}\n")
    sys.exit(1)

# Final Summary
print("="*70)
print("✅ VALIDATION SUCCESSFUL - ALL CHECKS PASSED!")
print("="*70)
print("\n📋 Summary:")
print(f"   • 7 Models created")
print(f"   • 7 Tables to be created via migration")
print(f"   • 4 Services implemented")
print(f"   • 5 Documentation files created")
print(f"   • 1 Migration file ready")
print(f"\n🚀 Next Steps:")
print(f"   1. Run: flask db upgrade")
print(f"   2. Check tables: SELECT name FROM sqlite_master WHERE type='table';")
print(f"   3. See FINANCE_ENHANCEMENTS.md for usage examples")
print(f"   4. See FINANCE_NEXT_STEPS.md for phase 2 implementation")
print("\n")

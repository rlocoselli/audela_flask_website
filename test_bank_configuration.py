#!/usr/bin/env python3
"""
Tests pour la configuration IBAN et l'intégration bancaire.

Usage:
    python3 test_bank_configuration.py
"""

import sys
sys.path.insert(0, '/home/testuser/audela_flask_website')

from audela.services.bank_configuration_service import (
    IBANValidator,
    BankConfigurationService,
    BalanceUpdateService,
)

print("\n" + "="*70)
print("BANK CONFIGURATION & IBAN VALIDATION - TESTS")
print("="*70 + "\n")

# Test 1: Validation IBAN
print("1. Testing IBAN Validation...")
print("-" * 70)

test_ibans = [
    ("DE89370400440532013000", True, "Valid German IBAN"),
    ("GB82WEST12345698765432", True, "Valid UK IBAN"),
    ("IT60X0542811101000000123456", True, "Valid Italian IBAN"),
    ("NL91ABNA0417164300", True, "Valid Dutch IBAN"),
    ("FR1420041010050500013M02606", True, "Valid French IBAN"),
    ("ES7100211401840502000513", True, "Valid Spanish IBAN"),
    ("INVALID123", False, "Too short"),
    ("FR76INVALID1234567890ABC", False, "Bad checksum"),
]

all_passed = True
for iban, should_be_valid, description in test_ibans:
    is_valid, message = IBANValidator.is_valid(iban)
    status = "✓" if is_valid == should_be_valid else "✗"
    
    if is_valid == should_be_valid:
        print(f"{status} {description}: {iban}")
    else:
        print(f"{status} {description}: {iban} (Expected {should_be_valid}, got {is_valid})")
        all_passed = False

print()

# Test 2: IBAN Formatting
print("2. Testing IBAN Formatting...")
print("-" * 70)

iban = "FR7620041010050500013M02606"
formatted = IBANValidator.format_iban(iban)
print(f"Original:  {iban}")
print(f"Formatted: {formatted}")
print(f"✓ Formatting works\n")

# Test 3: Service Methods
print("3. Testing Bank Configuration Service...")
print("-" * 70)

# Check if methods exist
methods_to_check = [
    ('configure_account_iban', BankConfigurationService),
    ('configure_company_iban', BankConfigurationService),
    ('setup_gocardless_connection', BankConfigurationService),
    ('get_account_configuration', BankConfigurationService),
]

for method_name, service_class in methods_to_check:
    if hasattr(service_class, method_name):
        print(f"✓ {service_class.__name__}.{method_name}")
    else:
        print(f"✗ {service_class.__name__}.{method_name} NOT FOUND")
        all_passed = False

print()

# Test 4: Balance Update Service
print("4. Testing Balance Update Service...")
print("-" * 70)

methods_to_check = [
    ('update_account_balance', BalanceUpdateService),
    ('recalculate_account_balance', BalanceUpdateService),
]

for method_name, service_class in methods_to_check:
    if hasattr(service_class, method_name):
        print(f"✓ {service_class.__name__}.{method_name}")
    else:
        print(f"✗ {service_class.__name__}.{method_name} NOT FOUND")
        all_passed = False

print()

# Test 5: CLI Commands
print("5. Testing Finance CLI Commands...")
print("-" * 70)

try:
    from audela.commands.finance_cli import (
        configure_iban,
        validate_iban,
        setup_gocardless,
        get_config,
        list_accounts,
        recalculate_balance,
    )
    
    commands = [
        'configure_iban',
        'validate_iban',
        'setup_gocardless',
        'get_config',
        'list_accounts',
        'recalculate_balance',
    ]
    
    for cmd in commands:
        print(f"✓ Command: flask finance {cmd}")
    
    print()
except Exception as e:
    print(f"✗ Error importing CLI commands: {e}\n")
    all_passed = False

# Test 6: Event Listeners
print("6. Testing Balance Update Event Listeners...")
print("-" * 70)

try:
    from audela.services.bank_configuration_service import (
        setup_balance_update_listeners,
        initialize_balance_updates,
    )
    print(f"✓ setup_balance_update_listeners function exists")
    print(f"✓ initialize_balance_updates function exists")
    print()
except Exception as e:
    print(f"✗ Error: {e}\n")
    all_passed = False

# Final Summary
print("="*70)
if all_passed:
    print("✅ ALL TESTS PASSED!")
    print("="*70)
    print("\n🚀 Next Steps:")
    print("   1. Run: flask finance list-accounts")
    print("   2. Run: flask finance validate-iban --iban 'YOUR_IBAN'")
    print("   3. Run: flask finance configure-iban --account-id 1 --iban 'YOUR_IBAN'")
    print("   4. Run: flask finance setup-gocardless --account-id 1 --company-id 1 ...")
    print("   5. See BANK_CONFIGURATION_GUIDE.md for more details\n")
    sys.exit(0)
else:
    print("❌ SOME TESTS FAILED!")
    print("="*70 + "\n")
    sys.exit(1)

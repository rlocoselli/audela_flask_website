#!/usr/bin/env python3
"""Tests pour la configuration IBAN et l'integration bancaire.

Usage:
    python3 test_bank_configuration.py
    pytest test_bank_configuration.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure local package imports also work when executed as a standalone script.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audela.services.bank_configuration_service import (  # noqa: E402
    BalanceUpdateService,
    BankConfigurationService,
    IBANValidator,
    initialize_balance_updates,
    setup_balance_update_listeners,
)


def _run_checks(verbose: bool = False) -> tuple[bool, list[str]]:
    messages: list[str] = []
    all_passed = True

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

    for iban, should_be_valid, description in test_ibans:
        is_valid, _ = IBANValidator.is_valid(iban)
        ok = is_valid == should_be_valid
        all_passed = all_passed and ok
        if verbose:
            status = "OK" if ok else "FAIL"
            messages.append(f"[{status}] {description}: {iban}")

    formatted = IBANValidator.format_iban("FR7620041010050500013M02606")
    format_ok = formatted == "FR76 2004 1010 0505 0001 3M02 606"
    all_passed = all_passed and format_ok
    if verbose:
        messages.append(f"[{'OK' if format_ok else 'FAIL'}] IBAN formatting")

    service_methods = [
        "configure_account_iban",
        "configure_company_iban",
        "setup_gocardless_connection",
        "get_account_configuration",
    ]
    for method in service_methods:
        ok = hasattr(BankConfigurationService, method)
        all_passed = all_passed and ok
        if verbose:
            messages.append(f"[{'OK' if ok else 'FAIL'}] BankConfigurationService.{method}")

    balance_methods = ["update_account_balance", "recalculate_account_balance"]
    for method in balance_methods:
        ok = hasattr(BalanceUpdateService, method)
        all_passed = all_passed and ok
        if verbose:
            messages.append(f"[{'OK' if ok else 'FAIL'}] BalanceUpdateService.{method}")

    cli_ok = True
    try:
        from audela.commands.finance_cli import (  # noqa: F401
            configure_iban,
            get_config,
            list_accounts,
            recalculate_balance,
            setup_gocardless,
            validate_iban,
        )
    except Exception:
        cli_ok = False
    all_passed = all_passed and cli_ok
    if verbose:
        messages.append(f"[{'OK' if cli_ok else 'FAIL'}] Finance CLI imports")

    listener_ok = callable(setup_balance_update_listeners) and callable(initialize_balance_updates)
    all_passed = all_passed and listener_ok
    if verbose:
        messages.append(f"[{'OK' if listener_ok else 'FAIL'}] Balance update listeners")

    return all_passed, messages


def test_bank_configuration_smoke() -> None:
    ok, details = _run_checks(verbose=False)
    assert ok, "Bank configuration smoke checks failed: " + "; ".join(details)


def main() -> int:
    print("\n" + "=" * 70)
    print("BANK CONFIGURATION & IBAN VALIDATION - TESTS")
    print("=" * 70 + "\n")

    ok, messages = _run_checks(verbose=True)
    for line in messages:
        print(line)

    print("\n" + "=" * 70)
    if ok:
        print("ALL TESTS PASSED")
        print("=" * 70)
        return 0

    print("SOME TESTS FAILED")
    print("=" * 70)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

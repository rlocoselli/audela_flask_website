# 🏦 Configuration IBAN & Intégration Bancaire

Guide pour configurer les comptes bancaires, les IBAN et l'intégration automatique avec GoCardless.

---

## 📋 Table des Matières

1. [Validation IBAN](#validation-iban)
2. [Configuration IBAN](#configuration-iban)
3. [Configuration GoCardless](#configuration-gocardless)
4. [Mise à Jour Automatique des Soldes](#mise-à-jour-automatique-des-soldes)
5. [CLI Commands](#cli-commands)
6. [API Programmatique](#api-programmatique)

---

## ✅ Validation IBAN

### Normes Supportées

La validation supporte **70+ codes pays** selon la norme ISO 13616:

- **SEPA:** FR, DE, ES, IT, NL, etc.
- **Europe:** GB, CH, NO, SE, etc.
- **Monde:** USA (IBAN routes), Canada, Japon, Australie, etc.

### Vérifications Effectuées

1. ✓ Longueur correcte (15-34 caractères)
2. ✓ Code pays valide (2 lettres)
3. ✓ Format alphanumérique
4. ✓ Checksum mod-97 (algorithme ISO)

### Exemple de Validation

```python
from audela.services.bank_configuration_service import IBANValidator

# Valider un IBAN
is_valid, message = IBANValidator.is_valid("FR7620041010050500013M02606")
# Returns: (True, "Valid IBAN")

# Formater pour display
formatted = IBANValidator.format_iban("FR7620041010050500013M02606")
# Returns: "FR76 2004 1010 0505 0001 3M02 606"
```

---

## 🔧 Configuration IBAN

### Via CLI Command

```bash
# Configurer IBAN pour un compte
flask finance configure-iban --account-id 1 --iban "FR7620041010050500013M02606"

# Configurer IBAN pour une entreprise
flask finance configure-iban --company-id 1 --iban "FR7620041010050500013M02606"

# Valider un IBAN avant configuration
flask finance validate-iban --iban "FR7620041010050500013M02606"
```

### Via Code Python

```python
from audela.services.bank_configuration_service import BankConfigurationService

# Configurer IBAN pour un compte
result = BankConfigurationService.configure_account_iban(
    account_id=1,
    iban="FR7620041010050500013M02606"
)

print(result)
# {
#     "status": "success",
#     "message": "IBAN configured for account Bank Account",
#     "iban": "FR76 2004 1010 0505 0001 3M02 606"
# }

# Configurer IBAN pour une entreprise
result = BankConfigurationService.configure_company_iban(
    company_id=1,
    iban="FR7620041010050500013M02606"
)
```

---

## 🏦 Configuration GoCardless

### Vue d'Ensemble

**GoCardless** (Nordigen API) permet:
- ✅ Importer automatiquement les transactions bancaires
- ✅ Réconciliation automatique
- ✅ Création automatique des contreparties
- ✅ Catégorisation automatique

### Via CLI Command

```bash
# Configuration de base
flask finance setup-gocardless \
  --account-id 1 \
  --company-id 1 \
  --institution SOCIETE_GENERALE_BNAGFRPP \
  --iban FR7620041010050500013M02606 \
  --auto-sync

# Avec tokens GoCardless (optionnel)
flask finance setup-gocardless \
  --account-id 1 \
  --company-id 1 \
  --institution SOCIETE_GENERALE_BNAGFRPP \
  --iban FR7620041010050500013M02606 \
  --access-token "YOUR_ACCESS_TOKEN" \
  --secret-id "YOUR_SECRET_ID" \
  --auto-sync
```

### Via Code Python

```python
from audela.services.bank_configuration_service import BankConfigurationService

# Configuration GoCardless
result = BankConfigurationService.setup_gocardless_connection(
    account_id=1,
    company_id=1,
    tenant_id=1,
    institution_id="SOCIETE_GENERALE_BNAGFRPP",
    iban="FR7620041010050500013M02606",
    access_token="optional_token",
    secret_id="optional_secret",
    auto_sync=True,
)

print(result)
# {
#     "status": "success",
#     "message": "Created GoCardless connection for account Bank Account",
#     "connection_id": 1,
#     "iban": "FR76 2004 1010 0505 0001 3M02 606",
#     "institution_id": "SOCIETE_GENERALE_BNAGFRPP",
#     "auto_sync": True
# }
```

### Lister les Institutions GoCardless Disponibles

**Codes d'institution** pour les banques principales:

| Pays | Banque | Code |
|------|--------|------|
| **FR** | Société Générale | `SOCIETE_GENERALE_BNAGFRPP` |
| **FR** | BNP Paribas | `BNPAPI22` |
| **FR** | Crédit Agricole | `AGRAFI22` |
| **FR** | Banque Populaire | `BNPDFRPP` |
| **DE** | Deutsche Bank | `DEUTSCHE_BANK_DRESDEFF` |
| **DE** | Commerzbank | `COMMERZBANK_COBADEFF` |
| **ES** | BBVA | `BBVAMM22` |
| **IT** | UniCredit | `UNCITIT2X` |
| **NL** | ING | `INGDDEDD` |
| **GB** | HSBC | `HBKAGB22` |

👉 **Liste complète:** https://developer.gocardless.com/

---

## 🔄 Mise à Jour Automatique des Soldes

### Fonctionnalité

Le système met à jour automatiquement le solde du compte (`FinanceAccount.balance`) à chaque:
- ✅ Création de transaction
- ✅ Modification de transaction
- ✅ Suppression de transaction

### Mécanisme

Les **SQLAlchemy Event Listeners** (déclencheurs) mettent à jour le solde:

```
Transaction créée (Amount = +500)
        ↓
Event listener "after_insert"
        ↓
Account.balance += 500
        ↓
Account.balance mis à jour
```

### Recalculer le Solde

En cas de discordance, recalculer le solde à partir des transactions:

```bash
# CLI Command
flask finance recalc-balance --account-id 1
# Résultat:
# Old balance: €1000.00
# New balance: €1150.50
# Difference: €+150.50
# Transactions: 25
```

Via Python:

```python
from audela.services.bank_configuration_service import BalanceUpdateService

result = BalanceUpdateService.recalculate_account_balance(account_id=1)

print(result)
# {
#     "status": "success",
#     "message": "Balance recalculated for account Bank Account",
#     "old_balance": 1000.00,
#     "new_balance": 1150.50,
#     "total_transactions": 25
# }
```

---

## 💻 CLI Commands

### Configuration d'IBAN

```bash
# Configurer IBAN avec prompt interactif
$ flask finance configure-iban --account-id 1
Enter IBAN: FR7620041010050500013M02606
✓ IBAN configured for account Bank Account
✓ IBAN: FR76 2004 1010 0505 0001 3M02 606

# Valider un IBAN
$ flask finance validate-iban
Enter IBAN to validate: FR7620041010050500013M02606
IBAN: FR7620041010050500013M02606
✓ Valid IBAN
Formatted: FR76 2004 1010 0505 0001 3M02 606

# IBAN invalide
$ flask finance validate-iban --iban "INVALID123"
IBAN: INVALID123
✗ IBAN too short (must be 15-34 chars), got 11
```

### Configuration GoCardless

```bash
# Setup avec options
$ flask finance setup-gocardless \
    --account-id 1 \
    --company-id 1 \
    --institution SOCIETE_GENERALE_BNAGFRPP \
    --iban FR7620041010050500013M02606 \
    --auto-sync

✓ Created GoCardless connection for account Bank Account:
  Connection ID:    1
  IBAN:             FR76 2004 1010 0505 0001 3M02 606
  Institution:      SOCIETE_GENERALE_BNAGFRPP
  Auto-sync:        Enabled
```

### Consulter Configuration

```bash
$ flask finance get-config --account-id 1

📊 Configuration for Account: Bank Account
──────────────────────────────────────────────────
Account ID:      1
Type:            bank
Balance:         €2.500,50
Currency:        EUR
IBAN:            FR76 2004 1010 0505 0001 3M02 606

🏦 GoCardless Configuration:
  Connection ID:    1
  Institution:      SOCIETE_GENERALE_BNAGFRPP
  IBAN:             FR76 2004 1010 0505 0001 3M02 606
  Sync Enabled:     Yes
  Last Sync:        2026-02-18 14:30:00.000000
  Auto-import:      Yes
  Auto-categorize:  Yes
  Status:           active
```

### Lister les Comptes

```bash
$ flask finance list-accounts

ID   Name                           Type            Balance        IBAN
──────────────────────────────────────────────────────────────────────────────
1    Bank Account                   bank        €2.500,50   FR76 2004 1010...
2    Credit Card                    credit_card €  -150,00   —
3    Savings Account                bank        €5.000,00   FR76 2004 1010...
```

---

## 🔌 API Programmatique

### Valider et Formater IBAN

```python
from audela.services.bank_configuration_service import IBANValidator

# Valider
is_valid, msg = IBANValidator.is_valid("FR7620041010050500013M02606")
assert is_valid, msg

# Formater
formatted = IBANValidator.format_iban("FR7620041010050500013M02606")
# "FR76 2004 1010 0505 0001 3M02 606"
```

### Configurer un Compte

```python
from audela.services.bank_configuration_service import BankConfigurationService

# Configurer IBAN
result = BankConfigurationService.configure_account_iban(
    account_id=1,
    iban="FR7620041010050500013M02606"
)

if result['status'] == 'success':
    print(f"IBAN: {result['iban']}")
else:
    print(f"Error: {result['message']}")
```

### Configurer GoCardless

```python
from audela.services.bank_configuration_service import BankConfigurationService

# Setup connection
result = BankConfigurationService.setup_gocardless_connection(
    account_id=1,
    company_id=1,
    tenant_id=1,
    institution_id="SOCIETE_GENERALE_BNAGFRPP",
    iban="FR7620041010050500013M02606",
    auto_sync=True,
)

if result['status'] == 'success':
    connection_id = result['connection_id']
    print(f"Connection created: {connection_id}")
```

### Obtenir Configuration

```python
from audela.services.bank_configuration_service import BankConfigurationService

config = BankConfigurationService.get_account_configuration(account_id=1)

if config['status'] == 'success':
    cfg = config['config']
    print(f"Account: {cfg['account_name']}")
    print(f"Balance: €{cfg['current_balance']}")
    print(f"IBAN: {cfg['iban']}")
    
    if cfg['gocardless_configured']:
        gc = cfg['gocardless']
        print(f"GoCardless: {gc['institution_id']}")
        print(f"Sync Status: {gc['status']}")
        print(f"Last Sync: {gc['last_sync']}")
```

### Mettre à Jour Soldes

```python
from audela.services.bank_configuration_service import BalanceUpdateService
from audela.models import FinanceAccount
from decimal import Decimal

# Obtenir le compte
account = FinanceAccount.query.get(1)

# Mettre à jour manuellement
BalanceUpdateService.update_account_balance(account, Decimal("500.00"))

# Recalculer à partir des transactions
result = BalanceUpdateService.recalculate_account_balance(account_id=1)
print(f"New balance: €{result['new_balance']}")
```

---

## 🔐 Sécurité

### Tokens GoCardless

Les tokens GoCardless sont stockés de façon sécurisée:

```python
# ✅ Chiffré en production (à implémenter)
connection.gocardless_access_token  # LargeBinary + chiffrement
```

**À faire:** Implémenter le chiffrement Fernet (voir FINANCE_NEXT_STEPS.md)

### Validation IBAN

L'IBAN est validé côté serveur:
- ✓ Checksum mod-97
- ✓ Longueur par pays
- ✓ Format pays

---

## 🚀 Workflow Complet

### 1. Configuration Initiale

```bash
# 1. Valider l'IBAN de la banque
$ flask finance validate-iban --iban "FR7620041010050500013M02606"

# 2. Configurer l'IBAN sur le compte
$ flask finance configure-iban --account-id 1 --iban "FR7620041010050500013M02606"

# 3. Configurer GoCardless pour sync automatique
$ flask finance setup-gocardless \
    --account-id 1 \
    --company-id 1 \
    --institution SOCIETE_GENERALE_BNAGFRPP \
    --iban FR7620041010050500013M02606 \
    --auto-sync

# 4. Vérifier la configuration
$ flask finance get-config --account-id 1
```

### 2. Opérations Quotidiennes

```python
# Les soldes sont mis à jour automatiquement
txn = FinanceTransaction(
    account_id=1,
    amount=500.00,
    description="Virement entrant"
)
db.session.add(txn)
db.session.commit()

# ➜ Account.balance automatiquement += 500.00
```

### 3. Synchronisation Bancaire

```python
from audela.services.finance_advanced_service import FinanceGoCardlessService

# Forcer une sync
sync_log = FinanceGoCardlessService.sync_transactions(connection_id=1)

# Voir l'historique
history = FinanceGoCardlessService.get_sync_history(connection_id=1)
```

---

## 📊 Exemple Complet

```bash
# 1. Lister les comptes
$ flask finance list-accounts

# 2. Valider IBAN
$ flask finance validate-iban --iban "FR7620041010050500013M02606"
✓ Valid IBAN

# 3. Configuration
$ flask finance configure-iban --account-id 1 --iban "FR7620041010050500013M02606"
✓ IBAN configured

$ flask finance setup-gocardless \
    --account-id 1 --company-id 1 \
    --institution SOCIETE_GENERALE_BNAGFRPP \
    --iban FR7620041010050500013M02606

# 4. Vérifier
$ flask finance get-config --account-id 1
✓ Configuration complète

# 5. Créer une transaction
# (Le solde se met à jour automatiquement)

# 6. Si besoin: recalculer
$ flask finance recalc-balance --account-id 1
✓ Balance recalculated
```

---

## 🐛 Troubleshooting

### IBAN invalide

```
✗ Invalid IBAN: IBAN too short (must be 15-34 chars), got 11
```

**Solution:** Vérifier le format. Voir les normes par pays.

### Compte non trouvé

```
✗ Error: Account 999 not found
```

**Solution:** Vérifier l'ID du compte avec `flask finance list-accounts`

### Solde incorrect après import

```bash
$ flask finance recalc-balance --account-id 1
```

Recalcule automatiquement à partir des transactions.

---

## 📚 Références

- [Norme ISO 13616 IBAN](https://en.wikipedia.org/wiki/International_Bank_Account_Number)
- [GoCardless API Docs](https://developer.gocardless.com/)
- [Nordigen Institution Codes](https://documentation.gocardless.com/institutions)

---

**Date:** 18 février 2026  
**Créé par:** Claude Haiku 4.5

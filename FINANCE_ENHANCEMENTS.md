# Finance Enhancements - Nouvelles Fonctionnalités

Documentation des 6 nouveaux modèles et fonctionnalités ajoutées au système financier.

## 1. **FinanceProduct** - Gestion des Produits avec TVA Automatique

### Description
Registre centralisé des produits et services avec calcul automatique de TVA basé sur la nature du produit.

### Champs Principaux
- `code` (String, 32) - Code produit unique
- `name` (String, 160) - Nom du produit
- `product_type` (String, 24) - Type: `good|service|digital|other`
- `unit_price` (Numeric, 18,4) - Prix unitaire
- `vat_rate` (Numeric, 9,4) - Taux TVA en % (ex: 20.00)
- `vat_applies` (Boolean) - Si la TVA s'applique automatiquement
- `vat_reverse_charge` (Boolean) - Pour les mécanismes de reverse charge
- `tax_exempt_reason` (String, 255) - Raison d'exonération (ex: "export", "intra-EU")
- `currency_code` (ForeignKey) - Devise
- `gl_account_id` (ForeignKey) - Compte GL de produit
- `vat_gl_account_id` (ForeignKey) - Compte GL TVA associé

### Cas d'Usage
```python
# Créer un produit service taxable
product = FinanceProduct.query.create(
    name="Consulting",
    product_type="service",
    unit_price=100.00,
    vat_rate=20.00,
    vat_applies=True,
    currency_code="EUR"
)

# Créer un produit exempté de TVA (export)
product_export = FinanceProduct.query.create(
    name="Export de biens",
    product_type="good",
    unit_price=500.00,
    vat_applies=False,
    tax_exempt_reason="export",
    currency_code="EUR"
)
```

---

## 2. **FinanceDailyBalance** - Suivi du Solde Quotidien

### Description
Snapshots quotidiens du solde des comptes pour analyse de tendances, réconciliation et tracking historique.

### Champs Principaux
- `account_id` (ForeignKey) - Compte financier
- `balance_date` (Date) - Date du solde quotidien
- `opening_balance` (Numeric, 18,2) - Solde d'ouverture
- `closing_balance` (Numeric, 18,2) - Solde de clôture
- `daily_inflow` (Numeric, 18,2) - Total des entrées du jour
- `daily_outflow` (Numeric, 18,2) - Total des sorties du jour
- `transaction_count` (Integer) - Nombre de transactions
- `is_reconciled` (Boolean) - Réconcilié?
- `reconciled_at` (DateTime) - Quand réconcilié
- `reconciliation_notes` (String, 500) - Notes de réconciliation

### Cas d'Usage
```python
from datetime import date, timedelta
from audela.models import FinanceDailyBalance

# Créer un snapshot quotidien
daily = FinanceDailyBalance.query.create(
    account_id=account.id,
    balance_date=date.today(),
    opening_balance=1000.00,
    closing_balance=1150.50,
    daily_inflow=500.00,
    daily_outflow=349.50,
    transaction_count=5,
    is_reconciled=True
)

# Requête: soldes historiques des 30 derniers jours
history = FinanceDailyBalance.query.filter(
    FinanceDailyBalance.account_id == account.id,
    FinanceDailyBalance.balance_date >= date.today() - timedelta(days=30)
).order_by(FinanceDailyBalance.balance_date).all()
```

---

## 3. **FinanceAdjustment** + **FinanceAdjustmentLog** - Ajustements avec Audit Complet

### Description
Enregistrement des ajustements (frais bancaires, intérêts, corrections) avec traçabilité complète sur qui a fait quoi et quand.

### FinanceAdjustment - Champs Principaux
- `account_id` (ForeignKey) - Compte ajusté
- `adjustment_date` (Date) - Date de l'ajustement
- `amount` (Numeric, 18,2) - Montant (positif ou négatif)
- `reason` (String, 64) - `interest|fee|correction|rounding|other`
- `description` (String, 300) - Description détaillée
- `counterparty_id` (ForeignKey, opt.) - Contrepartie responsable
- `status` (String, 32) - `pending|approved|rejected|voided`
- `approved_by_user_id` (Integer) - Qui a approuvé
- `approved_at` (DateTime) - Quand approuvé

### FinanceAdjustmentLog - Champs Principaux
- `adjustment_id` (ForeignKey) - Référence à l'ajustement
- `user_id` (Integer) - Utilisateur qui a effectué l'action
- `action` (String, 32) - `created|modified|approved|rejected|voided`
- `previous_values` (JSON) - État précédent
- `new_values` (JSON) - Nouvel état
- `change_reason` (String, 300) - Raison du changement
- `ip_address` (String, 45) - IP pour audit

### Cas d'Usage
```python
from audela.models import FinanceAdjustment, FinanceAdjustmentLog

# Créer un ajustement de frais bancaires
adjustment = FinanceAdjustment.query.create(
    account_id=account.id,
    adjustment_date=date.today(),
    amount=-10.50,
    reason="fee",
    description="Monthly banking fees from ABC Bank",
    counterparty_id=bank_counterparty.id,
    status="pending"
)

# Log automatique de la création
log = FinanceAdjustmentLog.query.create(
    adjustment_id=adjustment.id,
    user_id=current_user.id,
    action="created",
    new_values={"amount": -10.50, "reason": "fee"},
    ip_address=request.remote_addr
)

# Approuver l'ajustement
adjustment.status = "approved"
adjustment.approved_by_user_id = approver.id
adjustment.approved_at = datetime.utcnow()
db.session.commit()

# Log de l'approbation
log_approval = FinanceAdjustmentLog.query.create(
    adjustment_id=adjustment.id,
    user_id=approver.id,
    action="approved",
    change_reason="Verified against bank statement",
    ip_address=approver_ip
)

# Consulter l'historique complet
history = adjustment.logs.all()  # accès direct via relationship
```

---

## 4. **FinanceCounterpartyAttribute** - Attributs Flexibles pour Contrepartie

### Description
Permet d'ajouter des attributs personnalisés optionnels aux contreparties sans modifier le schéma existant.

### Champs Principaux
- `counterparty_id` (ForeignKey) - Contrepartie
- `attribute_name` (String, 64) - Nom de l'attribut (ex: "payment_terms")
- `attribute_value` (String, 500) - Valeur
- `attribute_type` (String, 32) - `string|number|date|boolean|json`
- `is_custom` (Boolean) - Attribut personnalisé vs système

### Cas d'Usage
```python
from audela.models import FinanceCounterpartyAttribute

# Ajouter des attributs flexibles à une contrepartie (fournisseur)
supplier = FinanceCounterparty.query.get(5)

# Conditions de paiement
attr1 = FinanceCounterpartyAttribute.query.create(
    counterparty_id=supplier.id,
    attribute_name="payment_terms",
    attribute_value="Net 30",
    attribute_type="string"
)

# Limite de crédit
attr2 = FinanceCounterpartyAttribute.query.create(
    counterparty_id=supplier.id,
    attribute_name="credit_limit",
    attribute_value="50000",
    attribute_type="number"
)

# Date de dernière commande
attr3 = FinanceCounterpartyAttribute.query.create(
    counterparty_id=supplier.id,
    attribute_name="last_order_date",
    attribute_value="2026-02-15",
    attribute_type="date"
)

# Accéder aux attributs
for attr in supplier.attributes:
    print(f"{attr.attribute_name}: {attr.attribute_value} ({attr.attribute_type})")
```

---

## 5. **FinanceGoCardlessConnection** + **FinanceGoCardlessSyncLog** - Intégration GoCardless

### Description
Intégration avec GoCardless (Nordigen) pour importer automatiquement les transactions bancaires en temps quasi-réel.

### FinanceGoCardlessConnection - Champs Principaux
- `account_id` (ForeignKey) - Compte financier lié
- `institution_id` (String, 120) - ID d'institution GoCardless
- `gocardless_account_id` (String, 120) - ID du compte chez GoCardless
- `iban` (String, 64) - IBAN
- `sync_enabled` (Boolean) - Activer la synchronisation
- `last_sync_date` (DateTime) - Dernière sync
- `last_sync_status` (String, 32) - `success|failure|pending`
- `sync_days_back` (Integer, default=90) - Nombre de jours à syncer
- `auto_import_enabled` (Boolean) - Importer auto les transactions
- `auto_create_counterparty` (Boolean) - Créer auto les contreparties
- `auto_categorize` (Boolean) - Appliquer auto les catégories
- `status` (String, 32) - `active|inactive|disconnected|error`

### FinanceGoCardlessSyncLog - Champs Principaux
- `connection_id` (ForeignKey)
- `sync_start_date` (DateTime) - Début de la sync
- `sync_end_date` (DateTime) - Fin de la sync
- `transactions_imported` (Integer) - Nombre importé
- `transactions_skipped` (Integer) - Nombre ignoré
- `transactions_failed` (Integer) - Nombre en erreur
- `status` (String, 32) - `pending|success|partial|failure`
- `error_message` (String, 500)
- `sync_metadata` (JSON) - Réponse GoCardless

### Cas d'Usage
```python
from audela.models import FinanceGoCardlessConnection, FinanceGoCardlessSyncLog

# Configurer une connexion GoCardless
connection = FinanceGoCardlessConnection.query.create(
    account_id=account.id,
    institution_id="SOCIETE_GENERALE_BNAGFRPP",  # BIC
    gocardless_account_id="IBAN_EXAMPLE",
    iban="FR1420041010050500013M02606",
    sync_enabled=True,
    sync_days_back=90,
    auto_import_enabled=True,
    auto_create_counterparty=True,
    auto_categorize=True,
    status="active"
)

# Après une synchronisation réussie
sync_log = FinanceGoCardlessSyncLog.query.create(
    connection_id=connection.id,
    sync_start_date=datetime.utcnow(),
    sync_end_date=datetime.utcnow(),
    transactions_imported=15,
    transactions_skipped=2,
    transactions_failed=0,
    status="success"
)

# Consulter l'historique des syncs
syncs = connection.syncs.filter_by(status='success').all()
print(f"Dernière sync réussie: {syncs[0].sync_end_date}")

# Accéder aux derniers logs
recent_logs = connection.syncs.order_by(FinanceGoCardlessSyncLog.created_at.desc()).limit(10)
```

---

## Migrations et Déploiement

### Appliquer les migrations
```bash
flask db upgrade
```

### Revert des migrations
```bash
flask db downgrade
```

---

## Workflow Recommandé

### 1. Gestion des Produits
- Cataloguer tous les produits/services avec TVA appropriée
- Utiliser pour l'automatisation du calcul TVA sur les factures
- Lier aux comptes GL appropriés

### 2. Suivi des Soldes
- Générer automatiquement `FinanceDailyBalance` chaque jour
- Analyse des tendances: graphiques de solde
- Détection de discordances en comparant avec les extraits bancaires

### 3. Ajustements
- Permettre les ajustements manuels (frais, intérêts, corrections)
- Workflow d'approbation multi-niveaux
- Audit complet via les logs

### 4. Contreparties
- Enrichir les contreparties avec des attributs flexibles
- Stocker conditions de paiement, limites de crédit, etc.
- Pas de modification du schéma existant

### 5. Intégration Bancaire
- Connecter comptes via GoCardless API
- Imports automatiques et quasi-temps réel
- Création ou enrichissement auto des transactions
- Application automatique des catégories

---

## Notes Techniques

### Relations SQLAlchemy
- Toutes les relations sont définies avec `relationship()` et`back_populates`
- Support des cascades pour suppression sécurisée
- Indexes créés pour les requêtes fréquentes

### Performance
- Indexes sur `(account_id, balance_date)` pour FinanceDailyBalance
- Indexes sur `(connection_id)` pour les logs GoCardless
- Partitionnement possible sur `balance_date` si nécessaire

### Sécurité
- `gocardless_access_token` stocké en `LargeBinary` (à chiffrer en production)
- `ip_address` tracée dans les logs d'ajustement
- Audit complet de tous les changements d'ajustement

---

## Prochaines Étapes Recommandées

1. **Service GoCardless** - Implémenter `FinanceGoCardlessService` pour les API calls
2. **Calcul TVA** - Créer logique automatique pour appliquer TVA sur factures
3. **Reporting** - Ajouter rapports sur les soldes quotidiens et tendances
4. **Webhooks** - Configurer webhooks GoCardless pour les imports temps-réel

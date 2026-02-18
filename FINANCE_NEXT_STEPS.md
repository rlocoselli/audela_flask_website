# 🔧 Finance System - Guide d'Implémentation Additionnelle

Ce document décrit les étapes pour compléter l'intégration et sécuriser le système.

---

## 1. Chiffrement des Tokens GoCardless

### Problème
Les tokens GoCardless sont actuellement stockés en `LargeBinary` sans chiffrement. Cela pose un risque de sécurité.

### Solution

Utiliser `cryptography` pour chiffrer/déchiffrer les tokens.

#### 1.1 Installation
```bash
pip install cryptography
```

#### 1.2 Créer un utilitaire de chiffrement

**Fichier:** `audela/utils/crypto.py`

```python
from cryptography.fernet import Fernet
import os

class TokenEncryption:
    """Utilitaire pour chiffrer/déchiffrer les tokens sensibles."""
    
    def __init__(self):
        # Récupérer la clé de l'environnement
        self.key = os.environ.get('ENCRYPTION_KEY')
        if not self.key:
            raise ValueError("ENCRYPTION_KEY not configured")
        self.cipher = Fernet(self.key)
    
    def encrypt_token(self, token: str) -> bytes:
        """Chiffrer un token."""
        return self.cipher.encrypt(token.encode())
    
    def decrypt_token(self, encrypted_token: bytes) -> str:
        """Déchiffrer un token."""
        return self.cipher.decrypt(encrypted_token).decode()
```

#### 1.3 Générer une clé de chiffrement

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Stocker le résultat dans .env: ENCRYPTION_KEY=<key>
```

#### 1.4 Modifier le modèle FinanceGoCardlessConnection

```python
from audela.utils.crypto import TokenEncryption

class FinanceGoCardlessConnection(db.Model):
    # ... autres champs ...
    
    _gocardless_access_token_encrypted = db.Column(
        db.LargeBinary, 
        nullable=True
    )
    
    @property
    def gocardless_access_token(self) -> str:
        """Retourner le token déchiffré."""
        if not self._gocardless_access_token_encrypted:
            return None
        try:
            encryption = TokenEncryption()
            return encryption.decrypt_token(self._gocardless_access_token_encrypted)
        except:
            return None
    
    @gocardless_access_token.setter
    def gocardless_access_token(self, value: str):
        """Chiffrer et stocker le token."""
        if not value:
            self._gocardless_access_token_encrypted = None
        else:
            encryption = TokenEncryption()
            self._gocardless_access_token_encrypted = encryption.encrypt_token(value)
```

---

## 2. Webhooks GoCardless pour Import Temps Réel

### Problème
Actuellement la sync est manuelle. Utiliser les webhooks de GoCardless pour imports automatiques.

### Solution

#### 2.1 Créer un endpoint webhook

**Fichier:** `audela/blueprints/api_v1/gocardless_webhooks.py`

```python
from flask import Blueprint, request, jsonify
import hmac
import hashlib
from audela.services.finance_advanced_service import (
    FinanceGoCardlessService
)

bp = Blueprint('gocardless_webhooks', __name__, url_prefix='/webhooks')

@bp.route('/gocardless', methods=['POST'])
def handle_gocardless_webhook():
    """
    Webhook pour les événements GoCardless.
    
    Événements:
    - TRANSACTIONS_READY: Nouvelles transactions disponibles
    - ACCOUNT_TRANSACTIONS_PULL_FAILED: Erreur lors du pull
    """
    
    # Valider signature HMAC
    signature = request.headers.get('Nordigen-Signature')
    if not verify_signature(request.data, signature):
        return jsonify({"error": "Invalid signature"}), 401
    
    payload = request.get_json()
    
    # Traiter les événements
    event_type = payload.get('requisition_id')
    
    if payload.get('status') == 'TRANSACTIONS_READY':
        # Synchroniser les transactions
        connection_id = get_connection_from_requisition(event_type)
        sync_log = FinanceGoCardlessService.sync_transactions(connection_id)
        
        return jsonify({
            "status": "success",
            "sync_id": sync_log.id,
            "transactions_imported": sync_log.transactions_imported
        }), 200
    
    return jsonify({"status": "processed"}), 200


def verify_signature(data: bytes, signature: str) -> bool:
    """Valider la signature HMAC du webhook."""
    secret = os.environ.get('GOCARDLESS_WEBHOOK_SECRET')
    expected = hmac.new(
        secret.encode(),
        data,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def get_connection_from_requisition(requisition_id: str):
    """Trouver la connexion GoCardless par requisition_id."""
    connection = FinanceGoCardlessConnection.query.filter_by(
        gocardless_account_id=requisition_id
    ).first()
    return connection.id if connection else None
```

#### 2.2 Enregistrer l'endpoint

**Fichier:** `audela/blueprints/api_v1/__init__.py`

```python
from .gocardless_webhooks import bp as gocardless_bp

def init_api_v1(app):
    app.register_blueprint(gocardless_bp)
```

---

## 3. Tâches Scheduled avec Celery

### Problème
Besoin d'une tâche récurrente pour générer les soldes quotidiens et synchroniser GoCardless.

### Solution

#### 3.1 Installer Celery

```bash
pip install celery redis
```

#### 3.2 Créer les tâches

**Fichier:** `audela/tasks/__init__.py`

```python
from celery import Celery
from celery.schedules import crontab
from datetime import date
from audela.extensions import db
import os

celery = Celery(
    'audela',
    broker=os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.environ.get('CELERY_BACKEND_URL', 'redis://localhost:6379/1'),
)

# Configuration
celery.conf.update(
    CELERY_TIMEZONE='Europe/Paris',
    CELERY_ENABLE_UTC=True,
    CELERY_TASK_SERIALIZER='json',
)

# Schedule
celery.conf.beat_schedule = {
    'record-daily-balances': {
        'task': 'audela.tasks.record_daily_balances',
        'schedule': crontab(hour=23, minute=59),  # 23:59 chaque jour
    },
    'sync-gocardless': {
        'task': 'audela.tasks.sync_all_gocardless',
        'schedule': crontab(hour='*/6'),  # Toutes les 6 heures
    },
}


@celery.task(name='audela.tasks.record_daily_balances')
def record_daily_balances():
    """Enregistrer les soldes quotidiens de tous les comptes."""
    from audela.models import FinanceAccount
    from audela.services.finance_advanced_service import FinanceDailyBalanceService
    
    accounts = FinanceAccount.query.all()
    count = 0
    
    for account in accounts:
        try:
            FinanceDailyBalanceService.record_daily_balance(
                account_id=account.id,
                company_id=account.company_id,
                tenant_id=1,  # À adapter
                balance_date=date.today(),
            )
            count += 1
        except Exception as e:
            print(f"Error recording balance for account {account.id}: {e}")
    
    return {"task": "record_daily_balances", "count": count}


@celery.task(name='audela.tasks.sync_all_gocardless')
def sync_all_gocardless():
    """Synchroniser tous les comptes GoCardless."""
    from audela.models import FinanceGoCardlessConnection
    from audela.services.finance_advanced_service import FinanceGoCardlessService
    
    connections = FinanceGoCardlessConnection.query.filter_by(
        sync_enabled=True
    ).all()
    
    results = []
    for conn in connections:
        try:
            sync_log = FinanceGoCardlessService.sync_transactions(conn.id)
            results.append({
                "connection_id": conn.id,
                "status": sync_log.status,
                "imported": sync_log.transactions_imported,
            })
        except Exception as e:
            results.append({
                "connection_id": conn.id,
                "status": "error",
                "error": str(e),
            })
    
    return {"task": "sync_all_gocardless", "results": results}
```

#### 3.3 Configuration dans `.env`

```env
# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_BACKEND_URL=redis://localhost:6379/1

# Chiffrement
ENCRYPTION_KEY=<votre_clé_fernet>

# GoCardless
GOCARDLESS_WEBHOOK_SECRET=<votre_secret>
```

---

## 4. API GoCardless - Implémentation

### Problème
Le service GoCardless est actuellement un stub. Il faut implémenter les appels réels à l'API Nordigen.

### Solution

#### 4.1 Installer le client GoCardless

```bash
pip install gocardless-api
```

#### 4.2 Créer le vrai service

**Fichier:** `audela/services/gocardless_service.py`

```python
import os
import requests
from datetime import datetime, timedelta
from audela.models import (
    FinanceTransaction,
    FinanceCounterparty,
    FinanceGoCardlessSyncLog,
)
from audela.extensions import db

class NordigenAPI:
    """Client pour l'API Nordigen (GoCardless)."""
    
    BASE_URL = "https://api.gocardless.com/api/v2"
    
    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
    
    def get_transactions(
        self,
        account_id: str,
        days_back: int = 90
    ) -> list:
        """Récupérer les transactions d'un compte."""
        
        date_from = (datetime.now() - timedelta(days=days_back)).date()
        
        url = f"{self.BASE_URL}/accounts/{account_id}/transactions/"
        params = {
            "date_from": str(date_from),
            "date_to": str(datetime.now().date()),
        }
        
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        
        return response.json().get('results', [])
    
    def get_account(self, account_id: str) -> dict:
        """Obtenir les détails d'un compte."""
        
        url = f"{self.BASE_URL}/accounts/{account_id}/"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        
        return response.json().get('account', {})


def import_transactions_from_gocardless(
    connection,
    sync_log: FinanceGoCardlessSyncLog
) -> dict:
    """
    Importer les transactions depuis GoCardless.
    
    Args:
        connection: FinanceGoCardlessConnection
        sync_log: Le log de sync à mettre à jour
    """
    
    try:
        # Connecter à GoCardless
        token = connection.gocardless_access_token
        api = NordigenAPI(token)
        
        # Récupérer les transactions
        transactions = api.get_transactions(
            connection.gocardless_account_id,
            days_back=connection.sync_days_back
        )
        
        imported = 0
        skipped = 0
        failed = 0
        
        for txn in transactions:
            try:
                # Traiter la transaction
                if should_skip_transaction(txn):
                    skipped += 1
                    continue
                
                # Créer ou mettre à jour la transaction
                finance_txn = FinanceTransaction(
                    tenant_id=connection.tenant_id,
                    company_id=connection.company_id,
                    account_id=connection.account_id,
                    txn_date=datetime.fromisoformat(txn['date']).date(),
                    amount=float(txn['amount']),
                    description=txn.get('remittance_information_unstructured', ''),
                    category="bank_import",
                )
                
                # Auto-créer contrepartie si enabled
                if connection.auto_create_counterparty:
                    counterparty = get_or_create_counterparty(txn)
                    finance_txn.counterparty_id = counterparty.id
                
                db.session.add(finance_txn)
                imported += 1
                
            except Exception as e:
                failed += 1
                print(f"Error importing transaction {txn.get('id')}: {e}")
        
        db.session.commit()
        
        # Mettre à jour le log
        sync_log.transactions_imported = imported
        sync_log.transactions_skipped = skipped
        sync_log.transactions_failed = failed
        sync_log.sync_end_date = datetime.utcnow()
        sync_log.status = "success" if imported > 0 else "partial"
        db.session.commit()
        
        return {
            "status": "success",
            "imported": imported,
            "skipped": skipped,
            "failed": failed,
        }
        
    except Exception as e:
        sync_log.status = "failure"
        sync_log.error_message = str(e)
        db.session.commit()
        
        return {
            "status": "failure",
            "error": str(e),
        }


def should_skip_transaction(txn: dict) -> bool:
    """Vérifier si la transaction doit être ignorée."""
    # Ignorer les transactions déjà importées
    # Ignorer certains types de transactions
    return False


def get_or_create_counterparty(txn: dict) -> FinanceCounterparty:
    """Créer ou retourner une contrepartie à partir d'une transaction."""
    
    counterparty_name = txn.get('creditor_name') or txn.get('debtor_name', 'Unknown')
    
    counterparty = FinanceCounterparty.query.filter_by(
        name=counterparty_name
    ).first()
    
    if not counterparty:
        counterparty = FinanceCounterparty(
            tenant_id=1,  # À adapter
            name=counterparty_name,
            kind="other",
        )
        db.session.add(counterparty)
        db.session.flush()
    
    return counterparty
```

---

## 5. Tests Unitaires

### Tests à créer

**Fichier:** `tests/test_finance_models.py`

```python
import pytest
from datetime import date, timedelta
from decimal import Decimal
from audela.models import (
    FinanceProduct,
    FinanceAdjustment,
    FinanceDailyBalance,
)


def test_finance_product_creation(app, db_session):
    """Tester la création d'un produit."""
    product = FinanceProduct(
        tenant_id=1,
        company_id=1,
        name="Test Product",
        product_type="service",
        unit_price=Decimal("100.00"),
        currency_code="EUR",
        vat_rate=Decimal("20.00"),
        vat_applies=True,
    )
    db_session.add(product)
    db_session.commit()
    
    assert product.id is not None
    assert product.vat_rate == Decimal("20.00")


def test_adjustment_creation_and_approval(app, db_session, account):
    """Tester la création et approbation d'un ajustement."""
    from audela.services.finance_advanced_service import FinanceAdjustmentService
    
    # Créer
    adj = FinanceAdjustmentService.create_adjustment(
        account_id=account.id,
        amount=Decimal("-10.00"),
        reason="fee",
        user_id=1,
    )
    
    assert adj.status == "pending"
    assert len(adj.logs) == 1
    
    # Approuver
    approved = FinanceAdjustmentService.approve_adjustment(adj.id, user_id=2)
    
    assert approved.status == "approved"
    assert len(approved.logs) == 2


def test_daily_balance_calculation(app, db_session, account):
    """Tester l'enregistrement des soldes quotidiens."""
    from audela.services.finance_advanced_service import FinanceDailyBalanceService
    
    daily = FinanceDailyBalanceService.record_daily_balance(
        account_id=account.id,
        company_id=account.company_id,
        tenant_id=1,
    )
    
    assert daily.balance_date == date.today()
    assert daily.is_reconciled == False
```

---

## 6. Migration de la Base de Données (Production)

### Avant de déployer

```bash
# 1. Backup
mysqldump -u user -p database > backup_$(date +%Y%m%d).sql

# 2. Tester la migration
flask db upgrade --sql

# 3. Appliquer
flask db upgrade

# 4. Vérifier
flask shell
# >>> from audela.models import FinanceProduct
# >>> FinanceProduct.query.count()
```

---

## 📋 Checklist Finalisation

- [ ] Réduire `gocardless_access_token_encrypted` en migration
- [ ] Implémenter chiffrement des tokens
- [ ] Créer endpoint webhook GoCardless
- [ ] Configurer Celery + Redis
- [ ] Implémenter l'API Nordigen réelle
- [ ] Écrire tests unitaires
- [ ] Documenter les secrets à configurer
- [ ] Tester sur staging
- [ ] Déployer sur production
- [ ] Monitorer les logs
- [ ] Documenter les alertes

---

**Prochaine étape:** Commencera par le chiffrement des tokens (Partie 1) et les webhooks (Partie 2).

# Prochaines Étapes - Phase 3: Production & Nordigen Integration

**Date:** Décembre 2024  
**Phase:** Phase 3 (Post-Phase 2 Implementation)  
**Status:** Planning

---

## 🎯 Objectifs Phase 3

Transformation d'une implémentation fonctionnelle en système production-ready avec intégration Nordigen/GoCardless réelle.

### Domaines:
1. 🔒 **Sécurité** - Encryption des tokens, webhook validation
2. 🔌 **API Integration** - Vraies appels à Nordigen
3. 🧹 **Polish** - Tests, monitoring, UI
4. 📊 **Analytics** - Reporting et dashboards

---

## 1️⃣ SÉCURITÉ & TOKENS (Priority High)

### 1.1 Encryption des Tokens

**Objectif:** Stocker les tokens GoCardless/Nordigen sécurisés (non en clair)

**Implémentation:**

```python
# File: audela/services/security_service.py (NEW)

from cryptography.fernet import Fernet
import os

class TokenEncryptionService:
    """Service pour chiffrement/déchiffrement des tokens bancaires."""
    
    def __init__(self):
        # Clé de chiffrement (depuis env var)
        key = os.getenv('FINANCE_CIPHER_KEY')
        if not key:
            # Générer une nouvelle clé
            key = Fernet.generate_key()
            print(f"⚠️  Set FINANCE_CIPHER_KEY={key.decode()}")
        self.cipher = Fernet(key)
    
    def encrypt_token(self, token: str) -> str:
        """Chiffrer un token."""
        encrypted = self.cipher.encrypt(token.encode())
        return encrypted.decode()
    
    def decrypt_token(self, encrypted_token: str) -> str:
        """Déchiffrer un token."""
        decrypted = self.cipher.decrypt(encrypted_token.encode())
        return decrypted.decode()

# Utilisation dans BankConfigurationService:
class BankConfigurationService:
    encryption = TokenEncryptionService()
    
    @staticmethod
    def setup_gocardless_connection(..., access_token, refresh_token, ...):
        # Chiffrer avant stockage
        encrypted_access = TokenEncryptionService().encrypt_token(access_token)
        encrypted_refresh = TokenEncryptionService().encrypt_token(refresh_token)
        
        connection = FinanceGoCardlessConnection(
            account_id=account_id,
            company_id=company_id,
            institution_id=institution_id,
            iban=iban,
            access_token=encrypted_access,      # ✅ CHIFFRÉ
            refresh_token=encrypted_refresh,    # ✅ CHIFFRÉ
            auto_sync=auto_sync,
            ...
        )
        db.session.add(connection)
        db.session.commit()
```

**Setup:**

```bash
# Générer clé
python3 << 'EOF'
from cryptography.fernet import Fernet
key = Fernet.generate_key()
print(f"FINANCE_CIPHER_KEY={key.decode()}")
EOF

# Configuration
export FINANCE_CIPHER_KEY="your_generated_key_here"
```

**Tests:**

```python
# test_token_encryption.py
from audela.services.security_service import TokenEncryptionService

svc = TokenEncryptionService()
original = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ..."

encrypted = svc.encrypt_token(original)
decrypted = svc.decrypt_token(encrypted)

assert decrypted == original  # ✅
```

---

### 1.2 Webhook Signature Validation

**Objectif:** Vérifier que les webhooks viennent vraiment de Nordigen

**Implémentation:**

```python
# File: audela/services/webhook_service.py (NEW)

import hmac
import hashlib
import json
from typing import Tuple

class WebhookValidationService:
    """Validation des webhooks GoCardless/Nordigen."""
    
    def __init__(self, webhook_secret: str):
        self.webhook_secret = webhook_secret
    
    def validate_signature(self, 
                          body: bytes, 
                          signature_header: str) -> Tuple[bool, str]:
        """
        Valider la signature d'un webhook.
        
        Args:
            body: Raw request body (bytes)
            signature_header: Valeur de X-Signature header
        
        Returns:
            (is_valid, message)
        """
        # Calculer signature attendue
        expected_sig = hmac.new(
            self.webhook_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        
        # Comparer (timing-safe)
        is_valid = hmac.compare_digest(expected_sig, signature_header)
        
        return is_valid, "Webhook signature valid" if is_valid else "Invalid signature"

# Usage dans Flask routes:
from flask import request, jsonify
from audela.services.webhook_service import WebhookValidationService

webhook_handler = WebhookValidationService(os.getenv('GOCARDLESS_WEBHOOK_SECRET'))

@app.route('/api/v1/webhooks/gocardless', methods=['POST'])
def handle_gocardless_webhook():
    # Valider signature
    signature = request.headers.get('X-Signature')
    is_valid, msg = webhook_handler.validate_signature(request.get_data(), signature)
    
    if not is_valid:
        return jsonify({'error': msg}), 401
    
    # Traiter webhook
    data = request.get_json()
    event_type = data.get('type')  # 'TRANSACTION_BOOKED', etc.
    
    if event_type == 'TRANSACTION_BOOKED':
        # Importer nouvelle transaction
        # ...
    
    return jsonify({'status': 'received'}), 200
```

---

## 2️⃣ API NORDIGEN INTEGRATION (Priority High)

### 2.1 Setup OAuth Flow

**Objectif:** Récupérer les vraies données de Nordigen

**Implémentation:**

```python
# File: audela/services/nordigen_api_service.py (NEW)

import requests
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal

class NordigenAPIService:
    """Client pour l'API Nordigen (GoCardless)."""
    
    BASE_URL = "https://ob.nordigen.com/api/v2"
    
    def __init__(self, client_id: str, secret_key: str):
        self.client_id = client_id
        self.secret_key = secret_key
        self.session = requests.Session()
    
    def authenticate(self) -> Dict:
        """Obtenir access_token avec appel d'API."""
        response = self.session.post(
            f"{self.BASE_URL}/token/new/",
            json={
                "secret_id": self.client_id,
                "secret_key": self.secret_key
            }
        )
        if response.status_code == 200:
            return response.json()  # {access: ..., refresh: ...}
        raise Exception(f"Auth failed: {response.text}")
    
    def get_requisition(self, redirect_url: str, institution_id: str) -> str:
        """
        Créer une permission d'accès utilisateur.
        
        Returns: requisition_id
        """
        response = self.session.post(
            f"{self.BASE_URL}/requisitions/",
            json={
                "redirect": redirect_url,
                "institution_id": institution_id,
                "agreement": "AGREEMENT_ID",  # A créer via API d'abord
                "user_language": "fr"
            },
            headers={"Authorization": f"Bearer {self.access_token}"}
        )
        if response.status_code == 201:
            return response.json()['id']
        raise Exception(f"Requisition failed: {response.text}")
    
    def get_accounts(self, requisition_id: str) -> List[Dict]:
        """Récupérer les comptes autorisés."""
        response = self.session.get(
            f"{self.BASE_URL}/requisitions/{requisition_id}/",
            headers={"Authorization": f"Bearer {self.access_token}"}
        )
        data = response.json()
        return data.get('accounts', [])  # List of account IDs
    
    def get_account_details(self, account_id: str) -> Dict:
        """Récupérer détails du compte (IBAN, etc)."""
        response = self.session.get(
            f"{self.BASE_URL}/accounts/{account_id}/details/",
            headers={"Authorization": f"Bearer {self.access_token}"}
        )
        return response.json()
    
    def get_account_balances(self, account_id: str) -> Dict:
        """Récupérer soldes du compte."""
        response = self.session.get(
            f"{self.BASE_URL}/accounts/{account_id}/balances/",
            headers={"Authorization": f"Bearer {self.access_token}"}
        )
        data = response.json()
        # Format: {balances: [{type: "CURRENT", balanceAmount: {...}}]}
        return data
    
    def get_transactions(self, 
                        account_id: str, 
                        date_from: Optional[str] = None,
                        date_to: Optional[str] = None) -> List[Dict]:
        """
        Récupérer les transactions.
        
        dates format: "2024-01-01"
        """
        # Par défaut: last 90 days
        if not date_from:
            date_from = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        if not date_to:
            date_to = datetime.now().strftime("%Y-%m-%d")
        
        response = self.session.get(
            f"{self.BASE_URL}/accounts/{account_id}/transactions/",
            params={
                "date_from": date_from,
                "date_to": date_to
            },
            headers={"Authorization": f"Bearer {self.access_token}"}
        )
        data = response.json()
        return data.get('transactions', {}).get('booked', [])

# Usage:
# 1. Setup
nordigen = NordigenAPIService(
    client_id=os.getenv("GOCARDLESS_CLIENT_ID"),
    secret_key=os.getenv("GOCARDLESS_SECRET_KEY")
)

# 2. Auth & Get permissions
auth = nordigen.authenticate()
nordigen.access_token = auth['access']
requisition_id = nordigen.get_requisition(
    redirect_url="https://audela.app/callback",
    institution_id="FRSOPRISAXXXXXX"
)
# → User clicks link, authorizes, redirects back with requisition_id

# 3. Sync transactions
account_ids = nordigen.get_accounts(requisition_id)
for account_id in account_ids:
    transactions = nordigen.get_transactions(account_id)
    # → Import into FinanceTransaction
```

**Setup:**

```bash
# Get credentials from GoCardless (https://ob.nordigen.com/)
export GOCARDLESS_CLIENT_ID="your_client_id"
export GOCARDLESS_SECRET_KEY="your_secret_key"
```

---

### 2.2 Transaction Import Service

**Objectif:** Mapper les transactions Nordigen vers FinanceTransaction

**Implémentation:**

```python
# File: audela/services/transaction_import_service.py (NEW)

from audela.models import (
    FinanceTransaction,
    FinanceAccount,
    FinanceCategory,
)
from audela.services.nordigen_api_service import NordigenAPIService
from decimal import Decimal
from datetime import datetime

class TransactionImportService:
    """Importer les transactions depuis Nordigen."""
    
    @staticmethod
    def import_nordigen_transactions(account_id: int,
                                     nordigen_account_id: str,
                                     nordigen_txns: List[Dict]) -> Dict:
        """
        Importer les transactions Nordigen.
        
        Returns:
            {
                'status': 'success',
                'imported': 42,
                'skipped': 5,
                'errors': []
            }
        """
        account = FinanceAccount.query.get(account_id)
        if not account:
            return {'status': 'error', 'message': 'Account not found'}
        
        imported = 0
        skipped = 0
        errors = []
        
        for txn_data in nordigen_txns:
            try:
                # Vérifier si déjà importé (via reference)
                ref = txn_data.get('internalTransactionId') or txn_data.get('transactionId')
                existing = FinanceTransaction.query.filter_by(
                    account_id=account_id,
                    external_reference=ref
                ).first()
                
                if existing:
                    skipped += 1
                    continue
                
                # Mapper les champs
                amount = Decimal(str(txn_data.get('transactionAmount', {}).get('amount', 0)))
                is_debit = txn_data.get('debitCreditIndicator') == 'DBIT'
                
                if is_debit:
                    amount = -amount  # Dépense négative
                
                # Créer transaction
                txn = FinanceTransaction(
                    account_id=account_id,
                    amount=amount,
                    description=txn_data.get('remittanceInformationUnstructured') or 
                               txn_data.get('id'),
                    transaction_date=datetime.fromisoformat(
                        txn_data.get('bookingDateTime', '').split('Z')[0]
                    ),
                    external_reference=ref,
                    vendor_reference=txn_data.get('bankTransactionCode'),
                    counterparty_name=txn_data.get('counterpartyName'),
                    counterparty_iban=txn_data.get('counterpartyAccount', {}).get('iban'),
                )
                
                db.session.add(txn)
                imported += 1
                
            except Exception as e:
                errors.append({
                    'transaction': txn_data.get('id'),
                    'error': str(e)
                })
        
        try:
            db.session.commit()
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Database error: {str(e)}',
                'imported': imported,
                'skipped': skipped,
            }
        
        return {
            'status': 'success',
            'imported': imported,
            'skipped': skipped,
            'errors': errors,
            'total': imported + skipped
        }
    
    @staticmethod
    def sync_account_balance_from_nordigen(account_id: int,
                                          nordigen_account_id: str) -> Dict:
        """Synchroniser le solde depuis Nordigen."""
        nordigen = NordigenAPIService(
            os.getenv("GOCARDLESS_CLIENT_ID"),
            os.getenv("GOCARDLESS_SECRET_KEY")
        )
        
        account = FinanceAccount.query.get(account_id)
        balances = nordigen.get_account_balances(nordigen_account_id)
        
        # Get CURRENT balance
        for balance in balances.get('balances', []):
            if balance.get('type') == 'CURRENT':
                amount = Decimal(str(balance['balanceAmount']['amount']))
                account.balance = amount
                db.session.commit()
                
                return {
                    'status': 'success',
                    'balance': str(amount),
                    'updated_at': datetime.now().isoformat()
                }
        
        return {'status': 'error', 'message': 'No CURRENT balance found'}
```

---

## 3️⃣ WEBHOOKS & REAL-TIME SYNC (Priority Medium)

**Objectif:** Importer les transactions en temps réel via webhooks

```python
# File: audela/blueprints/webhooks/__init__.py (NEW)

from flask import Blueprint, request, jsonify
from audela.services.webhook_service import WebhookValidationService
from audela.services.transaction_import_service import TransactionImportService
import os

webhooks_bp = Blueprint('webhooks', __name__, url_prefix='/api/v1/webhooks')

webhook_validator = WebhookValidationService(
    webhook_secret=os.getenv('GOCARDLESS_WEBHOOK_SECRET')
)

@webhooks_bp.route('/gocardless', methods=['POST'])
def handle_gocardless_webhook():
    """Recevoir et traiter les webhooks GoCardless."""
    
    # Validation signature
    signature = request.headers.get('X-Signature')
    is_valid, msg = webhook_validator.validate_signature(
        request.get_data(),
        signature
    )
    
    if not is_valid:
        return jsonify({'error': msg}), 401
    
    # Parse event
    event = request.get_json()
    event_type = event.get('type')
    
    if event_type == 'TRANSACTION_BOOKED':
        # Traiter nouvelle transaction
        account_id = event.get('account_id')
        transactions = event.get('transactions', [])
        
        result = TransactionImportService.import_nordigen_transactions(
            account_id=account_id,
            nordigen_account_id=event.get('nordigen_account_id'),
            nordigen_txns=transactions
        )
        
        return jsonify(result), 200
    
    elif event_type == 'ACCOUNT_UPDATED':
        # Synchroniser solde
        account_id = event.get('account_id')
        result = TransactionImportService.sync_account_balance_from_nordigen(
            account_id=account_id,
            nordigen_account_id=event.get('nordigen_account_id')
        )
        return jsonify(result), 200
    
    # Unknown event, acknowledge anyway
    return jsonify({'status': 'received'}), 200

# Register in audela/__init__.py
from audela.blueprints.webhooks import webhooks_bp
app.register_blueprint(webhooks_bp)
```

**Configuration GoCardless:**

```bash
# Dans le dashboard GoCardless:
1. Settings → Webhooks
2. Add webhook endpoint: https://audela.app/api/v1/webhooks/gocardless
3. Copy webhook secret
4. Set: export GOCARDLESS_WEBHOOK_SECRET="your_webhook_secret"
```

---

## 4️⃣ TESTS D'INTÉGRATION (Priority High)

```python
# File: tests/test_nordigen_integration.py (NEW)

import pytest
from unittest.mock import Mock, patch, MagicMock
from audela.services.nordigen_api_service import NordigenAPIService
from audela.services.transaction_import_service import TransactionImportService

@pytest.fixture
def nordigen_mock():
    with patch('audela.services.nordigen_api_service.requests.Session') as mock:
        yield mock

def test_nordigen_authenticate(nordigen_mock):
    """Test authentification Nordigen."""
    nordigen = NordigenAPIService("client_id", "secret_key")
    
    # Mock response
    nordigen_mock.return_value.post.return_value.json.return_value = {
        'access': 'eyJ0eXAi...',
        'refresh': 'eyJ0eXAi...'
    }
    
    auth = nordigen.authenticate()
    assert 'access' in auth
    assert 'refresh' in auth

def test_import_transactions(client, db):
    """Test import des transactions."""
    # Setup account
    account = FinanceAccount(
        id=1,
        name="Test Account",
        currency="EUR"
    )
    db.session.add(account)
    db.session.commit()
    
    # Mock transactions from Nordigen
    mock_txns = [
        {
            'id': 'TXN001',
            'internalTransactionId': 'INT001',
            'transactionAmount': {'amount': '100.00', 'currency': 'EUR'},
            'debitCreditIndicator': 'CRDT',
            'bookingDateTime': '2024-01-15T10:30:00Z',
            'remittanceInformationUnstructured': 'Payment from Bank',
            'counterpartyName': 'Company ABC',
            'counterpartyAccount': {'iban': 'FR1420041010050500013M02606'}
        }
    ]
    
    # Import
    result = TransactionImportService.import_nordigen_transactions(
        account_id=1,
        nordigen_account_id='ACCOUNT001',
        nordigen_txns=mock_txns
    )
    
    assert result['status'] == 'success'
    assert result['imported'] == 1
    
    # Verify transaction created
    txn = FinanceTransaction.query.first()
    assert txn.amount == Decimal('100.00')
    assert account.balance == Decimal('100.00')  # Auto-updated! ✓

def test_webhook_validation():
    """Test validation des webhooks."""
    from audela.services.webhook_service import WebhookValidationService
    
    validator = WebhookValidationService("secret123")
    body = b'{"type": "TRANSACTION_BOOKED"}'
    
    # Calculer signature correcte
    import hmac
    import hashlib
    correct_sig = hmac.new(
        b"secret123",
        body,
        hashlib.sha256
    ).hexdigest()
    
    # Test valid signature
    is_valid, msg = validator.validate_signature(body, correct_sig)
    assert is_valid is True
    
    # Test invalid signature
    is_valid, msg = validator.validate_signature(body, "wrong_sig")
    assert is_valid is False

@pytest.mark.integration
def test_full_sync_workflow(client, db):
    """Test workflow complet: auth → get accounts → import → webhook."""
    # Cette test utilise un sandbox Nordigen
    # À configurer avec vraies credentials de test
    pass
```

**Exécuter les tests:**

```bash
pytest tests/test_nordigen_integration.py -v
```

---

## 5️⃣ REST API ENDPOINTS (Priority Medium)

**Objectif:** Endpoints pour configuration bancaire via API

```python
# File: audela/blueprints/api_v1/bank_routes.py (NEW)

from flask import Blueprint, request, jsonify
from audela.services.bank_configuration_service import (
    BankConfigurationService,
    IBANValidator
)
from audela.models import FinanceAccount

bank_bp = Blueprint('bank', __name__, url_prefix='/api/v1/bank')

@bank_bp.route('/iban/validate', methods=['POST'])
def validate_iban_endpoint():
    """
    POST /api/v1/bank/iban/validate
    
    Body: {"iban": "FR1420041010050500013M02606"}
    """
    data = request.get_json()
    iban = data.get('iban')
    
    if not iban:
        return jsonify({'error': 'IBAN required'}), 400
    
    is_valid, message = IBANValidator.is_valid(iban)
    
    return jsonify({
        'is_valid': is_valid,
        'message': message,
        'formatted': IBANValidator.format_iban(iban) if is_valid else None
    }), 200

@bank_bp.route('/account/<int:account_id>/iban', methods=['PUT'])
def configure_iban_endpoint(account_id):
    """
    PUT /api/v1/bank/account/1/iban
    
    Body: {"iban": "FR1420041010050500013M02606"}
    """
    data = request.get_json()
    iban = data.get('iban')
    
    if not iban:
        return jsonify({'error': 'IBAN required'}), 400
    
    try:
        BankConfigurationService.configure_account_iban(
            account_id=account_id,
            iban=iban
        )
        
        account = FinanceAccount.query.get(account_id)
        return jsonify({
            'success': True,
            'account_id': account_id,
            'iban': account.iban,
            'formatted_iban': IBANValidator.format_iban(account.iban)
        }), 200
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

@bank_bp.route('/account/<int:account_id>/config', methods=['GET'])
def get_account_config(account_id):
    """
    GET /api/v1/bank/account/1/config
    
    Retourne: account, iban, gocardless config, is_configured
    """
    try:
        config = BankConfigurationService.get_account_configuration(account_id)
        return jsonify(config), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bank_bp.route('/account/<int:account_id>/gocardless', methods=['POST'])
def setup_gocardless_endpoint(account_id):
    """
    POST /api/v1/bank/account/1/gocardless
    
    Body: {
        "company_id": 1,
        "institution_id": "FRSOPRISAXXXXXX",
        "iban": "FR1420041010050500013M02606",
        "access_token": "eyJ...",
        "refresh_token": "eyJ...",
        "auto_sync": true
    }
    """
    data = request.get_json()
    
    try:
        result = BankConfigurationService.setup_gocardless_connection(
            account_id=account_id,
            company_id=data.get('company_id'),
            institution_id=data.get('institution_id'),
            iban=data.get('iban'),
            access_token=data.get('access_token'),
            refresh_token=data.get('refresh_token'),
            auto_sync=data.get('auto_sync', True),
            auto_import=data.get('auto_import', True),
            auto_categorize=data.get('auto_categorize', False),
        )
        
        return jsonify(result), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# Register in audela/blueprints/api_v1/__init__.py
from .bank_routes import bank_bp
api_v1_bp.register_blueprint(bank_bp)
```

---

## 6️⃣ FRONTEND / UI (Priority Low)

**Objectif:** Interface web pour configuration bancaire

```html
<!-- File: audela/templates_portal/bank_config.html (NEW) -->

{% extends "base.html" %}

{% block title %}Configuration Bancaire{% endblock %}

{% block content %}
<div class="container">
    <h1>Paramètres Bancaires</h1>
    
    <div class="card">
        <h2>1. Configuration IBAN</h2>
        <form id="iban-form" onsubmit="configureIBAN(event)">
            <div class="form-group">
                <label>IBAN:</label>
                <input type="text" id="iban-input" placeholder="FR1420041010050500013M02606" required>
            </div>
            <button type="submit">Valider et Enregistrer</button>
        </form>
        <div id="iban-status"></div>
    </div>
    
    <div class="card">
        <h2>2. GoCardless / Nordigen</h2>
        <button onclick="startGoCardlessFlow()">Connecter à la Banque</button>
    </div>
    
    <div class="card">
        <h2>3. Statut de Synchronisation</h2>
        <div id="sync-status">Chargement...</div>
    </div>
</div>

<script>
async function configureIBAN(e) {
    e.preventDefault();
    const iban = document.getElementById('iban-input').value;
    
    // Valider
    const validateResp = await fetch('/api/v1/bank/iban/validate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({iban})
    });
    
    const validation = await validateResp.json();
    
    if (!validation.is_valid) {
        showError(validation.message);
        return;
    }
    
    // Configurer
    const configResp = await fetch(`/api/v1/bank/account/1/iban`, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({iban})
    });
    
    const result = await configResp.json();
    if (result.success) {
        showSuccess(`IBAN configuré: ${result.formatted_iban}`);
    }
}

async function startGoCardlessFlow() {
    // Rediriger vers GoCardless OAuth
    const institutionId = "FRSOPRISAXXXXXX";  // À sélectionner
    window.location.href = `/auth/gocardless?institution_id=${institutionId}`;
}

async function loadSyncStatus() {
    const resp = await fetch('/api/v1/bank/account/1/config');
    const config = await resp.json();
    
    const status = document.getElementById('sync-status');
    status.innerHTML = `
        <div>IBAN: ${config.iban || 'Non configuré'}</div>
        <div>GoCardless: ${config.is_configured ? 'Connecté ✓' : 'Non connecté ✗'}</div>
        <div>Sync auto: ${config.gocardless_config?.auto_sync ? 'Activé ✓' : 'Désactivé ✗'}</div>
    `;
}

loadSyncStatus();
</script>
{% endblock %}
```

---

## 📋 Checklist Implementation

### Phase 3 - Security (Week 1-2)
- [ ] TokenEncryptionService (Fernet)
- [ ] WebhookValidationService (HMAC-SHA256)
- [ ] Tests encryption/decryption
- [ ] Setup env variables

### Phase 3 - API Integration (Week 2-3)
- [ ] NordigenAPIService
- [ ] TransactionImportService
- [ ] Full Nordigen workflows
- [ ] Tests unitaires + intégration

### Phase 3 - Webhooks (Week 3-4)
- [ ] Webhook blueprint
- [ ] Real-time sync
- [ ] Error handling & retries
- [ ] Rate limiting

### Phase 3 - REST API (Week 4)
- [ ] Bank configuration endpoints
- [ ] IBAN validation endpoint
- [ ] GoCardless setup endpoint
- [ ] Documentation (Swagger)

### Phase 3 - UI (Week 4-5)
- [ ] Bank config page
- [ ] IBAN input validation
- [ ] GoCardless OAuth flow
- [ ] Sync status dashboard

### Phase 3 - Testing & Deploy (Week 5-6)
- [ ] Full integration tests
- [ ] Performance testing
- [ ] Security audit
- [ ] Production deployment

---

## 🚀 Getting Started

```bash
# 1. Récupérer credentials GoCardless
# https://ob.nordigen.com/ → create account → get credentials

# 2. Setup env
export GOCARDLESS_CLIENT_ID="..."
export GOCARDLESS_SECRET_KEY="..."
export GOCARDLESS_WEBHOOK_SECRET="..."
export FINANCE_CIPHER_KEY="..." # Generate via Fernet

# 3. Create services
touch audela/services/security_service.py
touch audela/services/nordigen_api_service.py
touch audela/services/transaction_import_service.py
touch audela/services/webhook_service.py

# 4. Run tests
pytest tests/test_nordigen_integration.py -v

# 5. Start app
flask run
```

---

## 📞 Questions Fréquentes

**Q: Quand sera Phase 3 implémenté?**  
A: Dépend de la priorité. Security (semaines 1-2) est critique avant production.

**Q: Puis-je utiliser Phase 2 sans Phase 3?**  
A: Oui! Phase 2 fonctionne complètement standalone. Phase 3 ajoute juste l'intégration Nordigen réelle.

**Q: Comment tester les webhooks en local?**  
A: Utiliser ngrok (https://ngrok.com/) pour exposer localhost à internet, puis configurer webhook dans GoCardless.

---

## 📚 Références

- [GoCardless/Nordigen API](https://developer.gocardless.com/api)
- [Cryptography: Fernet](https://cryptography.io/en/latest/fernet/)
- [SQLAlchemy Event Listeners](https://docs.sqlalchemy.org/en/20/orm/events.html)

---

**Rédigé:** Décembre 2024  
**Version:** 1.0  
**Prêt pour:** Implementation Phase 3

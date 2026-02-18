# 🏦 Configuration Powens (Tink)

Guide rapide pour configurer l'intégration bancaire avec Powens/Tink.

---

## 📋 Prérequis

1. **Compte Powens/Tink** - Créer un compte développeur sur:
   - https://powens.com/
   - https://tink.com/

2. **Credentials API** - Obtenir:
   - `client_id`
   - `client_secret`
   - `access_token` (généré via OAuth)

---

## ⚙️ Configuration Environnement

Ajouter dans `.env` ou variables d'environnement:

```bash
# Powens/Tink API
POWENS_CLIENT_ID=votre_client_id
POWENS_CLIENT_SECRET=votre_secret
POWENS_WEBHOOK_SECRET=votre_webhook_secret

# Chiffrement tokens (production)
ENCRYPTION_KEY=votre_clé_fernet_32_bytes
```

### Générer une clé de chiffrement Fernet

```python
from cryptography.fernet import Fernet
key = Fernet.generate_key()
print(key.decode())  # Copier dans ENCRYPTION_KEY
```

---

## 🚀 Utilisation Basique

### 1. Créer une Connexion Bancaire

```python
from audela.services.finance_advanced_service import FinancePowensService

# Créer la connexion
connection = FinancePowensService.create_connection(
    account_id=1,              # ID du compte FinanceAccount
    company_id=1,              # ID de la compagnie
    tenant_id=1,               # ID du tenant
    institution_id="BNAGFRPP", # BIC de la banque
    iban="FR7612345678901234567890123"
)

print(f"✓ Connexion créée: ID {connection.id}")
print(f"  Status: {connection.status}")
print(f"  IBAN: {connection.iban}")
```

### 2. Synchroniser les Transactions

```python
# Lancer une synchronisation
sync_log = FinancePowensService.sync_transactions(
    connection_id=connection.id
)

print(f"✓ Sync terminée: {sync_log.status}")
print(f"  Transactions importées: {sync_log.transactions_imported}")
print(f"  Transactions ignorées: {sync_log.transactions_skipped}")
```

### 3. Consulter l'Historique

```python
# Obtenir les 10 dernières syncs
history = FinancePowensService.get_sync_history(
    connection_id=connection.id,
    limit=10
)

for sync in history:
    print(f"{sync.created_at}: {sync.status} - {sync.transactions_imported} transactions")
```

---

## 🔐 Chiffrement des Tokens (Production)

**Important:** Les tokens d'accès Powens doivent être chiffrés en production.

### Créer un service de chiffrement

**Fichier:** `audela/services/encryption_service.py`

```python
import os
from cryptography.fernet import Fernet

class EncryptionService:
    """Service pour chiffrer/déchiffrer les tokens."""
    
    @staticmethod
    def get_cipher():
        key = os.environ.get('ENCRYPTION_KEY')
        if not key:
            raise ValueError("ENCRYPTION_KEY not set")
        return Fernet(key.encode())
    
    @staticmethod
    def encrypt_token(token: str) -> bytes:
        """Chiffrer un token."""
        cipher = EncryptionService.get_cipher()
        return cipher.encrypt(token.encode())
    
    @staticmethod
    def decrypt_token(encrypted_token: bytes) -> str:
        """Déchiffrer un token."""
        cipher = EncryptionService.get_cipher()
        return cipher.decrypt(encrypted_token).decode()
```

### Modifier le modèle FinancePowensConnection

```python
from audela.services.encryption_service import EncryptionService

class FinancePowensConnection(db.Model):
    # ...
    
    _powens_access_token_encrypted = db.Column(
        'powens_access_token',
        db.LargeBinary,
        nullable=True
    )
    
    @property
    def powens_access_token(self) -> str:
        """Getter: déchiffre le token."""
        if not self._powens_access_token_encrypted:
            return None
        try:
            return EncryptionService.decrypt_token(
                self._powens_access_token_encrypted
            )
        except Exception:
            return None
    
    @powens_access_token.setter
    def powens_access_token(self, value: str):
        """Setter: chiffre le token avant stockage."""
        if value is None:
            self._powens_access_token_encrypted = None
        else:
            self._powens_access_token_encrypted = EncryptionService.encrypt_token(value)
```

---

## 🔄 Webhooks Temps Réel (Optionnel)

Pour recevoir les notifications de nouvelles transactions en temps réel.

### 1. Créer l'endpoint webhook

**Fichier:** `audela/blueprints/api_v1/powens_webhooks.py`

```python
from flask import Blueprint, request, jsonify
import hmac
import hashlib
import os

from audela.services.finance_advanced_service import FinancePowensService

bp = Blueprint('powens_webhooks', __name__, url_prefix='/webhooks')

@bp.route('/powens', methods=['POST'])
def handle_powens_webhook():
    """
    Webhook pour les événements Powens/Tink.
    """
    # Vérifier la signature
    signature = request.headers.get('X-Powens-Signature')
    if not verify_signature(request.data, signature):
        return jsonify({"error": "Invalid signature"}), 401
    
    payload = request.json
    event_type = payload.get('event_type')
    
    if event_type == 'transactions.new':
        # Nouvelle transaction détectée
        connection_id = payload.get('connection_id')
        sync_log = FinancePowensService.sync_transactions(connection_id)
        
        return jsonify({
            "status": "success",
            "sync_log_id": sync_log.id
        }), 200
    
    return jsonify({"status": "ignored"}), 200

def verify_signature(payload: bytes, signature: str) -> bool:
    """Vérifier la signature HMAC du webhook."""
    secret = os.environ.get('POWENS_WEBHOOK_SECRET')
    if not secret:
        return False
    
    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected, signature)
```

### 2. Enregistrer le blueprint

Dans `audela/__init__.py`:

```python
from audela.blueprints.api_v1.powens_webhooks import bp as powens_bp
app.register_blueprint(powens_bp)
```

### 3. Configurer dans Powens Dashboard

URL du webhook: `https://votredomaine.com/webhooks/powens`

---

## 🕐 Tâches Planifiées (Celery)

Pour synchroniser automatiquement tous les comptes chaque jour.

### Configuration Celery

**Fichier:** `audela/tasks.py`

```python
from celery import Celery
from audela.models import FinancePowensConnection
from audela.services.finance_advanced_service import FinancePowensService

celery = Celery('audela', broker='redis://localhost:6379/0')

@celery.task
def sync_all_powens_connections():
    """Synchroniser tous les comptes Powens actifs."""
    connections = FinancePowensConnection.query.filter_by(
        status='active',
        sync_enabled=True
    ).all()
    
    results = []
    for conn in connections:
        try:
            sync_log = FinancePowensService.sync_transactions(conn.id)
            results.append({
                'connection_id': conn.id,
                'status': sync_log.status,
                'imported': sync_log.transactions_imported
            })
        except Exception as e:
            results.append({
                'connection_id': conn.id,
                'error': str(e)
            })
    
    return results
```

### Schedule dans `celeryconfig.py`

```python
from celery.schedules import crontab

beat_schedule = {
    'sync-powens-daily': {
        'task': 'audela.tasks.sync_all_powens_connections',
        'schedule': crontab(hour=2, minute=0),  # Tous les jours à 2h
    },
}
```

---

## 📊 Exemple Complet

```python
from audela.extensions import db
from audela.models import FinanceAccount, FinanceCompany
from audela.services.finance_advanced_service import FinancePowensService

# 1. Trouver le compte bancaire
account = FinanceAccount.query.filter_by(name="Compte Courant").first()
company = FinanceCompany.query.first()

# 2. Créer la connexion Powens
connection = FinancePowensService.create_connection(
    account_id=account.id,
    company_id=company.id,
    tenant_id=company.tenant_id,
    institution_id="BNPAFRPP",  # BNP Paribas
    iban=account.iban
)

# 3. Synchroniser immédiatement
sync_log = FinancePowensService.sync_transactions(connection.id)

print(f"""
✓ Configuration terminée!

Connexion ID: {connection.id}
IBAN: {connection.iban}
Status: {connection.status}

Première sync:
- Transactions importées: {sync_log.transactions_imported}
- Status: {sync_log.status}
""")

# 4. Consulter l'historique
history = FinancePowensService.get_sync_history(connection.id)
print(f"\nHistorique: {len(history)} synchronisations")
```

---

## ✅ Checklist

- [ ] Créer compte Powens/Tink développeur
- [ ] Obtenir `client_id` et `client_secret`
- [ ] Configurer variables d'environnement
- [ ] Générer clé de chiffrement `ENCRYPTION_KEY`
- [ ] Créer connexion pour chaque compte bancaire
- [ ] Tester première synchronisation
- [ ] (Optionnel) Configurer webhooks
- [ ] (Optionnel) Configurer tâches Celery planifiées
- [ ] Vérifier les logs de synchronisation
- [ ] Backuper la base de données

---

## 🔧 Troubleshooting

### Erreur: "ENCRYPTION_KEY not set"
→ Ajouter `ENCRYPTION_KEY` dans `.env`

### Erreur: "Connection not found"
→ Vérifier que `connection.id` existe dans la DB

### Sync status = "failure"
→ Consulter `sync_log.error_message` pour détails

### Pas de transactions importées
→ Vérifier:
- IBAN correct
- Institution ID valide
- Token d'accès Powens valide
- Date `sync_days_back` appropriée

---

## 📚 Ressources

- **Powens API:** https://powens.com/developers
- **Tink API:** https://docs.tink.com/
- **Cryptography:** https://cryptography.io/
- **Celery:** https://docs.celeryproject.org/

---

**Créé le:** 18 février 2026  
**Version:** 1.0

"""
Finance Configuration Service - IBAN Configuration & Balance Updates

Services pour:
1. Configuration des IBAN pour les comptes
2. Configuration des connexions bancaires (GoCardless, etc)
3. Mise à jour automatique des soldes lors des transactions
4. Validation des IBAN
"""

import re
from typing import Optional, Dict, Tuple
from decimal import Decimal

from audela.extensions import db
from audela.models import (
    FinanceAccount,
    FinanceCompany,
    FinanceTransaction,
    FinanceGoCardlessConnection,
)


class IBANValidator:
    """Validateur D'IBAN selon la norme ISO 13616."""
    
    # Mapping des longueurs d'IBAN par pays
    IBAN_LENGTHS = {
        'AD': 24, 'AE': 23, 'AL': 28, 'AT': 20, 'AZ': 28, 'BA': 20, 'BE': 16,
        'BG': 22, 'BH': 22, 'BR': 29, 'BY': 28, 'CH': 21, 'CR': 22, 'CY': 28,
        'CZ': 24, 'DE': 22, 'DK': 18, 'DO': 28, 'EE': 20, 'EG': 29, 'ES': 24,
        'FI': 18, 'FO': 18, 'FR': 27, 'GB': 22, 'GE': 22, 'GI': 23, 'GL': 18,
        'GR': 27, 'GT': 28, 'HR': 21, 'HU': 28, 'IE': 22, 'IL': 23, 'IS': 26,
        'IT': 27, 'JO': 30, 'KW': 30, 'KZ': 20, 'LB': 28, 'LI': 21, 'LT': 20,
        'LU': 20, 'LV': 21, 'MC': 27, 'MD': 24, 'ME': 22, 'MK': 19, 'MR': 27,
        'MT': 31, 'MU': 30, 'NL': 18, 'NO': 15, 'PK': 24, 'PL': 28, 'PS': 29,
        'PT': 25, 'QA': 29, 'RO': 24, 'RS': 22, 'SA': 24, 'SE': 24, 'SI': 19,
        'SK': 24, 'SM': 27, 'TN': 24, 'TR': 26, 'UA': 29, 'VA': 22, 'VG': 24,
        'XK': 20,
    }
    
    @staticmethod
    def is_valid(iban: str) -> Tuple[bool, str]:
        """
        Valider un IBAN.
        
        Returns:
            Tuple: (is_valid, message)
        """
        if not iban:
            return False, "IBAN cannot be empty"
        
        # Nettoyer les espaces
        iban = iban.upper().replace(" ", "")
        
        # Vérifier format: code pays + 2 chiffres
        if len(iban) < 15:
            return False, f"IBAN too short (must be 15-34 chars), got {len(iban)}"
        
        if len(iban) > 34:
            return False, f"IBAN too long (max 34 chars), got {len(iban)}"
        
        # Extraire code pays (2 premiers caractères)
        country_code = iban[:2]
        if not country_code.isalpha():
            return False, f"Invalid country code: {country_code}"
        
        # Vérifier la longueur pour ce pays
        expected_length = IBANValidator.IBAN_LENGTHS.get(country_code)
        if expected_length and len(iban) != expected_length:
            return False, f"Invalid IBAN length for {country_code}: expected {expected_length}, got {len(iban)}"
        
        # Vérifier le format: pas de caractères spéciaux sauf alphanumériques
        if not re.match(r'^[A-Z0-9]+$', iban):
            return False, "IBAN contains invalid characters"
        
        # Algorithme mod-97 (checksum)
        # Déplacer les 4 premiers caractères à la fin
        rearranged = iban[4:] + iban[:4]
        
        # Remplacer les lettres par leurs chiffres (A=10, B=11, ..., Z=35)
        numeric = ''
        for char in rearranged:
            if char.isdigit():
                numeric += char
            else:
                numeric += str(ord(char) - ord('A') + 10)
        
        # Vérifier que mod 97 = 1
        if int(numeric) % 97 != 1:
            return False, "Invalid IBAN checksum"
        
        return True, "Valid IBAN"
    
    @staticmethod
    def format_iban(iban: str) -> str:
        """Formater l'IBAN pour display (avec espaces)."""
        iban_clean = iban.upper().replace(" ", "")
        return ' '.join([iban_clean[i:i+4] for i in range(0, len(iban_clean), 4)])


class BankConfigurationService:
    """Service pour configurer les comptes bancaires et l'API."""
    
    @staticmethod
    def configure_account_iban(
        account_id: int,
        iban: str,
    ) -> Dict:
        """
        Configurer l'IBAN pour un compte.
        
        Args:
            account_id: ID du compte
            iban: Numéro IBAN
            
        Returns:
            Dict avec statut et message
        """
        account = FinanceAccount.query.get(account_id)
        if not account:
            return {"status": "error", "message": f"Account {account_id} not found"}
        
        # Valider l'IBAN
        is_valid, message = IBANValidator.is_valid(iban)
        if not is_valid:
            return {"status": "error", "message": f"Invalid IBAN: {message}"}
        
        # Stocker l'IBAN formaté (caller must db.session.commit())
        account.iban = IBANValidator.format_iban(iban)
        
        return {
            "status": "success",
            "message": f"IBAN configured for account {account.name}",
            "iban": account.iban,
        }
    
    @staticmethod
    def configure_company_iban(
        company_id: int,
        iban: str,
    ) -> Dict:
        """
        Configurer l'IBAN pour une entreprise.
        
        Args:
            company_id: ID de l'entreprise
            iban: Numéro IBAN
            
        Returns:
            Dict avec statut et message
        """
        company = FinanceCompany.query.get(company_id)
        if not company:
            return {"status": "error", "message": f"Company {company_id} not found"}
        
        # Valider l'IBAN
        is_valid, message = IBANValidator.is_valid(iban)
        if not is_valid:
            return {"status": "error", "message": f"Invalid IBAN: {message}"}
        
        # Stocker l'IBAN formaté (caller must db.session.commit())
        company.iban = IBANValidator.format_iban(iban)
        
        return {
            "status": "success",
            "message": f"IBAN configured for company {company.name}",
            "iban": company.iban,
        }
    
    @staticmethod
    def setup_gocardless_connection(
        account_id: int,
        company_id: int,
        tenant_id: int,
        institution_id: str,
        iban: str,
        access_token: Optional[str] = None,
        secret_id: Optional[str] = None,
        auto_sync: bool = True,
    ) -> Dict:
        """
        Configurer une connexion GoCardless pour un compte.
        
        Args:
            account_id: ID du compte
            company_id: ID de l'entreprise
            tenant_id: ID du tenant
            institution_id: ID d'institution GoCardless/Nordigen
            iban: IBAN du compte bancaire
            access_token: Token d'accès GoCardless (optionnel)
            secret_id: Secret ID GoCardless (optionnel)
            auto_sync: Activer la synchronisation automatique
            
        Returns:
            Dict avec statut et message
        """
        
        # Valider l'IBAN
        is_valid, message = IBANValidator.is_valid(iban)
        if not is_valid:
            return {"status": "error", "message": f"Invalid IBAN: {message}"}
        
        account = FinanceAccount.query.get(account_id)
        if not account:
            return {"status": "error", "message": f"Account {account_id} not found"}
        
        # Vérifier si connexion existe
        existing = FinanceGoCardlessConnection.query.filter_by(
            account_id=account_id
        ).first()
        
        if existing:
            connection = existing
            message_prefix = "Updated"
        else:
            connection = FinanceGoCardlessConnection(
                tenant_id=tenant_id,
                company_id=company_id,
                account_id=account_id,
            )
            message_prefix = "Created"
        
        # Configurer
        connection.institution_id = institution_id
        connection.iban = IBANValidator.format_iban(iban)
        connection.sync_enabled = auto_sync
        connection.sync_days_back = 90
        connection.auto_import_enabled = True
        connection.auto_create_counterparty = True
        connection.auto_categorize = True
        connection.status = "active"
        
        if access_token:
            connection.gocardless_access_token = access_token.encode()
        
        if secret_id:
            connection.gocardless_secret_id = secret_id
        
        db.session.add(connection)
        db.session.commit()
        
        return {
            "status": "success",
            "message": f"{message_prefix} GoCardless connection for account {account.name}",
            "connection_id": connection.id,
            "iban": connection.iban,
            "institution_id": connection.institution_id,
            "auto_sync": connection.sync_enabled,
        }
    
    @staticmethod
    def get_account_configuration(account_id: int) -> Dict:
        """Obtenir la configuration d'un compte."""
        account = FinanceAccount.query.get(account_id)
        if not account:
            return {"status": "error", "message": f"Account {account_id} not found"}
        
        # Récupérer la connexion GoCardless si existe
        gocardless_conn = FinanceGoCardlessConnection.query.filter_by(
            account_id=account_id
        ).first()
        
        config = {
            "account_id": account.id,
            "account_name": account.name,
            "account_type": account.account_type,
            "current_balance": float(account.balance),
            "iban": account.iban,
            "currency": account.currency,
            "gocardless_configured": gocardless_conn is not None,
        }
        
        if gocardless_conn:
            config["gocardless"] = {
                "connection_id": gocardless_conn.id,
                "institution_id": gocardless_conn.institution_id,
                "iban": gocardless_conn.iban,
                "sync_enabled": gocardless_conn.sync_enabled,
                "last_sync": str(gocardless_conn.last_sync_date) if gocardless_conn.last_sync_date else None,
                "auto_import": gocardless_conn.auto_import_enabled,
                "auto_categorize": gocardless_conn.auto_categorize,
                "status": gocardless_conn.status,
            }
        
        return {
            "status": "success",
            "config": config,
        }


class BalanceUpdateService:
    """Service pour mettre à jour automatiquement les soldes."""
    
    @staticmethod
    def update_account_balance(account: FinanceAccount, amount: Decimal):
        """
        Mettre à jour le solde d'un compte.
        
        Args:
            account: Le compte à mettre à jour
            amount: Le montant à ajouter (positif/négatif)
        """
        old_balance = account.balance
        account.balance = (account.balance or Decimal(0)) + amount
        account.updated_at = db.func.now()
        
        return {
            "old_balance": old_balance,
            "new_balance": account.balance,
            "change": amount,
        }
    
    @staticmethod
    def recalculate_account_balance(account_id: int) -> Dict:
        """
        Recalculer le solde d'un compte à partir dels transactions.
        
        Utile pour une correction/audit.
        """
        from audela.models import FinanceAccount
        
        account = FinanceAccount.query.get(account_id)
        if not account:
            return {"status": "error", "message": f"Account {account_id} not found"}
        
        # Calculer le solde total
        total = db.session.query(
            db.func.sum(FinanceTransaction.amount)
        ).filter(
            FinanceTransaction.account_id == account_id
        ).scalar() or Decimal(0)
        
        old_balance = account.balance
        account.balance = total
        account.updated_at = db.func.now()
        db.session.commit()
        
        return {
            "status": "success",
            "message": f"Balance recalculated for account {account.name}",
            "old_balance": float(old_balance),
            "new_balance": float(account.balance),
            "total_transactions": FinanceTransaction.query.filter_by(
                account_id=account_id
            ).count(),
        }


# Event Listeners pour mettre à jour les soldes automatiquement
def setup_balance_update_listeners():
    """
    Configure les listeners SQLAlchemy pour mettre à jour le solde
    automatiquement quand une transaction est créée/modifiée/supprimée.
    """
    from sqlalchemy import event
    
    @event.listens_for(FinanceTransaction, 'after_insert')
    def receive_after_insert(mapper, connection, target):
        """Mettre à jour le solde après l'insertion d'une transaction."""
        account_table = FinanceAccount.__table__
        connection.execute(
            account_table.update()
            .where(account_table.c.id == target.account_id)
            .values(
                balance=db.func.coalesce(account_table.c.balance, 0) + target.amount,
                updated_at=db.func.now(),
            )
        )
    
    @event.listens_for(FinanceTransaction, 'after_update')
    def receive_after_update(mapper, connection, target):
        """Ajouter le nouveau montant après la mise à jour."""
        from sqlalchemy.orm.attributes import get_history
        amount_history = get_history(target, 'amount')
        
        if amount_history.has_changes():
            old_amount = amount_history.deleted[0] if amount_history.deleted else Decimal(0)
            new_amount = amount_history.added[0] if amount_history.added else target.amount
            delta = (new_amount or Decimal(0)) - (old_amount or Decimal(0))
            if delta:
                account_table = FinanceAccount.__table__
                connection.execute(
                    account_table.update()
                    .where(account_table.c.id == target.account_id)
                    .values(
                        balance=db.func.coalesce(account_table.c.balance, 0) + delta,
                        updated_at=db.func.now(),
                    )
                )
    
    @event.listens_for(FinanceTransaction, 'after_delete')
    def receive_after_delete(mapper, connection, target):
        """Soustraire le montant après la suppression d'une transaction."""
        account_table = FinanceAccount.__table__
        connection.execute(
            account_table.update()
            .where(account_table.c.id == target.account_id)
            .values(
                balance=db.func.coalesce(account_table.c.balance, 0) - target.amount,
                updated_at=db.func.now(),
            )
        )


# Initialiser les listeners au démarrage
def initialize_balance_updates():
    """Appeler au démarrage de l'app pour activer les mises à jour automatiques."""
    setup_balance_update_listeners()

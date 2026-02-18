"""
Finance Services - VAT Automatic Application & Adjustments Management

Services pour gérer:
1. Application automatique de la TVA sur les factures
2. Gestion des ajustements et audit
3. Suivi quotidien des soldes
4. Intégration GoCardless (stub)
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Dict, List, Tuple

from audela.extensions import db
from audela.models import (
    FinanceProduct,
    FinanceInvoice,
    FinanceInvoiceLine,
    FinanceAdjustment,
    FinanceAdjustmentLog,
    FinanceDailyBalance,
    FinanceTransaction,
    FinanceGoCardlessConnection,
    FinanceGoCardlessSyncLog,
)


class FinanceVATService:
    """Service pour l'application automatique de la TVA."""

    @staticmethod
    def calculate_vat_for_product(product: FinanceProduct, amount: Decimal) -> Tuple[Decimal, Decimal]:
        """
        Calculer le montant HT et TVA pour un produit.
        
        Args:
            product: Le produit avec sa configuration TVA
            amount: Montant HT/unitaire
            
        Returns:
            Tuple: (amount_excluding_vat, vat_amount)
        """
        if not product.vat_applies or product.vat_reverse_charge:
            return amount, Decimal(0)
        
        vat_rate = product.vat_rate / 100
        vat_amount = amount * vat_rate
        
        return amount, vat_amount

    @staticmethod
    def apply_vat_to_invoice_line(line: FinanceInvoiceLine) -> Dict:
        """
        Appliquer la TVA automatiquement sur une ligne de facture.
        
        Utilise la configuration TVA du produit if nécessaire.
        """
        if not line.product_id:
            return {"vat_amount": Decimal(0), "applied": False}
        
        product = FinanceProduct.query.get(line.product_id)
        if not product:
            return {"vat_amount": Decimal(0), "applied": False}
        
        if not product.vat_applies:
            line.vat_rate = Decimal(0)
            line.vat_amount = Decimal(0)
            return {"vat_amount": Decimal(0), "applied": False, "reason": "Product exempt"}
        
        # Calculer la TVA
        line_total = line.quantity * line.unit_price
        line.vat_rate = product.vat_rate
        line.vat_amount = line_total * (product.vat_rate / 100)
        
        db.session.commit()
        
        return {
            "vat_amount": line.vat_amount,
            "vat_rate": product.vat_rate,
            "applied": True
        }

    @staticmethod
    def apply_vat_to_invoice(invoice: FinanceInvoice) -> Dict:
        """
        Appliquer la TVA automatiquement sur tous les lignes d'une facture.
        """
        total_vat = Decimal(0)
        lines_processed = 0
        
        for line in invoice.lines:
            result = FinanceVATService.apply_vat_to_invoice_line(line)
            if result.get("applied"):
                total_vat += result.get("vat_amount", Decimal(0))
                lines_processed += 1
        
        invoice.vat_total = total_vat
        db.session.commit()
        
        return {
            "total_vat": total_vat,
            "lines_processed": lines_processed,
            "status": "success"
        }


class FinanceAdjustmentService:
    """Service pour gérer les ajustements avec audit complet."""

    @staticmethod
    def create_adjustment(
        account_id: int,
        amount: Decimal,
        reason: str,
        description: Optional[str] = None,
        counterparty_id: Optional[int] = None,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
    ) -> FinanceAdjustment:
        """
        Créer un nouvel ajustement avec log automatique.
        
        Args:
            account_id: ID du compte ajusté
            amount: Montant (positif/négatif)
            reason: Raison (interest|fee|correction|rounding|other)
            description: Description optionnelle
            counterparty_id: Contrepartie optionnelle
            user_id: Utilisateur qui crée
            ip_address: IP pour audit
            
        Returns:
            FinanceAdjustment créé
        """
        adjustment = FinanceAdjustment(
            account_id=account_id,
            adjustment_date=date.today(),
            amount=amount,
            reason=reason,
            description=description,
            counterparty_id=counterparty_id,
            status="pending",
            tenant_id=1,  # À adapter selon le contexte
            company_id=1,  # À adapter selon le contexte
        )
        db.session.add(adjustment)
        db.session.flush()  # Pour obtenir l'ID
        
        # Log de création
        log = FinanceAdjustmentLog(
            adjustment_id=adjustment.id,
            tenant_id=adjustment.tenant_id,
            user_id=user_id or 0,
            action="created",
            new_values={
                "amount": str(amount),
                "reason": reason,
                "description": description,
            },
            ip_address=ip_address,
        )
        db.session.add(log)
        db.session.commit()
        
        return adjustment

    @staticmethod
    def approve_adjustment(
        adjustment_id: int,
        approved_by_user_id: int,
        ip_address: Optional[str] = None,
    ) -> FinanceAdjustment:
        """Approuver un ajustement."""
        adjustment = FinanceAdjustment.query.get(adjustment_id)
        if not adjustment:
            raise ValueError(f"Adjustment {adjustment_id} not found")
        
        previous_status = adjustment.status
        adjustment.status = "approved"
        adjustment.approved_by_user_id = approved_by_user_id
        adjustment.approved_at = datetime.utcnow()
        db.session.commit()
        
        # Log de l'approbation
        log = FinanceAdjustmentLog(
            adjustment_id=adjustment.id,
            tenant_id=adjustment.tenant_id,
            user_id=approved_by_user_id,
            action="approved",
            previous_values={"status": previous_status},
            new_values={"status": "approved"},
            ip_address=ip_address,
        )
        db.session.add(log)
        db.session.commit()
        
        return adjustment

    @staticmethod
    def get_audit_trail(adjustment_id: int) -> List[FinanceAdjustmentLog]:
        """Obtenir l'historique complet d'un ajustement."""
        return FinanceAdjustmentLog.query.filter_by(
            adjustment_id=adjustment_id
        ).order_by(FinanceAdjustmentLog.created_at).all()


class FinanceDailyBalanceService:
    """Service pour gérer les soldes quotidiens."""

    @staticmethod
    def record_daily_balance(
        account_id: int,
        company_id: int,
        tenant_id: int,
        balance_date: Optional[date] = None,
    ) -> FinanceDailyBalance:
        """
        Enregistrer le solde quotidien d'un compte.
        
        Calcule automatiquement les totaux à partir des transactions.
        """
        balance_date = balance_date or date.today()
        
        # Obtenir les transactions du jour
        txns = FinanceTransaction.query.filter(
            FinanceTransaction.account_id == account_id,
            FinanceTransaction.txn_date == balance_date,
        ).all()
        
        # Calculer les totaux
        daily_inflow = sum(t.amount for t in txns if t.amount > 0)
        daily_outflow = sum(abs(t.amount) for t in txns if t.amount < 0)
        
        # Obtenir le solde actuel du compte
        from audela.models import FinanceAccount
        account = FinanceAccount.query.get(account_id)
        closing_balance = account.balance
        opening_balance = closing_balance - daily_inflow + daily_outflow
        
        daily_balance = FinanceDailyBalance(
            tenant_id=tenant_id,
            company_id=company_id,
            account_id=account_id,
            balance_date=balance_date,
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            daily_inflow=daily_inflow,
            daily_outflow=daily_outflow,
            transaction_count=len(txns),
            is_reconciled=False,
        )
        
        db.session.add(daily_balance)
        db.session.commit()
        
        return daily_balance

    @staticmethod
    def get_balance_history(
        account_id: int,
        start_date: date,
        end_date: date,
    ) -> List[FinanceDailyBalance]:
        """Obtenir l'historique des soldes quotidiens."""
        return FinanceDailyBalance.query.filter(
            FinanceDailyBalance.account_id == account_id,
            FinanceDailyBalance.balance_date >= start_date,
            FinanceDailyBalance.balance_date <= end_date,
        ).order_by(FinanceDailyBalance.balance_date).all()


class FinanceGoCardlessService:
    """Service pour l'intégration GoCardless (stub)."""

    @staticmethod
    def create_connection(
        account_id: int,
        company_id: int,
        tenant_id: int,
        institution_id: str,
        iban: str,
    ) -> FinanceGoCardlessConnection:
        """
        Créer une connexion GoCardless.
        
        En production, cela déclencherait le flow OAuth de Nordigen.
        """
        connection = FinanceGoCardlessConnection(
            tenant_id=tenant_id,
            company_id=company_id,
            account_id=account_id,
            institution_id=institution_id,
            iban=iban,
            sync_enabled=True,
            sync_days_back=90,
            auto_import_enabled=True,
            auto_create_counterparty=True,
            auto_categorize=True,
            status="active",
        )
        
        db.session.add(connection)
        db.session.commit()
        
        return connection

    @staticmethod
    def sync_transactions(connection_id: int) -> FinanceGoCardlessSyncLog:
        """
        Synchroniser les transactions depuis GoCardless.
        
        Stub - en production appelerait l'API Nordigen.
        """
        connection = FinanceGoCardlessConnection.query.get(connection_id)
        if not connection:
            raise ValueError(f"Connection {connection_id} not found")
        
        sync_log = FinanceGoCardlessSyncLog(
            tenant_id=connection.tenant_id,
            connection_id=connection_id,
            sync_start_date=datetime.utcnow(),
            status="pending",
        )
        
        db.session.add(sync_log)
        db.session.flush()
        
        # En production: appeler API Nordigen ici
        # transactions = call_gocardless_api(connection.gocardless_account_id)
        
        # Stub: simuler des données
        transactions_imported = 0
        transactions_skipped = 0
        
        sync_log.sync_end_date = datetime.utcnow()
        sync_log.transactions_imported = transactions_imported
        sync_log.transactions_skipped = transactions_skipped
        sync_log.status = "success" if transactions_imported > 0 else "partial"
        
        connection.last_sync_date = datetime.utcnow()
        connection.last_sync_status = "success"
        
        db.session.commit()
        
        return sync_log

    @staticmethod
    def get_sync_history(connection_id: int, limit: int = 10) -> List[FinanceGoCardlessSyncLog]:
        """Obtenir l'historique des synchronisations."""
        return FinanceGoCardlessSyncLog.query.filter_by(
            connection_id=connection_id
        ).order_by(FinanceGoCardlessSyncLog.created_at.desc()).limit(limit).all()


# Exemple d'utilisation
if __name__ == "__main__":
    print("Finance Services - Examples")
    print("=" * 50)
    
    # Exemple 1: Application de la TVA
    print("\n1. VAT Application Example:")
    # product = FinanceProduct.query.first()
    # if product:
    #     vat_info = FinanceVATService.calculate_vat_for_product(product, Decimal(100))
    #     print(f"   Product: {product.name}")
    #     print(f"   HT Amount: {vat_info[0]}")
    #     print(f"   VAT Amount: {vat_info[1]}")
    
    # Exemple 2: Création d'ajustement
    print("\n2. Adjustment Example:")
    # adj = FinanceAdjustmentService.create_adjustment(
    #     account_id=1,
    #     amount=Decimal("-10.50"),
    #     reason="fee",
    #     description="Monthly banking fees",
    #     user_id=1,
    # )
    # print(f"   Created adjustment: {adj.id}")
    
    # Exemple 3: Historique quotidien
    print("\n3. Daily Balance Example:")
    # daily = FinanceDailyBalanceService.record_daily_balance(
    #     account_id=1,
    #     company_id=1,
    #     tenant_id=1,
    # )
    # print(f"   Daily balance recorded for {daily.balance_date}")

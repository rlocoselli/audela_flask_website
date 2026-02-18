"""
Subscription Service

Gestion des abonnements, plans, facturation et restrictions.
Intégration Stripe pour les paiements.
"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal

from flask import current_app

from audela.extensions import db
from audela.models import Tenant, TenantSubscription, SubscriptionPlan, BillingEvent, User
from audela.services.email_service import EmailService


class SubscriptionService:
    """Service de gestion des abonnements."""

    @staticmethod
    def _default_plan_definitions() -> Dict[str, Dict[str, Any]]:
        """Définitions des plans par défaut pour bootstrap runtime."""
        return {
            "free": {
                "name": "Gratuit",
                "description": "Plan d'essai gratuit de 30 jours",
                "price_monthly": "0.00",
                "price_yearly": "0.00",
                "trial_days": 30,
                "has_finance": False,
                "has_bi": False,
                "max_users": 1,
                "max_companies": 1,
                "max_transactions_per_month": 100,
                "display_order": 1,
            },
            "finance_starter": {
                "name": "Finance Starter",
                "description": "Gestion financière pour petites entreprises",
                "price_monthly": "29.00",
                "price_yearly": "290.00",
                "trial_days": 30,
                "has_finance": True,
                "has_bi": False,
                "max_users": 3,
                "max_companies": 3,
                "max_transactions_per_month": 1000,
                "display_order": 2,
            },
            "finance_pro": {
                "name": "Finance Pro",
                "description": "Gestion financière avancée",
                "price_monthly": "79.00",
                "price_yearly": "790.00",
                "trial_days": 30,
                "has_finance": True,
                "has_bi": False,
                "max_users": 10,
                "max_companies": 10,
                "max_transactions_per_month": 5000,
                "display_order": 3,
            },
            "bi_starter": {
                "name": "BI Starter",
                "description": "Business Intelligence basique",
                "price_monthly": "39.00",
                "price_yearly": "390.00",
                "trial_days": 30,
                "has_finance": False,
                "has_bi": True,
                "max_users": 3,
                "max_companies": 5,
                "max_transactions_per_month": 1000,
                "display_order": 4,
            },
            "bi_pro": {
                "name": "BI Pro",
                "description": "Business Intelligence avancé",
                "price_monthly": "99.00",
                "price_yearly": "990.00",
                "trial_days": 30,
                "has_finance": False,
                "has_bi": True,
                "max_users": 10,
                "max_companies": 20,
                "max_transactions_per_month": 10000,
                "display_order": 5,
            },
            "enterprise": {
                "name": "Enterprise",
                "description": "Toutes les fonctionnalités",
                "price_monthly": "199.00",
                "price_yearly": "1990.00",
                "trial_days": 30,
                "has_finance": True,
                "has_bi": True,
                "max_users": -1,
                "max_companies": -1,
                "max_transactions_per_month": -1,
                "display_order": 6,
            },
        }

    @staticmethod
    def _ensure_default_plans_seeded() -> None:
        """Créer les plans par défaut s'ils n'existent pas encore."""
        defaults = SubscriptionService._default_plan_definitions()
        existing_codes = {code for (code,) in db.session.query(SubscriptionPlan.code).all()}
        missing_codes = [code for code in defaults.keys() if code not in existing_codes]

        if not missing_codes:
            return

        for code in missing_codes:
            data = defaults[code]
            db.session.add(
                SubscriptionPlan(
                    code=code,
                    name=data["name"],
                    description=data["description"],
                    price_monthly=Decimal(data["price_monthly"]),
                    price_yearly=Decimal(data["price_yearly"]),
                    currency="EUR",
                    has_finance=data["has_finance"],
                    has_bi=data["has_bi"],
                    max_users=data["max_users"],
                    max_companies=data["max_companies"],
                    max_transactions_per_month=data["max_transactions_per_month"],
                    storage_gb=1,
                    api_calls_per_day=1000,
                    trial_days=data["trial_days"],
                    is_active=True,
                    is_public=True,
                    display_order=data["display_order"],
                    features_json={},
                )
            )

        db.session.commit()
        current_app.logger.warning(
            "Auto-seeded missing subscription plans at runtime: %s",
            ", ".join(missing_codes)
        )
    
    @staticmethod
    def create_trial_subscription(tenant: Tenant, plan_code: str = "free") -> TenantSubscription:
        """
        Créer un abonnement trial pour un nouveau tenant.
        
        Args:
            tenant: Tenant
            plan_code: Code du plan (default: free)
        
        Returns:
            Subscription créée
        """
        SubscriptionService._ensure_default_plans_seeded()
        plan = SubscriptionPlan.query.filter_by(code=plan_code).first()
        if not plan:
            raise ValueError(f"Plan {plan_code} not found")
        
        trial_start = datetime.utcnow()
        trial_end = trial_start + timedelta(days=plan.trial_days)
        
        subscription = TenantSubscription(
            tenant_id=tenant.id,
            plan_id=plan.id,
            status="trial",
            trial_start_date=trial_start,
            trial_end_date=trial_end,
            current_period_start=trial_start,
            current_period_end=trial_end
        )
        
        db.session.add(subscription)
        
        # Créer événement billing
        event = BillingEvent(
            tenant_id=tenant.id,
            event_type="trial_started",
            metadata_json={
                "plan_code": plan.code,
                "trial_days": plan.trial_days
            }
        )
        db.session.add(event)
        
        db.session.commit()
        
        return subscription
    
    @staticmethod
    def upgrade_to_paid(
        tenant_id: int,
        plan_code: str,
        billing_cycle: str = "monthly",
        stripe_customer_id: Optional[str] = None,
        stripe_subscription_id: Optional[str] = None
    ) -> TenantSubscription:
        """
        Upgrader vers un plan payant.
        
        Args:
            tenant_id: ID du tenant
            plan_code: Code du nouveau plan
            billing_cycle: monthly ou yearly
            stripe_customer_id: ID client Stripe
            stripe_subscription_id: ID subscription Stripe
        
        Returns:
            Subscription mise à jour
        """
        SubscriptionService._ensure_default_plans_seeded()
        new_plan = SubscriptionPlan.query.filter_by(code=plan_code).first()
        if not new_plan:
            raise ValueError(f"Plan {plan_code} not found")

        subscription = TenantSubscription.query.filter_by(tenant_id=tenant_id).first()
        if not subscription:
            tenant = Tenant.query.get(tenant_id)
            if not tenant:
                raise ValueError("Tenant not found")

            subscription = TenantSubscription(
                tenant_id=tenant_id,
                plan_id=new_plan.id,
                status="inactive",
                billing_cycle=billing_cycle,
                current_users_count=0,
                current_companies_count=0,
                transactions_this_month=0,
            )
            db.session.add(subscription)
        
        # Mettre à jour
        subscription.plan_id = new_plan.id
        subscription.status = "active"
        subscription.billing_cycle = billing_cycle
        subscription.stripe_customer_id = stripe_customer_id
        subscription.stripe_subscription_id = stripe_subscription_id
        
        # Dates
        now = datetime.utcnow()
        subscription.current_period_start = now
        
        if billing_cycle == "yearly":
            subscription.current_period_end = now + timedelta(days=365)
        else:
            subscription.current_period_end = now + timedelta(days=30)
        
        subscription.next_billing_date = subscription.current_period_end
        
        # Créer événement
        amount = new_plan.price_yearly if billing_cycle == "yearly" else new_plan.price_monthly
        event = BillingEvent(
            tenant_id=tenant_id,
            subscription_id=subscription.id,
            event_type="subscription_created",
            amount=amount,
            currency=new_plan.currency,
            metadata_json={
                "plan_code": new_plan.code,
                "billing_cycle": billing_cycle
            }
        )
        db.session.add(event)
        
        db.session.commit()
        
        # Envoyer email de confirmation
        admin = User.query.filter_by(tenant_id=tenant_id).first()
        if admin:
            EmailService.send_subscription_confirmation_email(
                user=admin,
                plan_name=new_plan.name,
                amount=float(amount)
            )
        
        return subscription
    
    @staticmethod
    def cancel_subscription(tenant_id: int, reason: Optional[str] = None) -> TenantSubscription:
        """
        Annuler un abonnement.
        
        Args:
            tenant_id: ID du tenant
            reason: Raison de l'annulation
        
        Returns:
            Subscription annulée
        """
        subscription = TenantSubscription.query.filter_by(tenant_id=tenant_id).first()
        if not subscription:
            raise ValueError("Subscription not found")
        
        subscription.status = "cancelled"
        subscription.cancelled_at = datetime.utcnow()
        
        # Créer événement
        event = BillingEvent(
            tenant_id=tenant_id,
            subscription_id=subscription.id,
            event_type="subscription_cancelled",
            metadata_json={"reason": reason}
        )
        db.session.add(event)
        
        db.session.commit()
        
        return subscription
    
    @staticmethod
    def check_feature_access(tenant_id: int, feature: str) -> bool:
        """
        Vérifier l'accès à une feature.
        
        Args:
            tenant_id: ID du tenant
            feature: Nom de la feature (finance, bi, api, etc.)
        
        Returns:
            True si accès autorisé
        """
        subscription = TenantSubscription.query.filter_by(tenant_id=tenant_id).first()
        if not subscription:
            return False
        
        if not subscription.is_active():
            return False
        
        plan = subscription.plan
        
        # Vérifier les features
        if feature == "finance":
            return plan.has_finance
        elif feature == "bi":
            return plan.has_bi
        
        return False
    
    @staticmethod
    def check_limit(tenant_id: int, limit_type: str) -> tuple[bool, int, int]:
        """
        Vérifier une limite.
        
        Args:
            tenant_id: ID du tenant
            limit_type: Type de limite (users, companies, transactions)
        
        Returns:
            (can_add, current_count, max_limit)
        """
        subscription = TenantSubscription.query.filter_by(tenant_id=tenant_id).first()
        if not subscription or not subscription.is_active():
            return False, 0, 0
        
        plan = subscription.plan
        
        if limit_type == "users":
            max_limit = plan.max_users
            current = subscription.current_users_count
            can_add = max_limit == -1 or current < max_limit
            return can_add, current, max_limit
        
        elif limit_type == "companies":
            max_limit = plan.max_companies
            current = subscription.current_companies_count
            can_add = max_limit == -1 or current < max_limit
            return can_add, current, max_limit
        
        elif limit_type == "transactions":
            max_limit = plan.max_transactions_per_month
            current = subscription.transactions_this_month
            can_add = max_limit == -1 or current < max_limit
            return can_add, current, max_limit
        
        return False, 0, 0
    
    @staticmethod
    def increment_usage(tenant_id: int, usage_type: str, amount: int = 1):
        """
        Incrémenter un compteur d'usage.
        
        Args:
            tenant_id: ID du tenant
            usage_type: Type d'usage (users, companies, transactions)
            amount: Montant à incrémenter
        """
        subscription = TenantSubscription.query.filter_by(tenant_id=tenant_id).first()
        if not subscription:
            return
        
        if usage_type == "users":
            subscription.current_users_count += amount
        elif usage_type == "companies":
            subscription.current_companies_count += amount
        elif usage_type == "transactions":
            subscription.transactions_this_month += amount
        
        db.session.commit()
    
    @staticmethod
    def decrement_usage(tenant_id: int, usage_type: str, amount: int = 1):
        """
        Décrémenter un compteur d'usage.
        
        Args:
            tenant_id: ID du tenant
            usage_type: Type d'usage (users, companies, transactions)
            amount: Montant à décrémenter
        """
        subscription = TenantSubscription.query.filter_by(tenant_id=tenant_id).first()
        if not subscription:
            return
        
        if usage_type == "users":
            subscription.current_users_count = max(0, subscription.current_users_count - amount)
        elif usage_type == "companies":
            subscription.current_companies_count = max(0, subscription.current_companies_count - amount)
        elif usage_type == "transactions":
            subscription.transactions_this_month = max(0, subscription.transactions_this_month - amount)
        
        db.session.commit()
    
    @staticmethod
    def check_trial_expiration(tenant_id: int) -> Optional[int]:
        """
        Vérifier l'expiration du trial.
        
        Args:
            tenant_id: ID du tenant
        
        Returns:
            Nombre de jours restants (None si pas en trial)
        """
        subscription = TenantSubscription.query.filter_by(tenant_id=tenant_id).first()
        if not subscription or subscription.status != "trial":
            return None
        
        return subscription.days_left_in_trial()
    
    @staticmethod
    def send_trial_expiration_warnings():
        """
        Envoyer des emails d'avertissement pour les trials qui expirent bientôt.
        À exécuter quotidiennement via une tâche Celery.
        """
        # Trials qui expirent dans 7, 3, ou 1 jour
        warning_days = [7, 3, 1]
        
        for days in warning_days:
            warning_date = datetime.utcnow() + timedelta(days=days)
            
            subscriptions = TenantSubscription.query.filter(
                TenantSubscription.status == "trial",
                TenantSubscription.trial_end_date.between(
                    warning_date,
                    warning_date + timedelta(hours=24)
                )
            ).all()
            
            for sub in subscriptions:
                # Trouver l'admin du tenant
                admin = User.query.filter_by(
                    tenant_id=sub.tenant_id
                ).order_by(User.created_at).first()
                
                if admin:
                    EmailService.send_trial_expiring_email(admin, days)
    
    @staticmethod
    def get_available_plans(include_internal: bool = False) -> list[SubscriptionPlan]:
        """
        Obtenir les plans disponibles.
        
        Args:
            include_internal: Inclure les plans non-publics
        
        Returns:
            Liste des plans
        """
        SubscriptionService._ensure_default_plans_seeded()
        query = SubscriptionPlan.query.filter_by(is_active=True)
        
        if not include_internal:
            query = query.filter_by(is_public=True)
        
        return query.order_by(SubscriptionPlan.price_monthly).all()
    
    @staticmethod
    def create_stripe_checkout_session(
        tenant_id: int,
        plan_code: str,
        billing_cycle: str = "monthly",
        success_url: Optional[str] = None,
        cancel_url: Optional[str] = None
    ) -> str:
        """
        Créer une session Stripe Checkout.
        
        Args:
            tenant_id: ID du tenant
            plan_code: Code du plan
            billing_cycle: monthly ou yearly
        
        Returns:
            URL de redirection Stripe Checkout
        """
        import stripe
        
        stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')
        
        SubscriptionService._ensure_default_plans_seeded()
        plan = SubscriptionPlan.query.filter_by(code=plan_code).first()
        if not plan:
            raise ValueError(f"Plan {plan_code} not found")
        
        tenant = Tenant.query.get(tenant_id)
        if not tenant:
            raise ValueError("Tenant not found")
        
        # Prix selon le cycle
        amount = int(plan.price_yearly * 100) if billing_cycle == "yearly" else int(plan.price_monthly * 100)
        
        # Créer session
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': plan.currency.lower(),
                    'product_data': {
                        'name': plan.name,
                        'description': plan.description,
                    },
                    'recurring': {
                        'interval': 'year' if billing_cycle == "yearly" else 'month',
                    },
                    'unit_amount': amount,
                },
                'quantity': 1,
            }],
            mode='subscription',
            success_url=success_url or current_app.config.get('STRIPE_SUCCESS_URL', 'http://localhost:5000/billing/success'),
            cancel_url=cancel_url or current_app.config.get('STRIPE_CANCEL_URL', 'http://localhost:5000/billing/cancel'),
            client_reference_id=str(tenant_id),
            metadata={
                'tenant_id': tenant_id,
                'plan_code': plan_code,
                'billing_cycle': billing_cycle
            }
        )
        
        return session.url

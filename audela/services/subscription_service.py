"""
Subscription Service

Gestion des abonnements, plans, facturation et restrictions.
Intégration Stripe pour les paiements.
"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal

from flask import current_app, has_request_context
from flask_login import current_user

from audela.extensions import db
from audela.models import Tenant, TenantSubscription, SubscriptionPlan, BillingEvent, User
from audela.services.email_service import EmailService


class SubscriptionService:
    """Service de gestion des abonnements."""

    IFRS9_INCLUDED_PLAN_CODES = {"finance_banking", "credit_pro", "all_in_one_pro", "enterprise"}

    @staticmethod
    def _default_plan_definitions() -> Dict[str, Dict[str, Any]]:
        """Définitions des plans par défaut pour bootstrap runtime."""
        return {
            "free": {
                "name": "Gratuit",
                "description": "Essai gratuit 30 jours avec acces complet, limite a 1 utilisateur et volume de transactions plafonne",
                "price_monthly": "0.00",
                "price_yearly": "0.00",
                "trial_days": 30,
                "has_finance": True,
                "has_bi": True,
                "max_users": 1,
                "max_companies": 1,
                "max_transactions_per_month": 100,
                "features_json": {
                    "premium_support": False,
                    "has_credit": True,
                    "has_project": True,
                    "has_ifrs9": True,
                    "bi_tier": "lite",
                },
                "display_order": 1,
            },
            "finance_starter": {
                "name": "Finance Personal",
                "description": "Pilotage de finances personnelles et micro-activites",
                "price_monthly": "19.00",
                "price_yearly": "180.00",
                "trial_days": 30,
                "has_finance": True,
                "has_bi": False,
                "max_users": 1,
                "max_companies": 1,
                "max_transactions_per_month": -1,
                "features_json": {
                    "premium_support": False,
                },
                "display_order": 2,
            },
            "finance_pro": {
                "name": "Finance PME",
                "description": "Gestion financiere pour PME avec collaboration equipe",
                "price_monthly": "59.00",
                "price_yearly": "540.00",
                "trial_days": 30,
                "has_finance": True,
                "has_bi": False,
                "max_users": 10,
                "max_companies": 15,
                "max_transactions_per_month": -1,
                "features_json": {
                    "premium_support": False,
                },
                "display_order": 3,
            },
            "finance_banking": {
                "name": "Finance Banking",
                "description": "Pilotage financier pour institutions bancaires et structures multi-entites",
                "price_monthly": "149.00",
                "price_yearly": "1420.00",
                "trial_days": 30,
                "has_finance": True,
                "has_bi": False,
                "max_users": 50,
                "max_companies": 100,
                "max_transactions_per_month": -1,
                "features_json": {
                    "premium_support": True,
                    "has_ifrs9": True,
                },
                "display_order": 4,
            },
            "credit_starter": {
                "name": "Audela Credit Starter",
                "description": "Origination de credit pour petites equipes bancaires",
                "price_monthly": "49.00",
                "price_yearly": "468.00",
                "trial_days": 30,
                "has_finance": False,
                "has_bi": False,
                "max_users": 3,
                "max_companies": 5,
                "max_transactions_per_month": -1,
                "features_json": {
                    "premium_support": False,
                    "has_credit": True,
                },
                "display_order": 4,
            },
            "credit_pro": {
                "name": "Audela Credit Pro",
                "description": "Origination de credit avancee avec workflow complet",
                "price_monthly": "119.00",
                "price_yearly": "1140.00",
                "trial_days": 30,
                "has_finance": False,
                "has_bi": False,
                "max_users": 12,
                "max_companies": 20,
                "max_transactions_per_month": -1,
                "features_json": {
                    "premium_support": False,
                    "has_credit": True,
                    "has_ifrs9": True,
                },
                "display_order": 5,
            },
            "bi_starter": {
                "name": "BI Lite",
                "description": "Business Intelligence simple et guidee par IA pour equipes metier",
                "price_monthly": "39.00",
                "price_yearly": "372.00",
                "trial_days": 30,
                "has_finance": False,
                "has_bi": True,
                "max_users": 3,
                "max_companies": 5,
                "max_transactions_per_month": -1,
                "features_json": {
                    "premium_support": False,
                    "has_credit": False,
                    "bi_tier": "lite",
                },
                "display_order": 6,
            },
            "bi_pro": {
                "name": "BI Enterprise",
                "description": "Business Intelligence entreprise avec capacites avancees et gouvernance data",
                "price_monthly": "109.00",
                "price_yearly": "1040.00",
                "trial_days": 30,
                "has_finance": False,
                "has_bi": True,
                "max_users": 10,
                "max_companies": 20,
                "max_transactions_per_month": -1,
                "features_json": {
                    "premium_support": True,
                    "has_credit": False,
                    "bi_tier": "enterprise",
                },
                "display_order": 7,
            },
            "project_start": {
                "name": "Project Start",
                "description": "Gestion de projet simple (Kanban, Gantt, livrables)",
                "price_monthly": "15.00",
                "price_yearly": "144.00",
                "trial_days": 30,
                "has_finance": False,
                "has_bi": False,
                "max_users": 3,
                "max_companies": 3,
                "max_transactions_per_month": -1,
                "features_json": {
                    "premium_support": False,
                    "has_project": True,
                },
                "display_order": 8,
            },
            "project_team": {
                "name": "Project Team",
                "description": "Gestion de projet multi-équipes avec cérémonies Scrum",
                "price_monthly": "39.00",
                "price_yearly": "372.00",
                "trial_days": 30,
                "has_finance": False,
                "has_bi": False,
                "max_users": 10,
                "max_companies": 10,
                "max_transactions_per_month": -1,
                "features_json": {
                    "premium_support": False,
                    "has_project": True,
                },
                "display_order": 9,
            },
            "all_in_one_starter": {
                "name": "All-in-One Starter",
                "description": "Finance + BI + Audela Credit + Projet pour equipes en croissance",
                "price_monthly": "89.00",
                "price_yearly": "852.00",
                "trial_days": 30,
                "has_finance": True,
                "has_bi": True,
                "max_users": 10,
                "max_companies": 10,
                "max_transactions_per_month": -1,
                "features_json": {
                    "premium_support": False,
                    "has_project": True,
                    "has_credit": True,
                    "has_ifrs9": True,
                    "bi_tier": "lite",
                },
                "display_order": 10,
            },
            "all_in_one_pro": {
                "name": "All-in-One Pro",
                "description": "Suite complete Finance + BI + Audela Credit + Projet pour organisations avancees",
                "price_monthly": "179.00",
                "price_yearly": "1716.00",
                "trial_days": 30,
                "has_finance": True,
                "has_bi": True,
                "max_users": 30,
                "max_companies": 30,
                "max_transactions_per_month": -1,
                "features_json": {
                    "premium_support": True,
                    "has_project": True,
                    "has_credit": True,
                    "has_ifrs9": True,
                    "bi_tier": "enterprise",
                },
                "display_order": 11,
            },
            "enterprise": {
                "name": "Enterprise",
                "description": "Toutes les fonctionnalites, incluant Audela Credit",
                "price_monthly": "299.00",
                "price_yearly": "2868.00",
                "trial_days": 30,
                "has_finance": True,
                "has_bi": True,
                "max_users": -1,
                "max_companies": -1,
                "max_transactions_per_month": -1,
                "features_json": {
                    "premium_support": True,
                    "has_project": True,
                    "has_credit": True,
                    "has_ifrs9": True,
                    "bi_tier": "enterprise",
                },
                "display_order": 12,
            },
        }

    @staticmethod
    def _ensure_default_plans_seeded() -> None:
        """Créer les plans par défaut s'ils n'existent pas encore."""
        defaults = SubscriptionService._default_plan_definitions()
        existing_codes = {code for (code,) in db.session.query(SubscriptionPlan.code).all()}
        missing_codes = [code for code in defaults.keys() if code not in existing_codes]
        changed_codes: list[str] = []

        for code in missing_codes:
            data = defaults[code]
            monthly_value = Decimal(data["price_monthly"])
            features = dict(data.get("features_json") or {})
            features["premium_support"] = monthly_value > Decimal("100")
            db.session.add(
                SubscriptionPlan(
                    code=code,
                    name=data["name"],
                    description=data["description"],
                    price_monthly=monthly_value,
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
                    features_json=features,
                )
            )

        # Normalize key limits/features for existing plans to keep policy consistent.
        for code, data in defaults.items():
            plan = SubscriptionPlan.query.filter_by(code=code).first()
            if not plan:
                continue

            changed = False
            desired_monthly = Decimal(data["price_monthly"])
            desired_yearly = Decimal(data["price_yearly"])
            if Decimal(plan.price_monthly or 0) != desired_monthly:
                plan.price_monthly = desired_monthly
                changed = True
            if Decimal(plan.price_yearly or 0) != desired_yearly:
                plan.price_yearly = desired_yearly
                changed = True

            if str(plan.name or "") != str(data["name"]):
                plan.name = str(data["name"])
                changed = True
            if str(plan.description or "") != str(data["description"]):
                plan.description = str(data["description"])
                changed = True
            if bool(plan.has_finance) != bool(data["has_finance"]):
                plan.has_finance = bool(data["has_finance"])
                changed = True
            if bool(plan.has_bi) != bool(data["has_bi"]):
                plan.has_bi = bool(data["has_bi"])
                changed = True
            if int(plan.max_users or 0) != int(data["max_users"]):
                plan.max_users = int(data["max_users"])
                changed = True
            if int(plan.max_companies or 0) != int(data["max_companies"]):
                plan.max_companies = int(data["max_companies"])
                changed = True
            if int(plan.trial_days or 0) != int(data["trial_days"]):
                plan.trial_days = int(data["trial_days"])
                changed = True
            if int(plan.display_order or 0) != int(data["display_order"]):
                plan.display_order = int(data["display_order"])
                changed = True

            desired_tx = int(data["max_transactions_per_month"])
            if int(plan.max_transactions_per_month or 0) != desired_tx:
                plan.max_transactions_per_month = desired_tx
                changed = True

            if code == "enterprise":
                if int(plan.max_users or 0) != -1:
                    plan.max_users = -1
                    changed = True
                if int(plan.max_companies or 0) != -1:
                    plan.max_companies = -1
                    changed = True

            features = dict(plan.features_json) if isinstance(plan.features_json, dict) else {}
            original_features = dict(features)
            desired_features = data.get("features_json") or {}
            for feature_key, feature_value in desired_features.items():
                if features.get(feature_key) != feature_value:
                    features[feature_key] = feature_value

            # Policy: premium support for plans above 100 EUR monthly.
            features["premium_support"] = desired_monthly > Decimal("100")

            if features != original_features:
                plan.features_json = features
                changed = True

            if changed:
                changed_codes.append(code)

        if missing_codes or changed_codes:
            db.session.commit()

        if missing_codes:
            current_app.logger.warning(
                "Auto-seeded missing subscription plans at runtime: %s",
                ", ".join(missing_codes)
            )
        if changed_codes:
            current_app.logger.info(
                "Normalized subscription plan policy at runtime: %s",
                ", ".join(sorted(set(changed_codes)))
            )

    @staticmethod
    def _is_test_user_override(tenant_id: int) -> bool:
        """Return True when current request user is marked as a test user in tenant UAM."""
        if not has_request_context():
            return False
        try:
            if not getattr(current_user, "is_authenticated", False):
                return False
            if int(getattr(current_user, "tenant_id", 0) or 0) != int(tenant_id):
                return False
            tenant = Tenant.query.get(int(tenant_id))
            if not tenant:
                return False
            settings = tenant.settings_json if isinstance(tenant.settings_json, dict) else {}
            uam = settings.get("uam") if isinstance(settings.get("uam"), dict) else {}
            test_users = uam.get("test_users") if isinstance(uam.get("test_users"), list) else []
            return str(int(current_user.id)) in {str(x) for x in test_users}
        except Exception:
            return False
    
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
        if SubscriptionService._is_test_user_override(tenant_id):
            return True

        subscription = TenantSubscription.query.filter_by(tenant_id=tenant_id).first()
        if not subscription:
            return False
        
        if not subscription.is_active():
            return False
        
        plan = subscription.plan
        
        # Vérifier les features
        if feature == "finance":
            return bool(plan.has_finance or plan.code == "free")
        elif feature == "bi":
            return bool(plan.has_bi or plan.code == "free")
        elif feature == "credit":
            features = plan.features_json if isinstance(plan.features_json, dict) else {}
            return bool(features.get("has_credit", plan.code == "free"))
        elif feature == "ifrs9":
            features = plan.features_json if isinstance(plan.features_json, dict) else {}
            return bool(features.get("has_ifrs9", plan.code == "free" or plan.code in SubscriptionService.IFRS9_INCLUDED_PLAN_CODES))
        elif feature == "project":
            features = plan.features_json if isinstance(plan.features_json, dict) else {}
            return bool(features.get("has_project", plan.code == "free"))
        elif feature == "premium_support":
            features = plan.features_json if isinstance(plan.features_json, dict) else {}
            return bool(features.get("premium_support", False))
        
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
        if SubscriptionService._is_test_user_override(tenant_id):
            return True, 0, -1

        subscription = TenantSubscription.query.filter_by(tenant_id=tenant_id).first()
        if not subscription or not subscription.is_active():
            return False, 0, 0

        # Keep counters synchronized with real data to avoid stale zero values.
        SubscriptionService.sync_usage_counters(tenant_id)
        db.session.refresh(subscription)
        
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
            # Business rule: all paid plans have unlimited transactions.
            if str(getattr(plan, "code", "")) != "free" and float(plan.price_monthly or 0) > 0:
                max_limit = -1
            else:
                max_limit = plan.max_transactions_per_month
            current = subscription.transactions_this_month
            can_add = max_limit == -1 or current < max_limit
            return can_add, current, max_limit
        
        return False, 0, 0

    @staticmethod
    def sync_usage_counters(tenant_id: int) -> tuple[int, int, int]:
        """Synchronize stored usage counters with real data.

        Returns:
            (users_count, companies_count, transactions_this_month)
        """
        from audela.models.finance import FinanceCompany, FinanceTransaction

        subscription = TenantSubscription.query.filter_by(tenant_id=tenant_id).first()
        if not subscription:
            return 0, 0, 0

        users_count = User.query.filter_by(tenant_id=tenant_id).count()
        companies_count = FinanceCompany.query.filter_by(tenant_id=tenant_id).count()

        now = datetime.utcnow().date()
        month_start = now.replace(day=1)
        if month_start.month == 12:
            next_month = month_start.replace(year=month_start.year + 1, month=1, day=1)
        else:
            next_month = month_start.replace(month=month_start.month + 1, day=1)

        tx_month = (
            FinanceTransaction.query
            .filter(FinanceTransaction.tenant_id == tenant_id)
            .filter(FinanceTransaction.txn_date >= month_start)
            .filter(FinanceTransaction.txn_date < next_month)
            .count()
        )

        changed = False
        if int(subscription.current_users_count or 0) != int(users_count):
            subscription.current_users_count = int(users_count)
            changed = True
        if int(subscription.current_companies_count or 0) != int(companies_count):
            subscription.current_companies_count = int(companies_count)
            changed = True
        if int(subscription.transactions_this_month or 0) != int(tx_month):
            subscription.transactions_this_month = int(tx_month)
            changed = True

        if changed:
            db.session.commit()

        return int(users_count), int(companies_count), int(tx_month)
    
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

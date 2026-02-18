"""
Tenant Service

Gestion complète des tenants: création, configuration, utilisateurs, permissions.
"""

from typing import List, Optional, Any
from datetime import datetime
from types import SimpleNamespace
import re

from flask import current_app
from sqlalchemy import func

from audela.extensions import db
from audela.models import Tenant, User, Role, UserRole
from audela.models.subscription import EmailVerificationToken, UserInvitation
from audela.services.subscription_service import SubscriptionService
from audela.services.email_service import EmailService, EmailVerificationService


def dict_to_obj(d: Any) -> Any:
    """
    Convertir récursivement un dict en objet avec accès par attributs.
    Permet l'utilisation de obj.key au lieu de obj['key'] dans les templates.
    """
    if isinstance(d, dict):
        return SimpleNamespace(**{k: dict_to_obj(v) for k, v in d.items()})
    elif isinstance(d, list):
        return [dict_to_obj(item) for item in d]
    else:
        return d


class TenantService:
    """Service de gestion des tenants."""
    
    @staticmethod
    def create_tenant(
        name: str,
        email: str,
        password: str,
        plan_code: str = "free",
        send_verification: bool = True
    ) -> tuple[Tenant, User]:
        """
        Créer un nouveau tenant avec son premier utilisateur admin.
        
        Args:
            name: Nom du tenant
            email: Email de l'admin
            password: Mot de passe
            plan_code: Code du plan initial
            send_verification: Envoyer email de vérification
        
        Returns:
            (Tenant, User admin)
        """
        # Générer slug unique
        slug = TenantService._generate_slug(name)
        
        # Créer tenant
        tenant = Tenant(
            slug=slug,
            name=name,
            plan=plan_code,
            settings_json={}
        )
        db.session.add(tenant)
        db.session.flush()
        
        # Créer abonnement trial
        subscription = SubscriptionService.create_trial_subscription(tenant, plan_code)
        
        # Créer utilisateur admin
        user = TenantService.create_user(
            tenant_id=tenant.id,
            email=email,
            password=password,
            role_codes=["tenant_admin"],
            status="pending_verification" if send_verification else "active"
        )
        
        # Incrémenter compteur utilisateurs
        SubscriptionService.increment_usage(tenant.id, "users")
        
        db.session.commit()
        
        # Envoyer email de vérification
        if send_verification:
            token = EmailVerificationService.create_verification_token(user)
            EmailService.send_verification_email(user, token.token)
        
        current_app.logger.info(f"Created tenant {tenant.slug} with admin {user.email}")
        
        return tenant, user
    
    @staticmethod
    def create_user(
        tenant_id: int,
        email: str,
        password: str,
        role_codes: List[str],
        status: str = "active"
    ) -> User:
        """
        Créer un utilisateur dans un tenant.
        
        Args:
            tenant_id: ID du tenant
            email: Email
            password: Mot de passe
            role_codes: Liste des codes de rôles
            status: Status initial
        
        Returns:
            User créé
        """
        # Vérifier email unique dans le tenant
        existing = User.query.filter_by(
            tenant_id=tenant_id,
            email=email
        ).first()
        
        if existing:
            raise ValueError(f"Email {email} already exists in this tenant")
        
        # Créer user
        user = User(
            tenant_id=tenant_id,
            email=email,
            status=status
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.flush()
        
        # Assigner rôles
        for code in role_codes:
            role = Role.query.filter_by(code=code).first()
            if role:
                user_role = UserRole(user_id=user.id, role_id=role.id)
                db.session.add(user_role)
        
        db.session.commit()
        
        return user
    
    @staticmethod
    def invite_user(
        tenant_id: int,
        email: str,
        role_codes: List[str],
        invited_by_user_id: int
    ) -> UserInvitation:
        """
        Inviter un utilisateur à rejoindre le tenant.
        
        Args:
            tenant_id: ID du tenant
            email: Email de l'invité
            role_codes: Rôles à assigner
            invited_by_user_id: ID de l'inviteur
        
        Returns:
            Invitation créée
        """
        # Vérifier limite utilisateurs
        can_add, current, max_limit = SubscriptionService.check_limit(tenant_id, "users")
        if not can_add:
            raise ValueError(f"User limit reached ({current}/{max_limit})")
        
        # Vérifier si email déjà utilisé
        existing = User.query.filter_by(
            tenant_id=tenant_id,
            email=email
        ).first()
        
        if existing:
            raise ValueError(f"Email {email} already exists in this tenant")
        
        # Invalider invitations existantes
        UserInvitation.query.filter_by(
            tenant_id=tenant_id,
            email=email,
            status="pending"
        ).update({"status": "revoked"})
        
        # Créer invitation
        from audela.services.email_service import InvitationService
        invitation = InvitationService.create_invitation(
            tenant_id=tenant_id,
            email=email,
            role_codes=role_codes,
            invited_by_user_id=invited_by_user_id
        )
        
        # Envoyer email
        EmailService.send_invitation_email(invitation)
        
        return invitation
    
    @staticmethod
    def remove_user(tenant_id: int, user_id: int) -> bool:
        """
        Retirer un utilisateur du tenant.
        
        Args:
            tenant_id: ID du tenant
            user_id: ID de l'utilisateur
        
        Returns:
            True si retiré
        """
        user = User.query.filter_by(id=user_id, tenant_id=tenant_id).first()
        if not user:
            return False
        
        # Ne pas supprimer le dernier admin
        admin_role = Role.query.filter_by(code="tenant_admin").first()
        if admin_role:
            admin_count = User.query.join(UserRole).filter(
                User.tenant_id == tenant_id,
                UserRole.role_id == admin_role.id
            ).count()
            
            if admin_count <= 1 and user.has_role("tenant_admin"):
                raise ValueError("Cannot remove the last admin user")
        
        # Supprimer
        db.session.delete(user)
        
        # Décrémenter compteur
        SubscriptionService.decrement_usage(tenant_id, "users")
        
        db.session.commit()
        
        return True
    
    @staticmethod
    def update_user_roles(tenant_id: int, user_id: int, role_codes: List[str]) -> User:
        """
        Mettre à jour les rôles d'un utilisateur.
        
        Args:
            tenant_id: ID du tenant
            user_id: ID de l'utilisateur
            role_codes: Nouveaux rôles
        
        Returns:
            User mis à jour
        """
        user = User.query.filter_by(id=user_id, tenant_id=tenant_id).first()
        if not user:
            raise ValueError("User not found")
        
        # Supprimer anciens rôles
        UserRole.query.filter_by(user_id=user_id).delete()
        
        # Ajouter nouveaux rôles
        for code in role_codes:
            role = Role.query.filter_by(code=code).first()
            if role:
                user_role = UserRole(user_id=user.id, role_id=role.id)
                db.session.add(user_role)
        
        db.session.commit()
        
        return user
    
    @staticmethod
    def update_tenant_settings(tenant_id: int, settings: dict) -> Tenant:
        """
        Mettre à jour les paramètres du tenant.
        
        Args:
            tenant_id: ID du tenant
            settings: Nouveaux paramètres
        
        Returns:
            Tenant mis à jour
        """
        tenant = Tenant.query.get(tenant_id)
        if not tenant:
            raise ValueError("Tenant not found")
        
        # Fusionner avec settings existants
        current_settings = tenant.settings_json or {}
        current_settings.update(settings)
        tenant.settings_json = current_settings
        
        db.session.commit()
        
        return tenant
    
    @staticmethod
    def get_tenant_stats(tenant_id: int) -> SimpleNamespace:
        """
        Obtenir les statistiques du tenant.
        
        Args:
            tenant_id: ID du tenant
        
        Returns:
            Objet avec les stats (accessible par attributs)
        """
        from audela.models import FinanceCompany, FinanceTransaction
        
        tenant = Tenant.query.get(tenant_id)
        if not tenant:
            return dict_to_obj({})
        
        subscription = tenant.subscription
        
        # Base stats
        stats = {
            "tenant_name": tenant.name,
            "tenant_slug": tenant.slug,
            "users_count": User.query.filter_by(tenant_id=tenant_id).count(),
            "created_at": tenant.created_at,
            "plan_name": "No Plan",
            "plan_code": None,
            "subscription_status": "inactive",
            "is_trial": False,
            "trial_days_left": None,
            "has_finance": False,
            "has_bi": False,
            "usage": {
                "users": {"current": 0, "max": 0},
                "companies": {"current": 0, "max": 0},
                "transactions": {"current": 0, "max": 0}
            }
        }
        
        # Override with actual subscription data if available
        if subscription:
            stats.update({
                "plan_name": subscription.plan.name,
                "plan_code": subscription.plan.code,
                "subscription_status": subscription.status,
                "is_trial": subscription.is_trial(),
                "trial_days_left": subscription.days_left_in_trial(),
                "has_finance": subscription.plan.has_finance,
                "has_bi": subscription.plan.has_bi,
                "usage": {
                    "users": {
                        "current": subscription.current_users_count,
                        "max": subscription.plan.max_users
                    },
                    "companies": {
                        "current": subscription.current_companies_count,
                        "max": subscription.plan.max_companies
                    },
                    "transactions": {
                        "current": subscription.transactions_this_month,
                        "max": subscription.plan.max_transactions_per_month
                    }
                }
            })
        
        # Stats Finance (si disponible)
        if SubscriptionService.check_feature_access(tenant_id, "finance"):
            companies_count = FinanceCompany.query.filter_by(tenant_id=tenant_id).count()
            transactions_count = FinanceTransaction.query.join(
                FinanceCompany
            ).filter(
                FinanceCompany.tenant_id == tenant_id
            ).count()
            
            stats["finance_stats"] = {
                "companies": companies_count,
                "transactions": transactions_count
            }
        
        # Convertir le dict en objet pour accès par attributs dans les templates
        return dict_to_obj(stats)
    
    @staticmethod
    def list_users(tenant_id: int) -> List[dict]:
        """
        Lister les utilisateurs du tenant.
        
        Args:
            tenant_id: ID du tenant
        
        Returns:
            Liste des utilisateurs avec leurs rôles
        """
        users = User.query.filter_by(tenant_id=tenant_id).all()
        
        result = []
        for user in users:
            result.append({
                "id": user.id,
                "email": user.email,
                "status": user.status,
                "roles": [r.code for r in user.roles],
                "created_at": user.created_at,
                "last_login_at": user.last_login_at
            })
        
        return result
    
    @staticmethod
    def _generate_slug(name: str) -> str:
        """
        Générer un slug unique à partir du nom.
        
        Args:
            name: Nom du tenant
        
        Returns:
            Slug unique
        """
        # Nettoyer le nom
        slug = re.sub(r'[^\w\s-]', '', name.lower())
        slug = re.sub(r'[\s_-]+', '-', slug)
        slug = slug.strip('-')
        
        # Vérifier unicité
        base_slug = slug
        counter = 1
        
        while Tenant.query.filter_by(slug=slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1
        
        return slug
    
    @staticmethod
    def delete_tenant(tenant_id: int) -> bool:
        """
        Supprimer un tenant et toutes ses données.
        
        ATTENTION: Opération irréversible!
        
        Args:
            tenant_id: ID du tenant
        
        Returns:
            True si supprimé
        """
        tenant = Tenant.query.get(tenant_id)
        if not tenant:
            return False
        
        # Annuler abonnement si actif
        if tenant.subscription and tenant.subscription.is_active():
            SubscriptionService.cancel_subscription(tenant_id, "tenant_deleted")
        
        # Supprimer (cascade delete prend en charge les relations)
        db.session.delete(tenant)
        db.session.commit()
        
        current_app.logger.warning(f"Deleted tenant {tenant.slug} (ID: {tenant_id})")
        
        return True

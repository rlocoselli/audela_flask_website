"""
Subscription & Billing Models

Gestion des abonnements, plans, et facturation pour AUDELA.
Supporte: Trial gratuit, Finance module, BI module, gestion multi-utilisateurs.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import UniqueConstraint

from ..extensions import db


class SubscriptionPlan(db.Model):
    """Plans d'abonnement disponibles."""
    
    __tablename__ = "subscription_plans"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), nullable=False, unique=True, index=True)  # free, finance_starter, bi_pro, etc.
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    # Pricing
    price_monthly = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    price_yearly = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    currency = db.Column(db.String(3), nullable=False, default="EUR")
    
    # Features
    has_finance = db.Column(db.Boolean, nullable=False, default=False)
    has_bi = db.Column(db.Boolean, nullable=False, default=False)
    max_users = db.Column(db.Integer, nullable=False, default=1)  # -1 = unlimited
    max_companies = db.Column(db.Integer, nullable=False, default=1)  # -1 = unlimited
    max_transactions_per_month = db.Column(db.Integer, nullable=False, default=100)  # -1 = unlimited
    
    # Storage & limits
    storage_gb = db.Column(db.Integer, nullable=False, default=1)  # -1 = unlimited
    api_calls_per_day = db.Column(db.Integer, nullable=False, default=1000)  # -1 = unlimited
    
    # Trial
    trial_days = db.Column(db.Integer, nullable=False, default=30)
    
    # Status
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_public = db.Column(db.Boolean, nullable=False, default=True)  # Visible sur la page pricing
    display_order = db.Column(db.Integer, nullable=False, default=0)
    
    # Metadata
    features_json = db.Column(db.JSON, nullable=True)  # Features détaillées en JSON
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<SubscriptionPlan {self.code}>"


class TenantSubscription(db.Model):
    """Abonnement d'un tenant."""
    
    __tablename__ = "tenant_subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("subscription_plans.id"), nullable=False, index=True)
    
    # Status
    status = db.Column(db.String(32), nullable=False, default="trial")  # trial, active, suspended, cancelled
    
    # Dates
    trial_start_date = db.Column(db.DateTime, nullable=True)
    trial_end_date = db.Column(db.DateTime, nullable=True)
    current_period_start = db.Column(db.DateTime, nullable=True)
    current_period_end = db.Column(db.DateTime, nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    
    # Billing
    billing_cycle = db.Column(db.String(16), nullable=False, default="monthly")  # monthly, yearly
    next_billing_date = db.Column(db.DateTime, nullable=True)
    
    # Payment
    stripe_customer_id = db.Column(db.String(128), nullable=True)  # ID client Stripe
    stripe_subscription_id = db.Column(db.String(128), nullable=True)  # ID abonnement Stripe
    payment_method = db.Column(db.String(32), nullable=True)  # card, sepa, etc.
    
    # Usage tracking
    current_users_count = db.Column(db.Integer, nullable=False, default=0)
    current_companies_count = db.Column(db.Integer, nullable=False, default=0)
    transactions_this_month = db.Column(db.Integer, nullable=False, default=0)
    
    # Metadata
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = db.relationship("Tenant", back_populates="subscription")
    plan = db.relationship("SubscriptionPlan")

    def is_trial(self) -> bool:
        """Vérifier si en période trial."""
        return self.status == "trial"

    def is_active(self) -> bool:
        """Vérifier si l'abonnement est actif."""
        return self.status in ["trial", "active"]
    
    def is_trial_expired(self) -> bool:
        """Vérifier si le trial a expiré."""
        if not self.trial_end_date:
            return False
        return datetime.utcnow() > self.trial_end_date
    
    def days_left_in_trial(self) -> Optional[int]:
        """Nombre de jours restants dans le trial."""
        if not self.trial_end_date or self.status != "trial":
            return None
        delta = self.trial_end_date - datetime.utcnow()
        return max(0, delta.days)
    
    def can_add_user(self) -> bool:
        """Vérifier si on peut ajouter un utilisateur."""
        if self.plan.max_users == -1:
            return True
        return self.current_users_count < self.plan.max_users
    
    def can_add_company(self) -> bool:
        """Vérifier si on peut ajouter une company."""
        if self.plan.max_companies == -1:
            return True
        return self.current_companies_count < self.plan.max_companies

    def __repr__(self):
        return f"<TenantSubscription tenant={self.tenant_id} plan={self.plan.code} status={self.status}>"


class EmailVerificationToken(db.Model):
    """Tokens de vérification d'email."""
    
    __tablename__ = "email_verification_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token = db.Column(db.String(128), nullable=False, unique=True, index=True)
    
    email = db.Column(db.String(255), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    verified_at = db.Column(db.DateTime, nullable=True)
    
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("verification_tokens", lazy="dynamic"))

    def is_expired(self) -> bool:
        """Vérifier si le token a expiré."""
        return datetime.utcnow() > self.expires_at
    
    def is_verified(self) -> bool:
        """Vérifier si déjà vérifié."""
        return self.verified_at is not None

    @staticmethod
    def generate_token() -> str:
        """Générer un token unique."""
        import secrets
        return secrets.token_urlsafe(32)

    def __repr__(self):
        return f"<EmailVerificationToken user={self.user_id}>"


class UserInvitation(db.Model):
    """Invitations d'utilisateurs."""
    
    __tablename__ = "user_invitations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_invitation_email_per_tenant"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    invited_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    email = db.Column(db.String(255), nullable=False)
    token = db.Column(db.String(128), nullable=False, unique=True, index=True)
    
    # Roles à assigner
    role_codes = db.Column(db.JSON, nullable=False, default=list)  # ["tenant_admin", "finance_viewer"]
    
    # Status
    status = db.Column(db.String(32), nullable=False, default="pending")  # pending, accepted, expired, revoked
    expires_at = db.Column(db.DateTime, nullable=False)
    accepted_at = db.Column(db.DateTime, nullable=True)
    accepted_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    tenant = db.relationship("Tenant", backref=db.backref("invitations", lazy="dynamic"))
    invited_by = db.relationship("User", foreign_keys=[invited_by_user_id])
    accepted_by = db.relationship("User", foreign_keys=[accepted_by_user_id])

    def is_expired(self) -> bool:
        """Vérifier si l'invitation a expiré."""
        return datetime.utcnow() > self.expires_at
    
    def is_pending(self) -> bool:
        """Vérifier si en attente."""
        return self.status == "pending" and not self.is_expired()

    @staticmethod
    def generate_token() -> str:
        """Générer un token unique."""
        import secrets
        return secrets.token_urlsafe(32)

    def __repr__(self):
        return f"<UserInvitation email={self.email} tenant={self.tenant_id} status={self.status}>"


class BillingEvent(db.Model):
    """Historique des événements de facturation."""
    
    __tablename__ = "billing_events"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey("tenant_subscriptions.id", ondelete="CASCADE"), nullable=True, index=True)
    
    event_type = db.Column(db.String(64), nullable=False)  # trial_started, subscription_created, payment_succeeded, etc.
    amount = db.Column(db.Numeric(10, 2), nullable=True)
    currency = db.Column(db.String(3), nullable=True)
    
    # Stripe event
    stripe_event_id = db.Column(db.String(128), nullable=True)
    stripe_event_type = db.Column(db.String(128), nullable=True)
    
    # Metadata
    metadata_json = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    tenant = db.relationship("Tenant", backref=db.backref("billing_events", lazy="dynamic"))
    subscription = db.relationship("TenantSubscription", backref=db.backref("billing_events", lazy="dynamic"))

    def __repr__(self):
        return f"<BillingEvent {self.event_type} tenant={self.tenant_id}>"

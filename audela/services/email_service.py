"""
Email Service

Service pour envoyer des emails transactionnels (vérification, invitations, receipts, etc.)
Supporte: Flask-Mail, templates Jinja2, queuing optionnel.
"""

from typing import Optional, List
from datetime import datetime, timedelta
import os

from flask import current_app, render_template, url_for
from flask_mail import Message

from audela.extensions import db, mail
from audela.models import User, EmailVerificationToken, UserInvitation


class EmailService:
    """Service d'envoi d'emails."""
    
    @staticmethod
    def send_email(
        to: str | List[str],
        subject: str,
        template: str,
        **context
    ) -> bool:
        """
        Envoyer un email.
        
        Args:
            to: Email(s) destinataire(s)
            subject: Sujet de l'email
            template: Nom du template (sans extension)
            **context: Variables pour le template
        
        Returns:
            True si envoyé avec succès
        """
        try:
            if isinstance(to, str):
                to = [to]
            
            # Render HTML et text
            html_body = render_template(f"emails/{template}.html", **context)
            text_body = render_template(f"emails/{template}.txt", **context)
            
            msg = Message(
                subject=subject,
                recipients=to,
                html=html_body,
                body=text_body,
                sender=current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@audela.com')
            )
            
            mail.send(msg)
            return True
            
        except Exception as e:
            current_app.logger.error(f"Failed to send email to {to}: {str(e)}")
            return False
    
    @staticmethod
    def send_verification_email(user: User, token: str) -> bool:
        """
        Envoyer email de vérification.
        
        Args:
            user: Utilisateur
            token: Token de vérification
        
        Returns:
            True si envoyé
        """
        verification_url = url_for(
            'auth.verify_email',
            token=token,
            _external=True
        )
        
        return EmailService.send_email(
            to=user.email,
            subject="Vérifiez votre adresse email - AUDELA",
            template="verify_email",
            user=user,
            verification_url=verification_url,
            tenant_name=user.tenant.name
        )
    
    @staticmethod
    def send_invitation_email(invitation: UserInvitation) -> bool:
        """
        Envoyer email d'invitation.
        
        Args:
            invitation: Invitation
        
        Returns:
            True si envoyé
        """
        invitation_url = url_for(
            'auth.accept_invitation',
            token=invitation.token,
            _external=True
        )
        
        invited_by_name = invitation.invited_by.email if invitation.invited_by else "AUDELA"
        
        return EmailService.send_email(
            to=invitation.email,
            subject=f"Invitation à rejoindre {invitation.tenant.name} sur AUDELA",
            template="user_invitation",
            invitation=invitation,
            invitation_url=invitation_url,
            invited_by_name=invited_by_name,
            tenant_name=invitation.tenant.name
        )
    
    @staticmethod
    def send_welcome_email(user: User) -> bool:
        """
        Envoyer email de bienvenue après vérification.
        
        Args:
            user: Utilisateur
        
        Returns:
            True si envoyé
        """
        login_url = url_for('auth.login', _external=True)
        
        return EmailService.send_email(
            to=user.email,
            subject="Bienvenue sur AUDELA!",
            template="welcome",
            user=user,
            login_url=login_url,
            tenant_name=user.tenant.name
        )
    
    @staticmethod
    def send_trial_expiring_email(user: User, days_left: int) -> bool:
        """
        Envoyer email avant expiration du trial.
        
        Args:
            user: Utilisateur (admin du tenant)
            days_left: Jours restants
        
        Returns:
            True si envoyé
        """
        upgrade_url = url_for('billing.plans', _external=True)
        
        return EmailService.send_email(
            to=user.email,
            subject=f"Votre période d'essai expire dans {days_left} jours",
            template="trial_expiring",
            user=user,
            days_left=days_left,
            upgrade_url=upgrade_url,
            tenant_name=user.tenant.name
        )
    
    @staticmethod
    def send_subscription_confirmation_email(user: User, plan_name: str, amount: float) -> bool:
        """
        Envoyer email de confirmation d'abonnement.
        
        Args:
            user: Utilisateur
            plan_name: Nom du plan
            amount: Montant payé
        
        Returns:
            True si envoyé
        """
        return EmailService.send_email(
            to=user.email,
            subject="Confirmation de votre abonnement AUDELA",
            template="subscription_confirmed",
            user=user,
            plan_name=plan_name,
            amount=amount,
            tenant_name=user.tenant.name
        )
    
    @staticmethod
    def send_payment_failed_email(user: User) -> bool:
        """
        Envoyer email en cas d'échec de paiement.
        
        Args:
            user: Utilisateur
        
        Returns:
            True si envoyé
        """
        billing_url = url_for('billing.payment_method', _external=True)
        
        return EmailService.send_email(
            to=user.email,
            subject="Échec de paiement - AUDELA",
            template="payment_failed",
            user=user,
            billing_url=billing_url,
            tenant_name=user.tenant.name
        )
    
    @staticmethod
    def send_password_reset_email(user: User, token: str) -> bool:
        """
        Envoyer email de réinitialisation mot de passe.
        
        Args:
            user: Utilisateur
            token: Token de reset
        
        Returns:
            True si envoyé
        """
        reset_url = url_for(
            'auth.reset_password',
            token=token,
            _external=True
        )
        
        return EmailService.send_email(
            to=user.email,
            subject="Réinitialisation de votre mot de passe AUDELA",
            template="password_reset",
            user=user,
            reset_url=reset_url
        )


class EmailVerificationService:
    """Service de vérification d'email."""
    
    @staticmethod
    def create_verification_token(user: User) -> EmailVerificationToken:
        """
        Créer un token de vérification.
        
        Args:
            user: Utilisateur
        
        Returns:
            Token créé
        """
        token = EmailVerificationToken(
            user_id=user.id,
            token=EmailVerificationToken.generate_token(),
            email=user.email,
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        
        db.session.add(token)
        db.session.commit()
        
        return token
    
    @staticmethod
    def verify_token(token_string: str) -> tuple[bool, Optional[str]]:
        """
        Vérifier un token.
        
        Args:
            token_string: Token à vérifier
        
        Returns:
            (success, error_message)
        """
        token = EmailVerificationToken.query.filter_by(token=token_string).first()
        
        if not token:
            return False, "Token invalide"
        
        if token.is_verified():
            return False, "Email déjà vérifié"
        
        if token.is_expired():
            return False, "Token expiré"
        
        # Marquer comme vérifié
        token.verified_at = datetime.utcnow()
        
        # Mettre à jour le statut de l'utilisateur
        user = token.user
        if user.status == "pending_verification":
            user.status = "active"
        
        db.session.commit()
        
        return True, None
    
    @staticmethod
    def resend_verification(user: User) -> bool:
        """
        Renvoyer un email de vérification.
        
        Args:
            user: Utilisateur
        
        Returns:
            True si envoyé
        """
        # Invalider les anciens tokens
        EmailVerificationToken.query.filter_by(
            user_id=user.id,
            verified_at=None
        ).delete()
        
        # Créer nouveau token
        token = EmailVerificationService.create_verification_token(user)
        
        # Envoyer email
        return EmailService.send_verification_email(user, token.token)


class InvitationService:
    """Service de gestion des invitations."""
    
    @staticmethod
    def create_invitation(
        tenant_id: int,
        email: str,
        role_codes: List[str],
        invited_by_user_id: int
    ) -> UserInvitation:
        """
        Créer une invitation.
        
        Args:
            tenant_id: ID du tenant
            email: Email de l'invité
            role_codes: Codes des rôles à assigner
            invited_by_user_id: ID de l'utilisateur qui invite
        
        Returns:
            Invitation créée
        """
        invitation = UserInvitation(
            tenant_id=tenant_id,
            email=email,
            token=UserInvitation.generate_token(),
            role_codes=role_codes,
            invited_by_user_id=invited_by_user_id,
            expires_at=datetime.utcnow() + timedelta(days=7)
        )
        
        db.session.add(invitation)
        db.session.commit()
        
        return invitation
    
    @staticmethod
    def accept_invitation(token_string: str, password: str) -> tuple[bool, Optional[str], Optional[User]]:
        """
        Accepter une invitation.
        
        Args:
            token_string: Token d'invitation
            password: Mot de passe du nouvel utilisateur
        
        Returns:
            (success, error_message, user)
        """
        invitation = UserInvitation.query.filter_by(token=token_string).first()
        
        if not invitation:
            return False, "Invitation invalide", None
        
        if not invitation.is_pending():
            return False, "Invitation expirée ou déjà utilisée", None
        
        # Vérifier si l'email existe déjà
        existing_user = User.query.filter_by(
            tenant_id=invitation.tenant_id,
            email=invitation.email
        ).first()
        
        if existing_user:
            return False, "Cet email est déjà utilisé", None
        
        # Créer l'utilisateur
        from audela.services.tenant_service import TenantService
        user = TenantService.create_user(
            tenant_id=invitation.tenant_id,
            email=invitation.email,
            password=password,
            role_codes=invitation.role_codes,
            status="active"
        )
        
        # Marquer l'invitation comme acceptée
        invitation.status = "accepted"
        invitation.accepted_at = datetime.utcnow()
        invitation.accepted_by_user_id = user.id
        
        db.session.commit()
        
        return True, None, user

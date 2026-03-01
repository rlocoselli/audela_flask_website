"""
Email Service

Service pour envoyer des emails transactionnels (vérification, invitations, receipts, etc.)
Supporte: Flask-Mail, templates Jinja2, queuing optionnel.
"""

from typing import Optional, List, Any
from datetime import datetime, timedelta

from flask import current_app, render_template, url_for, g, has_request_context
from flask_mail import Message
from markupsafe import escape

from audela.extensions import db, mail
from audela.models import User, EmailVerificationToken, UserInvitation
from audela.i18n import tr, DEFAULT_LANG, normalize_lang


class EmailService:
    """Service d'envoi d'emails."""

    @staticmethod
    def _resolve_lang(lang: str | None = None) -> str:
        if lang:
            return normalize_lang(lang)
        if has_request_context():
            return normalize_lang(getattr(g, "lang", None))
        return DEFAULT_LANG
    
    @staticmethod
    def send_email(
        to: str | List[str],
        subject: str,
        template: str | None,
        lang: str | None = None,
        body_text: str | None = None,
        body_html: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
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
            
            resolved_lang = EmailService._resolve_lang(lang)
            template_context = dict(context)
            template_context["current_lang"] = resolved_lang
            template_context["_"] = lambda msgid, **kwargs: tr(msgid, resolved_lang, **kwargs)

            if template:
                html_body_resolved = render_template(f"emails/{template}.html", **template_context)
                text_body_resolved = render_template(f"emails/{template}.txt", **template_context)
            else:
                text_body_resolved = body_text or ""
                if body_html is not None:
                    html_body_resolved = body_html
                elif text_body_resolved:
                    html_body_resolved = f"<div style=\"white-space: pre-line; font-family: Arial, sans-serif;\">{escape(text_body_resolved)}</div>"
                else:
                    html_body_resolved = ""
            
            msg = Message(
                subject=subject,
                recipients=to,
                html=html_body_resolved,
                body=text_body_resolved,
                sender=current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@audela.com')
            )

            for attachment in attachments or []:
                filename = str(attachment.get("filename") or "attachment.bin")
                content_type = str(attachment.get("content_type") or "application/octet-stream")
                data = attachment.get("data")
                if data is None:
                    continue
                msg.attach(filename=filename, content_type=content_type, data=data)

            if current_app.config.get("MAIL_DEV_MODE", False):
                current_app.logger.info(
                    "MAIL_DEV_MODE active: email not sent (to=%s, subject=%s)",
                    to,
                    subject,
                )
                return True
            
            mail.send(msg)
            return True
            
        except Exception as e:
            current_app.logger.error(f"Failed to send email to {to}: {str(e)}")
            return False
    
    @staticmethod
    def send_verification_email(user: User, token: str, lang: str | None = None) -> bool:
        """
        Envoyer email de vérification.
        
        Args:
            user: Utilisateur
            token: Token de vérification
        
        Returns:
            True si envoyé
        """
        resolved_lang = EmailService._resolve_lang(lang)

        verification_url = url_for(
            'auth.verify_email',
            token=token,
            _external=True
        )
        
        return EmailService.send_email(
            to=user.email,
            subject=tr("Vérifiez votre adresse email - AUDELA", resolved_lang),
            template="verify_email",
            lang=resolved_lang,
            user=user,
            verification_url=verification_url,
            tenant_name=user.tenant.name
        )
    
    @staticmethod
    def send_invitation_email(invitation: UserInvitation, lang: str | None = None) -> bool:
        """
        Envoyer email d'invitation.
        
        Args:
            invitation: Invitation
        
        Returns:
            True si envoyé
        """
        resolved_lang = EmailService._resolve_lang(lang)

        invitation_url = url_for(
            'auth.accept_invitation',
            token=invitation.token,
            _external=True
        )
        
        invited_by_name = invitation.invited_by.email if invitation.invited_by else "AUDELA"
        
        return EmailService.send_email(
            to=invitation.email,
            subject=f"{tr('Invitation à rejoindre', resolved_lang)} {invitation.tenant.name} - AUDELA",
            template="user_invitation",
            lang=resolved_lang,
            invitation=invitation,
            invitation_url=invitation_url,
            invited_by_name=invited_by_name,
            tenant_name=invitation.tenant.name
        )
    
    @staticmethod
    def send_welcome_email(user: User, lang: str | None = None) -> bool:
        """
        Envoyer email de bienvenue après vérification.
        
        Args:
            user: Utilisateur
        
        Returns:
            True si envoyé
        """
        resolved_lang = EmailService._resolve_lang(lang)

        app_url = url_for('auth.login', _external=True)
        
        return EmailService.send_email(
            to=user.email,
            subject=tr("Bienvenue sur AUDELA!", resolved_lang),
            template="welcome",
            lang=resolved_lang,
            user=user,
            app_url=app_url,
            tenant_name=user.tenant.name
        )
    
    @staticmethod
    def send_trial_expiring_email(user: User, days_left: int, lang: str | None = None) -> bool:
        """
        Envoyer email avant expiration du trial.
        
        Args:
            user: Utilisateur (admin du tenant)
            days_left: Jours restants
        
        Returns:
            True si envoyé
        """
        resolved_lang = EmailService._resolve_lang(lang)

        upgrade_url = url_for('billing.plans', _external=True)
        
        return EmailService.send_email(
            to=user.email,
            subject=tr("Votre période d'essai expire bientôt", resolved_lang),
            template="trial_expiring",
            lang=resolved_lang,
            user=user,
            days_left=days_left,
            upgrade_url=upgrade_url,
            tenant_name=user.tenant.name
        )
    
    @staticmethod
    def send_subscription_confirmation_email(user: User, plan_name: str, amount: float, lang: str | None = None) -> bool:
        """
        Envoyer email de confirmation d'abonnement.
        
        Args:
            user: Utilisateur
            plan_name: Nom du plan
            amount: Montant payé
        
        Returns:
            True si envoyé
        """
        resolved_lang = EmailService._resolve_lang(lang)

        return EmailService.send_email(
            to=user.email,
            subject=tr("Confirmation de votre abonnement AUDELA", resolved_lang),
            template="subscription_confirmed",
            lang=resolved_lang,
            user=user,
            plan_name=plan_name,
            amount=amount,
            tenant_name=user.tenant.name
        )
    
    @staticmethod
    def send_payment_failed_email(user: User, lang: str | None = None) -> bool:
        """
        Envoyer email en cas d'échec de paiement.
        
        Args:
            user: Utilisateur
        
        Returns:
            True si envoyé
        """
        resolved_lang = EmailService._resolve_lang(lang)

        billing_url = url_for('billing.payment_method', _external=True)
        
        return EmailService.send_email(
            to=user.email,
            subject=tr("Échec de paiement - AUDELA", resolved_lang),
            template="payment_failed",
            lang=resolved_lang,
            user=user,
            billing_url=billing_url,
            tenant_name=user.tenant.name
        )
    
    @staticmethod
    def send_password_reset_email(user: User, token: str, lang: str | None = None) -> bool:
        """
        Envoyer email de réinitialisation mot de passe.
        
        Args:
            user: Utilisateur
            token: Token de reset
        
        Returns:
            True si envoyé
        """
        resolved_lang = EmailService._resolve_lang(lang)

        reset_url = url_for(
            'auth.reset_password',
            token=token,
            _external=True
        )
        
        return EmailService.send_email(
            to=user.email,
            subject=tr("Réinitialisation de votre mot de passe AUDELA", resolved_lang),
            template="password_reset",
            lang=resolved_lang,
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
        try:
            EmailVerificationService.verify_email(token_string)
            return True, None
        except ValueError as e:
            return False, str(e)

    @staticmethod
    def verify_email(token_string: str) -> User:
        """
        Vérifier un token d'email et activer l'utilisateur.

        Args:
            token_string: Token à vérifier

        Returns:
            Utilisateur vérifié

        Raises:
            ValueError: si le token est invalide/expiré/déjà utilisé
        """
        token = EmailVerificationToken.query.filter_by(token=token_string).first()
        
        if not token:
            raise ValueError("Token invalide")
        
        if token.is_verified():
            raise ValueError("Email déjà vérifié")
        
        if token.is_expired():
            raise ValueError("Token expiré")
        
        # Marquer comme vérifié
        token.verified_at = datetime.utcnow()
        
        # Mettre à jour le statut de l'utilisateur
        user = token.user
        if user.status == "pending_verification":
            user.status = "active"
        
        db.session.commit()
        return user
    
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

from __future__ import annotations

from datetime import datetime

from flask import flash, redirect, render_template, request, url_for, g, session, current_app
from flask_login import login_user, logout_user, current_user

from ...extensions import db
from ...models.bi import AuditEvent
from ...models.core import Tenant, User, Role
from ...models.subscription import EmailVerificationToken, UserInvitation
from ...services.tenant_service import TenantService
from ...services.email_service import EmailVerificationService, InvitationService
from ...tenancy import CurrentTenant, set_current_tenant, clear_current_tenant
from ...i18n import tr
from . import bp


@bp.route("/login", methods=["GET", "POST"])
def login():
    # MVP: tenant selected by slug on login screen
    if request.method == "POST":
        tenant_slug = request.form.get("tenant_slug", "").strip().lower()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        tenant = Tenant.query.filter_by(slug=tenant_slug).first()
        if not tenant:
            flash(tr("Tenant não encontrado.", getattr(g, "lang", None)), "error")
            return render_template("portal/login.html")

        user = User.query.filter_by(tenant_id=tenant.id, email=email).first()
        if not user or not user.check_password(password):
            flash(tr("Credenciais inválidas.", getattr(g, "lang", None)), "error")
            # Optional: record failed login attempt (without storing password)
            db.session.add(
                AuditEvent(
                    tenant_id=tenant.id,
                    user_id=user.id if user else None,
                    event_type="auth.login.failed",
                    payload_json={"email": email},
                )
            )
            db.session.commit()
            return render_template("portal/login.html")
        
        # Check email verification
        if user.status == "pending_verification":
            flash(tr("Você precisa verificar seu email antes de fazer login.", getattr(g, "lang", None)), "warning")
            return redirect(url_for("auth.resend_verification"))

        login_user(user)
        user.last_login_at = datetime.utcnow()
        db.session.add(
            AuditEvent(
                tenant_id=tenant.id,
                user_id=user.id,
                event_type="auth.login.success",
                payload_json={"email": email},
            )
        )
        db.session.commit()

        set_current_tenant(CurrentTenant(id=tenant.id, slug=tenant.slug, name=tenant.name))
        session.pop("app_mode", None)
        return redirect(url_for("portal.home"))

    return render_template("portal/login.html")


@bp.route("/login/finance", methods=["GET", "POST"])
def login_finance():
    """Dedicated login entry point for AUDELA Finance.

    This keeps BI and Finance separated at the UI level.
    """
    if request.method == "POST":
        tenant_slug = request.form.get("tenant_slug", "").strip().lower()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        tenant = Tenant.query.filter_by(slug=tenant_slug).first()
        if not tenant:
            flash(tr("Tenant não encontrado.", getattr(g, "lang", None)), "error")
            return render_template("portal/login_finance.html")

        user = User.query.filter_by(tenant_id=tenant.id, email=email).first()
        if not user or not user.check_password(password):
            flash(tr("Credenciais inválidas.", getattr(g, "lang", None)), "error")
            db.session.add(
                AuditEvent(
                    tenant_id=tenant.id,
                    user_id=user.id if user else None,
                    event_type="auth.login.failed",
                    payload_json={"email": email, "app": "finance"},
                )
            )
            db.session.commit()
            return render_template("portal/login_finance.html")
        
        # Check email verification
        if user.status == "pending_verification":
            flash(tr("Você precisa verificar seu email antes de fazer login.", getattr(g, "lang", None)), "warning")
            return redirect(url_for("auth.resend_verification"))

        login_user(user)
        user.last_login_at = datetime.utcnow()
        db.session.add(
            AuditEvent(
                tenant_id=tenant.id,
                user_id=user.id,
                event_type="auth.login.success",
                payload_json={"email": email, "app": "finance"},
            )
        )
        db.session.commit()

        set_current_tenant(CurrentTenant(id=tenant.id, slug=tenant.slug, name=tenant.name))
        session["app_mode"] = "finance"
        return redirect(url_for("finance.dashboard"))

    return render_template("portal/login_finance.html")


@bp.route("/logout")
def logout():
    logout_user()
    clear_current_tenant()
    return redirect(url_for("public.index"))


@bp.route("/bootstrap", methods=["GET", "POST"])
def bootstrap():
    """One-time helper to create the first tenant + admin.

    Remove or protect this route in production.
    """
    if request.method == "POST":
        tenant_slug = request.form.get("tenant_slug", "").strip().lower()
        tenant_name = request.form.get("tenant_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not tenant_slug or not tenant_name or not email or not password:
            flash(tr("Preencha todos os campos.", getattr(g, "lang", None)), "error")
            return render_template("portal/bootstrap.html")

        if Tenant.query.filter_by(slug=tenant_slug).first():
            flash(tr("Slug já existe.", getattr(g, "lang", None)), "error")
            return render_template("portal/bootstrap.html")

        tenant = Tenant(slug=tenant_slug, name=tenant_name)
        db.session.add(tenant)
        db.session.flush()

        # Ensure default roles exist
        for code, desc in [
            ("platform_admin", "Admin da plataforma"),
            ("tenant_admin", "Admin do tenant"),
            ("creator", "Criador"),
            ("viewer", "Visualizador"),
        ]:
            if not Role.query.filter_by(code=code).first():
                db.session.add(Role(code=code, description=desc))
        db.session.flush()

        user = User(tenant_id=tenant.id, email=email)
        user.set_password(password)
        # Assign tenant_admin role
        role = Role.query.filter_by(code="tenant_admin").first()
        user.roles.append(role)
        db.session.add(user)
        db.session.add(
            AuditEvent(
                tenant_id=tenant.id,
                user_id=None,
                event_type="platform.tenant.bootstrapped",
                payload_json={"tenant_slug": tenant.slug, "admin_email": email},
            )
        )
        db.session.commit()

        flash(tr("Tenant criado. Faça login.", getattr(g, "lang", None)), "success")
        return redirect(url_for("auth.login"))

    return render_template("portal/bootstrap.html")


@bp.route("/register", methods=["GET", "POST"])
def register():
    """
    Register new tenant with admin user.
    Sends email verification before allowing login.
    """
    if request.method == "POST":
        tenant_name = request.form.get("tenant_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")
        plan_code = request.form.get("plan_code", "free")
        
        # Validation
        if not tenant_name or not email or not password:
            flash(tr("Preencha todos os campos.", getattr(g, "lang", None)), "error")
            return render_template("portal/register.html")
        
        if password != password_confirm:
            flash(tr("As senhas não coincidem.", getattr(g, "lang", None)), "error")
            return render_template("portal/register.html")
        
        if len(password) < 8:
            flash(tr("A senha deve ter pelo menos 8 caracteres.", getattr(g, "lang", None)), "error")
            return render_template("portal/register.html")
        
        # Check if email already exists
        if User.query.filter_by(email=email).first():
            flash(tr("Este email já está em uso.", getattr(g, "lang", None)), "error")
            return render_template("portal/register.html")
        
        try:
            # Create tenant with admin user
            tenant, user = TenantService.create_tenant(
                name=tenant_name,
                email=email,
                password=password,
                plan_code=plan_code,
                send_verification=True
            )
            
            # Audit event
            db.session.add(
                AuditEvent(
                    tenant_id=tenant.id,
                    user_id=user.id,
                    event_type="auth.register.success",
                    payload_json={
                        "tenant_slug": tenant.slug,
                        "email": email,
                        "plan": plan_code
                    },
                )
            )
            db.session.commit()
            
            flash(
                tr("Conta criada! Verifique seu email para ativar.", getattr(g, "lang", None)),
                "success"
            )
            return redirect(url_for("auth.login"))
        
        except Exception as e:
            current_app.logger.error(f"Registration error: {e}")
            db.session.rollback()
            flash(tr("Erro ao criar conta. Tente novamente.", getattr(g, "lang", None)), "error")
            return render_template("portal/register.html")
    
    return render_template("portal/register.html")


@bp.route("/verify-email/<token>")
def verify_email(token):
    """Verify email address with token."""
    try:
        user = EmailVerificationService.verify_email(token)
        
        # Audit event
        db.session.add(
            AuditEvent(
                tenant_id=user.tenant_id,
                user_id=user.id,
                event_type="auth.email.verified",
                payload_json={"email": user.email},
            )
        )
        db.session.commit()
        
        flash(tr("Email verificado com sucesso! Você já pode fazer login.", getattr(g, "lang", None)), "success")
        return redirect(url_for("auth.login"))
    
    except ValueError as e:
        current_app.logger.warning(f"Email verification failed: {e}")
        flash(str(e), "error")
        return redirect(url_for("auth.resend_verification"))


@bp.route("/resend-verification", methods=["GET", "POST"])
def resend_verification():
    """Resend email verification link."""
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        
        if not email:
            flash(tr("Digite seu email.", getattr(g, "lang", None)), "error")
            return render_template("portal/resend_verification.html")
        
        # Find user
        user = User.query.filter_by(email=email, status="pending_verification").first()
        
        if user:
            try:
                EmailVerificationService.resend_verification_email(user)
                flash(
                    tr("Email de verificação reenviado. Verifique sua caixa de entrada.", getattr(g, "lang", None)),
                    "success"
                )
            except Exception as e:
                current_app.logger.error(f"Resend verification error: {e}")
                flash(tr("Erro ao enviar email. Tente novamente.", getattr(g, "lang", None)), "error")
        else:
            # Don't reveal if email exists or not
            flash(
                tr("Se o email existir, você receberá um link de verificação.", getattr(g, "lang", None)),
                "info"
            )
        
        return redirect(url_for("auth.login"))
    
    return render_template("portal/resend_verification.html")


@bp.route("/accept-invitation/<token>", methods=["GET", "POST"])
def accept_invitation(token):
    """Accept invitation and create user account."""
    # Find invitation
    invitation = UserInvitation.query.filter_by(
        token=token,
        status="pending"
    ).first()
    
    if not invitation:
        flash(tr("Convite inválido ou expirado.", getattr(g, "lang", None)), "error")
        return redirect(url_for("auth.login"))
    
    # Check if expired
    if invitation.is_expired():
        invitation.status = "expired"
        db.session.commit()
        flash(tr("Este convite expirou.", getattr(g, "lang", None)), "error")
        return redirect(url_for("auth.login"))
    
    if request.method == "POST":
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")
        
        # Validation
        if not password:
            flash(tr("Digite uma senha.", getattr(g, "lang", None)), "error")
            return render_template("portal/accept_invitation.html", invitation=invitation)
        
        if password != password_confirm:
            flash(tr("As senhas não coincidem.", getattr(g, "lang", None)), "error")
            return render_template("portal/accept_invitation.html", invitation=invitation)
        
        if len(password) < 8:
            flash(tr("A senha deve ter pelo menos 8 caracteres.", getattr(g, "lang", None)), "error")
            return render_template("portal/accept_invitation.html", invitation=invitation)
        
        try:
            # Accept invitation and create user
            user = InvitationService.accept_invitation(token, password)
            
            # Audit event
            db.session.add(
                AuditEvent(
                    tenant_id=user.tenant_id,
                    user_id=user.id,
                    event_type="auth.invitation.accepted",
                    payload_json={
                        "email": user.email,
                        "invited_by": invitation.invited_by.email
                    },
                )
            )
            db.session.commit()
            
            flash(tr("Convite aceito! Você já pode fazer login.", getattr(g, "lang", None)), "success")
            return redirect(url_for("auth.login"))
        
        except ValueError as e:
            current_app.logger.error(f"Invitation acceptance error: {e}")
            flash(str(e), "error")
            return render_template("portal/accept_invitation.html", invitation=invitation)
    
    return render_template("portal/accept_invitation.html", invitation=invitation)

"""
Tenant Management Routes

Routes pour la gestion du tenant: login, signup, dashboard, utilisateurs, abonnements.
"""
from flask import (
    render_template,
    redirect,
    url_for,
    flash,
    request,
    session,
    g,
    current_app
)
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime

from ...extensions import db
from ...models import Tenant, User, Role
from ...models.subscription import TenantSubscription
from ...models.bi import AuditEvent
from ...services.tenant_service import TenantService
from ...services.subscription_service import SubscriptionService
from ...tenancy import CurrentTenant, set_current_tenant, clear_current_tenant
from ...i18n import tr
from . import bp


@bp.route("/")
def index():
    """Redirect to login page."""
    if current_user.is_authenticated:
        return redirect(url_for("tenant.dashboard"))
    return redirect(url_for("tenant.login"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    """
    Combined login/signup page for tenant management.
    """
    if current_user.is_authenticated:
        return redirect(url_for("tenant.dashboard"))
    
    if request.method == "POST":
        action = request.form.get("action", "login")
        
        if action == "signup":
            return _handle_signup()
        else:
            return _handle_login()
    
    return render_template("tenant/login.html")


def _handle_login():
    """Handle tenant login."""
    tenant_slug = request.form.get("tenant_slug", "").strip().lower()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    
    tenant = Tenant.query.filter_by(slug=tenant_slug).first()
    if not tenant:
        flash(tr("Tenant não encontrado.", getattr(g, "lang", None)), "error")
        return render_template("tenant/login.html")
    
    user = User.query.filter_by(tenant_id=tenant.id, email=email).first()
    if not user or not user.check_password(password):
        flash(tr("Credenciais inválidas.", getattr(g, "lang", None)), "error")
        db.session.add(
            AuditEvent(
                tenant_id=tenant.id,
                user_id=user.id if user else None,
                event_type="tenant.login.failed",
                payload_json={"email": email},
            )
        )
        db.session.commit()
        return render_template("tenant/login.html")
    
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
            event_type="tenant.login.success",
            payload_json={"email": email},
        )
    )
    db.session.commit()
    
    set_current_tenant(CurrentTenant(id=tenant.id, slug=tenant.slug, name=tenant.name))
    return redirect(url_for("tenant.dashboard"))


def _handle_signup():
    """Handle tenant signup."""
    tenant_name = request.form.get("tenant_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    password_confirm = request.form.get("password_confirm", "")
    
    # Validation
    if not tenant_name or not email or not password:
        flash(tr("Preencha todos os campos.", getattr(g, "lang", None)), "error")
        return render_template("tenant/login.html")
    
    if password != password_confirm:
        flash(tr("As senhas não coincidem.", getattr(g, "lang", None)), "error")
        return render_template("tenant/login.html")
    
    if len(password) < 8:
        flash(tr("A senha deve ter pelo menos 8 caracteres.", getattr(g, "lang", None)), "error")
        return render_template("tenant/login.html")
    
    # Check if email already exists
    if User.query.filter_by(email=email).first():
        flash(tr("Este email já está em uso.", getattr(g, "lang", None)), "error")
        return render_template("tenant/login.html")
    
    try:
        # Create tenant with admin user
        tenant, user = TenantService.create_tenant(
            name=tenant_name,
            email=email,
            password=password,
            plan_code="free",
            send_verification=True
        )
        
        # Audit event
        db.session.add(
            AuditEvent(
                tenant_id=tenant.id,
                user_id=user.id,
                event_type="tenant.signup.success",
                payload_json={
                    "tenant_slug": tenant.slug,
                    "email": email
                },
            )
        )
        db.session.commit()
        
        flash(
            tr("Conta criada! Verifique seu email para ativar.", getattr(g, "lang", None)),
            "success"
        )
        return redirect(url_for("tenant.login"))
    
    except Exception as e:
        current_app.logger.error(f"Signup error: {e}")
        db.session.rollback()
        flash(tr("Erro ao criar conta. Tente novamente.", getattr(g, "lang", None)), "error")
        return render_template("tenant/login.html")


@bp.route("/dashboard")
@login_required
def dashboard():
    """Tenant management dashboard."""
    tenant = Tenant.query.get(current_user.tenant_id)
    if not tenant:
        flash("Tenant not found", "error")
        return redirect(url_for("tenant.login"))
    
    # Get tenant stats
    stats = TenantService.get_tenant_stats(current_user.tenant_id)
    
    # Get users
    users = TenantService.list_users(current_user.tenant_id)
    
    # Check permissions
    is_admin = current_user.has_role("tenant_admin")
    
    return render_template(
        "tenant/dashboard.html",
        tenant=tenant,
        subscription=tenant.subscription,
        stats=stats,
        users=users,
        is_admin=is_admin
    )


@bp.route("/users")
@login_required
def users():
    """User management page."""
    if not current_user.has_role("tenant_admin"):
        flash("Admin access required", "error")
        return redirect(url_for("tenant.dashboard"))
    
    tenant = Tenant.query.get(current_user.tenant_id)
    users = TenantService.list_users(current_user.tenant_id)
    
    # Check if can add more users
    can_add, current_count, max_limit = SubscriptionService.check_limit(
        current_user.tenant_id, "users"
    )
    
    return render_template(
        "tenant/users.html",
        tenant=tenant,
        users=users,
        can_add_user=can_add,
        current_users=current_count,
        max_users=max_limit
    )


@bp.route("/users/invite", methods=["GET", "POST"])
@login_required
def invite_user():
    """Invite a new user."""
    if not current_user.has_role("tenant_admin"):
        flash("Admin access required", "error")
        return redirect(url_for("tenant.dashboard"))
    
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        roles = request.form.getlist("roles")
        
        if not email:
            flash("Email is required", "error")
            return render_template("tenant/invite.html")
        
        if not roles:
            roles = ["viewer"]
        
        try:
            invitation = TenantService.invite_user(
                tenant_id=current_user.tenant_id,
                email=email,
                role_codes=roles,
                invited_by_user_id=current_user.id
            )
            
            flash(f"Invitation sent to {email}", "success")
            return redirect(url_for("tenant.users"))
        
        except ValueError as e:
            flash(str(e), "error")
            return render_template("tenant/invite.html")
    
    # Get available roles
    roles = Role.query.all()
    
    return render_template("tenant/invite.html", roles=roles)


@bp.route("/subscription")
@login_required
def subscription():
    """View subscription details."""
    tenant = Tenant.query.get(current_user.tenant_id)
    if not tenant:
        flash("Tenant not found", "error")
        return redirect(url_for("tenant.dashboard"))
    
    stats = TenantService.get_tenant_stats(current_user.tenant_id)
    
    return render_template(
        "tenant/subscription.html",
        tenant=tenant,
        subscription=tenant.subscription,
        stats=stats
    )


@bp.route("/products")
@login_required
def products():
    """Access subscribed products."""
    tenant = Tenant.query.get(current_user.tenant_id)
    if not tenant or not tenant.subscription:
        flash("No active subscription", "warning")
        return redirect(url_for("billing.plans"))
    
    subscription = tenant.subscription
    
    # Check access to products
    has_finance = SubscriptionService.check_feature_access(current_user.tenant_id, "finance")
    has_bi = SubscriptionService.check_feature_access(current_user.tenant_id, "bi")
    
    if not has_finance and not has_bi:
        flash("No products available. Please upgrade your subscription.", "warning")
        return redirect(url_for("billing.plans"))
    
    return render_template(
        "tenant/products.html",
        tenant=tenant,
        subscription=subscription,
        has_finance=has_finance,
        has_bi=has_bi
    )


@bp.route("/logout")
@login_required
def logout():
    """Logout from tenant dashboard."""
    logout_user()
    clear_current_tenant()
    return redirect(url_for("tenant.login"))

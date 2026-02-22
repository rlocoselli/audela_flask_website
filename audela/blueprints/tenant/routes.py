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
from sqlalchemy.orm.attributes import flag_modified
from werkzeug.utils import secure_filename
import os
import uuid

from ...extensions import db
from ...models import Tenant, User, Role
from ...models.subscription import TenantSubscription
from ...models.bi import AuditEvent
from ...models.prospect import Prospect
from ...services.tenant_service import TenantService
from ...services.subscription_service import SubscriptionService
from ...tenancy import CurrentTenant, set_current_tenant, clear_current_tenant, get_user_module_access
from ...i18n import tr
from . import bp


AVATAR_CHOICES = [
    "person-circle",
    "emoji-smile",
    "stars",
    "briefcase",
    "bar-chart",
    "rocket",
    "lightning",
    "palette",
]


def _tenant_user_profiles(tenant: Tenant) -> dict:
    settings = tenant.settings_json if isinstance(tenant.settings_json, dict) else {}
    raw = settings.get("user_profiles") if isinstance(settings.get("user_profiles"), dict) else {}
    return raw


def _tenant_user_profile(tenant: Tenant, user_id: int) -> dict:
    profiles = _tenant_user_profiles(tenant)
    p = profiles.get(str(int(user_id))) if isinstance(profiles, dict) else None
    if not isinstance(p, dict):
        p = {}
    return {
        "display_name": str(p.get("display_name") or "").strip(),
        "bio": str(p.get("bio") or "").strip(),
        "avatar_mode": str(p.get("avatar_mode") or "avatar").strip().lower() or "avatar",
        "avatar_icon": str(p.get("avatar_icon") or "person-circle").strip() or "person-circle",
        "photo_url": str(p.get("photo_url") or "").strip(),
        "updated_at": p.get("updated_at"),
    }


def _save_tenant_user_profile(tenant: Tenant, user_id: int, profile: dict) -> None:
    settings = tenant.settings_json if isinstance(tenant.settings_json, dict) else {}
    profiles = settings.get("user_profiles") if isinstance(settings.get("user_profiles"), dict) else {}
    profiles[str(int(user_id))] = profile
    settings["user_profiles"] = profiles
    tenant.settings_json = settings
    flag_modified(tenant, "settings_json")


def _save_profile_photo_upload(tenant_id: int, user_id: int, file_storage) -> str | None:
    if not file_storage or not getattr(file_storage, "filename", None):
        return None
    filename = secure_filename(file_storage.filename or "")
    if not filename:
        return None
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in {"png", "jpg", "jpeg", "webp", "gif"}:
        raise ValueError("Unsupported image format")

    rel_dir = os.path.join("uploads", "avatars", f"tenant_{int(tenant_id)}")
    abs_dir = os.path.join(current_app.static_folder, rel_dir)
    os.makedirs(abs_dir, exist_ok=True)
    new_name = f"u{int(user_id)}_{uuid.uuid4().hex}.{ext}"
    abs_path = os.path.join(abs_dir, new_name)
    file_storage.save(abs_path)
    rel_path = os.path.join(rel_dir, new_name).replace("\\", "/")
    return "/static/" + rel_path


def _tenant_branding(tenant: Tenant) -> dict:
    settings = tenant.settings_json if isinstance(tenant.settings_json, dict) else {}
    branding = settings.get("branding") if isinstance(settings.get("branding"), dict) else {}
    return {
        "nickname": str(branding.get("nickname") or "").strip(),
        "logo_url": str(branding.get("logo_url") or "").strip(),
        "updated_at": branding.get("updated_at"),
    }


def _save_tenant_branding(tenant: Tenant, branding: dict) -> None:
    settings = tenant.settings_json if isinstance(tenant.settings_json, dict) else {}
    settings["branding"] = branding
    tenant.settings_json = settings
    flag_modified(tenant, "settings_json")


def _save_tenant_user_module_access(tenant: Tenant, user_id: int, module_access: dict) -> None:
    settings = tenant.settings_json if isinstance(tenant.settings_json, dict) else {}
    uam = settings.get("uam") if isinstance(settings.get("uam"), dict) else {}
    rows = uam.get("module_access") if isinstance(uam.get("module_access"), dict) else {}
    rows[str(int(user_id))] = {
        "finance": bool(module_access.get("finance", True)),
        "bi": bool(module_access.get("bi", True)),
        "updated_at": datetime.utcnow().isoformat(),
    }
    uam["module_access"] = rows
    settings["uam"] = uam
    tenant.settings_json = settings
    flag_modified(tenant, "settings_json")


def _save_tenant_logo_upload(tenant_id: int, file_storage) -> str | None:
    if not file_storage or not getattr(file_storage, "filename", None):
        return None
    filename = secure_filename(file_storage.filename or "")
    if not filename:
        return None
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in {"png", "jpg", "jpeg", "webp", "gif", "svg"}:
        raise ValueError("Unsupported logo format")

    rel_dir = os.path.join("uploads", "tenant_logos", f"tenant_{int(tenant_id)}")
    abs_dir = os.path.join(current_app.static_folder, rel_dir)
    os.makedirs(abs_dir, exist_ok=True)
    new_name = f"logo_{uuid.uuid4().hex}.{ext}"
    abs_path = os.path.join(abs_dir, new_name)
    file_storage.save(abs_path)
    rel_path = os.path.join(rel_dir, new_name).replace("\\", "/")
    return "/static/" + rel_path


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
        flash(tr("Tenant not found", getattr(g, "lang", None)), "error")
        return redirect(url_for("tenant.login"))
    
    # Get tenant stats
    stats = TenantService.get_tenant_stats(current_user.tenant_id)
    
    # Get users
    users = TenantService.list_users(current_user.tenant_id)
    
    # Check permissions
    is_admin = current_user.has_role("tenant_admin")
    profile = _tenant_user_profile(tenant, current_user.id)
    branding = _tenant_branding(tenant)
    module_access = get_user_module_access(tenant, current_user.id)
    
    return render_template(
        "tenant/dashboard.html",
        tenant=tenant,
        subscription=tenant.subscription,
        stats=stats,
        users=users,
        is_admin=is_admin,
        profile=profile,
        branding=branding,
        module_access=module_access,
    )


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    tenant = Tenant.query.get(current_user.tenant_id)
    if not tenant:
        flash(tr("Tenant not found", getattr(g, "lang", None)), "error")
        return redirect(url_for("tenant.login"))

    profile_data = _tenant_user_profile(tenant, current_user.id)
    branding = _tenant_branding(tenant)
    is_admin = current_user.has_role("tenant_admin")

    if request.method == "POST":
        display_name = (request.form.get("display_name") or "").strip()
        bio = (request.form.get("bio") or "").strip()
        avatar_mode = (request.form.get("avatar_mode") or "avatar").strip().lower()
        avatar_icon = (request.form.get("avatar_icon") or "person-circle").strip()
        photo_url = (request.form.get("photo_url") or "").strip()

        if avatar_mode not in ("avatar", "photo"):
            avatar_mode = "avatar"
        if avatar_icon not in AVATAR_CHOICES:
            avatar_icon = "person-circle"
        if len(display_name) > 80:
            display_name = display_name[:80]
        if len(bio) > 500:
            bio = bio[:500]

        try:
            uploaded = _save_profile_photo_upload(tenant.id, current_user.id, request.files.get("photo_file"))
            if uploaded:
                photo_url = uploaded
                avatar_mode = "photo"
        except ValueError as e:
            flash(tr(str(e), getattr(g, "lang", None)), "error")
            return render_template(
                "tenant/profile.html",
                tenant=tenant,
                profile={
                    **profile_data,
                    "display_name": display_name,
                    "bio": bio,
                    "avatar_mode": avatar_mode,
                    "avatar_icon": avatar_icon,
                    "photo_url": photo_url,
                },
                avatar_choices=AVATAR_CHOICES,
            )

        profile_data = {
            "display_name": display_name,
            "bio": bio,
            "avatar_mode": avatar_mode,
            "avatar_icon": avatar_icon,
            "photo_url": photo_url,
            "updated_at": datetime.utcnow().isoformat(),
        }
        _save_tenant_user_profile(tenant, current_user.id, profile_data)

        if is_admin:
            tenant_nickname = (request.form.get("tenant_nickname") or "").strip()
            tenant_logo_url = (request.form.get("tenant_logo_url") or "").strip()
            if len(tenant_nickname) > 80:
                tenant_nickname = tenant_nickname[:80]
            try:
                uploaded_logo = _save_tenant_logo_upload(tenant.id, request.files.get("tenant_logo_file"))
                if uploaded_logo:
                    tenant_logo_url = uploaded_logo
            except ValueError as e:
                flash(tr(str(e), getattr(g, "lang", None)), "error")
                return render_template(
                    "tenant/profile.html",
                    tenant=tenant,
                    profile=profile_data,
                    avatar_choices=AVATAR_CHOICES,
                    is_admin=is_admin,
                    branding={
                        "nickname": tenant_nickname,
                        "logo_url": tenant_logo_url,
                    },
                )

            branding = {
                "nickname": tenant_nickname,
                "logo_url": tenant_logo_url,
                "updated_at": datetime.utcnow().isoformat(),
            }
            _save_tenant_branding(tenant, branding)

        db.session.commit()
        flash(tr("Profil mis à jour.", getattr(g, "lang", None)), "success")
        return redirect(url_for("tenant.profile"))

    return render_template(
        "tenant/profile.html",
        tenant=tenant,
        profile=profile_data,
        avatar_choices=AVATAR_CHOICES,
        is_admin=is_admin,
        branding=branding,
    )


@bp.route("/users")
@login_required
def users():
    """User management page."""
    if not current_user.has_role("tenant_admin"):
        flash(tr("Admin access required", getattr(g, "lang", None)), "error")
        return redirect(url_for("tenant.dashboard"))
    
    tenant = Tenant.query.get(current_user.tenant_id)
    users = TenantService.list_users(current_user.tenant_id)
    user_module_access = {}
    for u in users:
        uid = u.get("id") if isinstance(u, dict) else getattr(u, "id", None)
        if uid is None:
            continue
        user_module_access[int(uid)] = get_user_module_access(tenant, int(uid))
    
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
        max_users=max_limit,
        user_module_access=user_module_access,
    )


@bp.route("/users/<int:user_id>/module-access", methods=["POST"])
@login_required
def users_update_module_access(user_id: int):
    if not current_user.has_role("tenant_admin"):
        flash(tr("Admin access required", getattr(g, "lang", None)), "error")
        return redirect(url_for("tenant.dashboard"))

    tenant = Tenant.query.get(current_user.tenant_id)
    if not tenant:
        flash(tr("Tenant not found", getattr(g, "lang", None)), "error")
        return redirect(url_for("tenant.dashboard"))

    user = User.query.filter_by(id=user_id, tenant_id=tenant.id).first()
    if not user:
        flash(tr("User not found", getattr(g, "lang", None)), "error")
        return redirect(url_for("tenant.users"))

    finance_enabled = str(request.form.get("finance_access") or "").lower() in ("1", "true", "on", "yes")
    bi_enabled = str(request.form.get("bi_access") or "").lower() in ("1", "true", "on", "yes")

    _save_tenant_user_module_access(
        tenant,
        user.id,
        {
            "finance": finance_enabled,
            "bi": bi_enabled,
        },
    )
    db.session.commit()
    flash(tr("Accès modules mis à jour", getattr(g, "lang", None)), "success")
    return redirect(url_for("tenant.users"))


@bp.route("/prospects")
@login_required
def prospects_agenda():
    """Simple rendez-vous agenda for demo requests."""
    if not current_user.has_role("tenant_admin"):
        flash(tr("Admin access required", getattr(g, "lang", None)), "error")
        return redirect(url_for("tenant.dashboard"))

    date_from_raw = (request.args.get("from") or "").strip()
    date_to_raw = (request.args.get("to") or "").strip()
    status = (request.args.get("status") or "").strip().lower()

    q = Prospect.query
    if date_from_raw:
        try:
            date_from = datetime.strptime(date_from_raw, "%Y-%m-%d").date()
            q = q.filter(Prospect.rdv_date >= date_from)
        except ValueError:
            flash(tr("Date de début invalide", getattr(g, "lang", None)), "warning")
    if date_to_raw:
        try:
            date_to = datetime.strptime(date_to_raw, "%Y-%m-%d").date()
            q = q.filter(Prospect.rdv_date <= date_to)
        except ValueError:
            flash(tr("Date de fin invalide", getattr(g, "lang", None)), "warning")
    if status in {"new", "confirmed", "done", "cancelled"}:
        q = q.filter(Prospect.status == status)

    prospects = q.order_by(Prospect.rdv_date.asc(), Prospect.rdv_time.asc(), Prospect.created_at.desc()).all()
    return render_template(
        "tenant/prospects_agenda.html",
        tenant=Tenant.query.get(current_user.tenant_id),
        prospects=prospects,
        filters={"from": date_from_raw, "to": date_to_raw, "status": status},
    )


@bp.route("/users/invite", methods=["GET", "POST"])
@login_required
def invite_user():
    """Invite a new user."""
    if not current_user.has_role("tenant_admin"):
        flash(tr("Admin access required", getattr(g, "lang", None)), "error")
        return redirect(url_for("tenant.dashboard"))
    
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        roles = request.form.getlist("roles")
        
        if not email:
            flash(tr("Email is required", getattr(g, "lang", None)), "error")
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
            
            flash(tr("Invitation sent to {email}", getattr(g, "lang", None), email=email), "success")
            return redirect(url_for("tenant.users"))
        
        except ValueError as e:
            flash(tr(str(e), getattr(g, "lang", None)), "error")
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
        flash(tr("Tenant not found", getattr(g, "lang", None)), "error")
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
        flash(tr("No active subscription", getattr(g, "lang", None)), "warning")
        return redirect(url_for("billing.plans"))
    
    subscription = tenant.subscription
    
    # Check access to products
    has_finance = SubscriptionService.check_feature_access(current_user.tenant_id, "finance")
    has_bi = SubscriptionService.check_feature_access(current_user.tenant_id, "bi")
    has_project = SubscriptionService.check_feature_access(current_user.tenant_id, "project")
    
    if not has_finance and not has_bi and not has_project:
        flash(tr("No products available. Please upgrade your subscription.", getattr(g, "lang", None)), "warning")
        return redirect(url_for("billing.plans"))
    
    return render_template(
        "tenant/products.html",
        tenant=tenant,
        subscription=subscription,
        has_finance=has_finance,
        has_bi=has_bi,
        has_project=has_project,
    )


@bp.route("/logout")
@login_required
def logout():
    """Logout from tenant dashboard."""
    logout_user()
    clear_current_tenant()
    return redirect(url_for("tenant.login"))

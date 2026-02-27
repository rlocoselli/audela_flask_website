from __future__ import annotations

from datetime import datetime

from flask import flash, g, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user

from ...extensions import db
from ...i18n import tr
from ...models import BillingEvent, Role, SubscriptionPlan, Tenant, TenantSubscription, User
from ...tenancy import clear_current_tenant
from . import bp


ALLOWED_BILLING_CYCLES = {"monthly", "yearly"}


def _is_platform_admin(user: User | None) -> bool:
    return bool(user and user.is_authenticated and user.has_role("platform_admin"))


def _admin_guard_redirect():
    if not current_user.is_authenticated:
        return redirect(url_for("admin.login"))
    if not current_user.has_role("platform_admin"):
        flash(tr("Acesso negado.", getattr(g, "lang", None)), "error")
        return redirect(url_for("portal.home"))
    return None


@bp.route("/login", methods=["GET", "POST"])
def login():
    if _is_platform_admin(current_user):
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        identifier = (request.form.get("identifier") or "").strip()
        password = request.form.get("password") or ""

        if not identifier or not password:
            flash(tr("Preencha todos os campos.", getattr(g, "lang", None)), "error")
            return render_template("admin/login.html")

        user = (
            User.query
            .join(User.roles)
            .filter(Role.code == "platform_admin", User.email == identifier)
            .first()
        )

        if not user or not user.check_password(password):
            flash(tr("Credenciais inválidas.", getattr(g, "lang", None)), "error")
            return render_template("admin/login.html")

        login_user(user)
        clear_current_tenant()
        user.last_login_at = datetime.utcnow()
        db.session.commit()

        flash(tr("Login admin realizado com sucesso.", getattr(g, "lang", None)), "success")
        return redirect(url_for("admin.dashboard"))

    return render_template("admin/login.html")


@bp.route("/logout")
def logout():
    logout_user()
    clear_current_tenant()
    return redirect(url_for("admin.login"))


@bp.route("/")
def dashboard():
    guard = _admin_guard_redirect()
    if guard is not None:
        return guard

    plans = (
        SubscriptionPlan.query
        .filter_by(is_active=True)
        .order_by(SubscriptionPlan.display_order.asc(), SubscriptionPlan.name.asc())
        .all()
    )
    tenants = Tenant.query.order_by(Tenant.created_at.desc()).all()
    users = User.query.order_by(User.created_at.desc()).all()
    subscriptions = TenantSubscription.query.all()

    subscription_by_tenant = {row.tenant_id: row for row in subscriptions}
    tenant_by_id = {tenant.id: tenant for tenant in tenants}

    users_view = []
    for user in users:
        tenant = tenant_by_id.get(user.tenant_id)
        subscription = subscription_by_tenant.get(user.tenant_id)
        users_view.append(
            {
                "user": user,
                "tenant": tenant,
                "subscription": subscription,
                "plan_code": subscription.plan.code if subscription and subscription.plan else (tenant.plan if tenant else "-"),
                "plan_name": subscription.plan.name if subscription and subscription.plan else (tenant.plan if tenant else "-"),
            }
        )

    return render_template(
        "admin/dashboard.html",
        plans=plans,
        tenants=tenants,
        users_view=users_view,
        subscriptions=subscriptions,
    )


@bp.route("/set-user-plan", methods=["POST"])
def set_user_plan():
    guard = _admin_guard_redirect()
    if guard is not None:
        return guard

    user_id_raw = request.form.get("user_id")
    plan_code = (request.form.get("plan_code") or "").strip()
    billing_cycle = (request.form.get("billing_cycle") or "monthly").strip().lower()

    if not user_id_raw or not plan_code:
        flash(tr("Preencha todos os campos.", getattr(g, "lang", None)), "error")
        return redirect(url_for("admin.dashboard"))

    if billing_cycle not in ALLOWED_BILLING_CYCLES:
        billing_cycle = "monthly"

    try:
        user_id = int(user_id_raw)
    except ValueError:
        flash(tr("Configuration inválida.", getattr(g, "lang", None)), "error")
        return redirect(url_for("admin.dashboard"))

    user = User.query.get(user_id)
    plan = SubscriptionPlan.query.filter_by(code=plan_code, is_active=True).first()
    if not user or not plan:
        flash(tr("Configuração inválida.", getattr(g, "lang", None)), "error")
        return redirect(url_for("admin.dashboard"))

    tenant = Tenant.query.get(user.tenant_id)
    if not tenant:
        flash(tr("Tenant not found", getattr(g, "lang", None)), "error")
        return redirect(url_for("admin.dashboard"))

    now = datetime.utcnow()
    sub = TenantSubscription.query.filter_by(tenant_id=tenant.id).first()
    if not sub:
        sub = TenantSubscription(
            tenant_id=tenant.id,
            plan_id=plan.id,
            status="active",
            billing_cycle=billing_cycle,
            current_period_start=now,
            current_period_end=now,
            next_billing_date=now,
            current_users_count=0,
            current_companies_count=0,
            transactions_this_month=0,
        )
        db.session.add(sub)

    sub.plan_id = plan.id
    sub.status = "active"
    sub.billing_cycle = billing_cycle
    sub.current_period_start = now
    if billing_cycle == "yearly":
        sub.current_period_end = datetime(now.year + 1, now.month, min(now.day, 28), now.hour, now.minute, now.second)
    else:
        next_month = now.month + 1
        year = now.year
        if next_month > 12:
            year += 1
            next_month = 1
        sub.current_period_end = datetime(year, next_month, min(now.day, 28), now.hour, now.minute, now.second)
    sub.next_billing_date = sub.current_period_end

    tenant.plan = plan.code

    db.session.add(
        BillingEvent(
            tenant_id=tenant.id,
            subscription_id=sub.id,
            event_type="admin.subscription.updated",
            amount=plan.price_yearly if billing_cycle == "yearly" else plan.price_monthly,
            currency=plan.currency,
            metadata_json={
                "updated_by_user_id": current_user.id,
                "target_user_id": user.id,
                "plan_code": plan.code,
                "billing_cycle": billing_cycle,
            },
        )
    )
    db.session.commit()

    flash(
        tr("Assinatura atualizada para {email}.", getattr(g, "lang", None), email=user.email),
        "success",
    )
    return redirect(url_for("admin.dashboard"))


@bp.route("/change-password", methods=["POST"])
def change_admin_password():
    guard = _admin_guard_redirect()
    if guard is not None:
        return guard

    current_password = request.form.get("current_password") or ""
    new_password = request.form.get("new_password") or ""
    confirm_password = request.form.get("confirm_password") or ""

    if not current_password or not new_password or not confirm_password:
        flash(tr("Preencha todos os campos.", getattr(g, "lang", None)), "error")
        return redirect(url_for("admin.dashboard"))

    if not current_user.check_password(current_password):
        flash(tr("Senha atual inválida.", getattr(g, "lang", None)), "error")
        return redirect(url_for("admin.dashboard"))

    if new_password != confirm_password:
        flash(tr("As senhas não coincidem.", getattr(g, "lang", None)), "error")
        return redirect(url_for("admin.dashboard"))

    if len(new_password) < 12:
        flash(tr("A senha deve ter pelo menos 12 caracteres.", getattr(g, "lang", None)), "error")
        return redirect(url_for("admin.dashboard"))

    if new_password == current_password:
        flash(tr("A nova senha deve ser diferente da senha atual.", getattr(g, "lang", None)), "error")
        return redirect(url_for("admin.dashboard"))

    current_user.set_password(new_password)
    db.session.commit()
    flash(tr("Senha alterada com sucesso.", getattr(g, "lang", None)), "success")
    return redirect(url_for("admin.dashboard"))

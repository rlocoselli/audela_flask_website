from __future__ import annotations

from datetime import datetime

from flask import flash, redirect, render_template, request, url_for
from flask_login import login_user, logout_user

from ...extensions import db
from ...models.bi import AuditEvent
from ...models.core import Tenant, User, Role
from ...tenancy import CurrentTenant, set_current_tenant, clear_current_tenant
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
            flash("Tenant não encontrado.", "error")
            return render_template("portal/login.html")

        user = User.query.filter_by(tenant_id=tenant.id, email=email).first()
        if not user or not user.check_password(password):
            flash("Credenciais inválidas.", "error")
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
        return redirect(url_for("portal.home"))

    return render_template("portal/login.html")


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
            flash("Preencha todos os campos.", "error")
            return render_template("portal/bootstrap.html")

        if Tenant.query.filter_by(slug=tenant_slug).first():
            flash("Slug já existe.", "error")
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

        flash("Tenant criado. Faça login.", "success")
        return redirect(url_for("auth.login"))

    return render_template("portal/bootstrap.html")

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from functools import wraps

from flask import g, session, redirect, url_for, flash
from flask_login import current_user

from .i18n import tr


@dataclass(frozen=True)
class CurrentTenant:
    id: int
    slug: str
    name: str


def set_current_tenant(tenant: CurrentTenant) -> None:
    """Persist tenant in g + session.

    MVP strategy:
    - user logs in within a tenant context (tenant slug chosen at login)
    - tenant is stored in session

    Phase 2 options:
    - subdomain routing (tenant.example.com)
    - OIDC claim mapping (tid)
    """
    g.tenant = tenant
    session["tenant_id"] = tenant.id
    session["tenant_slug"] = tenant.slug


def get_current_tenant_id() -> Optional[int]:
    tid = getattr(g, "tenant", None)
    if tid is not None:
        return tid.id
    return session.get("tenant_id")


def clear_current_tenant() -> None:
    g.pop("tenant", None)
    session.pop("tenant_id", None)
    session.pop("tenant_slug", None)


def get_user_module_access(tenant, user_id: int | None) -> dict:
        """Return simple UAM module access flags for a user.

        Stored in tenant.settings_json under:
            {
                "uam": {
                    "module_access": {
                        "<user_id>": {"finance": true/false, "bi": true/false}
                    }
                }
            }

        Defaults to full access when missing.
        """
        if not tenant or user_id is None:
                return {"finance": True, "bi": True}

        settings = tenant.settings_json if isinstance(getattr(tenant, "settings_json", None), dict) else {}
        uam = settings.get("uam") if isinstance(settings.get("uam"), dict) else {}
        module_access = uam.get("module_access") if isinstance(uam.get("module_access"), dict) else {}
        row = module_access.get(str(int(user_id))) if isinstance(module_access, dict) else None
        if not isinstance(row, dict):
                row = {}

        return {
                "finance": bool(row.get("finance", True)),
                "bi": bool(row.get("bi", True)),
        }


def require_tenant(func):
    """
    Decorator to ensure a tenant context exists for the current user.
    Must be used after @login_required.
    
    If no tenant context is found, redirects to tenant login page.
    """
    @wraps(func)
    def decorated_view(*args, **kwargs):
        # Check if user has tenant context
        if not current_user.is_authenticated:
            flash(tr("Please log in to access this page.", getattr(g, "lang", None)), "warning")
            return redirect(url_for("tenant.login"))
        
        # Check if tenant_id exists
        if not hasattr(current_user, 'tenant_id') or current_user.tenant_id is None:
            flash(tr("No tenant context found. Please login with a tenant.", getattr(g, "lang", None)), "warning")
            return redirect(url_for("tenant.login"))
        
        # Ensure tenant is set in g
        if not hasattr(g, 'tenant') or g.tenant is None:
            # Try to restore from session
            tenant_id = session.get('tenant_id')
            if tenant_id:
                # Reconstruct tenant from session
                from .models import Tenant
                tenant = Tenant.query.get(tenant_id)
                if tenant:
                    g.tenant = CurrentTenant(
                        id=tenant.id,
                        slug=tenant.slug,
                        name=tenant.name
                    )
                else:
                    flash(tr("Tenant not found. Please login again.", getattr(g, "lang", None)), "danger")
                    return redirect(url_for("tenant.login"))
            else:
                flash(tr("No active tenant session. Please login.", getattr(g, "lang", None)), "warning")
                return redirect(url_for("tenant.login"))
        
        return func(*args, **kwargs)
    
    return decorated_view

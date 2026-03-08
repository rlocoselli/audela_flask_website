from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from functools import wraps

from flask import g, session, redirect, url_for, flash
from flask_login import current_user

from .i18n import tr


_DEFAULT_MENU_ACCESS: dict[str, list[str]] = {
    "finance": [
        "dashboard",
        "accounts",
        "transactions",
        "reports",
        "stats",
        "accounting",
        "pivot",
        "invoices",
        "alerts",
        "regulation",
        "liabilities",
        "investments",
        "recurring",
        "cashflow",
        "nii",
        "gaps",
        "liquidity",
        "risk",
        "settings",
        "imports",
        "help",
    ],
    "bi": [
        "home",
        "credit_origination",
        "sources",
        "api_sources",
        "web_extract",
        "integrations",
        "etl",
        "sources_diagram",
        "sql_editor",
        "excel_ai",
        "questions",
        "dashboards",
        "reports",
        "files",
        "statistics",
        "ratios",
        "ratio_indicator_create",
        "ratio_create",
        "alerting",
        "what_if",
        "explore",
        "ai_chat",
        "runs",
        "audit",
    ],
    "project": [
        "dashboard",
        "kanban",
        "gantt",
        "managers",
        "governance",
        "risks",
        "change",
        "reporting",
        "security",
        "notifications",
        "productivity",
        "deliverables",
        "ceremonies",
    ],
    "credit": [
        "overview",
        "borrowers",
        "deals",
        "facilities",
        "collateral",
        "guarantors",
        "statements",
        "ratios",
        "memos",
        "approvals",
        "backlog",
        "workflow",
        "documents",
    ],
}


def _normalize_bool_map(data: dict | None, keys: list[str], default_value: bool = True) -> dict[str, bool]:
    src = data if isinstance(data, dict) else {}
    return {k: bool(src.get(k, default_value)) for k in keys}


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
                        "<user_id>": {
                            "finance": true/false,
                            "bi": true/false,
                            "project": true/false,
                            "credit": true/false
                        }
                    }
                }
            }

        Defaults to full access when missing.
        """
        if not tenant or user_id is None:
            return {"finance": True, "bi": True, "project": True, "credit": True}

        settings = tenant.settings_json if isinstance(getattr(tenant, "settings_json", None), dict) else {}
        uam = settings.get("uam") if isinstance(settings.get("uam"), dict) else {}
        module_access = uam.get("module_access") if isinstance(uam.get("module_access"), dict) else {}
        row = module_access.get(str(int(user_id))) if isinstance(module_access, dict) else None
        if not isinstance(row, dict):
                row = {}

        return {
                "finance": bool(row.get("finance", True)),
                "bi": bool(row.get("bi", True)),
                "project": bool(row.get("project", True)),
            "credit": bool(row.get("credit", True)),
        }


def get_user_menu_access(tenant, user_id: int | None, product: str) -> dict[str, bool]:
    """Return menu-level permissions for a product and user.

    Stored under tenant.settings_json:
        settings_json["uam"]["menu_access"]["<user_id>"]["finance|bi|project"] = {
            "menu_key": true/false
        }

    Missing config defaults to full menu access.
    """
    product_key = str(product or "").strip().lower()
    defaults = _DEFAULT_MENU_ACCESS.get(product_key, [])
    if not defaults:
        return {}

    if not tenant or user_id is None:
        return {k: True for k in defaults}

    settings = tenant.settings_json if isinstance(getattr(tenant, "settings_json", None), dict) else {}
    uam = settings.get("uam") if isinstance(settings.get("uam"), dict) else {}
    menu_access = uam.get("menu_access") if isinstance(uam.get("menu_access"), dict) else {}
    by_user = menu_access.get(str(int(user_id))) if isinstance(menu_access.get(str(int(user_id))), dict) else {}
    row = by_user.get(product_key) if isinstance(by_user.get(product_key), dict) else {}
    return _normalize_bool_map(row, defaults, True)


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

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from flask import g, session


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

from __future__ import annotations

from datetime import datetime
import json
from io import BytesIO
import re
from uuid import uuid4

from flask import abort, flash, g, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
import pdfplumber

from ...extensions import csrf, db
from ...i18n import DEFAULT_LANG, normalize_lang, tr
from ...models.core import Tenant
from ...models.project_management import ProjectWorkspace
from ...services.ai_service import analyze_with_ai
from ...services.email_service import EmailService
from ...services.subscription_service import SubscriptionService
from ...tenancy import enforce_subscription_access_or_redirect, get_current_tenant_id, get_user_module_access, get_user_menu_access
from . import bp


def _(msgid: str, **kwargs):
    return tr(msgid, getattr(g, "lang", DEFAULT_LANG), **kwargs)


def _require_tenant() -> None:
    if not current_user.is_authenticated:
        abort(401)
    if not getattr(g, "tenant", None) or current_user.tenant_id != g.tenant.id:
        abort(403)


def _has_project_access(tenant: Tenant) -> bool:
    if not tenant or not getattr(tenant, "subscription", None) or not tenant.subscription.plan:
        return False
    if str(getattr(tenant.subscription.plan, "code", "")) == "free":
        return True
    return SubscriptionService.check_feature_access(tenant.id, "project")


def _is_tenant_admin() -> bool:
    has_role = getattr(current_user, "has_role", None)
    if not callable(has_role):
        return False
    return bool(has_role("tenant_admin"))


def _sanitize_state(payload: dict | None) -> dict:
    payload = payload or {}
    state = payload if isinstance(payload, dict) else {}

    def _list(name: str, max_items: int = 500):
        items = state.get(name)
        if not isinstance(items, list):
            return []
        return items[:max_items]

    selected_project_id = state.get("selected_project_id")
    if selected_project_id is not None:
        selected_project_id = str(selected_project_id)[:64]

    def _dict(name: str):
        value = state.get(name)
        return value if isinstance(value, dict) else {}

    return {
        "projects": _list("projects", 200),
        "selected_project_id": selected_project_id,
        "managers": _list("managers", 300),
        "cards": _list("cards", 1000),
        "ceremonies": _list("ceremonies", 300),
        "deliverables": _list("deliverables", 1000),
        "gantt": _list("gantt", 1000),
        "project_meta": _dict("project_meta"),
        "stakeholders": _list("stakeholders", 1000),
        "risks": _list("risks", 1000),
        "issues": _list("issues", 2000),
        "decisions": _list("decisions", 1000),
        "changes": _list("changes", 1000),
        "documents": _list("documents", 2000),
        "meetings": _list("meetings", 1000),
        "audit_log": _list("audit_log", 4000),
        "project_versions": _list("project_versions", 2000),
        "ai_builder": _dict("ai_builder"),
        "ai_builder_archives": _list("ai_builder_archives", 200),
        "security": _dict("security"),
        "notifications": _dict("notifications"),
    }


def _normalize_public_access(raw: str | None) -> str:
    return "rw" if str(raw or "").strip().lower() == "rw" else "ro"


def _normalize_public_column_order(raw) -> list[str]:
    valid = ["backlog", "todo", "doing", "done"]
    items = raw if isinstance(raw, list) else []
    normalized: list[str] = []
    for item in items:
        key = str(item or "").strip().lower()
        if key in valid and key not in normalized:
            normalized.append(key)
    for key in valid:
        if key not in normalized:
            normalized.append(key)
    return normalized


def _public_kanban_cfg(state: dict) -> dict:
    security = state.get("security") if isinstance(state.get("security"), dict) else {}
    share = security.get("public_kanban") if isinstance(security.get("public_kanban"), dict) else {}
    return {
        "enabled": bool(share.get("enabled", False)),
        "token": str(share.get("token") or "").strip(),
        "access": _normalize_public_access(share.get("access")),
        "project_id": str(share.get("project_id") or "").strip(),
        "expires_at": str(share.get("expires_at") or "").strip(),
        "column_order": _normalize_public_column_order(share.get("column_order")),
    }


def _save_public_kanban_cfg(state: dict, cfg: dict) -> None:
    security = state.get("security") if isinstance(state.get("security"), dict) else {}
    security["public_kanban"] = {
        "enabled": bool(cfg.get("enabled", False)),
        "token": str(cfg.get("token") or "").strip(),
        "access": _normalize_public_access(cfg.get("access")),
        "project_id": str(cfg.get("project_id") or "").strip(),
        "expires_at": str(cfg.get("expires_at") or "").strip(),
        "column_order": _normalize_public_column_order(cfg.get("column_order")),
    }
    state["security"] = security


def _parse_optional_iso_datetime(value: str | None) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None


def _is_public_share_expired(cfg: dict) -> bool:
    exp = _parse_optional_iso_datetime(cfg.get("expires_at"))
    if not exp:
        return False
    # datetime-local values are naive; compare them with local now to avoid
    # premature expiration caused by UTC offset differences.
    if exp.tzinfo is None:
        now = datetime.now()
    else:
        now = datetime.now(exp.tzinfo)
    return now > exp


def _find_public_workspace_by_token(token: str) -> tuple[ProjectWorkspace | None, dict, dict]:
    safe = str(token or "").strip()
    if len(safe) < 16:
        return None, {}, {}

    for ws in ProjectWorkspace.query.all():
        state = ws.state_json if isinstance(ws.state_json, dict) else {}
        cfg = _public_kanban_cfg(state)
        if cfg.get("enabled") and cfg.get("token") == safe and not _is_public_share_expired(cfg):
            return ws, state, cfg
    return None, {}, {}


def _sanitize_public_card(raw: dict, project_id: str) -> dict:
    card_id = str(raw.get("id") or "").strip()[:64] or uuid4().hex[:10]
    owners = raw.get("owners") if isinstance(raw.get("owners"), list) else []
    cleaned_owners = [str(x).strip()[:120] for x in owners if str(x or "").strip()][:8]
    owner = str(raw.get("owner") or "").strip()[:120]
    if not owner and cleaned_owners:
        owner = cleaned_owners[0]
    if owner and owner not in cleaned_owners:
        cleaned_owners.insert(0, owner)

    col = str(raw.get("col") or "todo").strip().lower()
    if col not in {"backlog", "todo", "doing", "done"}:
        col = "todo"

    priority = str(raw.get("priority") or "medium").strip().lower()
    if priority not in {"low", "medium", "high"}:
        priority = "medium"

    due_date = str(raw.get("due_date") or "").strip()[:10]
    if due_date and len(due_date) != 10:
        due_date = ""

    icon_raw = str(raw.get("icon") or "").strip()
    if re.match(r"^bi\s+bi-[a-z0-9-]+$", icon_raw, re.IGNORECASE):
        icon = icon_raw.lower()
    else:
        icon = icon_raw[:8]

    return {
        "id": card_id,
        "project_id": project_id,
        "title": str(raw.get("title") or "").strip()[:220],
        "icon": icon,
        "description": str(raw.get("description") or "").strip()[:2000],
        "owner": owner,
        "owners": cleaned_owners,
        "sprint": str(raw.get("sprint") or "").strip()[:80],
        "priority": priority,
        "due_date": due_date,
        "col": col,
    }


@bp.before_app_request
def _load_tenant_into_g() -> None:
    tenant_id = get_current_tenant_id()
    if getattr(g, "tenant", None) is None:
        g.tenant = None
        if tenant_id:
            tenant = Tenant.query.get(tenant_id)
            if tenant:
                g.tenant = tenant

    if (
        request.endpoint
        and request.endpoint.startswith("project.")
        and current_user.is_authenticated
        and getattr(g, "tenant", None)
        and current_user.tenant_id == g.tenant.id
    ):
        redirect_resp = enforce_subscription_access_or_redirect(current_user.tenant_id)
        if redirect_resp is not None:
            return redirect_resp

        access = get_user_module_access(g.tenant, current_user.id)
        if not access.get("project", True):
            flash(_("Accès Projet désactivé pour votre utilisateur."), "warning")
            return redirect(url_for("tenant.dashboard"))


@bp.app_context_processor
def _project_layout_context():
    tenant = getattr(g, "tenant", None)
    module_access = get_user_module_access(tenant, getattr(current_user, "id", None))
    project_menu_access = get_user_menu_access(tenant, getattr(current_user, "id", None), "project")
    return {
        "module_access": module_access,
        "project_menu_access": project_menu_access,
    }


@bp.route("/")
@login_required
def dashboard():
    _require_tenant()
    if not _has_project_access(g.tenant):
        flash(_("Le produit Projet n'est pas disponible dans votre plan actuel."), "warning")
        return redirect(url_for("billing.plans", product="project"))
    return render_template(
        "project/dashboard.html",
        tenant=g.tenant,
        title=_("AUDELA Projet"),
        is_tenant_admin=current_user.has_role("tenant_admin"),
    )


@bp.route("/api/workspace", methods=["GET"])
@login_required
def workspace_get():
    _require_tenant()
    if not _has_project_access(g.tenant):
        return jsonify({"ok": False, "error": _("Accès refusé au module Projet.")}), 403

    ws = ProjectWorkspace.query.filter_by(tenant_id=g.tenant.id).first()
    state = ws.state_json if ws and isinstance(ws.state_json, dict) else {}
    return jsonify({
        "ok": True,
        "state": _sanitize_state(state),
        "updated_at": ws.updated_at.isoformat() if ws and ws.updated_at else None,
    })


@bp.route("/api/workspace", methods=["POST"])
@login_required
def workspace_save():
    _require_tenant()
    if not _has_project_access(g.tenant):
        return jsonify({"ok": False, "error": _("Accès refusé au module Projet.")}), 403

    payload = request.get_json(silent=True) or {}
    state = _sanitize_state(payload.get("state") if isinstance(payload, dict) else {})

    ws = ProjectWorkspace.query.filter_by(tenant_id=g.tenant.id).first()
    previous_state = ws.state_json if ws and isinstance(ws.state_json, dict) else {}

    if not _is_tenant_admin():
        previous_security = previous_state.get("security") if isinstance(previous_state, dict) else {}
        state["security"] = previous_security if isinstance(previous_security, dict) else {}
        previous_notifications = previous_state.get("notifications") if isinstance(previous_state, dict) else {}
        state["notifications"] = previous_notifications if isinstance(previous_notifications, dict) else {}

    if not ws:
        ws = ProjectWorkspace(tenant_id=g.tenant.id)
        db.session.add(ws)

    ws.state_json = state
    ws.updated_by_user_id = getattr(current_user, "id", None)
    ws.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({"ok": True, "updated_at": ws.updated_at.isoformat() if ws.updated_at else None})


@bp.route("/api/public-kanban/share", methods=["POST"])
@login_required
def public_kanban_share_save():
    _require_tenant()
    if not _has_project_access(g.tenant):
        return jsonify({"ok": False, "error": _("Accès refusé au module Projet.")}), 403
    if not _is_tenant_admin():
        return jsonify({"ok": False, "error": _("Action réservée à l'administrateur tenant.")}), 403

    payload = request.get_json(silent=True) or {}
    enable = bool(payload.get("enabled", False))
    regenerate = bool(payload.get("regenerate", False))
    access = _normalize_public_access(payload.get("access"))
    expires_at_raw = str(payload.get("expires_at") or "").strip()

    if expires_at_raw and not _parse_optional_iso_datetime(expires_at_raw):
        return jsonify({"ok": False, "error": _("Date d'expiration invalide.")}), 400

    ws = ProjectWorkspace.query.filter_by(tenant_id=g.tenant.id).first()
    if not ws:
        ws = ProjectWorkspace(tenant_id=g.tenant.id, state_json=_sanitize_state({}))
        db.session.add(ws)

    state = ws.state_json if isinstance(ws.state_json, dict) else _sanitize_state({})
    cfg = _public_kanban_cfg(state)

    selected_project_id = str(payload.get("project_id") or cfg.get("project_id") or state.get("selected_project_id") or "").strip()
    if enable and not selected_project_id:
        return jsonify({"ok": False, "error": _("Sélectionnez un projet avant de partager le Kanban.")}), 400

    if enable:
        token = str(cfg.get("token") or "").strip()
        if regenerate or not token:
            token = uuid4().hex + uuid4().hex
        cfg.update({
            "enabled": True,
            "token": token,
            "access": access,
            "project_id": selected_project_id,
            "expires_at": expires_at_raw,
        })
    else:
        cfg.update({
            "enabled": False,
            "access": access,
            "project_id": selected_project_id,
            "expires_at": expires_at_raw,
        })

    _save_public_kanban_cfg(state, cfg)
    ws.state_json = _sanitize_state(state)
    ws.updated_by_user_id = getattr(current_user, "id", None)
    ws.updated_at = datetime.utcnow()
    db.session.commit()

    share_url = url_for("project.public_kanban", token=cfg.get("token"), _external=True) if cfg.get("enabled") and cfg.get("token") else ""
    return jsonify({
        "ok": True,
        "share": {
            "enabled": bool(cfg.get("enabled")),
            "access": _normalize_public_access(cfg.get("access")),
            "project_id": str(cfg.get("project_id") or ""),
            "token": str(cfg.get("token") or ""),
            "expires_at": str(cfg.get("expires_at") or ""),
            "column_order": _normalize_public_column_order(cfg.get("column_order")),
            "url": share_url,
        },
    })


@bp.route("/api/public-kanban/share/email", methods=["POST"])
@login_required
def public_kanban_share_email_send():
    _require_tenant()
    if not _has_project_access(g.tenant):
        return jsonify({"ok": False, "error": _("Accès refusé au module Projet.")}), 403
    if not _is_tenant_admin():
        return jsonify({"ok": False, "error": _("Action réservée à l'administrateur tenant.")}), 403

    payload = request.get_json(silent=True) or {}
    raw = str(payload.get("emails") or "").strip()
    if not raw:
        return jsonify({"ok": False, "error": _("Veuillez renseigner au moins un email.")}), 400

    emails = []
    for item in re.split(r"[;,\n]", raw):
        addr = str(item or "").strip().lower()
        if addr and addr not in emails:
            emails.append(addr)

    if not emails:
        return jsonify({"ok": False, "error": _("Veuillez renseigner au moins un email.")}), 400
    if len(emails) > 30:
        return jsonify({"ok": False, "error": _("Maximum 30 emails par envoi.")}), 400

    invalid = [e for e in emails if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", e)]
    if invalid:
        return jsonify({"ok": False, "error": _("Emails invalides: {emails}", emails=", ".join(invalid[:5]))}), 400

    ws = ProjectWorkspace.query.filter_by(tenant_id=g.tenant.id).first()
    state = ws.state_json if ws and isinstance(ws.state_json, dict) else {}
    cfg = _public_kanban_cfg(state)
    if not cfg.get("enabled") or not cfg.get("token"):
        return jsonify({"ok": False, "error": _("Activez d'abord le partage public pour générer un lien.")}), 400
    if _is_public_share_expired(cfg):
        return jsonify({"ok": False, "error": _("Le lien public est expiré. Régénérez un nouveau lien.")}), 400

    share_url = url_for("project.public_kanban", token=str(cfg.get("token") or ""), _external=True)
    project_id = str(cfg.get("project_id") or "").strip()
    projects = state.get("projects") if isinstance(state.get("projects"), list) else []
    project_row = next((p for p in projects if str((p or {}).get("id") or "") == project_id), None)
    project_name = str((project_row or {}).get("name") or _("Projet"))
    access_label = _("lecture et écriture") if _normalize_public_access(cfg.get("access")) == "rw" else _("lecture seule")
    expires_at = str(cfg.get("expires_at") or "").strip()

    subject = _("Lien Kanban partagé - {project}", project=project_name)
    body_lines = [
        _("Bonjour,"),
        "",
        _("Voici le lien de partage du Kanban du projet {project}.", project=project_name),
        _("Accès: {access}", access=access_label),
    ]
    if expires_at:
        body_lines.append(_("Expiration: {expiration}", expiration=expires_at.replace("T", " ").strip()[:16]))
    body_lines.extend([
        "",
        share_url,
        "",
        _("Message envoyé depuis AUDELA Projet."),
    ])
    body = "\n".join(body_lines)

    sent = []
    failed = []
    for email in emails:
        ok = EmailService.send_email(to=email, subject=subject, template=None, body_text=body)
        if ok:
            sent.append(email)
        else:
            failed.append(email)

    return jsonify({
        "ok": len(sent) > 0,
        "sent_count": len(sent),
        "failed_count": len(failed),
        "sent": sent,
        "failed": failed,
    }), (200 if sent else 500)


@bp.route("/public/kanban/<token>", methods=["GET"])
def public_kanban(token: str):
    ws, _state, cfg = _find_public_workspace_by_token(token)
    if not ws:
        return render_template(
            "project/public_kanban.html",
            token="invalid_public_link_token",
            access="ro",
            expires_at="",
            link_error=True,
        ), 404
    return render_template(
        "project/public_kanban.html",
        token=str(cfg.get("token") or ""),
        access=_normalize_public_access(cfg.get("access")),
        expires_at=str(cfg.get("expires_at") or ""),
        link_error=False,
    )


@bp.route("/public/kanban/<token>/state", methods=["GET"])
def public_kanban_state(token: str):
    ws, state, cfg = _find_public_workspace_by_token(token)
    if not ws:
        return jsonify({"ok": False, "error": "not_found"}), 404

    project_id = str(cfg.get("project_id") or "").strip()
    cards = [
        c for c in (state.get("cards") if isinstance(state.get("cards"), list) else [])
        if str((c or {}).get("project_id") or "") == project_id
    ]
    projects = state.get("projects") if isinstance(state.get("projects"), list) else []
    project_row = next((p for p in projects if str((p or {}).get("id") or "") == project_id), None)

    return jsonify({
        "ok": True,
        "share": {
            "access": _normalize_public_access(cfg.get("access")),
            "project_id": project_id,
            "expires_at": str(cfg.get("expires_at") or ""),
            "column_order": _normalize_public_column_order(cfg.get("column_order")),
        },
        "project": project_row if isinstance(project_row, dict) else {"id": project_id, "name": "Project"},
        "cards": cards,
        "updated_at": ws.updated_at.isoformat() if ws.updated_at else None,
    })


@bp.route("/public/kanban/<token>/state", methods=["POST"])
@csrf.exempt
def public_kanban_state_save(token: str):
    ws, state, cfg = _find_public_workspace_by_token(token)
    if not ws:
        return jsonify({"ok": False, "error": "not_found"}), 404
    if _normalize_public_access(cfg.get("access")) != "rw":
        return jsonify({"ok": False, "error": "read_only"}), 403

    payload = request.get_json(silent=True) or {}
    incoming_cards = payload.get("cards") if isinstance(payload.get("cards"), list) else []
    column_order = _normalize_public_column_order(payload.get("column_order"))
    project_id = str(cfg.get("project_id") or "").strip()
    cleaned_cards = [_sanitize_public_card(c, project_id) for c in incoming_cards if isinstance(c, dict)]

    all_cards = state.get("cards") if isinstance(state.get("cards"), list) else []
    other_cards = [c for c in all_cards if str((c or {}).get("project_id") or "") != project_id]
    state["cards"] = other_cards + cleaned_cards
    cfg["column_order"] = column_order
    _save_public_kanban_cfg(state, cfg)

    ws.state_json = _sanitize_state(state)
    ws.updated_by_user_id = None
    ws.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({"ok": True, "count": len(cleaned_cards), "updated_at": ws.updated_at.isoformat() if ws.updated_at else None})


def _project_ai_extract_sprints(text: str) -> int:
    m = re.search(r"(\d+)\s*sprint", text, flags=re.IGNORECASE)
    if not m:
        m = re.search(r"sprint\s*(\d+)", text, flags=re.IGNORECASE)
    if not m:
        return 0
    try:
        return max(1, min(12, int(m.group(1))))
    except Exception:
        return 0


def _project_ai_extract_name(text: str) -> str:
    q = re.search(r"[\"“](.+?)[\"”]", text)
    if q and q.group(1):
        return str(q.group(1)).strip()[:120]
    m = re.search(r"(?:projeto|project)\s+([\w\-\s]{4,60})", text, flags=re.IGNORECASE)
    if not m:
        return ""
    return str(m.group(1)).strip()[:120]


def _project_ai_extract_type(text: str) -> str:
    t = (text or "").lower()
    if re.search(r"mobile|app", t):
        return "Mobile"
    if re.search(r"web|portal|site", t):
        return "Web"
    if re.search(r"iot|device|sensor|capteur", t):
        return "IoT"
    if re.search(r"data|bi|analytics|etl", t):
        return "Data/BI"
    if re.search(r"finance|fintech|bank", t):
        return "Finance"
    return ""


def _project_ai_extract_responsibles(text: str) -> list[str]:
    raw = str(text or "").strip()
    if not raw:
        return []

    pattern = re.compile(
        r"(?:respons[aá]vel(?:eis)?|respons[aá]veis?|owners?|responsables?)\s*(?::|\-|\bé\b|\bis\b)?\s*(.+)$",
        flags=re.IGNORECASE,
    )
    m = pattern.search(raw)
    if not m:
        return []

    candidate = str(m.group(1) or "").strip()
    if not candidate:
        return []

    out: list[str] = []
    parts = re.split(r"[,;/]|\se\s|\sand\s|\s+\+\s+", candidate, flags=re.IGNORECASE)
    for part in parts:
        name = re.sub(r"^(?:o|a|os|as|um|uma|the)\s+", "", str(part or "").strip(), flags=re.IGNORECASE)
        name = re.sub(r"^[\-:\s]+", "", name)
        name = re.sub(r"\s+(?:por favor|please)$", "", name, flags=re.IGNORECASE)
        if not name:
            continue
        if re.fullmatch(r"(?:respons[aá]vel(?:eis)?|respons[aá]veis?|owner|owners?)", name, flags=re.IGNORECASE):
            continue
        if name not in out:
            out.append(name[:120])
    return out[:8]


def _project_ai_merge_draft(base: dict, incoming: dict) -> dict:
    def _safe_float(value, default=0.0):
        try:
            return float(value)
        except Exception:
            return float(default)

    def _safe_int(value, default=0):
        try:
            return int(value)
        except Exception:
            return int(default)

    out = {
        "name": str(base.get("name") or "").strip()[:120],
        "type": str(base.get("type") or "").strip()[:80],
        "sprints": _safe_int(base.get("sprints") or 0, 0) if str(base.get("sprints") or "").strip() else 0,
        "responsibles": [str(x).strip()[:120] for x in (base.get("responsibles") or []) if str(x).strip()][:8],
        "work_hours_per_day": _safe_float(base.get("work_hours_per_day") or 8, 8.0) if str(base.get("work_hours_per_day") or "").strip() else 8.0,
        "available_hours_per_day": _safe_float(base.get("available_hours_per_day") or 8, 8.0) if str(base.get("available_hours_per_day") or "").strip() else 8.0,
        "context": str(base.get("context") or "").strip()[:2000],
    }

    if isinstance(incoming, dict):
        if str(incoming.get("name") or "").strip():
            out["name"] = str(incoming.get("name") or "").strip()[:120]
        if str(incoming.get("type") or "").strip():
            out["type"] = str(incoming.get("type") or "").strip()[:80]
        try:
            s = int(incoming.get("sprints") or 0)
        except Exception:
            s = 0
        if s > 0:
            out["sprints"] = max(1, min(12, s))
        resp = incoming.get("responsibles") if isinstance(incoming.get("responsibles"), list) else []
        merged_resp = out["responsibles"] + [str(x).strip()[:120] for x in resp if str(x).strip()]
        dedup: list[str] = []
        for name in merged_resp:
            if name not in dedup:
                dedup.append(name)
        out["responsibles"] = dedup[:8]
        try:
            wh = float(incoming.get("work_hours_per_day") or out.get("work_hours_per_day") or 8)
        except Exception:
            wh = 8.0
        try:
            ah = float(incoming.get("available_hours_per_day") or out.get("available_hours_per_day") or 8)
        except Exception:
            ah = 8.0
        out["work_hours_per_day"] = max(1.0, min(12.0, wh))
        out["available_hours_per_day"] = max(1.0, min(12.0, ah))
        if str(incoming.get("context") or "").strip():
            out["context"] = str(incoming.get("context") or "").strip()[:2000]
    return out


def _project_ai_extract_hours(text: str) -> tuple[float | None, float | None]:
    t = text or ""
    m_work = re.search(r"(?:carga|trabalho|work)\s*(?:de)?\s*(\d+(?:[\.,]\d+)?)\s*h", t, flags=re.IGNORECASE)
    m_avail = re.search(r"(?:dispon[ií]veis?|capacidade|available)\s*(?:de)?\s*(\d+(?:[\.,]\d+)?)\s*h", t, flags=re.IGNORECASE)
    w = None
    a = None
    if m_work:
        try:
            w = float(m_work.group(1).replace(",", "."))
        except Exception:
            w = None
    if m_avail:
        try:
            a = float(m_avail.group(1).replace(",", "."))
        except Exception:
            a = None
    return w, a


def _project_ai_task_description(task: str, sprint: str, owner: str, context: str, lang: str) -> str:
    l = normalize_lang(lang)
    t = (task or "").lower()

    def _pick(mapping: dict[str, str], default: str) -> str:
        return mapping.get(l, default)

    if "backlog" in t or "refin" in t:
        objective = _pick({
            "pt": "Detalhar epicos e quebrar em historias prontas para sprint.",
            "en": "Detail epics and split into sprint-ready stories.",
            "es": "Detallar épicas y dividir en historias listas para sprint.",
            "it": "Dettagliare le epic e suddividerle in storie pronte per lo sprint.",
            "de": "Epics detaillieren und in sprintreife Stories aufteilen.",
            "fr": "Detailler les epics et decouper en stories pretes pour le sprint.",
        }, "Detalhar epicos e quebrar em historias prontas para sprint.")
    elif "ux" in t or "design" in t:
        objective = _pick({
            "pt": "Definir navegacao e telas-chave com especificacao pronta para handoff.",
            "en": "Define navigation and key screens with handoff-ready specs.",
            "es": "Definir navegacion y pantallas clave con especificacion para handoff.",
            "it": "Definire navigazione e schermate chiave con specifiche pronte per handoff.",
            "de": "Navigation und Kernscreens mit uebergabereifen Specs definieren.",
            "fr": "Definir la navigation et les ecrans cles avec des specs pretes au handoff.",
        }, "Definir navegacao e telas-chave com especificacao pronta para handoff.")
    elif "backend" in t:
        objective = _pick({
            "pt": "Implementar camada de servicos, validacoes e contratos de API.",
            "en": "Implement service layer, validations and API contracts.",
            "es": "Implementar capa de servicios, validaciones y contratos de API.",
            "it": "Implementare service layer, validazioni e contratti API.",
            "de": "Service-Layer, Validierungen und API-Vertraege implementieren.",
            "fr": "Implementer la couche service, les validations et les contrats API.",
        }, "Implementar camada de servicos, validacoes e contratos de API.")
    elif "frontend" in t:
        objective = _pick({
            "pt": "Construir fluxos, formularios e estados alinhados com APIs backend.",
            "en": "Build user flows, forms and states aligned with backend APIs.",
            "es": "Construir flujos, formularios y estados alineados con APIs backend.",
            "it": "Realizzare flussi utente, form e stati allineati alle API backend.",
            "de": "User-Flows, Formulare und Zustaende passend zu Backend-APIs umsetzen.",
            "fr": "Construire les parcours, formulaires et etats alignes aux APIs backend.",
        }, "Construir fluxos, formularios e estados alinhados com APIs backend.")
    elif "qa" in t or "test" in t or "integra" in t:
        objective = _pick({
            "pt": "Executar testes de integracao e validar cenarios criticos.",
            "en": "Execute integration tests and validate critical scenarios.",
            "es": "Ejecutar pruebas de integracion y validar escenarios criticos.",
            "it": "Eseguire test di integrazione e validare scenari critici.",
            "de": "Integrationstests ausfuehren und kritische Szenarien validieren.",
            "fr": "Executer les tests d'integration et valider les scenarios critiques.",
        }, "Executar testes de integracao e validar cenarios criticos.")
    else:
        objective = _pick({
            "pt": "Executar entrega incremental com validacao no fim da sprint.",
            "en": "Deliver incrementally and validate by sprint end.",
            "es": "Entregar de forma incremental y validar al final del sprint.",
            "it": "Consegna incrementale con validazione a fine sprint.",
            "de": "Inkrementell liefern und bis Sprintende validieren.",
            "fr": "Livrer de facon incrementale et valider en fin de sprint.",
        }, "Executar entrega incremental com validacao no fim da sprint.")

    labels = {
        "pt": ("Objetivo", "Escopo", "Criterios de aceite", "Dependencias", "Notas de execucao", "Responsavel", "Sprint"),
        "en": ("Objective", "Scope", "Acceptance criteria", "Dependencies", "Execution notes", "Owner", "Sprint"),
        "es": ("Objetivo", "Alcance", "Criterios de aceptacion", "Dependencias", "Notas de ejecucion", "Responsable", "Sprint"),
        "it": ("Obiettivo", "Ambito", "Criteri di accettazione", "Dipendenze", "Note di esecuzione", "Responsabile", "Sprint"),
        "de": ("Ziel", "Umfang", "Akzeptanzkriterien", "Abhaengigkeiten", "Ausfuehrungsnotizen", "Verantwortlich", "Sprint"),
        "fr": ("Objectif", "Perimetre", "Criteres d'acceptation", "Dependances", "Notes d'execution", "Responsable", "Sprint"),
    }
    o, s, c, d, n, ow, sp = labels.get(l, labels["pt"])
    ctx = (context or "").strip() or "-"
    owner_v = (owner or "-").strip() or "-"
    sprint_v = (sprint or "-").strip() or "-"

    return "\n".join([
        f"{o}: {objective}",
        f"{s}: {ctx}",
        f"{c}: 1) Entrega validada 2) Sem bloqueios criticos 3) Evidencia registrada",
        f"{d}: APIs, dados de homologacao, revisao tecnica",
        f"{n}: {ow} {owner_v} | {sp} {sprint_v}",
    ])


def _project_ai_task_priority(task: str) -> str:
    t = (task or "").lower()
    if any(k in t for k in ["integration", "integracao", "integration and tests", "backend", "bloqueio", "critical", "critico"]):
        return "high"
    if any(k in t for k in ["review", "retro", "planning", "refinement", "backlog", "ux", "design"]):
        return "medium"
    return "medium"


def _project_family(project_type: str) -> str:
    t = (project_type or "").strip().lower()
    if any(k in t for k in ["eng", "engenh", "engineering", "naval", "nuclear", "industrial", "construction", "civil", "mechanic", "mecanic"]):
        return "engineering"
    return "software"


def _project_ai_fallback_plan(draft: dict) -> list[dict]:
    def _safe_float(value, default=0.0):
        try:
            return float(value)
        except Exception:
            return float(default)

    sprints = max(1, min(12, int(draft.get("sprints") or 3)))
    owners = [str(x).strip() for x in (draft.get("responsibles") or []) if str(x).strip()] or ["PM"]
    work_hpd = max(1.0, min(12.0, _safe_float(draft.get("work_hours_per_day") or 8, 8.0)))
    avail_hpd = max(1.0, min(12.0, _safe_float(draft.get("available_hours_per_day") or 8, 8.0)))
    context = str(draft.get("context") or "").strip()[:500]
    lang = normalize_lang(str(draft.get("lang") or DEFAULT_LANG))
    complexity = str(draft.get("type") or "").lower()
    family = _project_family(complexity)
    base_days = 8 if complexity in {"web", "mobile"} else 10
    if complexity in {"iot", "data/bi", "finance"}:
        base_days = 10

    plan: list[dict] = []
    prev_review_ref: str | None = None
    for i in range(1, sprints + 1):
        sprint = f"Sprint {i}"
        owner_a = owners[(i - 1) % len(owners)]
        owner_b = owners[(i + 0) % len(owners)] if owners else owner_a
        owner_c = owners[(i + 1) % len(owners)] if owners else owner_a
        owner_q = owners[(i + 2) % len(owners)] if owners else owner_a

        backlog_ref = f"S{i}-backlog"
        ux_ref = f"S{i}-ux"
        be_ref = f"S{i}-be"
        fe_ref = f"S{i}-fe"
        qa_ref = f"S{i}-qa"
        review_ref = f"S{i}-review"
        retro_ref = f"S{i}-retro"

        be_days = max(3, base_days - 4)
        fe_days = max(3, base_days - 4)

        if family == "engineering":
            task_backlog = f"{sprint} - Scope and requirements freeze"
            task_ux = f"{sprint} - Engineering concept design"
            task_be = f"{sprint} - Detailed engineering and interfaces"
            task_fe = f"{sprint} - Procurement and fabrication package"
            task_qa = f"{sprint} - Verification, QA and compliance checks"
        else:
            task_backlog = f"{sprint} - Backlog refinement"
            task_ux = f"{sprint} - UX/UI definition"
            task_be = f"{sprint} - Backend implementation"
            task_fe = f"{sprint} - Frontend implementation"
            task_qa = f"{sprint} - Integration and tests"
        task_review = f"{sprint} - Sprint review"
        task_retro = f"{sprint} - Retro and next planning"

        plan.append({"ref": backlog_ref, "sprint": sprint, "task": task_backlog, "owner": owner_a, "duration_days": 1, "work_hours_per_day": work_hpd, "available_hours_per_day": avail_hpd, "predecessor_ref": prev_review_ref, "dependency_type": "FS", "description": _project_ai_task_description(task_backlog, sprint, owner_a, context, lang), "priority": _project_ai_task_priority(task_backlog)})
        plan.append({"ref": ux_ref, "sprint": sprint, "task": task_ux, "owner": owner_b, "duration_days": 2, "work_hours_per_day": work_hpd, "available_hours_per_day": avail_hpd, "predecessor_ref": backlog_ref, "dependency_type": "FS", "description": _project_ai_task_description(task_ux, sprint, owner_b, context, lang), "priority": _project_ai_task_priority(task_ux)})
        plan.append({"ref": be_ref, "sprint": sprint, "task": task_be, "owner": owner_b, "duration_days": be_days, "work_hours_per_day": work_hpd, "available_hours_per_day": avail_hpd, "predecessor_ref": backlog_ref, "dependency_type": "FS", "description": _project_ai_task_description(task_be, sprint, owner_b, context, lang), "priority": _project_ai_task_priority(task_be)})
        plan.append({"ref": fe_ref, "sprint": sprint, "task": task_fe, "owner": owner_c, "duration_days": fe_days, "work_hours_per_day": work_hpd, "available_hours_per_day": avail_hpd, "predecessor_ref": ux_ref, "dependency_type": "FS", "description": _project_ai_task_description(task_fe, sprint, owner_c, context, lang), "priority": _project_ai_task_priority(task_fe)})
        # Start integration in parallel with frontend/backend completion to reduce critical concentration.
        plan.append({"ref": qa_ref, "sprint": sprint, "task": task_qa, "owner": owner_q, "duration_days": 2, "work_hours_per_day": work_hpd, "available_hours_per_day": avail_hpd, "predecessor_ref": be_ref, "dependency_type": "FS", "description": _project_ai_task_description(task_qa, sprint, owner_q, context, lang), "priority": _project_ai_task_priority(task_qa)})
        plan.append({"ref": review_ref, "sprint": sprint, "task": task_review, "owner": owner_a, "duration_days": 1, "work_hours_per_day": work_hpd, "available_hours_per_day": avail_hpd, "predecessor_ref": qa_ref, "dependency_type": "FS", "description": _project_ai_task_description(task_review, sprint, owner_a, context, lang), "priority": _project_ai_task_priority(task_review)})
        plan.append({"ref": retro_ref, "sprint": sprint, "task": task_retro, "owner": owner_a, "duration_days": 1, "work_hours_per_day": work_hpd, "available_hours_per_day": avail_hpd, "predecessor_ref": review_ref, "dependency_type": "FS", "description": _project_ai_task_description(task_retro, sprint, owner_a, context, lang), "priority": _project_ai_task_priority(task_retro)})
        prev_review_ref = review_ref

    return plan


def _project_ai_extract_pdf_text(uploaded_file) -> str:
    if not uploaded_file or not getattr(uploaded_file, "filename", None):
        return ""
    filename = str(uploaded_file.filename or "").strip().lower()
    if not filename.endswith(".pdf"):
        return ""
    try:
        raw = uploaded_file.read() or b""
    except Exception:
        return ""
    if not raw:
        return ""
    # Reset cursor in case other code needs this file object later.
    try:
        uploaded_file.stream.seek(0)
    except Exception:
        pass

    chunks: list[str] = []
    try:
        with pdfplumber.open(BytesIO(raw)) as pdf:
            for page in (pdf.pages or [])[:20]:
                text = (page.extract_text() or "").strip()
                if text:
                    chunks.append(text)
                if sum(len(c) for c in chunks) >= 16000:
                    break
    except Exception:
        return ""
    return "\n\n".join(chunks)[:16000]


def _project_ai_safe_charter(ai_charter: dict | None) -> dict:
    src = ai_charter if isinstance(ai_charter, dict) else {}
    return {
        "objectives": str(src.get("objectives") or "").strip()[:3000],
        "scope": str(src.get("scope") or "").strip()[:3000],
        "deliverables": str(src.get("deliverables") or "").strip()[:5000],
        "milestones": str(src.get("milestones") or "").strip()[:5000],
    }


def _project_ai_fallback_charter(draft: dict, plan_tasks: list[dict], lang: str) -> dict:
    project_name = str(draft.get("name") or "Projeto").strip() or "Projeto"
    project_type = str(draft.get("type") or "Digital").strip() or "Digital"
    context = str(draft.get("context") or "").strip()
    family = _project_family(project_type)
    sprint_names: list[str] = []
    tasks_by_sprint: dict[str, list[str]] = {}

    for row in plan_tasks:
        if not isinstance(row, dict):
            continue
        sprint = str(row.get("sprint") or "").strip()
        task = str(row.get("task") or "").strip()
        if not sprint or not task:
            continue
        if sprint not in tasks_by_sprint:
            tasks_by_sprint[sprint] = []
            sprint_names.append(sprint)
        if len(tasks_by_sprint[sprint]) < 2:
            tasks_by_sprint[sprint].append(task)

    if not sprint_names:
        sprint_total = max(1, min(12, int(draft.get("sprints") or 3)))
        sprint_names = [f"Sprint {i}" for i in range(1, sprint_total + 1)]

    deliverable_lines = []
    milestone_lines = []
    milestone_prefix = "Gate" if family == "engineering" else "Milestone"
    for sprint in sprint_names:
        picks = tasks_by_sprint.get(sprint, [])
        if picks:
            deliverable_lines.append(f"- {sprint}: {' + '.join(picks)}")
            milestone_lines.append(f"- {milestone_prefix}: {picks[0]}")
        else:
            deliverable_lines.append(f"- {sprint}")
            milestone_lines.append(f"- {milestone_prefix}: {sprint}")

    objective = (
        f'Entregar o projeto "{project_name}" com incrementos validados por sprint, '
        "com nomenclatura e entregas alinhadas ao dominio tecnico informado."
    )
    scope = f"Escopo: {project_type}.\nContexto: {context or 'Definir no kickoff com stakeholders.'}"
    return {
        "objectives": objective[:3000],
        "scope": scope[:3000],
        "deliverables": "\n".join(deliverable_lines)[:5000],
        "milestones": "\n".join(milestone_lines)[:5000],
    }


def _project_ai_needs_sprint_name_enrichment(plan_tasks: list[dict]) -> bool:
    sprint_names = []
    for row in plan_tasks:
        if not isinstance(row, dict):
            continue
        sn = str(row.get("sprint") or "").strip()
        if sn and sn not in sprint_names:
            sprint_names.append(sn)
    if len(sprint_names) < 2:
        return False

    generic_count = 0
    for sn in sprint_names:
        if re.fullmatch(r"(?i)(sprint|iteration|iteracao|iteração|fase|phase)\s*\d+", sn):
            generic_count += 1
    return generic_count == len(sprint_names)


def _project_ai_enrich_sprint_names_with_ai(draft: dict, plan_tasks: list[dict], history: list, lang: str) -> list[dict]:
    if not _project_ai_needs_sprint_name_enrichment(plan_tasks):
        return plan_tasks

    sprint_buckets: list[dict] = []
    seen: dict[str, list[str]] = {}
    order: list[str] = []
    for row in plan_tasks:
        if not isinstance(row, dict):
            continue
        sn = str(row.get("sprint") or "").strip()
        task = str(row.get("task") or "").strip()
        if not sn:
            continue
        if sn not in seen:
            seen[sn] = []
            order.append(sn)
        if task and len(seen[sn]) < 6:
            seen[sn].append(task)
    for sn in order:
        sprint_buckets.append({"sprint": sn, "tasks": seen.get(sn, [])})
    if not sprint_buckets:
        return plan_tasks

    prompt = (
        "Rename sprint names so they match project type and task set. "
        "Avoid generic names like 'Sprint 1'. "
        "For engineering/naval/nuclear projects, avoid UX/app wording and prefer engineering/compliance vocabulary. "
        "Return JSON key 'sprint_names' as array of objects with fields 'from' and 'to'. "
        "Keep each 'to' under 48 chars and include sprint number prefix, e.g. 'Sprint 1 - Concept and interfaces'."
    )
    data_bundle = {
        "source": "project-ai-sprint-renaming",
        "question": prompt,
        "result": {
            "draft": draft,
            "sprint_buckets": sprint_buckets,
        },
    }

    try:
        ai = analyze_with_ai(
            data_bundle=data_bundle,
            user_message="Generate contextual sprint names",
            history=(history or [])[-6:],
            lang=lang,
            extra_json_keys=["sprint_names"],
        )
    except Exception:
        return plan_tasks

    raw_rows = ai.get("sprint_names") if isinstance(ai, dict) and isinstance(ai.get("sprint_names"), list) else []
    mapping: dict[str, str] = {}
    for row in raw_rows[:30]:
        if not isinstance(row, dict):
            continue
        src = str(row.get("from") or "").strip()[:40]
        dst = str(row.get("to") or "").strip()[:60]
        if not src or not dst:
            continue
        if not re.search(r"\d+", dst):
            continue
        mapping[src] = dst
    if not mapping:
        return plan_tasks

    renamed: list[dict] = []
    for row in plan_tasks:
        if not isinstance(row, dict):
            continue
        item = dict(row)
        sn = str(item.get("sprint") or "").strip()
        if sn in mapping:
            item["sprint"] = mapping[sn]
        renamed.append(item)
    return renamed


def _project_ai_sanitize_sprint_name_for_family(sprint_name: str, family: str) -> str:
    out = str(sprint_name or "").strip()
    if not out or family != "engineering":
        return out

    m = re.match(r"^(Sprint\s*\d+\s*-\s*)(.+)$", out, flags=re.IGNORECASE)
    prefix = m.group(1) if m else ""
    body = m.group(2) if m else out

    if re.search(r"\b(planning|planification|planificacion|planejamento|pianificazione|planung|ux|ui|frontend|backend)\b", body, flags=re.IGNORECASE):
        return f"{prefix}Engineering and compliance" if prefix else "Engineering and compliance"

    body = re.sub(r"\b(planning|planification|planificacion|planejamento|pianificazione|planung)\b", "engineering", body, flags=re.IGNORECASE)
    body = re.sub(r"\b(ux|ui)\b", "engineering", body, flags=re.IGNORECASE)
    body = re.sub(r"\b(frontend|backend)\b", "interfaces", body, flags=re.IGNORECASE)
    body = re.sub(r"\s+and\s+ux\b", " and compliance", body, flags=re.IGNORECASE)
    body = re.sub(r"\s+e\s+ux\b", " e conformidade", body, flags=re.IGNORECASE)
    body = re.sub(r"\s+", " ", body).strip()

    if re.search(r"\b(ux|ui|frontend|backend)\b", body, flags=re.IGNORECASE):
        body = "Engineering and compliance"
    if not body:
        body = "Engineering and compliance"
    return f"{prefix}{body}" if prefix else body


def _project_ai_default_smart_questions(draft: dict, plan_tasks: list[dict], lang: str) -> list[dict]:
    l = normalize_lang(lang)
    d_type = str(draft.get("type") or "").strip().lower()
    sprints = int(draft.get("sprints") or 0)
    owners = [str(x).strip() for x in (draft.get("responsibles") or []) if str(x).strip()]
    context = str(draft.get("context") or "").strip().lower()

    def txt(values: dict[str, str], fallback: str) -> str:
        return values.get(l, fallback)

    out: list[dict] = []

    if not d_type:
        out.append({
            "id": "sq-type",
            "question": txt({
                "pt": "Qual tipo de projeto melhor descreve seu objetivo atual?",
                "en": "What project type best describes your current objective?",
                "es": "¿Qué tipo de proyecto describe mejor su objetivo actual?",
                "it": "Quale tipo di progetto descrive meglio il tuo obiettivo attuale?",
                "de": "Welcher Projekttyp beschreibt Ihr aktuelles Ziel am besten?",
                "fr": "Quel type de projet décrit le mieux votre objectif actuel ?",
            }, "Qual tipo de projeto melhor descreve seu objetivo atual?"),
            "options": [
                {"label": "Software", "value": "Tipo do projeto: Software"},
                {"label": "Engenharia", "value": "Tipo do projeto: Engenharia"},
                {"label": "Naval", "value": "Tipo do projeto: Naval"},
                {"label": "Nuclear", "value": "Tipo do projeto: Nuclear"},
            ],
        })

    if sprints <= 0:
        opts = [3, 4, 6] if d_type in {"software", "web", "mobile"} else [6, 8, 10]
        out.append({
            "id": "sq-sprints",
            "question": txt({
                "pt": "Qual horizonte de sprints você prefere para esta entrega?",
                "en": "What sprint horizon do you prefer for this delivery?",
                "es": "¿Qué horizonte de sprints prefiere para esta entrega?",
                "it": "Quale orizzonte di sprint preferisci per questa consegna?",
                "de": "Welchen Sprint-Horizont bevorzugen Sie für diese Lieferung?",
                "fr": "Quel horizon de sprints préférez-vous pour cette livraison ?",
            }, "Qual horizonte de sprints você prefere para esta entrega?"),
            "options": [{"label": f"{n} sprints", "value": f"Planejar com {n} sprints"} for n in opts],
        })

    if not owners:
        out.append({
            "id": "sq-owners",
            "question": txt({
                "pt": "Como deseja estruturar os responsáveis principais?",
                "en": "How do you want to structure key owners?",
                "es": "¿Cómo desea estructurar los responsables principales?",
                "it": "Come vuoi strutturare i responsabili principali?",
                "de": "Wie möchten Sie die Hauptverantwortlichen strukturieren?",
                "fr": "Comment souhaitez-vous structurer les responsables principaux ?",
            }, "Como deseja estruturar os responsáveis principais?"),
            "options": [
                {"label": "Backend + Frontend + QA", "value": "Responsáveis dedicados para Backend, Frontend e QA"},
                {"label": "Equipe enxuta", "value": "Equipe enxuta com PM técnico e time full-stack"},
                {"label": "Equipe expandida", "value": "Equipe expandida com Arquitetura, QA e Compliance"},
            ],
        })

    if any(k in (d_type + " " + context) for k in ["nuclear", "naval", "conform", "compliance", "regulat"]):
        out.append({
            "id": "sq-gov",
            "question": txt({
                "pt": "Qual trilha de governança/conformidade devemos priorizar?",
                "en": "Which governance/compliance track should we prioritize?",
                "es": "¿Qué línea de gobernanza/conformidad debemos priorizar?",
                "it": "Quale percorso di governance/compliance dobbiamo prioritizzare?",
                "de": "Welche Governance-/Compliance-Linie sollen wir priorisieren?",
                "fr": "Quelle piste de gouvernance/conformité devons-nous prioriser ?",
            }, "Qual trilha de governança/conformidade devemos priorizar?"),
            "options": [
                {"label": "Gate de segurança", "value": "Priorizar gate de segurança em cada sprint"},
                {"label": "Validação documental", "value": "Incluir validação documental antes de cada milestone"},
                {"label": "Conformidade contínua", "value": "Aplicar checklist contínuo de conformidade"},
            ],
        })

    if plan_tasks:
        out.append({
            "id": "sq-focus",
            "question": txt({
                "pt": "Qual foco deve orientar o próximo refinamento do plano?",
                "en": "What focus should guide the next plan refinement?",
                "es": "¿Qué foco debe guiar el próximo refinamiento del plan?",
                "it": "Quale focus deve guidare il prossimo affinamento del piano?",
                "de": "Welcher Fokus sollte die nächste Planverfeinerung leiten?",
                "fr": "Quel focus doit guider le prochain raffinement du plan ?",
            }, "Qual foco deve orientar o próximo refinamento do plano?"),
            "options": [
                {"label": "Reduzir risco crítico", "value": "Refinar plano para reduzir risco crítico"},
                {"label": "Acelerar entrega", "value": "Refinar plano para acelerar entrega"},
                {"label": "Balancear carga", "value": "Refinar plano para balancear carga entre responsáveis"},
            ],
        })

    return out[:6]


def _project_ai_safe_smart_questions(raw_questions, draft: dict, plan_tasks: list[dict], lang: str) -> list[dict]:
    rows = raw_questions if isinstance(raw_questions, list) else []
    safe: list[dict] = []
    for i, row in enumerate(rows[:10]):
        if not isinstance(row, dict):
            continue
        q = str(row.get("question") or "").strip()[:240]
        if not q:
            continue
        opts_raw = row.get("options") if isinstance(row.get("options"), list) else []
        options: list[dict] = []
        for op in opts_raw[:8]:
            if isinstance(op, dict):
                label = str(op.get("label") or op.get("value") or "").strip()[:120]
                value = str(op.get("value") or op.get("label") or "").strip()[:240]
            else:
                label = str(op or "").strip()[:120]
                value = label
            if label:
                options.append({"label": label, "value": value or label})
        if not options:
            continue
        safe.append({
            "id": str(row.get("id") or f"sq-{i+1}").strip()[:40] or f"sq-{i+1}",
            "question": q,
            "rationale": str(row.get("rationale") or "").strip()[:300],
            "options": options,
        })

    if safe:
        return safe[:6]
    return _project_ai_default_smart_questions(draft, plan_tasks, lang)


@bp.route("/api/ai/project-chat", methods=["POST"])
@login_required
def ai_project_chat():
    _require_tenant()
    if not _has_project_access(g.tenant):
        return jsonify({"ok": False, "error": _("Accès refusé au module Projet.")}), 403

    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict) or not payload:
        payload = {}
        if request.form:
            payload["message"] = request.form.get("message")
            payload["lang"] = request.form.get("lang")
            try:
                payload["draft"] = json.loads(request.form.get("draft") or "{}")
            except Exception:
                payload["draft"] = {}
            try:
                payload["history"] = json.loads(request.form.get("history") or "[]")
            except Exception:
                payload["history"] = []

    message = str(payload.get("message") or "").strip()
    draft_raw = payload.get("draft") if isinstance(payload.get("draft"), dict) else {}
    history = payload.get("history") if isinstance(payload.get("history"), list) else []
    spec_pdf = request.files.get("spec_pdf") if request.files else None
    spec_text = _project_ai_extract_pdf_text(spec_pdf)
    if not message:
        return jsonify({"ok": False, "error": _("Message vide.")}), 400

    lang = normalize_lang(str(payload.get("lang") or getattr(g, "lang", DEFAULT_LANG)))
    base_draft = _project_ai_merge_draft(draft_raw, {})

    prompt = (
        "You are a PM assistant building a project setup from chat. "
        "Extract and update draft fields from the user request. "
        "Return concise reply + structured draft. "
        "When project type is engineering/naval/nuclear/industrial, avoid UX/UI or app-centric tasks and prefer engineering design, interfaces, procurement, compliance and verification tasks. "
        "Name each sprint according to its dominant tasks and project domain; avoid generic labels like Sprint 1/Sprint 2. "
        "Also return a creative project charter in key 'charter' with string fields: "
        "objectives, scope, deliverables, milestones. Deliverables and milestones names must match the project domain/type. "
        "Also return 'smart_questions' as an array of dynamic follow-up questions with selectable options, "
        "based on current conversation context and extracted project data."
    )
    data_bundle = {
        "source": "project-ai-builder",
        "question": prompt,
        "result": {
            "draft": base_draft,
            "spec_excerpt": spec_text,
            "has_spec_pdf": bool(spec_text),
        },
    }
    ai = analyze_with_ai(
        data_bundle=data_bundle,
        user_message=message,
        history=history[-8:],
        lang=lang,
        extra_json_keys=["draft", "ready_to_create", "missing", "plan_tasks", "planning_note", "charter", "smart_questions"],
    )

    draft = _project_ai_merge_draft(base_draft, ai.get("draft") if isinstance(ai.get("draft"), dict) else {})
    if not draft.get("name"):
        n = _project_ai_extract_name(message)
        if n:
            draft["name"] = n
    if not draft.get("type"):
        t = _project_ai_extract_type(message)
        if t:
            draft["type"] = t
    if not draft.get("sprints"):
        s = _project_ai_extract_sprints(message)
        if s:
            draft["sprints"] = s
    resp = _project_ai_extract_responsibles(message)
    if resp:
        draft = _project_ai_merge_draft(draft, {"responsibles": resp})
    work_hpd, avail_hpd = _project_ai_extract_hours(message)
    patch_hours = {}
    if work_hpd is not None:
        patch_hours["work_hours_per_day"] = work_hpd
    if avail_hpd is not None:
        patch_hours["available_hours_per_day"] = avail_hpd
    if patch_hours:
        draft = _project_ai_merge_draft(draft, patch_hours)
    draft["lang"] = lang

    missing = []
    if not draft.get("name"):
        missing.append(tr("nom du projet", lang))
    if not draft.get("type"):
        missing.append(tr("type de projet", lang))
    if not int(draft.get("sprints") or 0):
        missing.append(tr("nombre de sprints", lang))
    if not (draft.get("responsibles") or []):
        missing.append(tr("responsables", lang))

    ready_from_ai = bool(ai.get("ready_to_create"))
    ready = ready_from_ai or (len(missing) == 0)
    reply = str(ai.get("analysis") or "").strip()
    if not reply:
        if ready:
            owner_axis = tr("responsável por backend/frontend/QA", lang)
            if _project_family(str(draft.get("type") or "")) == "engineering":
                owner_axis = tr("responsável por engenharia/interfaces/conformidade", lang)
            reply = tr("Antes de criar, vamos refinar melhor as tarefas por sprint e responsável.", lang) + " " + tr("Confirme:", lang) + " 1) " + tr("principais entregáveis por sprint", lang) + ", 2) " + owner_axis + ", 3) " + tr("dependências críticas", lang) + ", 4) " + tr("riscos e restrições", lang) + "."
        else:
            reply = tr("Entendi. Para continuar, informe", lang) + ": " + ", ".join(missing) + "."

    plan_tasks = ai.get("plan_tasks") if isinstance(ai.get("plan_tasks"), list) else []
    def _safe_float(value, default=0.0):
        try:
            return float(value)
        except Exception:
            return float(default)

    def _safe_int(value, default=0):
        try:
            return int(value)
        except Exception:
            return int(default)

    safe_plan_tasks: list[dict] = []
    for row in plan_tasks[:80]:
        if not isinstance(row, dict):
            continue
        safe_plan_tasks.append({
            "ref": str(row.get("ref") or "").strip()[:40],
            "sprint": str(row.get("sprint") or "").strip()[:40],
            "task": str(row.get("task") or "").strip()[:140],
            "owner": str(row.get("owner") or "").strip()[:120],
            "duration_days": max(1, min(60, _safe_int(row.get("duration_days") or 1, 1))),
            "work_hours_per_day": max(1.0, min(12.0, _safe_float(row.get("work_hours_per_day") or draft.get("work_hours_per_day") or 8, 8.0))),
            "available_hours_per_day": max(1.0, min(12.0, _safe_float(row.get("available_hours_per_day") or draft.get("available_hours_per_day") or 8, 8.0))),
            "predecessor_ref": str(row.get("predecessor_ref") or "").strip()[:40] or None,
            "dependency_type": str(row.get("dependency_type") or "FS").strip().upper()[:2],
            "description": str(row.get("description") or "").strip()[:2000],
            "priority": str(row.get("priority") or "").strip().lower()[:10],
        })
    if not safe_plan_tasks:
        safe_plan_tasks = _project_ai_fallback_plan(draft)
    for item in safe_plan_tasks:
        if not str(item.get("description") or "").strip():
            item["description"] = _project_ai_task_description(
                str(item.get("task") or ""),
                str(item.get("sprint") or ""),
                str(item.get("owner") or ""),
                str(draft.get("context") or ""),
                lang,
            )
        if item.get("priority") not in {"low", "medium", "high"}:
            item["priority"] = _project_ai_task_priority(str(item.get("task") or ""))

    if _project_family(str(draft.get("type") or "")) == "engineering":
        for item in safe_plan_tasks:
            task_name = str(item.get("task") or "")
            lowered = task_name.lower()
            if any(k in lowered for k in ["ux", "ui"]):
                item["task"] = re.sub(r"(?i)ux/?ui.*$", "Engineering concept design", task_name).strip(" -")
                if not item["task"]:
                    item["task"] = "Engineering concept design"
            elif "frontend" in lowered:
                item["task"] = re.sub(r"(?i)frontend.*$", "Procurement and fabrication package", task_name).strip(" -")
                if not item["task"]:
                    item["task"] = "Procurement and fabrication package"
            elif "backend" in lowered:
                item["task"] = re.sub(r"(?i)backend.*$", "Detailed engineering and interfaces", task_name).strip(" -")
                if not item["task"]:
                    item["task"] = "Detailed engineering and interfaces"

    family = _project_family(str(draft.get("type") or ""))
    if family == "engineering":
        for item in safe_plan_tasks:
            item["sprint"] = _project_ai_sanitize_sprint_name_for_family(str(item.get("sprint") or ""), family)

    safe_plan_tasks = _project_ai_enrich_sprint_names_with_ai(draft, safe_plan_tasks, history, lang)

    if family == "engineering":
        for item in safe_plan_tasks:
            item["sprint"] = _project_ai_sanitize_sprint_name_for_family(str(item.get("sprint") or ""), family)

    planning_note = str(ai.get("planning_note") or "").strip()
    if not planning_note:
        planning_note = tr("As tarefas e durações foram sugeridas por IA com base em padrões de outros projetos e podem ser ajustadas manualmente.", lang)
    charter = _project_ai_safe_charter(ai.get("charter") if isinstance(ai, dict) else None)
    fallback_charter = _project_ai_fallback_charter(draft, safe_plan_tasks, lang)
    if not charter.get("objectives"):
        charter["objectives"] = fallback_charter["objectives"]
    if not charter.get("scope"):
        charter["scope"] = fallback_charter["scope"]
    if not charter.get("deliverables"):
        charter["deliverables"] = fallback_charter["deliverables"]
    if not charter.get("milestones"):
        charter["milestones"] = fallback_charter["milestones"]
    smart_questions = _project_ai_safe_smart_questions(
        ai.get("smart_questions") if isinstance(ai, dict) else None,
        draft,
        safe_plan_tasks,
        lang,
    )

    return jsonify({
        "ok": True,
        "reply": reply,
        "draft": draft,
        "missing": missing,
        "ready_to_create": ready,
        "plan_tasks": safe_plan_tasks,
        "planning_note": planning_note,
        "smart_questions": smart_questions,
        "charter": charter,
        "spec_used": bool(spec_text),
        "ai_error": ai.get("error") if isinstance(ai, dict) else None,
    })


@bp.route("/help/chat", methods=["POST"])
@login_required
def help_chat():
    _require_tenant()
    if not _has_project_access(g.tenant):
        return jsonify({"ok": False, "error": _("Accès refusé au module Projet.")}), 403

    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip()
    if not message:
        return jsonify({"ok": False, "error": _("Message vide.")}), 400

    text = message.lower()
    project_url = url_for("project.dashboard")

    if any(k in text for k in ["gantt", "planning", "plan", "cronograma", "cronogramme"]):
        reply = _(
            "Dans le Gantt, vous définissez les dates, les durées et les prédécesseurs. Les tâches critiques sont mises en évidence pour piloter le planning."
        )
    elif any(k in text for k in ["kanban", "card", "tâche", "tarefa", "task"]):
        reply = _(
            "Dans le Kanban, déplacez les cartes entre À faire, En cours et Terminé pour refléter l’avancement opérationnel du projet."
        )
    elif any(k in text for k in ["responsable", "responsável", "manager", "owner", "equipe", "équipe"]):
        reply = _(
            "Enregistrez les responsables avec taux horaire et heures par jour. Le coût des tâches est calculé automatiquement à partir de ces données."
        )
    elif any(k in text for k in ["spi", "cpi", "ev", "pv", "ac", "budget", "orçamento", "budget"]):
        reply = _(
            "Reporting EVM : PV est la valeur planifiée, EV la valeur acquise et AC le coût réel. SPI et CPI mesurent la performance délai et coût."
        )
    elif any(k in text for k in ["change", "changement", "approval", "aprovação", "approbation"]):
        reply = _(
            "Les changements suivent le workflow brouillon/revue/approuvé/rejeté. Les profils habilités peuvent valider ou rejeter les demandes."
        )
    elif any(k in text for k in ["risk", "risque", "issue", "incident", "decision", "décision"]):
        reply = _(
            "Vous pouvez enregistrer risques, incidents et décisions dans le bloc PMO pour assurer gouvernance, traçabilité et plan d’action."
        )
    else:
        reply = _(
            "Je peux vous aider sur Kanban, Gantt, responsables, budget, risques/incidents, changements et reporting SPI/CPI."
        )

    reply = f"{reply} {_('Ouvrez aussi le tableau projet')}: {project_url}"
    suggestions = [
        _("Comment ajouter une tâche Gantt ?"),
        _("Comment fonctionne SPI/CPI ?"),
        _("Comment approuver un changement ?"),
        _("Comment gérer les responsables ?"),
    ]
    return jsonify({"ok": True, "reply": reply, "suggestions": suggestions})

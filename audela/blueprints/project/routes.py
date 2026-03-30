from __future__ import annotations

from datetime import datetime
import re
from uuid import uuid4

from flask import abort, flash, g, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ...extensions import csrf, db
from ...i18n import DEFAULT_LANG, tr
from ...models.core import Tenant
from ...models.project_management import ProjectWorkspace
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

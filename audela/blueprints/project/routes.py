from __future__ import annotations

from datetime import datetime

from flask import abort, flash, g, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ...extensions import db
from ...i18n import DEFAULT_LANG, tr
from ...models.core import Tenant
from ...models.project_management import ProjectWorkspace
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

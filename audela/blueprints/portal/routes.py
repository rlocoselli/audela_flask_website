from __future__ import annotations

from datetime import datetime
import hashlib
import secrets
import re

import json
import copy

from flask import abort, flash, g, jsonify, make_response, redirect, render_template, request, url_for, send_file, session
from flask_login import current_user, login_required
from sqlalchemy.orm.attributes import flag_modified

from ...extensions import db, csrf
from ...models.bi import (
    AuditEvent,
    Dashboard,
    DashboardCard,
    DataSource,
    Question,
    QueryRun,
    Report,
    FileFolder,
    FileAsset,
)
from ...models.core import Tenant
from ...models.core import User, Role
from ...models.project_management import ProjectWorkspace
from ...security import require_roles
from ...services.query_service import QueryExecutionError, execute_sql
from ...services.datasource_service import decrypt_config, introspect_source
from ...services.nlq_service import generate_sql_from_nl
from ...services.pdf_export import table_to_pdf_bytes
from ...services.xlsx_export import table_to_xlsx_bytes
from ...services.ai_service import analyze_with_ai
from ...services.statistics_service import run_statistics_analysis, stats_report_to_pdf_bytes
from ...services.report_render_service import report_to_pdf_bytes
from ...services.file_storage_service import (
    delete_folder_tree,
    delete_stored_file,
    resolve_abs_path,
    store_upload,
    store_stream,
)
from ...services.file_introspect_service import introspect_file_schema
from ...services.subscription_service import SubscriptionService
from ...tenancy import get_current_tenant_id, get_user_module_access

from ...i18n import tr, DEFAULT_LANG


def _(msgid: str, **kwargs):
    """Translation helper for server-side flash/messages."""
    return tr(msgid, getattr(g, "lang", DEFAULT_LANG), **kwargs)

from ...i18n import tr
from . import bp


@bp.before_app_request
def load_tenant_into_g() -> None:
    """Load current tenant from session.

    MVP: tenant is stored in session during login.
    """
    tenant_id = get_current_tenant_id()
    g.tenant = None
    if tenant_id:
        tenant = Tenant.query.get(tenant_id)
        if tenant:
            g.tenant = tenant

    if (
        request.endpoint
        and request.endpoint.startswith("portal.")
        and current_user.is_authenticated
        and g.tenant
        and current_user.tenant_id == g.tenant.id
    ):
        if request.endpoint in {
            "portal.projects_hub",
            "portal.project_workspace_get",
            "portal.project_workspace_save",
        }:
            return None
        access = get_user_module_access(g.tenant, current_user.id)
        if not access.get("bi", True):
            flash(tr("Acesso BI desativado para seu usuário.", getattr(g, "lang", None)), "warning")
            return redirect(url_for("tenant.dashboard"))


def _require_tenant() -> None:
    if not current_user.is_authenticated:
        abort(401)
    if not g.tenant or current_user.tenant_id != g.tenant.id:
        abort(403)


@bp.app_context_processor
def _portal_layout_context():
    tenant = getattr(g, "tenant", None)
    module_access = get_user_module_access(tenant, getattr(current_user, "id", None))
    if not tenant or not getattr(tenant, "subscription", None):
        return {"transaction_usage": None, "module_access": module_access}

    _, current_count, max_limit = SubscriptionService.check_limit(tenant.id, "transactions")
    return {
        "module_access": module_access,
        "transaction_usage": {
            "current": int(current_count),
            "max": int(max_limit),
            "max_label": "∞" if int(max_limit) == -1 else str(int(max_limit)),
            "is_unlimited": int(max_limit) == -1,
        }
    }


def _bi_quota_check(required: int = 1) -> bool:
    tenant = getattr(g, "tenant", None)
    if not tenant or not getattr(tenant, "subscription", None):
        return True

    can_add, current_count, max_limit = SubscriptionService.check_limit(tenant.id, "transactions")
    if int(max_limit) == -1:
        return True

    remaining = max(0, int(max_limit) - int(current_count))
    if bool(can_add) and remaining >= int(required):
        return True

    flash(
        tr("Limite de transações do plano atingida ({current}/{max}).", getattr(g, "lang", None), current=current_count, max=max_limit),
        "error",
    )
    return False


def _bi_quota_consume(amount: int = 1) -> None:
    tenant = getattr(g, "tenant", None)
    if not tenant or not getattr(tenant, "subscription", None):
        return

    sub = tenant.subscription
    if not sub or not sub.is_active() or not sub.plan:
        return

    if int(sub.plan.max_transactions_per_month) == -1:
        return

    current = int(sub.transactions_this_month or 0)
    sub.transactions_this_month = max(0, current + int(amount))


def _audit(event_type: str, payload: dict | None = None) -> None:
    if not g.tenant:
        return
    evt = AuditEvent(
        tenant_id=g.tenant.id,
        user_id=getattr(current_user, "id", None),
        event_type=event_type,
        payload_json=payload or {},
    )
    db.session.add(evt)


def _integration_state_for_tenant(tenant: Tenant) -> dict:
    settings = tenant.settings_json if isinstance(tenant.settings_json, dict) else {}
    integrations = settings.get("integrations") if isinstance(settings.get("integrations"), dict) else {}
    api_creator = integrations.get("api_creator") if isinstance(integrations.get("api_creator"), dict) else {}
    app_keys = api_creator.get("app_keys") if isinstance(api_creator.get("app_keys"), list) else []
    endpoints = api_creator.get("question_endpoints") if isinstance(api_creator.get("question_endpoints"), list) else []
    return {
        "settings": settings,
        "integrations": integrations,
        "api_creator": api_creator,
        "app_keys": app_keys,
        "question_endpoints": endpoints,
    }


def _persist_integration_state(tenant: Tenant, state: dict) -> None:
    settings = state.get("settings") or {}
    integrations = state.get("integrations") or {}
    api_creator = state.get("api_creator") or {}
    api_creator["app_keys"] = state.get("app_keys") or []
    api_creator["question_endpoints"] = state.get("question_endpoints") or []
    integrations["api_creator"] = api_creator
    settings["integrations"] = integrations
    tenant.settings_json = copy.deepcopy(settings)
    flag_modified(tenant, "settings_json")


def _hash_app_key(raw_key: str) -> str:
    return hashlib.sha256((raw_key or "").encode("utf-8")).hexdigest()


def _new_key_id() -> str:
    return secrets.token_hex(6)


def _new_endpoint_id() -> str:
    return secrets.token_hex(6)


def _safe_slug(name: str) -> str:
    out = re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower())
    return out.strip("-")[:80]


def _sanitize_project_workspace_state(payload: dict | None) -> dict:
    payload = payload or {}
    state = payload if isinstance(payload, dict) else {}

    def _list(name: str, max_items: int = 300):
        items = state.get(name)
        if not isinstance(items, list):
            return []
        return items[:max_items]

    return {
        "cards": _list("cards", 500),
        "ceremonies": _list("ceremonies", 200),
        "deliverables": _list("deliverables", 500),
        "gantt": _list("gantt", 500),
    }


def _resolve_tenant_by_app_key(raw_key: str) -> tuple[Tenant | None, dict | None]:
    parts = (raw_key or "").split(".")
    if len(parts) != 4 or parts[0] != "ak":
        return None, None
    tenant_part, key_id = parts[1], parts[2]
    if not tenant_part.isdigit() or not key_id:
        return None, None
    tenant = Tenant.query.get(int(tenant_part))
    if not tenant:
        return None, None
    state = _integration_state_for_tenant(tenant)
    hashed = _hash_app_key(raw_key)
    for key in state.get("app_keys", []):
        if str(key.get("id") or "") != key_id:
            continue
        if not bool(key.get("active", True)):
            return None, None
        if str(key.get("key_hash") or "") != hashed:
            return None, None
        return tenant, key
    return None, None


@bp.route("/")
@login_required
def home():
    _require_tenant()
    requested_mode = (request.args.get("app_mode") or "").strip().lower()
    if requested_mode in {"finance", "bi"}:
        session["app_mode"] = requested_mode
    # If the user entered via the dedicated AUDELA Finance login, keep them in Finance.
    if session.get("app_mode") == "finance":
        return redirect(url_for("finance.dashboard"))
    # Show main dashboard (if any) and recent dashboards on home
    main = None
    try:
        main = Dashboard.query.filter_by(tenant_id=g.tenant.id, is_primary=True).first()
    except Exception:
        # DB schema may be out of date (missing is_primary). Don't crash the home page.
        main = None
    dashes = Dashboard.query.filter_by(tenant_id=g.tenant.id).order_by(Dashboard.updated_at.desc()).all()
    return render_template("portal/home.html", tenant=g.tenant, dashboards=dashes, main_dashboard=main)


# -----------------------------
# Data Sources
# -----------------------------


@bp.route("/sources")
@login_required
@require_roles("tenant_admin", "creator")
def sources_list():
    _require_tenant()
    sources = (
        DataSource.query.filter_by(tenant_id=g.tenant.id)
        .order_by(DataSource.created_at.desc())
        .all()
    )
    return render_template("portal/sources_list.html", tenant=g.tenant, sources=sources)


@bp.route("/sources/new", methods=["GET", "POST"])
@login_required
@require_roles("tenant_admin", "creator")
def sources_new():
    _require_tenant()

    # NOTE: we intentionally store the URL with the password redacted (***).
    # The real password is stored in cfg['conn']['password'] and injected at runtime.
    from ...services.datasource_service import (
        build_url_from_conn,
        inject_password_into_url,
        redact_url_password,
    )

    def _build_url_from_parts(ds_type: str, parts: dict) -> str:
        """Build a SQLAlchemy URL from structured form fields (best-effort)."""
        ds_type = (ds_type or '').lower().strip()
        host = (parts.get('host') or '').strip()
        port = (parts.get('port') or '').strip()
        database = (parts.get('database') or '').strip()
        username = (parts.get('username') or '').strip()
        password = (parts.get('password') or '')
        driver = (parts.get('driver') or '').strip()
        service_name = (parts.get('service_name') or '').strip()
        sid = (parts.get('sid') or '').strip()
        sqlite_path = (parts.get('sqlite_path') or '').strip()

        from sqlalchemy.engine import URL

        if ds_type == 'audela_finance':
            return 'internal://audela_finance'
        if ds_type == 'audela_project':
            return 'internal://audela_project'

        if ds_type == 'postgres':
            return str(URL.create(
                'postgresql+psycopg2',
                username=username or None,
                password=password or None,
                host=host or None,
                port=int(port) if port else None,
                database=database or None,
            ))

        if ds_type == 'mysql':
            return str(URL.create(
                'mysql+pymysql',
                username=username or None,
                password=password or None,
                host=host or None,
                port=int(port) if port else None,
                database=database or None,
            ))

        if ds_type == 'sqlserver':
            query = {}
            if driver:
                query['driver'] = driver
            return str(URL.create(
                'mssql+pyodbc',
                username=username or None,
                password=password or None,
                host=host or None,
                port=int(port) if port else None,
                database=database or None,
                query=query or None,
            ))

        if ds_type == 'oracle':
            query = {}
            if service_name:
                query['service_name'] = service_name
            elif sid:
                query['sid'] = sid
            return str(URL.create(
                'oracle+oracledb',
                username=username or None,
                password=password or None,
                host=host or None,
                port=int(port) if port else None,
                database=None,
                query=query or None,
            ))

        if ds_type == 'sqlite':
            # accept either a fully formed sqlite URL or a path
            if sqlite_path.startswith('sqlite:'):
                return sqlite_path
            p = sqlite_path or database
            if not p:
                return ''
            if p.startswith('/'):
                return 'sqlite:////' + p.lstrip('/')
            return 'sqlite:///' + p

        # fallback: keep raw
        return ''

    form = {
        'name': (request.form.get('name') or '').strip(),
        'type': (request.form.get('type') or '').strip().lower(),
        'url': (request.form.get('url') or '').strip(),
        'default_schema': (request.form.get('default_schema') or '').strip(),
        'tenant_column': (request.form.get('tenant_column') or '').strip(),
        'host': (request.form.get('host') or '').strip(),
        'port': (request.form.get('port') or '').strip(),
        'database': (request.form.get('database') or '').strip(),
        'username': (request.form.get('username') or '').strip(),
        'password': (request.form.get('password') or ''),
        'driver': (request.form.get('driver') or '').strip(),
        'service_name': (request.form.get('service_name') or '').strip(),
        'sid': (request.form.get('sid') or '').strip(),
        'sqlite_path': (request.form.get('sqlite_path') or '').strip(),
        'use_builder': (request.form.get('use_builder') or '').strip(),
        'policy_json': (request.form.get('policy_json') or '').strip(),
    }

    # Policy controls safety limits for queries on this datasource
    import json

    default_policy = {"timeout_seconds": 30, "max_rows": 5000, "read_only": True}

    def _to_bool(v, default=True):
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return bool(v)
        if isinstance(v, str):
            s = v.strip().lower()
            if s in ("true", "1", "yes", "y", "on"):
                return True
            if s in ("false", "0", "no", "n", "off"):
                return False
        return default

    def _to_int(v, default, *, min_v=1, max_v=50000):
        try:
            i = int(v)
        except Exception:
            return default
        if i < min_v:
            i = min_v
        if i > max_v:
            i = max_v
        return i

    def _sanitize_policy(p: dict) -> dict:
        out = dict(p or {})
        out["read_only"] = _to_bool(out.get("read_only"), bool(default_policy.get("read_only", True)))
        out["max_rows"] = _to_int(out.get("max_rows"), int(default_policy.get("max_rows", 5000)), min_v=1, max_v=50000)
        out["timeout_seconds"] = _to_int(out.get("timeout_seconds"), int(default_policy.get("timeout_seconds", 30)), min_v=1, max_v=300)
        return out

    if not form.get('policy_json'):
        form['policy_json'] = json.dumps(default_policy, indent=2, ensure_ascii=False)

    if request.method == 'POST':
        if not _bi_quota_check(1):
            return render_template('portal/sources_new.html', tenant=g.tenant, form=form)

        name = form['name']
        ds_type = form['type']
        default_schema = form['default_schema'] or None
        tenant_column = form['tenant_column'] or None

        url = form['url']
        if form['use_builder'] == '1' or not url:
            url = _build_url_from_parts(ds_type, form)

        if not name or not ds_type or not url:
            flash(tr('Preencha nome, tipo e conexão.', getattr(g, 'lang', None)), 'error')
            return render_template('portal/sources_new.html', tenant=g.tenant, form=form)

        # Parse and validate policy JSON
        policy_raw = (request.form.get('policy_json') or '').strip()
        try:
            if policy_raw:
                policy_obj = json.loads(policy_raw)
                if not isinstance(policy_obj, dict):
                    raise ValueError('policy_json deve ser um objeto JSON')
            else:
                policy_obj = default_policy
            policy_obj = _sanitize_policy(policy_obj)
        except Exception as e:
            flash(tr('Política inválida: {error}', getattr(g, 'lang', None), error=str(e)), 'error')
            form['policy_json'] = policy_raw or form.get('policy_json','')
            return render_template('portal/sources_new.html', tenant=g.tenant, form=form)


        from ...services.crypto import encrypt_json

        conn = {
            'host': form['host'],
            'port': form['port'],
            'database': form['database'],
            'username': form['username'],
            'password': form['password'],
            'driver': form['driver'],
            'service_name': form['service_name'],
            'sid': form['sid'],
            'sqlite_path': form['sqlite_path'],
        }

        # Ensure we have an effective URL that includes the real password for runtime use
        effective_url = inject_password_into_url(url, conn.get('password'))
        if (not effective_url) and conn:
            effective_url = build_url_from_conn(ds_type, conn)
        if not effective_url:
            flash(tr('Preencha nome, tipo e conexão.', getattr(g, 'lang', None)), 'error')
            return render_template('portal/sources_new.html', tenant=g.tenant, form=form)

        # Store URL redacted (no secrets in URL)
        stored_url = redact_url_password(effective_url)

        config = {
            'url': stored_url,
            'default_schema': default_schema,
            'tenant_column': tenant_column,
            'conn': conn,
        }

        ds = DataSource(
            tenant_id=g.tenant.id,
            type=ds_type,
            name=name,
            config_encrypted=encrypt_json(config),
            policy_json=policy_obj,
        )
        db.session.add(ds)
        _bi_quota_consume(1)
        _audit('bi.datasource.created', {'id': None, 'name': name, 'type': ds_type})
        db.session.commit()

        flash(tr('Fonte criada.', getattr(g, 'lang', None)), 'success')
        return redirect(url_for('portal.sources_list'))

    return render_template('portal/sources_new.html', tenant=g.tenant, form=form)


@bp.get("/sources/api")
def api_sources_list():
    """List API sources separately (for quick access)."""
    _require_tenant()
    sources = (
        db.session.query(DataSource)
        .filter(DataSource.tenant_id == g.tenant.id)
        .filter(DataSource.type == "api")
        .order_by(DataSource.created_at.desc())
        .all()
    )
    return render_template("portal/api_sources_list.html", tenant=g.tenant, sources=sources)


@bp.route("/sources/api/new", methods=["GET", "POST"])
@login_required
@require_roles("tenant_admin")
def api_sources_new():
    """Create a new API source.

    We store the API base URL in the encrypted config.
    Headers can be provided as JSON (optional).
    """
    _require_tenant()
    form = {
        "name": "",
        "base_url": "",
        "headers_json": "",
        "enable_auth_flow": False,
        "auth_url": "",
        "auth_method": "POST",
        "auth_headers_json": "",
        "auth_body_json": "",
        "token_json_path": "access_token",
        "token_header_name": "Authorization",
        "token_prefix": "Bearer",
    }

    if request.method == "POST":
        if not _bi_quota_check(1):
            return render_template("portal/api_sources_new.html", tenant=g.tenant, form=form)

        import json

        form = {
            "name": request.form.get("name", "").strip(),
            "base_url": request.form.get("base_url", "").strip(),
            "headers_json": (request.form.get("headers_json", "") or "").strip(),
            "enable_auth_flow": str(request.form.get("enable_auth_flow") or "").strip().lower() in ("1", "true", "on", "yes"),
            "auth_url": request.form.get("auth_url", "").strip(),
            "auth_method": (request.form.get("auth_method", "POST") or "POST").strip().upper(),
            "auth_headers_json": (request.form.get("auth_headers_json", "") or "").strip(),
            "auth_body_json": (request.form.get("auth_body_json", "") or "").strip(),
            "token_json_path": request.form.get("token_json_path", "access_token").strip(),
            "token_header_name": request.form.get("token_header_name", "Authorization").strip(),
            "token_prefix": request.form.get("token_prefix", "Bearer").strip(),
        }
        name = form["name"]
        base_url = form["base_url"]
        headers_raw = form["headers_json"]

        if not name or not base_url:
            flash(tr("Preencha nome e URL base.", getattr(g, "lang", None)), "error")
            return render_template("portal/api_sources_new.html", tenant=g.tenant, form=form)

        headers = None
        if headers_raw:
            try:
                headers = json.loads(headers_raw)
                if not isinstance(headers, dict):
                    raise ValueError("headers_json must be a JSON object")
            except Exception as e:
                flash(tr("JSON inválido em cabeçalhos: {error}", getattr(g, "lang", None), error=str(e)), "error")
                return render_template("portal/api_sources_new.html", tenant=g.tenant, form=form)

        auth_flow: dict = {"enabled": False}
        if form["enable_auth_flow"]:
            auth_method = form["auth_method"] if form["auth_method"] in ("GET", "POST", "PUT", "PATCH") else "POST"
            if not form["auth_url"]:
                flash(tr("Informe a URL de autenticação para o fluxo de token.", getattr(g, "lang", None)), "error")
                return render_template("portal/api_sources_new.html", tenant=g.tenant, form=form)

            auth_headers = {}
            if form["auth_headers_json"]:
                try:
                    auth_headers = json.loads(form["auth_headers_json"])
                    if not isinstance(auth_headers, dict):
                        raise ValueError("auth_headers_json must be a JSON object")
                except Exception as e:
                    flash(tr("JSON inválido em cabeçalhos de auth: {error}", getattr(g, "lang", None), error=str(e)), "error")
                    return render_template("portal/api_sources_new.html", tenant=g.tenant, form=form)

            auth_body = {}
            if form["auth_body_json"]:
                try:
                    auth_body = json.loads(form["auth_body_json"])
                    if not isinstance(auth_body, dict):
                        raise ValueError("auth_body_json must be a JSON object")
                except Exception as e:
                    flash(tr("JSON inválido em body de auth: {error}", getattr(g, "lang", None), error=str(e)), "error")
                    return render_template("portal/api_sources_new.html", tenant=g.tenant, form=form)

            auth_flow = {
                "enabled": True,
                "url": form["auth_url"],
                "method": auth_method,
                "headers": auth_headers,
                "body": auth_body,
                "token_json_path": form["token_json_path"] or "access_token",
                "token_header_name": form["token_header_name"] or "Authorization",
                "token_prefix": form["token_prefix"] or "Bearer",
            }

        from ...services.crypto import encrypt_json

        config = {
            "base_url": base_url,
            "headers": headers or {},
            "auth_flow": auth_flow,
        }

        ds = DataSource(
            tenant_id=g.tenant.id,
            type="api",
            name=name,
            base_url=base_url,
            config_encrypted=encrypt_json(config),
            policy_json={
                "timeout_seconds": 30,
                "max_rows": 5000,
                "read_only": True,
            },
        )
        db.session.add(ds)
        _bi_quota_consume(1)
        _audit("bi.datasource.created", {"id": None, "name": name, "type": "api"})
        db.session.commit()

        flash(tr("Fonte API criada.", getattr(g, "lang", None)), "success")
        return redirect(url_for("portal.api_sources_list"))

    return render_template("portal/api_sources_new.html", tenant=g.tenant, form=form)


@bp.get("/sources/api/<int:source_id>/preview")
@login_required
@require_roles("tenant_admin", "creator")
def api_sources_preview(source_id: int):
    _require_tenant()
    src = DataSource.query.filter_by(id=source_id, tenant_id=g.tenant.id, type="api").first_or_404()
    cfg = decrypt_config(src) or {}
    return render_template("portal/api_sources_preview.html", tenant=g.tenant, source=src, config=cfg)


@bp.post("/api/sources/api/<int:source_id>/preview_call")
@login_required
@require_roles("tenant_admin", "creator")
def api_sources_preview_call(source_id: int):
    _require_tenant()
    src = DataSource.query.filter_by(id=source_id, tenant_id=g.tenant.id, type="api").first_or_404()
    cfg = decrypt_config(src) or {}
    payload = request.get_json(silent=True) or {}

    import json
    import time
    import requests

    def _parse_obj(v, name: str):
        if v in (None, ""):
            return {}
        if isinstance(v, dict):
            return v
        if isinstance(v, str):
            vv = v.strip()
            if not vv:
                return {}
            try:
                obj = json.loads(vv)
                if not isinstance(obj, dict):
                    raise ValueError("not object")
                return obj
            except Exception:
                raise ValueError(f"{name} inválido (JSON esperado)")
        raise ValueError(f"{name} inválido")

    def _extract_path(data, path: str):
        cur = data
        for part in [p for p in str(path or "").split(".") if p]:
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return None
        return cur

    try:
        method = str(payload.get("method") or "GET").strip().upper()
        if method not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
            return jsonify({"ok": False, "error": tr("Método HTTP inválido.", getattr(g, "lang", None))}), 400

        url = str(payload.get("url") or cfg.get("base_url") or src.base_url or "").strip()
        if not url:
            return jsonify({"ok": False, "error": tr("URL é obrigatória.", getattr(g, "lang", None))}), 400

        base_headers = cfg.get("headers") if isinstance(cfg.get("headers"), dict) else {}
        req_headers = {}
        req_headers.update(base_headers)
        req_headers.update(_parse_obj(payload.get("headers"), "headers"))
        req_params = _parse_obj(payload.get("params"), "params")
        req_body = _parse_obj(payload.get("body"), "body")
        timeout_s = int(payload.get("timeout") or 30)
        timeout_s = max(3, min(timeout_s, 120))

        use_auth_flow = bool(payload.get("use_auth_flow"))
        auth_debug = None
        if use_auth_flow:
            auth_cfg_in = payload.get("auth_flow") if isinstance(payload.get("auth_flow"), dict) else {}
            auth_cfg_base = cfg.get("auth_flow") if isinstance(cfg.get("auth_flow"), dict) else {}
            auth_cfg = {**auth_cfg_base, **auth_cfg_in}
            auth_url = str(auth_cfg.get("url") or "").strip()
            auth_method = str(auth_cfg.get("method") or "POST").strip().upper()
            auth_headers = _parse_obj(auth_cfg.get("headers"), "auth headers")
            auth_body = _parse_obj(auth_cfg.get("body"), "auth body")
            token_path = str(auth_cfg.get("token_json_path") or "access_token").strip()
            token_header = str(auth_cfg.get("token_header_name") or "Authorization").strip() or "Authorization"
            token_prefix = str(auth_cfg.get("token_prefix") or "Bearer").strip() or "Bearer"

            if not auth_url:
                return jsonify({"ok": False, "error": tr("Fluxo de auth ativo sem URL de autenticação.", getattr(g, "lang", None))}), 400
            if auth_method not in ("GET", "POST", "PUT", "PATCH"):
                auth_method = "POST"

            auth_started = time.perf_counter()
            auth_resp = requests.request(
                method=auth_method,
                url=auth_url,
                headers=auth_headers,
                params=(auth_body if auth_method == "GET" else None),
                json=(auth_body if auth_method != "GET" else None),
                timeout=timeout_s,
            )
            auth_elapsed = int((time.perf_counter() - auth_started) * 1000)
            auth_text = auth_resp.text or ""
            try:
                auth_json = auth_resp.json()
            except Exception:
                auth_json = None
            if auth_resp.status_code >= 400:
                return jsonify({
                    "ok": False,
                    "error": tr("Falha na autenticação prévia ({code}).", getattr(g, "lang", None), code=auth_resp.status_code),
                    "auth": {
                        "status_code": auth_resp.status_code,
                        "elapsed_ms": auth_elapsed,
                        "headers": dict(auth_resp.headers or {}),
                        "body": auth_json if auth_json is not None else auth_text[:20000],
                    },
                }), 400

            token_val = _extract_path(auth_json if isinstance(auth_json, dict) else {}, token_path)
            if token_val in (None, ""):
                return jsonify({
                    "ok": False,
                    "error": tr("Token não encontrado no JSON de autenticação.", getattr(g, "lang", None)),
                    "auth": {
                        "status_code": auth_resp.status_code,
                        "elapsed_ms": auth_elapsed,
                    },
                }), 400

            req_headers[token_header] = f"{token_prefix} {token_val}".strip()
            auth_debug = {
                "status_code": auth_resp.status_code,
                "elapsed_ms": auth_elapsed,
                "token_header": token_header,
                "token_prefix": token_prefix,
                "token_json_path": token_path,
            }

        started = time.perf_counter()
        resp = requests.request(
            method=method,
            url=url,
            headers=req_headers,
            params=req_params,
            json=(req_body if method in ("POST", "PUT", "PATCH") else None),
            timeout=timeout_s,
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        txt = resp.text or ""
        try:
            body = resp.json()
        except Exception:
            body = txt[:20000]

        return jsonify({
            "ok": True,
            "request": {
                "method": method,
                "url": url,
                "headers": req_headers,
                "params": req_params,
                "body": req_body,
                "timeout": timeout_s,
            },
            "auth": auth_debug,
            "response": {
                "status_code": resp.status_code,
                "elapsed_ms": elapsed_ms,
                "headers": dict(resp.headers or {}),
                "body": body,
            },
        })
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except requests.RequestException as e:
        return jsonify({"ok": False, "error": tr("Erro de rede/API: {error}", getattr(g, "lang", None), error=str(e))}), 502
    except Exception as e:
        return jsonify({"ok": False, "error": tr("Erro ao executar preview: {error}", getattr(g, "lang", None), error=str(e))}), 500


@bp.route("/integrations")
@login_required
@require_roles("tenant_admin", "creator")
def integrations_hub():
    _require_tenant()
    state = _integration_state_for_tenant(g.tenant)
    questions = Question.query.filter_by(tenant_id=g.tenant.id).order_by(Question.name.asc()).all()
    q_by_id = {q.id: q for q in questions}

    endpoints = []
    for e in state.get("question_endpoints", []):
        qid = int(e.get("question_id") or 0)
        q = q_by_id.get(qid)
        endpoints.append(
            {
                **e,
                "question_name": q.name if q else tr("Pergunta removida", getattr(g, "lang", None)),
            }
        )

    return render_template(
        "portal/integrations_hub.html",
        tenant=g.tenant,
        questions=questions,
        app_keys=state.get("app_keys", []),
        endpoints=endpoints,
    )


@bp.post("/integrations/app-keys/create")
@login_required
@require_roles("tenant_admin")
def integrations_app_key_create():
    _require_tenant()
    label = (request.form.get("label") or "").strip() or "Default"
    state = _integration_state_for_tenant(g.tenant)
    key_id = _new_key_id()
    secret = secrets.token_urlsafe(24)
    raw_key = f"ak.{g.tenant.id}.{key_id}.{secret}"
    now_iso = datetime.utcnow().isoformat()
    state["app_keys"].append(
        {
            "id": key_id,
            "label": label[:80],
            "key_hash": _hash_app_key(raw_key),
            "active": True,
            "created_at": now_iso,
            "last_used_at": None,
            "last_used_ip": None,
        }
    )
    _persist_integration_state(g.tenant, state)
    _audit("bi.integration.app_key.created", {"key_id": key_id, "label": label[:80]})
    db.session.commit()
    flash(tr("Application key criada. Copie agora: {key}", getattr(g, "lang", None), key=raw_key), "success")
    return redirect(url_for("portal.integrations_hub"))


@bp.post("/integrations/app-keys/<string:key_id>/toggle")
@login_required
@require_roles("tenant_admin")
def integrations_app_key_toggle(key_id: str):
    _require_tenant()
    state = _integration_state_for_tenant(g.tenant)
    found = None
    for k in state.get("app_keys", []):
        if str(k.get("id") or "") == key_id:
            found = k
            break
    if not found:
        flash(tr("Chave não encontrada.", getattr(g, "lang", None)), "error")
        return redirect(url_for("portal.integrations_hub"))

    found["active"] = not bool(found.get("active", True))
    _persist_integration_state(g.tenant, state)
    _audit("bi.integration.app_key.toggled", {"key_id": key_id, "active": bool(found.get("active"))})
    db.session.commit()
    flash(tr("Status da chave atualizado.", getattr(g, "lang", None)), "success")
    return redirect(url_for("portal.integrations_hub"))


@bp.post("/integrations/app-keys/<string:key_id>/delete")
@login_required
@require_roles("tenant_admin")
def integrations_app_key_delete(key_id: str):
    _require_tenant()
    state = _integration_state_for_tenant(g.tenant)
    before = len(state.get("app_keys", []))
    state["app_keys"] = [k for k in state.get("app_keys", []) if str(k.get("id") or "") != key_id]
    if len(state["app_keys"]) == before:
        flash(tr("Chave não encontrada.", getattr(g, "lang", None)), "error")
        return redirect(url_for("portal.integrations_hub"))
    _persist_integration_state(g.tenant, state)
    _audit("bi.integration.app_key.deleted", {"key_id": key_id})
    db.session.commit()
    flash(tr("Chave removida.", getattr(g, "lang", None)), "success")
    return redirect(url_for("portal.integrations_hub"))


@bp.post("/integrations/endpoints/create")
@login_required
@require_roles("tenant_admin", "creator")
def integrations_endpoint_create():
    _require_tenant()
    try:
        question_id = int(request.form.get("question_id") or 0)
    except Exception:
        question_id = 0
    title = (request.form.get("title") or "").strip()
    slug_in = (request.form.get("slug") or "").strip()
    method = (request.form.get("method") or "POST").strip().upper()
    row_limit_raw = request.form.get("row_limit") or "1000"

    q = Question.query.filter_by(id=question_id, tenant_id=g.tenant.id).first()
    if not q:
        flash(tr("Pergunta inválida.", getattr(g, "lang", None)), "error")
        return redirect(url_for("portal.integrations_hub"))

    if method not in ("GET", "POST", "ANY"):
        method = "POST"

    try:
        row_limit = max(1, min(int(row_limit_raw), 10000))
    except Exception:
        row_limit = 1000

    slug = _safe_slug(slug_in or title or q.name)
    if not slug:
        flash(tr("Slug inválido.", getattr(g, "lang", None)), "error")
        return redirect(url_for("portal.integrations_hub"))

    state = _integration_state_for_tenant(g.tenant)
    if any(str(e.get("slug") or "") == slug for e in state.get("question_endpoints", [])):
        flash(tr("Slug já existe. Escolha outro.", getattr(g, "lang", None)), "error")
        return redirect(url_for("portal.integrations_hub"))

    endpoint_id = _new_endpoint_id()
    state["question_endpoints"].append(
        {
            "id": endpoint_id,
            "title": (title or q.name)[:120],
            "slug": slug,
            "question_id": q.id,
            "method": method,
            "row_limit": row_limit,
            "enabled": True,
            "created_at": datetime.utcnow().isoformat(),
        }
    )
    _persist_integration_state(g.tenant, state)
    _audit("bi.integration.endpoint.created", {"endpoint_id": endpoint_id, "slug": slug, "question_id": q.id})
    db.session.commit()
    flash(tr("Endpoint de integração criado.", getattr(g, "lang", None)), "success")
    return redirect(url_for("portal.integrations_hub"))


@bp.post("/integrations/endpoints/<string:endpoint_id>/toggle")
@login_required
@require_roles("tenant_admin", "creator")
def integrations_endpoint_toggle(endpoint_id: str):
    _require_tenant()
    state = _integration_state_for_tenant(g.tenant)
    found = None
    for e in state.get("question_endpoints", []):
        if str(e.get("id") or "") == endpoint_id:
            found = e
            break
    if not found:
        flash(tr("Endpoint não encontrado.", getattr(g, "lang", None)), "error")
        return redirect(url_for("portal.integrations_hub"))
    found["enabled"] = not bool(found.get("enabled", True))
    _persist_integration_state(g.tenant, state)
    _audit("bi.integration.endpoint.toggled", {"endpoint_id": endpoint_id, "enabled": bool(found.get("enabled"))})
    db.session.commit()
    flash(tr("Status do endpoint atualizado.", getattr(g, "lang", None)), "success")
    return redirect(url_for("portal.integrations_hub"))


@bp.post("/integrations/endpoints/<string:endpoint_id>/delete")
@login_required
@require_roles("tenant_admin", "creator")
def integrations_endpoint_delete(endpoint_id: str):
    _require_tenant()
    state = _integration_state_for_tenant(g.tenant)
    before = len(state.get("question_endpoints", []))
    state["question_endpoints"] = [
        e for e in state.get("question_endpoints", []) if str(e.get("id") or "") != endpoint_id
    ]
    if len(state["question_endpoints"]) == before:
        flash(tr("Endpoint não encontrado.", getattr(g, "lang", None)), "error")
        return redirect(url_for("portal.integrations_hub"))

    _persist_integration_state(g.tenant, state)
    _audit("bi.integration.endpoint.deleted", {"endpoint_id": endpoint_id})
    db.session.commit()
    flash(tr("Endpoint removido.", getattr(g, "lang", None)), "success")
    return redirect(url_for("portal.integrations_hub"))


@bp.post("/integrations/endpoints/test")
@login_required
@require_roles("tenant_admin", "creator")
def integrations_endpoint_test():
    _require_tenant()
    payload = request.get_json(silent=True) or {}

    try:
        endpoint_id = str(payload.get("endpoint_id") or "").strip()
        if not endpoint_id:
            return jsonify({"ok": False, "error": tr("Endpoint inválido.", getattr(g, "lang", None))}), 400

        params_in = payload.get("params") if isinstance(payload.get("params"), dict) else {}
        state = _integration_state_for_tenant(g.tenant)
        endpoint = None
        for e in state.get("question_endpoints", []):
            if str(e.get("id") or "") == endpoint_id:
                endpoint = e
                break
        if not endpoint:
            return jsonify({"ok": False, "error": tr("Endpoint não encontrado.", getattr(g, "lang", None))}), 404
        if not bool(endpoint.get("enabled", True)):
            return jsonify({"ok": False, "error": tr("Endpoint inativo.", getattr(g, "lang", None))}), 400

        question_id = int(endpoint.get("question_id") or 0)
        q = Question.query.filter_by(id=question_id, tenant_id=g.tenant.id).first()
        if not q:
            return jsonify({"ok": False, "error": tr("Pergunta inválida.", getattr(g, "lang", None))}), 404

        src = DataSource.query.filter_by(id=q.source_id, tenant_id=g.tenant.id).first()
        if not src:
            return jsonify({"ok": False, "error": tr("Fonte inválida.", getattr(g, "lang", None))}), 404

        params = {}
        params.update(params_in)
        params["tenant_id"] = g.tenant.id
        row_limit = max(1, min(int(endpoint.get("row_limit") or 1000), 10000))

        res = execute_sql(src, q.sql_text or "", params=params, row_limit=row_limit)
        rows = res.get("rows") or []
        return jsonify(
            {
                "ok": True,
                "endpoint": {"id": endpoint_id, "slug": endpoint.get("slug"), "title": endpoint.get("title")},
                "result": {
                    "columns": res.get("columns") or [],
                    "rows": rows,
                    "row_count": len(rows),
                },
            }
        )
    except QueryExecutionError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": tr("Erro no teste: {error}", getattr(g, "lang", None), error=str(e))}), 500


@csrf.exempt
@bp.route("/api/integrations/q/<string:slug>", methods=["GET", "POST"])
def integrations_question_api(slug: str):
    raw_key = (request.headers.get("X-App-Key") or request.headers.get("X-API-Key") or "").strip()
    if not raw_key:
        return jsonify({"ok": False, "error": "missing app key"}), 401

    tenant, key_rec = _resolve_tenant_by_app_key(raw_key)
    if not tenant or not key_rec:
        return jsonify({"ok": False, "error": "invalid app key"}), 401

    state = _integration_state_for_tenant(tenant)
    endpoint = None
    for item in state.get("question_endpoints", []):
        if str(item.get("slug") or "") == slug:
            endpoint = item
            break
    if not endpoint or not bool(endpoint.get("enabled", True)):
        return jsonify({"ok": False, "error": "endpoint not found"}), 404

    allowed_method = str(endpoint.get("method") or "POST").upper()
    if allowed_method in ("GET", "POST") and request.method != allowed_method:
        return jsonify({"ok": False, "error": "method not allowed"}), 405

    try:
        question_id = int(endpoint.get("question_id") or 0)
    except Exception:
        question_id = 0
    q = Question.query.filter_by(id=question_id, tenant_id=tenant.id).first()
    if not q:
        return jsonify({"ok": False, "error": "question not found"}), 404
    src = DataSource.query.filter_by(id=q.source_id, tenant_id=tenant.id).first()
    if not src:
        return jsonify({"ok": False, "error": "source not found"}), 404

    params = {}
    payload = request.get_json(silent=True) if request.method == "POST" else None
    if isinstance(payload, dict):
        p = payload.get("params")
        if isinstance(p, dict):
            params.update(p)
        else:
            params.update({k: v for k, v in payload.items() if k != "params"})
    for k, v in request.args.items():
        params[k] = v
    params["tenant_id"] = tenant.id

    try:
        row_limit = max(1, min(int(endpoint.get("row_limit") or 1000), 10000))
    except Exception:
        row_limit = 1000

    try:
        res = execute_sql(src, q.sql_text or "", params=params, row_limit=row_limit)
    except QueryExecutionError as e:
        return jsonify({"ok": False, "error": str(e)}), 400

    key_rec["last_used_at"] = datetime.utcnow().isoformat()
    key_rec["last_used_ip"] = (request.headers.get("X-Forwarded-For") or request.remote_addr or "")[:120]
    _persist_integration_state(tenant, state)
    db.session.commit()

    rows = res.get("rows") or []
    return jsonify(
        {
            "ok": True,
            "tenant": {"id": tenant.id, "slug": tenant.slug},
            "endpoint": {"slug": slug, "title": endpoint.get("title"), "question_id": q.id},
            "result": {
                "columns": res.get("columns") or [],
                "rows": rows,
                "row_count": len(rows),
            },
        }
    )


@bp.route("/sources/<int:source_id>/delete", methods=["POST"])
@login_required
@require_roles("tenant_admin")
def sources_delete(source_id: int):
    _require_tenant()
    src = DataSource.query.filter_by(id=source_id, tenant_id=g.tenant.id).first_or_404()
    _audit("bi.datasource.deleted", {"id": src.id, "name": src.name})
    db.session.delete(src)
    db.session.commit()
    flash(tr("Fonte removida.", getattr(g, "lang", None)), "success")
    return redirect(url_for("portal.sources_list"))

@bp.route("/apisources/<int:source_id>/delete", methods=["POST"])
@login_required
@require_roles("tenant_admin")
def apisources_delete(source_id: int):
    _require_tenant()
    src = DataSource.query.filter_by(id=source_id, tenant_id=g.tenant.id).first_or_404()
    _audit("bi.datasource.deleted", {"id": src.id, "name": src.name})
    db.session.delete(src)
    db.session.commit()
    flash(tr("Fonte removida.", getattr(g, "lang", None)), "success")
    return redirect(url_for("portal.api_sources_list"))

@bp.route("/sources/<int:source_id>")
@login_required
@require_roles("tenant_admin", "creator")
def sources_view(source_id: int):
    _require_tenant()
    src = DataSource.query.filter_by(id=source_id, tenant_id=g.tenant.id).first_or_404()
    cfg = decrypt_config(src) or {}

    # Never render raw secrets in the UI
    cfg_disp = dict(cfg)
    try:
        from ...services.datasource_service import redact_url_password

        if isinstance(cfg_disp.get("url"), str):
            cfg_disp["url"] = redact_url_password(cfg_disp.get("url") or "")
    except Exception:
        pass

    c = cfg_disp.get("conn") if isinstance(cfg_disp.get("conn"), dict) else None
    if c is not None:
        c2 = dict(c)
        cfg_disp["conn"] = c2

    return render_template("portal/sources_view.html", tenant=g.tenant, source=src, config=cfg_disp)

@bp.route("/sources/<int:source_id>/edit", methods=["GET", "POST"])
@login_required
@require_roles("tenant_admin", "creator")
def sources_edit(source_id: int):
    _require_tenant()
    src = DataSource.query.filter_by(id=source_id, tenant_id=g.tenant.id).first_or_404()
    cfg_existing = decrypt_config(src) or {}

    # Store URL with password redacted (***). Password lives in cfg['conn']['password'].
    from ...services.datasource_service import (
        build_url_from_conn,
        inject_password_into_url,
        redact_url_password,
    )

    def _build_url_from_parts(ds_type: str, parts: dict) -> str:
        ds_type = (ds_type or '').lower().strip()
        host = (parts.get('host') or '').strip()
        port = (parts.get('port') or '').strip()
        database = (parts.get('database') or '').strip()
        username = (parts.get('username') or '').strip()
        password = (parts.get('password') or '')
        driver = (parts.get('driver') or '').strip()
        service_name = (parts.get('service_name') or '').strip()
        sid = (parts.get('sid') or '').strip()
        sqlite_path = (parts.get('sqlite_path') or '').strip()

        from sqlalchemy.engine import URL

        if ds_type == 'audela_finance':
            return 'internal://audela_finance'
        if ds_type == 'audela_project':
            return 'internal://audela_project'

        if ds_type == 'postgres':
            return str(URL.create(
                'postgresql+psycopg2',
                username=username or None,
                password=password or None,
                host=host or None,
                port=int(port) if port else None,
                database=database or None,
            ))

        if ds_type == 'mysql':
            return str(URL.create(
                'mysql+pymysql',
                username=username or None,
                password=password or None,
                host=host or None,
                port=int(port) if port else None,
                database=database or None,
            ))

        if ds_type == 'sqlserver':
            query = {}
            if driver:
                query['driver'] = driver
            return str(URL.create(
                'mssql+pyodbc',
                username=username or None,
                password=password or None,
                host=host or None,
                port=int(port) if port else None,
                database=database or None,
                query=query or None,
            ))

        if ds_type == 'oracle':
            query = {}
            if service_name:
                query['service_name'] = service_name
            elif sid:
                query['sid'] = sid
            return str(URL.create(
                'oracle+oracledb',
                username=username or None,
                password=password or None,
                host=host or None,
                port=int(port) if port else None,
                database=None,
                query=query or None,
            ))

        if ds_type == 'sqlite':
            if sqlite_path.startswith('sqlite:'):
                return sqlite_path
            p = sqlite_path or database
            if not p:
                return ''
            if p.startswith('/'):
                return 'sqlite:////' + p.lstrip('/')
            return 'sqlite:///' + p

        return ''

    # build initial form
    conn = cfg_existing.get('conn') if isinstance(cfg_existing.get('conn'), dict) else {}
    url_existing = (cfg_existing.get('url') or '').strip()

    # If no structured conn, best-effort parse from SQLAlchemy URL
    if not conn and url_existing:
        try:
            from sqlalchemy.engine.url import make_url
            u = make_url(url_existing)
            conn = {
                'host': u.host or '',
                'port': str(u.port or ''),
                'database': u.database or '',
                'username': u.username or '',
                'password': u.password or '',
            }
            q = dict(u.query or {})
            if (src.type or '').lower() == 'sqlserver':
                conn['driver'] = q.get('driver', '')
            if (src.type or '').lower() == 'oracle':
                conn['service_name'] = q.get('service_name', '')
                conn['sid'] = q.get('sid', '')
        except Exception:
            conn = {}

    form = {
        'name': (request.form.get('name') or src.name or '').strip(),
        'type': (request.form.get('type') or src.type or '').strip().lower(),
        'url': (request.form.get('url') or url_existing or '').strip(),
        'default_schema': (request.form.get('default_schema') or (cfg_existing.get('default_schema') or '')).strip(),
        'tenant_column': (request.form.get('tenant_column') or (cfg_existing.get('tenant_column') or '')).strip(),
        'host': (request.form.get('host') or conn.get('host') or '').strip(),
        'port': (request.form.get('port') or conn.get('port') or '').strip(),
        'database': (request.form.get('database') or conn.get('database') or '').strip(),
        'username': (request.form.get('username') or conn.get('username') or '').strip(),
        'password': (request.form.get('password') or '').strip(),
        'driver': (request.form.get('driver') or conn.get('driver') or '').strip(),
        'service_name': (request.form.get('service_name') or conn.get('service_name') or '').strip(),
        'sid': (request.form.get('sid') or conn.get('sid') or '').strip(),
        'sqlite_path': (request.form.get('sqlite_path') or conn.get('sqlite_path') or '').strip(),
        'use_builder': (request.form.get('use_builder') or '').strip(),
        'policy_json': (request.form.get('policy_json') or '').strip(),
    }

    # Policy controls safety limits for queries on this datasource
    import json

    default_policy = src.policy_json or {"timeout_seconds": 30, "max_rows": 5000, "read_only": True}

    def _to_bool(v, default=True):
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return bool(v)
        if isinstance(v, str):
            s = v.strip().lower()
            if s in ("true", "1", "yes", "y", "on"):
                return True
            if s in ("false", "0", "no", "n", "off"):
                return False
        return default

    def _to_int(v, default, *, min_v=1, max_v=50000):
        try:
            i = int(v)
        except Exception:
            return default
        if i < min_v:
            i = min_v
        if i > max_v:
            i = max_v
        return i

    def _sanitize_policy(p: dict) -> dict:
        out = dict(p or {})
        out["read_only"] = _to_bool(out.get("read_only"), bool(default_policy.get("read_only", True)))
        out["max_rows"] = _to_int(out.get("max_rows"), int(default_policy.get("max_rows", 5000)), min_v=1, max_v=50000)
        out["timeout_seconds"] = _to_int(out.get("timeout_seconds"), int(default_policy.get("timeout_seconds", 30)), min_v=1, max_v=300)
        return out

    if not form.get('policy_json'):
        form['policy_json'] = json.dumps(default_policy, indent=2, ensure_ascii=False)

    has_password = bool(conn.get('password'))

    if request.method == 'POST':
        name = form['name']
        ds_type = form['type']
        default_schema = form['default_schema'] or None
        tenant_column = form['tenant_column'] or None

        # If password left empty, keep existing password if we have it
        existing_pwd = (conn.get('password') or '')
        if not form['password'] and existing_pwd:
            form['password'] = existing_pwd

        url = (form['url'] or '').strip()
        if form['use_builder'] == '1' or not url:
            url = _build_url_from_parts(ds_type, form)

        # If user used manual URL and did not fill the password field, try extracting it
        # (but ignore redacted placeholders like "***").
        if not form.get('password') and url:
            try:
                from sqlalchemy.engine.url import make_url

                def _looks_masked(p: str | None) -> bool:
                    if not p:
                        return True
                    s = str(p)
                    if set(s).issubset({"*"}) and len(s) >= 3:
                        return True
                    if set(s).issubset({"•"}) and len(s) >= 3:
                        return True
                    if s.endswith("***") and "*" not in s[:-3]:
                        return True
                    return False

                u = make_url(url)
                if u.password and not _looks_masked(u.password):
                    form['password'] = u.password
            except Exception:
                pass

        if not name or not ds_type or not url:
            flash(tr('Preencha nome, tipo e conexão.', getattr(g, 'lang', None)), 'error')
            return render_template('portal/sources_edit.html', tenant=g.tenant, source=src, form=form, has_password=has_password)

        # Parse and validate policy JSON
        policy_raw = (request.form.get('policy_json') or '').strip()
        try:
            if policy_raw:
                policy_obj = json.loads(policy_raw)
                if not isinstance(policy_obj, dict):
                    raise ValueError('policy_json deve ser um objeto JSON')
            else:
                policy_obj = default_policy
            policy_obj = _sanitize_policy(policy_obj)
        except Exception as e:
            flash(tr('Política inválida: {error}', getattr(g, 'lang', None), error=str(e)), 'error')
            form['policy_json'] = policy_raw or form.get('policy_json','')
            return render_template('portal/sources_edit.html', tenant=g.tenant, source=src, form=form, has_password=has_password)


        from ...services.crypto import encrypt_json
        from ...services.datasource_service import clear_engine_cache

        new_conn = {
            'host': form['host'],
            'port': form['port'],
            'database': form['database'],
            'username': form['username'],
            'password': form['password'],
            'driver': form['driver'],
            'service_name': form['service_name'],
            'sid': form['sid'],
            'sqlite_path': form['sqlite_path'],
        }

        # Ensure we have an effective URL that includes the real password for runtime use
        effective_url = inject_password_into_url(url, new_conn.get('password'))
        if (not effective_url) and new_conn:
            effective_url = build_url_from_conn(ds_type, new_conn)
        if not effective_url:
            flash(tr('Preencha nome, tipo e conexão.', getattr(g, 'lang', None)), 'error')
            return render_template('portal/sources_edit.html', tenant=g.tenant, source=src, form=form, has_password=has_password)

        stored_url = redact_url_password(effective_url)

        config = {
            'url': stored_url,
            'default_schema': default_schema,
            'tenant_column': tenant_column,
            'conn': new_conn,
        }

        src.name = name
        src.type = ds_type
        src.config_encrypted = encrypt_json(config)
        src.policy_json = policy_obj
        db.session.commit()
        clear_engine_cache()

        flash(tr('Fonte atualizada.', getattr(g, 'lang', None)), 'success')
        return redirect(url_for('portal.sources_view', source_id=src.id))

    return render_template('portal/sources_edit.html', tenant=g.tenant, source=src, form=form, has_password=has_password)


@bp.route("/api/sources/test_connection", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def api_sources_test_connection():
    """Test a DB connection using the provided (unsaved) datasource config.

    This endpoint is used by the 'Test connection' button in the datasource form.
    It does not persist anything.

    Payload shape (best-effort):
    {
      source_id?: int,  # optional (edit form)
      type: 'postgres'|'mysql'|'sqlserver'|'oracle'|'sqlite',
      use_builder: '1'|'0',
      url?: str,
      host/port/database/username/password/driver/service_name/sid/sqlite_path?: str
    }
    """
    _require_tenant()
    payload = request.get_json(silent=True) or {}

    # Optional: reuse existing password when editing
    src = None
    existing_cfg = {}
    try:
        source_id = int(payload.get("source_id") or 0)
    except Exception:
        source_id = 0
    if source_id:
        src = DataSource.query.filter_by(id=source_id, tenant_id=g.tenant.id).first()
        if src:
            try:
                existing_cfg = decrypt_config(src) or {}
            except Exception:
                existing_cfg = {}

    def _build_url_from_parts(ds_type: str, parts: dict) -> str:
        ds_type = (ds_type or "").lower().strip()
        host = (parts.get("host") or "").strip()
        port = (parts.get("port") or "").strip()
        database = (parts.get("database") or "").strip()
        username = (parts.get("username") or "").strip()
        password = (parts.get("password") or "")
        driver = (parts.get("driver") or "").strip()
        service_name = (parts.get("service_name") or "").strip()
        sid = (parts.get("sid") or "").strip()
        sqlite_path = (parts.get("sqlite_path") or "").strip()

        from sqlalchemy.engine import URL

        if ds_type == "audela_finance":
            return "internal://audela_finance"
        if ds_type == "audela_project":
            return "internal://audela_project"

        if ds_type == "postgres":
            return str(
                URL.create(
                    "postgresql+psycopg2",
                    username=username or None,
                    password=password or None,
                    host=host or None,
                    port=int(port) if port else None,
                    database=database or None,
                )
            )

        if ds_type == "mysql":
            return str(
                URL.create(
                    "mysql+pymysql",
                    username=username or None,
                    password=password or None,
                    host=host or None,
                    port=int(port) if port else None,
                    database=database or None,
                )
            )

        if ds_type == "sqlserver":
            query = {}
            if driver:
                query["driver"] = driver
            return str(
                URL.create(
                    "mssql+pyodbc",
                    username=username or None,
                    password=password or None,
                    host=host or None,
                    port=int(port) if port else None,
                    database=database or None,
                    query=query or None,
                )
            )

        if ds_type == "oracle":
            query = {}
            if service_name:
                query["service_name"] = service_name
            elif sid:
                query["sid"] = sid
            return str(
                URL.create(
                    "oracle+oracledb",
                    username=username or None,
                    password=password or None,
                    host=host or None,
                    port=int(port) if port else None,
                    database=None,
                    query=query or None,
                )
            )

        if ds_type == "sqlite":
            if sqlite_path.startswith("sqlite:"):
                return sqlite_path
            p = sqlite_path or database
            if not p:
                return ""
            if p.startswith("/"):
                return "sqlite:////" + p.lstrip("/")
            return "sqlite:///" + p

        return ""

    ds_type = (payload.get("type") or "").strip().lower()
    use_builder = str(payload.get("use_builder") or "0").strip()
    url = (payload.get("url") or "").strip()

    # merge password from existing config (edit form)
    existing_conn = existing_cfg.get("conn") if isinstance(existing_cfg.get("conn"), dict) else {}
    existing_pwd = (existing_conn.get("password") or "") if isinstance(existing_conn, dict) else ""

    parts = {
        "host": (payload.get("host") or "").strip(),
        "port": (payload.get("port") or "").strip(),
        "database": (payload.get("database") or "").strip(),
        "username": (payload.get("username") or "").strip(),
        "password": payload.get("password") or "",
        "driver": (payload.get("driver") or "").strip(),
        "service_name": (payload.get("service_name") or "").strip(),
        "sid": (payload.get("sid") or "").strip(),
        "sqlite_path": (payload.get("sqlite_path") or "").strip(),
    }

    if not parts["password"] and existing_pwd:
        parts["password"] = existing_pwd
        
    if use_builder == "1" or not url:
        url = _build_url_from_parts(ds_type, parts)
    
    # If URL has redacted password (***), inject the real one from parts
    try:
        from ...services.datasource_service import inject_password_into_url

        url = inject_password_into_url(url, parts.get("password"))
    except Exception:
        pass

    if not url:
        return jsonify({"ok": False, "error": tr("Informe uma URL de conexão.", getattr(g, "lang", None))}), 400

    if ds_type in ("audela_finance", "audela_project"):
        return jsonify({"ok": True, "message": tr("Conexão interna OK.", getattr(g, "lang", None))})

    # Try connecting (no persistence)
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.pool import NullPool

        eng = create_engine(url, pool_pre_ping=True, poolclass=NullPool)
        with eng.connect() as conn:
            # connect + close is enough for a smoke test
            pass
        return jsonify({"ok": True, "message": tr("Conexão OK.", getattr(g, "lang", None))})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": tr("Falha na conexão: {error}", getattr(g, "lang", None), error=str(e))}), 400



@bp.route("/sources/<int:source_id>/introspect")
@login_required
@require_roles("tenant_admin", "creator")
def sources_introspect(source_id: int):
    _require_tenant()
    src = DataSource.query.filter_by(id=source_id, tenant_id=g.tenant.id).first_or_404()
    try:
        meta = introspect_source(src)
    except Exception as e:  # noqa: BLE001
        flash(tr("Falha ao introspectar: {error}", getattr(g, "lang", None), error=str(e)), "error")
        meta = {"schemas": []}
    _audit("bi.datasource.introspected", {"id": src.id})
    db.session.commit()
    return render_template(
        "portal/sources_introspect.html",
        tenant=g.tenant,
        source=src,
        meta=meta,
    )


@bp.route("/sources/diagram")
@login_required
@require_roles("tenant_admin", "creator")
def sources_diagram():
    _require_tenant()
    sources = (
        DataSource.query.filter_by(tenant_id=g.tenant.id)
        .order_by(DataSource.name.asc())
        .all()
    )
    return render_template("portal/sources_diagram.html", tenant=g.tenant, sources=sources)


# -----------------------------
# API (schema, NLQ, export)
# -----------------------------


@bp.route("/api/sources/<int:source_id>/schema")
@login_required
@require_roles("tenant_admin", "creator")
def api_source_schema(source_id: int):
    _require_tenant()
    src = DataSource.query.filter_by(id=source_id, tenant_id=g.tenant.id).first_or_404()
    meta = introspect_source(src)
    return jsonify(meta)


@bp.route("/api/files/<int:file_id>/schema")
@login_required
@require_roles("tenant_admin", "creator")
def api_file_schema(file_id: int):
    """Return cached file schema (or infer it) for autocomplete/join builder."""
    _require_tenant()
    asset = FileAsset.query.filter_by(id=file_id, tenant_id=g.tenant.id).first_or_404()
    schema = asset.schema_json
    if not schema:
        try:
            abs_path = resolve_abs_path(g.tenant.id, asset.storage_path)
            schema = introspect_file_schema(abs_path, asset.file_format)
            asset.schema_json = schema
            db.session.commit()
        except Exception:
            schema = {"columns": []}
    return jsonify(schema or {"columns": []})


@bp.route("/api/sources/<int:source_id>/diagram")
@login_required
@require_roles("tenant_admin", "creator")
def api_source_diagram(source_id: int):
    """Return a simple graph (tables + inferred relations) for a source."""
    _require_tenant()
    src = DataSource.query.filter_by(id=source_id, tenant_id=g.tenant.id).first_or_404()
    meta = introspect_source(src)
    # Flatten tables across schemas
    tables = []
    for s in meta.get("schemas", []):
        for t in s.get("tables", []):
            table_name = t.get("name")
            schema_name = s.get("name")
            raw_columns = t.get("columns", []) or []
            columns = []
            for c in raw_columns:
                if isinstance(c, dict):
                    columns.append(
                        {
                            "name": c.get("name"),
                            "type": c.get("type"),
                            "nullable": c.get("nullable"),
                            "primary_key": c.get("primary_key") or c.get("pk"),
                            "default": c.get("default"),
                        }
                    )
                else:
                    columns.append({"name": str(c)})

            tables.append(
                {
                    "name": table_name,
                    "schema": schema_name,
                    "full_name": f"{schema_name}.{table_name}" if schema_name else table_name,
                    "columns": columns,
                    "column_count": len(columns),
                }
            )

    # Infer relations via simple foreign-key naming heuristics (col ending with _id)
    name_index = {t["name"]: t for t in tables}
    relations = []
    for t in tables:
        for col in t.get("columns", []):
            col_name = col if isinstance(col, str) else (col or {}).get("name")
            if not isinstance(col_name, str):
                continue
            if not col_name.endswith("_id"):
                continue
            base = col_name[:-3]
            target = None
            # direct match
            if base in name_index:
                target = base
            # try plural/singular heuristics
            elif base + "s" in name_index:
                target = base + "s"
            elif base.endswith("s") and base[:-1] in name_index:
                target = base[:-1]
            else:
                # fallback: find table that contains base
                for tn in name_index:
                    if tn.endswith(base) or tn.startswith(base):
                        target = tn
                        break
            if target:
                relations.append({"from": f"{t['name']}.{col_name}", "to": f"{target}.id"})

    return jsonify({"tables": tables, "relations": relations})


@bp.route("/api/nlq", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def api_nlq():
    _require_tenant()
    payload = request.get_json(silent=True) or {}
    try:
        source_id = int(payload.get("source_id") or 0)
    except Exception:
        source_id = 0
    text = (payload.get("text") or "").strip()
    if not source_id:
        return jsonify({"error": tr("Selecione uma fonte.", getattr(g, "lang", None))}), 400
    src = DataSource.query.filter_by(id=source_id, tenant_id=g.tenant.id).first()
    if not src:
        return jsonify({"error": tr("Fonte inválida.", getattr(g, "lang", None))}), 404
    sql_text, warnings = generate_sql_from_nl(src, text, lang=getattr(g, "lang", None))
    return jsonify({"sql": sql_text, "warnings": warnings})


@bp.route("/api/workspaces/draft_sql", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def api_workspaces_draft_sql():
    """Generate a SQL draft (optionally via OpenAI) for a *new* workspace.

    We build an in-memory workspace datasource using the selected files + DB tables,
    then reuse the existing NLQ service grounded on its schema.
    """
    _require_tenant()
    payload = request.get_json(silent=True) or {}

    prompt = (payload.get("prompt") or payload.get("text") or "").strip()
    if not prompt:
        return jsonify({"error": tr("Descreva sua análise.", getattr(g, "lang", None))}), 400

    try:
        base_db_source_id = int(payload.get("db_source_id") or 0) or None
    except Exception:
        base_db_source_id = None

    db_tables = payload.get("db_tables") or []
    if isinstance(db_tables, str):
        db_tables = [x.strip() for x in db_tables.split(",") if x.strip()]
    if not isinstance(db_tables, list):
        db_tables = []

    files_cfg_in = payload.get("files") or []
    if not isinstance(files_cfg_in, list):
        files_cfg_in = []

    # Enforce tenant isolation for file ids
    file_ids = []
    for x in files_cfg_in:
        try:
            fid = int((x or {}).get("file_id") or 0)
            if fid:
                file_ids.append(fid)
        except Exception:
            continue

    allowed_ids = set()
    if file_ids:
        allowed_ids = {a.id for a in FileAsset.query.filter(FileAsset.tenant_id == g.tenant.id, FileAsset.id.in_(file_ids)).all()}

    files_cfg: list[dict] = []
    for x in files_cfg_in:
        try:
            fid = int((x or {}).get("file_id") or 0)
        except Exception:
            continue
        if fid and fid in allowed_ids:
            alias = (x or {}).get("table") or f"file_{fid}"
            files_cfg.append({"file_id": fid, "table": str(alias).strip()})

    # Validate DB source id belongs to tenant
    if base_db_source_id:
        base = DataSource.query.filter_by(id=int(base_db_source_id), tenant_id=g.tenant.id).first()
        if not base:
            base_db_source_id = None
            db_tables = []

    try:
        max_rows = int(payload.get("max_rows") or 5000)
    except Exception:
        max_rows = 5000
    max_rows = max(100, min(max_rows, 50000))

    cfg = {
        "db_source_id": base_db_source_id,
        "db_tables": [str(x).strip() for x in db_tables if str(x).strip()][:200],
        "db_views": [],
        "files": files_cfg,
        "max_rows": max_rows,
    }

    from ...services.crypto import encrypt_json

    draft = DataSource(
        tenant_id=g.tenant.id,
        name="__draft_workspace__",
        type="workspace",
        config_encrypted=encrypt_json(cfg),
        policy_json={"read_only": True, "max_rows": max_rows, "timeout_seconds": 30},
    )

    sql_text, warnings = generate_sql_from_nl(draft, prompt, lang=getattr(g, "lang", None))
    return jsonify({"sql": sql_text, "warnings": warnings})


@bp.route("/api/export/pdf", methods=["POST"])
@login_required
def api_export_pdf():
    _require_tenant()
    payload = request.get_json(silent=True) or {}
    title = (payload.get("title") or "Export").strip()
    columns = payload.get("columns") or []
    rows = payload.get("rows") or []

    # Conservative limits
    if not isinstance(columns, list) or not isinstance(rows, list):
        return jsonify({"error": "Payload inválido."}), 400
    if len(columns) > 200:
        return jsonify({"error": "Muitas colunas."}), 400
    if len(rows) > 5000:
        rows = rows[:5000]

    pdf_bytes = table_to_pdf_bytes(title, [str(c) for c in columns], rows)
    resp = make_response(pdf_bytes)
    resp.headers["Content-Type"] = "application/pdf"
    resp.headers["Content-Disposition"] = f'attachment; filename="{title[:80].replace(" ", "_")}.pdf"'
    return resp


@bp.route("/api/export/xlsx", methods=["POST"])
@login_required
def api_export_xlsx():
    """Export a result table to Excel.

    Expected payload: {title, columns, rows, add_chart?}
    """
    _require_tenant()
    payload = request.get_json(silent=True) or {}
    title = (payload.get("title") or "Export").strip()
    columns = payload.get("columns") or []
    rows = payload.get("rows") or []
    add_chart = bool(payload.get("add_chart", True))

    if not isinstance(columns, list) or not isinstance(rows, list):
        return jsonify({"error": "Payload inválido."}), 400
    if len(columns) > 300:
        return jsonify({"error": "Muitas colunas."}), 400
    if len(rows) > 50000:
        rows = rows[:50000]

    xlsx_bytes = table_to_xlsx_bytes(title, [str(c) for c in columns], rows, add_chart=add_chart)
    resp = make_response(xlsx_bytes)
    resp.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    resp.headers["Content-Disposition"] = f'attachment; filename="{title[:80].replace(" ", "_")}.xlsx"'
    return resp


@bp.route("/api/excel/generate", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def api_excel_generate():
    """Generate an Excel file from a natural-language request.

    Payload:
      {
        source_id: int,
        prompt: str,
        title?: str,
        max_rows?: int,
        add_chart?: bool,
        store?: bool,
        folder_id?: int
      }
    """
    _require_tenant()
    payload = request.get_json(silent=True) or {}

    try:
        source_id = int(payload.get("source_id"))
    except Exception:
        return jsonify({"error": "source_id inválido."}), 400

    prompt = (payload.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"error": "Prompt vazio."}), 400

    title = (payload.get("title") or "Excel Export").strip() or "Excel Export"
    add_chart = bool(payload.get("add_chart", True))
    store = bool(payload.get("store", True))
    folder_id = payload.get("folder_id")

    try:
        max_rows = int(payload.get("max_rows") or 5000)
    except Exception:
        max_rows = 5000
    max_rows = max(100, min(max_rows, 50000))

    source = DataSource.query.filter_by(id=source_id, tenant_id=g.tenant.id).first()
    if not source:
        return jsonify({"error": "Fonte inválida."}), 404

    # NLQ -> SQL (OpenAI if configured, else heuristic)
    sql_text, warnings = generate_sql_from_nl(source, prompt, lang=getattr(g, "lang", None))

    # Execute
    try:
        result = execute_sql(source, sql_text, params={"tenant_id": g.tenant.id}, row_limit=max_rows)
    except QueryExecutionError as e:
        return jsonify({"error": str(e), "sql": sql_text, "warnings": warnings}), 400

    xlsx_bytes = table_to_xlsx_bytes(
        title,
        [str(c) for c in (result.get("columns") or [])],
        result.get("rows") or [],
        add_chart=add_chart,
    )

    # Optionally store in tenant files
    stored_asset = None
    if store:
        from werkzeug.utils import secure_filename

        folder = None
        if folder_id not in (None, "", 0, "0"):
            try:
                folder = FileFolder.query.filter_by(id=int(folder_id), tenant_id=g.tenant.id).first()
            except Exception:
                folder = None

        folder_rel = _folder_rel_path(folder)
        filename = secure_filename(f"{title}.xlsx") or "export.xlsx"
        from ...services.file_storage_service import store_bytes
        from ...services.file_introspect_service import infer_schema_for_asset

        stored = store_bytes(g.tenant.id, folder_rel, filename, xlsx_bytes)
        asset = FileAsset(
            tenant_id=g.tenant.id,
            folder_id=folder.id if folder else None,
            name=title,
            storage_path=stored.rel_path,
            file_format=stored.file_format,
            original_filename=stored.original_filename,
        )
        asset.schema_json = infer_schema_for_asset(asset)
        db.session.add(asset)
        db.session.commit()
        stored_asset = {"id": asset.id, "name": asset.name}

    # Return as file download (and include diagnostics in headers)
    resp = make_response(xlsx_bytes)
    resp.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    resp.headers["Content-Disposition"] = f'attachment; filename="{title[:80].replace(" ", "_")}.xlsx"'
    if warnings:
        resp.headers["X-Audela-Warnings"] = "; ".join([str(w) for w in warnings[:5]])
    if stored_asset:
        resp.headers["X-Audela-FileAsset"] = str(stored_asset.get("id"))
    return resp


# -----------------------------
# Files (Upload / URL / S3)
# -----------------------------


def _folder_rel_path(folder: FileFolder | None) -> str:
    """Map a folder tree to a stable on-disk path.

    Uses folder IDs instead of names to avoid rename/move issues.
    """
    if not folder:
        return ""
    chain = []
    cur = folder
    while cur is not None:
        chain.append(f"f_{cur.id}")
        cur = cur.parent
    chain.reverse()
    return "folders/" + "/".join(chain)


def _build_files_tree(tenant_id: int):
    folders = FileFolder.query.filter_by(tenant_id=tenant_id).all()
    files = FileAsset.query.filter_by(tenant_id=tenant_id).order_by(FileAsset.created_at.desc()).all()

    f_by_id: dict[int, dict] = {}
    roots: list[dict] = []
    for f in folders:
        f_by_id[f.id] = {"folder": f, "children": [], "files": []}
    for f in folders:
        node = f_by_id[f.id]
        if f.parent_id and f.parent_id in f_by_id:
            f_by_id[f.parent_id]["children"].append(node)
        else:
            roots.append(node)
    for a in files:
        if a.folder_id and a.folder_id in f_by_id:
            f_by_id[a.folder_id]["files"].append(a)
    # root-level files
    root_files = [a for a in files if not a.folder_id]
    return {"roots": roots, "root_files": root_files}


@bp.route("/files", methods=["GET"])
@login_required
@require_roles("tenant_admin", "creator")
def files_home():
    _require_tenant()

    # Current folder selection
    folder_id = request.args.get("folder")
    current_folder: FileFolder | None = None
    if folder_id:
        try:
            current_folder = FileFolder.query.filter_by(
                id=int(folder_id), tenant_id=g.tenant.id
            ).first()
        except Exception:
            current_folder = None

    tree = _build_files_tree(g.tenant.id)
    all_folders = FileFolder.query.filter_by(tenant_id=g.tenant.id).order_by(FileFolder.name.asc()).all()

    # Children listing (explorer right pane)
    parent_id = current_folder.id if current_folder else None
    child_folders = (
        FileFolder.query.filter_by(tenant_id=g.tenant.id, parent_id=parent_id)
        .order_by(FileFolder.name.asc())
        .all()
    )
    child_files = (
        FileAsset.query.filter_by(tenant_id=g.tenant.id, folder_id=parent_id)
        .order_by(FileAsset.created_at.desc())
        .all()
    )

    # Breadcrumb
    breadcrumb: list[FileFolder] = []
    breadcrumb_ids: list[int] = []
    cur = current_folder
    while cur is not None:
        breadcrumb.append(cur)
        breadcrumb_ids.append(cur.id)
        cur = cur.parent
    breadcrumb.reverse()
    breadcrumb_ids.reverse()

    return render_template(
        "portal/files.html",
        tenant=g.tenant,
        tree=tree,
        folders=all_folders,
        current_folder=current_folder,
        child_folders=child_folders,
        child_files=child_files,
        breadcrumb=breadcrumb,
        breadcrumb_ids=set(breadcrumb_ids),
    )


def _safe_next_url() -> str | None:
    nxt = request.form.get("next") or request.args.get("next")
    if not nxt:
        return None
    nxt = str(nxt)
    # Basic open-redirect protection: only allow local relative URLs
    if nxt.startswith("/") and "://" not in nxt and "\\" not in nxt:
        return nxt
    return None

def _redirect_back(default_endpoint: str = "portal.files_home", **kwargs):
    nxt = _safe_next_url()
    if nxt:
        return redirect(nxt)
    return redirect(url_for(default_endpoint, **kwargs))


@bp.route("/files/folders", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def files_create_folder():
    _require_tenant()

    name = (request.form.get("name") or "").strip()
    parent_id = request.form.get("parent_id")

    if not name:
        flash(_("Nome da pasta é obrigatório."), "danger")
        return _redirect_back()

    parent = None
    if parent_id:
        try:
            parent = FileFolder.query.filter_by(id=int(parent_id), tenant_id=g.tenant.id).first()
        except Exception:
            parent = None

    folder = FileFolder(tenant_id=g.tenant.id, name=name, parent_id=parent.id if parent else None)
    db.session.add(folder)
    db.session.commit()

    # Ensure folder path exists on disk
    rel = _folder_rel_path(folder)
    from ...services.file_storage_service import ensure_tenant_root

    base = ensure_tenant_root(g.tenant.id)
    import os

    os.makedirs(os.path.join(base, rel), exist_ok=True)

    flash(_("Pasta criada."), "success")
    return _redirect_back(folder=folder.parent_id or "")


@bp.route("/files/upload", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def files_upload():
    _require_tenant()

    f = request.files.get("file")
    display_name = (request.form.get("display_name") or "").strip()
    folder_id = request.form.get("folder_id")

    folder = None
    if folder_id:
        try:
            folder = FileFolder.query.filter_by(id=int(folder_id), tenant_id=g.tenant.id).first()
        except Exception:
            folder = None

    if not f:
        flash(_("Nenhum arquivo enviado."), "danger")
        return _redirect_back(folder=folder.id if folder else "")

    from ...services.file_storage_service import store_upload
    from ...services.file_introspect_service import infer_schema_for_asset

    folder_rel = _folder_rel_path(folder)
    stored = store_upload(g.tenant.id, f, folder_rel=folder_rel)

    asset = FileAsset(
        tenant_id=g.tenant.id,
        folder_id=folder.id if folder else None,
        name=display_name or stored.get("original_filename") or "arquivo",
        storage_path=stored["storage_path"],
        file_format=stored["file_format"],
        original_filename=stored.get("original_filename"),
    )
    asset.schema_json = infer_schema_for_asset(asset)
    db.session.add(asset)
    db.session.commit()

    flash(_("Arquivo enviado."), "success")
    return _redirect_back(folder=folder.id if folder else "")


@bp.route("/files/from_url", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def files_from_url():
    _require_tenant()

    url = (request.form.get("url") or "").strip()
    filename = (request.form.get("filename") or "").strip()
    display_name = (request.form.get("display_name") or "").strip()
    folder_id = request.form.get("folder_id")

    if not url:
        flash(_("URL é obrigatória."), "danger")
        return _redirect_back()

    folder = None
    if folder_id:
        try:
            folder = FileFolder.query.filter_by(id=int(folder_id), tenant_id=g.tenant.id).first()
        except Exception:
            folder = None

    from ...services.file_storage_service import download_from_url
    from ...services.file_introspect_service import infer_schema_for_asset

    folder_rel = _folder_rel_path(folder)
    stored = download_from_url(g.tenant.id, url, filename_hint=filename, folder_rel=folder_rel)

    asset = FileAsset(
        tenant_id=g.tenant.id,
        folder_id=folder.id if folder else None,
        name=display_name or stored.get("original_filename") or filename or "arquivo",
        storage_path=stored["storage_path"],
        file_format=stored["file_format"],
        original_filename=stored.get("original_filename"),
    )
    asset.schema_json = infer_schema_for_asset(asset)
    db.session.add(asset)
    db.session.commit()

    flash(_("Arquivo importado da URL."), "success")
    return _redirect_back(folder=folder.id if folder else "")


@bp.route("/files/from_s3", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def files_from_s3():
    _require_tenant()

    bucket = (request.form.get("bucket") or "").strip()
    key = (request.form.get("key") or "").strip()
    filename = (request.form.get("filename") or "").strip()
    region = (request.form.get("region") or "").strip() or None
    display_name = (request.form.get("display_name") or "").strip()
    folder_id = request.form.get("folder_id")

    if not bucket or not key:
        flash(_("Bucket e key são obrigatórios."), "danger")
        return _redirect_back()

    folder = None
    if folder_id:
        try:
            folder = FileFolder.query.filter_by(id=int(folder_id), tenant_id=g.tenant.id).first()
        except Exception:
            folder = None

    from ...services.file_storage_service import download_from_s3
    from ...services.file_introspect_service import infer_schema_for_asset

    folder_rel = _folder_rel_path(folder)
    stored = download_from_s3(g.tenant.id, bucket=bucket, key=key, filename_hint=filename, region=region, folder_rel=folder_rel)

    asset = FileAsset(
        tenant_id=g.tenant.id,
        folder_id=folder.id if folder else None,
        name=display_name or stored.get("original_filename") or filename or key.split("/")[-1] or "arquivo",
        storage_path=stored["storage_path"],
        file_format=stored["file_format"],
        original_filename=stored.get("original_filename"),
    )
    asset.schema_json = infer_schema_for_asset(asset)
    db.session.add(asset)
    db.session.commit()

    flash(_("Arquivo importado do S3."), "success")
    return _redirect_back(folder=folder.id if folder else "")


@bp.route("/files/<int:file_id>/download", methods=["GET"])
@login_required
@require_roles("tenant_admin", "creator")
def files_download(file_id: int):
    _require_tenant()
    asset = FileAsset.query.filter_by(id=file_id, tenant_id=g.tenant.id).first_or_404()

    from ...services.file_storage_service import resolve_abs_path

    abs_path = resolve_abs_path(g.tenant.id, asset.storage_path)
    return send_file(abs_path, as_attachment=True, download_name=asset.original_filename or asset.name)


@bp.route("/files/<int:file_id>/delete", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def files_delete(file_id: int):
    _require_tenant()

    asset = FileAsset.query.filter_by(id=file_id, tenant_id=g.tenant.id).first_or_404()

    from ...services.file_storage_service import delete_storage_path

    delete_storage_path(g.tenant.id, asset.storage_path)
    db.session.delete(asset)
    db.session.commit()

    flash(_("Arquivo removido."), "success")
    return _redirect_back()


@bp.route("/files/folders/<int:folder_id>/delete", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def files_folders_delete(folder_id: int):
    _require_tenant()

    folder = FileFolder.query.filter_by(id=folder_id, tenant_id=g.tenant.id).first_or_404()

    # Delete assets in subtree
    from ...services.file_storage_service import delete_storage_path
    import os
    import shutil
    from ...services.file_storage_service import ensure_tenant_root

    tenant_root = ensure_tenant_root(g.tenant.id)
    rel = _folder_rel_path(folder)
    abs_dir = os.path.join(tenant_root, rel)

    # Remove all file assets that live under that folder path
    prefix = rel + "/"
    assets = FileAsset.query.filter(
        FileAsset.tenant_id == g.tenant.id,
        FileAsset.storage_path.like(prefix + "%"),
    ).all()
    for a in assets:
        try:
            delete_storage_path(g.tenant.id, a.storage_path)
        except Exception:
            pass
        db.session.delete(a)

    # Delete folder row + descendants (DB cascade should handle children via relationship; but be explicit)
    # Remove descendant folders from DB
    def gather_descendants(fid: int) -> list[FileFolder]:
        out = []
        stack = [fid]
        while stack:
            x = stack.pop()
            kids = FileFolder.query.filter_by(tenant_id=g.tenant.id, parent_id=x).all()
            for k in kids:
                out.append(k)
                stack.append(k.id)
        return out

    for sub in gather_descendants(folder.id):
        db.session.delete(sub)

    db.session.delete(folder)
    db.session.commit()

    # Remove directory tree from disk
    try:
        if os.path.isdir(abs_dir):
            shutil.rmtree(abs_dir, ignore_errors=True)
    except Exception:
        pass

    flash(_("Pasta removida."), "success")
    return _redirect_back()


# --- Explorer operations (rename / move) ---

@bp.route("/files/<int:file_id>/rename", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def files_rename(file_id: int):
    _require_tenant()
    asset = FileAsset.query.filter_by(id=file_id, tenant_id=g.tenant.id).first_or_404()

    if request.is_json:
        name = (request.json or {}).get("name")
    else:
        name = request.form.get("name")

    name = (name or "").strip()
    if not name:
        msg = _("Nome é obrigatório.")
        if request.is_json:
            return jsonify({"ok": False, "error": msg}), 400
        flash(msg, "danger")
        return _redirect_back()

    asset.name = name
    db.session.commit()

    if request.is_json:
        return jsonify({"ok": True})
    flash(_("Arquivo renomeado."), "success")
    return _redirect_back()


@bp.route("/files/folders/<int:folder_id>/rename", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def folders_rename(folder_id: int):
    _require_tenant()
    folder = FileFolder.query.filter_by(id=folder_id, tenant_id=g.tenant.id).first_or_404()

    if request.is_json:
        name = (request.json or {}).get("name")
    else:
        name = request.form.get("name")

    name = (name or "").strip()
    if not name:
        msg = _("Nome é obrigatório.")
        if request.is_json:
            return jsonify({"ok": False, "error": msg}), 400
        flash(msg, "danger")
        return _redirect_back()

    folder.name = name
    db.session.commit()

    if request.is_json:
        return jsonify({"ok": True})
    flash(_("Pasta renomeada."), "success")
    return _redirect_back(folder=folder.id)


@bp.route("/files/<int:file_id>/move", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def files_move(file_id: int):
    _require_tenant()
    asset = FileAsset.query.filter_by(id=file_id, tenant_id=g.tenant.id).first_or_404()

    if request.is_json:
        new_folder_id = (request.json or {}).get("folder_id")
    else:
        new_folder_id = request.form.get("folder_id")

    new_folder = None
    if new_folder_id not in (None, "", 0, "0"):
        try:
            new_folder = FileFolder.query.filter_by(id=int(new_folder_id), tenant_id=g.tenant.id).first()
        except Exception:
            new_folder = None

    import os
    import shutil
    from ...services.file_storage_service import ensure_tenant_root

    tenant_root = ensure_tenant_root(g.tenant.id)
    old_rel = asset.storage_path
    old_abs = os.path.join(tenant_root, old_rel)

    new_dir_rel = _folder_rel_path(new_folder)
    filename = os.path.basename(old_rel)
    new_rel = (new_dir_rel + "/" + filename) if new_dir_rel else filename
    new_abs = os.path.join(tenant_root, new_rel)
    os.makedirs(os.path.dirname(new_abs), exist_ok=True)

    try:
        if os.path.exists(old_abs):
            shutil.move(old_abs, new_abs)
    except Exception:
        pass

    asset.folder_id = new_folder.id if new_folder else None
    asset.storage_path = new_rel
    db.session.commit()

    if request.is_json:
        return jsonify({"ok": True})
    flash(_("Arquivo movido."), "success")
    return _redirect_back(folder=new_folder.id if new_folder else "")


@bp.route("/files/folders/<int:folder_id>/move", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def folders_move(folder_id: int):
    _require_tenant()
    folder = FileFolder.query.filter_by(id=folder_id, tenant_id=g.tenant.id).first_or_404()

    if request.is_json:
        new_parent_id = (request.json or {}).get("parent_id")
    else:
        new_parent_id = request.form.get("parent_id")

    new_parent = None
    if new_parent_id not in (None, "", 0, "0"):
        try:
            new_parent = FileFolder.query.filter_by(id=int(new_parent_id), tenant_id=g.tenant.id).first()
        except Exception:
            new_parent = None

    # Prevent cycles: can't move folder into itself/subtree
    def descendant_ids(root_id: int) -> set[int]:
        out = set()
        stack = [root_id]
        while stack:
            x = stack.pop()
            kids = FileFolder.query.filter_by(tenant_id=g.tenant.id, parent_id=x).all()
            for k in kids:
                if k.id not in out:
                    out.add(k.id)
                    stack.append(k.id)
        return out

    bad = descendant_ids(folder.id)
    bad.add(folder.id)
    if new_parent and new_parent.id in bad:
        msg = _("Movimento inválido.")
        if request.is_json:
            return jsonify({"ok": False, "error": msg}), 400
        flash(msg, "danger")
        return _redirect_back(folder=folder.id)

    import os
    import shutil
    from ...services.file_storage_service import ensure_tenant_root

    tenant_root = ensure_tenant_root(g.tenant.id)

    old_rel = _folder_rel_path(folder)

    # Update parent
    folder.parent_id = new_parent.id if new_parent else None
    folder.parent = new_parent
    db.session.flush()

    new_rel = _folder_rel_path(folder)

    # Move folder dir on disk
    old_abs = os.path.join(tenant_root, old_rel)
    new_abs = os.path.join(tenant_root, new_rel)
    os.makedirs(os.path.dirname(new_abs), exist_ok=True)
    try:
        if os.path.isdir(old_abs):
            shutil.move(old_abs, new_abs)
        else:
            os.makedirs(new_abs, exist_ok=True)
    except Exception:
        os.makedirs(new_abs, exist_ok=True)

    # Update storage_path for assets under this folder subtree
    prefix = old_rel + "/"
    assets = FileAsset.query.filter(
        FileAsset.tenant_id == g.tenant.id,
        FileAsset.storage_path.like(prefix + "%"),
    ).all()
    for a in assets:
        a.storage_path = new_rel + a.storage_path[len(old_rel):]

    db.session.commit()

    if request.is_json:
        return jsonify({"ok": True})
    flash(_("Pasta movida."), "success")
    return _redirect_back(folder=folder.id)


# -----------------------------
# Workspaces (datasource that joins DB + files)
# -----------------------------


@bp.route("/workspaces", methods=["GET"])
@login_required
@require_roles("tenant_admin", "creator")
def workspaces_list():
    _require_tenant()
    workspaces = DataSource.query.filter_by(tenant_id=g.tenant.id, type="workspace").order_by(DataSource.created_at.desc()).all()
    return render_template("portal/workspaces_list.html", tenant=g.tenant, workspaces=workspaces)


@bp.route("/workspaces/new", methods=["GET", "POST"])
@login_required
@require_roles("tenant_admin", "creator")
def workspaces_new():
    _require_tenant()
    db_sources = DataSource.query.filter(DataSource.tenant_id == g.tenant.id, DataSource.type != "workspace").order_by(DataSource.name.asc()).all()
    files = FileAsset.query.filter_by(tenant_id=g.tenant.id).order_by(FileAsset.created_at.desc()).all()

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        base_db_source_id = int(request.form.get("db_source_id") or 0) or None
        db_tables_raw = (request.form.get("db_tables") or "").strip()
        max_rows = int(request.form.get("max_rows") or 5000)
        starter_sql = (request.form.get("starter_sql") or "").strip()

        if not name:
            flash(tr("Nome é obrigatório.", getattr(g, "lang", None)), "error")
            return render_template("portal/workspaces_new.html", tenant=g.tenant, db_sources=db_sources, files=files)

        selected_files = request.form.getlist("file_id")
        files_cfg = []
        for fid_s in selected_files:
            try:
                fid = int(fid_s)
            except Exception:
                continue
            alias = (request.form.get(f"alias_{fid}") or f"file_{fid}").strip()
            files_cfg.append({"file_id": fid, "table": alias})

        db_tables_list = [t.strip() for t in db_tables_raw.split(",") if t.strip()] if db_tables_raw else []

        cfg = {
            "db_source_id": base_db_source_id,
            "db_tables": db_tables_list,
            "db_views": [],
            "files": files_cfg,
            "max_rows": max(100, min(max_rows, 50000)),
            "starter_sql": starter_sql,
        }
        policy = {"read_only": True, "max_rows": max(100, min(max_rows, 50000)), "timeout_seconds": 30}

        from ...services.crypto import encrypt_json

        ws = DataSource(
            tenant_id=g.tenant.id,
            name=name,
            type="workspace",
            config_encrypted=encrypt_json(cfg),
            policy_json=policy,
        )
        db.session.add(ws)
        db.session.commit()
        _audit("bi.workspaces.created", {"id": ws.id, "name": ws.name, "db_source_id": base_db_source_id, "files": [x.get("file_id") for x in files_cfg]})
        flash(tr("Workspace criado.", getattr(g, "lang", None)), "success")
        return redirect(url_for("portal.sources_view", source_id=ws.id))

    return render_template("portal/workspaces_new.html", tenant=g.tenant, db_sources=db_sources, files=files)


# -----------------------------
# Statistics (advanced analysis)
# -----------------------------


@bp.route("/statistics", methods=["GET"]) 
@login_required
@require_roles("tenant_admin", "creator")
def statistics_home():
    """Statistics module: run advanced analyses on a selected datasource/query."""
    _require_tenant()
    sources = DataSource.query.filter_by(tenant_id=g.tenant.id).order_by(DataSource.name.asc()).all()
    questions = Question.query.filter_by(tenant_id=g.tenant.id).order_by(Question.updated_at.desc()).all()
    return render_template(
        "portal/statistics.html",
        tenant=g.tenant,
        sources=sources,
        questions=questions,
        result=None,
        stats=None,
        ai=None,
        error=None,
    )


@bp.route("/statistics/run", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def statistics_run():
    _require_tenant()
    sources = DataSource.query.filter_by(tenant_id=g.tenant.id).order_by(DataSource.name.asc()).all()
    questions = Question.query.filter_by(tenant_id=g.tenant.id).order_by(Question.updated_at.desc()).all()

    # Inputs
    source_id = int(request.form.get("source_id") or 0)
    question_id = int(request.form.get("question_id") or 0)
    sql_text = (request.form.get("sql_text") or "").strip()
    note = (request.form.get("note") or "").strip()

    src = None
    q = None
    if question_id:
        q = Question.query.filter_by(id=question_id, tenant_id=g.tenant.id).first()
        if q:
            src = DataSource.query.filter_by(id=q.source_id, tenant_id=g.tenant.id).first()
            sql_text = (q.sql_text or "").strip()

    if not src and source_id:
        src = DataSource.query.filter_by(id=source_id, tenant_id=g.tenant.id).first()

    if not src:
        return render_template(
            "portal/statistics.html",
            tenant=g.tenant,
            sources=sources,
            questions=questions,
            result=None,
            stats=None,
            ai=None,
            error=tr("Selecione uma fonte (ou pergunta).", getattr(g, "lang", None)),
        )

    if not sql_text:
        return render_template(
            "portal/statistics.html",
            tenant=g.tenant,
            sources=sources,
            questions=questions,
            result=None,
            stats=None,
            ai=None,
            error=tr("Informe um SQL (somente leitura) ou selecione uma pergunta.", getattr(g, "lang", None)),
        )

    # Run query (light sample for analysis)
    try:
        res = execute_sql(src, sql_text, params={"tenant_id": g.tenant.id})
    except QueryExecutionError as e:
        return render_template(
            "portal/statistics.html",
            tenant=g.tenant,
            sources=sources,
            questions=questions,
            result=None,
            stats=None,
            ai=None,
            error=str(e),
        )

    # Keep the in-memory dataset bounded for UI + OpenAI
    if isinstance(res.get("rows"), list) and len(res["rows"]) > 2000:
        res["rows"] = res["rows"][:2000]

    stats = run_statistics_analysis(res)

    # Ask OpenAI for an interpreted report (optional)
    ai = None
    try:
        # Send a compact bundle (stats + a small sample)
        sample_rows = (res.get("rows") or [])[:200]
        bundle = {
            "question": {"name": q.name, "id": q.id} if q else None,
            "source": {"id": src.id, "name": src.name, "type": src.type},
            "result": {"columns": res.get("columns"), "rows": sample_rows},
            "stats": stats,
        }
        user_msg = note or tr(
            "Faça uma análise estatística completa (distribuição normal/gaussiana, correlação, regressão linear e um pequeno cenário de Monte Carlo). Explique achados e riscos. Retorne em linguagem clara.",
            getattr(g, "lang", None),
        )
        ai = analyze_with_ai(bundle, user_msg, history=None, lang=getattr(g, "lang", None))
    except Exception as e:  # noqa: BLE001
        ai = {"error": f"IA indisponível: {e}"}

    # Store last run in session for PDF export
    try:
        from flask import session

        session["stats_last"] = {
            "source_id": src.id,
            "question_id": q.id if q else None,
            "sql_text": sql_text,
            "note": note,
            "generated_at": datetime.utcnow().isoformat(),
        }
    except Exception:
        pass

    return render_template(
        "portal/statistics.html",
        tenant=g.tenant,
        sources=sources,
        questions=questions,
        result=res,
        stats=stats,
        ai=ai,
        error=None,
    )


@bp.route("/statistics/pdf", methods=["GET"])
@login_required
@require_roles("tenant_admin", "creator")
def statistics_pdf():
    """Export the last statistics report to PDF."""
    _require_tenant()
    from flask import session

    payload = session.get("stats_last") or {}
    source_id = int(payload.get("source_id") or 0)
    sql_text = (payload.get("sql_text") or "").strip()
    if not source_id or not sql_text:
        flash(tr("Nenhuma análise recente para exportar.", getattr(g, "lang", None)), "error")
        return redirect(url_for("portal.statistics_home"))

    src = DataSource.query.filter_by(id=source_id, tenant_id=g.tenant.id).first_or_404()

    res = execute_sql(src, sql_text, params={"tenant_id": g.tenant.id})
    if isinstance(res.get("rows"), list) and len(res["rows"]) > 5000:
        res["rows"] = res["rows"][:5000]

    stats = run_statistics_analysis(res)

    # Try to reuse AI output from a fresh call (best-effort)
    ai = None
    try:
        sample_rows = (res.get("rows") or [])[:200]
        bundle = {
            "source": {"id": src.id, "name": src.name, "type": src.type},
            "result": {"columns": res.get("columns"), "rows": sample_rows},
            "stats": stats,
        }
        user_msg = (payload.get("note") or "").strip() or tr(
            "Gere um resumo executivo da análise estatística, com recomendações.",
            getattr(g, "lang", None),
        )
        ai = analyze_with_ai(bundle, user_msg, history=None, lang=getattr(g, "lang", None))
    except Exception:
        ai = None

    title = f"Statistics - {src.name}"
    pdf_bytes = stats_report_to_pdf_bytes(title=title, source=src, sql_text=sql_text, result=res, stats=stats, ai=ai)

    resp = make_response(pdf_bytes)
    resp.headers["Content-Type"] = "application/pdf"
    resp.headers["Content-Disposition"] = f'attachment; filename="{title[:80].replace(" ", "_")}.pdf"'
    return resp


# -----------------------------
# SQL Editor (ad-hoc)
# -----------------------------


@bp.route("/sql", methods=["GET", "POST"])
@login_required
@require_roles("tenant_admin", "creator")
def sql_editor():
    _require_tenant()
    sources = DataSource.query.filter_by(tenant_id=g.tenant.id).order_by(DataSource.name.asc()).all()
    result = None
    error = None
    elapsed_ms = None

    if request.method == "POST":
        source_id = int(request.form.get("source_id") or 0)
        sql_text = request.form.get("sql_text", "")
        params_text = (request.form.get("params_json") or "").strip()
        src = DataSource.query.filter_by(id=source_id, tenant_id=g.tenant.id).first()
        if not src:
            flash(tr("Selecione uma fonte válida.", getattr(g, "lang", None)), "error")
            return render_template("portal/sql_editor.html", tenant=g.tenant, sources=sources)

        started = datetime.utcnow()
        qr = QueryRun(tenant_id=g.tenant.id, question_id=None, user_id=current_user.id, status="running")
        db.session.add(qr)
        db.session.flush()
        # Parse user parameters (JSON) and enforce tenant_id server-side.
        user_params: dict = {}
        if params_text:
            try:
                maybe = json.loads(params_text)
                if isinstance(maybe, dict):
                    user_params = maybe
                else:
                    raise ValueError("params must be object")
            except Exception as e:  # noqa: BLE001
                error = f"Parâmetros JSON inválidos: {e}"
                qr.status = "error"
                qr.error = error
                _audit("bi.query.failed", {"source_id": src.id, "query_run_id": qr.id, "error": error})
                elapsed_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
                qr.duration_ms = elapsed_ms
                db.session.commit()
                return render_template(
                    "portal/sql_editor.html",
                    tenant=g.tenant,
                    sources=sources,
                    result=None,
                    error=error,
                    elapsed_ms=elapsed_ms,
                )

        # Never let the client spoof tenant_id.
        user_params["tenant_id"] = g.tenant.id

        try:
            result = execute_sql(src, sql_text, params=user_params)
            qr.status = "success"
            qr.rows = len(result.get("rows", []))
            _audit("bi.query.executed", {"source_id": src.id, "query_run_id": qr.id, "ad_hoc": True})
        except QueryExecutionError as e:
            error = str(e)
            qr.status = "error"
            qr.error = error
            _audit("bi.query.failed", {"source_id": src.id, "query_run_id": qr.id, "error": error})
        finally:
            elapsed_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
            qr.duration_ms = elapsed_ms
            db.session.commit()

    return render_template(
        "portal/sql_editor.html",
        tenant=g.tenant,
        sources=sources,
        result=result,
        error=error,
        elapsed_ms=elapsed_ms,
    )


# -----------------------------
# Excel AI (NLQ -> SQL -> XLSX)
# -----------------------------


@bp.route("/excel", methods=["GET"])
@login_required
@require_roles("tenant_admin", "creator")
def excel_ai():
    _require_tenant()
    sources = DataSource.query.filter_by(tenant_id=g.tenant.id).order_by(DataSource.name.asc()).all()
    folders = FileFolder.query.filter_by(tenant_id=g.tenant.id).order_by(FileFolder.name.asc()).all()
    return render_template(
        "portal/excel_ai.html",
        tenant=g.tenant,
        sources=sources,
        folders=folders,
    )
# -----------------------------
# Questions
# -----------------------------


@bp.route("/questions")
@login_required
def questions_list():
    _require_tenant()
    qs = Question.query.filter_by(tenant_id=g.tenant.id).order_by(Question.updated_at.desc()).all()
    return render_template("portal/questions_list.html", tenant=g.tenant, questions=qs)


@bp.route("/questions/new", methods=["GET", "POST"])
@login_required
@require_roles("tenant_admin", "creator")
def questions_new():
    _require_tenant()
    sources = DataSource.query.filter_by(tenant_id=g.tenant.id).order_by(DataSource.name.asc()).all()
    if request.method == "POST":
        if not _bi_quota_check(1):
            return render_template("portal/questions_new.html", tenant=g.tenant, sources=sources)

        name = request.form.get("name", "").strip()
        source_id = int(request.form.get("source_id") or 0)
        sql_text = request.form.get("sql_text", "")
        if not name or not source_id or not sql_text.strip():
            flash(tr("Preencha nome, fonte e SQL.", getattr(g, "lang", None)), "error")
            return render_template("portal/questions_new.html", tenant=g.tenant, sources=sources)
        src = DataSource.query.filter_by(id=source_id, tenant_id=g.tenant.id).first()
        if not src:
            flash(tr("Fonte inválida.", getattr(g, "lang", None)), "error")
            return render_template("portal/questions_new.html", tenant=g.tenant, sources=sources)

        q = Question(
            tenant_id=g.tenant.id,
            source_id=src.id,
            name=name,
            sql_text=sql_text,
            params_schema_json={},
            viz_config_json={},
            acl_json={},
        )
        db.session.add(q)
        db.session.flush()
        _bi_quota_consume(1)
        _audit("bi.question.created", {"id": q.id, "name": q.name, "source_id": src.id})
        db.session.commit()
        flash(tr("Pergunta criada.", getattr(g, "lang", None)), "success")
        return redirect(url_for("portal.questions_view", question_id=q.id))

    return render_template("portal/questions_new.html", tenant=g.tenant, sources=sources)


@bp.route("/api/questions/preview", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def api_questions_preview():
    _require_tenant()
    payload = request.get_json(silent=True) or {}

    try:
        source_id = int(payload.get("source_id") or 0)
    except Exception:
        source_id = 0
    sql_text = str(payload.get("sql_text") or "").strip()
    params_payload = payload.get("params") if isinstance(payload.get("params"), dict) else {}

    if not source_id:
        return jsonify({"error": tr("Selecione uma fonte.", getattr(g, "lang", None))}), 400
    if not sql_text:
        return jsonify({"error": tr("Informe um SQL para pré-visualizar.", getattr(g, "lang", None))}), 400

    src = DataSource.query.filter_by(id=source_id, tenant_id=g.tenant.id).first()
    if not src:
        return jsonify({"error": tr("Fonte inválida.", getattr(g, "lang", None))}), 404

    user_params: dict = {}
    user_params.update(params_payload)
    user_params["tenant_id"] = g.tenant.id

    try:
        res = execute_sql(src, sql_text, params=user_params, row_limit=200)
    except QueryExecutionError as e:
        return jsonify({"error": str(e)}), 400

    rows = res.get("rows") or []
    if len(rows) > 200:
        rows = rows[:200]

    return jsonify({
        "ok": True,
        "result": {
            "columns": res.get("columns") or [],
            "rows": rows,
            "row_count": len(rows),
        },
    })


@bp.route("/questions/<int:question_id>")
@login_required
def questions_view(question_id: int):
    _require_tenant()
    q = Question.query.filter_by(id=question_id, tenant_id=g.tenant.id).first_or_404()
    src = DataSource.query.filter_by(id=q.source_id, tenant_id=g.tenant.id).first_or_404()
    _audit("bi.question.viewed", {"id": q.id})
    db.session.commit()
    return render_template("portal/questions_view.html", tenant=g.tenant, question=q, source=src)


@bp.route("/questions/<int:question_id>/viz", methods=["GET", "POST"])
@login_required
@require_roles("tenant_admin", "creator")
def questions_viz(question_id: int):
    """Configure question visualization (charts/pivot/gauge)."""

    _require_tenant()
    q = Question.query.filter_by(id=question_id, tenant_id=g.tenant.id).first_or_404()
    src = DataSource.query.filter_by(id=q.source_id, tenant_id=g.tenant.id).first_or_404()

    if request.method == "POST":
        raw = request.form.get("viz_config_json", "{}")
        try:
            cfg = json.loads(raw) if raw else {}
        except Exception:
            cfg = {}
            flash(tr("Configuração inválida.", getattr(g, "lang", None)), "error")
            return redirect(url_for("portal.questions_viz", question_id=q.id))

        if not isinstance(cfg, dict):
            cfg = {}

        q.viz_config_json = cfg
        _audit("bi.question.viz.updated", {"id": q.id})
        db.session.commit()
        flash(tr("Visualização salva.", getattr(g, "lang", None)), "success")
        return redirect(url_for("portal.questions_view", question_id=q.id))

    # GET: run once to preview
    try:
        res = execute_sql(src, q.sql_text, params={"tenant_id": g.tenant.id})
    except QueryExecutionError as e:
        res = {"columns": [], "rows": [], "error": str(e)}

    # keep preview light
    if isinstance(res.get("rows"), list) and len(res["rows"]) > 1000:
        res["rows"] = res["rows"][:1000]

    return render_template(
        "portal/questions_viz.html",
        tenant=g.tenant,
        question=q,
        source=src,
        result=res,
        viz_config=q.viz_config_json or {},
    )


@bp.route("/questions/<int:question_id>/run", methods=["GET", "POST"])
@login_required
def questions_run(question_id: int):
    _require_tenant()
    q = Question.query.filter_by(id=question_id, tenant_id=g.tenant.id).first_or_404()
    src = DataSource.query.filter_by(id=q.source_id, tenant_id=g.tenant.id).first_or_404()

    if request.method == "GET":
        return render_template(
            "portal/questions_run.html",
            tenant=g.tenant,
            question=q,
            source=src,
            result=None,
            error=None,
            elapsed_ms=None,
            viz_config=q.viz_config_json or {},
            sql_text=q.sql_text,
            params_json="",
        )

    # Allow editing the SQL at runtime (does not overwrite the saved Question unless explicitly saved elsewhere)
    sql_text = (request.form.get("sql_text") or q.sql_text or "").strip()
    params_text = (request.form.get("params_json") or "").strip()

    started = datetime.utcnow()
    qr = QueryRun(tenant_id=g.tenant.id, question_id=q.id, user_id=current_user.id, status="running")
    db.session.add(qr)
    db.session.flush()

    result = None
    error = None
    elapsed_ms = None
    # Parse user parameters (JSON) and enforce tenant_id server-side.
    user_params: dict = {}
    if params_text:
        try:
            maybe = json.loads(params_text)
            if isinstance(maybe, dict):
                user_params = maybe
            else:
                raise ValueError("params must be object")
        except Exception as e:  # noqa: BLE001
            error = f"Parâmetros JSON inválidos: {e}"
            qr.status = "error"
            qr.error = error
            _audit("bi.question.failed", {"id": q.id, "query_run_id": qr.id, "error": error})
            elapsed_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
            qr.duration_ms = elapsed_ms
            db.session.commit()
            return render_template(
                "portal/questions_run.html",
                tenant=g.tenant,
                question=q,
                source=src,
                result=None,
                error=error,
                elapsed_ms=elapsed_ms,
                viz_config=q.viz_config_json or {},
            )

    user_params["tenant_id"] = g.tenant.id

    try:
        result = execute_sql(src, sql_text, params=user_params)
        qr.status = "success"
        qr.rows = len(result.get("rows", []))
        _audit("bi.question.executed", {"id": q.id, "query_run_id": qr.id})
    except QueryExecutionError as e:
        error = str(e)
        qr.status = "error"
        qr.error = error
        _audit("bi.question.failed", {"id": q.id, "query_run_id": qr.id, "error": error})
    finally:
        elapsed_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
        qr.duration_ms = elapsed_ms
        db.session.commit()

    return render_template(
        "portal/questions_run.html",
        tenant=g.tenant,
        question=q,
        source=src,
        result=result,
        error=error,
        elapsed_ms=elapsed_ms,
        viz_config=q.viz_config_json or {},
        sql_text=sql_text,
        params_json=params_text,
    )


@bp.route("/questions/<int:question_id>/delete", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def questions_delete(question_id: int):
    _require_tenant()
    q = Question.query.filter_by(id=question_id, tenant_id=g.tenant.id).first_or_404()
    _audit("bi.question.deleted", {"id": q.id, "name": q.name})
    db.session.delete(q)
    db.session.commit()
    flash(tr("Pergunta removida.", getattr(g, "lang", None)), "success")
    return redirect(url_for("portal.questions_list"))


# -----------------------------
# Dashboards
# -----------------------------


@bp.route("/dashboards")
@login_required
def dashboards_list():
    _require_tenant()
    ds = Dashboard.query.filter_by(tenant_id=g.tenant.id).order_by(Dashboard.updated_at.desc()).all()
    return render_template("portal/dashboards_list.html", tenant=g.tenant, dashboards=ds)


# -----------------------------
# Reports (Crystal-like builder)
# -----------------------------


@bp.route("/reports")
@login_required
def reports_list():
    _require_tenant()
    reps = Report.query.filter_by(tenant_id=g.tenant.id).order_by(Report.updated_at.desc()).all()
    return render_template("portal/reports_list.html", tenant=g.tenant, reports=reps)


@bp.route("/reports/new", methods=["GET", "POST"])
@login_required
@require_roles("tenant_admin", "creator")
def reports_new():
    _require_tenant()
    sources = DataSource.query.filter_by(tenant_id=g.tenant.id).order_by(DataSource.name.asc()).all()
    if request.method == "POST":
        if not _bi_quota_check(1):
            return render_template("portal/reports_new.html", tenant=g.tenant, sources=sources)

        name = (request.form.get("name") or "").strip()
        source_id = int(request.form.get("source_id") or 0)
        if not name or not source_id:
            flash(tr("Informe nome e fonte.", getattr(g, "lang", None)), "error")
            return render_template("portal/reports_new.html", tenant=g.tenant, sources=sources)
        src = DataSource.query.filter_by(id=source_id, tenant_id=g.tenant.id).first()
        if not src:
            flash(tr("Fonte inválida.", getattr(g, "lang", None)), "error")
            return render_template("portal/reports_new.html", tenant=g.tenant, sources=sources)

        rep = Report(
            tenant_id=g.tenant.id,
            source_id=src.id,
            name=name,
            layout_json={
                "version": 4,
                "page": {"size": "A4", "orientation": "portrait"},
                "settings": {
                    "page_number": True,
                    "page_number_label": "Page {page} / {pages}",
                },
                "bands": {
                    "report_header": [],
                    "page_header": [],
                    "detail": [],
                    "page_footer": [],
                    "report_footer": [],
                },
                # backward compat (older viewers)
                "sections": {"header": [], "body": [], "footer": []},
            },
        )
        db.session.add(rep)
        _bi_quota_consume(1)
        db.session.commit()
        flash(tr("Relatório criado.", getattr(g, "lang", None)), "success")
        return redirect(url_for("portal.report_builder", report_id=rep.id))

    return render_template("portal/reports_new.html", tenant=g.tenant, sources=sources)


@bp.route("/reports/<int:report_id>/builder", methods=["GET"])
@login_required
@require_roles("tenant_admin", "creator")
def report_builder(report_id: int):
    _require_tenant()
    rep = Report.query.filter_by(id=report_id, tenant_id=g.tenant.id).first_or_404()
    src = DataSource.query.filter_by(id=rep.source_id, tenant_id=g.tenant.id).first_or_404()
    questions = Question.query.filter_by(tenant_id=g.tenant.id, source_id=src.id).order_by(Question.name.asc()).all()
    return render_template(
        "portal/report_builder.html",
        tenant=g.tenant,
        report=rep,
        source=src,
        questions=questions,
    )


@bp.route("/reports/<int:report_id>/view", methods=["GET"])
@login_required
def report_view(report_id: int):
    """Read-only viewer for Report Builder layouts."""
    _require_tenant()
    rep = Report.query.filter_by(id=report_id, tenant_id=g.tenant.id).first_or_404()
    src = DataSource.query.filter_by(id=rep.source_id, tenant_id=g.tenant.id).first_or_404()
    questions = Question.query.filter_by(tenant_id=g.tenant.id, source_id=src.id).order_by(Question.name.asc()).all()
    q_by_id = {q.id: q for q in questions}

    layout = rep.layout_json or {}
    bands = (layout.get("bands") or {})
    if not bands:
        # Backward compat: map header/body/footer -> page_header/detail/page_footer
        secs = (layout.get("sections") or {})
        bands = {
            "report_header": [],
            "page_header": secs.get("header") or [],
            "detail": secs.get("body") or [],
            "page_footer": secs.get("footer") or [],
            "report_footer": [],
        }

    from datetime import datetime, date
    import re

    def _fmt_date(dt: object, fmt: str) -> str:
        fmt = (fmt or "dd/MM/yyyy").strip()
        mapping = {
            "yyyy": "%Y",
            "MM": "%m",
            "dd": "%d",
            "HH": "%H",
            "mm": "%M",
            "ss": "%S",
        }
        py = fmt
        for k, v in mapping.items():
            py = py.replace(k, v)
        try:
            if isinstance(dt, datetime):
                return dt.strftime(py)
            if isinstance(dt, date):
                return dt.strftime(py)
        except Exception:
            pass
        return str(dt)

    def _fmt_number(v: object, decimals: int | None) -> str:
        if decimals is None:
            return str(v)
        try:
            if v is None:
                return ""
            if isinstance(v, (int, float)):
                return f"{float(v):.{decimals}f}"
            # try numeric strings
            if isinstance(v, str) and v.strip() and v.strip().replace('.', '', 1).replace('-', '', 1).isdigit():
                return f"{float(v):.{decimals}f}"
        except Exception:
            pass
        return str(v)

    def _format_cell(v: object, decimals: int | None, date_fmt: str | None) -> str:
        if v is None:
            return ""
        if isinstance(v, (datetime, date)):
            return _fmt_date(v, date_fmt or "dd/MM/yyyy")
        if decimals is not None and isinstance(v, (int, float, str)):
            return _fmt_number(v, decimals)
        return str(v)

    def _to_float(v: object) -> float | None:
        try:
            if v is None:
                return None
            if isinstance(v, bool):
                return float(int(v))
            if isinstance(v, (int, float)):
                return float(v)
            s = str(v).strip()
            if not s:
                return None
            s = s.replace(" ", "")
            if "," in s and "." not in s:
                s = s.replace(",", ".")
            elif "," in s and "." in s:
                s = s.replace(",", "")
            return float(s)
        except Exception:
            return None

    def _group_metric(rows: list, cols: list, mode: str, sum_field: str) -> float | int | None:
        m = str(mode or "").strip().lower()
        if m == "count":
            return len(rows or [])
        if m != "sum":
            return None
        idx = _find_col_index(cols, sum_field)
        if idx < 0:
            return None
        total = 0.0
        used = False
        for r in rows or []:
            if not isinstance(r, (list, tuple)) or idx >= len(r):
                continue
            num = _to_float(r[idx])
            if num is None:
                continue
            total += num
            used = True
        if not used:
            return None
        return total

    def _format_group_metric(v: float | int | None, mode: str, decimals: int | None, date_fmt: str | None) -> str:
        if v is None:
            return ""
        m = str(mode or "").strip().lower()
        if m == "count":
            try:
                return str(int(v))
            except Exception:
                return str(v)
        return _format_cell(v, decimals, date_fmt)

    def _find_col_index(cols: list, name: str) -> int:
        needle = str(name or "").strip()
        if not needle:
            return -1
        for i, c in enumerate(cols or []):
            if str(c) == needle:
                return i
        low = needle.lower()
        for i, c in enumerate(cols or []):
            if str(c).lower() == low:
                return i
        return -1

    def _sort_rows(rows: list, idx: int, desc: bool) -> list:
        if idx < 0:
            return rows

        def key_fn(r):
            try:
                v = r[idx] if isinstance(r, (list, tuple)) and idx < len(r) else None
            except Exception:
                v = None
            if v is None:
                return (1, "")
            if isinstance(v, (int, float)):
                return (0, float(v))
            s = str(v)
            try:
                return (0, float(s))
            except Exception:
                return (0, s.lower())

        try:
            return sorted(rows, key=key_fn, reverse=desc)
        except Exception:
            return rows

    def _apply_filter_rows(rows: list, cols: list, field: str, op: str, value: str) -> list:
        idx = _find_col_index(cols, field)
        if idx < 0:
            return rows
        oper = str(op or "").strip().lower()
        needle = str(value or "")
        if oper not in ("eq", "contains", "gt", "gte", "lt", "lte"):
            return rows

        def _num(v: object) -> float | None:
            return _to_float(v)

        out = []
        for r in rows or []:
            rv = r[idx] if isinstance(r, (list, tuple)) and idx < len(r) else None
            ok = False
            if oper == "eq":
                ok = str(rv or "").strip().lower() == needle.strip().lower()
            elif oper == "contains":
                ok = needle.strip().lower() in str(rv or "").lower()
            else:
                a = _num(rv)
                b = _num(needle)
                if a is None or b is None:
                    ok = False
                elif oper == "gt":
                    ok = a > b
                elif oper == "gte":
                    ok = a >= b
                elif oper == "lt":
                    ok = a < b
                elif oper == "lte":
                    ok = a <= b
            if ok:
                out.append(r)
        return out

    def _apply_bound_format(v: object, fmt: str) -> str:
        f = str(fmt or "").strip()
        if not f:
            return _format_cell(v, None, None)
        try:
            if f.startswith(".") and f.endswith("f"):
                return format(float(v), f)
        except Exception:
            pass
        if isinstance(v, (datetime, date)):
            return _fmt_date(v, f)
        return str(v if v is not None else "")

    def _safe_ident(name: str) -> str:
        import re
        raw = str(name or "").strip()
        if not raw:
            raise ValueError("identificador vazio")
        parts = raw.split(".")
        for p in parts:
            if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", p):
                raise ValueError("identificador inválido")
        return ".".join(parts)

    def _question_field_value(qid: int, field: str) -> str:
        q = q_by_id.get(int(qid or 0))
        if not q:
            raise ValueError("Pergunta não encontrada")
        res = execute_sql(src, q.sql_text or "", {"tenant_id": g.tenant.id}, row_limit=1)
        cols = res.get("columns") or []
        rows = res.get("rows") or []
        if not rows:
            return ""
        idx = -1
        for i, c in enumerate(cols):
            if str(c) == str(field):
                idx = i
                break
        if idx < 0:
            for i, c in enumerate(cols):
                if str(c).lower() == str(field).lower():
                    idx = i
                    break
        if idx < 0:
            raise ValueError("Campo não encontrado na pergunta")
        row0 = rows[0] if isinstance(rows[0], (list, tuple)) else []
        return _format_cell(row0[idx] if idx < len(row0) else "", None, None)

    def _table_field_value(table_name: str, field_name: str) -> str:
        tbl = _safe_ident(table_name)
        fld = _safe_ident(field_name)
        sql = f"SELECT {fld} FROM {tbl} LIMIT 1"
        res = execute_sql(src, sql, {"tenant_id": g.tenant.id}, row_limit=1)
        rows = res.get("rows") or []
        if not rows:
            return ""
        row0 = rows[0] if isinstance(rows[0], (list, tuple)) else []
        return _format_cell(row0[0] if row0 else "", None, None)

    _q_cache: dict[int, tuple[list, list]] = {}
    _tbl_cache: dict[str, tuple[list, list]] = {}

    def _question_result(qid: int) -> tuple[list, list]:
        q = q_by_id.get(int(qid or 0))
        if not q:
            return [], []
        qqid = int(q.id)
        if qqid in _q_cache:
            return _q_cache[qqid]
        try:
            res = execute_sql(src, q.sql_text or "", {"tenant_id": g.tenant.id}, row_limit=1000)
            cols = res.get("columns") or []
            rows = res.get("rows") or []
            _q_cache[qqid] = (cols, rows)
            return cols, rows
        except Exception:
            return [], []

    def _table_result(table_name: str) -> tuple[list, list]:
        t = str(table_name or "").strip()
        if not t:
            return [], []
        if t in _tbl_cache:
            return _tbl_cache[t]
        try:
            sql = f"SELECT * FROM {_safe_ident(t)} LIMIT 1000"
            res = execute_sql(src, sql, {"tenant_id": g.tenant.id}, row_limit=1000)
            cols = res.get("columns") or []
            rows = res.get("rows") or []
            _tbl_cache[t] = (cols, rows)
            return cols, rows
        except Exception:
            return [], []

    _ph_re = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")

    def _resolve_ref(expr: str) -> tuple[list, list, str | None]:
        s = str(expr or "").strip()
        m = re.match(r"^question[:.]\s*(\d+)(?:\.([A-Za-z_][A-Za-z0-9_]*))?$", s, flags=re.I)
        if m:
            qid = int(m.group(1))
            fld = m.group(2)
            cols, rows = _question_result(qid)
            return cols, rows, fld
        m = re.match(r"^table[:.]\s*([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?)(?:\.([A-Za-z_][A-Za-z0-9_]*))?$", s, flags=re.I)
        if m:
            tbl = m.group(1)
            fld = m.group(2)
            cols, rows = _table_result(tbl)
            return cols, rows, fld
        return [], [], None

    def _resolve_placeholder_text(text: str) -> str:
        raw = str(text or "")

        def repl(m):
            key = str(m.group(1) or "").strip()
            low = key.lower()
            if low == "date":
                return _fmt_date(datetime.now(), "dd/MM/yyyy")
            if low == "datetime":
                return _fmt_date(datetime.now(), "dd/MM/yyyy HH:mm")

            fm = re.match(r"^(sum|avg|count)\((.+)\)$", key, flags=re.I)
            if fm:
                fn = fm.group(1).lower()
                ref = fm.group(2).strip()
                cols, rows, fld = _resolve_ref(ref)
                if not rows:
                    return ""
                if fn == "count":
                    return str(len(rows))
                idx = _find_col_index(cols, fld or "")
                if idx < 0:
                    return ""
                nums = []
                for r in rows:
                    if not isinstance(r, (list, tuple)) or idx >= len(r):
                        continue
                    n = _to_float(r[idx])
                    if n is not None:
                        nums.append(n)
                if not nums:
                    return ""
                if fn == "sum":
                    return _format_cell(sum(nums), 2, None)
                if fn == "avg":
                    return _format_cell(sum(nums) / len(nums), 2, None)
                return ""

            cols, rows, fld = _resolve_ref(key)
            if rows and fld:
                idx = _find_col_index(cols, fld)
                if idx >= 0:
                    r0 = rows[0] if isinstance(rows[0], (list, tuple)) else []
                    if isinstance(r0, (list, tuple)) and idx < len(r0):
                        return _format_cell(r0[idx], None, None)
            return m.group(0)

        return _ph_re.sub(repl, raw)

    # Build a render-friendly bands structure and prefetch tables per block
    render_bands: dict[str, list[dict]] = {}
    blocks_data: dict[str, dict] = {}

    order = [
        "report_header",
        "page_header",
        "detail",
        "page_footer",
        "report_footer",
    ]

    for band_name in order:
        out_list: list[dict] = []
        source_blocks = bands.get(band_name) or []
        idx = 0
        while idx < len(source_blocks):
            b = source_blocks[idx]
            bb = dict(b) if isinstance(b, dict) else {}
            btype = (bb.get("type") or "").lower()
            key = f"{band_name}:{idx}"
            bb["_key"] = key

            if btype == "data_field" and band_name == "detail":
                run: list[dict] = []
                run_bind_key = ""
                j = idx
                while j < len(source_blocks):
                    cb = dict(source_blocks[j]) if isinstance(source_blocks[j], dict) else {}
                    ctype = (cb.get("type") or "").lower()
                    if ctype != "data_field":
                        break
                    ccfg = cb.get("config") if isinstance(cb.get("config"), dict) else {}
                    cbind = (ccfg.get("binding") or {}) if isinstance(ccfg.get("binding"), dict) else {}
                    csrc = (cbind.get("source") or "").strip().lower()
                    cfield = str(cbind.get("field") or "").strip()
                    if csrc not in ("question", "table") or not cfield:
                        break
                    cbind_key = f"{csrc}:{cbind.get('question_id') if csrc == 'question' else cbind.get('table')}"
                    if not run_bind_key:
                        run_bind_key = cbind_key
                    if cbind_key != run_bind_key:
                        break
                    run.append(cb)
                    j += 1

                if len(run) >= 2:
                    first_cfg = run[0].get("config") if isinstance(run[0].get("config"), dict) else {}
                    first_bind = (first_cfg.get("binding") or {}) if isinstance(first_cfg.get("binding"), dict) else {}
                    source_kind = (first_bind.get("source") or "").strip().lower()

                    try:
                        dataset_rows = []
                        table_style_cfg = (first_cfg.get("table") if isinstance(first_cfg.get("table"), dict) else {})
                        table_style_cfg = {
                            "theme": str(table_style_cfg.get("theme") or "crystal").strip().lower() or "crystal",
                            "zebra": bool(table_style_cfg.get("zebra")),
                            "repeat_header": bool(table_style_cfg.get("repeat_header", True)),
                            "header_bg": str(table_style_cfg.get("header_bg") or "").strip(),
                        }
                        if source_kind == "question":
                            qid = int(first_bind.get("question_id") or 0)
                            q = q_by_id.get(qid)
                            if not q:
                                raise ValueError("Pergunta não encontrada")
                            res = execute_sql(src, q.sql_text or "", {"tenant_id": g.tenant.id}, row_limit=100)
                            cols_all = res.get("columns") or []
                            rows_all = res.get("rows") or []
                            col_map = {str(c): i for i, c in enumerate(cols_all)}
                            for rr in rows_all:
                                row_out: list[str] = []
                                for rb in run:
                                    rcfg = rb.get("config") if isinstance(rb.get("config"), dict) else {}
                                    rbind = (rcfg.get("binding") or {}) if isinstance(rcfg.get("binding"), dict) else {}
                                    field = str(rbind.get("field") or "").strip()
                                    fmt = str(rcfg.get("format") or "").strip()
                                    empty_text = str(rcfg.get("empty_text") or "")
                                    ridx = col_map.get(field)
                                    if ridx is None:
                                        ridx = col_map.get(field.lower())
                                    val = rr[ridx] if isinstance(rr, (list, tuple)) and ridx is not None and ridx < len(rr) else None
                                    sval = _apply_bound_format(val, fmt)
                                    if sval in ("", None):
                                        sval = empty_text
                                    row_out.append(str(sval or ""))
                                dataset_rows.append(row_out)

                        elif source_kind == "table":
                            table_name = _safe_ident(str(first_bind.get("table") or "").strip())
                            fields = []
                            for rb in run:
                                rcfg = rb.get("config") if isinstance(rb.get("config"), dict) else {}
                                rbind = (rcfg.get("binding") or {}) if isinstance(rcfg.get("binding"), dict) else {}
                                fields.append(_safe_ident(str(rbind.get("field") or "").strip()))
                            sql = f"SELECT {', '.join(fields)} FROM {table_name} LIMIT 100"
                            res = execute_sql(src, sql, {"tenant_id": g.tenant.id}, row_limit=100)
                            rows_all = res.get("rows") or []
                            for rr in rows_all:
                                row_out: list[str] = []
                                for cidx, rb in enumerate(run):
                                    rcfg = rb.get("config") if isinstance(rb.get("config"), dict) else {}
                                    fmt = str(rcfg.get("format") or "").strip()
                                    empty_text = str(rcfg.get("empty_text") or "")
                                    val = rr[cidx] if isinstance(rr, (list, tuple)) and cidx < len(rr) else None
                                    sval = _apply_bound_format(val, fmt)
                                    if sval in ("", None):
                                        sval = empty_text
                                    row_out.append(str(sval or ""))
                                dataset_rows.append(row_out)

                        headers = []
                        column_styles = []
                        group_idx = -1
                        group_label_tpl = 'Groupe: {group}'
                        group_count = False
                        for ridx, rb in enumerate(run):
                            rcfg = rb.get("config") if isinstance(rb.get("config"), dict) else {}
                            if bool(rcfg.get("group_key")) and group_idx < 0:
                                group_idx = ridx
                                group_label_tpl = str(rcfg.get("group_label") or 'Groupe: {group}')
                                group_count = True
                        for rb in run:
                            rcfg = rb.get("config") if isinstance(rb.get("config"), dict) else {}
                            rbind = (rcfg.get("binding") or {}) if isinstance(rcfg.get("binding"), dict) else {}
                            h = str(rb.get("title") or "").strip() or str(rbind.get("field") or "")
                            headers.append(h)
                            rst = rb.get("style") if isinstance(rb.get("style"), dict) else {}
                            column_styles.append({
                                "color": str(rst.get("color") or "").strip(),
                                "background": str(rst.get("background") or "").strip(),
                                "align": str(rst.get("align") or "").strip().lower(),
                                "font_size": str(rst.get("font_size") or "").strip(),
                                "bold": bool(rst.get("bold")),
                                "italic": bool(rst.get("italic")),
                                "underline": bool(rst.get("underline")),
                            })

                        rowset_title = str(bb.get("title") or "").strip()
                        if headers and rowset_title and rowset_title.strip().lower() == str(headers[0]).strip().lower():
                            rowset_title = ""

                        rowset_block = {
                            "type": "data_rowset",
                            "title": rowset_title,
                            "config": {
                                "table": table_style_cfg,
                            },
                            "_key": key,
                        }
                        out_list.append(rowset_block)
                        blocks_data[key] = {
                            "columns": headers,
                            "rows": dataset_rows,
                            "column_styles": column_styles,
                        }
                        if group_idx >= 0:
                            groups_map: dict[str, list[list[str]]] = {}
                            for rr in dataset_rows:
                                gval = rr[group_idx] if group_idx < len(rr) else ''
                                groups_map.setdefault(str(gval), []).append(rr)
                            groups = []
                            for gname, grows in groups_map.items():
                                groups.append({
                                    "name": gname,
                                    "label": group_label_tpl.replace('{group}', str(gname)),
                                    "count": len(grows),
                                    "rows": grows,
                                })
                            blocks_data[key]["groups"] = groups
                            blocks_data[key]["group_count"] = group_count
                        idx = j
                        continue
                    except Exception as e:
                        blocks_data[key] = {"columns": [], "rows": [], "error": str(e)}
                        out_list.append(bb)
                        idx += 1
                        continue

            if btype == "question":
                qid = int(bb.get("question_id") or 0)
                q = q_by_id.get(qid)
                cfg = bb.get("config") if isinstance(bb.get("config"), dict) else {}
                tcfg = (cfg.get("table") or {}) if isinstance(cfg.get("table"), dict) else {}
                decimals = None
                try:
                    if tcfg.get("decimals") is not None and str(tcfg.get("decimals")).strip() != "":
                        decimals = int(tcfg.get("decimals"))
                except Exception:
                    decimals = None
                date_fmt = tcfg.get("date_format") or None

                if not q:
                    blocks_data[key] = {"columns": [], "rows": [], "error": "Pergunta não encontrada"}
                else:
                    try:
                        res = execute_sql(src, q.sql_text or "", {"tenant_id": g.tenant.id}, row_limit=25)
                        cols = res.get("columns") or []
                        rows = res.get("rows") or []

                        filter_field = str(tcfg.get("filter_field") or "").strip()
                        filter_op = str(tcfg.get("filter_op") or "").strip().lower()
                        filter_value = str(tcfg.get("filter_value") or "").strip()
                        if filter_field and filter_op:
                            rows = _apply_filter_rows(rows, cols, filter_field, filter_op, filter_value)

                        sort_by = str(tcfg.get("sort_by") or "").strip()
                        sort_dir = str(tcfg.get("sort_dir") or "asc").strip().lower()
                        sort_idx = _find_col_index(cols, sort_by)
                        rows = _sort_rows(rows, sort_idx, sort_dir == "desc")

                        group_by = str(tcfg.get("group_by") or "").strip()
                        group_label = str(tcfg.get("group_label") or "{group}")
                        group_count = bool(tcfg.get("group_count"))
                        group_subtotal_mode = str(tcfg.get("group_subtotal_mode") or "").strip().lower()
                        if group_subtotal_mode not in ("count", "sum"):
                            group_subtotal_mode = ""
                        group_subtotal_field = str(tcfg.get("group_subtotal_field") or "").strip()
                        group_subtotal_label = str(tcfg.get("group_subtotal_label") or "").strip() or "Sous-total"
                        grand_total = bool(tcfg.get("grand_total"))
                        grand_total_label = str(tcfg.get("grand_total_label") or "").strip() or "Grand total"
                        footer_item_count = bool(tcfg.get("footer_item_count"))
                        footer_item_count_label = str(tcfg.get("footer_item_count_label") or "").strip() or "Items"
                        group_idx = _find_col_index(cols, group_by)

                        # format cells
                        rows_fmt = [[_format_cell(c, decimals, date_fmt) for c in r] for r in rows]

                        payload = {"columns": cols, "rows": rows_fmt}
                        if footer_item_count:
                            payload["footer_item_count"] = f"{footer_item_count_label}: {len(rows)}"
                        if group_idx >= 0:
                            groups_map: dict[str, dict[str, list]] = {}
                            for rr, rf in zip(rows, rows_fmt):
                                gv = rr[group_idx] if isinstance(rr, (list, tuple)) and group_idx < len(rr) else ""
                                gs = _format_cell(gv, None, date_fmt)
                                bucket = groups_map.setdefault(gs, {"raw": [], "fmt": []})
                                bucket["raw"].append(rr)
                                bucket["fmt"].append(rf)

                            groups = []
                            for gname, group_data in groups_map.items():
                                grows_raw = group_data.get("raw") or []
                                grows_fmt = group_data.get("fmt") or []
                                label = group_label.replace("{group}", str(gname or ""))
                                grp_payload = {
                                    "name": gname,
                                    "label": label,
                                    "count": len(grows_fmt),
                                    "rows": grows_fmt,
                                }
                                if group_subtotal_mode:
                                    subtotal_value = _group_metric(grows_raw, cols, group_subtotal_mode, group_subtotal_field)
                                    subtotal_text = _format_group_metric(subtotal_value, group_subtotal_mode, decimals, date_fmt)
                                    if subtotal_text != "":
                                        grp_payload["subtotal"] = f"{group_subtotal_label}: {subtotal_text}"
                                groups.append(grp_payload)
                            payload["groups"] = groups
                            payload["group_count"] = group_count
                        if grand_total and group_subtotal_mode:
                            grand_value = _group_metric(rows, cols, group_subtotal_mode, group_subtotal_field)
                            grand_text = _format_group_metric(grand_value, group_subtotal_mode, decimals, date_fmt)
                            if grand_text != "":
                                payload["grand_total"] = f"{grand_total_label}: {grand_text}"
                        blocks_data[key] = payload
                    except Exception as e:
                        blocks_data[key] = {"columns": [], "rows": [], "error": str(e)}

            elif btype == "field":
                cfg = bb.get("config") if isinstance(bb.get("config"), dict) else {}
                kind = (cfg.get("kind") or "date").lower()
                fmt = cfg.get("format") or ("dd/MM/yyyy HH:mm" if kind == "datetime" else "dd/MM/yyyy")
                now = datetime.now()
                val = _fmt_date(now, fmt)
                bb["value"] = val

            elif btype in ("text", "markdown"):
                raw_content = bb.get("content") if bb.get("content") is not None else bb.get("text")
                if raw_content is not None:
                    resolved = _resolve_placeholder_text(str(raw_content))
                    bb["content"] = resolved
                    bb["text"] = resolved
                if bb.get("title"):
                    bb["title"] = _resolve_placeholder_text(str(bb.get("title") or ""))

            elif btype == "data_field":
                cfg = bb.get("config") if isinstance(bb.get("config"), dict) else {}
                bind = (cfg.get("binding") or {}) if isinstance(cfg.get("binding"), dict) else {}
                source_kind = (bind.get("source") or "").strip().lower()
                try:
                    if source_kind == "question":
                        qid = int(bind.get("question_id") or 0)
                        field = str(bind.get("field") or "").strip()
                        value = _question_field_value(qid, field)
                    elif source_kind == "table":
                        table_name = str(bind.get("table") or "").strip()
                        field = str(bind.get("field") or "").strip()
                        value = _table_field_value(table_name, field)
                    else:
                        value = ""

                    if value in (None, ""):
                        value = str(cfg.get("empty_text") or "")
                    bb["value"] = value
                    blocks_data[key] = {"value": value}
                except Exception as e:
                    blocks_data[key] = {"value": "", "error": str(e)}

            out_list.append(bb)
            idx += 1
        render_bands[band_name] = out_list

    return render_template(
        "portal/report_view.html",
        tenant=g.tenant,
        report=rep,
        source=src,
        questions=q_by_id,
        layout=layout,
        bands=render_bands,
        blocks_data=blocks_data,
    )



@bp.route("/reports/<int:report_id>/pdf", methods=["GET"])
@login_required
def report_pdf(report_id: int):
    """Export a Report Builder layout to PDF."""
    _require_tenant()
    rep = Report.query.filter_by(id=report_id, tenant_id=g.tenant.id).first_or_404()
    src = DataSource.query.filter_by(id=rep.source_id, tenant_id=g.tenant.id).first_or_404()
    questions = Question.query.filter_by(tenant_id=g.tenant.id, source_id=src.id).order_by(Question.name.asc()).all()
    q_by_id = {q.id: q for q in questions}

    pdf = report_to_pdf_bytes(
        title=rep.name or "Report",
        report=rep,
        source=src,
        tenant_id=g.tenant.id,
        questions_by_id=q_by_id,
        lang=getattr(g, "lang", None),
    )
    resp = make_response(pdf)
    resp.headers["Content-Type"] = "application/pdf"
    safe = (rep.name or "report").replace("/", "-")
    resp.headers["Content-Disposition"] = f'attachment; filename="{safe}.pdf"'
    return resp


@bp.route("/api/reports/<int:report_id>", methods=["GET"])
@login_required
def api_report_get(report_id: int):
    _require_tenant()
    rep = Report.query.filter_by(id=report_id, tenant_id=g.tenant.id).first_or_404()
    return jsonify({"id": rep.id, "name": rep.name, "source_id": rep.source_id, "layout": rep.layout_json or {}})


@bp.route("/api/reports/<int:report_id>", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def api_report_save(report_id: int):
    _require_tenant()
    rep = Report.query.filter_by(id=report_id, tenant_id=g.tenant.id).first_or_404()
    payload = request.get_json(silent=True) or {}
    layout = payload.get("layout")
    if not isinstance(layout, dict):
        return jsonify({"error": "layout inválido"}), 400
    # keep it small / safe
    rep.layout_json = layout
    db.session.commit()
    return jsonify({"ok": True})


@bp.route('/users')
@login_required
@require_roles('tenant_admin')
def users_list():
    _require_tenant()
    users = User.query.filter_by(tenant_id=g.tenant.id).order_by(User.email.asc()).all()
    return render_template('portal/users_list.html', tenant=g.tenant, users=users)


@bp.route('/users/new', methods=['GET', 'POST'])
@login_required
@require_roles('tenant_admin')
def users_new():
    _require_tenant()
    roles = Role.query.order_by(Role.code.asc()).all()
    if request.method == 'POST':
        email = request.form.get('email','').strip().lower()
        password = request.form.get('password','').strip()
        role_ids = request.form.getlist('roles') or []
        if not email or not password:
            flash(tr('Email e senha são obrigatórios.', getattr(g, "lang", None)), 'error')
            return render_template('portal/users_new.html', tenant=g.tenant, roles=roles)
        u = User(tenant_id=g.tenant.id, email=email)
        u.set_password(password)
        if role_ids:
            u.roles = Role.query.filter(Role.id.in_(role_ids)).all()
        db.session.add(u)
        db.session.commit()
        flash(tr('Usuário criado.', getattr(g, "lang", None)), 'success')
        return redirect(url_for('portal.users_list'))
    return render_template('portal/users_new.html', tenant=g.tenant, roles=roles)


@bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@require_roles('tenant_admin')
def users_delete(user_id: int):
    _require_tenant()
    u = User.query.filter_by(id=user_id, tenant_id=g.tenant.id).first_or_404()
    db.session.delete(u)
    db.session.commit()
    flash(tr('Usuário removido.', getattr(g, "lang", None)), 'success')
    return redirect(url_for('portal.users_list'))


@bp.route("/dashboards/new", methods=["GET", "POST"])
@login_required
@require_roles("tenant_admin", "creator")
def dashboards_new():
    _require_tenant()
    questions = Question.query.filter_by(tenant_id=g.tenant.id).order_by(Question.name.asc()).all()
    if request.method == "POST":
        if not _bi_quota_check(1):
            return render_template("portal/dashboards_new.html", tenant=g.tenant, questions=questions)

        name = request.form.get("name", "").strip()
        selected = request.form.getlist("question_ids")
        if not name:
            flash(tr("Informe um nome.", getattr(g, "lang", None)), "error")
            return render_template("portal/dashboards_new.html", tenant=g.tenant, questions=questions)

        dash = Dashboard(tenant_id=g.tenant.id, name=name, layout_json={}, filters_json={}, acl_json={})
        db.session.add(dash)
        db.session.flush()

        # Create cards in a simple vertical layout
        y = 0
        for qid_str in selected:
            try:
                qid = int(qid_str)
            except ValueError:
                continue
            q = Question.query.filter_by(id=qid, tenant_id=g.tenant.id).first()
            if not q:
                continue
            card = DashboardCard(
                tenant_id=g.tenant.id,
                dashboard_id=dash.id,
                question_id=q.id,
                viz_config_json={},
                position_json={"x": 0, "y": y, "w": 12, "h": 6},
            )
            y += 6
            db.session.add(card)

        _audit("bi.dashboard.created", {"id": dash.id, "name": dash.name, "cards": len(selected)})
        _bi_quota_consume(1)
        db.session.commit()
        flash(tr("Dashboard criado.", getattr(g, "lang", None)), "success")
        return redirect(url_for("portal.dashboard_view", dashboard_id=dash.id))

    return render_template("portal/dashboards_new.html", tenant=g.tenant, questions=questions)


@bp.route("/dashboards/<int:dashboard_id>")
@login_required
def dashboard_view(dashboard_id: int):
    _require_tenant()

    # IMPORTANT: avoid leaking existence across tenants -> 404 if tenant mismatch
    dash = Dashboard.query.filter_by(id=dashboard_id, tenant_id=g.tenant.id).first_or_404()
    cards = (
        DashboardCard.query.filter_by(dashboard_id=dash.id, tenant_id=g.tenant.id)
        .order_by(DashboardCard.id.asc())
        .all()
    )

    

    # For the dashboard builder (Add card)
    all_questions = (
        Question.query.filter_by(tenant_id=g.tenant.id)
        .order_by(Question.updated_at.desc())
        .all()
    )

    rendered_cards = []
    for c in cards:
        q = Question.query.filter_by(id=c.question_id, tenant_id=g.tenant.id).first()
        if not q:
            continue
        src = DataSource.query.filter_by(id=q.source_id, tenant_id=g.tenant.id).first()
        if not src:
            continue
        try:
            res = execute_sql(src, q.sql_text, params={"tenant_id": g.tenant.id})
        except QueryExecutionError as e:
            res = {"columns": [], "rows": [], "error": str(e)}
        
        # Determine visualization config with intelligent fallback
        viz_cfg = {"type": "table"}
        
        # Use question-level config as base
        if isinstance(getattr(q, "viz_config_json", None), dict) and q.viz_config_json:
            viz_cfg = q.viz_config_json.copy() if isinstance(q.viz_config_json, dict) else {}
        
        # Card-level config overrides, but only if it specifies more than just type
        card_cfg = getattr(c, "viz_config_json", None)
        if isinstance(card_cfg, dict) and card_cfg and len(card_cfg) > 1:
            # Card has meaningful overrides beyond just type
            viz_cfg = card_cfg
        elif isinstance(card_cfg, dict) and card_cfg and card_cfg.get("type") not in [None, "table"]:
            # Card specifies a non-table type, use it but merge with question config
            viz_cfg.update(card_cfg)

        rendered_cards.append({"card": c, "question": q, "result": res, "viz_config": viz_cfg})

    _audit("bi.dashboard.viewed", {"id": dash.id})
    db.session.commit()
    return render_template(
        "portal/dashboard_view.html",
        tenant=g.tenant,
        dashboard=dash,
        cards=rendered_cards,
        all_questions=all_questions,
    )


@bp.route("/dashboards/<int:dashboard_id>/delete", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def dashboards_delete(dashboard_id: int):
    _require_tenant()
    dash = Dashboard.query.filter_by(id=dashboard_id, tenant_id=g.tenant.id).first_or_404()
    _audit("bi.dashboard.deleted", {"id": dash.id, "name": dash.name})
    db.session.delete(dash)
    db.session.commit()
    flash(tr("Dashboard removido.", getattr(g, "lang", None)), "success")
    return redirect(url_for("portal.dashboards_list"))


@bp.route("/dashboards/<int:dashboard_id>/set_primary", methods=["POST"])
@login_required
@require_roles("tenant_admin")
def dashboards_set_primary(dashboard_id: int):
    _require_tenant()
    dash = Dashboard.query.filter_by(id=dashboard_id, tenant_id=g.tenant.id).first_or_404()
    try:
        # clear previous primary
        Dashboard.query.filter_by(tenant_id=g.tenant.id, is_primary=True).update({"is_primary": False})
        dash.is_primary = True
        db.session.commit()
        flash(tr("Dashboard definido como principal.", getattr(g, "lang", None)), "success")
    except Exception:
        db.session.rollback()
        flash(tr("Operação não suportada: execute as migrações do banco para habilitar essa função.", getattr(g, "lang", None)), "error")
    return redirect(url_for("portal.dashboards_list"))




# -----------------------------
# Explore (Superset-like)
# -----------------------------


@bp.route("/explore")
@login_required
def explore():
    _require_tenant()
    qs = Question.query.filter_by(tenant_id=g.tenant.id).order_by(Question.updated_at.desc()).all()
    dashes = Dashboard.query.filter_by(tenant_id=g.tenant.id).order_by(Dashboard.updated_at.desc()).all()
    return render_template("portal/explore.html", tenant=g.tenant, questions=qs, dashboards=dashes)


@bp.route("/api/questions/<int:question_id>/data", methods=["POST"])
@login_required
def api_question_data(question_id: int):
    _require_tenant()
    q = Question.query.filter_by(id=question_id, tenant_id=g.tenant.id).first_or_404()
    src = DataSource.query.filter_by(id=q.source_id, tenant_id=g.tenant.id).first_or_404()
    payload = request.get_json(silent=True) or {}
    params = payload.get("params") or {}
    agg = payload.get("agg")
    if params and not isinstance(params, dict):
        return jsonify({"error": "Parâmetros devem ser um objeto JSON."}), 400
    user_params: dict = {}
    if isinstance(params, dict):
        user_params.update(params)
    user_params["tenant_id"] = g.tenant.id
    try:
        # If aggregation requested, build an aggregated SQL wrapping the original query
        if agg and isinstance(agg, dict):
            dim = agg.get("dim")
            metric = agg.get("metric")
            func = (agg.get("func") or "SUM").upper()
            if not dim or not metric:
                return jsonify({"error": "Agg requires dim and metric."}), 400
            # Build a safe-ish aggregated query by wrapping the original SQL as a subquery
            agg_sql = f"SELECT {dim} AS dim, {func}({metric}) AS value FROM (\n{q.sql_text}\n) AS _t GROUP BY {dim} ORDER BY value DESC LIMIT 1000"
            res = execute_sql(src, agg_sql, params=user_params)
        else:
            res = execute_sql(src, q.sql_text, params=user_params)
    except QueryExecutionError as e:
        return jsonify({"error": str(e)}), 400
    # trim for safety
    rows = res.get("rows") or []
    if len(rows) > 5000:
        res["rows"] = rows[:5000]
    return jsonify(res)


@bp.route("/api/questions/<int:question_id>/viz", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def api_question_save_viz(question_id: int):
    _require_tenant()
    q = Question.query.filter_by(id=question_id, tenant_id=g.tenant.id).first_or_404()
    payload = request.get_json(silent=True) or {}
    cfg = payload.get("viz_config") or {}
    if cfg and not isinstance(cfg, dict):
        return jsonify({"error": "viz_config inválido."}), 400
    q.viz_config_json = cfg
    _audit("bi.question.viz.updated", {"id": q.id})
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/api/dashboards/<int:dashboard_id>/cards", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def api_dashboard_add_card(dashboard_id: int):
    _require_tenant()
    dash = Dashboard.query.filter_by(id=dashboard_id, tenant_id=g.tenant.id).first_or_404()
    payload = request.get_json(silent=True) or {}
    try:
        qid = int(payload.get("question_id") or 0)
    except Exception:
        qid = 0
    if not qid:
        return jsonify({"error": "Pergunta inválida."}), 400
    q = Question.query.filter_by(id=qid, tenant_id=g.tenant.id).first_or_404()
    cfg = payload.get("viz_config") or {}
    if cfg and not isinstance(cfg, dict):
        return jsonify({"error": "viz_config inválido."}), 400

    # place at bottom (roughly)
    cards = DashboardCard.query.filter_by(dashboard_id=dash.id, tenant_id=g.tenant.id).all()
    max_y = 0
    for c in cards:
        pj = c.position_json or {}
        try:
            y = int(pj.get("y") or 0)
            h = int(pj.get("h") or 6)
        except Exception:
            y, h = 0, 6
        max_y = max(max_y, y + h)

    card = DashboardCard(
        tenant_id=g.tenant.id,
        dashboard_id=dash.id,
        question_id=q.id,
        position_json={"x": 0, "y": max_y, "w": 12, "h": 6},
        viz_config_json=cfg or {},
    )
    db.session.add(card)
    _audit("bi.dashboard.card.created", {"dashboard_id": dash.id, "card_id": None, "question_id": q.id})
    db.session.commit()
    return jsonify({"ok": True, "card_id": card.id})


@bp.route("/api/dashboards/<int:dashboard_id>/cards/<int:card_id>", methods=["DELETE"])
@login_required
@require_roles("tenant_admin", "creator")
def api_dashboard_delete_card(dashboard_id: int, card_id: int):
    _require_tenant()
    dash = Dashboard.query.filter_by(id=dashboard_id, tenant_id=g.tenant.id).first_or_404()
    card = DashboardCard.query.filter_by(id=card_id, dashboard_id=dash.id, tenant_id=g.tenant.id).first_or_404()
    _audit("bi.dashboard.card.deleted", {"dashboard_id": dash.id, "card_id": card.id})
    db.session.delete(card)
    db.session.commit()
    return jsonify({"ok": True})

# -----------------------------
# Audit & Query Runs
# -----------------------------


@bp.route("/audit")
@login_required
@require_roles("tenant_admin", "creator")
def audit_list():
    _require_tenant()
    events = (
        AuditEvent.query.filter_by(tenant_id=g.tenant.id)
        .order_by(AuditEvent.created_at.desc())
        .limit(200)
        .all()
    )
    return render_template("portal/audit_list.html", tenant=g.tenant, events=events)


@bp.route("/runs")
@login_required
@require_roles("tenant_admin", "creator")
def runs_list():
    _require_tenant()
    runs = (
        QueryRun.query.filter_by(tenant_id=g.tenant.id)
        .order_by(QueryRun.started_at.desc())
        .limit(200)
        .all()
    )
    return render_template("portal/runs_list.html", tenant=g.tenant, runs=runs)



# -----------------------------
# Dashboard Layout API (Gridstack)
# -----------------------------


@bp.route("/api/dashboards/<int:dashboard_id>/layout", methods=["POST"])
@login_required
@require_roles("tenant_admin", "creator")
def api_dashboard_layout(dashboard_id: int):
    _require_tenant()
    dash = Dashboard.query.filter_by(id=dashboard_id, tenant_id=g.tenant.id).first_or_404()

    payload = request.get_json(silent=True) or {}
    items = payload.get("items") or []
    if not isinstance(items, list):
        return jsonify({"error": "Payload inválido."}), 400

    # Build map for faster validation
    cards = DashboardCard.query.filter_by(dashboard_id=dash.id, tenant_id=g.tenant.id).all()
    card_map = {c.id: c for c in cards}

    updated = 0
    for it in items:
        if not isinstance(it, dict):
            continue
        try:
            cid = int(it.get("card_id") or 0)
            x = int(it.get("x") or 0)
            y = int(it.get("y") or 0)
            w = int(it.get("w") or 12)
            h = int(it.get("h") or 6)
        except Exception:
            continue
        c = card_map.get(cid)
        if not c:
            continue
        # Conservative bounds
        if w < 1: w = 1
        if w > 12: w = 12
        if h < 2: h = 2
        if h > 30: h = 30
        if x < 0: x = 0
        if x > 11: x = 11
        if y < 0: y = 0

        c.position_json = {"x": x, "y": y, "w": w, "h": h}
        updated += 1

    _audit("bi.dashboard.layout.updated", {"id": dash.id, "updated": updated})
    db.session.commit()
    return jsonify({"ok": True, "updated": updated})


# -----------------------------
# AI Assistant (Chat + analysis)
# -----------------------------


@bp.route("/ai")
@login_required
def ai_chat():
    _require_tenant()
    qs = Question.query.filter_by(tenant_id=g.tenant.id).order_by(Question.updated_at.desc()).all()
    return render_template("portal/ai_chat.html", tenant=g.tenant, questions=qs)


@bp.route("/api/ai/chat", methods=["POST"])
@login_required
def api_ai_chat():
    _require_tenant()
    payload = request.get_json(silent=True) or {}

    try:
        question_id = int(payload.get("question_id") or 0)
    except Exception:
        question_id = 0

    message = (payload.get("message") or "").strip()
    history = payload.get("history") or []
    params = payload.get("params") or {}

    if not question_id:
        return jsonify({"error": "Selecione uma pergunta."}), 400
    if not message:
        return jsonify({"error": "Mensagem vazia."}), 400
    if params and not isinstance(params, dict):
        return jsonify({"error": "Parâmetros devem ser um objeto JSON."}), 400
    if history and not isinstance(history, list):
        history = []

    q = Question.query.filter_by(id=question_id, tenant_id=g.tenant.id).first_or_404()
    src = DataSource.query.filter_by(id=q.source_id, tenant_id=g.tenant.id).first_or_404()

    # Execute query (bounded)
    user_params: dict = {}
    if isinstance(params, dict):
        user_params.update(params)
    user_params["tenant_id"] = g.tenant.id

    try:
        res = execute_sql(src, q.sql_text, params=user_params)
    except QueryExecutionError as e:
        return jsonify({"error": str(e)}), 400

    # Keep payload light
    rows = res.get("rows") or []
    cols = res.get("columns") or []
    if len(rows) > 2000:
        rows = rows[:2000]

    # Quick profile (no heavy deps)
    profile = {"columns": [], "row_count": len(rows)}
    for i, c in enumerate(cols):
        col_vals = [r[i] for r in rows if isinstance(r, list) and i < len(r)]
        non_null = [v for v in col_vals if v is not None]
        sample = non_null[:10]
        # numeric?
        nums = []
        for v in non_null[:500]:
            try:
                nums.append(float(v))
            except Exception:
                pass
        col_info = {"name": str(c), "sample": sample}
        if len(nums) >= max(3, int(0.6 * min(500, len(non_null) or 1))):
            if nums:
                col_info.update({
                    "type": "number",
                    "min": min(nums),
                    "max": max(nums),
                    "avg": sum(nums) / len(nums),
                })
        else:
            col_info["type"] = "text"
            # top values (light)
            counts = {}
            for v in non_null[:1000]:
                sv = str(v)
                counts[sv] = counts.get(sv, 0) + 1
            top = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:8]
            col_info["top"] = top
        profile["columns"].append(col_info)

    data_bundle = {
        "question": {"id": q.id, "name": q.name},
        "sql": q.sql_text,
        "params": {k: v for k, v in (params or {}).items()},
        "result": {
            "columns": cols,
            "rows_sample": rows[:200],
            "row_count": len(rows),
        },
        "profile": profile,
        "lang": getattr(g, "lang", None),
    }

    ai = analyze_with_ai(data_bundle, message, history=history, lang=getattr(g, "lang", None))
    return jsonify(ai)


@bp.route("/api/help/chat", methods=["POST"])
@login_required
def api_help_chat():
    _require_tenant()
    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip()
    if not message:
        return jsonify({"ok": False, "error": _("Mensagem vazia.")}), 400

    text = message.lower()
    if any(k in text for k in ["sql", "query", "consulta", "requête", "abfrage"]):
        reply = _(
            "No Editor SQL você pode escrever, testar e salvar consultas. Use autocomplete com Ctrl+Space e execute com Ctrl+Enter."
        )
    elif any(k in text for k in ["pergunta", "question", "pregunta", "domanda", "frage"]):
        reply = _(
            "Perguntas são consultas salvas. Você pode adicionar filtros e reutilizar em dashboards e relatórios."
        )
    elif any(k in text for k in ["dashboard", "painel", "tableau", "cruscotto"]):
        reply = _(
            "Dashboards reúnem cards de perguntas. Você pode ajustar layout, visualizações e definir um dashboard principal."
        )
    elif any(k in text for k in ["relatório", "report", "rapport", "informe", "bericht"]):
        reply = _(
            "Relatórios permitem montar páginas com blocos de texto, imagem e perguntas com exportação em PDF."
        )
    elif any(k in text for k in ["fonte", "source", "fuente", "quelle"]):
        reply = _(
            "Fontes conectam bancos e APIs. Cadastre a conexão e introspecte schema para usar no editor e no builder."
        )
    elif any(k in text for k in ["etl", "pipeline", "workflow", "fluxo"]):
        reply = _(
            "No ETL Builder você encadeia Extract, Transform e Load, incluindo decisões e ramificações true/false."
        )
    else:
        reply = _(
            "Posso ajudar com Fontes, SQL, Perguntas, Dashboards, Relatórios e ETL."
        )

    suggestions = [
        _("Como criar uma fonte de dados?"),
        _("Como escrever SQL no editor?"),
        _("Como salvar uma pergunta?"),
        _("Como montar um dashboard?"),
    ]
    return jsonify({"ok": True, "reply": reply, "suggestions": suggestions})

@bp.get("/etls")
def etls_list():
    # List saved ETL workflows for the current tenant
    return render_template("portal/etls_list.html", title="ETLs")


@bp.route("/projects")
@login_required
def projects_hub():
    return redirect(url_for("project.dashboard"))


@bp.route("/api/projects/workspace", methods=["GET"])
@login_required
def project_workspace_get():
    return redirect(url_for("project.workspace_get"))


@bp.route("/api/projects/workspace", methods=["POST"])
@login_required
def project_workspace_save():
    return redirect(url_for("project.workspace_save"), code=307)

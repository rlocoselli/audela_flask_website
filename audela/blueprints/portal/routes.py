from __future__ import annotations

from datetime import datetime

import json

from flask import abort, flash, g, jsonify, make_response, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ...extensions import db
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
from ...security import require_roles
from ...services.query_service import QueryExecutionError, execute_sql
from ...services.datasource_service import decrypt_config, introspect_source
from ...services.nlq_service import generate_sql_from_nl
from ...services.pdf_export import table_to_pdf_bytes
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
from ...tenancy import get_current_tenant_id

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


def _require_tenant() -> None:
    if not current_user.is_authenticated:
        abort(401)
    if not g.tenant or current_user.tenant_id != g.tenant.id:
        abort(403)


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


@bp.route("/")
@login_required
def home():
    _require_tenant()
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

        if ds_type == 'postgres':
            return str(URL.create(
                'postgresql+psycopg',
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
    }

    if request.method == 'POST':
        name = form['name']
        ds_type = form['type']
        default_schema = form['default_schema'] or None
        tenant_column = form['tenant_column'] or None

        url = form['url']
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
            policy_json={
                'timeout_seconds': 30,
                'max_rows': 5000,
                'read_only': True,
            },
        )
        db.session.add(ds)
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
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        base_url = request.form.get("base_url", "").strip()
        headers_raw = (request.form.get("headers_json", "") or "").strip()

        if not name or not base_url:
            flash(tr("Preencha nome e URL base.", getattr(g, "lang", None)), "error")
            return render_template("portal/api_sources_new.html", tenant=g.tenant)

        headers = None
        if headers_raw:
            import json

            try:
                headers = json.loads(headers_raw)
                if not isinstance(headers, dict):
                    raise ValueError("headers_json must be a JSON object")
            except Exception as e:
                flash(tr("JSON inválido em cabeçalhos: {error}", getattr(g, "lang", None), error=str(e)), "error")
                return render_template(
                    "portal/api_sources_new.html",
                    tenant=g.tenant,
                    form={"name": name, "base_url": base_url, "headers_json": headers_raw},
                )

        from ...services.crypto import encrypt_json

        config = {
            "base_url": base_url,
            "headers": headers or {},
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
        _audit("bi.datasource.created", {"id": None, "name": name, "type": "api"})
        db.session.commit()

        flash(tr("Fonte API criada.", getattr(g, "lang", None)), "success")
        return redirect(url_for("portal.api_sources_list"))

    return render_template("portal/api_sources_new.html", tenant=g.tenant)


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
        if c2.get("password"):
            c2["password"] = "***"
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

        if ds_type == 'postgres':
            return str(URL.create(
                'postgresql+psycopg',
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
    }

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

        if ds_type == "postgres":
            return str(
                URL.create(
                    "postgresql+psycopg",
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
            tables.append({"name": t.get("name"), "columns": [c.get("name") for c in t.get("columns", [])]})

    # Infer relations via simple foreign-key naming heuristics (col ending with _id)
    name_index = {t["name"]: t for t in tables}
    relations = []
    for t in tables:
        for col in t.get("columns", []):
            if not isinstance(col, str):
                continue
            if not col.endswith("_id"):
                continue
            base = col[:-3]
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
                relations.append({"from": f"{t['name']}.{col}", "to": f"{target}.id"})

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
            flash("Selecione uma fonte válida.", "error")
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
        _audit("bi.question.created", {"id": q.id, "name": q.name, "source_id": src.id})
        db.session.commit()
        flash(tr("Pergunta criada.", getattr(g, "lang", None)), "success")
        return redirect(url_for("portal.questions_view", question_id=q.id))

    return render_template("portal/questions_new.html", tenant=g.tenant, sources=sources)


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
        for idx, b in enumerate(bands.get(band_name) or []):
            bb = dict(b) if isinstance(b, dict) else {}
            btype = (bb.get("type") or "").lower()
            key = f"{band_name}:{idx}"
            bb["_key"] = key

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
                        # format cells
                        rows_fmt = [[_format_cell(c, decimals, date_fmt) for c in r] for r in rows]
                        blocks_data[key] = {"columns": cols, "rows": rows_fmt}
                    except Exception as e:
                        blocks_data[key] = {"columns": [], "rows": [], "error": str(e)}

            elif btype == "field":
                cfg = bb.get("config") if isinstance(bb.get("config"), dict) else {}
                kind = (cfg.get("kind") or "date").lower()
                fmt = cfg.get("format") or ("dd/MM/yyyy HH:mm" if kind == "datetime" else "dd/MM/yyyy")
                now = datetime.now()
                val = _fmt_date(now, fmt)
                bb["value"] = val

            out_list.append(bb)
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

@bp.get("/etls")
def etls_list():
    # List saved ETL workflows for the current tenant
    return render_template("portal/etls_list.html", title="ETLs")

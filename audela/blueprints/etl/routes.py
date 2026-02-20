from __future__ import annotations

import json
import os
from datetime import datetime

from sqlalchemy import create_engine, text

import requests

from flask import Blueprint, current_app, jsonify, render_template, request, g, Response, stream_with_context

from audela.etl.engine import ETLEngine, ETLContext
from audela.etl.registry import REGISTRY
from audela.etl.workflow_loader import normalize_workflow
from audela.extensions import csrf, db

bp = Blueprint("etl", __name__, url_prefix="/etl")

def _workflows_dir() -> str:
    # Store under instance/etl_workflows/<tenant_slug>
    base = os.path.join(current_app.instance_path, "etl_workflows")
    tenant_slug = getattr(getattr(g, "tenant", None), "slug", None) or "global"
    d = os.path.join(base, tenant_slug)
    os.makedirs(d, exist_ok=True)
    return d

@bp.get("/builder")
def builder():
    return render_template("portal/etl_builder.html")

@bp.get("/api/workflows")
def list_workflows():
    d = _workflows_dir()
    # Return unique base names, prefer ones having drawflow raw
    bases = {}
    for fn in sorted(os.listdir(d)):
        if fn.endswith(".drawflow.json"):
            base = fn[:-len(".drawflow.json")]
            bases.setdefault(base, {"name": base, "has_drawflow": True})
        elif fn.endswith(".json"):
            base = fn[:-len(".json")]
            bases.setdefault(base, {"name": base, "has_drawflow": False})
        elif fn.endswith(".yaml") or fn.endswith(".yml"):
            base = fn.rsplit(".", 1)[0]
            bases.setdefault(base, {"name": base, "has_drawflow": False})
    return jsonify({"workflows": sorted(bases.values(), key=lambda x: x["name"])})


@bp.post("/api/workflows")
@csrf.exempt
def save_workflow():
    payload = request.get_json(force=True, silent=False)

    # Name can be provided explicitly from UI
    name = (payload or {}).get("name") or "workflow"
    safe = "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in str(name)).strip("_") or "workflow"
    d = _workflows_dir()

    # Always save the raw builder graph (drawflow export)
    raw_path = os.path.join(d, f"{safe}.drawflow.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # Try to also save normalized workflow JSON/YAML (may fail if graph is incomplete)
    wf = None
    error = None
    try:
        wf = normalize_workflow(payload)
    except Exception as e:
        error = str(e)

    json_path = os.path.join(d, f"{safe}.json")
    yaml_path = os.path.join(d, f"{safe}.yaml")
    yaml_ok = False

    if wf is not None:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(wf, f, ensure_ascii=False, indent=2)
        try:
            import yaml  # type: ignore
            with open(yaml_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(wf, f, sort_keys=False, allow_unicode=True)
            yaml_ok = True
        except Exception:
            yaml_ok = False

    return jsonify({
        "ok": True,
        "name": safe,
        "raw": os.path.basename(raw_path),
        "workflow_saved": wf is not None,
        "yaml_ok": yaml_ok,
        "warning": error,
    })

@bp.post("/api/run")
@csrf.exempt
def run_workflow():
    payload = request.get_json(force=True, silent=False)
    wf = normalize_workflow(payload)
    # Ensure handlers registered
    import audela.etl  # noqa: F401

    engine = ETLEngine()
    app_obj = current_app._get_current_object()
    result = engine.run(wf, app=current_app)
    return jsonify(result)

@bp.post("/api/preview")
@csrf.exempt
def preview_workflow():
    payload = request.get_json(force=True, silent=False)
    wf = normalize_workflow(payload)
    import audela.etl  # noqa: F401
    engine = ETLEngine()
    app_obj = current_app._get_current_object()
    result = engine.preview(wf, app=current_app, limit=int(request.args.get("limit", 20)))
    return jsonify(result)


from audela.models.etl_catalog import ETLConnection
from audela.etl.crypto import encrypt_json, decrypt_json

@bp.get("/api/connections")
def list_connections():
    tenant = getattr(g, "tenant", None)
    q = ETLConnection.query
    if tenant is not None:
        q = q.filter((ETLConnection.tenant_id == tenant.id) | (ETLConnection.tenant_id.is_(None)))
    items = q.order_by(ETLConnection.name.asc()).all()
    return jsonify({"connections": [{"id": c.id, "name": c.name, "type": c.type} for c in items]})

@bp.post("/api/connections")
@csrf.exempt
def create_connection():
    payload = request.get_json(force=True, silent=False)
    name = payload.get("name")
    ctype = payload.get("type")
    data = payload.get("data") or {}
    if not name or not ctype:
        return jsonify({"ok": False, "error": "name and type required"}), 400
    enc = encrypt_json(current_app, data)
    tenant = getattr(g, "tenant", None)
    conn = ETLConnection(name=name, type=ctype, encrypted_payload=enc, tenant_id=getattr(tenant, "id", None))
    db.session.add(conn)
    db.session.commit()
    return jsonify({"ok": True, "id": conn.id})

@bp.get("/api/connections/<int:conn_id>")
def get_connection(conn_id: int):
    conn = ETLConnection.query.get_or_404(conn_id)
    data = decrypt_json(current_app, conn.encrypted_payload)
    return jsonify({"id": conn.id, "name": conn.name, "type": conn.type, "data": data})


@bp.get("/api/workflows/<name>")
def get_workflow(name: str):
    d = _workflows_dir()
    safe = "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in name).strip("_")
    if not safe:
        return jsonify({"ok": False, "error": "invalid name"}), 400

    # Prefer raw drawflow export if present
    raw_path = os.path.join(d, f"{safe}.drawflow.json")
    if os.path.exists(raw_path):
        with open(raw_path, "r", encoding="utf-8") as f:
            return jsonify({"ok": True, "kind": "drawflow", "name": safe, "data": json.load(f)})

    # Fallback to workflow json/yaml
    json_path = os.path.join(d, f"{safe}.json")
    yaml_path = os.path.join(d, f"{safe}.yaml")
    yml_path = os.path.join(d, f"{safe}.yml")
    path = None
    kind = None
    if os.path.exists(json_path):
        path, kind = json_path, "workflow"
        with open(path, "r", encoding="utf-8") as f:
            return jsonify({"ok": True, "kind": kind, "name": safe, "data": json.load(f)})
    for yp in (yaml_path, yml_path):
        if os.path.exists(yp):
            try:
                import yaml  # type: ignore
                with open(yp, "r", encoding="utf-8") as f:
                    return jsonify({"ok": True, "kind": "workflow", "name": safe, "data": yaml.safe_load(f)})
            except Exception as e:
                return jsonify({"ok": False, "error": str(e)}), 500

    return jsonify({"ok": False, "error": "not found"}), 404


@bp.post("/api/test/http")
@csrf.exempt
def test_http():
    cfg = request.get_json(force=True, silent=False) or {}
    url = cfg.get("url")
    if not url:
        return jsonify({"ok": False, "error": "url required"}), 400
    method = (cfg.get("method") or "GET").upper()
    headers = cfg.get("headers") or {}
    params = cfg.get("params") or {}
    timeout = int(cfg.get("timeout") or 15)
    try:
        resp = requests.request(method=method, url=url, headers=headers, params=params, timeout=timeout)
        content_type = resp.headers.get("Content-Type", "")
        preview = None
        if "application/json" in content_type:
            preview = resp.json()
        else:
            preview = (resp.text or "")[:1000]
        return jsonify({"ok": True, "status": resp.status_code, "content_type": content_type, "preview": preview})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@bp.post("/api/connections/<int:conn_id>/test")
@csrf.exempt
def test_connection(conn_id: int):
    from audela.models.etl_catalog import ETLConnection
    from audela.etl.crypto import decrypt_json

    conn = ETLConnection.query.get_or_404(conn_id)
    # Tenant isolation (best-effort)
    tenant = getattr(g, "tenant", None)
    if tenant is not None and conn.tenant_id is not None and conn.tenant_id != tenant.id:
        return jsonify({"ok": False, "error": "forbidden"}), 403

    data = decrypt_json(current_app, conn.encrypted_payload)
    ctype = (conn.type or "").lower()

    try:
        if ctype in ("http", "api"):
            url = data.get("url") or data.get("base_url")
            if not url:
                return jsonify({"ok": False, "error": "connection missing url/base_url"}), 400
            method = (data.get("method") or "GET").upper()
            headers = data.get("headers") or {}
            params = data.get("params") or {}
            timeout = int(data.get("timeout") or 15)
            resp = requests.request(method=method, url=url, headers=headers, params=params, timeout=timeout)
            return jsonify({"ok": True, "type": ctype, "status": resp.status_code})
        else:
            # DB: accept sqlalchemy_url or url; or build postgres from parts
            sqlalchemy_url = data.get("sqlalchemy_url") or data.get("url")
            if not sqlalchemy_url and ctype in ("postgres", "postgresql"):
                host = data.get("host")
                port = int(data.get("port") or 5432)
                dbname = data.get("database") or data.get("dbname")
                user = data.get("username") or data.get("user")
                pwd = data.get("password")
                if not (host and dbname and user and pwd):
                    return jsonify({"ok": False, "error": "missing postgres fields (host/database/username/password)"}), 400
                sqlalchemy_url = f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{dbname}"
            if not sqlalchemy_url:
                return jsonify({"ok": False, "error": "connection missing sqlalchemy_url/url"}), 400

            engine = create_engine(sqlalchemy_url, pool_pre_ping=True)
            with engine.connect() as c:
                c.execute(text("SELECT 1"))
            return jsonify({"ok": True, "type": ctype, "message": "connection ok"})
    except Exception as e:
        return jsonify({"ok": False, "type": ctype, "error": str(e)}), 400

from audela.models.bi import DataSource
from audela.services.datasource_service import get_engine


@bp.get("/api/sources/db")
def list_db_sources():
    tenant = getattr(g, "tenant", None)
    if tenant is None:
        return jsonify({"sources": []})
    sources = DataSource.query.filter_by(tenant_id=tenant.id).order_by(DataSource.created_at.desc()).all()
    return jsonify({"sources": [{"id": s.id, "name": s.name, "type": s.type} for s in sources]})

@bp.post("/api/sources/db/<int:source_id>/test")
@csrf.exempt
def test_db_source(source_id: int):
    tenant = getattr(g, "tenant", None)
    if tenant is None:
        return jsonify({"ok": False, "error": "tenant required"}), 400
    src = DataSource.query.filter_by(id=source_id, tenant_id=tenant.id).first()
    if not src:
        return jsonify({"ok": False, "error": "not found"}), 404
    try:
        eng = get_engine(src)
        from sqlalchemy import text as _text
        with eng.connect() as c:
            c.execute(_text("SELECT 1"))
        return jsonify({"ok": True, "message": "connection ok"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@bp.get("/api/sources/api")
def list_api_sources():
    try:
        from audela.extensions import db as _db
        rows = _db.session.execute(text("SELECT id, name, base_url, method FROM data_sources where type='api' ORDER BY created_at DESC")).mappings().all()
        return jsonify({"sources": [dict(r) for r in rows]})
    except Exception:
        return jsonify({"sources": []})

@bp.post("/api/sources/api/<int:source_id>/test")
@csrf.exempt
def test_api_source(source_id: int):
    try:
        from audela.extensions import db as _db
        row = _db.session.execute(text("SELECT id, base_url, method, headers, params, auth_token, auth_type FROM data_sources WHERE id=:id and type='api'"), {"id": source_id}).mappings().first()
        if not row:
            return jsonify({"ok": False, "error": "not found"}), 404
        url = row["base_url"]
        method = (row["method"] or "GET").upper()
        headers = row["headers"] or {}
        params = row["params"] or {}
        auth_type = row.get("auth_type")
        token = row.get("auth_token")
        if token and auth_type:
            if auth_type.lower() == "bearer":
                headers = {**headers, "Authorization": f"Bearer {token}"}
        resp = requests.request(method=method, url=url, headers=headers, params=params, timeout=15)
        return jsonify({"ok": True, "status": resp.status_code})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@bp.post("/api/run_stream")
@csrf.exempt
def run_workflow_stream():
    payload = request.get_json(force=True, silent=False)
    wf = normalize_workflow(payload)
    engine = ETLEngine()
    app_obj = current_app._get_current_object()

    def gen():
        events = []

        def cb(ev):
            events.append(ev)

        # Run in same thread, but we can yield between steps by draining events list.
        # We'll wrap cb to yield immediately by using a closure with outer yield not allowed, so we poll events list.
        import threading, time, json as _json
        done = {"ok": False, "result": None, "error": None}

        def runner():
            try:
                with app_obj.app_context():
                    res = engine.run(wf, app=app_obj, progress_cb=cb)
                done["ok"] = True
                done["result"] = res
            except Exception as e:
                done["ok"] = False
                done["error"] = str(e)

        t = threading.Thread(target=runner, daemon=True)
        t.start()

        # stream events
        while t.is_alive() or events:
            while events:
                ev = events.pop(0)
                yield _json.dumps(ev, ensure_ascii=False) + "\n"
            time.sleep(0.05)

        # final
        if done["ok"] and done["result"] is not None:
            yield _json.dumps({"event": "done", "result": done["result"]}, ensure_ascii=False) + "\n"
        else:
            yield _json.dumps({"event": "error", "error": done["error"] or "unknown"}, ensure_ascii=False) + "\n"

    return Response(stream_with_context(gen()), mimetype="application/x-ndjson")


@bp.post("/api/notify/test")
@csrf.exempt
def test_notify_integration():
    payload = request.get_json(force=True, silent=False) or {}
    cfg = payload.get("config") if isinstance(payload.get("config"), dict) else payload
    sample_rows = payload.get("sample_rows") if isinstance(payload.get("sample_rows"), list) else []

    import audela.etl  # noqa: F401
    handler = REGISTRY.get("notify.integration")
    if handler is None:
        return jsonify({"ok": False, "error": "notify.integration handler not found"}), 500

    ctx = ETLContext(data=sample_rows, meta={
        "workflow": {"name": str(payload.get("workflow") or "test_workflow")},
        "last_scalar": payload.get("last_scalar"),
        "tables": payload.get("tables") if isinstance(payload.get("tables"), dict) else {"staging": "staging.sample_table"},
    })

    try:
        handler(cfg, ctx, app=current_app)
        notifications = ctx.meta.get("notifications") if isinstance(ctx.meta.get("notifications"), list) else []
        latest = notifications[-1] if notifications else {"ok": True, "message": "sent"}
        return jsonify({"ok": bool(latest.get("ok", True)), "result": latest, "notifications": notifications})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

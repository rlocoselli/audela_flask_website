from __future__ import annotations

import json
import os
from datetime import datetime

from flask import Blueprint, current_app, jsonify, render_template, request, g, g

from audela.etl.engine import ETLEngine
from audela.etl.workflow_loader import normalize_workflow
from audela.extensions import csrf, db

bp = Blueprint("etl", __name__, url_prefix="/etl")

def _workflows_dir() -> str:
    # Store under instance/etl_workflows
    d = os.path.join(current_app.instance_path, "etl_workflows")
    os.makedirs(d, exist_ok=True)
    return d

@bp.get("/builder")
def builder():
    return render_template("portal/etl_builder.html")

@bp.get("/api/workflows")
def list_workflows():
    d = _workflows_dir()
    items = []
    for fn in sorted(os.listdir(d)):
        if fn.endswith(".yaml") or fn.endswith(".yml") or fn.endswith(".json"):
            items.append(fn)
    return jsonify({"workflows": items})

@bp.post("/api/workflows")
@csrf.exempt
def save_workflow():
    payload = request.get_json(force=True, silent=False)
    wf = normalize_workflow(payload)
    name = wf.get("name") or "workflow"
    safe = "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in name).strip("_") or "workflow"
    d = _workflows_dir()

    # Save JSON
    json_path = os.path.join(d, f"{safe}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(wf, f, ensure_ascii=False, indent=2)

    # Save YAML (optional dependency)
    yaml_ok = False
    yaml_path = os.path.join(d, f"{safe}.yaml")
    try:
        import yaml  # type: ignore
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(wf, f, sort_keys=False, allow_unicode=True)
        yaml_ok = True
    except Exception:
        yaml_ok = False

    return jsonify({"ok": True, "name": safe, "json": os.path.basename(json_path), "yaml": os.path.basename(yaml_path), "yaml_ok": yaml_ok})

@bp.post("/api/run")
@csrf.exempt
def run_workflow():
    payload = request.get_json(force=True, silent=False)
    wf = normalize_workflow(payload)
    # Ensure handlers registered
    import audela.etl  # noqa: F401

    engine = ETLEngine()
    result = engine.run(wf, app=current_app)
    return jsonify(result)

@bp.post("/api/preview")
@csrf.exempt
def preview_workflow():
    payload = request.get_json(force=True, silent=False)
    wf = normalize_workflow(payload)
    import audela.etl  # noqa: F401
    engine = ETLEngine()
    result = engine.preview(wf, app=current_app, limit=int(request.args.get("limit", 20)))
    return jsonify(result)


from audela.models.etl_catalog import ETLConnection
from audela.etl.crypto import encrypt_json, decrypt_json

@bp.get("/api/connections")
def list_connections():
    items = ETLConnection.query.order_by(ETLConnection.name.asc()).all()
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
    conn = ETLConnection(name=name, type=ctype, encrypted_payload=enc)
    db.session.add(conn)
    db.session.commit()
    return jsonify({"ok": True, "id": conn.id})

@bp.get("/api/connections/<int:conn_id>")
def get_connection(conn_id: int):
    conn = ETLConnection.query.get_or_404(conn_id)
    data = decrypt_json(current_app, conn.encrypted_payload)
    return jsonify({"id": conn.id, "name": conn.name, "type": conn.type, "data": data})

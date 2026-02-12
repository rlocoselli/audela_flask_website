from __future__ import annotations

from typing import Any, Dict, List
import requests
from sqlalchemy import text

from audela.models.bi import DataSource
from audela.services.datasource_service import get_engine

from flask import current_app

from .registry import register
from .table_manager import ensure_table



def _validate_connection(config: Dict[str, Any], app):
    name = config.get("connection") or config.get("connection_name")
    if not name:
        return None
    try:
        from audela.models.etl_catalog import ETLConnection
        c = ETLConnection.query.filter_by(name=name).first()
        if not c:
            raise ValueError(f"Unknown connection: {name}")
        return c
    except Exception:
        # If DB not ready/migrated, don't hard fail on validation
        return None



def _get_api_source(app, api_source_id: int):
    # ApiSource is stored in table api_sources (legacy module). We query via main SQLAlchemy engine.
    try:
        from audela.extensions import db  # main app db
        row = db.session.execute(text("SELECT id, name, base_url FROM data_sources WHERE id = :id"), {"id": api_source_id}).mappings().first()
        return dict(row) if row else None
    except Exception:
        return None

def _get_db_source(source_id: int):
    return DataSource.query.get(source_id)


@register("extract.http")
def extract_http(config: Dict[str, Any], ctx, app=None):
    # Can use a saved API source (api_sources table) + path overrides
    api_source_id = config.get("api_source_id")
    if api_source_id and (app is not None):
        src = _get_api_source(app, int(api_source_id))
        if src:
            base_url = (src.get("base_url") or "").strip()
            path = (config.get("path") or config.get("url") or "").strip()
            if path.startswith("http://") or path.startswith("https://"):
                url = path
            else:
                if not base_url:
                    url = path
                else:
                    url = (base_url.rstrip("/") + "/" + path.lstrip("/")).rstrip("/")
            config = {
                **config,
                "url": url,
                "method": config.get("method") or src.get("method") or "GET",
                "headers": {**(src.get("headers") or {}), **(config.get("headers") or {})},
                "params": {**(src.get("params") or {}), **(config.get("params") or {})},
            }

    url = (config.get("url") or "").strip()
    if not url:
        raise ValueError("extract.http requires config.url (or api_source_id + path)")

    method = (config.get("method") or "GET").upper()
    headers = config.get("headers") or {}
    params = config.get("params") or {}
    timeout = int(config.get("timeout") or 30)

    resp = requests.request(method=method, url=url, headers=headers, params=params, timeout=timeout)
    resp.raise_for_status()

    # Try JSON; fallback to text
    try:
        data = resp.json()
    except Exception:
        txt = resp.text or ""
        return [{"value": txt[:20000]}]

    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return data
    return [{"value": data}]


@register("extract.sql")
def extract_sql(config: Dict[str, Any], ctx, app=None):
    query = config.get("query")
    if not query:
        raise ValueError("extract.sql requires config.query")

    # If a saved DB source is selected, use its SQLAlchemy engine.
    db_source_id = config.get("db_source_id") or config.get("source_id")
    if db_source_id:
        src = _get_db_source(int(db_source_id))
        if not src:
            raise ValueError(f"Unknown DB source id: {db_source_id}")
        engine = get_engine(src)
    else:
        # Fallback to the app's main DB
        from audela.extensions import db
        engine = db.engine

    with engine.begin() as conn:
        rows = conn.execute(text(query)).mappings().all()
    return [dict(r) for r in rows]


@register("transform.mapping")
def transform_mapping(config: Dict[str, Any], ctx, app=None):
    data = ctx.data
    if data is None:
        return None
    if not isinstance(data, list):
        raise ValueError("transform.mapping expects list of rows")
    fields = config.get("fields") or {}
    if not fields:
        return data

    out: List[Dict[str, Any]] = []
    for row in data:
        new_row = {}
        for out_key, expr in fields.items():
            new_row[out_key] = _get_value(row, expr)
        out.append(new_row)
    return out


def _get_value(obj: Any, expr: str) -> Any:
    # Minimal dot-path resolver:
    # - if expr starts with "$.", treat as path on row dict
    # - else if expr is a plain key, take row[key]
    if not isinstance(expr, str):
        return None
    if expr.startswith("$."):
        path = expr[2:]
    else:
        path = expr
    cur = obj
    for part in path.split("."):
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


@register("load.warehouse")
def load_warehouse(config: Dict[str, Any], ctx, app=None):
    data = ctx.data
    if data is None:
        return None
    if not isinstance(data, list):
        raise ValueError("load.warehouse expects list of rows")

    table_name = config.get("table") or config.get("table_name")
    if not table_name:
        raise ValueError("load.warehouse requires config.table")

    schema = config.get("schema") or "public"
    create_if_missing = bool(config.get("create_table_if_missing", True))
    add_cols = bool(config.get("add_columns_if_missing", True))
    mode = (config.get("mode") or "append").lower()

    if mode not in ("append",):
        raise ValueError("Only mode=append supported in MVP")

    warehouse_source_id = config.get("warehouse_source_id") or config.get("db_source_id") or config.get("source_id")
    if warehouse_source_id:
        src = _get_db_source(int(warehouse_source_id))
        if not src:
            raise ValueError(f"Unknown warehouse source id: {warehouse_source_id}")
        engine = get_engine(src)
    else:
        from audela.extensions import db
        engine = db.engine


    # Ensure table exists + columns
    table = ensure_table(engine, schema=schema, table_name=table_name, rows=data,
                         create_table_if_missing=create_if_missing,
                         add_columns_if_missing=add_cols)

    # Insert
    with engine.begin() as conn:
        conn.execute(table.insert(), data)

    return data
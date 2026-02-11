from __future__ import annotations

from typing import Any, Dict, List
import requests
from sqlalchemy import text
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


@register("extract.http")
def extract_http(config: Dict[str, Any], ctx, app=None):
    url = config.get("url")
    if not url:
        raise ValueError("extract.http requires config.url")
    method = (config.get("method") or "GET").upper()
    headers = config.get("headers") or {}
    params = config.get("params") or {}
    timeout = int(config.get("timeout") or 30)

    resp = requests.request(method=method, url=url, headers=headers, params=params, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    # If it's a dict, wrap into list with one row
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
    # use Flask-SQLAlchemy engine
    from audela.extensions import db
    engine = db.get_engine(app or current_app)
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
    schema = config.get("schema") or "public"
    create_if_missing = bool(config.get("create_table_if_missing", True))
    add_cols = bool(config.get("add_columns_if_missing", True))
    mode = (config.get("mode") or "append").lower()

    if mode not in ("append",):
        raise ValueError("Only mode=append supported in MVP")

    from audela.extensions import db
    engine = db.get_engine(app or current_app)

    # Ensure table exists + columns
    table = ensure_table(engine, schema=schema, table_name=table_name, rows=data,
                         create_table_if_missing=create_if_missing,
                         add_columns_if_missing=add_cols)

    # Insert
    with engine.begin() as conn:
        conn.execute(table.insert(), data)

    return data
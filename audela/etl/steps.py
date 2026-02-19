from __future__ import annotations

from typing import Any, Dict, List
import json
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

    result_mode = str(config.get("result_mode") or "rows").strip().lower()
    strict_scalar = bool(config.get("strict_scalar", True))
    scalar_key = str(config.get("scalar_key") or "last_scalar").strip()

    # If a saved DB source is selected, use it. Workspace sources are executed via DuckDB.
    db_source_id = config.get("db_source_id") or config.get("source_id")
    if db_source_id:
        src = _get_db_source(int(db_source_id))
        if not src:
            raise ValueError(f"Unknown DB source id: {db_source_id}")

        if (src.type or "").lower() == "workspace":
            from audela.services.query_service import execute_sql as _execute_sql

            res = _execute_sql(src, query, params={}, row_limit=None)
            cols = res.get("columns") or []
            rows = res.get("rows") or []
            return [dict(zip(cols, r)) for r in rows]

        engine = get_engine(src)
    else:
        # Fallback to the app's main DB
        from audela.extensions import db
        engine = db.engine

    if result_mode == "scalar":
        with engine.begin() as conn:
            res = conn.execute(text(query))
            cols = list(res.keys())
            rows = res.fetchmany(2)

        if strict_scalar:
            if len(cols) != 1:
                raise ValueError("extract.sql scalar exige exatamente 1 coluna.")
            if len(rows) != 1:
                raise ValueError("extract.sql scalar exige exatamente 1 linha.")

        scalar_val = None
        if rows:
            r0 = rows[0]
            scalar_val = r0[0] if isinstance(r0, (list, tuple)) else (list(r0)[0] if r0 is not None else None)

        ctx.meta["last_scalar"] = scalar_val
        scalars = ctx.meta.get("scalars") if isinstance(ctx.meta.get("scalars"), dict) else {}
        if scalar_key:
            scalars[scalar_key] = scalar_val
        ctx.meta["scalars"] = scalars
        return [{"scalar": scalar_val}]

    with engine.begin() as conn:
        rows = conn.execute(text(query)).mappings().all()
    return [dict(r) for r in rows]


def _to_num(v: Any):
    try:
        if isinstance(v, bool):
            return None
        if isinstance(v, (int, float)):
            return float(v)
        return float(str(v).strip())
    except Exception:
        return None


def _to_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    s = str(v or "").strip().lower()
    return s in ("1", "true", "yes", "y", "on")


def _parse_comp_value(raw: Any) -> Any:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return ""
    try:
        return json.loads(s)
    except Exception:
        return s


@register("transform.decision.scalar")
def transform_decision_scalar(config: Dict[str, Any], ctx, app=None):
    source = str(config.get("source") or "last_scalar").strip().lower()
    scalar_key = str(config.get("scalar_key") or "").strip()
    op = str(config.get("operator") or "eq").strip().lower()
    compare = _parse_comp_value(config.get("value"))
    on_true = str(config.get("on_true") or "continue").strip().lower()
    on_false = str(config.get("on_false") or "stop").strip().lower()
    message = str(config.get("message") or "").strip() or "Decision scalar"

    if source == "meta_key" and scalar_key:
        scalars = ctx.meta.get("scalars") if isinstance(ctx.meta.get("scalars"), dict) else {}
        scalar = scalars.get(scalar_key)
    else:
        scalar = ctx.meta.get("last_scalar")

    def _cmp(a: Any, b: Any) -> bool:
        if op in ("empty", "is_empty"):
            return a in (None, "", [], {})
        if op in ("not_empty", "is_not_empty"):
            return a not in (None, "", [], {})
        if op in ("true", "is_true"):
            return _to_bool(a)
        if op in ("false", "is_false"):
            return not _to_bool(a)

        an = _to_num(a)
        bn = _to_num(b)
        if an is not None and bn is not None:
            if op in ("eq", "="):
                return an == bn
            if op in ("ne", "!="):
                return an != bn
            if op in ("gt", ">"):
                return an > bn
            if op in ("gte", ">="):
                return an >= bn
            if op in ("lt", "<"):
                return an < bn
            if op in ("lte", "<="):
                return an <= bn

        a_s = "" if a is None else str(a)
        b_s = "" if b is None else str(b)
        if op in ("eq", "="):
            return a_s == b_s
        if op in ("ne", "!="):
            return a_s != b_s
        if op in ("contains",):
            return b_s in a_s
        if op in ("in",):
            if isinstance(b, (list, tuple, set)):
                return a in b
            return a_s in [x.strip() for x in b_s.split(",") if x.strip()]
        if op in ("not_in",):
            if isinstance(b, (list, tuple, set)):
                return a not in b
            return a_s not in [x.strip() for x in b_s.split(",") if x.strip()]
        return a_s == b_s

    passed = _cmp(scalar, compare)
    action = on_true if passed else on_false

    ctx.meta["last_decision"] = {
        "scalar": scalar,
        "operator": op,
        "value": compare,
        "passed": passed,
        "action": action,
        "message": message,
    }

    cur_step_id = str(ctx.meta.get("_current_step_id") or "").strip()
    if cur_step_id:
        route_map = ctx.meta.get("_step_route") if isinstance(ctx.meta.get("_step_route"), dict) else {}
        route_map[cur_step_id] = "output_1" if passed else "output_2"
        ctx.meta["_step_route"] = route_map

    if action == "error":
        raise ValueError(f"{message}: decision {'true' if passed else 'false'}")
    if action == "stop":
        ctx.meta["_stop_workflow"] = True
        ctx.meta["_stop_reason"] = f"{message}: decision {'true' if passed else 'false'}"

    return ctx.data


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
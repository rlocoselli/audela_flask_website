from __future__ import annotations

from typing import Any, Dict, List
import json
import re
from datetime import datetime
import requests
from sqlalchemy import text
from flask_mail import Message

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


def _meta_tables(ctx) -> Dict[str, str]:
    tables = ctx.meta.get("tables")
    if isinstance(tables, dict):
        return tables
    tables = {}
    ctx.meta["tables"] = tables
    return tables


def _qual_table_name(schema: str, table: str) -> str:
    if schema:
        return f"{schema}.{table}"
    return table


def _as_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    s = str(v or "").strip().lower()
    return s in ("1", "true", "yes", "y", "on")


def _safe_ident(name: str, default: str = "table") -> str:
    raw = str(name or "").strip()
    if not raw:
        raw = default
    return re.sub(r"[^a-zA-Z0-9_]", "_", raw).strip("_") or default


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
    return _as_bool(v)


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


def _row_fields(rule: Dict[str, Any], row: Dict[str, Any]) -> List[str]:
    fields = rule.get("fields")
    if isinstance(fields, list) and fields:
        return [str(f) for f in fields if str(f).strip()]
    field = rule.get("field")
    if field:
        return [str(field)]
    return list(row.keys())


def _parse_date_value(value: Any, formats: List[str], output_format: str | None):
    if value in (None, ""):
        return value
    if isinstance(value, datetime):
        dt = value
    else:
        txt = str(value).strip()
        dt = None
        for fmt in formats:
            try:
                dt = datetime.strptime(txt, fmt)
                break
            except Exception:
                continue
        if dt is None:
            return value
    if output_format:
        try:
            return dt.strftime(output_format)
        except Exception:
            return value
    return dt.isoformat()


def _apply_cleaning_rule(row: Dict[str, Any], rule: Dict[str, Any], stats: Dict[str, Any]):
    rtype = str(rule.get("type") or "").strip().lower()
    if not rtype:
        return row

    out = dict(row)
    changed = 0

    if rtype == "trim":
        for field in _row_fields(rule, out):
            val = out.get(field)
            if isinstance(val, str):
                nv = val.strip()
                if nv != val:
                    out[field] = nv
                    changed += 1

    elif rtype == "normalize_nulls":
        default_tokens = ["", "null", "none", "na", "n/a", "nan", "-"]
        tokens = rule.get("tokens") if isinstance(rule.get("tokens"), list) else default_tokens
        norm = set(str(t).strip().lower() for t in tokens)
        for field in _row_fields(rule, out):
            val = out.get(field)
            if val is None:
                continue
            sval = str(val).strip().lower()
            if sval in norm:
                out[field] = None
                changed += 1

    elif rtype == "case":
        mode = str(rule.get("mode") or "lower").strip().lower()
        for field in _row_fields(rule, out):
            val = out.get(field)
            if not isinstance(val, str):
                continue
            if mode == "upper":
                nv = val.upper()
            elif mode == "title":
                nv = val.title()
            else:
                nv = val.lower()
            if nv != val:
                out[field] = nv
                changed += 1

    elif rtype == "regex_replace":
        pattern = str(rule.get("pattern") or "")
        repl = str(rule.get("repl") or "")
        if pattern:
            for field in _row_fields(rule, out):
                val = out.get(field)
                if val is None:
                    continue
                s = str(val)
                nv = re.sub(pattern, repl, s)
                if nv != s:
                    out[field] = nv
                    changed += 1

    elif rtype == "cast":
        cast_to = str(rule.get("to") or "str").strip().lower()
        for field in _row_fields(rule, out):
            val = out.get(field)
            if val is None:
                continue
            try:
                if cast_to == "int":
                    nv = int(float(val))
                elif cast_to == "float":
                    nv = float(val)
                elif cast_to == "bool":
                    nv = _as_bool(val)
                else:
                    nv = str(val)
            except Exception:
                continue
            if nv != val:
                out[field] = nv
                changed += 1

    elif rtype == "fillna":
        fill_val = rule.get("value")
        for field in _row_fields(rule, out):
            if out.get(field) is None:
                out[field] = fill_val
                changed += 1

    elif rtype == "parse_date":
        formats = rule.get("formats") if isinstance(rule.get("formats"), list) and rule.get("formats") else ["%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"]
        output_format = rule.get("output")
        output_format = str(output_format) if output_format else None
        for field in _row_fields(rule, out):
            val = out.get(field)
            nv = _parse_date_value(val, [str(f) for f in formats], output_format)
            if nv != val:
                out[field] = nv
                changed += 1

    elif rtype == "clip":
        min_v = rule.get("min")
        max_v = rule.get("max")
        min_n = _to_num(min_v)
        max_n = _to_num(max_v)
        for field in _row_fields(rule, out):
            val = out.get(field)
            num = _to_num(val)
            if num is None:
                continue
            nv = num
            if min_n is not None and nv < min_n:
                nv = min_n
            if max_n is not None and nv > max_n:
                nv = max_n
            if nv != num:
                out[field] = nv
                changed += 1

    if changed:
        stats["changed_cells"] = int(stats.get("changed_cells") or 0) + changed
    return out


def _preset_rules(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    presets = config.get("presets") if isinstance(config.get("presets"), list) else []
    rules: List[Dict[str, Any]] = []
    for p in presets:
        key = str(p).strip().lower()
        if key == "basic_text":
            rules.extend([
                {"type": "trim"},
                {"type": "normalize_nulls"},
            ])
        elif key == "email_standardization":
            rules.extend([
                {"type": "trim", "fields": ["email"]},
                {"type": "case", "mode": "lower", "fields": ["email"]},
            ])
        elif key == "phone_digits":
            rules.extend([
                {"type": "regex_replace", "pattern": r"[^0-9+]", "repl": "", "fields": ["phone", "mobile", "telephone"]},
            ])
        elif key == "dates_iso":
            rules.extend([
                {"type": "parse_date"},
            ])
    custom_rules = config.get("rules") if isinstance(config.get("rules"), list) else []
    for r in custom_rules:
        if isinstance(r, dict):
            rules.append(r)
    return rules


@register("transform.cleaning_rules")
def transform_cleaning_rules(config: Dict[str, Any], ctx, app=None):
    data = ctx.data
    if data is None:
        return None
    if not isinstance(data, list):
        raise ValueError("transform.cleaning_rules expects list of rows")

    rules = _preset_rules(config)
    if not rules:
        return data

    cleaned: List[Dict[str, Any]] = []
    stats: Dict[str, Any] = {
        "rows_in": len(data),
        "rows_out": 0,
        "changed_cells": 0,
        "dedup_removed": 0,
        "rules_count": len(rules),
    }

    for row in data:
        if isinstance(row, dict):
            cur = dict(row)
        else:
            cur = {"value": row}
        for rule in rules:
            cur = _apply_cleaning_rule(cur, rule, stats)
        cleaned.append(cur)

    dedup_cfg = config.get("deduplicate") if isinstance(config.get("deduplicate"), dict) else {}
    do_dedup = _as_bool(dedup_cfg.get("enabled")) if dedup_cfg else False
    if do_dedup:
        fields = dedup_cfg.get("fields") if isinstance(dedup_cfg.get("fields"), list) and dedup_cfg.get("fields") else []
        fields = [str(f) for f in fields]
        keep = str(dedup_cfg.get("keep") or "first").strip().lower()
        indexed = list(enumerate(cleaned))
        if keep == "last":
            indexed = list(reversed(indexed))
        seen = set()
        deduped = []
        for _, row in indexed:
            if fields:
                key = tuple(row.get(f) for f in fields)
            else:
                key = tuple(sorted(row.items()))
            if key in seen:
                stats["dedup_removed"] += 1
                continue
            seen.add(key)
            deduped.append(row)
        if keep == "last":
            deduped.reverse()
        cleaned = deduped

    stats["rows_out"] = len(cleaned)
    log = ctx.meta.get("cleaning_log") if isinstance(ctx.meta.get("cleaning_log"), list) else []
    log.append(stats)
    ctx.meta["cleaning_log"] = log
    ctx.meta["last_cleaning"] = stats
    return cleaned


def _resolve_table_placeholder(ctx, key: str) -> str:
    tables = _meta_tables(ctx)
    k = str(key or "").strip()
    return tables.get(k) or k


def _replace_table_placeholders(code: str, ctx) -> str:
    pattern = re.compile(r"\{\{\s*table:([a-zA-Z0-9_.-]+)\s*\}\}")
    return pattern.sub(lambda m: repr(_resolve_table_placeholder(ctx, m.group(1))), code)


def _render_notify_template(text_value: str, ctx, config: Dict[str, Any]) -> str:
    rendered = str(text_value or "")
    rendered = re.sub(
        r"\{\{\s*table:([a-zA-Z0-9_.-]+)\s*\}\}",
        lambda m: _resolve_table_placeholder(ctx, m.group(1)),
        rendered,
    )
    rendered = re.sub(
        r"\{\{\s*meta:([a-zA-Z0-9_.-]+)\s*\}\}",
        lambda m: str((ctx.meta or {}).get(m.group(1), "")),
        rendered,
    )
    rendered = rendered.replace("{{rows_count}}", str(len(ctx.data) if isinstance(ctx.data, list) else 0))
    rendered = rendered.replace("{{workflow}}", str((ctx.meta.get("workflow") or {}).get("name") or "workflow"))
    rendered = rendered.replace("{{step}}", str(config.get("name") or config.get("integration") or "notify"))
    return rendered


@register("notify.integration")
def notify_integration(config: Dict[str, Any], ctx, app=None):
    integration = str(config.get("integration") or "email").strip().lower()
    enabled = _as_bool(config.get("enabled", True))
    if not enabled:
        return ctx.data

    subject = _render_notify_template(str(config.get("subject") or "ETL notification"), ctx, config)
    message = _render_notify_template(str(config.get("message") or "Workflow {{workflow}} completed."), ctx, config)

    notification_log = ctx.meta.get("notifications") if isinstance(ctx.meta.get("notifications"), list) else []
    log_item = {
        "integration": integration,
        "subject": subject,
        "message": message,
        "ok": False,
        "error": None,
        "ts": datetime.utcnow().isoformat(),
    }

    try:
        if integration == "email":
            to_raw = config.get("to") or ""
            if isinstance(to_raw, list):
                recipients = [str(x).strip() for x in to_raw if str(x).strip()]
            else:
                recipients = [x.strip() for x in str(to_raw).split(",") if x.strip()]
            if not recipients:
                raise ValueError("notify.integration email requires recipient(s) in config.to")

            sender = str(config.get("sender") or current_app.config.get("MAIL_DEFAULT_SENDER") or "noreply@audela.com")
            msg = Message(subject=subject, recipients=recipients, body=message, sender=sender)
            if _as_bool(config.get("as_html", False)):
                msg.html = message

            from audela.extensions import mail
            mail.send(msg)
            log_item["ok"] = True
            log_item["targets"] = recipients

        elif integration in ("teams", "slack"):
            webhook_url = str(config.get("webhook_url") or "").strip()
            if not webhook_url:
                raise ValueError(f"notify.integration {integration} requires config.webhook_url")

            timeout = int(config.get("timeout") or 15)
            headers = config.get("headers") if isinstance(config.get("headers"), dict) else {}
            if integration == "teams":
                payload = {"text": f"{subject}\n\n{message}" if subject else message}
            else:
                payload = {"text": f"*{subject}*\n{message}" if subject else message}

            custom_payload = config.get("payload") if isinstance(config.get("payload"), dict) else None
            if custom_payload:
                payload = custom_payload

            resp = requests.post(webhook_url, json=payload, headers=headers, timeout=timeout)
            if resp.status_code >= 400:
                raise ValueError(f"Webhook HTTP {resp.status_code}: {resp.text[:400]}")
            log_item["ok"] = True
            log_item["targets"] = [webhook_url]

        else:
            raise ValueError("notify.integration integration must be one of: email, teams, slack")

    except Exception as e:
        log_item["error"] = str(e)
        notification_log.append(log_item)
        ctx.meta["notifications"] = notification_log
        if _as_bool(config.get("fail_on_error", False)):
            raise
        return ctx.data

    notification_log.append(log_item)
    ctx.meta["notifications"] = notification_log
    return ctx.data


@register("transform.python_advanced")
def transform_python_advanced(config: Dict[str, Any], ctx, app=None):
    code = str(config.get("code") or "").strip()
    if not code:
        raise ValueError("transform.python_advanced requires config.code")

    rendered_code = _replace_table_placeholders(code, ctx)
    input_mode = str(config.get("input_mode") or "current").strip().lower()
    input_table_key = str(config.get("input_table_key") or "").strip()
    data = ctx.data

    if input_mode == "table" and input_table_key:
        tables_data = ctx.meta.get("table_data") if isinstance(ctx.meta.get("table_data"), dict) else {}
        table_rows = tables_data.get(input_table_key)
        if table_rows is not None:
            data = table_rows

    def table(name: str):
        return _resolve_table_placeholder(ctx, name)

    allowed_builtins = {
        "len": len,
        "min": min,
        "max": max,
        "sum": sum,
        "sorted": sorted,
        "enumerate": enumerate,
        "range": range,
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "dict": dict,
        "list": list,
        "set": set,
        "tuple": tuple,
        "abs": abs,
        "round": round,
        "any": any,
        "all": all,
    }

    global_env = {
        "__builtins__": allowed_builtins,
        "re": re,
        "json": json,
        "datetime": datetime,
    }
    local_env = {
        "ctx": ctx,
        "meta": ctx.meta,
        "data": data,
        "rows": data,
        "result": None,
        "table": table,
    }

    exec(rendered_code, global_env, local_env)

    result = local_env.get("result")
    if result is None:
        result = local_env.get("data", data)

    output_table_key = str(config.get("output_table_key") or "").strip()
    if output_table_key and isinstance(result, list):
        tables_data = ctx.meta.get("table_data") if isinstance(ctx.meta.get("table_data"), dict) else {}
        tables_data[output_table_key] = result
        ctx.meta["table_data"] = tables_data

    return result


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

    tables = _meta_tables(ctx)
    table_key = str(config.get("table_key") or "warehouse").strip() or "warehouse"
    tables[table_key] = _qual_table_name(schema, table_name)
    ctx.meta["last_loaded_table"] = tables[table_key]

    return data


@register("load.staging_table")
def load_staging_table(config: Dict[str, Any], ctx, app=None):
    data = ctx.data
    if data is None:
        return None
    if not isinstance(data, list):
        raise ValueError("load.staging_table expects list of rows")

    base_name = str(config.get("table") or config.get("table_name") or "dataset").strip()
    base_name = _safe_ident(base_name, default="dataset")
    prefix = str(config.get("table_prefix") or "stg_")
    schema = str(config.get("schema") or "staging").strip() or "staging"
    run_suffix = _as_bool(config.get("run_suffix", True))
    mode = str(config.get("mode") or "append").strip().lower()

    suffix = datetime.utcnow().strftime("%Y%m%d_%H%M%S") if run_suffix else ""
    table_name = f"{prefix}{base_name}{'_' + suffix if suffix else ''}"

    create_if_missing = bool(config.get("create_table_if_missing", True))
    add_cols = bool(config.get("add_columns_if_missing", True))

    warehouse_source_id = config.get("warehouse_source_id") or config.get("db_source_id") or config.get("source_id")
    if warehouse_source_id:
        src = _get_db_source(int(warehouse_source_id))
        if not src:
            raise ValueError(f"Unknown warehouse source id: {warehouse_source_id}")
        engine = get_engine(src)
    else:
        from audela.extensions import db
        engine = db.engine

    table = ensure_table(engine, schema=schema, table_name=table_name, rows=data,
                         create_table_if_missing=create_if_missing,
                         add_columns_if_missing=add_cols)

    with engine.begin() as conn:
        if mode == "replace":
            conn.execute(table.delete())
        conn.execute(table.insert(), data)

    tables = _meta_tables(ctx)
    table_key = str(config.get("table_key") or "staging").strip() or "staging"
    full_name = _qual_table_name(schema, table_name)
    tables[table_key] = full_name

    runs = ctx.meta.get("staging_runs") if isinstance(ctx.meta.get("staging_runs"), list) else []
    runs.append({
        "table_key": table_key,
        "table": full_name,
        "rows": len(data),
        "mode": mode,
    })
    ctx.meta["staging_runs"] = runs

    return data
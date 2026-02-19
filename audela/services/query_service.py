from __future__ import annotations

from functools import lru_cache
import re
import time
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from ..models.bi import DataSource
from ..config import Config
from .datasource_service import decrypt_config, get_engine


class QueryExecutionError(Exception):
    pass


_READONLY_PREFIXES = ("select", "with", "show", "describe", "explain")


def _json_safe_value(v: Any) -> Any:
    """Best-effort conversion to JSON-serializable values.

    Jinja's `tojson` will fail on `Decimal`, `datetime`, etc.
    """
    if v is None:
        return None
    if isinstance(v, Decimal):
        # preserve numeric nature for charts
        return float(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, (bytes, bytearray)):
        try:
            return v.decode("utf-8", errors="replace")
        except Exception:
            return str(v)
    return v


def _json_safe_row(row: Any) -> list[Any]:
    return [_json_safe_value(x) for x in list(row)]


def _strip_sql_comments(sql: str) -> str:
    # remove -- line comments
    sql = re.sub(r"--.*?\n", "\n", sql)
    # remove /* */ block comments
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    return sql


def _is_readonly(sql: str) -> bool:
    cleaned = _strip_sql_comments(sql).strip().lstrip("(").strip()
    if not cleaned:
        return False
    first = cleaned.split(None, 1)[0].lower()
    return first in _READONLY_PREFIXES


def _apply_tenant_scoping_if_configured(sql: str, tenant_id: int, cfg: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """MVP tenant scoping.

    If the datasource config declares `tenant_column`, we enforce that the SQL text contains
    a bind placeholder :tenant_id and we pass the parameter.

    Why this approach?
    - Safe: no brittle SQL rewriting.
    - Still lets you guarantee scoping when you control the datasets.

    In production, prefer native RLS / views / policies.
    """
    tenant_column = cfg.get("tenant_column")
    if not tenant_column:
        return sql, {}

    # Enforce presence of :tenant_id so scoping can't be bypassed.
    if ":tenant_id" not in sql:
        raise QueryExecutionError(
            "Esta fonte requer escopo por tenant, mas a query não contém o parâmetro :tenant_id. "
            "Inclua um filtro (ex.: WHERE tenant_id = :tenant_id)."
        )
    return sql, {"tenant_id": tenant_id}


def _leading_sql_keyword(sql: str) -> str:
    cleaned = _strip_sql_comments(sql).strip().lstrip("(").strip()
    if not cleaned:
        return ""
    return cleaned.split(None, 1)[0].lower()


def _is_finance_source(source: DataSource) -> bool:
    return (source.type or "").strip().lower() == "audela_finance"


@lru_cache(maxsize=64)
def _finance_tenant_tables_by_engine(engine_url: str) -> tuple[str, ...]:
    """Return finance tables that have a tenant_id column."""
    from .datasource_service import _engine_for_source

    eng = _engine_for_source(-1, engine_url)
    insp = inspect(eng)

    table_names: list[str] = []
    try:
        if eng.dialect.name == "postgresql":
            table_names = insp.get_table_names(schema="public")
        else:
            table_names = insp.get_table_names()
    except Exception:
        table_names = []

    out: list[str] = []
    for t in table_names:
        if not str(t).startswith("finance_"):
            continue
        try:
            cols = insp.get_columns(t, schema="public" if eng.dialect.name == "postgresql" else None)
        except Exception:
            cols = []
        names = {str(c.get("name") or "") for c in cols}
        if "tenant_id" in names:
            out.append(str(t))
    return tuple(sorted(out))


def _rewrite_from_join_tables(sql: str, table_alias_map: dict[str, str]) -> str:
    rewritten = sql
    for table_name in sorted(table_alias_map.keys(), key=len, reverse=True):
        alias = table_alias_map[table_name]
        pat = re.compile(
            rf'(?i)\b(from|join)\s+((?:"?[A-Za-z_][A-Za-z0-9_]*"?\.)?"?{re.escape(table_name)}"?)\b'
        )
        rewritten = pat.sub(lambda m: f"{m.group(1)} {alias}", rewritten)
    return rewritten


def _inject_with_prefix(sql: str, ctes_sql: str) -> str:
    s = (sql or "").strip()
    low = s.lower()
    if low.startswith("with recursive "):
        rest = s[len("with recursive "):].lstrip()
        return f"WITH RECURSIVE {ctes_sql}, {rest}"
    if low.startswith("with "):
        rest = s[len("with "):].lstrip()
        return f"WITH {ctes_sql}, {rest}"
    return f"WITH {ctes_sql} {s}"


def _auto_scope_finance_sql(sql: str, tenant_id: int, source: DataSource) -> tuple[str, dict[str, Any]]:
    kw = _leading_sql_keyword(sql)
    if kw not in ("select", "with"):
        return sql, {}

    eng = get_engine(source)
    table_names = list(_finance_tenant_tables_by_engine(str(eng.url)))
    if not table_names:
        return sql, {}

    alias_map = {t: f"__scoped_{t}" for t in table_names}
    rewritten = _rewrite_from_join_tables(sql, alias_map)

    ctes = []
    for t in table_names:
        alias = alias_map[t]
        ctes.append(f'{alias} AS (SELECT * FROM "{t}" WHERE tenant_id = :tenant_id)')
    scoped_sql = _inject_with_prefix(rewritten, ", ".join(ctes))
    return scoped_sql, {"tenant_id": tenant_id}


def execute_sql(
    source: DataSource,
    sql_text: str,
    params: dict[str, Any] | None = None,
    *,
    row_limit: int | None = None,
) -> dict[str, Any]:
    """Execute a SQL query with conservative safety limits.

    Returns {columns: [...], rows: [...]}.
    """
    sql_text = (sql_text or "").strip()
    if not sql_text:
        raise QueryExecutionError("SQL vazio.")

    # Workspace datasource (files + optional base DB)
    if (source.type or "").lower() == "workspace":
        from .workspace_query_service import execute_workspace_sql

        return execute_workspace_sql(source, sql_text, params=params, row_limit=row_limit)

    policy = source.policy_json or {}
    read_only = bool(policy.get("read_only", True))
    max_rows = int(policy.get("max_rows", Config.QUERY_MAX_ROWS))

    # Optional caller-side row limit (e.g. report preview/PDF).
    # We never exceed datasource policy max_rows.
    if row_limit is not None:
        try:
            rl = int(row_limit)
            if rl > 0:
                max_rows = min(max_rows, rl)
        except Exception:
            pass
    timeout_seconds = int(policy.get("timeout_seconds", Config.QUERY_TIMEOUT_SECONDS))

    if read_only and not _is_readonly(sql_text):
        raise QueryExecutionError("Somente queries de leitura são permitidas (SELECT/WITH...).")

    cfg = decrypt_config(source)
    tenant_id = None
    if params and "tenant_id" in params:
        try:
            tenant_id = int(params["tenant_id"])
        except Exception:
            tenant_id = None

    extra_params: dict[str, Any] = {}
    if _is_finance_source(source):
        if tenant_id is None:
            raise QueryExecutionError("Fonte Finance exige contexto de tenant.")
        sql_text, extra_params = _auto_scope_finance_sql(sql_text, tenant_id, source)
    elif tenant_id is not None:
        sql_text, extra_params = _apply_tenant_scoping_if_configured(sql_text, tenant_id, cfg)

    bind_params = {}
    if params:
        bind_params.update(params)
    bind_params.update(extra_params)

    # Best-effort row limit (DB-specific LIMIT is not injected; you control this in SQL).
    eng = get_engine(source)
    started = time.time()

    try:
        with eng.connect() as conn:
            # Attempt statement timeout for Postgres via SET LOCAL
            if eng.dialect.name == "postgresql":
                try:
                    conn.execute(text(f"SET LOCAL statement_timeout = {timeout_seconds * 1000}"))
                except Exception:
                    pass

            res = conn.execute(text(sql_text), bind_params)
            # If it's a SELECT-like statement, fetch.
            if res.returns_rows:
                rows = res.fetchmany(size=max_rows)
                cols = list(res.keys())
                # Convert row tuples to JSON-safe plain lists for template rendering.
                data = [_json_safe_row(r) for r in rows]
            else:
                cols, data = [], []

    except SQLAlchemyError as e:
        raise QueryExecutionError(str(e.__cause__ or e)) from e

    elapsed_ms = int((time.time() - started) * 1000)
    return {"columns": cols, "rows": data, "elapsed_ms": elapsed_ms}

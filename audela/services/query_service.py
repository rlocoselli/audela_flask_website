from __future__ import annotations

import re
import time
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import text
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


def execute_sql(source: DataSource, sql_text: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute a SQL query with conservative safety limits.

    Returns {columns: [...], rows: [...]}.
    """
    sql_text = (sql_text or "").strip()
    if not sql_text:
        raise QueryExecutionError("SQL vazio.")

    policy = source.policy_json or {}
    read_only = bool(policy.get("read_only", True))
    max_rows = int(policy.get("max_rows", Config.QUERY_MAX_ROWS))
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
    if tenant_id is not None:
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

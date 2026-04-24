from __future__ import annotations

from functools import lru_cache
from typing import Any

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import URL, make_url

from ..models.bi import DataSource
from .crypto import decrypt_json


def decrypt_config(source: DataSource) -> dict[str, Any]:
    return decrypt_json(source.config_encrypted)


def _is_masked_password(pwd: str | None) -> bool:
    return False


def redact_url_password(url: str) -> str:
    """Return a SQLAlchemy URL with password redacted (***).

    If parsing fails, returns the original string.
    """
    s = (url or "").strip()
    if not s:
        return s
    try:
        u = make_url(s)
        return str(u)
    except Exception:
        return s


def inject_password_into_url(url: str, password: str | None) -> str:
    """Inject password into URL when it's missing or masked.

    If URL already has a non-masked password, it's preserved.
    If parsing fails, returns original.
    """
    s = (url or "").strip()
    if not s:
        return s
    pwd = password or ""
    if not pwd:
        return s
    try:
        u = make_url(s)
        u = u.set(password=pwd)
        return str(u).replace("***", password)
    except Exception:
        return s


def build_url_from_conn(ds_type: str, conn: dict[str, Any]) -> str:
    """Build a SQLAlchemy URL from structured connection parts (best-effort)."""
    ds_type = (ds_type or "").lower().strip()
    host = (conn.get("host") or "").strip()
    port = (conn.get("port") or "").strip()
    database = (conn.get("database") or "").strip()
    username = (conn.get("username") or "").strip()
    password = conn.get("password") or None
    driver = (conn.get("driver") or "").strip()
    service_name = (conn.get("service_name") or "").strip()
    sid = (conn.get("sid") or "").strip()
    sqlite_path = (conn.get("sqlite_path") or "").strip()

    if ds_type == "audela_finance":
        return "internal://audela_finance"
    if ds_type == "audela_project":
        return "internal://audela_project"

    if ds_type == "sqlite":
        if sqlite_path.startswith("sqlite:"):
            return sqlite_path
        p = sqlite_path or database
        if not p:
            return ""
        if p.startswith("/"):
            return "sqlite:////" + p.lstrip("/")
        return "sqlite:///" + p

    if ds_type == "postgres":
        return str(
            URL.create(
                "postgresql+psycopg2",
                username=username or None,
                password=password,
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
                password=password,
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
                password=password,
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
                password=password,
                host=host or None,
                port=int(port) if port else None,
                database=None,
                query=query or None,
            )
        )

    return ""


@lru_cache(maxsize=256)
def _engine_for_source(source_id: int, url: str) -> Engine:
    # pool_pre_ping avoids dead connections for long-lived processes.
    return create_engine(url, pool_pre_ping=True)


def get_engine(source: DataSource) -> Engine:
    if (source.type or '').lower() in ('workspace', 'audela_finance', 'audela_project'):
        from ..extensions import db
        return db.engine

    cfg = decrypt_config(source)
    url = (cfg.get("url") or "").strip()
    conn = cfg.get("conn") if isinstance(cfg.get("conn"), dict) else {}
    pwd = (conn.get("password") or "") if isinstance(conn, dict) else ""

    # Prefer building from structured conn if URL is missing.
    if not url and conn:
        url = build_url_from_conn(source.type, conn)

    if not url:
        raise ValueError("DataSource sem URL de conexão.")

    # If URL is redacted (***), inject the real password from conn.
    effective_url = inject_password_into_url(url, pwd)
    return _engine_for_source(source.id, effective_url)


def introspect_source(source: DataSource) -> dict[str, Any]:
    # Workspace datasource (files + optional base DB)
    if (source.type or "").lower() == "workspace":
        from .workspace_query_service import introspect_workspace

        return introspect_workspace(source)

    """Return a lightweight metadata catalog.

    Output shape:
    {
      "schemas": [
        {"name": "public", "tables": [
           {"name": "orders", "columns": [{"name": "id", "type": "INTEGER"}, ...]}
        ]}
      ]
    }
    """
    cfg = decrypt_config(source)
    default_schema = cfg.get("default_schema")

    eng = get_engine(source)
    insp = inspect(eng)
    try:
        schemas = insp.get_schema_names()
    except Exception:  # some DBs may not support schemas
        schemas = [default_schema] if default_schema else [None]

    out: dict[str, Any] = {"schemas": []}
    for schema in schemas:
        if default_schema and schema not in (default_schema, None):
            # keep MVP simple: show only default_schema if provided
            continue
        schema_name = schema or default_schema or "default"
        try:
            table_names = insp.get_table_names(schema=schema)
        except Exception:
            table_names = []
        try:
            view_names = insp.get_view_names(schema=schema)
        except Exception:
            view_names = []

        names_with_kind: list[tuple[str, str]] = []
        seen_names: set[str] = set()
        for name in table_names:
            n = str(name or "").strip()
            if not n or n in seen_names:
                continue
            seen_names.add(n)
            names_with_kind.append((n, "table"))
        for name in view_names:
            n = str(name or "").strip()
            if not n or n in seen_names:
                continue
            seen_names.add(n)
            names_with_kind.append((n, "view"))

        tables = []
        for tname, kind in sorted(names_with_kind, key=lambda x: x[0])[:200]:
            try:
                cols = insp.get_columns(tname, schema=schema)
            except Exception:
                cols = []
            tables.append(
                {
                    "name": tname,
                    "kind": kind,
                    "columns": [
                        {"name": c.get("name"), "type": str(c.get("type"))} for c in cols
                    ],
                }
            )
        out["schemas"].append({"name": schema_name, "tables": tables})
    return out


def introspect_source_tables(source: DataSource, *, max_tables_per_schema: int = 500) -> dict[str, Any]:
    """Return schemas with table/view names only (no columns)."""
    if (source.type or "").lower() == "workspace":
        meta = introspect_source(source)
        out: dict[str, Any] = {"schemas": []}
        for schema in (meta.get("schemas") or []):
            tables = []
            for table in (schema.get("tables") or [])[:max_tables_per_schema]:
                tables.append({
                    "name": table.get("name"),
                    "kind": table.get("kind") or "table",
                })
            out["schemas"].append({"name": schema.get("name") or "default", "tables": tables})
        return out

    cfg = decrypt_config(source)
    default_schema = cfg.get("default_schema")

    eng = get_engine(source)
    insp = inspect(eng)
    try:
        schemas = insp.get_schema_names()
    except Exception:
        schemas = [default_schema] if default_schema else [None]

    out: dict[str, Any] = {"schemas": []}
    for schema in schemas:
        if default_schema and schema not in (default_schema, None):
            continue
        schema_name = schema or default_schema or "default"
        try:
            table_names = insp.get_table_names(schema=schema)
        except Exception:
            table_names = []
        try:
            view_names = insp.get_view_names(schema=schema)
        except Exception:
            view_names = []

        names_with_kind: list[tuple[str, str]] = []
        seen_names: set[str] = set()
        for name in table_names:
            n = str(name or "").strip()
            if not n or n in seen_names:
                continue
            seen_names.add(n)
            names_with_kind.append((n, "table"))
        for name in view_names:
            n = str(name or "").strip()
            if not n or n in seen_names:
                continue
            seen_names.add(n)
            names_with_kind.append((n, "view"))

        tables = [
            {"name": tname, "kind": kind}
            for tname, kind in sorted(names_with_kind, key=lambda x: x[0])[:max_tables_per_schema]
        ]
        out["schemas"].append({"name": schema_name, "tables": tables})
    return out


def introspect_source_table_columns(source: DataSource, table_name: str, *, schema: str | None = None) -> dict[str, Any]:
    """Return columns for one table/view only."""
    tname = str(table_name or "").strip()
    if not tname:
        return {"columns": []}

    if (source.type or "").lower() == "workspace":
        meta = introspect_source(source)
        schema_req = str(schema or "").strip().lower()
        for sch in (meta.get("schemas") or []):
            sch_name = str(sch.get("name") or "default")
            if schema_req and sch_name.lower() != schema_req:
                continue
            for table in (sch.get("tables") or []):
                if str(table.get("name") or "").strip().lower() != tname.lower():
                    continue
                cols = []
                for col in (table.get("columns") or []):
                    if isinstance(col, dict):
                        cols.append({"name": col.get("name"), "type": str(col.get("type") or "")})
                    else:
                        cols.append({"name": str(col), "type": ""})
                return {"columns": cols}
        return {"columns": []}

    eng = get_engine(source)
    insp = inspect(eng)

    try:
        cols = insp.get_columns(tname, schema=schema)
    except Exception:
        cols = []

    return {
        "columns": [{"name": c.get("name"), "type": str(c.get("type") or "")} for c in cols]
    }


def clear_engine_cache() -> None:
    """Clear cached SQLAlchemy engines (use after changing a datasource URL)."""
    try:
        _engine_for_source.cache_clear()
    except Exception:
        pass

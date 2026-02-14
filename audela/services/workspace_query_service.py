from __future__ import annotations

import re
import time
from typing import Any

import pandas as pd
from sqlalchemy import inspect

from ..models.bi import DataSource
from .crypto import decrypt_json
from .datasource_service import get_engine
from .file_storage_service import resolve_abs_path


# -----------------------------
# Workspace engine (DuckDB)
# -----------------------------


def _sanitize_table_name(name: str) -> str:
    """Restrict to [A-Za-z0-9_]."""
    name = (name or "").strip()
    name = re.sub(r"[^A-Za-z0-9_]", "_", name)
    if not name:
        return "t"
    if name[0].isdigit():
        name = "t_" + name
    return name


def _ident(name: str) -> str:
    # DuckDB uses double quotes for identifiers
    return '"' + (name or "").replace('"', '""') + '"'


def _lit(s: str) -> str:
    # SQL string literal
    return "'" + (s or "").replace("'", "''") + "'"


def _rewrite_schema_prefixes(sql_text: str) -> str:
    """Allow users to write files.<alias> or db.<table> in the editor."""
    sql_text = re.sub(r"\bfiles\.", "", sql_text, flags=re.I)
    sql_text = re.sub(r"\bdb\.", "db_", sql_text, flags=re.I)
    return sql_text


def _rewrite_named_params(sql_text: str) -> str:
    """Convert SQLAlchemy-style :param to DuckDB $param.

    DuckDB's Python API supports named parameters with a $prefix.
    We avoid rewriting :: casts via negative lookbehind.
    """
    return re.sub(r"(?<!:):([A-Za-z_][A-Za-z0-9_]*)", r"$\1", sql_text)


def _duckdb_conn():
    import duckdb

    con = duckdb.connect(database=":memory:")
    # Best-effort: enable Excel support if available
    try:
        con.execute("INSTALL excel")
        con.execute("LOAD excel")
    except Exception:
        pass
    # Try to be conservative with resource usage.
    try:
        con.execute("PRAGMA threads=4")
    except Exception:
        pass
    return con


def _register_file_view(con, alias: str, abs_path: str, file_format: str, max_rows: int | None):
    fmt = (file_format or "").lower().strip()
    view = _ident(alias)

    limit_sql = f" LIMIT {int(max_rows)}" if max_rows and int(max_rows) > 0 else ""

    if fmt == "csv":
        sql = f"CREATE OR REPLACE VIEW {view} AS SELECT * FROM read_csv_auto({_lit(abs_path)}){limit_sql}"
        con.execute(sql)
        return

    if fmt == "parquet":
        sql = f"CREATE OR REPLACE VIEW {view} AS SELECT * FROM read_parquet({_lit(abs_path)}){limit_sql}"
        con.execute(sql)
        return

    if fmt == "excel":
        # DuckDB supports .xlsx via read_xlsx (excel extension). .xls may fail.
        try:
            sql = f"CREATE OR REPLACE VIEW {view} AS SELECT * FROM read_xlsx({_lit(abs_path)}){limit_sql}"
            con.execute(sql)
            return
        except Exception:
            # Fallback: pandas -> register
            df = None
            try:
                df = pd.read_excel(abs_path)
            except Exception:
                for engine in ('openpyxl', 'xlrd'):
                    try:
                        df = pd.read_excel(abs_path, engine=engine)
                        break
                    except Exception:
                        continue
            if df is None:
                df = pd.read_excel(abs_path)
            if max_rows and len(df) > max_rows:
                df = df.head(max_rows)
            con.register("__tmp_excel__", df)
            con.execute(f"CREATE OR REPLACE VIEW {view} AS SELECT * FROM __tmp_excel__")
            con.unregister("__tmp_excel__")
            return

    raise ValueError(f"Formato não suportado: {file_format}")


def _import_db_table(con, eng, schema: str | None, table_name: str, *, max_rows: int):
    """Import a DB table sample into DuckDB as a local table."""
    t = table_name.strip()
    if not t:
        return
    safe = _sanitize_table_name(t)
    dest = _ident(f"db_{safe}")
    # Select sample
    if schema:
        sql = f'SELECT * FROM "{schema}"."{t}" LIMIT {int(max_rows)}'
    else:
        sql = f'SELECT * FROM "{t}" LIMIT {int(max_rows)}'

    df = pd.read_sql_query(sql, eng)
    con.register("__tmp_db__", df)
    con.execute(f"CREATE OR REPLACE TABLE {dest} AS SELECT * FROM __tmp_db__")
    con.unregister("__tmp_db__")


def execute_workspace_sql(
    workspace_source: DataSource,
    sql_text: str,
    params: dict[str, Any] | None = None,
    *,
    row_limit: int | None = None,
) -> dict[str, Any]:
    """Execute SQL using DuckDB over:

    - selected file assets (registered as views)
    - optional base DB datasource tables (imported as db_<table>)

    This enables JOINs between files and DB samples.
    """

    cfg = decrypt_json(workspace_source.config_encrypted)
    max_rows = int(cfg.get("max_rows", 5000))

    if row_limit is not None:
        try:
            rl = int(row_limit)
            if rl > 0:
                max_rows = min(max_rows, rl)
        except Exception:
            pass

    started = time.time()

    # Connection is per execution (simple + safe)
    con = _duckdb_conn()

    # Register selected files
    from ..models.bi import FileAsset

    files_cfg = cfg.get("files") or []
    if files_cfg:
        # tenant_id is stored in datasource; enforce isolation by querying only those file ids
        file_ids = [int(x.get("file_id")) for x in files_cfg if x.get("file_id")]
        assets = FileAsset.query.filter(FileAsset.tenant_id == workspace_source.tenant_id, FileAsset.id.in_(file_ids)).all()
        by_id = {a.id: a for a in assets}

        for f in files_cfg:
            fid = int(f.get("file_id"))
            alias = _sanitize_table_name(f.get("table") or f"file_{fid}")
            asset = by_id.get(fid)
            if not asset:
                continue
            abs_path = resolve_abs_path(workspace_source.tenant_id, asset.storage_path)
            _register_file_view(con, alias, abs_path, asset.file_format, max_rows)

    # Optionally import DB tables
    base_id = cfg.get("db_source_id")
    if base_id:
        base = DataSource.query.filter_by(id=int(base_id), tenant_id=workspace_source.tenant_id).first()
        if base:
            base_cfg = decrypt_json(base.config_encrypted)
            schema = base_cfg.get("default_schema")
            eng = get_engine(base)
            db_tables_cfg = cfg.get("db_tables")
            if isinstance(db_tables_cfg, str):
                db_tables = [x.strip() for x in db_tables_cfg.split(",") if x.strip()]
            elif isinstance(db_tables_cfg, list):
                db_tables = [str(x).strip() for x in db_tables_cfg if str(x).strip()]
            else:
                db_tables = []
            for t in db_tables[:50]:
                try:
                    _import_db_table(con, eng, schema, t, max_rows=max_rows)
                except Exception:
                    # ignore broken tables
                    continue

    # Execute query
    sql = _rewrite_schema_prefixes(sql_text)
    sql = _rewrite_named_params(sql)
    # Always cap output rows
    cleaned = sql.strip().rstrip(";")
    wrapped = f"SELECT * FROM ({cleaned}) AS __q LIMIT {int(max_rows)}"

    bind_params = params or {}

    # DuckDB is strict: passing extra named parameters raises an error.
    # Keep only params actually referenced in the SQL (e.g. $param).
    if bind_params:
        used = set(re.findall(r"\$([A-Za-z_][A-Za-z0-9_]*)", wrapped))
        bind_params = {k: v for k, v in bind_params.items() if k in used}

    try:
        res = con.execute(wrapped, bind_params)
        cols = [d[0] for d in res.description] if res.description else []
        rows = res.fetchall()
    finally:
        try:
            con.close()
        except Exception:
            pass

    # JSON-safe conversion (basic)
    out_rows: list[list[Any]] = []
    for r in rows:
        row = []
        for v in r:
            if hasattr(v, "isoformat"):
                try:
                    v = v.isoformat()
                except Exception:
                    pass
            row.append(v)
        out_rows.append(row)

    elapsed_ms = int((time.time() - started) * 1000)
    return {"columns": cols, "rows": out_rows, "elapsed_ms": elapsed_ms}


def introspect_workspace(workspace_source: DataSource) -> dict[str, Any]:
    """Return a lightweight catalog for autocomplete.

    Includes:
    - files.<alias> tables with columns from cached schema
    - db.<table> (as db_<table>) columns unknown (MVP)
    """

    cfg = decrypt_json(workspace_source.config_encrypted)
    out: dict[str, Any] = {"schemas": []}

    # Files schema
    from ..models.bi import FileAsset

    files_cfg = cfg.get("files") or []
    file_ids = [int(x.get("file_id")) for x in files_cfg if x.get("file_id")]
    assets = FileAsset.query.filter(FileAsset.tenant_id == workspace_source.tenant_id, FileAsset.id.in_(file_ids)).all() if file_ids else []
    by_id = {a.id: a for a in assets}

    file_tables = []
    for f in files_cfg:
        fid = int(f.get("file_id"))
        alias = _sanitize_table_name(f.get("table") or f"file_{fid}")
        asset = by_id.get(fid)
        if not asset:
            continue
        cols = []
        schema = asset.schema_json or {}
        for c in (schema.get("columns") or []):
            cols.append({"name": c.get("name"), "type": c.get("type")})
        file_tables.append({"name": alias, "columns": cols})

    out["schemas"].append({"name": "files", "tables": file_tables})

    # DB tables (MVP: no columns until first run)
    db_tables_cfg = cfg.get("db_tables")
    if isinstance(db_tables_cfg, str):
        db_tables = [x.strip() for x in db_tables_cfg.split(",") if x.strip()]
    elif isinstance(db_tables_cfg, list):
        db_tables = [str(x).strip() for x in db_tables_cfg if str(x).strip()]
    else:
        db_tables = []

    db_tables_out: list[dict[str, Any]] = []
    base_id = cfg.get("db_source_id")
    if base_id and db_tables:
        base = DataSource.query.filter_by(id=int(base_id), tenant_id=workspace_source.tenant_id).first()
        if base:
            try:
                base_cfg = decrypt_json(base.config_encrypted)
                schema = base_cfg.get("default_schema")
                eng = get_engine(base)
                insp = inspect(eng)
                for t in db_tables[:200]:
                    safe = _sanitize_table_name(t)
                    cols = []
                    try:
                        raw_cols = insp.get_columns(t, schema=schema)
                        cols = [{"name": c.get("name"), "type": str(c.get("type"))} for c in raw_cols]
                    except Exception:
                        cols = []
                    db_tables_out.append({"name": safe, "columns": cols})
            except Exception:
                db_tables_out = [{"name": _sanitize_table_name(t), "columns": []} for t in db_tables[:200]]
        else:
            db_tables_out = [{"name": _sanitize_table_name(t), "columns": []} for t in db_tables[:200]]
    else:
        db_tables_out = [{"name": _sanitize_table_name(t), "columns": []} for t in db_tables[:200]]

    out["schemas"].append({"name": "db", "tables": db_tables_out})

    return out

from __future__ import annotations

from functools import lru_cache
from typing import Any

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine

from ..models.bi import DataSource
from .crypto import decrypt_json


def decrypt_config(source: DataSource) -> dict[str, Any]:
    return decrypt_json(source.config_encrypted)


@lru_cache(maxsize=256)
def _engine_for_source(source_id: int, url: str) -> Engine:
    # pool_pre_ping avoids dead connections for long-lived processes.
    return create_engine(url, pool_pre_ping=True)


def get_engine(source: DataSource) -> Engine:
    cfg = decrypt_config(source)
    url = cfg.get("url")
    if not url:
        raise ValueError("DataSource sem URL de conexão.")
    return _engine_for_source(source.id, url)


def introspect_source(source: DataSource) -> dict[str, Any]:
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
        tables = []
        for tname in sorted(table_names)[:200]:
            try:
                cols = insp.get_columns(tname, schema=schema)
            except Exception:
                cols = []
            tables.append(
                {
                    "name": tname,
                    "columns": [
                        {"name": c.get("name"), "type": str(c.get("type"))} for c in cols
                    ],
                }
            )
        out["schemas"].append({"name": schema_name, "tables": tables})
    return out

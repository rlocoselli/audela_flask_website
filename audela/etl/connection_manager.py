from __future__ import annotations

from typing import Any, Dict, Optional
import urllib.parse

from flask import current_app, g
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from audela.models.etl_catalog import ETLConnection
from audela.etl.crypto import decrypt_json


def _build_url(conn_type: str, data: Dict[str, Any]) -> str:
    ct = (conn_type or "").lower()

    if ct in ("postgres", "postgresql"):
        host = data.get("host", "localhost")
        port = int(data.get("port", 5432))
        database = data.get("database") or data.get("dbname") or data.get("db") or ""
        user = data.get("user") or data.get("username") or ""
        password = data.get("password") or ""
        return (
            "postgresql+psycopg22://"
            f"{urllib.parse.quote_plus(str(user))}:{urllib.parse.quote_plus(str(password))}"
            f"@{host}:{port}/{database}"
        )

    if ct in ("mssql", "sqlserver"):
        # Requires pyodbc + an ODBC driver installed on the host.
        # Option A) full ODBC connect string
        odbc = data.get("odbc_connect")
        if odbc:
            return "mssql+pyodbc:///?odbc_connect=" + urllib.parse.quote_plus(str(odbc))

        # Option B) fields
        host = data.get("host", "localhost")
        port = data.get("port")  # optional
        database = data.get("database") or ""
        user = data.get("user") or data.get("username") or ""
        password = data.get("password") or ""
        driver = data.get("driver", "ODBC Driver 17 for SQL Server")
        server = f"{host},{port}" if port else str(host)

        return (
            "mssql+pyodbc://"
            f"{urllib.parse.quote_plus(str(user))}:{urllib.parse.quote_plus(str(password))}"
            f"@{server}/{database}?driver={urllib.parse.quote_plus(str(driver))}"
        )

    if ct == "sqlite":
        url = data.get("url")
        if url:
            return str(url)
        path = data.get("path") or data.get("filepath") or data.get("file") or "instance/app.sqlite"
        if str(path).startswith("/"):
            return f"sqlite:///{path}"
        return f"sqlite:///{path}"

    raise ValueError(f"Unsupported connection type: {conn_type}")


def get_engine_for_connection(connection_name: str, *, app=None) -> Engine:
    """Return SQLAlchemy Engine for a connection name from the catalog.
    Engines are cached per-request in flask.g to avoid recreating them.
    """
    if not connection_name:
        raise ValueError("connection_name is required")

    cache = getattr(g, "_etl_engines", None)
    if cache is None:
        cache = {}
        setattr(g, "_etl_engines", cache)

    if connection_name in cache:
        return cache[connection_name]

    app = app or current_app
    conn = ETLConnection.query.filter_by(name=connection_name).first()
    if not conn:
        raise ValueError(f"Unknown connection: {connection_name}")

    data = decrypt_json(app, conn.encrypted_payload)
    url = _build_url(conn.type, data)

    engine = create_engine(url, pool_pre_ping=True, future=True)
    cache[connection_name] = engine
    return engine

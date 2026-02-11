from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import Table, Column, MetaData, inspect, text
from sqlalchemy.engine import Engine

from .schema_infer import infer_columns, normalize_col_name

def ensure_table(engine: Engine, *, schema: str, table_name: str, rows: List[Dict[str, Any]],
                 create_table_if_missing: bool = True,
                 add_columns_if_missing: bool = True) -> Table:
    if not table_name:
        raise ValueError("table_name required")

    table_name = normalize_col_name(table_name)
    schema = schema or "public"
    inspector = inspect(engine)
    metadata = MetaData(schema=schema)

    has = inspector.has_table(table_name, schema=schema)
    cols_map = {}
    if rows:
        # normalize keys in rows too (in-place copy)
        norm_rows = []
        for r in rows:
            nr = {normalize_col_name(k): v for k, v in r.items()}
            norm_rows.append(nr)
        rows[:] = norm_rows
        cols_map = infer_columns(rows)

    if not has:
        if not create_table_if_missing:
            raise ValueError(f"Target table {schema}.{table_name} does not exist")
        columns = [Column("etl_loaded_at", text("CURRENT_TIMESTAMP").type, nullable=True)]
        for k, t in cols_map.items():
            columns.append(Column(k, t))
        table = Table(table_name, metadata, *columns)
        metadata.create_all(engine, tables=[table])
        return table

    # Reflect existing table
    table = Table(table_name, metadata, autoload_with=engine)

    if add_columns_if_missing and cols_map:
        existing = {c.name for c in table.columns}
        for k, t in cols_map.items():
            if k not in existing:
                # Dialect-specific compilation for type
                coltype_sql = t().compile(dialect=engine.dialect)
                stmt = text(f'ALTER TABLE "{schema}"."{table_name}" ADD COLUMN "{k}" {coltype_sql}')
                with engine.begin() as conn:
                    conn.execute(stmt)
        # re-reflect after alter
        metadata2 = MetaData(schema=schema)
        table = Table(table_name, metadata2, autoload_with=engine)

    return table
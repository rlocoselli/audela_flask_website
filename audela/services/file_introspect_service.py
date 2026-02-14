from __future__ import annotations

import csv
from typing import Any, Optional

import pandas as pd


def infer_schema_for_asset(asset: Any, *, max_rows: int = 200) -> dict[str, Any]:
    """Helper used by portal routes (kept for compatibility).

    The portal stores uploaded files as FileAsset objects. This function
    resolves the absolute path inside the tenant storage root and returns
    a lightweight schema for autocomplete/IA.

    Expects an object with attributes: tenant_id, storage_path, file_format.
    """
    try:
        tenant_id = int(getattr(asset, "tenant_id"))
        storage_path = str(getattr(asset, "storage_path"))
        file_format = str(getattr(asset, "file_format"))
    except Exception:
        return {"columns": []}

    from .file_storage_service import resolve_abs_path

    try:
        abs_path = resolve_abs_path(tenant_id, storage_path)
        return introspect_file_schema(abs_path, file_format, max_rows=max_rows)
    except Exception:
        # Do not break uploads if schema inference fails
        return {"columns": []}


def _dtype_to_str(dtype: Any) -> str:
    try:
        return str(dtype)
    except Exception:
        return "unknown"


def sniff_csv_delimiter(path: str) -> Optional[str]:
    """Best-effort delimiter detection."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            sample = f.read(8192)
        if not sample.strip():
            return None
        dialect = csv.Sniffer().sniff(sample, delimiters=[",", ";", "\t", "|"])
        return dialect.delimiter
    except Exception:
        return None


def _read_excel_any(path: str, *, nrows: int | None = None) -> pd.DataFrame:
    """Read Excel files (xls/xlsx) with engine fallbacks.

    Some uploads may have a mismatched extension; we try the common engines.
    """
    read_kwargs = {}
    if nrows is not None:
        read_kwargs['nrows'] = nrows

    # Default auto-engine first
    try:
        return pd.read_excel(path, **read_kwargs)
    except Exception:
        pass

    # Try explicit engines
    for engine in ('openpyxl', 'xlrd'):
        try:
            return pd.read_excel(path, engine=engine, **read_kwargs)
        except Exception:
            continue

    # Re-raise with original behavior
    return pd.read_excel(path, **read_kwargs)


def introspect_file_schema(path: str, file_format: str, *, max_rows: int = 200) -> dict[str, Any]:
    """Return a lightweight schema for autocomplete.

    Shape:
      {"columns": [{"name": "col", "type": "int64"}, ...]}

    Notes:
    - CSV: tries to sniff delimiter.
    - Excel: reads first sheet by default.
    - Parquet: requires pyarrow/fastparquet (will raise if missing).
    """
    fmt = (file_format or "").lower().strip()
    if fmt in ("xlsx", "xls", "excel"):
        df = _read_excel_any(path, nrows=max_rows)
    elif fmt == "csv":
        delim = sniff_csv_delimiter(path) or ","
        # Try utf-8 first; fallback Latin-1
        try:
            df = pd.read_csv(path, sep=delim, nrows=max_rows)
        except UnicodeDecodeError:
            df = pd.read_csv(path, sep=delim, nrows=max_rows, encoding="latin-1")
    elif fmt == "parquet":
        df = pd.read_parquet(path)
        if len(df) > max_rows:
            df = df.head(max_rows)
    else:
        raise ValueError(f"Formato não suportado: {file_format}")

    cols = []
    for c in df.columns:
        cols.append({"name": str(c), "type": _dtype_to_str(df[c].dtype)})
    return {"columns": cols}


def dataframe_from_file(path: str, file_format: str) -> pd.DataFrame:
    fmt = (file_format or "").lower().strip()
    if fmt in ("xlsx", "xls", "excel"):
        return _read_excel_any(path)
    if fmt == "csv":
        delim = sniff_csv_delimiter(path) or ","
        try:
            return pd.read_csv(path, sep=delim)
        except UnicodeDecodeError:
            return pd.read_csv(path, sep=delim, encoding="latin-1")
    if fmt == "parquet":
        return pd.read_parquet(path)
    raise ValueError(f"Formato não suportado: {file_format}")

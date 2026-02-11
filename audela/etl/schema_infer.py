from __future__ import annotations

from typing import Any, Dict, List, Tuple
from datetime import datetime, date
from sqlalchemy import Integer, Float, Boolean, DateTime, Text, JSON, Numeric

def infer_sqlalchemy_type(value: Any):
    if value is None:
        return Text
    if isinstance(value, bool):
        return Boolean
    if isinstance(value, int):
        # Python int can overflow DB int; keep Integer for MVP
        return Integer
    if isinstance(value, float):
        return Float
    if isinstance(value, (datetime, date)):
        return DateTime
    if isinstance(value, (dict, list)):
        return JSON
    return Text

def infer_columns(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not rows:
        return {}
    # infer from first non-null sample for each key
    cols: Dict[str, Any] = {}
    for row in rows[:50]:
        for k, v in row.items():
            if k not in cols and v is not None:
                cols[k] = infer_sqlalchemy_type(v)
    # fallback for keys never seen non-null
    for k in rows[0].keys():
        cols.setdefault(k, Text)
    return cols

def normalize_col_name(name: str) -> str:
    # simple snake-ish normalization (keep alnum and _)
    out = []
    for ch in name.strip():
        if ch.isalnum():
            out.append(ch.lower())
        elif ch in (" ", "-", ".", "/"):
            out.append("_")
        elif ch == "_":
            out.append("_")
    s = "".join(out)
    while "__" in s:
        s = s.replace("__", "_")
    return s.strip("_") or "col"
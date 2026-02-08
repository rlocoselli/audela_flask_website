from __future__ import annotations

import json
import os
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import requests

from ..i18n import tr
from ..models.bi import DataSource
from .datasource_service import decrypt_config, get_engine, introspect_source


_READONLY_PREFIXES = ("select", "with", "show", "describe", "explain")


def _env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    if v is None or v == "":
        return default
    return v


def _strip_sql_comments(sql: str) -> str:
    sql = re.sub(r"--.*?\n", "\n", sql)
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    return sql


def _is_readonly(sql: str) -> bool:
    cleaned = _strip_sql_comments(sql).strip().lstrip("(").strip()
    if not cleaned:
        return False
    first = cleaned.split(None, 1)[0].lower()
    return first in _READONLY_PREFIXES


def _json_default(o: Any):
    if isinstance(o, Decimal):
        return float(o)
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    return str(o)


def _tokenize(text: str) -> list[str]:
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9_\-\s]+", " ", text)
    return [t for t in text.split() if t]


def _find_best_table(meta: dict[str, Any], tokens: list[str]) -> str | None:
    tables: list[str] = []
    for s in meta.get("schemas", []):
        for t in s.get("tables", []):
            if t.get("name"):
                tables.append(str(t["name"]))

    if not tables:
        return None

    for tok in tokens:
        for tname in tables:
            if tok == tname.lower():
                return tname

    for tok in tokens:
        for tname in tables:
            if tok in tname.lower() and len(tok) >= 3:
                return tname

    if len(tables) == 1:
        return tables[0]

    return None


def _columns_for_table(meta: dict[str, Any], table_name: str) -> list[str]:
    for s in meta.get("schemas", []):
        for t in s.get("tables", []):
            if str(t.get("name")) == table_name:
                return [str(c.get("name")) for c in t.get("columns", []) if c.get("name")]
    return []


def _pick_column_by_token(columns: list[str], token: str) -> str | None:
    if not token:
        return None
    token = token.lower()
    for c in columns:
        if c.lower() == token:
            return c
    for c in columns:
        if token in c.lower() and len(token) >= 3:
            return c
    return None


def _heuristic_generate_sql_from_nl(source: DataSource, text: str, lang: str | None = None) -> tuple[str, list[str]]:
    """Heuristic natural-language -> SQL suggestion.

    Conservative: produces a starting point the user can edit.
    """
    warnings: list[str] = []
    meta = introspect_source(source)
    tokens = _tokenize(text)

    table = _find_best_table(meta, tokens)
    if not table:
        return (
            f"-- {tr('Não foi possível identificar uma tabela com segurança.', lang)}\n"
            f"-- {tr('Selecione uma tabela no Query Builder (à direita) ou escreva o SQL manualmente.', lang)}\n\n"
            "SELECT *\nFROM <tabela>\nLIMIT 100",
            [tr("Tabela não identificada", lang)],
        )

    columns = _columns_for_table(meta, table)

    count_kw = {"count", "quantos", "cantidad", "combien", "wie", "anzahl", "conteggio"}
    sum_kw = {"sum", "total", "soma", "somma", "somme", "summe"}
    avg_kw = {"avg", "average", "média", "media", "moyenne", "durchschnitt"}
    by_kw = {"by", "por", "par", "per", "nach", "grupo", "group"}

    agg: str | None = None
    if any(t in count_kw for t in tokens):
        agg = "count"
    if any(t in sum_kw for t in tokens):
        agg = "sum"
    if any(t in avg_kw for t in tokens):
        agg = "avg"

    dim_col: str | None = None
    for i, tok in enumerate(tokens[:-1]):
        if tok in by_kw:
            candidate = tokens[i + 1]
            dim_col = _pick_column_by_token(columns, candidate)
            if dim_col:
                break

    metric_col: str | None = None
    of_kw = {"of", "de", "du", "del", "di", "von"}
    for i, tok in enumerate(tokens[:-1]):
        if tok in of_kw:
            metric_col = _pick_column_by_token(columns, tokens[i + 1])
            if metric_col:
                break

    if agg in ("sum", "avg") and not metric_col:
        for prefer in (
            "amount",
            "total",
            "value",
            "valor",
            "montant",
            "importo",
            "preis",
            "qty",
            "quant",
            "count",
        ):
            for c in columns:
                if prefer in c.lower():
                    metric_col = c
                    break
            if metric_col:
                break
        if not metric_col and columns:
            metric_col = columns[-1]
            warnings.append(tr("Coluna métrica escolhida por fallback", lang))

    cfg = decrypt_config(source)
    tenant_column = cfg.get("tenant_column")
    tenant_where = ""
    if tenant_column:
        tenant_where = f"WHERE {tenant_column} = :tenant_id\n"

    if agg and dim_col:
        if agg == "count":
            select_expr = "COUNT(*) AS total"
        else:
            if not metric_col:
                metric_col = "<coluna_metrica>"
                warnings.append(tr("Coluna métrica não identificada", lang))
            select_expr = f"{agg.upper()}({metric_col}) AS value"

        sql = (
            f"SELECT\n  {dim_col} AS dimension,\n  {select_expr}\n"
            f"FROM {table}\n"
            f"{tenant_where}"
            f"GROUP BY {dim_col}\n"
            f"ORDER BY 2 DESC\n"
            "LIMIT 500"
        )
        return sql, warnings

    if agg and not dim_col:
        if agg == "count":
            select_expr = "COUNT(*) AS total"
        else:
            if not metric_col:
                metric_col = "<coluna_metrica>"
                warnings.append(tr("Coluna métrica não identificada", lang))
            select_expr = f"{agg.upper()}({metric_col}) AS value"
        sql = f"SELECT {select_expr}\nFROM {table}\n{tenant_where}".rstrip() + "\n"
        return sql, warnings

    sql = f"SELECT *\nFROM {table}\n{tenant_where}LIMIT 100"
    if not text.strip():
        warnings.append(tr("Texto vazio", lang))
    return sql, warnings


def _openai_generate_sql_from_nl(source: DataSource, text: str, lang: str | None = None) -> tuple[str, list[str]]:
    """LLM-based NLQ -> SQL using OpenAI, grounded on schema."""
    api_key = _env("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY missing")

    model = _env("OPENAI_MODEL", "gpt-4o-mini")
    base_url = _env("OPENAI_BASE_URL", "https://api.openai.com/v1")

    text = (text or "").strip()
    if not text:
        return _heuristic_generate_sql_from_nl(source, text, lang=lang)

    cfg = decrypt_config(source)
    meta = introspect_source(source)

    dialect = "unknown"
    try:
        dialect = get_engine(source).dialect.name
    except Exception:
        dialect = "unknown"

    rules = {
        "dialect": dialect,
        "read_only": True,
        "must_use_only_provided_schema": True,
        "always_include_limit": True,
        "limit_default": 500,
        "tenant_column": cfg.get("tenant_column") or "",
        "require_tenant_placeholder": bool(cfg.get("tenant_column")),
        "tenant_placeholder": ":tenant_id",
    }

    # Compact schema payload to reduce tokens
    schemas_compact: list[dict[str, Any]] = []
    for sc in meta.get("schemas", [])[:5]:
        sc_tables = []
        for t in (sc.get("tables", []) or [])[:200]:
            cols = [c.get("name") for c in (t.get("columns", []) or []) if c.get("name")]
            sc_tables.append({"name": t.get("name"), "columns": cols[:300]})
        schemas_compact.append({"name": sc.get("name"), "tables": sc_tables})

    context = {"schema": {"schemas": schemas_compact}, "rules": rules}

    sys_prompt = (
        "You are a SQL assistant for a BI portal.\n"
        "Return ONLY valid JSON with keys: sql, warnings.\n"
        "The SQL must be READ-ONLY (SELECT/WITH/SHOW/DESCRIBE/EXPLAIN).\n"
        "Use ONLY the provided schema tables/columns.\n"
        "If rules.require_tenant_placeholder is true, SQL MUST include ':tenant_id' in WHERE.\n"
        "Always include a LIMIT (rules.limit_default) unless user explicitly requests full export.\n"
        "Do not include markdown fences.\n"
    )

    messages = [
        {"role": "system", "content": sys_prompt},
        {
            "role": "user",
            "content": (
                "CONTEXT (JSON):\n"
                + json.dumps(context, ensure_ascii=False, default=_json_default)
                + "\n\nUSER REQUEST:\n"
                + text
            ),
        },
    ]

    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {
        "model": model,
        "messages": messages,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }

    r = requests.post(url, headers=headers, json=body, timeout=60)
    if r.status_code >= 400:
        # retry without response_format for older backends
        body.pop("response_format", None)
        r = requests.post(url, headers=headers, json=body, timeout=60)
    r.raise_for_status()
    data = r.json()
    content = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""

    try:
        parsed = json.loads(content)
    except Exception:
        parsed = {}

    sql = (parsed.get("sql") or "").strip() if isinstance(parsed, dict) else ""
    warnings = parsed.get("warnings") if isinstance(parsed, dict) else []
    if not isinstance(warnings, list):
        warnings = []

    if not sql:
        raise RuntimeError("LLM did not return sql")

    # Server-side safety validation
    if not _is_readonly(sql):
        raise RuntimeError("SQL gerado não é somente leitura")

    # Hard block list as extra defense
    if re.search(r"\b(insert|update|delete|drop|alter|truncate|create)\b", sql, flags=re.I):
        raise RuntimeError("SQL gerado contém comandos não permitidos")

    if rules["require_tenant_placeholder"] and ":tenant_id" not in sql:
        raise RuntimeError("Fonte exige tenant, mas SQL gerado não incluiu :tenant_id")

    return sql, [str(w) for w in warnings[:8]]


def generate_sql_from_nl(source: DataSource, text: str, lang: str | None = None) -> tuple[str, list[str]]:
    """Natural language -> SQL.

    Behavior:
    - If OPENAI_API_KEY is configured, use OpenAI grounded on schema.
    - Otherwise, fall back to the existing heuristic generator.
    """
    if _env("OPENAI_API_KEY"):
        try:
            return _openai_generate_sql_from_nl(source, text, lang=lang)
        except Exception as e:  # noqa: BLE001
            sql, warnings = _heuristic_generate_sql_from_nl(source, text, lang=lang)
            warnings = warnings or []
            warnings.insert(0, f"{tr('Falha ao usar OpenAI; usando fallback heurístico.', lang)}: {e}")
            return sql, warnings

    return _heuristic_generate_sql_from_nl(source, text, lang=lang)

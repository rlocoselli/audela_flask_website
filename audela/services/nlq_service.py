from __future__ import annotations

import re
from typing import Any

from ..models.bi import DataSource
from .datasource_service import decrypt_config, introspect_source
from ..i18n import tr


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

    # Exact token match on table name first
    for tok in tokens:
        for tname in tables:
            if tok == tname.lower():
                return tname

    # Partial match
    for tok in tokens:
        for tname in tables:
            if tok in tname.lower() and len(tok) >= 3:
                return tname

    # Single table fallback
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


def generate_sql_from_nl(source: DataSource, text: str, lang: str | None = None) -> tuple[str, list[str]]:
    """Heuristic natural-language -> SQL suggestion.

    This is intentionally conservative: it aims to produce *a starting point* that the user can edit.
    For production-grade NLQ, plug in a dedicated LLM provider.
    """

    warnings: list[str] = []
    meta = introspect_source(source)
    tokens = _tokenize(text)

    table = _find_best_table(meta, tokens)
    if not table:
        # Provide a safe scaffold.
        return (
            f"-- {tr('Não foi possível identificar uma tabela com segurança.', lang)}\n"
            f"-- {tr('Selecione uma tabela no Query Builder (à direita) ou escreva o SQL manualmente.', lang)}\n\n"
            "SELECT *\nFROM <tabela>\nLIMIT 100",
            [tr("Tabela não identificada", lang)],
        )

    columns = _columns_for_table(meta, table)

    # Keywords across supported languages
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

    # Dimension after a "by"-like token
    dim_col: str | None = None
    for i, tok in enumerate(tokens[:-1]):
        if tok in by_kw:
            candidate = tokens[i + 1]
            dim_col = _pick_column_by_token(columns, candidate)
            if dim_col:
                break

    # Metric column
    metric_col: str | None = None
    # Look for "of/de/du/del/di/von" patterns
    of_kw = {"of", "de", "du", "del", "di", "von"}
    for i, tok in enumerate(tokens[:-1]):
        if tok in of_kw:
            metric_col = _pick_column_by_token(columns, tokens[i + 1])
            if metric_col:
                break

    # Fallback: use a likely numeric-ish column name for sum/avg
    if agg in ("sum", "avg") and not metric_col:
        for prefer in ("amount", "total", "value", "valor", "montant", "importo", "preis", "qty", "quant", "count"):
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
            select_expr = f"COUNT(*) AS total"
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

    # Default: sample rows
    sql = f"SELECT *\nFROM {table}\n{tenant_where}LIMIT 100"
    if not text.strip():
        warnings.append(tr("Texto vazio", lang))
    return sql, warnings

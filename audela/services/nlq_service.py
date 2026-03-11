from __future__ import annotations

import json
import os
import re
from datetime import date, datetime
from decimal import Decimal
from itertools import combinations
from typing import Any

import requests
from sqlalchemy import inspect as sqla_inspect

from ..i18n import tr
from ..models.bi import DataSource
from .ai_runtime_config import resolve_ai_runtime_config
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


def _single_sql_statement(sql: str) -> tuple[str, bool]:
    """Keep only the first SQL statement.

    Returns (statement, had_extra_statements).
    """
    s = _strip_sql_comments(str(sql or "")).strip()
    if not s:
        return "", False

    in_single = False
    in_double = False
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "'" and not in_double:
            # SQL single-quote escape: ''
            if in_single and i + 1 < len(s) and s[i + 1] == "'":
                i += 2
                continue
            in_single = not in_single
        elif ch == '"' and not in_single:
            # Identifier quote escape: ""
            if in_double and i + 1 < len(s) and s[i + 1] == '"':
                i += 2
                continue
            in_double = not in_double
        elif ch == ";" and not in_single and not in_double:
            first = s[:i].strip()
            rest = s[i + 1 :].strip()
            if first:
                return first, bool(rest)
        i += 1

    return s.rstrip(";").strip(), False


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


def _normalize_table_ref(name: str) -> str:
    raw = str(name or "").strip()
    if not raw:
        return ""
    parts = [p.strip().strip('"`[]') for p in raw.split(".") if p and str(p).strip()]
    return ".".join(parts).lower()


def _meta_has_tables(meta: dict[str, Any]) -> bool:
    for sc in (meta.get("schemas") or []):
        if (sc.get("tables") or []):
            return True
    return False


def _filter_meta_to_allowed_tables(meta: dict[str, Any], allowed_tables: list[str]) -> dict[str, Any]:
    allowed_full: set[str] = set()
    allowed_bare: set[str] = set()
    for name in (allowed_tables or []):
        norm = _normalize_table_ref(name)
        if not norm:
            continue
        allowed_full.add(norm)
        allowed_bare.add(norm.split(".")[-1])

    if not allowed_full:
        return meta

    filtered_schemas: list[dict[str, Any]] = []
    for sc in (meta.get("schemas") or []):
        schema_name = str(sc.get("name") or "").strip()
        kept_tables: list[dict[str, Any]] = []
        for tbl in (sc.get("tables") or []):
            table_name = str(tbl.get("name") or "").strip()
            if not table_name:
                continue

            full_name = f"{schema_name}.{table_name}" if schema_name else table_name
            full_norm = _normalize_table_ref(full_name)
            bare_norm = _normalize_table_ref(table_name)
            if full_norm in allowed_full or bare_norm in allowed_bare:
                kept_tables.append(tbl)

        if kept_tables:
            sc_copy = dict(sc)
            sc_copy["tables"] = kept_tables
            filtered_schemas.append(sc_copy)

    meta_copy = dict(meta)
    meta_copy["schemas"] = filtered_schemas
    return meta_copy


def _table_display_name(schema_name: str, table_name: str) -> str:
    sc = str(schema_name or "").strip()
    tb = str(table_name or "").strip()
    if not tb:
        return ""
    if not sc or sc.lower() in {"default", "none"}:
        return tb
    return f"{sc}.{tb}"


def _build_relationship_hints(
    source: DataSource,
    meta: dict[str, Any],
    required_tables: list[str] | None = None,
) -> dict[str, Any]:
    selected_full = {_normalize_table_ref(t) for t in (required_tables or []) if _normalize_table_ref(t)}
    selected_bare = {x.split(".")[-1] for x in selected_full}

    table_defs: list[dict[str, Any]] = []
    columns_by_table: dict[str, set[str]] = {}
    for sc in (meta.get("schemas") or []):
        schema_name = str(sc.get("name") or "").strip()
        inspector_schema = None if not schema_name or schema_name.lower() in {"default", "none"} else schema_name
        for tbl in (sc.get("tables") or []):
            table_name = str(tbl.get("name") or "").strip()
            if not table_name:
                continue
            display = _table_display_name(schema_name, table_name)
            full_norm = _normalize_table_ref(display)
            bare_norm = _normalize_table_ref(table_name)
            if selected_full and full_norm not in selected_full and bare_norm not in selected_bare:
                continue
            table_defs.append(
                {
                    "schema": inspector_schema,
                    "schema_display": schema_name,
                    "table": table_name,
                    "display": display,
                    "norm": full_norm,
                    "bare": bare_norm,
                }
            )
            colset: set[str] = set()
            for c in (tbl.get("columns") or []):
                cname = str((c or {}).get("name") or "").strip().lower()
                if cname:
                    colset.add(cname)
            columns_by_table[display] = colset

    if not table_defs:
        return {"foreign_keys": [], "natural_keys": []}

    fk_hints: list[dict[str, Any]] = []
    seen_fk: set[str] = set()
    fk_pairs: set[tuple[str, str]] = set()
    try:
        insp = sqla_inspect(get_engine(source))
    except Exception:
        insp = None

    if insp is not None:
        for td in table_defs:
            try:
                fks = insp.get_foreign_keys(td["table"], schema=td["schema"]) or []
            except Exception:
                fks = []
            for fk in fks:
                ref_table = str(fk.get("referred_table") or "").strip()
                if not ref_table:
                    continue
                ref_schema = str(fk.get("referred_schema") or "").strip()
                ref_display = _table_display_name(ref_schema, ref_table)
                ref_norm = _normalize_table_ref(ref_display)
                ref_bare = _normalize_table_ref(ref_table)
                if selected_full and ref_norm not in selected_full and ref_bare not in selected_bare:
                    continue

                left_cols = [str(c or "").strip() for c in (fk.get("constrained_columns") or []) if str(c or "").strip()]
                right_cols = [str(c or "").strip() for c in (fk.get("referred_columns") or []) if str(c or "").strip()]
                if not left_cols or not right_cols:
                    continue

                cond_parts = []
                for lc, rc in zip(left_cols, right_cols):
                    cond_parts.append(f"{td['display']}.{lc} = {ref_display}.{rc}")
                if not cond_parts:
                    continue

                key = f"{td['display']}|{ref_display}|{'&'.join(cond_parts)}"
                if key in seen_fk:
                    continue
                seen_fk.add(key)
                fk_pairs.add(tuple(sorted([td["display"], ref_display])))
                fk_hints.append(
                    {
                        "left_table": td["display"],
                        "right_table": ref_display,
                        "left_columns": left_cols,
                        "right_columns": right_cols,
                        "join_condition": " AND ".join(cond_parts),
                        "confidence": "foreign_key",
                    }
                )
                if len(fk_hints) >= 120:
                    break

    key_like_cols = {
        "id",
        "tenant_id",
        "company_id",
        "organization_id",
        "org_id",
        "customer_id",
        "client_id",
        "user_id",
        "account_id",
        "order_id",
        "invoice_id",
        "product_id",
        "sku",
        "email",
        "phone",
        "cpf",
        "cnpj",
    }
    natural_hints: list[dict[str, Any]] = []
    table_names = list(columns_by_table.keys())[:60]
    for a, b in combinations(table_names, 2):
        if tuple(sorted([a, b])) in fk_pairs:
            continue
        common = columns_by_table.get(a, set()) & columns_by_table.get(b, set())
        if not common:
            continue
        candidates = [c for c in sorted(common) if c.endswith("_id") or c in key_like_cols]
        if not candidates:
            continue
        chosen = candidates[:2]
        cond = " AND ".join([f"{a}.{c} = {b}.{c}" for c in chosen])
        natural_hints.append(
            {
                "left_table": a,
                "right_table": b,
                "columns": chosen,
                "join_condition": cond,
                "confidence": "natural_key",
            }
        )
        if len(natural_hints) >= 80:
            break

    return {"foreign_keys": fk_hints, "natural_keys": natural_hints}


def _extract_sql_from_join_tables(sql: str) -> list[str]:
    """Extract table references from FROM/JOIN clauses (best effort)."""
    cleaned = _strip_sql_comments(str(sql or ""))
    refs = re.findall(r"\b(?:from|join)\s+([\w\"`\[\]\.]+)", cleaned, flags=re.I)
    out: list[str] = []
    for ref in refs:
        raw = str(ref or "").strip()
        if not raw:
            continue
        if raw.startswith("("):
            continue
        norm = _normalize_table_ref(raw)
        if norm:
            out.append(norm)
    return out


def _enforce_selected_table_scope(
    sql: str,
    warnings: list[str],
    allowed_tables: list[str],
    *,
    lang: str | None = None,
    require_all_allowed_tables: bool = False,
) -> tuple[str, list[str]]:
    if not allowed_tables:
        return sql, warnings

    allowed_full = {_normalize_table_ref(x) for x in allowed_tables if _normalize_table_ref(x)}
    allowed_bare = {x.split(".")[-1] for x in allowed_full}
    refs = _extract_sql_from_join_tables(sql)
    if not refs:
        return sql, warnings

    invalid: list[str] = []
    used_full = set(refs)
    used_bare = {ref.split(".")[-1] for ref in refs}
    for ref in refs:
        bare = ref.split(".")[-1]
        if ref in allowed_full or bare in allowed_bare:
            continue
        invalid.append(ref)

    if invalid:
        msg = tr("SQL gerado usou tabela fora da seleção permitida.", lang)
        detail = ", ".join(sorted(set(invalid))[:4])
        return "", [f"{msg} ({detail})"]

    if require_all_allowed_tables and allowed_full:
        missing: list[str] = []
        for ref in sorted(allowed_full):
            bare = ref.split(".")[-1]
            if ref in used_full or bare in used_bare:
                continue
            missing.append(ref)
        if missing:
            msg = tr("SQL gerado não utilizou todas as tabelas selecionadas.", lang)
            detail = ", ".join(missing[:6])
            return "", [f"{msg} ({detail})"]

    return sql, warnings


def _heuristic_generate_sql_from_nl(
    source: DataSource,
    text: str,
    lang: str | None = None,
    schema_meta: dict[str, Any] | None = None,
) -> tuple[str, list[str]]:
    """Heuristic natural-language -> SQL suggestion.

    Conservative: produces a starting point the user can edit.
    """
    warnings: list[str] = []
    meta = schema_meta if isinstance(schema_meta, dict) else introspect_source(source)
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


def _openai_generate_sql_from_nl(
    source: DataSource,
    text: str,
    lang: str | None = None,
    schema_meta: dict[str, Any] | None = None,
    required_tables: list[str] | None = None,
    timeout_seconds: int | None = None,
) -> tuple[str, list[str]]:
    """LLM-based NLQ -> SQL using OpenAI, grounded on schema."""
    runtime = resolve_ai_runtime_config(default_model="gpt-4o-mini")
    api_key = runtime.get("api_key")
    if not api_key:
        raise RuntimeError(f"{runtime.get('missing_key_env') or 'OPENAI_API_KEY'} missing")

    model = runtime.get("model") or "gpt-4o-mini"
    base_url = runtime.get("base_url") or "https://api.openai.com/v1"

    text = (text or "").strip()
    if not text:
        return _heuristic_generate_sql_from_nl(source, text, lang=lang)

    cfg = decrypt_config(source)
    meta = schema_meta if isinstance(schema_meta, dict) else introspect_source(source)

    dialect = "unknown"
    try:
        dialect = get_engine(source).dialect.name
    except Exception:
        dialect = "unknown"

    rules = {
        "dialect": dialect,
        "read_only": True,
        "must_use_only_provided_schema": True,
        "required_tables": [str(t) for t in (required_tables or []) if str(t).strip()],
        "must_join_required_tables": bool(required_tables),
        "join_using_relationship_hints": True,
        "always_include_limit": True,
        "limit_default": 500,
        "tenant_column": cfg.get("tenant_column") or "",
        "require_tenant_placeholder": bool(cfg.get("tenant_column")),
        "tenant_placeholder": ":tenant_id",
    }

    # Compact schema payload to reduce tokens
    include_col_types = bool(required_tables)
    schemas_compact: list[dict[str, Any]] = []
    for sc in meta.get("schemas", [])[:5]:
        sc_tables = []
        for t in (sc.get("tables", []) or [])[:200]:
            if include_col_types:
                cols = [
                    {
                        "name": c.get("name"),
                        "type": str(c.get("type") or ""),
                    }
                    for c in (t.get("columns", []) or [])
                    if c.get("name")
                ]
            else:
                cols = [c.get("name") for c in (t.get("columns", []) or []) if c.get("name")]
            sc_tables.append({"name": t.get("name"), "kind": t.get("kind") or "table", "columns": cols[:300]})
        schemas_compact.append({"name": sc.get("name"), "tables": sc_tables})

    relationships = _build_relationship_hints(source, meta, rules.get("required_tables") or [])
    context = {"schema": {"schemas": schemas_compact}, "relationships": relationships, "rules": rules}

    sys_prompt = (
        "You are a SQL assistant for a BI portal.\n"
        "Return ONLY valid JSON with keys: sql, warnings.\n"
        "The SQL must be READ-ONLY (SELECT/WITH/SHOW/DESCRIBE/EXPLAIN).\n"
        "Use ONLY the provided schema tables/columns.\n"
        "If rules.required_tables is non-empty, SQL MUST reference ALL those tables (JOIN when needed).\n"
        "If rules.must_join_required_tables is true and multiple required tables exist, build one connected query joining all of them.\n"
        "Use context.relationships.foreign_keys first for JOIN conditions; if missing, use context.relationships.natural_keys.\n"
        "Never use cartesian joins; every JOIN must have an ON condition.\n"
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

    read_timeout = max(5, int(timeout_seconds if timeout_seconds is not None else (runtime.get("read_timeout_seconds") or runtime.get("timeout_seconds") or 600)))
    connect_timeout = max(3, int(runtime.get("connect_timeout_seconds") or min(10, read_timeout)))
    req_timeout: tuple[int, int] = (connect_timeout, read_timeout)

    r = requests.post(url, headers=headers, json=body, timeout=req_timeout)
    if r.status_code >= 400:
        # retry without response_format for older backends
        body.pop("response_format", None)
        r = requests.post(url, headers=headers, json=body, timeout=req_timeout)
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

    sql, had_extra = _single_sql_statement(sql)
    if had_extra:
        warnings.append(tr("Apenas a primeira instrução SQL foi considerada; instruções adicionais foram descartadas.", lang))

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


def generate_sql_from_nl(
    source: DataSource,
    text: str,
    lang: str | None = None,
    allowed_tables: list[str] | None = None,
    require_all_allowed_tables: bool = False,
    timeout_seconds: int | None = None,
    allow_scope_retry: bool = True,
) -> tuple[str, list[str]]:
    """Natural language -> SQL.

    Behavior:
    - If an AI runtime API key is available, use LLM grounded on schema.
    - Otherwise, fall back to the existing heuristic generator.
    """
    runtime = resolve_ai_runtime_config(default_model="gpt-4o-mini")

    selected_tables: list[str] = []
    if isinstance(allowed_tables, list):
        seen: set[str] = set()
        for item in allowed_tables:
            norm = _normalize_table_ref(str(item or ""))
            if not norm or norm in seen:
                continue
            seen.add(norm)
            selected_tables.append(norm)

    schema_meta: dict[str, Any] | None = None
    if selected_tables:
        try:
            base_meta = introspect_source(source)
        except Exception:
            base_meta = {"schemas": []}
        schema_meta = _filter_meta_to_allowed_tables(base_meta, selected_tables)
        if not _meta_has_tables(schema_meta):
            return "", [tr("Nenhuma das tabelas selecionadas foi encontrada nesta fonte.", lang)]

    if runtime.get("api_key"):
        try:
            sql, warnings = _openai_generate_sql_from_nl(
                source,
                text,
                lang=lang,
                schema_meta=schema_meta,
                required_tables=selected_tables,
                timeout_seconds=timeout_seconds,
            )
        except Exception as e:  # noqa: BLE001
            sql, warnings = _heuristic_generate_sql_from_nl(source, text, lang=lang, schema_meta=schema_meta)
            warnings = warnings or []
            warnings.insert(0, f"{tr('Falha ao usar OpenAI; usando fallback heurístico.', lang)}: {e}")
        scoped_sql, scoped_warnings = _enforce_selected_table_scope(
            sql,
            warnings or [],
            selected_tables,
            lang=lang,
            require_all_allowed_tables=require_all_allowed_tables,
        )

        # One-shot retry: if strict table scope failed, ask model again with harder instruction.
        if (
            not scoped_sql
            and runtime.get("api_key")
            and require_all_allowed_tables
            and selected_tables
            and allow_scope_retry
        ):
            retry_prompt = (
                f"{text}\n\n"
                "Mandatory SQL constraint: include ALL these tables in FROM/JOIN clauses: "
                + ", ".join(selected_tables)
                + "."
            )
            try:
                sql2, warnings2 = _openai_generate_sql_from_nl(
                    source,
                    retry_prompt,
                    lang=lang,
                    schema_meta=schema_meta,
                    required_tables=selected_tables,
                    timeout_seconds=timeout_seconds,
                )
                scoped_sql2, scoped_warnings2 = _enforce_selected_table_scope(
                    sql2,
                    warnings2 or [],
                    selected_tables,
                    lang=lang,
                    require_all_allowed_tables=True,
                )
                if scoped_sql2:
                    scoped_warnings2 = scoped_warnings2 or []
                    scoped_warnings2.insert(0, tr("SQL regenerated to include all selected tables.", lang))
                    return scoped_sql2, scoped_warnings2
            except Exception:
                pass

        return scoped_sql, scoped_warnings

    sql, warnings = _heuristic_generate_sql_from_nl(source, text, lang=lang, schema_meta=schema_meta)
    return _enforce_selected_table_scope(
        sql,
        warnings or [],
        selected_tables,
        lang=lang,
        require_all_allowed_tables=require_all_allowed_tables,
    )

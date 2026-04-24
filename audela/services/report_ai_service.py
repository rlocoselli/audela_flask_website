from __future__ import annotations

import json
from typing import Any

import requests

from .ai_runtime_config import resolve_ai_runtime_config


ALLOWED_REPORT_BLOCK_TYPES = {"text", "markdown", "question", "field", "image", "data_field"}


def compact_schema_meta(meta: dict[str, Any] | None, max_tables: int = 10, max_columns: int = 12) -> dict[str, Any]:
    meta = meta if isinstance(meta, dict) else {}
    out: dict[str, Any] = {"schemas": []}
    for schema in (meta.get("schemas") or [])[:3]:
        tables_out = []
        for table in (schema.get("tables") or [])[:max_tables]:
            cols_out = []
            for column in (table.get("columns") or [])[:max_columns]:
                if isinstance(column, dict):
                    cols_out.append({"name": column.get("name"), "type": str(column.get("type") or "")})
                else:
                    cols_out.append({"name": str(column), "type": ""})
            tables_out.append({"name": table.get("name"), "columns": cols_out})
        out["schemas"].append({"name": schema.get("name") or "default", "tables": tables_out})
    return out


def _table_map(schema_meta: dict[str, Any]) -> dict[str, list[str]]:
    tables: dict[str, list[str]] = {}
    for schema in (schema_meta.get("schemas") or []):
        schema_name = str(schema.get("name") or "").strip()
        for table in (schema.get("tables") or []):
            table_name = str(table.get("name") or "").strip()
            if not table_name:
                continue
            full_name = f"{schema_name}.{table_name}" if schema_name else table_name
            cols = [str(col.get("name") or "").strip() for col in (table.get("columns") or []) if str(col.get("name") or "").strip()]
            tables[full_name] = cols
            tables.setdefault(table_name, cols)
    return tables


def _default_layout() -> dict[str, Any]:
    return {
        "version": 5,
        "page": {"size": "A4", "orientation": "portrait"},
        "settings": {"page_number": True, "page_number_label": "Page {page} / {pages}"},
        "bands": {
            "report_header": [],
            "page_header": [],
            "detail": [],
            "page_footer": [],
            "report_footer": [],
        },
    }


def _sanitize_block(block: dict[str, Any], valid_question_ids: set[int], tables: dict[str, list[str]]) -> dict[str, Any] | None:
    block_type = str(block.get("type") or "").strip().lower()
    if block_type not in ALLOWED_REPORT_BLOCK_TYPES:
        return None

    out: dict[str, Any] = {"type": block_type, "title": str(block.get("title") or "").strip()}
    if block_type in {"text", "markdown"}:
        out["content"] = str(block.get("content") or block.get("text") or "").strip()
        if not out["content"]:
            out["content"] = out["title"]
    elif block_type == "question":
        try:
            qid = int(block.get("question_id") or 0)
        except Exception:
            qid = 0
        if qid not in valid_question_ids:
            return None
        out["question_id"] = qid
        cfg = block.get("config") if isinstance(block.get("config"), dict) else {}
        table_cfg = cfg.get("table") if isinstance(cfg.get("table"), dict) else {}
        sort_dir = str(table_cfg.get("sort_dir") or "asc").strip().lower()
        if sort_dir not in {"asc", "desc"}:
            sort_dir = "asc"
        filter_op = str(table_cfg.get("filter_op") or "").strip().lower()
        if filter_op and filter_op not in {"eq", "contains", "gt", "gte", "lt", "lte"}:
            filter_op = ""
        subtotal_mode = str(table_cfg.get("group_subtotal_mode") or "").strip().lower()
        if subtotal_mode and subtotal_mode not in {"count", "sum"}:
            subtotal_mode = ""
        out["config"] = {
            "table": {
                "theme": str(table_cfg.get("theme") or "crystal").strip() or "crystal",
                "zebra": bool(table_cfg.get("zebra")),
                "repeat_header": bool(table_cfg.get("repeat_header", True)),
                "decimals": table_cfg.get("decimals") if table_cfg.get("decimals") not in (None, "") else "",
                "date_format": str(table_cfg.get("date_format") or "").strip(),
                "sort_by": str(table_cfg.get("sort_by") or "").strip(),
                "sort_dir": sort_dir,
                "filter_field": str(table_cfg.get("filter_field") or "").strip(),
                "filter_op": filter_op,
                "filter_value": str(table_cfg.get("filter_value") or "").strip(),
                "group_by": str(table_cfg.get("group_by") or "").strip(),
                "group_label": str(table_cfg.get("group_label") or "{group}").strip() or "{group}",
                "group_count": bool(table_cfg.get("group_count")),
                "group_subtotal_mode": subtotal_mode,
                "group_subtotal_field": str(table_cfg.get("group_subtotal_field") or "").strip(),
                "group_subtotal_label": str(table_cfg.get("group_subtotal_label") or "Sous-total").strip() or "Sous-total",
                "grand_total": bool(table_cfg.get("grand_total")),
                "grand_total_label": str(table_cfg.get("grand_total_label") or "Grand total").strip() or "Grand total",
                "footer_item_count": bool(table_cfg.get("footer_item_count")),
                "footer_item_count_label": str(table_cfg.get("footer_item_count_label") or "Items").strip() or "Items",
            }
        }
    elif block_type == "field":
        cfg = block.get("config") if isinstance(block.get("config"), dict) else {}
        kind = str(cfg.get("kind") or "date").strip().lower()
        if kind not in {"date", "datetime"}:
            kind = "date"
        out["config"] = {
            "kind": kind,
            "format": str(cfg.get("format") or ("dd/MM/yyyy HH:mm" if kind == "datetime" else "dd/MM/yyyy")),
        }
    elif block_type == "image":
        out["url"] = str(block.get("url") or block.get("image_url") or "").strip()
        out["alt"] = str(block.get("alt") or "").strip()
        out["caption"] = str(block.get("caption") or "").strip()
        out["width"] = str(block.get("width") or "").strip()
        out["align"] = str(block.get("align") or "").strip()
    elif block_type == "data_field":
        cfg = block.get("config") if isinstance(block.get("config"), dict) else {}
        binding = cfg.get("binding") if isinstance(cfg.get("binding"), dict) else {}
        source = str(binding.get("source") or "").strip().lower()
        field = str(binding.get("field") or "").strip()
        if source == "question":
            try:
                qid = int(binding.get("question_id") or 0)
            except Exception:
                qid = 0
            if qid not in valid_question_ids or not field:
                return None
            bind_out = {"source": "question", "question_id": qid, "field": field, "question_name": str(binding.get("question_name") or "").strip()}
        elif source == "table":
            table = str(binding.get("table") or "").strip()
            if not table or not field:
                return None
            if table not in tables:
                matches = [name for name in tables.keys() if name.lower() == table.lower()]
                if matches:
                    table = matches[0]
            bind_out = {"source": "table", "table": table, "field": field}
        else:
            return None
        data_field_cfg: dict = {
            "binding": bind_out,
            "format": str(cfg.get("format") or "").strip(),
            "empty_text": str(cfg.get("empty_text") or "").strip(),
        }
        if cfg.get("group_key"):
            data_field_cfg["group_key"] = True
            data_field_cfg["group_label"] = str(cfg.get("group_label") or "{group}").strip() or "{group}"
        # Preserve table-level subtotal/grand-total config (set by AI or user).
        tbl_dfcfg = cfg.get("table") if isinstance(cfg.get("table"), dict) else {}
        if tbl_dfcfg:
            df_subtotal_mode = str(tbl_dfcfg.get("group_subtotal_mode") or "").strip().lower()
            if df_subtotal_mode not in {"count", "sum", "avg", "min", "max"}:
                df_subtotal_mode = ""
            data_field_cfg["table"] = {
                "theme": str(tbl_dfcfg.get("theme") or "crystal").strip() or "crystal",
                "zebra": bool(tbl_dfcfg.get("zebra")),
                "repeat_header": bool(tbl_dfcfg.get("repeat_header", True)),
                "header_bg": str(tbl_dfcfg.get("header_bg") or "").strip(),
                "group_subtotal_mode": df_subtotal_mode,
                "group_subtotal_field": str(tbl_dfcfg.get("group_subtotal_field") or "").strip(),
                "group_subtotal_label": str(tbl_dfcfg.get("group_subtotal_label") or "Sous-total").strip() or "Sous-total",
                "grand_total": bool(tbl_dfcfg.get("grand_total")),
                "grand_total_label": str(tbl_dfcfg.get("grand_total_label") or "Grand total").strip() or "Grand total",
                "footer_item_count": bool(tbl_dfcfg.get("footer_item_count")),
                "footer_item_count_label": str(tbl_dfcfg.get("footer_item_count_label") or "Items").strip() or "Items",
            }
        # Preserve per-field aggregation config.
        agg_dfcfg = cfg.get("aggregation") if isinstance(cfg.get("aggregation"), dict) else {}
        if agg_dfcfg:
            data_field_cfg["aggregation"] = {
                "mode": str(agg_dfcfg.get("mode") or "").strip().lower(),
                "label": str(agg_dfcfg.get("label") or "").strip(),
                "grand_total": bool(agg_dfcfg.get("grand_total")),
            }
        out["config"] = data_field_cfg

    style = block.get("style") if isinstance(block.get("style"), dict) else {}
    if style:
        out["style"] = {
            "color": str(style.get("color") or "").strip(),
            "background": str(style.get("background") or "").strip(),
            "align": str(style.get("align") or "").strip(),
            "font_size": str(style.get("font_size") or "").strip(),
            "bold": bool(style.get("bold")),
            "italic": bool(style.get("italic")),
            "underline": bool(style.get("underline")),
        }
    return out


_DATE_KEYWORDS = {
    "date", "month", "year", "ordered", "order_date", "sale_date", "sales_date",
    "invoice", "invoice_date", "transaction_date", "period", "mois", "annee", "année",
    "mensuel", "annuel", "timestamp", "datetime",
}
_AMOUNT_KEYWORDS = {
    "total", "amount", "price", "revenue", "sales", "sum", "cost", "value",
    "montant", "vente", "chiffre", "income", "profit", "subtotal", "net", "gross",
}
_SECONDARY_AMOUNT_KEYWORDS = {"qty", "quantity", "count", "units", "volume"}
_TECHNICAL_DATE_MARKERS = {"etl", "loaded", "load", "ingest", "created", "updated", "modified", "sync", "batch"}
_DIMENSION_KEYWORDS = {"name", "customer", "client", "product", "category", "region", "country", "city", "segment", "status", "channel"}


def _col_matches_any(col: str, keywords: set[str]) -> bool:
    col_l = col.lower()
    return any(kw in col_l for kw in keywords)


def _prompt_tokens(prompt: str) -> set[str]:
    raw = str(prompt or "").lower()
    buf: list[str] = []
    cur = []
    for ch in raw:
        if ch.isalnum() or ch == "_":
            cur.append(ch)
        else:
            if cur:
                tok = "".join(cur).strip()
                if tok:
                    buf.append(tok)
                cur = []
    if cur:
        tok = "".join(cur).strip()
        if tok:
            buf.append(tok)
    return set(buf)


def _score_name_against_prompt(name: str, prompt_tokens: set[str]) -> int:
    n = str(name or "").lower()
    if not n or not prompt_tokens:
        return 0
    score = 0
    for tok in prompt_tokens:
        if tok and tok in n:
            score += 3
    # Small bonus for known business terms
    if any(k in n for k in {"sale", "sales", "order", "invoice", "transaction", "revenue"}):
        score += 2
    return score


def _is_technical_column(col: str) -> bool:
    cl = str(col or "").lower().strip()
    if not cl:
        return False
    if any(m in cl for m in _TECHNICAL_DATE_MARKERS):
        return True
    if cl.endswith("_at") or cl.endswith("_ts") or "timestamp" in cl:
        return True
    return False


def _pick_dimension_column(columns: list[str], date_col: str, amount_col: str, prompt: str = "") -> str:
    prompt_tokens = _prompt_tokens(prompt)
    best_col = ""
    best_score = -10_000
    dcl = str(date_col or "").lower().strip()
    acl = str(amount_col or "").lower().strip()
    for col in columns:
        c = str(col or "").strip()
        if not c:
            continue
        cl = c.lower()
        if cl == dcl or (acl and cl == acl):
            continue
        score = 0
        if _is_technical_column(cl):
            score -= 8
        if _col_matches_any(cl, _DIMENSION_KEYWORDS):
            score += 7
        if cl.endswith("_name") or "name" in cl:
            score += 5
        # Avoid accidentally choosing alternate date/amount columns as the third display field.
        if _col_matches_any(cl, _DATE_KEYWORDS):
            score -= 3
        if _col_matches_any(cl, _AMOUNT_KEYWORDS) or _col_matches_any(cl, _SECONDARY_AMOUNT_KEYWORDS):
            score -= 2
        score += _score_name_against_prompt(cl, prompt_tokens)
        if score > best_score:
            best_score = score
            best_col = c
    return best_col


def _wants_sum_amount(prompt: str) -> bool:
    p = str(prompt or "").lower()
    positive = {"sum", "somme", "amount", "revenue", "montant", "chiffre", "sales amount", "total amount", "order total"}
    negative = {"count", "number of", "nombre", "nb", "orders count", "order count"}
    if any(n in p for n in negative):
        return False
    return any(tok in p for tok in positive)


def _default_group_metric(prompt: str, amount_col: str) -> tuple[str, str]:
    if amount_col and _wants_sum_amount(prompt):
        return "sum", amount_col
    return "count", ""


def _best_date_column(columns: list[str], prompt_tokens: set[str]) -> str:
    best_col = ""
    best_score = -10_000
    for col in columns:
        c = str(col or "").strip()
        if not c:
            continue
        cl = c.lower()
        score = 0
        if _col_matches_any(cl, _DATE_KEYWORDS):
            score += 8
        if "date" in cl:
            score += 6
        if any(x in cl for x in {"order_date", "sale_date", "invoice_date", "transaction_date"}):
            score += 8
        if any(x in cl for x in _TECHNICAL_DATE_MARKERS):
            score -= 7
        score += _score_name_against_prompt(cl, prompt_tokens)
        if score > best_score:
            best_score = score
            best_col = c
    # Ignore very weak matches (e.g., technical timestamps without business date semantics).
    return best_col if best_score >= 6 else ""


def _best_amount_column(columns: list[str], prompt_tokens: set[str]) -> str:
    best_primary = ""
    best_primary_score = -10_000
    best_secondary = ""
    best_secondary_score = -10_000
    for col in columns:
        c = str(col or "").strip()
        if not c:
            continue
        cl = c.lower()
        p_score = 0
        s_score = 0
        if _col_matches_any(cl, _AMOUNT_KEYWORDS):
            p_score += 8
        if any(x in cl for x in {"total", "amount", "revenue", "price", "net", "gross"}):
            p_score += 6
        if _col_matches_any(cl, _SECONDARY_AMOUNT_KEYWORDS):
            s_score += 5
        p_score += _score_name_against_prompt(cl, prompt_tokens)
        s_score += _score_name_against_prompt(cl, prompt_tokens)
        if p_score > best_primary_score:
            best_primary_score = p_score
            best_primary = c
        if s_score > best_secondary_score:
            best_secondary_score = s_score
            best_secondary = c
    if best_primary and best_primary_score >= 8:
        return best_primary
    if best_secondary_score >= 6:
        return best_secondary
    return ""


def _detect_grouping_hint(tables: dict[str, list[str]], prompt: str = "") -> dict[str, str]:
    """Scan schema columns and return best candidate date + amount column names."""
    prompt_tokens = _prompt_tokens(prompt)
    best_date: str | None = None
    best_amount: str | None = None
    best_score = -10_000
    for table_name, columns in tables.items():
        cols = [str(c or "").strip() for c in (columns or []) if str(c or "").strip()]
        if not cols:
            continue
        date_col = _best_date_column(cols, prompt_tokens)
        amount_col = _best_amount_column(cols, prompt_tokens)
        if not date_col:
            continue
        score = _score_name_against_prompt(str(table_name), prompt_tokens)
        if amount_col:
            score += 5
        if score > best_score:
            best_score = score
            best_date = date_col
            best_amount = amount_col
    result: dict[str, str] = {}
    if best_date:
        result["date_col"] = best_date
    if best_amount:
        result["amount_col"] = best_amount
    return result


def _detect_grouping_table_hint(tables: dict[str, list[str]], prompt: str = "") -> dict[str, str]:
    """Pick a source table that contains a date-like column (and ideally an amount-like column)."""
    prompt_tokens = _prompt_tokens(prompt)
    best: dict[str, str] = {}
    best_score = -10_000
    for table_name, columns in tables.items():
        # Prefer unqualified table names over schema-qualified aliases.
        if "." in str(table_name or ""):
            continue
        cols = [str(c or "").strip() for c in (columns or []) if str(c or "").strip()]
        if not cols:
            continue
        hint = _detect_grouping_hint_from_columns(cols, prompt=prompt)
        if not hint.get("date_col"):
            continue
        candidate = {
            "table": str(table_name),
            "date_col": str(hint.get("date_col") or ""),
        }
        if hint.get("amount_col"):
            candidate["amount_col"] = str(hint.get("amount_col") or "")
        score = _score_name_against_prompt(str(table_name), prompt_tokens)
        if candidate.get("amount_col"):
            score += 5
        if score > best_score:
            best_score = score
            best = candidate
    return best


def _detect_grouping_hint_from_columns(columns: list[str], prompt: str = "") -> dict[str, str]:
    """Detect date and amount columns from a single question result-set schema."""
    prompt_tokens = _prompt_tokens(prompt)
    clean_cols = [str(col or "").strip() for col in columns if str(col or "").strip()]
    best_date = _best_date_column(clean_cols, prompt_tokens)
    best_amount = _best_amount_column(clean_cols, prompt_tokens)
    result: dict[str, str] = {}
    if best_date:
        result["date_col"] = best_date
    if best_amount:
        result["amount_col"] = best_amount
    return result


def _prompt_wants_grouping(prompt: str) -> bool:
    """Return True when the prompt clearly asks for grouped / subtotal data."""
    keywords = {
        "group", "grouped", "grouping", "subtotal", "sub-total", "regroup",
        "by month", "by year", "par mois", "par année", "par an",
        "month", "year", "mois", "annee", "année", "mensuel", "annually",
    }
    p = prompt.lower()
    return any(kw in p for kw in keywords)


def _grouping_expression_from_prompt(prompt: str, date_col: str) -> str:
    p = str(prompt or "").lower()
    wants_month = any(token in p for token in {"month", "months", "by month", "mois", "mensuel"})
    wants_year = any(token in p for token in {"year", "years", "by year", "année", "annee", "annuel", "annual"})
    if wants_month and wants_year:
        return f"month_year({date_col})"
    if wants_year:
        return f"year({date_col})"
    if wants_month:
        return f"month({date_col})"
    return date_col


def _is_derived_group_by(value: str) -> bool:
    v = str(value or "").strip().lower()
    return v.startswith("month(") or v.startswith("year(") or v.startswith("month_year(") or v.startswith("year_month(")


def _fallback_data_field_blocks(tables: dict[str, list[str]]) -> list[dict[str, Any]]:
    for table_name, columns in tables.items():
        if not columns:
            continue
        return [
            {
                "type": "data_field",
                "title": col.replace("_", " ").title(),
                "config": {"binding": {"source": "table", "table": table_name, "field": col}, "format": "", "empty_text": ""},
            }
            for col in columns[:4]
        ]
    return []


def _apply_visual_polish(layout: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    bands = layout.get("bands") if isinstance(layout.get("bands"), dict) else {}
    report_name = str(context.get("report_name") or "AI Report").strip() or "AI Report"

    header_blocks = bands.get("report_header") if isinstance(bands.get("report_header"), list) else []
    if not header_blocks:
        header_blocks = []
        bands["report_header"] = header_blocks

    if not header_blocks:
        header_blocks.append({
            "type": "text",
            "title": "Title",
            "content": report_name,
            "style": {
                "font_size": "30px",
                "bold": True,
                "align": "left",
                "color": "#0b1220",
                "background": "",
                "italic": False,
                "underline": False,
            },
        })
    else:
        first = header_blocks[0]
        if isinstance(first, dict) and str(first.get("type") or "").lower() in {"text", "markdown"}:
            first.setdefault("content", report_name)
            style = first.get("style") if isinstance(first.get("style"), dict) else {}
            style.update({
                "bold": True,
                "font_size": str(style.get("font_size") or "30px"),
                "color": str(style.get("color") or "#0b1220"),
                "align": str(style.get("align") or "left"),
                "background": str(style.get("background") or ""),
                "italic": bool(style.get("italic")),
                "underline": bool(style.get("underline")),
            })
            first["style"] = style

    detail_blocks = bands.get("detail") if isinstance(bands.get("detail"), list) else []
    if detail_blocks and isinstance(detail_blocks[0], dict):
        first_detail = detail_blocks[0]
        detail_type = str(first_detail.get("type") or "").lower()
        if detail_type == "markdown":
            content = str(first_detail.get("content") or "").strip()
            if content and not content.lstrip().startswith("#"):
                first_detail["content"] = f"## {content}"
        elif detail_type == "text":
            style = first_detail.get("style") if isinstance(first_detail.get("style"), dict) else {}
            style.update({
                "bold": True,
                "font_size": str(style.get("font_size") or "18px"),
                "color": str(style.get("color") or "#1f2937"),
                "align": str(style.get("align") or "left"),
                "background": str(style.get("background") or ""),
                "italic": bool(style.get("italic")),
                "underline": bool(style.get("underline")),
            })
            first_detail["style"] = style

    layout["bands"] = bands
    return layout


def sanitize_report_layout(layout: dict[str, Any], context: dict[str, Any], prompt: str) -> dict[str, Any]:
    base = _default_layout()
    incoming = layout if isinstance(layout, dict) else {}
    base["page"] = incoming.get("page") if isinstance(incoming.get("page"), dict) else base["page"]
    settings = incoming.get("settings") if isinstance(incoming.get("settings"), dict) else {}
    base["settings"] = {
        "page_number": bool(settings.get("page_number", True)),
        "page_number_label": str(settings.get("page_number_label") or "Page {page} / {pages}"),
    }

    questions = context.get("questions") if isinstance(context.get("questions"), list) else []
    valid_question_ids = {int(q.get("id")) for q in questions if str(q.get("id") or "").isdigit()}
    question_cols_by_id: dict[int, list[str]] = {}
    for q in questions:
        if not isinstance(q, dict):
            continue
        try:
            qid = int(q.get("id") or 0)
        except Exception:
            qid = 0
        if qid <= 0:
            continue
        cols = q.get("columns") if isinstance(q.get("columns"), list) else []
        question_cols_by_id[qid] = [str(c).strip() for c in cols if str(c).strip()]

    tables = _table_map(context.get("schema") if isinstance(context.get("schema"), dict) else {})

    incoming_bands = incoming.get("bands") if isinstance(incoming.get("bands"), dict) else {}
    sanitized_bands: dict[str, list[dict[str, Any]]] = {}
    for band_name in base["bands"].keys():
        blocks_in = incoming_bands.get(band_name) if isinstance(incoming_bands.get(band_name), list) else []
        blocks_out = []
        for block in blocks_in[:12]:
            if not isinstance(block, dict):
                continue
            sanitized = _sanitize_block(block, valid_question_ids, tables)
            if sanitized:
                blocks_out.append(sanitized)
        sanitized_bands[band_name] = blocks_out

    if not sanitized_bands["report_header"]:
        sanitized_bands["report_header"].append({
            "type": "text",
            "title": "Title",
            "content": str(context.get("report_name") or "AI Report"),
            "style": {"font_size": "28px", "bold": True, "align": "left", "color": "#0f172a", "background": "", "italic": False, "underline": False},
        })
    if not sanitized_bands["page_header"]:
        sanitized_bands["page_header"].append({"type": "field", "title": "Date", "config": {"kind": "date", "format": "dd/MM/yyyy"}})
    if not sanitized_bands["detail"]:
        first_question = next(iter(valid_question_ids), None)
        if first_question:
            sanitized_bands["detail"].append({"type": "question", "title": "Data table", "question_id": first_question, "config": {"table": {"theme": "crystal", "zebra": True, "repeat_header": True, "decimals": ""}}})
        else:
            sanitized_bands["detail"].extend(_fallback_data_field_blocks(tables))
    has_data_block = any(
        isinstance(b, dict) and str(b.get("type") or "").strip().lower() in {"question", "data_field"}
        for b in (sanitized_bands["detail"] or [])
    )

    if not has_data_block:
        fallback_fields = _fallback_data_field_blocks(tables)
        if len(fallback_fields) >= 2:
            # Prefer direct schema-based bindings so AI can render data even without saved questions.
            sanitized_bands["detail"].extend(fallback_fields[:4])
        else:
            first_question = next(iter(valid_question_ids), None)
            if first_question:
                sanitized_bands["detail"].append(
                    {
                        "type": "question",
                        "title": "Data table",
                        "question_id": first_question,
                        "config": {
                            "table": {
                                "theme": "crystal",
                                "zebra": True,
                                "repeat_header": True,
                                "decimals": "",
                            }
                        },
                    }
                )

    if not sanitized_bands["detail"]:
        sanitized_bands["detail"].append({"type": "markdown", "title": "Summary", "content": str(prompt or context.get("report_name") or "Report summary")})

    # Auto-fill or refine grouping when the prompt asks for it.
    if _prompt_wants_grouping(prompt):
        schema_hint = _detect_grouping_hint(tables, prompt=prompt)
        table_hint = _detect_grouping_table_hint(tables, prompt=prompt)
        best_grouping_qid: int | None = None
        best_grouping_hint: dict[str, str] = {}
        for qid, cols in question_cols_by_id.items():
            q_hint = _detect_grouping_hint_from_columns(cols, prompt=prompt)
            if not q_hint.get("date_col"):
                continue
            if not best_grouping_qid:
                best_grouping_qid = qid
                best_grouping_hint = q_hint
            if q_hint.get("amount_col"):
                best_grouping_qid = qid
                best_grouping_hint = q_hint
                break

        applied_grouping_on_question = False
        first_question_idx = -1
        if schema_hint or best_grouping_qid:
            for idx, block in enumerate(sanitized_bands["detail"]):
                if isinstance(block, dict) and block.get("type") == "question":
                    first_question_idx = idx
                    break

            for block in sanitized_bands["detail"]:
                if not isinstance(block, dict) or block.get("type") != "question":
                    continue
                # Ensure config.table exists
                if "config" not in block or not isinstance(block["config"], dict):
                    block["config"] = {}
                if "table" not in block["config"] or not isinstance(block["config"]["table"], dict):
                    block["config"]["table"] = {}
                tbl_cfg = block["config"]["table"]

                try:
                    qid = int(block.get("question_id") or 0)
                except Exception:
                    qid = 0
                q_cols = question_cols_by_id.get(qid, [])
                q_hint = _detect_grouping_hint_from_columns(q_cols, prompt=prompt) if q_cols else {}

                # If current question has no date column but another question does,
                # switch to the best grouping-capable question.
                if not q_hint.get("date_col") and best_grouping_qid and best_grouping_qid != qid:
                    block["question_id"] = best_grouping_qid
                    q_hint = dict(best_grouping_hint)

                # Do not force schema-level date columns onto a question that explicitly
                # has columns and none of them are date-like.
                active_hint = q_hint if q_hint else (schema_hint if not q_cols else {})

                if active_hint.get("date_col"):
                    applied_grouping_on_question = True
                    existing_group_by = str(tbl_cfg.get("group_by") or "").strip()
                    desired_group_by = _grouping_expression_from_prompt(prompt, active_hint["date_col"])
                    if not existing_group_by:
                        tbl_cfg["group_by"] = desired_group_by
                    elif not _is_derived_group_by(existing_group_by):
                        if existing_group_by.lower() == str(active_hint["date_col"]).lower() or _col_matches_any(existing_group_by, _DATE_KEYWORDS):
                            tbl_cfg["group_by"] = desired_group_by
                    if not tbl_cfg.get("group_label"):
                        tbl_cfg["group_label"] = "{group}"
                    if not tbl_cfg.get("group_count"):
                        tbl_cfg["group_count"] = False
                    if not tbl_cfg.get("sort_by"):
                        tbl_cfg["sort_by"] = active_hint["date_col"]
                    if not tbl_cfg.get("sort_dir"):
                        tbl_cfg["sort_dir"] = "asc"

                    # When user asks totals/subtotals, always enable a metric.
                    default_mode, default_field = _default_group_metric(prompt, str(active_hint.get("amount_col") or ""))
                    if not tbl_cfg.get("group_subtotal_mode"):
                        tbl_cfg["group_subtotal_mode"] = default_mode
                    if str(tbl_cfg.get("group_subtotal_mode") or "").strip().lower() == "sum":
                        if not tbl_cfg.get("group_subtotal_field"):
                            tbl_cfg["group_subtotal_field"] = default_field
                    else:
                        tbl_cfg["group_subtotal_field"] = ""
                    if not tbl_cfg.get("group_subtotal_label"):
                        tbl_cfg["group_subtotal_label"] = "Sous-total"
                    if not tbl_cfg.get("grand_total"):
                        tbl_cfg["grand_total"] = True
                    if not tbl_cfg.get("grand_total_label"):
                        tbl_cfg["grand_total_label"] = "Grand total"
                    if not tbl_cfg.get("footer_item_count"):
                        tbl_cfg["footer_item_count"] = True

                if active_hint.get("amount_col"):
                    default_mode, default_field = _default_group_metric(prompt, str(active_hint.get("amount_col") or ""))
                    if not tbl_cfg.get("group_subtotal_mode"):
                        tbl_cfg["group_subtotal_mode"] = default_mode
                    if str(tbl_cfg.get("group_subtotal_mode") or "").strip().lower() == "sum":
                        tbl_cfg["group_subtotal_field"] = default_field
                    else:
                        tbl_cfg["group_subtotal_field"] = ""
                    if not tbl_cfg.get("group_subtotal_label"):
                        tbl_cfg["group_subtotal_label"] = "Sous-total"
                    if not tbl_cfg.get("grand_total"):
                        tbl_cfg["grand_total"] = True
                    if not tbl_cfg.get("grand_total_label"):
                        tbl_cfg["grand_total_label"] = "Grand total"

        # If no saved question can support date grouping, build a direct table rowset
        # from source columns so month/year grouping still works in preview/PDF.
        if not applied_grouping_on_question and first_question_idx >= 0 and table_hint.get("table") and table_hint.get("date_col"):
            table_name = str(table_hint.get("table") or "").strip()
            date_col = str(table_hint.get("date_col") or "").strip()
            amount_col = str(table_hint.get("amount_col") or "").strip()
            cols = tables.get(table_name) or []
            display_cols = [str(c) for c in cols if str(c)]
            other_col = _pick_dimension_column(display_cols, date_col, amount_col, prompt=prompt)
            subtotal_mode, subtotal_field = _default_group_metric(prompt, amount_col)

            rowset_blocks: list[dict[str, Any]] = []
            rowset_blocks.append(
                {
                    "type": "data_field",
                    "title": date_col.replace("_", " ").title(),
                    "config": {
                        "binding": {"source": "table", "table": table_name, "field": date_col},
                        "format": "MM/yyyy",
                        "empty_text": "",
                        "group_key": True,
                        "group_label": "{group}",
                        "table": {
                            "theme": "crystal",
                            "zebra": True,
                            "repeat_header": True,
                            "group_subtotal_mode": subtotal_mode,
                            "group_subtotal_field": subtotal_field,
                            "group_subtotal_label": "Sous-total",
                            "grand_total": True,
                            "grand_total_label": "Grand total",
                            "footer_item_count": True,
                            "footer_item_count_label": "Items",
                        },
                    },
                }
            )
            if amount_col:
                rowset_blocks.append(
                    {
                        "type": "data_field",
                        "title": amount_col.replace("_", " ").title(),
                        "config": {
                            "binding": {"source": "table", "table": table_name, "field": amount_col},
                            "format": "",
                            "empty_text": "",
                        },
                    }
                )
            if other_col:
                rowset_blocks.append(
                    {
                        "type": "data_field",
                        "title": other_col.replace("_", " ").title(),
                        "config": {
                            "binding": {"source": "table", "table": table_name, "field": other_col},
                            "format": "",
                            "empty_text": "",
                        },
                    }
                )

            sanitized_bands["detail"][first_question_idx:first_question_idx + 1] = rowset_blocks

    base["bands"] = sanitized_bands
    return _apply_visual_polish(base, context)


def generate_report_layout_from_prompt(prompt: str, context: dict[str, Any], *, lang: str | None = None) -> dict[str, Any]:
    runtime = resolve_ai_runtime_config(default_model="gpt-4o-mini")
    api_key = runtime.get("api_key")
    if not api_key:
        raise RuntimeError(f"{runtime.get('missing_key_env') or 'OPENAI_API_KEY'} missing")

    user_prompt = str(prompt or "").strip()
    if not user_prompt:
        raise RuntimeError("Prompt is required")

    system_prompt = (
        "You design layouts for a drag-and-drop business report builder. "
        "Return ONLY JSON with keys: name, summary, warnings, layout. "
        "layout must contain version, page, settings, bands. "
        "bands must contain arrays for report_header, page_header, detail, page_footer, report_footer. "
        "Allowed block types are exactly: text, markdown, question, field, image, data_field. "
        "For question blocks use an existing integer question_id from context. "
        "Question table config supports: theme, zebra, repeat_header, decimals, date_format, sort_by, sort_dir, "
        "filter_field, filter_op, filter_value, group_by, group_label, group_count, "
        "group_subtotal_mode, group_subtotal_field, group_subtotal_label, grand_total, grand_total_label, "
        "footer_item_count, footer_item_count_label. "
        "For data_field blocks use config.binding with source=table or source=question and include the exact field name. "
        "The detail band must include at least one data block (question or data_field). "
        "When user asks for grouped reports (e.g., by month/year) include group_by and subtotal fields in question table config. "
        "group_by may use derived date expressions like month(order_date), year(order_date), or month_year(order_date) when grouping by calendar periods. "
        "Prefer concise business-ready layouts with 4 to 10 blocks total. "
        "Always make report titles visually strong: bold, larger font size, clean hierarchy. "
        "Use markdown headings for section titles when using markdown blocks. "
        "No markdown fences."
    )

    payload = {
        "model": runtime.get("model") or "gpt-4o-mini",
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Language: " + str(lang or "en") + "\n\nREPORT CONTEXT (JSON):\n" + json.dumps(context, ensure_ascii=False) + "\n\nUSER REQUEST:\n" + user_prompt},
        ],
    }

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    base_url = runtime.get("base_url") or "https://api.openai.com/v1"
    timeout_seconds = int(runtime.get("read_timeout_seconds") or runtime.get("timeout_seconds") or 90)
    url = f"{str(base_url).rstrip('/')}/chat/completions"
    response = requests.post(url, headers=headers, json=payload, timeout=timeout_seconds)
    if response.status_code >= 400:
        payload.pop("response_format", None)
        response = requests.post(url, headers=headers, json=payload, timeout=timeout_seconds)
    response.raise_for_status()

    body = response.json()
    content = (body.get("choices") or [{}])[0].get("message", {}).get("content") or "{}"
    try:
        obj = json.loads(content)
    except Exception as exc:
        raise RuntimeError("OpenAI returned invalid JSON") from exc
    if not isinstance(obj, dict):
        raise RuntimeError("OpenAI output must be a JSON object")

    layout = sanitize_report_layout(obj.get("layout") if isinstance(obj.get("layout"), dict) else {}, context, user_prompt)
    warnings = obj.get("warnings") if isinstance(obj.get("warnings"), list) else []
    return {
        "name": str(obj.get("name") or context.get("report_name") or "AI Report"),
        "summary": str(obj.get("summary") or "").strip(),
        "warnings": [str(w) for w in warnings if str(w).strip()],
        "layout": layout,
    }
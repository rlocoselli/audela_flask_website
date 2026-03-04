from __future__ import annotations

import json
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import requests
from sqlalchemy import text

from ..extensions import db
from .ai_runtime_config import resolve_ai_runtime_config


SUPPORTED_RATIO_LANGS: tuple[str, ...] = ("fr", "en", "pt", "es", "it", "de")
_READONLY_PREFIXES = ("select", "with", "show", "describe", "explain")
_FORBIDDEN_SQL_RE = re.compile(r"\b(insert|update|delete|drop|alter|truncate|create|grant|revoke)\b", flags=re.I)
_SOURCE_TABLE_MAP: dict[str, str] = {
    "transactions": "finance_transactions",
    "invoices": "finance_invoices",
    "accounts": "finance_accounts",
    "liabilities": "finance_liabilities",
    "investments": "finance_investments",
}


def _normalize_source_hint(source_hint: str | None) -> str | None:
    value = str(source_hint or "").strip().lower()
    return value if value in _SOURCE_TABLE_MAP else None


def _json_default(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return str(obj)


def _strip_sql_comments(sql_text: str) -> str:
    sql_text = re.sub(r"--.*?\n", "\n", sql_text)
    sql_text = re.sub(r"/\*.*?\*/", " ", sql_text, flags=re.S)
    return sql_text


def _is_readonly_sql(sql_text: str) -> bool:
    cleaned = _strip_sql_comments(sql_text).strip().lstrip("(").strip()
    if not cleaned:
        return False
    first = cleaned.split(None, 1)[0].lower()
    return first in _READONLY_PREFIXES


def validate_scalar_sql(sql_text: str) -> str:
    sql_text = (sql_text or "").strip()
    if not sql_text:
        raise ValueError("SQL vide.")

    if ";" in sql_text:
        raise ValueError("SQL invalide: les requêtes multiples ne sont pas autorisées.")

    if not _is_readonly_sql(sql_text):
        raise ValueError("Seules les requêtes de lecture sont autorisées (SELECT/WITH...).")

    if _FORBIDDEN_SQL_RE.search(sql_text):
        raise ValueError("SQL invalide: commande non autorisée détectée.")

    if ":tenant_id" not in sql_text or ":company_id" not in sql_text:
        raise ValueError("La requête doit contenir :tenant_id et :company_id.")

    return sql_text


def _to_decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        return Decimal(int(value))
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Valeur scalaire non numérique: {value}") from exc


def execute_scalar_sql(sql_text: str, params: dict[str, Any]) -> Decimal:
    validated_sql = validate_scalar_sql(sql_text)
    result = db.session.execute(text(validated_sql), params or {})
    row = result.first()
    if row is None:
        return Decimal("0")
    return _to_decimal(row[0])


def normalize_ratio_labels(labels: Any, fallback_name: str) -> dict[str, str]:
    labels = labels if isinstance(labels, dict) else {}
    out: dict[str, str] = {}
    for lang in SUPPORTED_RATIO_LANGS:
        value = str(labels.get(lang) or "").strip()
        out[lang] = value or fallback_name
    return out


def normalize_ratio_config(raw: Any) -> dict[str, list[dict[str, Any]]]:
    raw = raw if isinstance(raw, dict) else {}
    indicators_raw = raw.get("indicators") if isinstance(raw.get("indicators"), list) else []
    ratios_raw = raw.get("ratios") if isinstance(raw.get("ratios"), list) else []

    indicators: list[dict[str, Any]] = []
    seen_indicators: set[str] = set()
    for item in indicators_raw:
        if not isinstance(item, dict):
            continue
        indicator_id = str(item.get("id") or "").strip()
        if not indicator_id or indicator_id in seen_indicators:
            continue

        name = str(item.get("name") or "").strip() or f"indicator_{indicator_id[:8]}"
        sql_text = str(item.get("sql") or "").strip()
        if not sql_text:
            continue
        source_id = None
        try:
            parsed_source_id = int(item.get("source_id") or 0)
            if parsed_source_id > 0:
                source_id = parsed_source_id
        except Exception:
            source_id = None

        indicators.append(
            {
                "id": indicator_id,
                "name": name,
                "description": str(item.get("description") or "").strip(),
                "labels": normalize_ratio_labels(item.get("labels"), name),
                "sql": sql_text,
                "source_id": source_id,
                "created_at": str(item.get("created_at") or ""),
            }
        )
        seen_indicators.add(indicator_id)

    ratios: list[dict[str, Any]] = []
    seen_ratios: set[str] = set()
    indicator_ids = {row["id"] for row in indicators}
    for item in ratios_raw:
        if not isinstance(item, dict):
            continue

        ratio_id = str(item.get("id") or "").strip()
        if not ratio_id or ratio_id in seen_ratios:
            continue

        numerator_id = str(item.get("numerator_id") or "").strip()
        denominator_id = str(item.get("denominator_id") or "").strip()
        if numerator_id not in indicator_ids or denominator_id not in indicator_ids:
            continue

        name = str(item.get("name") or "").strip() or f"ratio_{ratio_id[:8]}"

        try:
            multiplier = float(item.get("multiplier") if item.get("multiplier") is not None else 100.0)
        except Exception:
            multiplier = 100.0

        try:
            precision = int(item.get("precision") if item.get("precision") is not None else 2)
        except Exception:
            precision = 2
        precision = max(0, min(6, precision))

        ratios.append(
            {
                "id": ratio_id,
                "name": name,
                "description": str(item.get("description") or "").strip(),
                "labels": normalize_ratio_labels(item.get("labels"), name),
                "numerator_id": numerator_id,
                "denominator_id": denominator_id,
                "multiplier": multiplier,
                "precision": precision,
                "suffix": str(item.get("suffix") or "%").strip() or "%",
                "created_at": str(item.get("created_at") or ""),
            }
        )
        seen_ratios.add(ratio_id)

    return {"indicators": indicators, "ratios": ratios}


def compute_ratio_value(numerator_value: Decimal, denominator_value: Decimal, multiplier: float = 100.0) -> Decimal | None:
    if denominator_value == 0:
        return None
    return (numerator_value / denominator_value) * Decimal(str(multiplier))


def _heuristic_indicator_from_nl(text: str, lang: str | None = None, source_hint: str | None = None) -> tuple[str, str, list[str]]:
    content = (text or "").strip().lower()
    warnings: list[str] = []
    source_key = _normalize_source_hint(source_hint)

    if not content:
        return (
            "Indicateur scalaire",
            "SELECT 0 AS value",
            ["Texte vide, requête de fallback générée."],
        )

    is_invoice = any(token in content for token in ["invoice", "facture", "fatura", "fattura", "factura"]) or source_key == "invoices"
    is_count = any(token in content for token in ["count", "combien", "quantos", "cuantos", "conteggio", "anzahl", "nombre"])
    is_avg = any(token in content for token in ["average", "avg", "moyenne", "média", "media"])
    is_expense = any(token in content for token in ["expense", "dépense", "despesa", "gasto", "costo", "cost"])
    is_income = any(token in content for token in ["income", "revenue", "vente", "recette", "receita", "ingreso", "revenu", "ca"])

    if source_key == "accounts":
        if is_count:
            return (
                "Nombre de comptes",
                (
                    "SELECT COUNT(*) AS value\n"
                    "FROM finance_accounts\n"
                    "WHERE tenant_id = :tenant_id\n"
                    "  AND company_id = :company_id\n"
                    "  AND :start_date <= :end_date"
                ),
                warnings,
            )
        if is_avg:
            return (
                "Solde moyen des comptes",
                (
                    "SELECT COALESCE(AVG(balance), 0) AS value\n"
                    "FROM finance_accounts\n"
                    "WHERE tenant_id = :tenant_id\n"
                    "  AND company_id = :company_id\n"
                    "  AND :start_date <= :end_date"
                ),
                warnings,
            )
        return (
            "Solde total des comptes",
            (
                "SELECT COALESCE(SUM(balance), 0) AS value\n"
                "FROM finance_accounts\n"
                "WHERE tenant_id = :tenant_id\n"
                "  AND company_id = :company_id\n"
                "  AND :start_date <= :end_date"
            ),
            warnings,
        )

    if source_key == "liabilities":
        if is_count:
            return (
                "Nombre de financements",
                (
                    "SELECT COUNT(*) AS value\n"
                    "FROM finance_liabilities\n"
                    "WHERE tenant_id = :tenant_id\n"
                    "  AND company_id = :company_id\n"
                    "  AND maturity_date BETWEEN :start_date AND :end_date"
                ),
                warnings,
            )
        if is_avg:
            return (
                "Encours moyen",
                (
                    "SELECT COALESCE(AVG(outstanding_amount), 0) AS value\n"
                    "FROM finance_liabilities\n"
                    "WHERE tenant_id = :tenant_id\n"
                    "  AND company_id = :company_id\n"
                    "  AND maturity_date BETWEEN :start_date AND :end_date"
                ),
                warnings,
            )
        return (
            "Encours total",
            (
                "SELECT COALESCE(SUM(outstanding_amount), 0) AS value\n"
                "FROM finance_liabilities\n"
                "WHERE tenant_id = :tenant_id\n"
                "  AND company_id = :company_id\n"
                "  AND maturity_date BETWEEN :start_date AND :end_date"
            ),
            warnings,
        )

    if source_key == "investments":
        if is_count:
            return (
                "Nombre d'investissements",
                (
                    "SELECT COUNT(*) AS value\n"
                    "FROM finance_investments\n"
                    "WHERE tenant_id = :tenant_id\n"
                    "  AND company_id = :company_id\n"
                    "  AND started_on BETWEEN :start_date AND :end_date"
                ),
                warnings,
            )
        if is_avg:
            return (
                "Valeur moyenne des investissements",
                (
                    "SELECT COALESCE(AVG(current_value), 0) AS value\n"
                    "FROM finance_investments\n"
                    "WHERE tenant_id = :tenant_id\n"
                    "  AND company_id = :company_id\n"
                    "  AND started_on BETWEEN :start_date AND :end_date"
                ),
                warnings,
            )
        return (
            "Valeur totale des investissements",
            (
                "SELECT COALESCE(SUM(current_value), 0) AS value\n"
                "FROM finance_investments\n"
                "WHERE tenant_id = :tenant_id\n"
                "  AND company_id = :company_id\n"
                "  AND started_on BETWEEN :start_date AND :end_date"
            ),
            warnings,
        )

    if is_invoice:
        if is_count:
            return (
                "Nombre de factures",
                (
                    "SELECT COUNT(*) AS value\n"
                    "FROM finance_invoices\n"
                    "WHERE tenant_id = :tenant_id\n"
                    "  AND company_id = :company_id\n"
                    "  AND issue_date BETWEEN :start_date AND :end_date"
                ),
                warnings,
            )

        if is_avg:
            return (
                "Panier moyen facture",
                (
                    "SELECT COALESCE(AVG(total_gross), 0) AS value\n"
                    "FROM finance_invoices\n"
                    "WHERE tenant_id = :tenant_id\n"
                    "  AND company_id = :company_id\n"
                    "  AND invoice_type = 'sale'\n"
                    "  AND status != 'void'\n"
                    "  AND issue_date BETWEEN :start_date AND :end_date"
                ),
                warnings,
            )

        return (
            "Montant factures",
            (
                "SELECT COALESCE(SUM(total_gross), 0) AS value\n"
                "FROM finance_invoices\n"
                "WHERE tenant_id = :tenant_id\n"
                "  AND company_id = :company_id\n"
                "  AND invoice_type = 'sale'\n"
                "  AND status != 'void'\n"
                "  AND issue_date BETWEEN :start_date AND :end_date"
            ),
            warnings,
        )

    if is_count:
        return (
            "Nombre de transactions",
            (
                "SELECT COUNT(*) AS value\n"
                "FROM finance_transactions\n"
                "WHERE tenant_id = :tenant_id\n"
                "  AND company_id = :company_id\n"
                "  AND txn_date BETWEEN :start_date AND :end_date"
            ),
            warnings,
        )

    if is_avg and is_expense:
        return (
            "Dépense moyenne",
            (
                "SELECT COALESCE(AVG(CASE WHEN amount < 0 THEN -amount END), 0) AS value\n"
                "FROM finance_transactions\n"
                "WHERE tenant_id = :tenant_id\n"
                "  AND company_id = :company_id\n"
                "  AND txn_date BETWEEN :start_date AND :end_date"
            ),
            warnings,
        )

    if is_avg and is_income:
        return (
            "Revenu moyen",
            (
                "SELECT COALESCE(AVG(CASE WHEN amount > 0 THEN amount END), 0) AS value\n"
                "FROM finance_transactions\n"
                "WHERE tenant_id = :tenant_id\n"
                "  AND company_id = :company_id\n"
                "  AND txn_date BETWEEN :start_date AND :end_date"
            ),
            warnings,
        )

    if is_expense:
        return (
            "Dépenses totales",
            (
                "SELECT COALESCE(SUM(CASE WHEN amount < 0 THEN -amount ELSE 0 END), 0) AS value\n"
                "FROM finance_transactions\n"
                "WHERE tenant_id = :tenant_id\n"
                "  AND company_id = :company_id\n"
                "  AND txn_date BETWEEN :start_date AND :end_date"
            ),
            warnings,
        )

    if is_income:
        return (
            "Revenus totaux",
            (
                "SELECT COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0) AS value\n"
                "FROM finance_transactions\n"
                "WHERE tenant_id = :tenant_id\n"
                "  AND company_id = :company_id\n"
                "  AND txn_date BETWEEN :start_date AND :end_date"
            ),
            warnings,
        )

    warnings.append("Interprétation heuristique générique appliquée.")
    return (
        "Flux net",
        (
            "SELECT COALESCE(SUM(amount), 0) AS value\n"
            "FROM finance_transactions\n"
            "WHERE tenant_id = :tenant_id\n"
            "  AND company_id = :company_id\n"
            "  AND txn_date BETWEEN :start_date AND :end_date"
        ),
        warnings,
    )


def _openai_indicator_from_nl(text: str, lang: str | None = None, source_hint: str | None = None) -> tuple[str, str, list[str]]:
    runtime = resolve_ai_runtime_config(default_model="gpt-4o-mini")
    api_key = runtime.get("api_key")
    if not api_key:
        raise RuntimeError(f"{runtime.get('missing_key_env') or 'OPENAI_API_KEY'} missing")

    model = runtime.get("model") or "gpt-4o-mini"
    base_url = runtime.get("base_url") or "https://api.openai.com/v1"

    schema_context = {
        "tables": {
            "finance_transactions": ["id", "tenant_id", "company_id", "txn_date", "amount", "category", "counterparty", "account_id"],
            "finance_invoices": ["id", "tenant_id", "company_id", "invoice_type", "status", "issue_date", "due_date", "total_net", "total_tax", "total_gross"],
            "finance_accounts": ["id", "tenant_id", "company_id", "name", "account_type", "side", "currency", "balance", "limit_amount"],
            "finance_liabilities": ["id", "tenant_id", "company_id", "name", "outstanding_amount", "maturity_date", "interest_rate"],
            "finance_investments": ["id", "tenant_id", "company_id", "name", "provider", "invested_amount", "current_value", "status", "started_on"],
        },
        "rules": {
            "read_only": True,
            "single_scalar": True,
            "must_include_placeholders": [":tenant_id", ":company_id", ":start_date", ":end_date"],
            "expected_alias": "value",
            "forbidden_keywords": ["insert", "update", "delete", "drop", "alter", "truncate", "create"],
        },
    }
    selected_source = _normalize_source_hint(source_hint)
    if selected_source:
        schema_context["preferred_source"] = selected_source
        schema_context["preferred_table"] = _SOURCE_TABLE_MAP[selected_source]

    system_prompt = (
        "You generate SQL scalar indicators for AUDELA Finance. "
        "Return ONLY JSON with keys: name, sql, warnings. "
        "SQL must be read-only and return one numeric column aliased as value. "
        "SQL must include :tenant_id, :company_id, :start_date, :end_date placeholders. "
        "Use only provided tables/columns. No markdown, no comments."
    )

    payload = {
        "model": model,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "Context (JSON):\n"
                    + json.dumps(schema_context, ensure_ascii=False, default=_json_default)
                    + "\n\nLanguage: "
                    + str(lang or "fr")
                    + "\nPreferred source: "
                    + str(selected_source or "auto")
                    + "\n\nUser request:\n"
                    + str(text or "")
                ),
            },
        ],
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    url = f"{base_url.rstrip('/')}/chat/completions"
    response = requests.post(url, headers=headers, json=payload, timeout=60)
    if response.status_code >= 400:
        payload.pop("response_format", None)
        response = requests.post(url, headers=headers, json=payload, timeout=60)
    response.raise_for_status()

    body = response.json()
    content = (body.get("choices") or [{}])[0].get("message", {}).get("content") or "{}"

    try:
        parsed = json.loads(content)
    except Exception as exc:
        raise RuntimeError("OpenAI returned invalid JSON") from exc

    if not isinstance(parsed, dict):
        raise RuntimeError("OpenAI output must be a JSON object")

    name = str(parsed.get("name") or "Indicateur scalaire").strip()
    sql_text = str(parsed.get("sql") or "").strip()
    warnings = parsed.get("warnings") if isinstance(parsed.get("warnings"), list) else []

    validate_scalar_sql(sql_text)
    if ":start_date" not in sql_text or ":end_date" not in sql_text:
        raise RuntimeError("SQL généré sans placeholders de période (:start_date/:end_date)")

    return name, sql_text, [str(w) for w in warnings[:8]]


def generate_scalar_indicator_from_nl(text: str, lang: str | None = None, source_hint: str | None = None) -> dict[str, Any]:
    runtime = resolve_ai_runtime_config(default_model="gpt-4o-mini")
    if runtime.get("api_key"):
        try:
            name, sql_text, warnings = _openai_indicator_from_nl(text, lang=lang, source_hint=source_hint)
            return {"name": name, "sql": sql_text, "warnings": warnings}
        except Exception as exc:
            name, sql_text, warnings = _heuristic_indicator_from_nl(text, lang=lang, source_hint=source_hint)
            warnings = warnings or []
            warnings.insert(0, f"Fallback heuristique: {exc}")
            return {"name": name, "sql": sql_text, "warnings": warnings}

    name, sql_text, warnings = _heuristic_indicator_from_nl(text, lang=lang, source_hint=source_hint)
    return {"name": name, "sql": sql_text, "warnings": warnings}

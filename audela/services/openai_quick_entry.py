from __future__ import annotations

import json
import os
from datetime import date
from typing import Any, Dict, Optional

import requests


class OpenAIQuickEntryError(RuntimeError):
    pass


def _env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    if v is None or v == "":
        return default
    return v


def _extract_openai_error_message(raw_text: str) -> str:
    if not raw_text:
        return "Unknown error"
    txt = raw_text.strip()
    try:
        j = json.loads(txt)
        if isinstance(j, dict):
            err = j.get("error")
            if isinstance(err, dict):
                msg = err.get("message")
                if isinstance(msg, str) and msg.strip():
                    return msg.strip()
    except Exception:
        pass
    return txt[:280]


def _build_schema() -> Dict[str, Any]:
    """Structured Outputs schema for quick entry parsing.

    IMPORTANT (strict): every key in properties must appear in required.
    Optional values are modeled with a union including null.
    """

    return {
        "type": "object",
        "properties": {
            "direction": {
                "type": "string",
                "description": "inflow or outflow",
                "enum": ["inflow", "outflow"],
            },
            "amount": {
                "type": "number",
                "description": "Absolute amount (positive).",
            },
            "currency": {
                "type": ["string", "null"],
                "description": "ISO 4217 (e.g., EUR).",
            },
            "category": {
                "type": ["string", "null"],
                "description": "Category name, if provided.",
            },
            "counterparty": {
                "type": ["string", "null"],
                "description": "Merchant/counterparty name, if provided.",
            },
            "description": {
                "type": ["string", "null"],
                "description": "Short free-text description, optional.",
            },
            "txn_date": {
                "type": ["string", "null"],
                "description": "ISO date YYYY-MM-DD. If absent, null.",
            },
        },
        "required": [
            "direction",
            "amount",
            "currency",
            "category",
            "counterparty",
            "description",
            "txn_date",
        ],
        "additionalProperties": False,
    }


def parse_quick_entry_text_via_openai(
    text: str,
    *,
    lang: Optional[str] = None,
    default_currency: str = "EUR",
) -> Dict[str, Any]:
    api_key = _env("OPENAI_API_KEY")
    if not api_key:
        raise OpenAIQuickEntryError("OPENAI_API_KEY missing")

    model = _env("OPENAI_MODEL", "gpt-4o-mini")
    base_url = _env("OPENAI_BASE_URL", "https://api.openai.com/v1")
    timeout_s = int(_env("OPENAI_QUICK_ENTRY_TIMEOUT_SECONDS", "25") or 25)

    schema = _build_schema()
    today = date.today().isoformat()
    lang_hint = (lang or "").strip() or "auto"

    sys_prompt = (
        "You are a finance assistant. Convert a short user note into a single bank transaction. "
        "Return ONLY JSON matching the provided schema (no markdown, no extra text). "
        "If direction is unclear, infer it from words like income/salary/refund vs purchase/rent/tax. "
        "Amount must be absolute (positive). "
        "If the user did not specify a currency, use the default_currency. "
        "If the user did not specify a date, return null for txn_date."
    )

    user_prompt = (
        f"Context:\n"
        f"- today: {today}\n"
        f"- default_currency: {default_currency}\n"
        f"- lang_hint: {lang_hint}\n\n"
        f"User note:\n{text.strip()[:4000]}"
    )

    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "quick_entry_transaction",
                "schema": schema,
                "strict": True,
            },
        },
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    url = f"{base_url.rstrip('/')}/chat/completions"
    try:
        r = requests.post(url, headers=headers, json=body, timeout=(10, timeout_s))
    except requests.Timeout as e:
        raise OpenAIQuickEntryError(f"OpenAI timeout after {timeout_s}s") from e
    except requests.RequestException as e:
        raise OpenAIQuickEntryError(f"OpenAI request failed: {str(e)[:200]}") from e

    if not r.ok:
        msg = _extract_openai_error_message(r.text)
        raise OpenAIQuickEntryError(f"OpenAI error ({r.status_code}): {msg}")

    payload = r.json() or {}
    content = (payload.get("choices") or [{}])[0].get("message", {}).get("content")
    if not content:
        raise OpenAIQuickEntryError("OpenAI returned empty content")

    try:
        obj = json.loads(content)
    except Exception as e:
        raise OpenAIQuickEntryError(f"OpenAI output is not valid JSON: {e}") from e
    if not isinstance(obj, dict):
        raise OpenAIQuickEntryError("OpenAI output JSON is not an object")

    # Basic normalization
    if obj.get("currency") in (None, ""):
        obj["currency"] = default_currency
    return obj

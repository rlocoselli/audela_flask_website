from __future__ import annotations

import io
import json
import os
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import requests

from .bank_statement import (
    StatementImportError,
    detect_bank_from_text,
    extract_text_google_vision,
    extract_text_pdfplumber,
    extract_text_tesseract,
)


class OpenAIStatementError(RuntimeError):
    pass


def _extract_openai_error_message(raw_text: str) -> str:
    """Best-effort extraction of OpenAI error message from a JSON payload."""
    if not raw_text:
        return "Unknown error"
    txt = raw_text.strip()
    # Try JSON: {"error": {"message": "..."}}
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
    # Fallback to raw text (trim)
    return txt[:280]


def _env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    if v is None or v == "":
        return default
    return v


def _build_schema() -> Dict[str, Any]:
    """JSON schema for Structured Outputs.

    Note: keep to a conservative subset for `strict: true`.
    """

    txn_item = {
        "type": "object",
        "properties": {
            "txn_date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
            "description": {"type": "string"},
            "amount": {"type": "number", "description": "Debit negative, credit positive"},
            "currency": {"type": ["string", "null"], "description": "ISO 4217 (e.g., EUR)"},
            "counterparty": {"type": ["string", "null"], "description": "Merchant / counterparty name, optional"},
            "reference": {"type": ["string", "null"], "description": "Transaction reference / id, optional"},
            "balance": {"type": ["number", "null"], "description": "Account balance after txn, optional"},
        },
        # In strict mode, every key in `properties` must be present in `required`.
        # Optional values can be emulated by allowing `null` in the property's type.
        "required": [
            "txn_date",
            "description",
            "amount",
            "currency",
            "counterparty",
            "reference",
            "balance",
        ],
        "additionalProperties": False,
    }

    schema = {
        "type": "object",
        "properties": {
            "bank": {"type": ["string", "null"], "description": "Detected bank id: bnp|sg|revolut|generic"},
            "currency": {"type": ["string", "null"], "description": "Statement currency (ISO 4217)"},
            "transactions": {"type": "array", "items": txn_item},
        },
        # OpenAI strict schema requirement: `required` must include *every* key in `properties`.
        "required": ["bank", "currency", "transactions"],
        "additionalProperties": False,
    }
    return schema


def _extract_text_with_optional_ocr(
    pdf_bytes: bytes,
    *,
    max_pages: int,
    google_vision_api_key: Optional[str] = None,
) -> Tuple[str, Dict[str, Any]]:
    """Extract text from PDF. If empty, optionally try OCR."""

    meta: Dict[str, Any] = {}
    text = ""
    try:
        text = extract_text_pdfplumber(pdf_bytes, max_pages=max_pages)
        meta["extractor"] = "pdfplumber"
        meta["extracted_chars"] = len(text)
    except Exception as e:
        meta["extractor_error"] = str(e)[:250]

    if len((text or "").strip()) >= 250:
        return text, meta

    # OCR fallbacks
    if google_vision_api_key:
        try:
            text = extract_text_google_vision(pdf_bytes, api_key=google_vision_api_key, max_pages=min(max_pages, 5))
            meta["extractor"] = "google_vision"
            meta["extracted_chars"] = len(text)
            if len((text or "").strip()) >= 250:
                return text, meta
        except Exception as e:
            meta["google_vision_error"] = str(e)[:250]

    try:
        text = extract_text_tesseract(pdf_bytes, max_pages=min(max_pages, 5))
        meta["extractor"] = "tesseract"
        meta["extracted_chars"] = len(text)
    except Exception as e:
        meta["tesseract_error"] = str(e)[:250]

    return text or "", meta


def _call_openai_structured_json(
    *,
    api_key: str,
    model: str,
    base_url: str,
    system_prompt: str,
    user_text: str,
    timeout: int | None = None,
) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}/chat/completions"

    # Keep the whole request under common reverse-proxy limits.
    # Default: 110s (just under 2 minutes).
    if timeout is None:
        try:
            timeout = int(_env("OPENAI_HTTP_TIMEOUT_SECONDS", "110") or 110)
        except Exception:
            timeout = 110

    schema = _build_schema()
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "bank_statement_transactions",
                "schema": schema,
                "strict": True,
            },
        },
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        # (connect timeout, read timeout)
        r = requests.post(url, headers=headers, json=body, timeout=(10, timeout))
    except requests.Timeout as e:
        raise OpenAIStatementError(f"OpenAI timeout after {timeout}s") from e
    except requests.RequestException as e:
        raise OpenAIStatementError(f"OpenAI request failed: {str(e)[:200]}") from e

    if not r.ok:
        msg = _extract_openai_error_message(r.text)
        raise OpenAIStatementError(f"OpenAI error ({r.status_code}): {msg}")
    payload = r.json() or {}
    content = (payload.get("choices") or [{}])[0].get("message", {}).get("content")
    if not content:
        raise OpenAIStatementError("OpenAI returned empty content")
    try:
        obj = json.loads(content)
    except Exception as e:
        raise OpenAIStatementError(f"OpenAI output is not valid JSON: {e}") from e
    if not isinstance(obj, dict):
        raise OpenAIStatementError("OpenAI output JSON is not an object")
    return obj


def parse_bank_statement_pdf_via_openai(
    pdf_bytes: bytes,
    *,
    filename: str = "statement.pdf",
    default_currency: str = "EUR",
    bank_hint: Optional[str] = None,
    google_vision_api_key: Optional[str] = None,
    max_pages: int = 10,
) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
    """Parse a bank statement PDF with OpenAI Structured Outputs.

    Returns: (bank_detected, rows, meta)
    where rows are dicts compatible with finance.statement_import.
    """

    api_key = _env("OPENAI_API_KEY")
    if not api_key:
        raise OpenAIStatementError("OPENAI_API_KEY missing")

    model = _env("OPENAI_MODEL", "gpt-4o-mini")
    base_url = _env("OPENAI_BASE_URL", "https://api.openai.com/v1")

    text, meta = _extract_text_with_optional_ocr(
        pdf_bytes,
        max_pages=max_pages,
        google_vision_api_key=google_vision_api_key,
    )

    if len((text or "").strip()) < 50:
        raise StatementImportError("Unable to extract text from PDF (try OCR providers)")

    detected = detect_bank_from_text(text)
    bank = bank_hint or detected
    meta["bank_detected"] = detected
    meta["bank_hint"] = bank_hint
    meta["filename"] = filename

    sys_prompt = (
        "You are a bank statement parser. Extract transactions from raw statement text. "
        "Return ONLY JSON that matches the provided schema. "
        "Do not include balances summary lines, opening/closing balance, or totals. "
        "Debit must be negative and credit positive. "
        "Normalize dates to ISO YYYY-MM-DD."
    )

    user_prompt = (
        f"Statement metadata:\n"
        f"- bank_hint: {bank}\n"
        f"- default_currency: {default_currency}\n"
        f"\nStatement text (may include multiple pages):\n{text[:120000]}"
    )

    obj = _call_openai_structured_json(
        api_key=api_key,
        model=model or "gpt-4o-mini",
        base_url=base_url or "https://api.openai.com/v1",
        system_prompt=sys_prompt,
        user_text=user_prompt,
    )

    out_rows: List[Dict[str, Any]] = []
    currency = (obj.get("currency") or default_currency or "EUR").strip()[:8]
    bank_out = (obj.get("bank") or bank).strip().lower() if isinstance(obj.get("bank"), str) else bank

    for t in (obj.get("transactions") or []):
        if not isinstance(t, dict):
            continue
        ds = (t.get("txn_date") or "").strip()
        desc = (t.get("description") or "").strip()
        amt = t.get("amount")
        if not ds or not desc or amt is None:
            continue
        try:
            d = datetime.strptime(ds[:10], "%Y-%m-%d").date()
        except Exception:
            # try a couple common formats
            d = None
            for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
                try:
                    d = datetime.strptime(ds, fmt).date()
                    break
                except Exception:
                    pass
            if d is None:
                continue
        try:
            amount_f = float(amt)
        except Exception:
            continue

        out_rows.append(
            {
                "txn_date": d,
                "amount": amount_f,
                "description": desc,
                "category": None,
                "counterparty": (t.get("counterparty") or "").strip() or None,
                "currency": (t.get("currency") or currency).strip() or currency,
                "reference": (t.get("reference") or "").strip() or None,
                "balance": t.get("balance"),
                "raw": t,
            }
        )

    meta["openai_model"] = model
    meta["openai_rows"] = len(out_rows)
    return bank_out or bank, out_rows, meta

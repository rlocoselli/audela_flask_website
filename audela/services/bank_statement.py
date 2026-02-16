from __future__ import annotations

import base64
import io
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import requests


class StatementImportError(RuntimeError):
    pass


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        s = str(value).strip().replace(" ", "")
        s = s.replace(".", "").replace(",", ".")
        return float(s)
    except Exception:
        return None


def detect_bank_from_text(text: str) -> str:
    t = (text or "").lower()
    if "bnp" in t and "paribas" in t:
        return "bnp"
    if "société générale" in t or "societe generale" in t or "sg" in t and "soci" in t:
        return "sg"
    if "revolut" in t:
        return "revolut"
    return "generic"


@dataclass
class ParsedTransaction:
    date: date
    description: str
    amount: float
    balance: Optional[float] = None
    counterparty: Optional[str] = None
    currency: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None


def parse_text_transactions(text: str, bank: Optional[str] = None, *, default_currency: str = "EUR") -> Tuple[str, List[ParsedTransaction]]:
    bank = bank or detect_bank_from_text(text)
    text = text or ""

    # Extremely pragmatic parsing: most bank statements will have a line per operation starting with a date.
    # We keep dedicated regex variants for a few banks but also offer a generic fallback.

    patterns: List[re.Pattern]
    if bank == "revolut":
        patterns = [
            re.compile(r"^(?P<d>\d{4}-\d{2}-\d{2})\s+(?P<desc>.+?)\s+(?P<amt>[-+]?\d+[\.,]\d{2})\s*(?P<ccy>[A-Z]{3})?$", re.M),
        ]
    else:
        # Common French statements: dd/mm/yyyy ... amount
        patterns = [
            re.compile(r"^(?P<d>\d{2}/\d{2}/\d{4})\s+(?P<desc>.+?)\s+(?P<amt>[-+]?\d+[\.,]\d{2})\s*(?P<bal>\d+[\.,]\d{2})?$", re.M),
            re.compile(r"^(?P<d>\d{2}-\d{2}-\d{4})\s+(?P<desc>.+?)\s+(?P<amt>[-+]?\d+[\.,]\d{2})\s*(?P<bal>\d+[\.,]\d{2})?$", re.M),
        ]

    results: List[ParsedTransaction] = []
    for pat in patterns:
        for m in pat.finditer(text):
            ds = m.group("d")
            try:
                if "-" in ds and len(ds) == 10 and ds[4] == "-":
                    d = datetime.strptime(ds, "%Y-%m-%d").date()
                elif "/" in ds:
                    d = datetime.strptime(ds, "%d/%m/%Y").date()
                else:
                    d = datetime.strptime(ds, "%d-%m-%Y").date()
            except Exception:
                continue
            desc = (m.group("desc") or "").strip()
            amt = _safe_float(m.group("amt"))
            if amt is None:
                continue
            bal = _safe_float(m.groupdict().get("bal"))
            ccy = (m.groupdict().get("ccy") or default_currency).strip() if m.groupdict().get("ccy") else default_currency
            results.append(ParsedTransaction(date=d, description=desc, amount=amt, balance=bal, currency=ccy))

        if results:
            break

    # If nothing matched, fallback to a looser parser: scan lines and try to find a date + amount.
    if not results:
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            m = re.match(r"^(\d{2}/\d{2}/\d{4})\s+(.+)$", line)
            if not m:
                continue
            ds = m.group(1)
            rest = m.group(2)
            am = re.search(r"([-+]?\d+[\.,]\d{2})\s*$", rest)
            if not am:
                continue
            try:
                d = datetime.strptime(ds, "%d/%m/%Y").date()
            except Exception:
                continue
            amt = _safe_float(am.group(1))
            desc = rest[: am.start()].strip()
            if amt is None:
                continue
            results.append(ParsedTransaction(date=d, description=desc, amount=amt, currency=default_currency))

    return bank, results


def extract_text_pdfplumber(pdf_bytes: bytes, *, max_pages: int = 10) -> str:
    try:
        import pdfplumber
    except Exception as e:
        raise StatementImportError("pdfplumber not installed") from e
    text_parts: List[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for i, page in enumerate(pdf.pages[:max_pages]):
            try:
                t = page.extract_text() or ""
            except Exception:
                t = ""
            if t:
                text_parts.append(t)
    return "\n".join(text_parts)


def extract_text_tesseract(pdf_bytes: bytes, *, max_pages: int = 5) -> str:
    """OCR fallback using local Tesseract.

    Requires system dependencies: poppler (pdf2image) and tesseract.
    """
    try:
        from pdf2image import convert_from_bytes
        import pytesseract
    except Exception as e:
        raise StatementImportError("Tesseract OCR dependencies not installed") from e
    images = convert_from_bytes(pdf_bytes, fmt="png", first_page=1, last_page=max_pages)
    parts: List[str] = []
    for img in images:
        parts.append(pytesseract.image_to_string(img) or "")
    return "\n".join(parts)


def extract_text_google_vision(pdf_bytes: bytes, *, api_key: str, max_pages: int = 5) -> str:
    """OCR fallback using Google Vision (image-based, no GCS required).

    We convert the PDF pages to images locally then call `images:annotate` with DOCUMENT_TEXT_DETECTION.
    """
    try:
        from pdf2image import convert_from_bytes
    except Exception as e:
        raise StatementImportError("pdf2image not installed") from e

    images = convert_from_bytes(pdf_bytes, fmt="png", first_page=1, last_page=max_pages)
    requests_payload = []
    for img in images:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        content = base64.b64encode(buf.getvalue()).decode("ascii")
        requests_payload.append(
            {
                "image": {"content": content},
                "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
            }
        )

    url = f"https://vision.googleapis.com/v1/images:annotate?key={api_key}"
    r = requests.post(url, json={"requests": requests_payload}, timeout=60)
    if not r.ok:
        raise StatementImportError(f"Google Vision OCR failed ({r.status_code}): {r.text[:400]}")
    payload = r.json() or {}
    parts: List[str] = []
    for resp in payload.get("responses", []):
        ta = resp.get("fullTextAnnotation") or {}
        txt = ta.get("text") or ""
        if txt:
            parts.append(txt)
    return "\n".join(parts)


def parse_pdf_via_mindee(pdf_bytes: bytes, *, api_key: str) -> Tuple[str, List[ParsedTransaction]]:
    """Use Mindee Bank Statement model (if configured) to obtain transactions."""
    url = "https://api.mindee.net/v1/products/mindee/bank_statement/v1/predict"
    headers = {"Authorization": f"Token {api_key}"}
    files = {"document": ("statement.pdf", pdf_bytes, "application/pdf")}
    r = requests.post(url, headers=headers, files=files, timeout=90)
    if not r.ok:
        raise StatementImportError(f"Mindee failed ({r.status_code}): {r.text[:400]}")
    payload = r.json() or {}
    # Mindee schema can vary; we try common paths.
    prediction = (
        payload.get("document", {})
        .get("inference", {})
        .get("prediction", {})
    )
    transactions = prediction.get("transactions") or prediction.get("operations") or []
    out: List[ParsedTransaction] = []
    for t in transactions:
        ds = t.get("date") or t.get("value_date") or t.get("operation_date")
        if not ds:
            continue
        try:
            d = datetime.fromisoformat(ds).date() if "-" in ds else datetime.strptime(ds, "%d/%m/%Y").date()
        except Exception:
            continue
        desc = (t.get("description") or t.get("label") or t.get("name") or "").strip()
        amt = _safe_float(t.get("amount") or t.get("value") or t.get("amount_value"))
        if amt is None:
            continue
        bal = _safe_float(t.get("balance"))
        ccy = (t.get("currency") or "EUR").strip()
        cp = (t.get("counterparty") or t.get("merchant") or "").strip() or None
        out.append(ParsedTransaction(date=d, description=desc, amount=amt, balance=bal, currency=ccy, counterparty=cp, raw=t))
    return "mindee", out


def import_bank_statement(
    pdf_bytes: bytes,
    *,
    prefer: str = "local",
    default_currency: str = "EUR",
    bank_hint: Optional[str] = None,
    mindee_api_key: Optional[str] = None,
    google_vision_api_key: Optional[str] = None,
    max_pages: int = 10,
) -> Tuple[str, List[ParsedTransaction], Dict[str, Any]]:
    """High-level import with fallback strategies.

    prefer: local|mindee|google|tesseract
    """
    meta: Dict[str, Any] = {"method": prefer}

    def _local() -> Tuple[str, List[ParsedTransaction]]:
        txt = extract_text_pdfplumber(pdf_bytes, max_pages=max_pages)
        meta["extracted_chars"] = len(txt)
        bank, txns = parse_text_transactions(txt, bank=bank_hint, default_currency=default_currency)
        meta["bank"] = bank
        return bank, txns

    if prefer == "mindee":
        if not mindee_api_key:
            raise StatementImportError("MINDEE_API_KEY missing")
        bank, txns = parse_pdf_via_mindee(pdf_bytes, api_key=mindee_api_key)
        meta["bank"] = bank
        return bank, txns, meta

    if prefer == "google":
        if not google_vision_api_key:
            raise StatementImportError("GOOGLE_VISION_API_KEY missing")
        txt = extract_text_google_vision(pdf_bytes, api_key=google_vision_api_key, max_pages=min(max_pages, 5))
        meta["extracted_chars"] = len(txt)
        bank, txns = parse_text_transactions(txt, bank=bank_hint, default_currency=default_currency)
        meta["bank"] = bank
        return bank, txns, meta

    if prefer == "tesseract":
        txt = extract_text_tesseract(pdf_bytes, max_pages=min(max_pages, 5))
        meta["extracted_chars"] = len(txt)
        bank, txns = parse_text_transactions(txt, bank=bank_hint, default_currency=default_currency)
        meta["bank"] = bank
        return bank, txns, meta

    # Default: local with fallback strategy
    bank, txns = _local()
    if txns:
        return bank, txns, meta

    # Fallbacks: Mindee then OCR
    if mindee_api_key:
        try:
            b2, t2 = parse_pdf_via_mindee(pdf_bytes, api_key=mindee_api_key)
            if t2:
                meta["method"] = "mindee_fallback"
                meta["bank"] = b2
                return b2, t2, meta
        except Exception:
            pass

    if google_vision_api_key:
        try:
            txt = extract_text_google_vision(pdf_bytes, api_key=google_vision_api_key, max_pages=3)
            b2, t2 = parse_text_transactions(txt, bank=bank_hint, default_currency=default_currency)
            if t2:
                meta["method"] = "google_vision_fallback"
                meta["bank"] = b2
                return b2, t2, meta
        except Exception:
            pass

    # Last resort: local Tesseract
    try:
        txt = extract_text_tesseract(pdf_bytes, max_pages=3)
        b2, t2 = parse_text_transactions(txt, bank=bank_hint, default_currency=default_currency)
        meta["method"] = "tesseract_fallback"
        meta["bank"] = b2
        return b2, t2, meta
    except Exception:
        return bank, txns, meta

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
import io
import json
import re
from typing import Any
from urllib.parse import urlparse

import requests

from .ai_runtime_config import resolve_ai_runtime_config


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tables: list[dict[str, Any]] = []
        self._in_table = False
        self._in_row = False
        self._in_cell = False
        self._cell_tag = ""
        self._current_table: list[list[str]] = []
        self._current_table_attrs: dict[str, Any] = {}
        self._current_row: list[str] = []
        self._current_cell_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._in_table = True
            self._current_table = []
            attrs_dict = {str(k): str(v or "") for k, v in (attrs or [])}
            classes = [c for c in (attrs_dict.get("class") or "").split() if c]
            self._current_table_attrs = {
                "id": attrs_dict.get("id") or "",
                "class": classes,
            }
        elif self._in_table and tag == "tr":
            self._in_row = True
            self._current_row = []
        elif self._in_row and tag in {"td", "th"}:
            self._in_cell = True
            self._cell_tag = tag
            self._current_cell_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._current_cell_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._in_cell and tag == self._cell_tag:
            value = re.sub(r"\s+", " ", "".join(self._current_cell_parts)).strip()
            self._current_row.append(value)
            self._in_cell = False
            self._cell_tag = ""
            self._current_cell_parts = []
        elif self._in_row and tag == "tr":
            if any((c or "").strip() for c in self._current_row):
                self._current_table.append(self._current_row)
            self._current_row = []
            self._in_row = False
        elif self._in_table and tag == "table":
            if self._current_table:
                self.tables.append(
                    {
                        "rows": self._current_table,
                        "attrs": dict(self._current_table_attrs),
                    }
                )
            self._current_table = []
            self._current_table_attrs = {}
            self._in_table = False


@dataclass
class ExtractResult:
    columns: list[str]
    rows: list[list[Any]]
    source_url: str
    mode: str


def _fetch_resource(url: str, timeout: int = 30, verify_ssl: bool = True) -> tuple[str, str, bytes]:
    r = requests.get(
        url,
        timeout=timeout,
        verify=bool(verify_ssl),
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; AudelaBot/1.0; +https://audela.example)",
            "Accept-Language": "fr,en;q=0.9,pt;q=0.8",
        },
    )
    # Some pages (notably ratp.fr) can return Cloudflare challenge HTML instead
    # of the target content for server-side clients. In that case, try a known
    # official equivalent URL that is accessible server-side.
    if _is_cloudflare_challenge_response(r):
        fallback_url = _fallback_url_for_cloudflare(url)
        if fallback_url:
            rf = requests.get(
                fallback_url,
                timeout=timeout,
                verify=bool(verify_ssl),
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; AudelaBot/1.0; +https://audela.example)",
                    "Accept-Language": "fr,en;q=0.9,pt;q=0.8",
                },
            )
            rf.raise_for_status()
            content_type_f = (rf.headers.get("content-type") or "").lower()
            final_url_f = str(rf.url or fallback_url)
            return final_url_f, content_type_f, (rf.content or b"")

    r.raise_for_status()
    content_type = (r.headers.get("content-type") or "").lower()
    final_url = str(r.url or url)
    return final_url, content_type, (r.content or b"")


def _is_cloudflare_challenge_response(resp: requests.Response) -> bool:
    status = int(getattr(resp, "status_code", 0) or 0)
    text = (resp.text or "")[:5000].lower() if hasattr(resp, "text") else ""
    if status == 403 and ("cloudflare" in text or "just a moment" in text):
        return True
    if "cf-challenge" in text or "cdn-cgi/challenge-platform" in text:
        return True
    if "enable javascript and cookies to continue" in text:
        return True
    return False


def _fallback_url_for_cloudflare(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()
    path = (parsed.path or "").strip()

    # Official parity page: RATP tariffs page can be blocked by anti-bot,
    # while IDFM page remains accessible and contains tariff information.
    if "ratp.fr" in host and path.startswith("/titres-et-tarifs"):
        return "https://www.iledefrance-mobilites.fr/titres-et-tarifs"

    return ""


def _table_to_headers_rows(table_rows: list[list[str]]) -> tuple[list[str], list[list[str]]]:
    if not table_rows:
        return [], []

    first = table_rows[0]
    has_header = any(re.search(r"[A-Za-zÀ-ÿ]", c or "") for c in first)
    if has_header:
        headers = [(c or "").strip() or f"col_{i+1}" for i, c in enumerate(first)]
        rows = table_rows[1:]
    else:
        width = max((len(r) for r in table_rows), default=0)
        headers = [f"col_{i+1}" for i in range(width)]
        rows = table_rows

    norm_rows: list[list[str]] = []
    for r in rows:
        out = list(r)
        while len(out) < len(headers):
            out.append("")
        norm_rows.append(out[: len(headers)])

    return headers, norm_rows


def _match_table_selector(table_obj: dict[str, Any], selector: str) -> bool:
    selector = (selector or "").strip()
    if not selector:
        return False
    attrs = table_obj.get("attrs") if isinstance(table_obj.get("attrs"), dict) else {}
    table_id = str(attrs.get("id") or "").strip()
    classes = attrs.get("class") if isinstance(attrs.get("class"), list) else []

    if selector.startswith("#"):
        return table_id == selector[1:]
    if selector.startswith("."):
        cls = selector[1:]
        return cls in classes

    m_id = re.search(r"#([A-Za-z0-9_\-:.]+)", selector)
    if m_id and table_id == m_id.group(1):
        return True

    m_class = re.search(r"\.([A-Za-z0-9_\-]+)", selector)
    if m_class and m_class.group(1) in classes:
        return True

    return False


def _best_table(html: str, table_selector: str | None = None) -> tuple[list[str], list[list[str]]]:
    p = _TableParser()
    p.feed(html)
    if not p.tables:
        return [], []

    selector = (table_selector or "").strip()
    if selector:
        nth = re.search(r"table\s*:\s*nth-of-type\((\d+)\)", selector, flags=re.I)
        if nth:
            idx = max(1, int(nth.group(1))) - 1
            if idx < len(p.tables):
                return _table_to_headers_rows(p.tables[idx].get("rows") or [])

        for t in p.tables:
            if _match_table_selector(t, selector):
                return _table_to_headers_rows(t.get("rows") or [])

    best_obj = max(
        p.tables,
        key=lambda t: (
            len(t.get("rows") or []),
            max((len(r) for r in (t.get("rows") or [])), default=0),
        ),
    )
    if not best_obj:
        return [], []
    return _table_to_headers_rows(best_obj.get("rows") or [])


def _best_table_from_pdf(pdf_bytes: bytes, max_rows: int = 300) -> tuple[list[str], list[list[str]], str]:
    try:
        import pdfplumber
    except Exception:
        return [], [], ""

    page_texts: list[str] = []
    all_tables: list[list[list[str]]] = []

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages[:20]:
                txt = page.extract_text() or ""
                if txt.strip():
                    page_texts.append(txt)

                tables = page.extract_tables() or []
                for t in tables:
                    norm_t: list[list[str]] = []
                    for row in t or []:
                        vals = [re.sub(r"\s+", " ", str(c or "")).strip() for c in (row or [])]
                        if any(v for v in vals):
                            norm_t.append(vals)
                    if norm_t:
                        all_tables.append(norm_t)
    except Exception:
        return [], [], "\n".join(page_texts)

    if all_tables:
        best = max(all_tables, key=lambda t: (len(t), max((len(r) for r in t), default=0)))
        first = best[0] if best else []
        has_header = any(re.search(r"[A-Za-zÀ-ÿ]", c or "") for c in first)
        if has_header:
            headers = [(c or "").strip() or f"col_{i+1}" for i, c in enumerate(first)]
            rows = best[1:]
        else:
            width = max((len(r) for r in best), default=0)
            headers = [f"col_{i+1}" for i in range(width)]
            rows = best

        out_rows: list[list[str]] = []
        for r in rows[:max_rows]:
            rr = list(r)
            while len(rr) < len(headers):
                rr.append("")
            out_rows.append(rr[: len(headers)])

        return headers, out_rows, "\n".join(page_texts)

    # No tabular structure detected in PDF -> text lines fallback
    text_blob = "\n".join(page_texts).strip()
    if not text_blob:
        return [], [], ""
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text_blob.splitlines() if ln and ln.strip()]
    rows = [[ln] for ln in lines[:max_rows]]
    return ["text"], rows, text_blob


def _extract_plain_text(html: str, max_chars: int = 12000) -> str:
    cleaned = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    cleaned = re.sub(r"<style[\s\S]*?</style>", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:max_chars]


def _parse_schema(schema_text: str) -> list[str]:
    if not schema_text:
        return []
    parts = [p.strip() for p in re.split(r"[,;\n]", schema_text) if p.strip()]
    seen: set[str] = set()
    cols: list[str] = []
    for p in parts:
        key = _norm(p)
        if key in seen:
            continue
        seen.add(key)
        cols.append(p)
    return cols


def _map_rows_to_schema(src_cols: list[str], src_rows: list[list[Any]], dst_cols: list[str], max_rows: int) -> list[list[Any]]:
    if not dst_cols:
        return src_rows[:max_rows]

    src_index = { _norm(c): i for i, c in enumerate(src_cols) }
    out: list[list[Any]] = []
    for r in src_rows[:max_rows]:
        row_out = []
        for dc in dst_cols:
            idx = src_index.get(_norm(dc))
            row_out.append(r[idx] if idx is not None and idx < len(r) else None)
        out.append(row_out)
    return out


def _ai_structure_if_possible(
    html_text: str,
    src_cols: list[str],
    src_rows: list[list[Any]],
    target_cols: list[str],
    lang: str | None,
    max_rows: int,
) -> tuple[list[str], list[list[Any]], bool]:
    runtime = resolve_ai_runtime_config(default_model="gpt-4o-mini")
    api_key = runtime.get("api_key")
    base_url = runtime.get("base_url")
    model = runtime.get("model")
    if not api_key or not base_url or not model:
        return src_cols, src_rows[:max_rows], False

    sample_rows = src_rows[:40]
    desired = target_cols or src_cols
    prompt = (
        "Tu structures des données web en table JSON. "
        "Retourne STRICTEMENT un JSON avec: columns (liste) et rows (liste de listes). "
        f"Langue UI: {lang or 'fr'}. "
        f"Colonnes souhaitées: {desired}. "
        f"Colonnes source: {src_cols}. "
        f"Extrait texte: {html_text[:4000]} "
        f"Aperçu lignes: {json.dumps(sample_rows, ensure_ascii=False)[:6000]}"
    )

    payload = {
        "model": model,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "You are a strict data extraction engine."},
            {"role": "user", "content": prompt},
        ],
    }

    resp = requests.post(
        f"{str(base_url).rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=45,
    )
    if resp.status_code >= 400:
        return src_cols, src_rows[:max_rows], False

    data = resp.json() if resp.content else {}
    txt = (data.get("choices") or [{}])[0].get("message", {}).get("content") or "{}"
    try:
        parsed = json.loads(txt)
    except Exception:
        return src_cols, src_rows[:max_rows], False

    cols = parsed.get("columns") if isinstance(parsed, dict) else None
    rows = parsed.get("rows") if isinstance(parsed, dict) else None
    if not isinstance(cols, list) or not isinstance(rows, list):
        return src_cols, src_rows[:max_rows], False

    clean_cols = [str(c).strip() for c in cols if str(c).strip()]
    if not clean_cols:
        return src_cols, src_rows[:max_rows], False

    out_rows: list[list[Any]] = []
    for r in rows[:max_rows]:
        if isinstance(r, list):
            rr = list(r)
            while len(rr) < len(clean_cols):
                rr.append(None)
            out_rows.append(rr[: len(clean_cols)])
    if not out_rows:
        return src_cols, src_rows[:max_rows], False

    return clean_cols, out_rows, True


def extract_structured_table_from_web(
    url: str,
    schema_text: str = "",
    lang: str | None = None,
    max_rows: int = 300,
    verify_ssl: bool = True,
    table_selector: str | None = None,
) -> ExtractResult:
    final_url, content_type, content = _fetch_resource(url, verify_ssl=verify_ssl)
    is_pdf = (
        "application/pdf" in content_type
        or final_url.lower().endswith(".pdf")
        or str(url).lower().endswith(".pdf")
    )

    source_text_for_ai = ""
    src_cols: list[str]
    src_rows: list[list[Any]]

    if is_pdf:
        src_cols, src_rows, pdf_text = _best_table_from_pdf(content, max_rows=max_rows)
        source_text_for_ai = pdf_text[:12000]
        if not src_cols:
            source_text_for_ai = (content.decode("utf-8", errors="ignore") or "")[:12000]
            snippets = [s.strip() for s in re.split(r"[.!?]\s+", source_text_for_ai) if s.strip()][:max_rows]
            src_cols = ["text"]
            src_rows = [[s] for s in snippets]
    else:
        html = content.decode("utf-8", errors="ignore")
        src_cols, src_rows = _best_table(html, table_selector=table_selector)
        source_text_for_ai = _extract_plain_text(html, max_chars=12000)

        if not src_cols:
            txt = _extract_plain_text(html, max_chars=20000)
            snippets = [s.strip() for s in re.split(r"[.!?]\s+", txt) if s.strip()][:max_rows]
            src_cols = ["text"]
            src_rows = [[s] for s in snippets]

    target_cols = _parse_schema(schema_text)
    ai_cols, ai_rows, used_ai = _ai_structure_if_possible(
        source_text_for_ai,
        src_cols,
        src_rows,
        target_cols,
        lang,
        max_rows,
    )

    if used_ai:
        return ExtractResult(columns=ai_cols, rows=ai_rows, source_url=final_url, mode="ai")

    out_cols = target_cols or src_cols
    out_rows = _map_rows_to_schema(src_cols, src_rows, out_cols, max_rows=max_rows)
    return ExtractResult(columns=out_cols, rows=out_rows, source_url=final_url, mode="heuristic")


def _extract_first_url(text: str) -> str:
    m = re.search(r"https?://[^\s)\]>'\"]+", text or "", flags=re.I)
    return str(m.group(0)).strip() if m else ""


def _extract_selector(text: str) -> str:
    src = text or ""
    # Remove URLs first so domains like "oracle.com" are not mistaken as
    # CSS class selectors (e.g. ".oracle.com").
    src_no_urls = re.sub(r"https?://\S+", " ", src, flags=re.I)

    # Only try selector extraction when user wording hints selector intent.
    has_selector_intent = bool(
        re.search(r"selector|sélecteur|css|id\b|class\b|table\s*:\s*nth-of-type", src_no_urls, flags=re.I)
    )
    if not has_selector_intent:
        return ""

    m = re.search(r"(#[-_A-Za-z0-9:.]+)", src_no_urls)
    if m:
        return str(m.group(1)).strip()
    m = re.search(r"(\.[-_A-Za-z0-9:_-]+)", src_no_urls)
    if m:
        return str(m.group(1)).strip()
    m = re.search(r"(table\s*:\s*nth-of-type\(\s*\d+\s*\))", src_no_urls, flags=re.I)
    if m:
        return str(m.group(1)).strip()
    return ""


def _extract_schema_candidates(text: str) -> list[str]:
    raw = text or ""
    marker = re.search(r"(?:colonnes?|columns?|schema|champs?)\s*[:=-]\s*(.+)", raw, flags=re.I)
    # Keep schema empty when user did not explicitly provide schema markers.
    if not marker:
        return []
    chunk = marker.group(1)
    chunk = re.sub(r"\n+", ",", chunk)
    parts = [p.strip(" .;:-") for p in re.split(r"[,;|]", chunk) if p and p.strip(" .;:-")]
    out: list[str] = []
    seen: set[str] = set()
    for p in parts[:30]:
        key = _norm(p)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def suggest_web_extract_config_from_text(
    prompt_text: str,
    current_url: str = "",
    current_schema: str = "",
    current_selector: str = "",
    current_max_rows: int = 200,
    current_verify_ssl: bool = True,
    lang: str | None = None,
) -> dict[str, Any]:
    """Generate a scraping configuration from natural-language text.

    Returns a dict with: url, schema, table_selector, max_rows, verify_ssl,
    provider, model, used_ai.
    """
    text = (prompt_text or "").strip()
    if not text:
        return {
            "url": current_url,
            "schema": current_schema,
            "table_selector": current_selector,
            "max_rows": int(current_max_rows or 200),
            "verify_ssl": bool(current_verify_ssl),
            "provider": "none",
            "model": "",
            "used_ai": False,
        }

    runtime = resolve_ai_runtime_config(default_model="gpt-4o-mini")
    api_key = runtime.get("api_key") or ""
    base_url = runtime.get("base_url") or ""
    model = runtime.get("model") or ""

    fallback_url = _extract_first_url(text) or (current_url or "")
    fallback_selector = _extract_selector(text) or (current_selector or "")
    fallback_cols = _extract_schema_candidates(text)
    fallback_schema = ", ".join(fallback_cols) if fallback_cols else (current_schema or "")

    rows_guess = int(current_max_rows or 200)
    m_rows = re.search(r"(?:max\s*rows?|lignes?\s*max|rows?)\s*[:= ]\s*(\d{2,4})", text, flags=re.I)
    if m_rows:
        try:
            rows_guess = int(m_rows.group(1))
        except Exception:
            rows_guess = int(current_max_rows or 200)
    rows_guess = max(10, min(1000, rows_guess))

    ssl_guess = bool(current_verify_ssl)
    if re.search(r"(?:sans\s+ssl|no\s+ssl|ignore\s+ssl|skip\s+ssl)", text, flags=re.I):
        ssl_guess = False
    elif re.search(r"(?:avec\s+ssl|verify\s+ssl|ssl\s+on)", text, flags=re.I):
        ssl_guess = True

    if not (api_key and base_url and model):
        return {
            "url": fallback_url,
            "schema": fallback_schema,
            "table_selector": fallback_selector,
            "max_rows": rows_guess,
            "verify_ssl": ssl_guess,
            "provider": "none",
            "model": "",
            "used_ai": False,
        }

    system_prompt = (
        "You are a web scraping configuration assistant. "
        "Return strictly one JSON object with keys: "
        "url (string), schema_columns (array of strings), table_selector (string), "
        "max_rows (integer), verify_ssl (boolean). "
        "Do not include markdown."
    )

    user_payload = {
        "language": lang or "fr",
        "request": text,
        "current": {
            "url": current_url,
            "schema": current_schema,
            "table_selector": current_selector,
            "max_rows": int(current_max_rows or 200),
            "verify_ssl": bool(current_verify_ssl),
        },
        "rules": [
            "Prefer explicit URL from text.",
            "If missing fields, keep current values.",
            "max_rows must be in [10, 1000].",
            "table_selector can be #id, .class or table:nth-of-type(n).",
        ],
    }

    payload = {
        "model": model,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
    }

    try:
        r = requests.post(
            f"{str(base_url).rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=(10, 45),
        )
        if r.status_code >= 400:
            payload.pop("response_format", None)
            r = requests.post(
                f"{str(base_url).rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=(10, 45),
            )
        r.raise_for_status()
        data = r.json() if r.content else {}
        txt = (data.get("choices") or [{}])[0].get("message", {}).get("content") or "{}"
        parsed = json.loads(txt)
    except Exception:
        parsed = {}

    ai_url = str(parsed.get("url") or "").strip() if isinstance(parsed, dict) else ""
    ai_selector = str(parsed.get("table_selector") or "").strip() if isinstance(parsed, dict) else ""
    ai_rows = parsed.get("max_rows") if isinstance(parsed, dict) else None
    ai_ssl = parsed.get("verify_ssl") if isinstance(parsed, dict) else None
    ai_cols_raw = parsed.get("schema_columns") if isinstance(parsed, dict) else None

    ai_cols: list[str] = []
    if isinstance(ai_cols_raw, list):
        seen: set[str] = set()
        for c in ai_cols_raw:
            val = str(c or "").strip()
            key = _norm(val)
            if not val or key in seen:
                continue
            seen.add(key)
            ai_cols.append(val)

    try:
        out_rows = int(ai_rows) if ai_rows is not None else rows_guess
    except Exception:
        out_rows = rows_guess
    out_rows = max(10, min(1000, out_rows))

    out_verify_ssl = bool(ai_ssl) if isinstance(ai_ssl, bool) else ssl_guess
    out_url = ai_url or fallback_url
    out_selector = ai_selector or fallback_selector
    out_schema = ", ".join(ai_cols) if ai_cols else fallback_schema

    return {
        "url": out_url,
        "schema": out_schema,
        "table_selector": out_selector,
        "max_rows": out_rows,
        "verify_ssl": out_verify_ssl,
        "provider": str(runtime.get("provider") or ""),
        "model": str(model),
        "used_ai": bool(parsed),
    }

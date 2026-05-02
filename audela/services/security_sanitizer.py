from __future__ import annotations

import re
from typing import Any

_SENSITIVE_KEY_RE = re.compile(
    r"(?i)(password|passwd|pwd|secret|token|apikey|api_key|access_key|client_secret|authorization)"
)

# Mask credentials embedded in URIs: scheme://user:pass@host -> scheme://user:***@host
_URI_CREDENTIAL_RE = re.compile(r"([a-zA-Z][a-zA-Z0-9+.-]*://[^\s/:@]+:)([^@\s]+)(@)")

# Mask key/value secrets in free text (error messages, logs).
_KV_SECRET_RE = re.compile(
    r"(?i)\b(password|passwd|pwd|secret|token|apikey|api_key|access_key|client_secret)\b\s*[:=]\s*([^\s,;]+)"
)


def redact_secrets_in_text(value: Any, *, max_len: int = 500) -> str:
    text = str(value or "")
    if not text:
        return ""

    text = _URI_CREDENTIAL_RE.sub(r"\1***\3", text)
    text = _KV_SECRET_RE.sub(r"\1=***", text)

    if len(text) > max_len:
        return text[:max_len]
    return text


def safe_error_message(error: Exception | str | Any, *, fallback: str = "Operation failed") -> str:
    redacted = redact_secrets_in_text(error)
    return redacted or fallback


def redact_sensitive_mapping(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}

    out: dict[str, Any] = {}
    for key, value in payload.items():
        k = str(key)
        if _SENSITIVE_KEY_RE.search(k):
            out[k] = "***"
            continue

        if isinstance(value, dict):
            out[k] = redact_sensitive_mapping(value)
        elif isinstance(value, list):
            sanitized_list: list[Any] = []
            for item in value:
                if isinstance(item, dict):
                    sanitized_list.append(redact_sensitive_mapping(item))
                else:
                    sanitized_list.append(redact_secrets_in_text(item, max_len=200))
            out[k] = sanitized_list
        else:
            out[k] = redact_secrets_in_text(value, max_len=200)
    return out

from __future__ import annotations

import os
from typing import Any

from flask import g, has_request_context


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value


def _tenant_ai_settings() -> dict[str, Any]:
    if not has_request_context():
        return {}
    tenant = getattr(g, "tenant", None)
    if not tenant:
        return {}
    settings = tenant.settings_json if isinstance(getattr(tenant, "settings_json", None), dict) else {}
    ai = settings.get("ai") if isinstance(settings.get("ai"), dict) else {}
    return ai


def resolve_ai_runtime_config(default_model: str) -> dict[str, str]:
    ai = _tenant_ai_settings()
    provider = str(ai.get("provider") or "openai").strip().lower()
    if provider not in {"openai", "mistral"}:
        provider = "openai"

    model_override = str(ai.get("model") or "").strip()

    if provider == "mistral":
        api_key = _env("MISTRAL_API_KEY", "") or ""
        base_url = _env("MISTRAL_BASE_URL", "https://api.mistral.ai/v1") or "https://api.mistral.ai/v1"
        model = model_override or (_env("MISTRAL_MODEL", "mistral-small-latest") or "mistral-small-latest")
        return {
            "provider": "mistral",
            "api_key": api_key,
            "base_url": base_url,
            "model": model,
            "missing_key_env": "MISTRAL_API_KEY",
        }

    api_key = _env("OPENAI_API_KEY", "") or ""
    base_url = _env("OPENAI_BASE_URL", "https://api.openai.com/v1") or "https://api.openai.com/v1"
    model = model_override or (_env("OPENAI_MODEL", default_model) or default_model)
    return {
        "provider": "openai",
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "missing_key_env": "OPENAI_API_KEY",
    }

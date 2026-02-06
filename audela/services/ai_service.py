from __future__ import annotations

import json
import os
from typing import Any

import requests

from ..i18n import DEFAULT_LANG, tr


def _env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    if v is None or v == "":
        return default
    return v


def _json_safe(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    s = text.strip()
    # Strip common wrappers
    if s.startswith("```"):
        s = s.strip("` ")
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def analyze_with_ai(data_bundle: dict[str, Any], user_message: str, history: list[dict[str, Any]] | None = None, lang: str | None = None) -> dict[str, Any]:
    """Call OpenAI (optional) and return {analysis, charts, followups}.

    This is an MVP. If OPENAI_API_KEY is not set, returns an error dict.
    Response will be in the language specified by `lang` parameter.
    """
    api_key = _env("OPENAI_API_KEY")
    if not api_key:
        lang_code = lang or DEFAULT_LANG
        return {"error": tr("Chave OpenAI ausente. Defina OPENAI_API_KEY no servidor.", lang_code)}

    model = _env("OPENAI_MODEL", "gpt-4o-mini")
    base_url = _env("OPENAI_BASE_URL", "https://api.openai.com/v1")
    lang_code = lang or DEFAULT_LANG

    # Build system prompt in the selected language
    sys_prompt = (
        f"{tr('You are a BI analyst', lang_code)}. {tr('You receive metadata and data sample', lang_code)}. "
        f"{tr('Respond with clear insights', lang_code)}. "
        f"{tr('Your output MUST be valid JSON', lang_code)}:\n"
        f"- {tr('analysis key', lang_code)}\n"
        f"- {tr('charts key', lang_code)}\n"
        f"- {tr('followups key', lang_code)}\n\n"
        f"Rules:\n"
        f"- {tr('Use only the provided sample', lang_code)}.\n"
        f"- {tr('For charts generate safe ECharts', lang_code)}.\n"
        f"- {tr('If insufficient data return empty', lang_code)}."
    )

    # Keep context light
    payload_context = {
        "question": data_bundle.get("question"),
        "params": data_bundle.get("params"),
        "result": data_bundle.get("result"),
        "profile": data_bundle.get("profile"),
    }

    messages: list[dict[str, Any]] = [{"role": "system", "content": sys_prompt}]

    # Light history (last 8)
    if history:
        for msg in history[-8:]:
            role = msg.get("role")
            content = msg.get("content")
            if role in ("user", "assistant") and isinstance(content, str) and content.strip():
                messages.append({"role": role, "content": content.strip()[:4000]})

    messages.append({
        "role": "user",
        "content": (
            "Contexto (JSON):\n" + json.dumps(payload_context, ensure_ascii=False) + "\n\n" +
            "Pergunta do usuário: " + user_message
        )
    })

    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    body = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        # Best effort: ask for JSON output
        "response_format": {"type": "json_object"},
    }

    try:
        r = requests.post(url, headers=headers, json=body, timeout=60)
        if r.status_code >= 400:
            # Retry without response_format for older models
            body.pop("response_format", None)
            r = requests.post(url, headers=headers, json=body, timeout=60)
        r.raise_for_status()
        data = r.json()
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content")
    except Exception as e:
        return {"error": f"Erro ao chamar IA: {e}"}

    parsed = _json_safe(content or "")
    if not parsed:
        # Return raw text as analysis
        return {"analysis": str(content or ""), "charts": [], "followups": []}

    analysis = parsed.get("analysis") or parsed.get("analysis_md") or ""
    charts = parsed.get("charts") or []
    followups = parsed.get("followups") or parsed.get("suggestions") or []

    # Defensive sanitization: charts must be list of dicts with option dict
    safe_charts: list[dict[str, Any]] = []
    if isinstance(charts, list):
        for ch in charts[:5]:
            if not isinstance(ch, dict):
                continue
            title = ch.get("title")
            opt = ch.get("echarts_option")
            if isinstance(title, str) and isinstance(opt, dict):
                safe_charts.append({"title": title[:120], "echarts_option": opt})

    safe_followups: list[str] = []
    if isinstance(followups, list):
        for s in followups[:8]:
            if isinstance(s, str) and s.strip():
                safe_followups.append(s.strip()[:200])

    return {"analysis": analysis, "charts": safe_charts, "followups": safe_followups}

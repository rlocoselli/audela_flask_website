from __future__ import annotations

import json
import os
from typing import Any

import requests


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
    """
    api_key = _env("OPENAI_API_KEY")
    if not api_key:
        return {"error": "Chave OpenAI ausente. Defina OPENAI_API_KEY no servidor."}

    model = _env("OPENAI_MODEL", "gpt-4o-mini")
    base_url = _env("OPENAI_BASE_URL", "https://api.openai.com/v1")

    sys_prompt = (
        "Você é um analista de BI. Você recebe metadados e uma amostra de dados (colunas/linhas) "
        "de uma pergunta SQL. Responda com insights claros, hipóteses, limitações, e sugira gráficos. "
        "Sua saída DEVE ser um JSON válido (sem markdown, sem blocos de código) com estas chaves:\n"
        "- analysis: string (markdown simples permitido, mas sem HTML)\n"
        "- charts: lista de objetos {title: string, echarts_option: object}\n"
        "- followups: lista de strings\n\n"
        "Regras:\n"
        "- Use apenas a amostra e o perfil fornecidos; se faltar algo, diga explicitamente.\n"
        "- Para charts, gere opções ECharts seguras, sem funções JS.\n"
        "- Se não houver dados suficientes, retorne charts=[] e explique no analysis."
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

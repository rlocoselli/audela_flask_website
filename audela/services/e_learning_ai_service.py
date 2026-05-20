"""AI-powered content service for the e-learning admin.

Provides three main capabilities:
  1. generate(prompt, field, lang)   – generate brand-new content
  2. improve(text, field, lang)      – fix grammar, style, clarity
  3. translate(text, target_langs)   – translate a text into a list of language codes

Falls back gracefully (returns the original text / an empty string) when
OPENAI_API_KEY is not set so the rest of the admin still works offline.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from flask import current_app
from .ai_runtime_config import resolve_ai_runtime_config

log = logging.getLogger(__name__)

# Supported platform languages (must match audela/i18n.py SUPPORTED_LANGS)
ALL_LANGS: list[str] = ["pt", "en", "fr", "es", "it", "de"]

LANG_NAMES: dict[str, str] = {
    "pt": "Portuguese (Brazil / Portugal)",
    "en": "English",
    "fr": "French",
    "es": "Spanish",
    "it": "Italian",
    "de": "German",
}


def _client():
    """Lazy-build an OpenAI client from app config.

    Returns None when API key or openai package is unavailable.
    """
    try:
        import openai  # noqa: PLC0415
    except ImportError:
        log.warning("openai package not installed — AI features disabled")
        return None

    runtime = resolve_ai_runtime_config(default_model="gpt-4o-mini")
    api_key: str = str(runtime.get("api_key") or "")
    if not api_key:
        log.info("%s not configured — AI features disabled", runtime.get("missing_key_env") or "OPENAI_API_KEY")
        return None

    kwargs: dict[str, Any] = {"api_key": api_key}
    base_url = str(runtime.get("base_url") or "")
    if base_url:
        kwargs["base_url"] = base_url.rstrip("/")

    return openai.OpenAI(**kwargs)


def _model() -> str:
    runtime = resolve_ai_runtime_config(default_model="gpt-4o-mini")
    m = str(runtime.get("model") or "")
    return m or "gpt-4o-mini"


def _chat(messages: list[dict], max_tokens: int = 2048) -> str | None:
    client = _client()
    if client is None:
        return None
    try:
        resp = client.chat.completions.create(
            model=_model(),
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.7,
        )
        return resp.choices[0].message.content.strip()
    except Exception as exc:  # noqa: BLE001
        log.error("OpenAI call failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def generate_content(
    prompt: str,
    field: str = "content",
    lang: str = "en",
    context: str = "",
) -> str:
    """Use AI to create course content from scratch.

    ``field`` hints the model on the expected format:
      - ``title``        → concise, one line
      - ``description``  → 2-4 sentences
      - ``content_html`` → rich HTML explanation, 300-600 words
      - ``instruction``  → exercise brief, step-by-step
      - ``hint``         → a single instructional hint
    """
    lang_name = LANG_NAMES.get(lang, lang)
    fmt_guide = _format_guide(field)

    system = (
        "You are an expert educational content writer for a professional BI / data analytics platform "
        "called AUDELA. You write concise, practical, authoritative course materials in the style of "
        "a top-tier online school (think Coursera, DataCamp). "
        "Always respond ONLY with the requested content — no preamble, no explanation."
    )
    user = (
        f"Write the following content in {lang_name}.\n"
        f"Field type: {field}\n"
        f"{fmt_guide}\n"
    )
    if context:
        user += f"\nContext / surrounding content:\n{context}\n"
    user += f"\nPrompt / topic:\n{prompt}"

    result = _chat([{"role": "system", "content": system}, {"role": "user", "content": user}])
    return result or ""


def improve_text(
    text: str,
    field: str = "content",
    lang: str = "en",
) -> str:
    """Fix grammar, style, and clarity of existing text.

    Returns the improved version in the same language.
    """
    if not text or not text.strip():
        return text

    lang_name = LANG_NAMES.get(lang, lang)
    system = (
        "You are a professional educational editor. "
        "Fix grammar, improve clarity, sharpen structure, and keep a professional tone. "
        "Preserve all HTML tags if present. "
        "Respond ONLY with the improved text — no preamble."
    )
    user = (
        f"Language: {lang_name}\n"
        f"Field: {field}\n\n"
        f"Original:\n{text}"
    )
    result = _chat([{"role": "system", "content": system}, {"role": "user", "content": user}])
    return result or text


def translate_content(
    text: str,
    source_lang: str = "en",
    target_langs: list[str] | None = None,
) -> dict[str, str]:
    """Translate ``text`` into all target languages.

    Returns a dict mapping each target lang code to the translated string.
    Missing / failed translations fall back to the original text.
    """
    if target_langs is None:
        target_langs = [lg for lg in ALL_LANGS if lg != source_lang]

    if not text or not text.strip():
        return {lg: text for lg in target_langs}

    targets_desc = ", ".join(f"{LANG_NAMES.get(lg, lg)} ({lg})" for lg in target_langs)
    system = (
        "You are a professional multilingual translator specialising in technical and educational content. "
        "Preserve all HTML tags. "
        "Respond ONLY with a valid JSON object mapping language codes to translations — no preamble."
    )
    user = (
        f"Translate the following text from {LANG_NAMES.get(source_lang, source_lang)} into: {targets_desc}.\n\n"
        f"Source text:\n{text}\n\n"
        f"Respond as JSON: {{\"pt\": \"...\", \"en\": \"...\", ...}}"
    )
    raw = _chat([{"role": "system", "content": system}, {"role": "user", "content": user}], max_tokens=3000)
    if not raw:
        return {lg: text for lg in target_langs}

    # Strip markdown code fences if present
    raw = raw.strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
        raw = raw.rstrip("`").strip()

    try:
        parsed: dict = json.loads(raw)
        return {lg: parsed.get(lg, text) for lg in target_langs}
    except json.JSONDecodeError:
        log.error("Failed to parse AI translation JSON: %s", raw[:200])
        return {lg: text for lg in target_langs}


def translate_i18n_dict(
    base_dict: dict,
    source_lang: str = "en",
) -> dict:
    """Take an existing multi-lang dict, translate the source_lang value into all missing langs."""
    source_text = base_dict.get(source_lang, "")
    if not source_text:
        # Try any lang that has content
        for lg in ALL_LANGS:
            if base_dict.get(lg):
                source_text = base_dict[lg]
                source_lang = lg
                break
    if not source_text:
        return base_dict

    missing = [lg for lg in ALL_LANGS if not base_dict.get(lg)]
    if not missing:
        return base_dict

    translations = translate_content(source_text, source_lang=source_lang, target_langs=missing)
    result = dict(base_dict)
    result.update(translations)
    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _format_guide(field: str) -> str:
    guides = {
        "title": "Write a concise, clear title (max 12 words). No period at the end.",
        "description": "Write 2-4 sentences. Professional tone. No bullet points.",
        "content_html": (
            "Write rich HTML (use <p>, <ul>, <li>, <code>, <strong> etc.). "
            "Aim for 400-700 words. Include concrete examples. "
            "Do NOT include <html>, <head>, or <body> tags."
        ),
        "instruction": (
            "Write a clear, step-by-step exercise brief. "
            "Start with context, then state the goal precisely, then list steps as a numbered <ol>. "
            "Use <p> and <ol>/<li>. Aim for 150-300 words."
        ),
        "hint": (
            "Write a single, helpful hint that guides without giving away the full answer. "
            "Max 2 sentences. Plain text (no HTML)."
        ),
    }
    return guides.get(field, "Write clear, professional educational content.")

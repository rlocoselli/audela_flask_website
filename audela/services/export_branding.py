from __future__ import annotations

from typing import Any


def resolve_brand_tokens(style_guide: str | None = "") -> dict[str, Any]:
    """Resolve cohesive export design tokens from free-text style guidance.

    Used by PDF, XLSX, PPTX and executive HTML so all generated artifacts
    share a consistent visual language.
    """
    text = str(style_guide or "").lower()

    # Default premium (investor-ish blue)
    tokens: dict[str, Any] = {
        "brand": "premium",
        "bg": "#f3f8ff",
        "card": "#ffffff",
        "ink": "#10223d",
        "muted": "#4f6485",
        "line": "#cfe0f5",
        "accent": "#0c63e7",
        "accent2": "#1a8ec8",
        "hero": "linear-gradient(120deg, #0c63e7, #1a8ec8)",
        "font_web": "'Avenir Next', 'Segoe UI', 'Helvetica Neue', Arial, sans-serif",
        "font_exec_web": "'Avenir Next', 'Segoe UI', 'Helvetica Neue', Arial, sans-serif",
        "font_ppt": "Calibri",
        "xlsx_template": "modern",
        "xlsx_color_theme": "blue",
    }

    if any(k in text for k in ["bank", "banking", "graphite", "board", "corporate"]):
        tokens.update(
            {
                "brand": "banking",
                "bg": "#f6f7f9",
                "card": "#ffffff",
                "ink": "#1d2430",
                "muted": "#5f6673",
                "line": "#d8dde6",
                "accent": "#3a4a63",
                "accent2": "#6a7485",
                "hero": "linear-gradient(120deg, #3a4a63, #6a7485)",
                "font_web": "'IBM Plex Sans', 'Segoe UI', Arial, sans-serif",
                "font_exec_web": "'IBM Plex Sans', 'Segoe UI', Arial, sans-serif",
                "font_ppt": "Arial",
                "xlsx_template": "executive",
                "xlsx_color_theme": "slate",
            }
        )
    elif any(k in text for k in ["operations", "forest", "green", "vert", "operational"]):
        tokens.update(
            {
                "brand": "operations",
                "bg": "#f2faf5",
                "card": "#ffffff",
                "ink": "#153525",
                "muted": "#4c6f5c",
                "line": "#d3e8dc",
                "accent": "#1f8f57",
                "accent2": "#4aa83a",
                "hero": "linear-gradient(120deg, #1f8f57, #4aa83a)",
                "font_web": "'Manrope', 'Segoe UI', Arial, sans-serif",
                "font_exec_web": "'Manrope', 'Segoe UI', Arial, sans-serif",
                "font_ppt": "Calibri",
                "xlsx_template": "modern",
                "xlsx_color_theme": "emerald",
            }
        )
    elif any(k in text for k in ["investor", "ocean", "blue", "editorial", "premium"]):
        tokens.update(
            {
                "brand": "investor",
                "bg": "#f3f8ff",
                "card": "#ffffff",
                "ink": "#10223d",
                "muted": "#4f6485",
                "line": "#cfe0f5",
                "accent": "#0c63e7",
                "accent2": "#1a8ec8",
                "hero": "linear-gradient(120deg, #0c63e7, #1a8ec8)",
                "font_web": "'Avenir Next', 'Segoe UI', 'Helvetica Neue', Arial, sans-serif",
                "font_exec_web": "'Avenir Next', 'Segoe UI', 'Helvetica Neue', Arial, sans-serif",
                "font_ppt": "Calibri",
                "xlsx_template": "modern",
                "xlsx_color_theme": "blue",
            }
        )

    if any(k in text for k in ["editorial", "magazine", "story"]):
        tokens["font_exec_web"] = "Georgia, 'Times New Roman', serif"

    if any(k in text for k in ["tech", "digital"]):
        tokens["font_web"] = "'Manrope', 'Segoe UI', Arial, sans-serif"
        tokens["font_exec_web"] = "'Manrope', 'Segoe UI', Arial, sans-serif"

    return tokens

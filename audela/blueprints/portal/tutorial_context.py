"""Tutorial context processor for Flask.

Injects tutorial configuration into Jinja2 templates automatically.
"""

from __future__ import annotations

from flask import g

from ...services.tutorial_service import TUTORIAL_CONFIG, get_product_menu_tutorials
from ...i18n import DEFAULT_LANG


def inject_tutorial_context() -> dict[str, any]:
    """Inject tutorial configuration into template context.
    
    Provides:
    - tutorial_config: Full tutorial configuration
    - get_product_tutorials: Function to get tutorials for a product
    - get_product_menu_tutorials: Function to get menu tutorials for a product
    """
    lang = getattr(g, "lang", DEFAULT_LANG)
    
    return {
        "tutorial_config": TUTORIAL_CONFIG,
        "get_product_menu_tutorials": get_product_menu_tutorials,
        "current_tutorial_lang": lang,
    }

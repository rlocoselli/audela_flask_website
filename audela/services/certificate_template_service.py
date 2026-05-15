"""Certificate template storage helpers for e-learning certificates."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

CERT_TEMPLATE_ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

DEFAULT_TEMPLATE_META: dict[str, Any] = {
    "template_name": "Default Certificate",
    "background_image": None,
    "updated_at": None,
    "updated_by": None,
}


def certificate_template_dir(app) -> str:
    base = os.path.join(app.instance_path, "certificate_templates")
    os.makedirs(base, exist_ok=True)
    return base


def certificate_template_meta_path(app) -> str:
    return os.path.join(certificate_template_dir(app), "template_meta.json")


def load_certificate_template_meta(app) -> dict[str, Any]:
    meta = dict(DEFAULT_TEMPLATE_META)
    path = certificate_template_meta_path(app)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            if isinstance(raw, dict):
                for key in DEFAULT_TEMPLATE_META:
                    if key in raw:
                        meta[key] = raw[key]
        except (OSError, json.JSONDecodeError, TypeError):
            pass

    bg = meta.get("background_image")
    if bg and not os.path.exists(os.path.join(certificate_template_dir(app), bg)):
        meta["background_image"] = None
    return meta


def save_certificate_template_meta(app, meta: dict[str, Any]) -> dict[str, Any]:
    merged = dict(DEFAULT_TEMPLATE_META)
    merged.update({k: v for k, v in meta.items() if k in DEFAULT_TEMPLATE_META})
    merged["updated_at"] = datetime.utcnow().isoformat()

    path = certificate_template_meta_path(app)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(merged, fh, ensure_ascii=True, indent=2)
    return merged


def is_allowed_certificate_template_file(filename: str) -> bool:
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in CERT_TEMPLATE_ALLOWED_EXTENSIONS


def get_background_image_path(app) -> str | None:
    meta = load_certificate_template_meta(app)
    bg = meta.get("background_image")
    if not bg:
        return None

    full_path = os.path.join(certificate_template_dir(app), bg)
    if not os.path.exists(full_path):
        return None
    return full_path

from __future__ import annotations

import base64
import hashlib
import json
import os
from typing import Any

from cryptography.fernet import Fernet, InvalidToken


def _derive_fernet_key(secret: str) -> bytes:
    """Derive a stable Fernet key from a secret string.

    Fernet expects a 32-byte urlsafe base64 key.
    """
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _get_fernet() -> Fernet:
    # Prefer a dedicated key; fallback to Flask SECRET_KEY.
    secret = os.environ.get("DATA_KEY") or os.environ.get("SECRET_KEY") or "dev-secret-change-me"
    return Fernet(_derive_fernet_key(secret))


def encrypt_json(payload: dict[str, Any]) -> bytes:
    f = _get_fernet()
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return f.encrypt(raw)


def decrypt_json(blob: bytes) -> dict[str, Any]:
    f = _get_fernet()
    try:
        raw = f.decrypt(blob)
    except InvalidToken as e:
        raise ValueError("Falha ao descriptografar config (chave incorreta?).") from e
    return json.loads(raw.decode("utf-8"))

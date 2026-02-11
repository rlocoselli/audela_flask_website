from __future__ import annotations

import base64
import hashlib
import json
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet

def _derive_key(secret: str) -> bytes:
    # Fernet needs 32 urlsafe base64-encoded bytes
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)

def get_fernet(app) -> Fernet:
    # Prefer explicit key, else derive from SECRET_KEY
    key = app.config.get("ETL_CATALOG_KEY")
    if key:
        # Allow providing already-base64 key
        try:
            return Fernet(key.encode("utf-8"))
        except Exception:
            return Fernet(_derive_key(key))
    secret = app.config.get("SECRET_KEY") or "dev-secret-key"
    return Fernet(_derive_key(secret))

def encrypt_json(app, data: Dict[str, Any]) -> str:
    f = get_fernet(app)
    token = f.encrypt(json.dumps(data, ensure_ascii=False).encode("utf-8"))
    return token.decode("utf-8")

def decrypt_json(app, token: str) -> Dict[str, Any]:
    f = get_fernet(app)
    raw = f.decrypt(token.encode("utf-8"))
    return json.loads(raw.decode("utf-8"))

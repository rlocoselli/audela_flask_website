from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from flask import current_app


class BridgeError(RuntimeError):
    pass


class BridgeClient:
    """Small Bridge API client for PSD2 aggregation.

    This implementation follows Bridge's v3 aggregation flow:
    - create user (optionally with external_user_id)
    - get user access token via /authorization/token
    - create connect session via /connect-sessions
    - list accounts & transactions
    """

    def __init__(self):
        cfg = current_app.config

        # Fallback: some deployments do not inject env vars into the process
        # (e.g., systemd service without EnvironmentFile). In that case, read
        # project .env directly so bank integration still works.
        env_file_values = self._read_project_env_file()

        def _pick(name: str, default: str = "") -> str:
            return (
                str(cfg.get(name) or "").strip()
                or str(os.environ.get(name) or "").strip()
                or str(env_file_values.get(name) or "").strip()
                or default
            )

        def _pick_with_source(name: str, default: str = "") -> Tuple[str, str]:
            for source_name, raw_val in (
                ("config", cfg.get(name)),
                ("env", os.environ.get(name)),
                ("dotenv", env_file_values.get(name)),
            ):
                val = str(raw_val or "").strip()
                if val:
                    return val, source_name
            return default, "default"

        self.base_url = (
            _pick("BRIDGE_BASE_URL", "https://api.bridgeapi.io")
        ).rstrip("/")

        bridge_client_id, bridge_client_id_source = _pick_with_source("BRIDGE_CLIENT_ID")
        bridge_client_secret, bridge_client_secret_source = _pick_with_source("BRIDGE_CLIENT_SECRET")
        powens_client_id, powens_client_id_source = _pick_with_source("POWENS_CLIENT_ID")
        powens_client_secret, powens_client_secret_source = _pick_with_source("POWENS_CLIENT_SECRET")

        # Compat: some deployments still expose Powens naming.
        # Prefer BRIDGE_* but fallback to POWENS_* when needed.
        self.client_id = bridge_client_id or powens_client_id
        self.client_secret = bridge_client_secret or powens_client_secret
        self.version = _pick("BRIDGE_VERSION", "2025-01-15")

        self._client_id_source = (
            f"BRIDGE_CLIENT_ID@{bridge_client_id_source}"
            if bridge_client_id
            else f"POWENS_CLIENT_ID@{powens_client_id_source}"
            if powens_client_id
            else "missing"
        )
        self._client_secret_source = (
            f"BRIDGE_CLIENT_SECRET@{bridge_client_secret_source}"
            if bridge_client_secret
            else f"POWENS_CLIENT_SECRET@{powens_client_secret_source}"
            if powens_client_secret
            else "missing"
        )
        self._config_diagnostics = {
            "BRIDGE_CLIENT_ID": self._source_diagnostics("BRIDGE_CLIENT_ID", cfg, env_file_values),
            "BRIDGE_CLIENT_SECRET": self._source_diagnostics("BRIDGE_CLIENT_SECRET", cfg, env_file_values),
            "POWENS_CLIENT_ID": self._source_diagnostics("POWENS_CLIENT_ID", cfg, env_file_values),
            "POWENS_CLIENT_SECRET": self._source_diagnostics("POWENS_CLIENT_SECRET", cfg, env_file_values),
            "selected": {
                "client_id": self._client_id_source,
                "client_secret": self._client_secret_source,
            },
        }

    def is_configured(self) -> bool:
        configured = bool(self.client_id and self.client_secret)
        if not configured:
            current_app.logger.warning(
                "BridgeClient is_configured=False missing=%s diagnostics=%s",
                ", ".join(self.missing_config_keys()) or "unknown",
                self._config_diagnostics,
            )
        return configured

    def missing_config_keys(self) -> List[str]:
        missing: List[str] = []
        if not self.client_id:
            missing.append("BRIDGE_CLIENT_ID (ou POWENS_CLIENT_ID)")
        if not self.client_secret:
            missing.append("BRIDGE_CLIENT_SECRET (ou POWENS_CLIENT_SECRET)")
        return missing

    def config_diagnostics(self) -> Dict[str, Any]:
        return dict(self._config_diagnostics)

    @staticmethod
    def _safe_value_state(raw_val: Any) -> str:
        if raw_val is None:
            return "missing"
        text = str(raw_val)
        if text == "":
            return "empty"
        trimmed = text.strip()
        if not trimmed:
            return "blank"
        return f"set(len={len(trimmed)})"

    @classmethod
    def _source_diagnostics(cls, key: str, cfg: Any, env_file_values: Dict[str, str]) -> Dict[str, str]:
        return {
            "config": cls._safe_value_state(cfg.get(key)),
            "env": cls._safe_value_state(os.environ.get(key)),
            "dotenv": cls._safe_value_state(env_file_values.get(key)),
        }

    @staticmethod
    def _read_project_env_file() -> Dict[str, str]:
        values: Dict[str, str] = {}
        try:
            project_root = Path(current_app.root_path).parent
            env_path = project_root / ".env"
            if not env_path.exists():
                return values

            for raw_line in env_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key:
                    values[key] = val
        except Exception:
            # Keep bridge lookup resilient even if .env parsing fails.
            return {}
        return values

    def _headers(self, bearer: Optional[str] = None) -> Dict[str, str]:
        h = {
            "Bridge-Version": self.version,
            "accept": "application/json",
            "content-type": "application/json",
            "Client-Id": self.client_id or "",
            "Client-Secret": self.client_secret or "",
        }
        if bearer:
            h["Authorization"] = f"Bearer {bearer}"
        return h

    def _raise_for(self, r: requests.Response) -> None:
        if r.ok:
            return
        try:
            payload = r.json()
        except Exception:
            payload = {"text": r.text}
        raise BridgeError(f"Bridge API error {r.status_code}: {payload}")

    @staticmethod
    def _extract_error_codes(payload: Any) -> List[str]:
        out: List[str] = []
        if isinstance(payload, dict):
            errors = payload.get("errors")
            if isinstance(errors, list):
                for e in errors:
                    if isinstance(e, dict):
                        c = str(e.get("code") or "").strip().lower()
                        if c:
                            out.append(c)
        return out

    @classmethod
    def _is_invalid_body_error(cls, r: requests.Response) -> bool:
        if r.status_code != 400:
            return False
        try:
            payload = r.json()
        except Exception:
            payload = {"text": r.text}

        codes = cls._extract_error_codes(payload)
        if any(c in {"invalid_request", "invalid_body", "bad_request"} for c in codes):
            text_blob = json.dumps(payload, ensure_ascii=False).lower()
            return "invalid body" in text_blob or "body content" in text_blob or "invalid_request" in text_blob
        return False

    @classmethod
    def _is_context_invalid_error(cls, r: requests.Response) -> bool:
        if r.status_code != 400:
            return False
        try:
            payload = r.json()
        except Exception:
            payload = {"text": r.text}

        codes = cls._extract_error_codes(payload)
        if "connect_session.context_invalid" in codes:
            return True

        text_blob = json.dumps(payload, ensure_ascii=False).lower()
        return "context_invalid" in text_blob and "context" in text_blob

    @staticmethod
    def _compact_body(body: Dict[str, Any]) -> Dict[str, Any]:
        compact: Dict[str, Any] = {}
        for k, v in body.items():
            if v is None:
                continue
            if isinstance(v, str):
                vv = v.strip()
                if vv == "":
                    continue
                compact[k] = vv
            else:
                compact[k] = v
        return compact

    def create_user(self, external_user_id: Optional[str] = None, email: Optional[str] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/v3/aggregation/users"
        candidate_bodies = [
            {"external_user_id": external_user_id, "email": email},
            {"external_user_id": external_user_id},
            {"externalUserId": external_user_id, "email": email},
            {"externalUserId": external_user_id},
            {"email": email},
            {},
        ]

        attempted_signatures: set[str] = set()
        for raw_body in candidate_bodies:
            body = self._compact_body(raw_body)
            signature = ",".join(sorted(body.keys())) or "<empty>"
            if signature in attempted_signatures:
                continue
            attempted_signatures.add(signature)

            r = requests.post(url, headers=self._headers(), data=json.dumps(body))
            # If user already exists, Bridge may respond with 409; in that case, we proceed.
            if r.status_code in (200, 201):
                return r.json()
            if r.status_code == 409:
                return {"status": "exists"}
            if self._is_invalid_body_error(r):
                current_app.logger.warning(
                    "Bridge create_user rejected payload shape=%s status=%s",
                    signature,
                    r.status_code,
                )
                continue
            self._raise_for(r)

        raise BridgeError("Bridge API error 400: invalid body content (create_user payload shapes exhausted)")
        return {}

    def get_user_token(self, *, user_uuid: Optional[str] = None, external_user_id: Optional[str] = None) -> Tuple[str, Optional[datetime]]:
        url = f"{self.base_url}/v3/aggregation/authorization/token"
        if not user_uuid and not external_user_id:
            raise BridgeError("Missing user_uuid or external_user_id")

        candidate_bodies = []
        if user_uuid:
            candidate_bodies.extend([
                {"user_uuid": user_uuid},
                {"userUuid": user_uuid},
            ])
        if external_user_id:
            candidate_bodies.extend([
                {"external_user_id": external_user_id},
                {"externalUserId": external_user_id},
            ])

        attempted_signatures: set[str] = set()
        data: Dict[str, Any] = {}
        for raw_body in candidate_bodies:
            body = self._compact_body(raw_body)
            signature = ",".join(sorted(body.keys())) or "<empty>"
            if signature in attempted_signatures:
                continue
            attempted_signatures.add(signature)

            r = requests.post(url, headers=self._headers(), data=json.dumps(body))
            if r.ok:
                data = r.json()
                break
            if self._is_invalid_body_error(r):
                current_app.logger.warning(
                    "Bridge get_user_token rejected payload shape=%s status=%s",
                    signature,
                    r.status_code,
                )
                continue
            self._raise_for(r)
        else:
            raise BridgeError("Bridge API error 400: invalid body content (get_user_token payload shapes exhausted)")

        token = data.get("access_token")
        exp = data.get("expires_at")
        exp_dt = None
        if exp:
            try:
                exp_dt = datetime.fromisoformat(exp.replace("Z", "+00:00"))
            except Exception:
                exp_dt = None
        return token, exp_dt

    def create_connect_session(self, *, bearer: str, user_email: str, callback_url: Optional[str] = None, context: Optional[str] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/v3/aggregation/connect-sessions"
        candidate_bodies = [
            {"user_email": user_email, "callback_url": callback_url, "context": context},
            {"user_email": user_email, "callback_url": callback_url},
            {"user_email": user_email, "redirect_url": callback_url, "context": context},
            {"user_email": user_email, "redirect_url": callback_url},
            {"email": user_email, "callback_url": callback_url},
            {"email": user_email, "redirect_url": callback_url},
            {"callback_url": callback_url, "context": context},
            {"callback_url": callback_url},
            {"redirect_url": callback_url, "state": context},
            {"redirect_url": callback_url},
            {},
        ]

        attempted_signatures: set[str] = set()
        for raw_body in candidate_bodies:
            body = self._compact_body(raw_body)
            signature = ",".join(sorted(body.keys())) or "<empty>"
            if signature in attempted_signatures:
                continue
            attempted_signatures.add(signature)

            r = requests.post(url, headers=self._headers(bearer=bearer), data=json.dumps(body))
            if r.ok:
                return r.json()
            if self._is_invalid_body_error(r):
                current_app.logger.warning(
                    "Bridge create_connect_session rejected payload shape=%s status=%s",
                    signature,
                    r.status_code,
                )
                continue
            if ("context" in body or "state" in body) and self._is_context_invalid_error(r):
                current_app.logger.warning(
                    "Bridge create_connect_session rejected context/state payload shape=%s status=%s; retrying without context/state",
                    signature,
                    r.status_code,
                )
                continue
            self._raise_for(r)

        raise BridgeError("Bridge API error 400: invalid body content (connect_session payload shapes exhausted)")

    def list_accounts(self, *, bearer: str, item_id: str) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/v3/aggregation/accounts"
        r = requests.get(url, headers=self._headers(bearer=bearer), params={"item_id": item_id, "limit": 500})
        self._raise_for(r)
        payload = r.json() or {}
        return payload.get("resources") or payload.get("data") or payload.get("accounts") or []

    def list_transactions(self, *, bearer: str, account_id: str, date_from: Optional[str] = None, date_to: Optional[str] = None) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/v3/aggregation/transactions"
        params: Dict[str, Any] = {"account_id": account_id, "limit": 500}
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        r = requests.get(url, headers=self._headers(bearer=bearer), params=params)
        self._raise_for(r)
        payload = r.json() or {}
        return payload.get("resources") or payload.get("data") or payload.get("transactions") or []

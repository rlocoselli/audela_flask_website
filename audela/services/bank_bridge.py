from __future__ import annotations

import json
from datetime import datetime
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
        self.base_url = cfg.get("BRIDGE_BASE_URL", "https://api.bridgeapi.io")
        self.client_id = cfg.get("BRIDGE_CLIENT_ID")
        self.client_secret = cfg.get("BRIDGE_CLIENT_SECRET")
        self.version = cfg.get("BRIDGE_VERSION", "2025-01-15")

    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

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

    def create_user(self, external_user_id: Optional[str] = None, email: Optional[str] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/v3/aggregation/users"
        body: Dict[str, Any] = {}
        if external_user_id:
            body["external_user_id"] = external_user_id
        if email:
            body["email"] = email
        r = requests.post(url, headers=self._headers(), data=json.dumps(body))
        # If user already exists, Bridge may respond with 409; in that case, we proceed.
        if r.status_code in (200, 201):
            return r.json()
        if r.status_code == 409:
            return {"status": "exists"}
        self._raise_for(r)
        return {}

    def get_user_token(self, *, user_uuid: Optional[str] = None, external_user_id: Optional[str] = None) -> Tuple[str, Optional[datetime]]:
        url = f"{self.base_url}/v3/aggregation/authorization/token"
        body: Dict[str, Any] = {}
        if user_uuid:
            body["user_uuid"] = user_uuid
        elif external_user_id:
            body["external_user_id"] = external_user_id
        else:
            raise BridgeError("Missing user_uuid or external_user_id")
        r = requests.post(url, headers=self._headers(), data=json.dumps(body))
        self._raise_for(r)
        data = r.json()
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
        body: Dict[str, Any] = {"user_email": user_email}
        if callback_url:
            body["callback_url"] = callback_url
        if context:
            body["context"] = context
        r = requests.post(url, headers=self._headers(bearer=bearer), data=json.dumps(body))
        self._raise_for(r)
        return r.json()

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

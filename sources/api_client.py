import requests

class ApiClient:

    @staticmethod
    def fetch(source):
        headers = source.headers or {}
        params = source.params or {}

        if source.auth_type == "bearer" and source.auth_token:
            headers["Authorization"] = f"Bearer {source.auth_token}"

        response = requests.request(
            method=source.method,
            url=source.base_url,
            headers=headers,
            params=params,
            timeout=30
        )

        response.raise_for_status()
        return response.json()
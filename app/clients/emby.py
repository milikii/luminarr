from __future__ import annotations

import httpx


class EmbyClient:
    def __init__(self, base_url: str, api_key: str, timeout_seconds: float = 10.0) -> None:
        cleaned_base = base_url.rstrip("/")
        if cleaned_base.endswith("/emby"):
            self._api_base = cleaned_base
        else:
            self._api_base = f"{cleaned_base}/emby"
        self._api_key = api_key.strip()
        self._timeout_seconds = timeout_seconds

    async def refresh_library(self) -> None:
        url = f"{self._api_base}/Library/Refresh"
        params = {"api_key": self._api_key}
        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            response = await client.post(url, params=params)
        response.raise_for_status()

from __future__ import annotations

import httpx


class JellyfinClient:
    def __init__(self, base_url: str, api_key: str, timeout_seconds: float = 10.0) -> None:
        self._api_base = base_url.rstrip("/")
        self._api_key = api_key.strip()
        self._timeout_seconds = timeout_seconds

    async def refresh_library(self) -> None:
        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            response = await client.post(
                f"{self._api_base}/Library/Refresh",
                headers={"X-Emby-Token": self._api_key},
            )
        response.raise_for_status()

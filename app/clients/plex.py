from __future__ import annotations

import httpx


class PlexClient:
    def __init__(self, base_url: str, token: str, timeout_seconds: float = 10.0) -> None:
        self._api_base = base_url.rstrip("/")
        self._token = token.strip()
        self._timeout_seconds = timeout_seconds

    async def refresh_library(self) -> None:
        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            response = await client.get(
                f"{self._api_base}/library/sections/all/refresh",
                params={"X-Plex-Token": self._token},
            )
        response.raise_for_status()

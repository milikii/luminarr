from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx


class ProwlarrClient:
    def __init__(self, base_url: str, api_key: str, timeout_seconds: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds

    async def search(self, query: str) -> list[Mapping[str, Any]]:
        cleaned_query = query.strip()
        if not cleaned_query:
            return []

        response = await self._get("/api/v1/search", params={"query": cleaned_query, "type": "search"})
        data = response.json()
        if not isinstance(data, list):
            return []
        return [item for item in data if isinstance(item, Mapping)]

    async def _get(self, path: str, params: Mapping[str, str]) -> httpx.Response:
        url = f"{self._base_url}{path}"
        headers = {"X-Api-Key": self._api_key}
        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            response = await client.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response

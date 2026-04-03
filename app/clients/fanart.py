from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True, slots=True)
class FanartMovieImages:
    poster_url: str
    backdrop_url: str


class FanartClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://webservice.fanart.tv/v3",
        timeout_seconds: float = 10.0,
    ) -> None:
        self._api_key = api_key.strip()
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    async def get_movie_images(self, tmdb_id: str) -> FanartMovieImages | None:
        cleaned_tmdb_id = tmdb_id.strip()
        if not cleaned_tmdb_id:
            return None

        response = await self._get(
            f"/movies/{cleaned_tmdb_id}",
            params={
                "api_key": self._api_key,
            },
        )
        data = response.json()
        if not isinstance(data, Mapping):
            return None

        poster_url = _pick_image_url(data, "movieposter", "hdmovieclearart", "moviethumb")
        backdrop_url = _pick_image_url(data, "moviebackground", "moviethumb")
        if not poster_url and not backdrop_url:
            return None
        return FanartMovieImages(poster_url=poster_url, backdrop_url=backdrop_url)

    async def _get(self, path: str, params: Mapping[str, str]) -> httpx.Response:
        url = f"{self._base_url}{path}"
        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            response = await client.get(url, params=params)
        response.raise_for_status()
        return response


def _pick_image_url(payload: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        raw_items = payload.get(key)
        if not isinstance(raw_items, list):
            continue
        for raw_item in raw_items:
            if not isinstance(raw_item, Mapping):
                continue
            raw_url = raw_item.get("url")
            if raw_url is None:
                continue
            cleaned = str(raw_url).strip()
            if cleaned:
                return cleaned
    return ""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True, slots=True)
class TmdbMovie:
    title: str
    original_title: str
    year: str
    tmdb_id: str = ""


class TmdbClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.themoviedb.org",
        timeout_seconds: float = 10.0,
    ) -> None:
        self._api_key = api_key.strip()
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    async def search_movie(self, title: str, year: str = "") -> TmdbMovie | None:
        cleaned_title = title.strip()
        if not cleaned_title:
            return None

        params: dict[str, str] = {
            "api_key": self._api_key,
            "query": cleaned_title,
            "include_adult": "false",
        }
        cleaned_year = year.strip()
        if cleaned_year:
            params["year"] = cleaned_year

        response = await self._get("/3/search/movie", params=params)
        data = response.json()
        if not isinstance(data, Mapping):
            return None

        raw_results = data.get("results")
        if not isinstance(raw_results, list):
            return None

        for item in raw_results:
            if not isinstance(item, Mapping):
                continue
            movie = _to_tmdb_movie(item)
            if movie is not None:
                return movie
        return None

    async def _get(self, path: str, params: Mapping[str, str]) -> httpx.Response:
        url = f"{self._base_url}{path}"
        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            response = await client.get(url, params=params)
        response.raise_for_status()
        return response


def _to_tmdb_movie(item: Mapping[str, Any]) -> TmdbMovie | None:
    movie_id = _safe_id(item.get("id"))
    title = _safe_text(item.get("title"))
    original_title = _safe_text(item.get("original_title"))
    resolved_title = title or original_title
    if not resolved_title:
        return None

    release_date = _safe_text(item.get("release_date"))
    year = _extract_year(release_date)
    return TmdbMovie(tmdb_id=movie_id, title=resolved_title, original_title=original_title, year=year)


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    return text


def _safe_id(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    return text


def _extract_year(value: str) -> str:
    matched = re.match(r"^(?:19|20)\d{2}", value)
    if matched is None:
        return ""
    return matched.group(0)

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import httpx

from app.search_title_normalization import normalize_match_key, score_title_match


@dataclass(frozen=True, slots=True)
class TmdbMovie:
    title: str
    original_title: str
    year: str
    tmdb_id: str = ""
    media_type: str = "movie"


class TmdbClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.themoviedb.org",
        timeout_seconds: float = 10.0,
        proxy_url: str = "",
    ) -> None:
        self._api_key = api_key.strip()
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._proxy_url = proxy_url.strip()

    async def search_movie(self, title: str, year: str = "") -> TmdbMovie | None:
        results = await self.search_movie_candidates(title, year=year, limit=5)
        if not results:
            return None
        return _pick_best_tmdb_match(results, title=title, year=year)

    async def search_movie_candidates(
        self,
        title: str,
        year: str = "",
        *,
        limit: int = 3,
    ) -> list[TmdbMovie]:
        return await self._search_candidates(
            path="/3/search/movie",
            title=title,
            year=year,
            year_param_name="year",
            result_builder=_to_tmdb_movie,
            limit=limit,
        )

    async def get_movie_by_id(self, tmdb_id: str) -> TmdbMovie | None:
        cleaned_tmdb_id = tmdb_id.strip()
        if not cleaned_tmdb_id:
            return None
        response = await self._get(
            f"/3/movie/{cleaned_tmdb_id}",
            params={"api_key": self._api_key},
        )
        data = response.json()
        if not isinstance(data, Mapping):
            return None
        return _to_tmdb_movie(data)

    async def search_tv(self, title: str, year: str = "") -> TmdbMovie | None:
        results = await self.search_tv_candidates(title, year=year, limit=5)
        if not results:
            return None
        return _pick_best_tmdb_match(results, title=title, year=year)

    async def search_tv_candidates(
        self,
        title: str,
        year: str = "",
        *,
        limit: int = 3,
    ) -> list[TmdbMovie]:
        return await self._search_candidates(
            path="/3/search/tv",
            title=title,
            year=year,
            year_param_name="first_air_date_year",
            result_builder=_to_tmdb_tv,
            limit=limit,
        )

    async def _search_candidates(
        self,
        *,
        path: str,
        title: str,
        year: str,
        year_param_name: str,
        result_builder: Callable[[Mapping[str, Any]], TmdbMovie | None],
        limit: int,
    ) -> list[TmdbMovie]:
        cleaned_title = title.strip()
        if not cleaned_title:
            return []

        params: dict[str, str] = {
            "api_key": self._api_key,
            "query": cleaned_title,
            "include_adult": "false",
        }
        cleaned_year = year.strip()
        if cleaned_year:
            params[year_param_name] = cleaned_year

        response = await self._get(path, params=params)
        data = response.json()
        if not isinstance(data, Mapping):
            return []

        raw_results = data.get("results")
        if not isinstance(raw_results, list):
            return []

        resolved_results: list[TmdbMovie] = []
        seen_ids: set[str] = set()
        for item in raw_results:
            if not isinstance(item, Mapping):
                continue
            media = result_builder(item)
            if media is None:
                continue
            media_id = media.tmdb_id
            if media_id and media_id in seen_ids:
                continue
            if media_id:
                seen_ids.add(media_id)
            resolved_results.append(media)
            if len(resolved_results) >= max(1, limit):
                break
        return resolved_results

    async def _get(self, path: str, params: Mapping[str, str]) -> httpx.Response:
        url = f"{self._base_url}{path}"
        async with httpx.AsyncClient(timeout=self._timeout_seconds, proxy=self._proxy_url or None) as client:
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
    return TmdbMovie(
        tmdb_id=movie_id,
        title=resolved_title,
        original_title=original_title,
        year=year,
        media_type="movie",
    )


def _to_tmdb_tv(item: Mapping[str, Any]) -> TmdbMovie | None:
    series_id = _safe_id(item.get("id"))
    title = _safe_text(item.get("name"))
    original_title = _safe_text(item.get("original_name"))
    resolved_title = title or original_title
    if not resolved_title:
        return None

    first_air_date = _safe_text(item.get("first_air_date"))
    year = _extract_year(first_air_date)
    return TmdbMovie(
        tmdb_id=series_id,
        title=resolved_title,
        original_title=original_title,
        year=year,
        media_type="tv",
    )


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


def _pick_best_tmdb_match(
    candidates: list[TmdbMovie],
    *,
    title: str,
    year: str,
) -> TmdbMovie:
    cleaned_title = normalize_match_key(title)
    cleaned_year = year.strip()
    best_candidate = candidates[0]
    best_score = _score_tmdb_match(best_candidate, title=cleaned_title, year=cleaned_year)
    for candidate in candidates[1:]:
        score = _score_tmdb_match(candidate, title=cleaned_title, year=cleaned_year)
        if score > best_score:
            best_candidate = candidate
            best_score = score
    return best_candidate


def _score_tmdb_match(candidate: TmdbMovie, *, title: str, year: str) -> tuple[int, int, int]:
    normalized_title = normalize_match_key(candidate.title)
    normalized_original_title = normalize_match_key(candidate.original_title)
    title_score = max(
        score_title_match(title, normalized_title),
        score_title_match(title, normalized_original_title),
    )
    year_score = 1 if year and candidate.year == year else 0
    exact_year_penalty = 0 if year_score or not year else -1
    return title_score, year_score, exact_year_penalty

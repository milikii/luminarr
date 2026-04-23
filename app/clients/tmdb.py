from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import httpx


_SEQUEL_ALIAS_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bpart\s+one\b", re.IGNORECASE), "1"),
    (re.compile(r"\bpart\s+two\b", re.IGNORECASE), "2"),
    (re.compile(r"\bpart\s+three\b", re.IGNORECASE), "3"),
    (re.compile(r"\bpart\s+four\b", re.IGNORECASE), "4"),
    (re.compile(r"\bpart\s+five\b", re.IGNORECASE), "5"),
    (re.compile(r"\bpart\s+six\b", re.IGNORECASE), "6"),
    (re.compile(r"\bpart\s+seven\b", re.IGNORECASE), "7"),
    (re.compile(r"\bpart\s+eight\b", re.IGNORECASE), "8"),
    (re.compile(r"\bpart\s+nine\b", re.IGNORECASE), "9"),
    (re.compile(r"\bpart\s+ten\b", re.IGNORECASE), "10"),
    (re.compile(r"\bviii\b", re.IGNORECASE), "8"),
    (re.compile(r"\bvii\b", re.IGNORECASE), "7"),
    (re.compile(r"\bvi\b", re.IGNORECASE), "6"),
    (re.compile(r"\biv\b", re.IGNORECASE), "4"),
    (re.compile(r"\biii\b", re.IGNORECASE), "3"),
    (re.compile(r"\bii\b", re.IGNORECASE), "2"),
    (re.compile(r"\bix\b", re.IGNORECASE), "9"),
    (re.compile(r"\bx\b", re.IGNORECASE), "10"),
)
_CHINESE_PART_PATTERN = re.compile(r"第\s*(?P<value>[一二三四五六七八九十两\d]+)\s*部", re.IGNORECASE)
_CHINESE_NUMERAL_MAP = {
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


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
    cleaned_title = _normalize_match_key(title)
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
    normalized_title = _normalize_match_key(candidate.title)
    normalized_original_title = _normalize_match_key(candidate.original_title)
    title_score = max(
        _score_title_variant(title, normalized_title),
        _score_title_variant(title, normalized_original_title),
    )
    year_score = 1 if year and candidate.year == year else 0
    exact_year_penalty = 0 if year_score or not year else -1
    return title_score, year_score, exact_year_penalty


def _score_title_variant(query: str, candidate_title: str) -> int:
    if not query or not candidate_title:
        return 0
    if candidate_title == query:
        return 4
    if candidate_title.startswith(query):
        return 3
    if query in candidate_title:
        return 2
    return 1 if candidate_title.replace(" ", "") == query.replace(" ", "") else 0


def _normalize_match_key(value: str) -> str:
    cleaned = unicodedata.normalize("NFKC", value).strip().lower()
    if not cleaned:
        return ""
    cleaned = re.sub(r"[._:：\-]+", " ", cleaned)
    cleaned = _normalize_sequel_aliases(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _normalize_sequel_aliases(value: str) -> str:
    normalized = value
    normalized = _CHINESE_PART_PATTERN.sub(lambda match: str(_parse_chinese_part_number(match.group("value"))), normalized)
    for pattern, replacement in _SEQUEL_ALIAS_PATTERNS:
        normalized = pattern.sub(replacement, normalized)
    return normalized


def _parse_chinese_part_number(value: str) -> int:
    cleaned = value.strip()
    if not cleaned:
        return 0
    if cleaned.isdigit():
        return int(cleaned)
    if cleaned == "十":
        return 10
    if cleaned.startswith("十") and len(cleaned) == 2:
        return 10 + _CHINESE_NUMERAL_MAP.get(cleaned[1], 0)
    if cleaned.endswith("十") and len(cleaned) == 2:
        return _CHINESE_NUMERAL_MAP.get(cleaned[0], 0) * 10
    if "十" in cleaned and len(cleaned) == 3:
        tens, _, ones = cleaned.partition("十")
        return _CHINESE_NUMERAL_MAP.get(tens, 0) * 10 + _CHINESE_NUMERAL_MAP.get(ones, 0)
    return _CHINESE_NUMERAL_MAP.get(cleaned, 0)

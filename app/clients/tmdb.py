from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import httpx

from app.search_franchise_intent import (
    PRIMARY_FRANCHISE_INTENT_BOOST,
    has_explicit_franchise_intent,
    resolve_franchise_intent_boost,
)
from app.search_title_normalization import (
    ShortQueryCandidateProfile,
    is_short_cjk_title_query,
    is_title_match_prefix_family,
    normalize_match_key,
    resolve_short_query_contains_slots,
    resolve_title_match_relation,
    score_title_match,
    should_preserve_short_query_candidate_spread,
    title_match_relation_priority,
    SHORT_STRONG_TITLE_COMPACT_LIMIT,
)

SHORT_GENERIC_QUERY_SAMPLE_LIMIT = 10


@dataclass(frozen=True, slots=True)
class TmdbMovie:
    title: str
    original_title: str
    year: str
    tmdb_id: str = ""
    media_type: str = "movie"
    poster_path: str = ""
    overview: str = ""
    popularity: float = 0.0
    vote_count: int = 0


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
            params={
                "api_key": self._api_key,
                "language": "zh-CN",
            },
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

    async def search_media_candidates(
        self,
        title: str,
        year: str = "",
        *,
        limit: int = 5,
    ) -> list[TmdbMovie]:
        sample_limit = _resolve_tmdb_sampling_limit(title=title, year=year, limit=limit)
        movie_candidates = await self.search_movie_candidates(title, year=year, limit=sample_limit)
        tv_candidates = await self.search_tv_candidates(title, year=year, limit=sample_limit)
        return _rank_tmdb_candidates(
            [*movie_candidates, *tv_candidates],
            title=title,
            year=year,
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
            "language": "zh-CN",
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
        poster_path=_safe_text(item.get("poster_path")),
        overview=_safe_text(item.get("overview")),
        popularity=_safe_float(item.get("popularity")),
        vote_count=_safe_int(item.get("vote_count")),
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
        poster_path=_safe_text(item.get("poster_path")),
        overview=_safe_text(item.get("overview")),
        popularity=_safe_float(item.get("popularity")),
        vote_count=_safe_int(item.get("vote_count")),
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


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


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


def _rank_tmdb_candidates(
    candidates: list[TmdbMovie],
    *,
    title: str,
    year: str,
    limit: int,
) -> list[TmdbMovie]:
    cleaned_title = normalize_match_key(title)
    cleaned_year = year.strip()
    seen_keys: set[tuple[str, str]] = set()
    ranked_candidates: list[TmdbMovie] = []
    scored_candidates = [
        (_score_tmdb_match(candidate, title=cleaned_title, year=cleaned_year), candidate)
        for candidate in candidates
    ]
    scored_candidates.sort(key=lambda item: item[0], reverse=True)
    if has_explicit_franchise_intent(title):
        scored_candidates = _prefer_primary_franchise_cluster(scored_candidates, title=title)
    preserve_short_query_spread = _should_preserve_short_query_candidate_spread(
        title=title,
        year=cleaned_year,
        scored_candidates=scored_candidates,
    )
    if preserve_short_query_spread:
        scored_candidates = _diversify_short_query_scored_candidates(
            title=title,
            limit=limit,
            scored_candidates=scored_candidates,
        )
    elif scored_candidates and _should_compact_short_strong_title_candidates(
        title=title,
        year=cleaned_year,
        best_score=scored_candidates[0][0],
    ):
        scored_candidates = _compact_short_strong_title_candidates(
            title=title,
            limit=limit,
            scored_candidates=scored_candidates,
        )
    elif scored_candidates:
        best_score = scored_candidates[0][0]
        if best_score[0] >= 3 and best_score[1] > 0:
            exact_compact_title = _compact_tmdb_match_key(cleaned_title)
            exact_family: list[tuple[tuple[int, int, int], TmdbMovie]] = []
            for score, candidate in scored_candidates:
                normalized_title = _compact_tmdb_match_key(normalize_match_key(candidate.title))
                normalized_original_title = _compact_tmdb_match_key(normalize_match_key(candidate.original_title))
                if normalized_title == exact_compact_title or normalized_original_title == exact_compact_title:
                    exact_family.append((score, candidate))
            if exact_family:
                scored_candidates = exact_family
            else:
                scored_candidates = [
                    item for item in scored_candidates if item[0][0] >= best_score[0]
                ]
    for _, candidate in scored_candidates:
        dedupe_key = (candidate.media_type, candidate.tmdb_id or f"{candidate.title}|{candidate.year}")
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        ranked_candidates.append(candidate)
        if len(ranked_candidates) >= max(1, limit):
            break
    return ranked_candidates


def _prefer_primary_franchise_cluster(
    scored_candidates: list[tuple[tuple[int, int, int], TmdbMovie]],
    *,
    title: str,
) -> list[tuple[tuple[int, int, int], TmdbMovie]]:
    primary_candidates = [
        item
        for item in scored_candidates
        if resolve_franchise_intent_boost(title, item[1].title, item[1].original_title) >= PRIMARY_FRANCHISE_INTENT_BOOST
    ]
    if primary_candidates:
        return primary_candidates
    return scored_candidates


def _should_preserve_short_query_candidate_spread(
    *,
    title: str,
    year: str,
    scored_candidates: list[tuple[tuple[int, int, int], TmdbMovie]],
) -> bool:
    if not scored_candidates:
        return False
    competitor_profiles: list[ShortQueryCandidateProfile] = []
    for _, candidate in scored_candidates[1:]:
        relation = _resolve_tmdb_candidate_match_relation(title=title, candidate=candidate)
        competitor_profiles.append(
            ShortQueryCandidateProfile(
                dedupe_key=f"{candidate.media_type}:{candidate.tmdb_id or f'{candidate.title}|{candidate.year}'}",
                relation=relation,
                popularity=candidate.popularity,
                vote_count=candidate.vote_count,
            )
        )
    return should_preserve_short_query_candidate_spread(
        title=title,
        year=year,
        top_exact_bias=scored_candidates[0][0][1],
        competitor_profiles=competitor_profiles,
    )


def _should_compact_short_strong_title_candidates(
    *,
    title: str,
    year: str,
    best_score: tuple[int, int, int],
) -> bool:
    return (
        not year.strip()
        and is_short_cjk_title_query(title)
        and best_score[0] >= 3
        and best_score[1] > 0
    )


def _compact_short_strong_title_candidates(
    *,
    title: str,
    limit: int,
    scored_candidates: list[tuple[tuple[int, int, int], TmdbMovie]],
) -> list[tuple[tuple[int, int, int], TmdbMovie]]:
    top_item = scored_candidates[0]
    family_items: list[tuple[tuple[int, int, int], TmdbMovie]] = []
    for item in scored_candidates[1:]:
        relation = _resolve_tmdb_candidate_match_relation(title=title, candidate=item[1])
        if is_title_match_prefix_family(relation):
            family_items.append(item)
    family_items.sort(key=_short_query_prefix_sort_key, reverse=True)
    compact_limit = max(1, min(limit, SHORT_STRONG_TITLE_COMPACT_LIMIT))
    return [top_item, *family_items[: max(0, compact_limit - 1)]]


def _diversify_short_query_scored_candidates(
    *,
    title: str,
    limit: int,
    scored_candidates: list[tuple[tuple[int, int, int], TmdbMovie]],
) -> list[tuple[tuple[int, int, int], TmdbMovie]]:
    if len(scored_candidates) <= 1:
        return scored_candidates

    top_item = scored_candidates[0]
    prefix_items: list[tuple[tuple[int, int, int], TmdbMovie]] = []
    contains_items: list[tuple[tuple[int, int, int], TmdbMovie]] = []
    fallback_items: list[tuple[tuple[int, int, int], TmdbMovie]] = []
    for item in scored_candidates[1:]:
        relation = _resolve_tmdb_candidate_match_relation(title=title, candidate=item[1])
        if relation == "contains":
            contains_items.append(item)
        elif is_title_match_prefix_family(relation):
            prefix_items.append(item)
        else:
            fallback_items.append(item)

    prefix_items.sort(key=_short_query_prefix_sort_key, reverse=True)
    contains_items.sort(key=_short_query_contains_sort_key, reverse=True)
    top_relation = _resolve_tmdb_candidate_match_relation(title=title, candidate=top_item[1])
    family_candidate_count = len(prefix_items) + (1 if is_title_match_prefix_family(top_relation) else 0)
    contains_slots = resolve_short_query_contains_slots(
        limit=limit,
        family_candidate_count=family_candidate_count,
        contains_count=len(contains_items),
    )
    selected: list[tuple[tuple[int, int, int], TmdbMovie]] = [top_item]
    selected.extend(prefix_items[: max(0, limit - 1 - contains_slots)])
    selected.extend(contains_items[:contains_slots])

    seen_keys = {
        (item[1].media_type, item[1].tmdb_id or f"{item[1].title}|{item[1].year}")
        for item in selected
    }
    for item in [*prefix_items, *contains_items, *fallback_items]:
        dedupe_key = (item[1].media_type, item[1].tmdb_id or f"{item[1].title}|{item[1].year}")
        if dedupe_key in seen_keys:
            continue
        selected.append(item)
        seen_keys.add(dedupe_key)
        if len(selected) >= max(1, limit):
            break
    return selected

def _short_query_contains_sort_key(item: tuple[tuple[int, int, int], TmdbMovie]) -> tuple[int, float, int, int, int]:
    score, candidate = item
    return (
        score[0],
        candidate.popularity,
        candidate.vote_count,
        1 if candidate.poster_path else 0,
        1 if candidate.overview else 0,
    )


def _short_query_prefix_sort_key(item: tuple[tuple[int, int, int], TmdbMovie]) -> tuple[int, int, float, int, int, int]:
    score, candidate = item
    return (
        score[0],
        score[1],
        candidate.popularity,
        candidate.vote_count,
        1 if candidate.poster_path else 0,
        1 if candidate.overview else 0,
    )


def _resolve_tmdb_candidate_match_relation(*, title: str, candidate: TmdbMovie) -> str:
    localized_relation = resolve_title_match_relation(title, candidate.title)
    original_relation = resolve_title_match_relation(title, candidate.original_title)
    if title_match_relation_priority(original_relation) > title_match_relation_priority(localized_relation):
        return original_relation
    return localized_relation


def _resolve_tmdb_sampling_limit(*, title: str, year: str, limit: int) -> int:
    if year.strip() or not is_short_cjk_title_query(title):
        return max(1, limit)
    return max(limit, SHORT_GENERIC_QUERY_SAMPLE_LIMIT)


def _score_tmdb_match(candidate: TmdbMovie, *, title: str, year: str) -> tuple[int, int, int]:
    normalized_title = normalize_match_key(candidate.title)
    normalized_original_title = normalize_match_key(candidate.original_title)
    compact_query = _compact_tmdb_match_key(title)
    compact_title = _compact_tmdb_match_key(normalized_title)
    compact_original_title = _compact_tmdb_match_key(normalized_original_title)
    franchise_intent_boost = resolve_franchise_intent_boost(title, candidate.title, candidate.original_title)
    title_score = max(
        score_title_match(title, normalized_title),
        score_title_match(title, normalized_original_title),
    )
    exact_bias = 0
    if compact_query and (compact_title == compact_query or compact_original_title == compact_query):
        exact_bias = 2
    elif normalized_title == title or normalized_original_title == title:
        exact_bias = 1
    year_score = 1 if year and candidate.year == year else 0
    exact_year_penalty = 0 if year_score or not year else -1
    return title_score + franchise_intent_boost * 10, exact_bias, year_score + exact_year_penalty


def _compact_tmdb_match_key(value: str) -> str:
    return re.sub(r"[\W_]+", "", value, flags=re.UNICODE).lower()

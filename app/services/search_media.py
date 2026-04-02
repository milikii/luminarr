from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.clients.tmdb import TmdbMovie
from app.db.candidate_repo import CandidateMappingRepo

SearchFunc = Callable[[str], Awaitable[Sequence[Mapping[str, Any]]]]
LookupMovieFunc = Callable[[str, str], Awaitable[TmdbMovie | None]]

EMPTY_QUERY_TEXT = "请输入要搜索的内容。"
NO_RESULT_TEXT_TEMPLATE = "未找到候选结果：{query}"


@dataclass(frozen=True, slots=True)
class Candidate:
    title: str
    year: str
    quality: str
    size: str
    indexer: str


@dataclass(frozen=True, slots=True)
class ParsedMovieQuery:
    title: str
    year: str


class SearchMediaService:
    def __init__(
        self,
        search_func: SearchFunc,
        limit: int = 5,
        candidate_repo: CandidateMappingRepo | None = None,
        lookup_movie_func: LookupMovieFunc | None = None,
    ) -> None:
        self._search_func = search_func
        self._limit = max(1, limit)
        self._candidate_repo = candidate_repo
        self._lookup_movie_func = lookup_movie_func
        self._recent_candidates_by_chat: dict[int, list[dict[str, Any]]] = {}

    async def search_and_format(self, query: str, chat_id: int | None = None) -> str:
        cleaned_query = query.strip()
        if not cleaned_query:
            return EMPTY_QUERY_TEXT

        parsed_query = parse_movie_query(cleaned_query)
        fallback_query = _build_query(parsed_query.title, parsed_query.year)
        raw_results: Sequence[Mapping[str, Any]] = ()

        if self._lookup_movie_func is not None:
            try:
                tmdb_movie = await self._lookup_movie_func(parsed_query.title, parsed_query.year)
            except Exception:
                tmdb_movie = None
            if tmdb_movie is not None:
                resolved_year = tmdb_movie.year or parsed_query.year
                ordered_queries = _unique_queries(
                    [
                        _build_query(tmdb_movie.title, resolved_year),
                        _build_query(tmdb_movie.original_title, resolved_year),
                    ]
                )
                raw_results = await _search_first_non_empty(self._search_func, ordered_queries)
            else:
                raw_results = await self._search_func(fallback_query)
        else:
            raw_results = await self._search_func(fallback_query)

        selected_raw_results = [_to_candidate_dict(item) for item in raw_results[: self._limit]]
        if chat_id is not None:
            self._recent_candidates_by_chat[chat_id] = selected_raw_results
            if self._candidate_repo is not None:
                try:
                    self._candidate_repo.save_candidates(chat_id, selected_raw_results)
                except Exception:
                    pass

        candidates = [normalize_candidate(item) for item in selected_raw_results]
        return format_candidates(cleaned_query, candidates)

    def get_cached_candidate(self, chat_id: int, index: int) -> Mapping[str, Any] | None:
        if index < 1:
            return None
        candidates = self._recent_candidates_by_chat.get(chat_id)
        resolved_index = index - 1
        if candidates and resolved_index < len(candidates):
            return candidates[resolved_index]

        if self._candidate_repo is None:
            return None
        try:
            persisted_candidate = self._candidate_repo.get_candidate(chat_id, index)
        except Exception:
            return None
        if persisted_candidate is None:
            return None
        return persisted_candidate


def parse_movie_query(query: str) -> ParsedMovieQuery:
    cleaned_query = _normalize_spaces(query)
    if not cleaned_query:
        return ParsedMovieQuery(title="", year="")

    matched_parentheses = re.match(
        r"^(?P<title>.+?)\s*[\(（](?P<year>(?:19|20)\d{2})[\)）]\s*$",
        cleaned_query,
    )
    if matched_parentheses is not None:
        title = _normalize_spaces(matched_parentheses.group("title"))
        year = matched_parentheses.group("year")
        if title:
            return ParsedMovieQuery(title=title, year=year)

    matched_suffix = re.match(r"^(?P<title>.+?)\s+(?P<year>(?:19|20)\d{2})\s*$", cleaned_query)
    if matched_suffix is not None:
        title = _normalize_spaces(matched_suffix.group("title"))
        year = matched_suffix.group("year")
        if title:
            return ParsedMovieQuery(title=title, year=year)

    return ParsedMovieQuery(title=cleaned_query, year="")


def normalize_candidate(item: Mapping[str, Any]) -> Candidate:
    title = _safe_text(item.get("title"), default="(no title)")
    year = _safe_year(item.get("year"))
    quality = _safe_text(item.get("quality"), default="-")
    if quality == "-" and "resolution" in item:
        quality = _safe_text(item.get("resolution"), default="-")
    if quality == "-":
        quality = _guess_quality_from_title(title)
    size = _format_size(item.get("size"))
    indexer = _safe_indexer(item.get("indexer"), item.get("indexerName"))
    return Candidate(title=title, year=year, quality=quality, size=size, indexer=indexer)


def format_candidates(query: str, candidates: Sequence[Candidate]) -> str:
    if not candidates:
        return NO_RESULT_TEXT_TEMPLATE.format(query=query)

    lines = [f"搜索结果：{query}"]
    for i, item in enumerate(candidates, start=1):
        lines.append(f"{i}. {item.title} ({item.year})")
        lines.append(f"   画质: {item.quality} | 大小: {item.size} | 站点: {item.indexer}")
    return "\n".join(lines)


def _safe_text(value: Any, default: str) -> str:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    return text


def _safe_year(value: Any) -> str:
    if value is None:
        return "-"
    text = str(value).strip()
    if not text:
        return "-"
    return text


def _safe_indexer(indexer_value: Any, indexer_name_value: Any) -> str:
    if isinstance(indexer_value, Mapping):
        mapped_name = _safe_text(indexer_value.get("name"), default="-")
        if mapped_name != "-":
            return mapped_name

    name = _safe_text(indexer_name_value, default="-")
    if name != "-":
        return name
    return _safe_text(indexer_value, default="-")


def _format_size(size_value: Any) -> str:
    if size_value is None:
        return "-"

    try:
        bytes_value = int(size_value)
    except (TypeError, ValueError):
        return "-"

    if bytes_value <= 0:
        return "-"

    units = ("B", "KB", "MB", "GB", "TB")
    size = float(bytes_value)
    unit_index = 0
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    return f"{size:.1f} {units[unit_index]}"


def _guess_quality_from_title(title: str) -> str:
    resolution_match = re.search(r"\b(2160p|1080p|720p|480p|4k)\b", title, flags=re.IGNORECASE)
    source_match = re.search(
        r"\b(web[- ]dl|webrip|bluray|remux|hdtv|dvdrip|bdrip)\b",
        title,
        flags=re.IGNORECASE,
    )
    if not resolution_match and not source_match:
        return "-"

    resolution = "-"
    if resolution_match:
        raw_resolution = resolution_match.group(1)
        resolution = "4K" if raw_resolution.lower() == "4k" else raw_resolution.lower()

    if not source_match:
        return resolution

    source_raw = source_match.group(1).lower().replace(" ", "-")
    source_map = {
        "web-dl": "WEB-DL",
        "webrip": "WEBRip",
        "bluray": "BluRay",
        "remux": "Remux",
        "hdtv": "HDTV",
        "dvdrip": "DVDRip",
        "bdrip": "BDRip",
    }
    source = source_map.get(source_raw, source_raw.upper())
    if resolution == "-":
        return source
    return f"{resolution} {source}"


def _to_candidate_dict(item: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): value for key, value in item.items()}


def _normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _build_query(title: str, year: str) -> str:
    cleaned_title = _normalize_spaces(title)
    cleaned_year = year.strip()
    if not cleaned_year:
        return cleaned_title
    return f"{cleaned_title} {cleaned_year}"


async def _search_first_non_empty(search_func: SearchFunc, ordered_queries: Sequence[str]) -> Sequence[Mapping[str, Any]]:
    for query in ordered_queries:
        raw_results = await search_func(query)
        if raw_results:
            return raw_results
    return ()


def _unique_queries(candidates: Sequence[str]) -> list[str]:
    ordered_queries: list[str] = []
    for query in candidates:
        cleaned_query = query.strip()
        if not cleaned_query:
            continue
        if cleaned_query in ordered_queries:
            continue
        ordered_queries.append(cleaned_query)
    return ordered_queries

from __future__ import annotations

import re
import unicodedata
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.search_title_normalization import compact_match_key, normalize_match_key
from app.clients.tmdb import TmdbMovie
from app.services.media_name_parser import parse_media_name

SearchFunc = Callable[[str], Awaitable[Sequence[Mapping[str, Any]]]]
LookupMovieFunc = Callable[[str, str], Awaitable[TmdbMovie | None]]


@dataclass(frozen=True, slots=True)
class ParsedMovieQuery:
    title: str
    year: str


@dataclass(frozen=True, slots=True)
class SearchRequestContext:
    parsed_query: ParsedMovieQuery
    tmdb_movie: TmdbMovie | None
    resolved_query: str
    raw_results: Sequence[Mapping[str, Any]]


_TRAILING_SEQUEL_DIGIT_WITH_YEAR_RE = re.compile(
    r"^(?P<title>.+?)(?P<separator>\s*)(?P<sequel>\d{1,2})(?:\s+|\s*[\[(]\s*)(?P<year>(?:19|20)\d{2})(?:\s*[\])])?$"
)
_TRAILING_SEQUEL_TOKEN_WITH_YEAR_RE = re.compile(
    r"^(?P<title>.+?)(?P<separator>\s*)(?P<sequel>(?:\d{1,2}|ii|iii|iv|v|vi|vii|viii|ix|x|第\s*[一二三四五六七八九十两\d]+\s*部))(?:\s+|\s*[\[(]\s*)(?P<year>(?:19|20)\d{2})(?:\s*[\])])?$",
    re.IGNORECASE,
)
def normalize_spaces(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return re.sub(r"\s+", " ", normalized.strip())


def parse_movie_query(query: str) -> ParsedMovieQuery:
    cleaned_query = normalize_spaces(query)
    if not cleaned_query:
        return ParsedMovieQuery(title="", year="")

    parsed_name = parse_media_name(cleaned_query)
    title = normalize_spaces(parsed_name.title or cleaned_query)
    year = str(parsed_name.year) if parsed_name.year is not None else ""
    title = _restore_trailing_sequel_token_title(
        cleaned_query=cleaned_query,
        parsed_title=title,
        parsed_year=year,
    )
    return ParsedMovieQuery(title=title, year=year)


def _restore_sequel_digit_title(
    *,
    cleaned_query: str,
    parsed_title: str,
    parsed_year: str,
) -> str:
    if not parsed_title or not parsed_year:
        return parsed_title
    match = _TRAILING_SEQUEL_DIGIT_WITH_YEAR_RE.match(cleaned_query)
    if match is None:
        return parsed_title
    if (match.group("year") or "").strip() != parsed_year:
        return parsed_title
    base_title = normalize_spaces(match.group("title") or "")
    if base_title != parsed_title:
        return parsed_title
    separator = _resolve_query_separator(match, base_title=base_title, sequel=(match.group("sequel") or "").strip())
    sequel = (match.group("sequel") or "").strip()
    return f"{parsed_title}{separator}{sequel}".strip()


def _restore_trailing_sequel_token_title(
    *,
    cleaned_query: str,
    parsed_title: str,
    parsed_year: str,
) -> str:
    restored_digit_title = _restore_sequel_digit_title(
        cleaned_query=cleaned_query,
        parsed_title=parsed_title,
        parsed_year=parsed_year,
    )
    match = _TRAILING_SEQUEL_TOKEN_WITH_YEAR_RE.match(cleaned_query)
    if match is None:
        return restored_digit_title
    if (match.group("year") or "").strip() != parsed_year:
        return restored_digit_title
    base_title = normalize_spaces(match.group("title") or "")
    sequel = normalize_spaces(match.group("sequel") or "")
    separator = _resolve_query_separator(match, base_title=base_title, sequel=sequel)
    candidate_title = f"{base_title}{separator}{sequel}".strip()
    if candidate_title == restored_digit_title:
        return restored_digit_title
    parsed_compact = compact_match_key(normalize_match_key(restored_digit_title))
    base_compact = compact_match_key(normalize_match_key(base_title))
    candidate_compact = compact_match_key(normalize_match_key(candidate_title))
    if parsed_compact == base_compact:
        return candidate_title
    if separator and parsed_compact == candidate_compact:
        return candidate_title
    return restored_digit_title


async def build_search_request_context(
    *,
    user_query: str,
    search_func: SearchFunc,
    lookup_movie_func: LookupMovieFunc | None,
) -> SearchRequestContext:
    parsed_query = parse_movie_query(user_query)
    tmdb_movie: TmdbMovie | None = None

    if lookup_movie_func is not None:
        try:
            tmdb_movie = await lookup_movie_func(parsed_query.title, parsed_query.year)
        except Exception as error:
            print(
                f"\033[31m[TMDB 查询失败]\033[0m query={user_query} title={parsed_query.title} year={parsed_query.year or '-'} 错误={error}\n\033[33m[处理建议]\033[0m 检查 TMDB API、代理和网络连通性；当前会退回普通搜索，但海报卡片和标题归一化结果可能缺失。",
                flush=True,
            )

    tmdb_confident = _is_tmdb_confident_match(parsed_query=parsed_query, tmdb_movie=tmdb_movie)
    ordered_queries = _resolve_ordered_queries(
        parsed_query=parsed_query,
        tmdb_movie=tmdb_movie,
        prefer_tmdb=tmdb_confident,
    )
    resolved_query, raw_results = await _search_candidates_with_logging(
        search_func=search_func,
        ordered_queries=ordered_queries,
        user_query=user_query,
    )
    return SearchRequestContext(
        parsed_query=parsed_query,
        tmdb_movie=tmdb_movie if tmdb_confident else None,
        resolved_query=resolved_query,
        raw_results=raw_results,
    )


def _resolve_ordered_queries(
    *,
    parsed_query: ParsedMovieQuery,
    tmdb_movie: TmdbMovie | None,
    prefer_tmdb: bool,
) -> tuple[str, ...]:
    fallback_query = _build_query(parsed_query.title, parsed_query.year)
    fallback_title_only_query = _build_query(parsed_query.title, "")
    if tmdb_movie is None:
        return tuple(_unique_queries([fallback_query, fallback_title_only_query]))

    resolved_year = tmdb_movie.year or parsed_query.year
    english_query = _build_query(tmdb_movie.title, resolved_year)
    original_query = _build_query(tmdb_movie.original_title, resolved_year)
    english_title_only_query = _build_query(tmdb_movie.title, "")
    original_title_only_query = _build_query(tmdb_movie.original_title, "")
    return tuple(
        _unique_queries(
            (
                [
                    english_query,
                    original_query,
                    fallback_query,
                    english_title_only_query,
                    original_title_only_query,
                    fallback_title_only_query,
                ]
                if prefer_tmdb
                else [
                    fallback_query,
                    english_query,
                    original_query,
                    fallback_title_only_query,
                    english_title_only_query,
                    original_title_only_query,
                ]
            )
        )
    ) or (fallback_query,)


def _build_query(title: str, year: str) -> str:
    cleaned_title = normalize_spaces(title)
    cleaned_year = year.strip()
    if not cleaned_year:
        return cleaned_title
    return f"{cleaned_title} {cleaned_year}"


async def _search_first_non_empty(
    search_func: SearchFunc,
    ordered_queries: Sequence[str],
) -> tuple[str, Sequence[Mapping[str, Any]]]:
    for query in ordered_queries:
        raw_results = await search_func(query)
        if raw_results:
            return query, raw_results
    return "", ()


async def _search_candidates_with_logging(
    *,
    search_func: SearchFunc,
    ordered_queries: Sequence[str],
    user_query: str,
) -> tuple[str, Sequence[Mapping[str, Any]]]:
    try:
        return await _search_first_non_empty(search_func, ordered_queries)
    except Exception as error:
        query_display = " | ".join(query for query in ordered_queries if query.strip()) or user_query
        print(
            f"\033[31m[搜索源查询失败]\033[0m query={user_query} ordered_queries={query_display} 错误={error}\n\033[33m[处理建议]\033[0m 检查 Prowlarr/BT 来源、代理和网络连通性；当前搜索未拿到结果，且这不是正常的“无候选”状态。",
            flush=True,
        )
        raise


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


def _is_tmdb_confident_match(
    *,
    parsed_query: ParsedMovieQuery,
    tmdb_movie: TmdbMovie | None,
) -> bool:
    if tmdb_movie is None:
        return False
    normalized_query = normalize_match_key(parsed_query.title)
    if not normalized_query:
        return False
    compact_query = compact_match_key(normalized_query)
    normalized_title = normalize_match_key(tmdb_movie.title)
    normalized_original_title = normalize_match_key(tmdb_movie.original_title)
    normalized_candidates = {normalized_title, normalized_original_title}
    compact_candidates = {compact_match_key(candidate) for candidate in normalized_candidates if candidate}
    return normalized_query in normalized_candidates or compact_query in compact_candidates


def _resolve_query_separator(match: re.Match[str], *, base_title: str, sequel: str) -> str:
    raw_separator = match.group("separator") or ""
    raw_title = match.group("title") or ""
    if (raw_separator or raw_title.endswith(" ")) and _should_preserve_query_separator(base_title, sequel):
        return " "
    return ""


def _should_preserve_query_separator(base_title: str, sequel: str) -> bool:
    _ = sequel
    return bool(re.search(r"[a-z0-9]", base_title, re.IGNORECASE))

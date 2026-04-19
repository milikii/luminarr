from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

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


def normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def parse_movie_query(query: str) -> ParsedMovieQuery:
    cleaned_query = normalize_spaces(query)
    if not cleaned_query:
        return ParsedMovieQuery(title="", year="")

    parsed_name = parse_media_name(cleaned_query)
    title = normalize_spaces(parsed_name.title or cleaned_query)
    year = str(parsed_name.year) if parsed_name.year is not None else ""
    return ParsedMovieQuery(title=title, year=year)


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

    ordered_queries = _resolve_ordered_queries(parsed_query=parsed_query, tmdb_movie=tmdb_movie)
    resolved_query, raw_results = await _search_candidates_with_logging(
        search_func=search_func,
        ordered_queries=ordered_queries,
        user_query=user_query,
    )
    return SearchRequestContext(
        parsed_query=parsed_query,
        tmdb_movie=tmdb_movie,
        resolved_query=resolved_query,
        raw_results=raw_results,
    )


def _resolve_ordered_queries(
    *,
    parsed_query: ParsedMovieQuery,
    tmdb_movie: TmdbMovie | None,
) -> tuple[str, ...]:
    fallback_query = _build_query(parsed_query.title, parsed_query.year)
    if tmdb_movie is None:
        return (fallback_query,)

    resolved_year = tmdb_movie.year or parsed_query.year
    return tuple(
        _unique_queries(
            [
                _build_query(tmdb_movie.title, resolved_year),
                _build_query(tmdb_movie.original_title, resolved_year),
            ]
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

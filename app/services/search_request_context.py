from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

import httpx

from app.clients.tmdb import TmdbMovie
from app.operational_logging import emit_operational_log
from app.search_title_normalization import (
    compact_match_key,
    is_confident_title_match,
    normalize_match_key,
    normalize_spaces,
    score_title_match,
)
from app.services.search_query_parser import ParsedMovieQuery, parse_movie_query

SearchFunc = Callable[[str], Awaitable[Sequence[Mapping[str, Any]]]]
LookupMovieFunc = Callable[[str, str], Awaitable[TmdbMovie | None]]
LookupMediaCandidatesFunc = Callable[[str, str], Awaitable[Sequence[TmdbMovie]]]
MediaIdentityState = Literal["high_confidence_identity", "needs_confirmation", "empty"]

HIGH_CONFIDENCE_IDENTITY: MediaIdentityState = "high_confidence_identity"
NEEDS_CONFIRMATION: MediaIdentityState = "needs_confirmation"
EMPTY_MEDIA_IDENTITY: MediaIdentityState = "empty"


@dataclass(frozen=True, slots=True)
class _MediaIdentityCandidateSignal:
    candidate: TmdbMovie
    title_match_score: int
    confident_title_match: bool
    year_match: bool


@dataclass(frozen=True, slots=True)
class _MediaIdentityAssessment:
    state: MediaIdentityState
    reason: str
    identity_movie: TmdbMovie | None


@dataclass(frozen=True, slots=True)
class SearchRequestContext:
    parsed_query: ParsedMovieQuery
    tmdb_movie: TmdbMovie | None
    tmdb_identity_movie: TmdbMovie | None
    tmdb_candidates: tuple[TmdbMovie, ...]
    media_identity_state: MediaIdentityState
    media_identity_reason: str
    resolved_query: str
    raw_results: Sequence[Mapping[str, Any]]


async def build_search_request_context(
    *,
    user_query: str,
    search_func: SearchFunc,
    lookup_movie_func: LookupMovieFunc | None,
    lookup_media_candidates_func: LookupMediaCandidatesFunc | None = None,
) -> SearchRequestContext:
    parsed_query = parse_movie_query(user_query)
    tmdb_movie: TmdbMovie | None = None
    tmdb_candidates: tuple[TmdbMovie, ...] = ()
    media_identity_assessment = _MediaIdentityAssessment(
        state=EMPTY_MEDIA_IDENTITY,
        reason="tmdb_lookup_unavailable",
        identity_movie=None,
    )

    if lookup_media_candidates_func is not None:
        try:
            tmdb_candidates = tuple(await lookup_media_candidates_func(parsed_query.title, parsed_query.year))
        except (httpx.HTTPError, json.JSONDecodeError) as error:
            emit_operational_log(
                title="TMDB 候选查询失败",
                detail=f"query={user_query} title={parsed_query.title} year={parsed_query.year or '-'} 错误={error}",
                fix_hint="检查 TMDB API、代理和网络连通性；当前会退回普通搜索，但候选卡片信息可能缺失。",
            )
        if tmdb_candidates:
            tmdb_movie = tmdb_candidates[0]
        media_identity_assessment = _assess_media_identity(
            parsed_query=parsed_query,
            tmdb_candidates=tmdb_candidates,
        )
        if media_identity_assessment.state == NEEDS_CONFIRMATION:
            return SearchRequestContext(
                parsed_query=parsed_query,
                tmdb_movie=tmdb_movie,
                tmdb_identity_movie=media_identity_assessment.identity_movie,
                tmdb_candidates=tmdb_candidates,
                media_identity_state=media_identity_assessment.state,
                media_identity_reason=media_identity_assessment.reason,
                resolved_query="",
                raw_results=(),
            )

    if lookup_media_candidates_func is None and lookup_movie_func is not None:
        try:
            tmdb_movie = await lookup_movie_func(parsed_query.title, parsed_query.year)
        except (httpx.HTTPError, json.JSONDecodeError) as error:
            emit_operational_log(
                title="TMDB 查询失败",
                detail=f"query={user_query} title={parsed_query.title} year={parsed_query.year or '-'} 错误={error}",
                fix_hint="检查 TMDB API、代理和网络连通性；当前会退回普通搜索，但海报卡片和标题归一化结果可能缺失。",
            )
        if tmdb_movie is not None:
            tmdb_candidates = (tmdb_movie,)

    tmdb_confident = _is_tmdb_confident_match(parsed_query=parsed_query, tmdb_movie=tmdb_movie)
    if lookup_media_candidates_func is None:
        media_identity_assessment = _MediaIdentityAssessment(
            state=HIGH_CONFIDENCE_IDENTITY if tmdb_confident else EMPTY_MEDIA_IDENTITY,
            reason="lookup_movie_exact_match" if tmdb_confident else "lookup_movie_unconfirmed",
            identity_movie=tmdb_movie if tmdb_confident else None,
        )
    ordered_queries = _resolve_ordered_queries(
        parsed_query=parsed_query,
        tmdb_movie=tmdb_movie,
    )
    resolved_query, raw_results = await _search_candidates_with_logging(
        search_func=search_func,
        ordered_queries=ordered_queries,
        user_query=user_query,
    )
    return SearchRequestContext(
        parsed_query=parsed_query,
        tmdb_movie=tmdb_movie if lookup_media_candidates_func is not None or tmdb_confident else None,
        tmdb_identity_movie=media_identity_assessment.identity_movie,
        tmdb_candidates=tmdb_candidates,
        media_identity_state=media_identity_assessment.state,
        media_identity_reason=media_identity_assessment.reason,
        resolved_query=resolved_query,
        raw_results=raw_results,
    )


def _assess_media_identity(
    *,
    parsed_query: ParsedMovieQuery,
    tmdb_candidates: Sequence[TmdbMovie],
) -> _MediaIdentityAssessment:
    if not tmdb_candidates:
        return _MediaIdentityAssessment(
            state=EMPTY_MEDIA_IDENTITY,
            reason="no_tmdb_candidates",
            identity_movie=None,
        )

    signals = tuple(
        _build_media_identity_candidate_signal(parsed_query=parsed_query, candidate=candidate)
        for candidate in tmdb_candidates
    )
    top_signal = signals[0]

    if not parsed_query.year.strip():
        return _MediaIdentityAssessment(
            state=NEEDS_CONFIRMATION,
            reason="title_only_query",
            identity_movie=None,
        )

    if not top_signal.year_match:
        return _MediaIdentityAssessment(
            state=NEEDS_CONFIRMATION,
            reason="top_candidate_year_mismatch",
            identity_movie=None,
        )

    if not top_signal.confident_title_match:
        return _MediaIdentityAssessment(
            state=NEEDS_CONFIRMATION,
            reason="low_confidence_title_match",
            identity_movie=None,
        )

    if _has_competing_identity_candidate(top_signal=top_signal, other_signals=signals[1:]):
        return _MediaIdentityAssessment(
            state=NEEDS_CONFIRMATION,
            reason="ambiguous_tmdb_candidates",
            identity_movie=None,
        )

    return _MediaIdentityAssessment(
        state=HIGH_CONFIDENCE_IDENTITY,
        reason="explicit_year_exact_match",
        identity_movie=top_signal.candidate,
    )


def _build_media_identity_candidate_signal(
    *,
    parsed_query: ParsedMovieQuery,
    candidate: TmdbMovie,
) -> _MediaIdentityCandidateSignal:
    title_match_score = max(
        score_title_match(parsed_query.title, candidate.title),
        score_title_match(parsed_query.title, candidate.original_title),
    )
    return _MediaIdentityCandidateSignal(
        candidate=candidate,
        title_match_score=title_match_score,
        confident_title_match=(
            _is_tmdb_confident_match(parsed_query=parsed_query, tmdb_movie=candidate) or title_match_score >= 3
        ),
        year_match=_candidate_year_matches_query(parsed_query=parsed_query, candidate=candidate),
    )


def _candidate_year_matches_query(
    *,
    parsed_query: ParsedMovieQuery,
    candidate: TmdbMovie,
) -> bool:
    resolved_year = parsed_query.year.strip()
    if not resolved_year:
        return False
    return candidate.year.strip() == resolved_year


def _has_competing_identity_candidate(
    *,
    top_signal: _MediaIdentityCandidateSignal,
    other_signals: Sequence[_MediaIdentityCandidateSignal],
) -> bool:
    minimum_competing_score = max(3, top_signal.title_match_score - 1)
    for signal in other_signals:
        if not signal.year_match:
            continue
        if signal.confident_title_match:
            return True
        if signal.title_match_score >= minimum_competing_score:
            return True
    return False


def _resolve_ordered_queries(
    *,
    parsed_query: ParsedMovieQuery,
    tmdb_movie: TmdbMovie | None,
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
            [
                english_query,
                original_query,
                fallback_query,
                english_title_only_query,
                original_title_only_query,
                fallback_title_only_query,
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
    except (httpx.HTTPError, json.JSONDecodeError) as error:
        query_display = " | ".join(query for query in ordered_queries if query.strip()) or user_query
        emit_operational_log(
            title="搜索源查询失败",
            detail=f"query={user_query} ordered_queries={query_display} 错误={error}",
            fix_hint="检查 Prowlarr/BT 来源、代理和网络连通性；当前搜索未拿到结果，且这不是正常的“无候选”状态。",
        )
        raise


def _unique_queries(candidates: Sequence[str]) -> list[str]:
    ordered_queries: list[str] = []
    seen_query_keys: set[str] = set()
    for query in candidates:
        cleaned_query = query.strip()
        if not cleaned_query:
            continue
        query_key = _query_dedupe_key(cleaned_query)
        if query_key in seen_query_keys:
            continue
        ordered_queries.append(cleaned_query)
        seen_query_keys.add(query_key)
    return ordered_queries


def _query_dedupe_key(query: str) -> str:
    normalized_query = normalize_match_key(query)
    if not normalized_query:
        return query.strip()
    return compact_match_key(normalized_query)


def _is_tmdb_confident_match(
    *,
    parsed_query: ParsedMovieQuery,
    tmdb_movie: TmdbMovie | None,
) -> bool:
    if tmdb_movie is None:
        return False
    return is_confident_title_match(parsed_query.title, tmdb_movie.title) or is_confident_title_match(
        parsed_query.title,
        tmdb_movie.original_title,
    )

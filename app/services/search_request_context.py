from __future__ import annotations

import inspect
import json
import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

import httpx

from app.clients.tmdb import TmdbMovie
from app.operational_logging import emit_operational_log
from app.search_franchise_intent import (
    PRIMARY_FRANCHISE_INTENT_BOOST,
    franchise_family_metric_sort_key,
    has_explicit_franchise_intent,
    resolve_franchise_intent_boost,
)
from app.search_title_normalization import (
    ShortQueryCandidateProfile,
    SHORT_STRONG_TITLE_COMPACT_LIMIT,
    compact_match_key,
    is_confident_title_match,
    is_title_match_prefix_family,
    normalize_match_key,
    normalize_spaces,
    resolve_short_query_contains_slots,
    resolve_title_match_relation,
    score_title_match,
    should_preserve_short_query_candidate_spread,
    title_match_relation_priority,
)
from app.services.search_query_parser import ParsedMovieQuery, parse_movie_query

SearchFunc = Callable[[str], Awaitable[Sequence[Mapping[str, Any]]]]
LookupMovieFunc = Callable[[str, str], Awaitable[TmdbMovie | None]]
LookupMediaCandidatesFunc = Callable[[str, str], Awaitable[Sequence[TmdbMovie]]]
MediaIdentityState = Literal["high_confidence_identity", "needs_confirmation", "empty"]

HIGH_CONFIDENCE_IDENTITY: MediaIdentityState = "high_confidence_identity"
NEEDS_CONFIRMATION: MediaIdentityState = "needs_confirmation"
EMPTY_MEDIA_IDENTITY: MediaIdentityState = "empty"
STRONG_TITLE_CONFIRMATION_LIMIT = SHORT_STRONG_TITLE_COMPACT_LIMIT
AMBIGUOUS_TITLE_CONFIRMATION_LIMIT = 5
TITLE_MATCH_WEIGHT = 100
EXACT_TITLE_BIAS_WEIGHT = 25
YEAR_MATCH_WEIGHT = 15
YEAR_MISMATCH_PENALTY = -10
STRONG_TITLE_MIN_MATCH_SCORE = 3
STRONG_TITLE_LARGE_GAP = 60
STRONG_TITLE_EXACT_GAP = 25
STRONG_TITLE_YEAR_GAP = 20
FRANCHISE_INTENT_RELEVANCE_WEIGHT = 500
EXPANDED_CONFIRMATION_CANDIDATE_LOOKUP_LIMIT = 30


@dataclass(frozen=True, slots=True)
class _MediaIdentityCandidateSignal:
    candidate: TmdbMovie
    franchise_intent_boost: int
    title_match_score: int
    exact_title_bias: int
    confident_title_match: bool
    year_match: bool
    relevance_score: int


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
    confirmation_candidate_limit: int | None = None,
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
            tmdb_candidates = tuple(
                await _lookup_confirmation_media_candidates(
                    lookup_media_candidates_func=lookup_media_candidates_func,
                    title=parsed_query.title,
                    year=parsed_query.year,
                    confirmation_candidate_limit=confirmation_candidate_limit,
                )
            )
        except (httpx.HTTPError, json.JSONDecodeError) as error:
            emit_operational_log(
                title="TMDB 候选查询失败",
                detail=f"query={user_query} title={parsed_query.title} year={parsed_query.year or '-'} 错误={error}",
                fix_hint="检查 TMDB API、代理和网络连通性；当前会退回普通搜索，但候选卡片信息可能缺失。",
            )
        if tmdb_candidates:
            tmdb_candidates = _select_confirmation_tmdb_candidates(
                parsed_query=parsed_query,
                tmdb_candidates=tmdb_candidates,
                confirmation_candidate_limit=confirmation_candidate_limit,
            )
            tmdb_movie = tmdb_candidates[0]
        media_identity_assessment = _assess_media_identity(
            parsed_query=parsed_query,
            tmdb_candidates=tmdb_candidates,
        )
        if tmdb_candidates:
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


async def _lookup_confirmation_media_candidates(
    *,
    lookup_media_candidates_func: LookupMediaCandidatesFunc,
    title: str,
    year: str,
    confirmation_candidate_limit: int | None,
) -> Sequence[TmdbMovie]:
    desired_limit = _resolve_confirmation_candidate_lookup_limit(confirmation_candidate_limit)
    if desired_limit is None:
        return await lookup_media_candidates_func(title, year)
    try:
        signature = inspect.signature(lookup_media_candidates_func)
    except (TypeError, ValueError):
        signature = None
    if signature is None or "limit" not in signature.parameters:
        return await lookup_media_candidates_func(title, year)
    return await lookup_media_candidates_func(title, year, limit=desired_limit)


def _resolve_confirmation_candidate_lookup_limit(confirmation_candidate_limit: int | None) -> int | None:
    if confirmation_candidate_limit is None:
        return None
    if confirmation_candidate_limit <= 0:
        return EXPANDED_CONFIRMATION_CANDIDATE_LOOKUP_LIMIT
    return confirmation_candidate_limit


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

    signals = _ordered_media_identity_candidate_signals(
        parsed_query=parsed_query,
        tmdb_candidates=tmdb_candidates,
    )
    signals = _prefer_primary_franchise_confirmation_signals(
        parsed_query=parsed_query,
        signals=signals,
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
    exact_title_bias = _resolve_exact_title_bias(
        query_title=parsed_query.title,
        localized_title=candidate.title,
        original_title=candidate.original_title,
    )
    year_match = _candidate_year_matches_query(parsed_query=parsed_query, candidate=candidate)
    franchise_intent_boost = resolve_franchise_intent_boost(
        parsed_query.title,
        candidate.title,
        candidate.original_title,
    )
    title_match_score = max(
        score_title_match(parsed_query.title, candidate.title),
        score_title_match(parsed_query.title, candidate.original_title),
    )
    return _MediaIdentityCandidateSignal(
        candidate=candidate,
        franchise_intent_boost=franchise_intent_boost,
        title_match_score=title_match_score,
        exact_title_bias=exact_title_bias,
        confident_title_match=(
            _is_tmdb_confident_match(parsed_query=parsed_query, tmdb_movie=candidate) or title_match_score >= 3
        ),
        year_match=year_match,
        relevance_score=_score_confirmation_candidate(
            franchise_intent_boost=franchise_intent_boost,
            title_match_score=title_match_score,
            exact_title_bias=exact_title_bias,
            year_match=year_match,
            query_year=parsed_query.year,
        ),
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


def _select_confirmation_tmdb_candidates(
    *,
    parsed_query: ParsedMovieQuery,
    tmdb_candidates: Sequence[TmdbMovie],
    confirmation_candidate_limit: int | None = None,
) -> tuple[TmdbMovie, ...]:
    if not tmdb_candidates:
        return ()

    signals = _ordered_media_identity_candidate_signals(
        parsed_query=parsed_query,
        tmdb_candidates=tmdb_candidates,
    )
    signals = _prefer_primary_franchise_confirmation_signals(
        parsed_query=parsed_query,
        signals=signals,
    )
    if _should_preserve_short_query_candidate_spread(parsed_query=parsed_query, signals=signals):
        signals = _diversify_short_query_confirmation_signals(
            parsed_query=parsed_query,
            signals=signals,
        )
    if confirmation_candidate_limit is None:
        limit = _resolve_confirmation_candidate_limit(parsed_query=parsed_query, signals=signals)
    elif confirmation_candidate_limit <= 0:
        limit = len(signals)
    else:
        limit = min(len(signals), confirmation_candidate_limit)
    return tuple(signal.candidate for signal in signals[:limit])


def _ordered_media_identity_candidate_signals(
    *,
    parsed_query: ParsedMovieQuery,
    tmdb_candidates: Sequence[TmdbMovie],
) -> tuple[_MediaIdentityCandidateSignal, ...]:
    signals = [
        _build_media_identity_candidate_signal(parsed_query=parsed_query, candidate=candidate)
        for candidate in tmdb_candidates
    ]
    signals.sort(
        key=lambda signal: (
            signal.relevance_score,
            signal.title_match_score,
            signal.exact_title_bias,
        ),
        reverse=True,
    )
    return tuple(signals)


def _prefer_primary_franchise_confirmation_signals(
    *,
    parsed_query: ParsedMovieQuery,
    signals: Sequence[_MediaIdentityCandidateSignal],
) -> tuple[_MediaIdentityCandidateSignal, ...]:
    if not signals or not has_explicit_franchise_intent(parsed_query.title):
        return tuple(signals)

    primary_signals = tuple(
        signal for signal in signals if signal.franchise_intent_boost >= PRIMARY_FRANCHISE_INTENT_BOOST
    )
    if primary_signals:
        return tuple(
            sorted(
                primary_signals,
                key=lambda signal: _protected_franchise_confirmation_sort_key(
                    signal,
                    query_year=parsed_query.year,
                ),
                reverse=True,
            )
        )
    return tuple(signals)


def _protected_franchise_confirmation_sort_key(
    signal: _MediaIdentityCandidateSignal,
    *,
    query_year: str,
) -> tuple[int, float, float, int]:
    candidate = signal.candidate
    metric_key = franchise_family_metric_sort_key(
        popularity=candidate.popularity,
        vote_average=candidate.vote_average,
        vote_count=candidate.vote_count,
    )
    year_priority = 1 if query_year.strip() and candidate.year == query_year.strip() else 0
    return year_priority, *metric_key


def _resolve_confirmation_candidate_limit(
    *,
    parsed_query: ParsedMovieQuery,
    signals: Sequence[_MediaIdentityCandidateSignal],
) -> int:
    if not signals:
        return 0
    if _should_compact_confirmation_candidates(parsed_query=parsed_query, signals=signals):
        return min(len(signals), STRONG_TITLE_CONFIRMATION_LIMIT)
    return min(len(signals), AMBIGUOUS_TITLE_CONFIRMATION_LIMIT)


def _should_compact_confirmation_candidates(
    *,
    parsed_query: ParsedMovieQuery,
    signals: Sequence[_MediaIdentityCandidateSignal],
) -> bool:
    top_signal = signals[0]
    if _should_preserve_short_query_candidate_spread(parsed_query=parsed_query, signals=signals):
        return False
    if top_signal.title_match_score < STRONG_TITLE_MIN_MATCH_SCORE:
        return False
    if top_signal.exact_title_bias <= 0 and not top_signal.confident_title_match:
        return False
    if len(signals) == 1:
        return True

    second_signal = signals[1]
    relevance_gap = top_signal.relevance_score - second_signal.relevance_score
    if relevance_gap >= STRONG_TITLE_LARGE_GAP:
        return True
    if top_signal.exact_title_bias > second_signal.exact_title_bias and relevance_gap >= STRONG_TITLE_EXACT_GAP:
        return True
    if (
        parsed_query.year.strip()
        and top_signal.year_match
        and not second_signal.year_match
        and relevance_gap >= STRONG_TITLE_YEAR_GAP
    ):
        return True
    return False


def _should_preserve_short_query_candidate_spread(
    *,
    parsed_query: ParsedMovieQuery,
    signals: Sequence[_MediaIdentityCandidateSignal],
) -> bool:
    if not signals:
        return False
    competitor_profiles: list[ShortQueryCandidateProfile] = []
    for signal in signals[1:]:
        relation = _resolve_confirmation_candidate_match_relation(
            query_title=parsed_query.title,
            candidate=signal.candidate,
        )
        competitor_profiles.append(
            ShortQueryCandidateProfile(
                dedupe_key=f"{signal.candidate.media_type}:{signal.candidate.tmdb_id or f'{signal.candidate.title}|{signal.candidate.year}'}",
                relation=relation,
                popularity=signal.candidate.popularity,
                vote_count=signal.candidate.vote_count,
            )
        )
    return should_preserve_short_query_candidate_spread(
        title=parsed_query.title,
        year=parsed_query.year,
        top_exact_bias=signals[0].exact_title_bias,
        competitor_profiles=competitor_profiles,
    )


def _diversify_short_query_confirmation_signals(
    *,
    parsed_query: ParsedMovieQuery,
    signals: Sequence[_MediaIdentityCandidateSignal],
) -> tuple[_MediaIdentityCandidateSignal, ...]:
    if len(signals) <= 1:
        return tuple(signals)

    top_signal = signals[0]
    prefix_signals: list[_MediaIdentityCandidateSignal] = []
    contains_signals: list[_MediaIdentityCandidateSignal] = []
    fallback_signals: list[_MediaIdentityCandidateSignal] = []
    for signal in signals[1:]:
        relation = _resolve_confirmation_candidate_match_relation(
            query_title=parsed_query.title,
            candidate=signal.candidate,
        )
        if relation == "contains":
            contains_signals.append(signal)
        elif is_title_match_prefix_family(relation):
            prefix_signals.append(signal)
        else:
            fallback_signals.append(signal)

    if has_explicit_franchise_intent(parsed_query.title):
        prefix_signals.sort(
            key=lambda signal: _protected_franchise_confirmation_sort_key(signal, query_year=""),
            reverse=True,
        )
    else:
        prefix_signals.sort(key=_short_query_confirmation_prefix_sort_key, reverse=True)
    contains_signals.sort(key=_short_query_confirmation_contains_sort_key, reverse=True)
    top_relation = _resolve_confirmation_candidate_match_relation(
        query_title=parsed_query.title,
        candidate=top_signal.candidate,
    )
    family_candidate_count = len(prefix_signals) + (1 if is_title_match_prefix_family(top_relation) else 0)
    contains_slots = resolve_short_query_contains_slots(
        limit=AMBIGUOUS_TITLE_CONFIRMATION_LIMIT,
        family_candidate_count=family_candidate_count,
        contains_count=len(contains_signals),
    )
    selected: list[_MediaIdentityCandidateSignal] = [top_signal]
    selected.extend(prefix_signals[: max(0, AMBIGUOUS_TITLE_CONFIRMATION_LIMIT - 1 - contains_slots)])
    selected.extend(contains_signals[:contains_slots])

    seen_keys = {
        (signal.candidate.media_type, signal.candidate.tmdb_id or f"{signal.candidate.title}|{signal.candidate.year}")
        for signal in selected
    }
    for signal in [*prefix_signals, *contains_signals, *fallback_signals]:
        candidate_key = (
            signal.candidate.media_type,
            signal.candidate.tmdb_id or f"{signal.candidate.title}|{signal.candidate.year}",
        )
        if candidate_key in seen_keys:
            continue
        selected.append(signal)
        seen_keys.add(candidate_key)
        if len(selected) >= AMBIGUOUS_TITLE_CONFIRMATION_LIMIT:
            break
    return tuple(selected)


def _resolve_confirmation_candidate_match_relation(*, query_title: str, candidate: TmdbMovie) -> str:
    localized_relation = resolve_title_match_relation(query_title, candidate.title)
    original_relation = resolve_title_match_relation(query_title, candidate.original_title)
    if title_match_relation_priority(original_relation) > title_match_relation_priority(localized_relation):
        return original_relation
    return localized_relation


def _short_query_confirmation_contains_sort_key(
    signal: _MediaIdentityCandidateSignal,
) -> tuple[int, float, int, int, int]:
    candidate = signal.candidate
    return (
        signal.relevance_score,
        candidate.popularity,
        candidate.vote_count,
        1 if candidate.poster_path else 0,
        1 if candidate.overview else 0,
    )


def _short_query_confirmation_prefix_sort_key(
    signal: _MediaIdentityCandidateSignal,
) -> tuple[int, int, float, int, int, int]:
    candidate = signal.candidate
    return (
        signal.relevance_score,
        signal.exact_title_bias,
        candidate.popularity,
        candidate.vote_count,
        1 if candidate.poster_path else 0,
        1 if candidate.overview else 0,
    )


def _resolve_exact_title_bias(
    *,
    query_title: str,
    localized_title: str,
    original_title: str,
) -> int:
    compact_query = _compact_title_match_key(query_title)
    compact_localized_title = _compact_title_match_key(localized_title)
    compact_original_title = _compact_title_match_key(original_title)
    normalized_query = normalize_match_key(query_title)
    normalized_localized_title = normalize_match_key(localized_title)
    normalized_original_title = normalize_match_key(original_title)
    if compact_query and (compact_localized_title == compact_query or compact_original_title == compact_query):
        return 2
    if normalized_query and (normalized_localized_title == normalized_query or normalized_original_title == normalized_query):
        return 1
    return 0


def _score_confirmation_candidate(
    *,
    franchise_intent_boost: int,
    title_match_score: int,
    exact_title_bias: int,
    year_match: bool,
    query_year: str,
) -> int:
    year_score = 0
    if query_year.strip():
        year_score = YEAR_MATCH_WEIGHT if year_match else YEAR_MISMATCH_PENALTY
    return (
        franchise_intent_boost * FRANCHISE_INTENT_RELEVANCE_WEIGHT
        + title_match_score * TITLE_MATCH_WEIGHT
        + exact_title_bias * EXACT_TITLE_BIAS_WEIGHT
        + year_score
    )


def _compact_title_match_key(value: str) -> str:
    return re.sub(r"[\W_]+", "", normalize_match_key(value), flags=re.UNICODE).lower()


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

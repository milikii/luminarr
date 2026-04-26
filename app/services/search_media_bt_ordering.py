from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from app.search_title_normalization import BT_RESULT_TITLE_NOISE_TOKENS, compact_match_key, normalize_match_key, normalize_spaces
from app.services.bt_candidate_scorer import BTCandidate, BTScoringContext, filter_candidates, load_bt_scoring_rules
from app.services.bt_sources import resolve_bt_source
from app.services.search_query_parser import parse_movie_query
from app.services.search_reply_formatter import safe_indexer, safe_text


def order_media_bt_results(
    raw_results: Sequence[Mapping[str, Any]],
    *,
    query: str,
    load_bt_scoring_rules_func=load_bt_scoring_rules,
) -> Sequence[Mapping[str, Any]]:
    candidate_pairs: list[tuple[BTCandidate, Mapping[str, Any]]] = []
    remainder: list[Mapping[str, Any]] = []
    for item in raw_results:
        candidate = _build_media_bt_candidate(item)
        if candidate is None:
            remainder.append(item)
            continue
        candidate_pairs.append((candidate, item))
    if not candidate_pairs:
        return raw_results

    scored_candidates = filter_candidates(
        [candidate for candidate, _ in candidate_pairs],
        BTScoringContext(query=query, media_kind="movie"),
        rules=load_bt_scoring_rules_func(),
    )
    if all(scored_candidate.drop_reason == "title_mismatch" for scored_candidate in scored_candidates):
        fallback_queries = _derive_media_title_fallback_queries(raw_results, query=query)
        best_fallback_metrics: tuple[int, float, float] | None = None
        best_rescored_candidates: Sequence[Any] | None = None
        for fallback_query in fallback_queries:
            rescored_candidates = filter_candidates(
                [candidate for candidate, _ in candidate_pairs],
                BTScoringContext(query=fallback_query, media_kind="movie"),
                rules=load_bt_scoring_rules_func(),
            )
            fallback_metrics = _score_fallback_candidates(rescored_candidates)
            if fallback_metrics[0] <= 0:
                continue
            if best_fallback_metrics is None or fallback_metrics > best_fallback_metrics:
                best_fallback_metrics = fallback_metrics
                best_rescored_candidates = rescored_candidates
        if best_rescored_candidates is not None:
            scored_candidates = list(best_rescored_candidates)

    ordered_results: list[Mapping[str, Any]] = []
    for scored_candidate in scored_candidates:
        if scored_candidate.drop_reason is not None:
            continue
        for candidate, item in candidate_pairs:
            if candidate is scored_candidate.candidate:
                ordered_results.append(item)
                break
    if not ordered_results:
        return ()
    ordered_results.extend(remainder)
    return tuple(_dedupe_media_bt_results_by_title(ordered_results))


def _dedupe_media_bt_results_by_title(results: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    deduped_results: list[Mapping[str, Any]] = []
    seen_titles: set[str] = set()
    for item in results:
        title_key = _media_bt_result_dedupe_key(item)
        if title_key:
            if title_key in seen_titles:
                continue
            seen_titles.add(title_key)
        deduped_results.append(item)
    return deduped_results


def _media_bt_result_dedupe_key(item: Mapping[str, Any]) -> str:
    title = normalize_spaces(safe_text(item.get("title"), default=""))
    if not title:
        return ""
    normalized_title = _normalize_media_bt_title_for_dedupe(title)
    if not normalized_title:
        return title.lower()
    resolution = _extract_resolution_token(title)
    if not resolution:
        return normalized_title
    return f"{normalized_title}|{resolution}"


def _normalize_media_bt_title_for_dedupe(title: str) -> str:
    cleaned_title = re.sub(r"-[A-Za-z0-9][A-Za-z0-9-]*$", "", title.strip())
    normalized_title = normalize_match_key(cleaned_title)
    if not normalized_title:
        return ""
    filtered_tokens: list[str] = []
    stopwords = BT_RESULT_TITLE_NOISE_TOKENS | {"2audio", "gbr", "usa", "jpn", "fra"}
    for token in normalized_title.split():
        if re.fullmatch(r"(?:19|20)\d{2}", token):
            continue
        if token in stopwords:
            continue
        filtered_tokens.append(token)
    return compact_match_key(" ".join(filtered_tokens))


def _extract_resolution_token(title: str) -> str:
    match = re.search(r"\b(2160p|4k|1080p|720p|480p)\b", title, flags=re.IGNORECASE)
    if match is None:
        return ""
    token = str(match.group(1) or "").lower()
    if token == "4k":
        return "2160p"
    return token


def _derive_media_title_fallback_queries(
    raw_results: Sequence[Mapping[str, Any]],
    *,
    query: str,
) -> tuple[str, ...]:
    parsed_query = parse_movie_query(query)
    titles = [safe_text(item.get("title"), default="") for item in raw_results[:5]]
    normalized_titles = [_normalize_title_tokens_for_fallback(title) for title in titles if title]
    if not normalized_titles:
        return ()
    token_counts = _count_fallback_tokens(normalized_titles)
    minimum_shared_count = 1 if len(normalized_titles) == 1 else 2
    fallback_queries: list[str] = []
    for title_tokens in normalized_titles:
        common_tokens = [token for token in title_tokens if token_counts.get(token, 0) >= minimum_shared_count]
        if not common_tokens:
            continue
        query_text = " ".join(common_tokens).strip()
        if not query_text:
            continue
        fallback_queries.append(f"{query_text} {parsed_query.year}".strip() if parsed_query.year else query_text)
    return tuple(dict.fromkeys(fallback_queries))


def _normalize_title_tokens_for_fallback(title: str) -> list[str]:
    normalized = re.sub(r"\b\d\.\d\b", " ", title.strip(), flags=re.IGNORECASE)
    normalized = normalize_match_key(normalized)
    tokens = [token for token in normalized.split() if token]
    stopwords = BT_RESULT_TITLE_NOISE_TOKENS | {"max"}
    return [token for token in tokens if token not in stopwords and not re.fullmatch(r"(?:19|20)\d{2}", token)]


def _count_fallback_tokens(normalized_titles: Sequence[Sequence[str]]) -> dict[str, int]:
    token_counts: dict[str, int] = {}
    for tokens in normalized_titles:
        for token in dict.fromkeys(tokens):
            token_counts[token] = token_counts.get(token, 0) + 1
    return token_counts


def _score_fallback_candidates(scored_candidates: Sequence[Any]) -> tuple[int, float, float]:
    accepted_candidates = [candidate for candidate in scored_candidates if candidate.drop_reason is None]
    if not accepted_candidates:
        return 0, 0.0, 0.0
    return (
        len(accepted_candidates),
        max(candidate.score for candidate in accepted_candidates),
        sum(candidate.score for candidate in accepted_candidates),
    )


def _build_media_bt_candidate(item: Mapping[str, Any]) -> BTCandidate | None:
    source = resolve_bt_source(item)
    title = safe_text(item.get("title"), default="")
    if not source or not title:
        return None
    return BTCandidate(
        source_site=safe_indexer(item.get("indexer"), item.get("indexerName")),
        title=title,
        magnet_or_torrent_url=source,
        size_bytes=_safe_optional_int(item.get("size")),
        seeders=_safe_optional_int(item.get("seeders")),
        leechers=_safe_optional_int(item.get("peers")),
        resolution=_extract_resolution(title),
        codec=_extract_codec(title),
        source_type=_extract_source_type(title),
        audio=(),
        release_group=_extract_release_group(title),
        age_days=None,
        media_kind="movie",
    )


def _extract_resolution(title: str) -> str | None:
    lowered_title = title.strip().lower()
    if re.search(r"\b(2160p|4k)\b", lowered_title):
        return "2160p"
    if re.search(r"\b1080p\b", lowered_title):
        return "1080p"
    if re.search(r"\b720p\b", lowered_title):
        return "720p"
    return None


def _extract_codec(title: str) -> str | None:
    lowered_title = title.strip().lower()
    if re.search(r"\b(x265|hevc)\b", lowered_title):
        return "x265" if "x265" in lowered_title else "HEVC"
    if re.search(r"\b(x264|avc)\b", lowered_title):
        return "x264"
    return None


def _extract_source_type(title: str) -> str | None:
    lowered_title = title.strip().lower()
    if "remux" in lowered_title:
        return "Remux"
    if "bluray" in lowered_title or "blu-ray" in lowered_title:
        return "BluRay"
    if "bdrip" in lowered_title:
        return "BDRip"
    if "web-dl" in lowered_title or "webdl" in lowered_title:
        return "WEB-DL"
    if "webrip" in lowered_title or "web-rip" in lowered_title:
        return "WEBRip"
    return None


def _extract_release_group(title: str) -> str | None:
    matched = re.search(r"-([A-Za-z0-9][A-Za-z0-9-]+)$", title.strip())
    if matched is None:
        return None
    return str(matched.group(1) or "").strip() or None


def _safe_optional_int(value: Any) -> int | None:
    try:
        resolved = int(value)
    except (TypeError, ValueError):
        return None
    if resolved > 0:
        return resolved
    return None

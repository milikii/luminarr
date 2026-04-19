from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass

_INFO_HASH_PATTERN = re.compile(r"xt=urn:btih:([0-9a-z]{32,40})", re.IGNORECASE)
_NORMALIZED_TEXT_PATTERN = re.compile(r"[^0-9a-z\u4e00-\u9fff]+", re.IGNORECASE)
_LOW_QUALITY_PATTERN = re.compile(r"\b(cam|hdcam|ts|tc|telesync|telecine|screener|枪版|摄像)\b", re.IGNORECASE)
_MULTI_ITEM_PATTERNS = (
    re.compile(r"\bcomplete\b", re.IGNORECASE),
    re.compile(r"\bcollection\b", re.IGNORECASE),
    re.compile(r"\bbatch\b", re.IGNORECASE),
    re.compile(r"\bpack\b", re.IGNORECASE),
    re.compile(r"\b全集\b", re.IGNORECASE),
    re.compile(r"\b合集\b", re.IGNORECASE),
    re.compile(r"\b全季\b", re.IGNORECASE),
    re.compile(r"\b打包\b", re.IGNORECASE),
    re.compile(r"\bs\d{1,2}\s*-\s*s?\d{1,2}\b", re.IGNORECASE),
    re.compile(r"\bs\d{1,2}\b(?!\s*e\d{1,3})", re.IGNORECASE),
    re.compile(r"\be\d{1,3}\s*-\s*e?\d{1,3}\b", re.IGNORECASE),
    re.compile(r"\b\d{1,3}\s*-\s*\d{1,3}\b", re.IGNORECASE),
)
_DEFAULT_MOVIE_SIZE_RANGE = (5 * 1024**3, 15 * 1024**3)
_DEFAULT_EPISODE_SIZE_RANGE = (1 * 1024**3, 5 * 1024**3)


@dataclass(frozen=True, slots=True)
class BTCandidate:
    source_site: str
    title: str
    magnet_or_torrent_url: str
    size_bytes: int | None
    seeders: int | None
    leechers: int | None
    resolution: str | None
    codec: str | None
    source_type: str | None
    audio: tuple[str, ...]
    release_group: str | None
    age_days: int | None
    media_kind: str


@dataclass(frozen=True, slots=True)
class BTScoringContext:
    query: str
    media_kind: str
    single_item_mode: bool = False
    seen_info_hashes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    candidate: BTCandidate
    score: float
    score_breakdown: dict[str, float]
    drop_reason: str | None


@dataclass(frozen=True, slots=True)
class BTScoringRules:
    weights: dict[str, float]
    resolution_scores: dict[str | None, float]
    source_type_scores: dict[str | None, float]
    codec_scores: dict[str | None, float]
    release_group_preferred: tuple[str, ...]


DEFAULT_BT_SCORING_RULES = BTScoringRules(
    weights={
        "resolution": 3.0,
        "source_type": 2.5,
        "seeders": 2.0,
        "size_fit": 1.5,
        "codec": 1.0,
        "release_group": 0.5,
    },
    resolution_scores={
        "2160p": 1.0,
        "1080p": 0.8,
        "720p": 0.4,
        None: 0.2,
    },
    source_type_scores={
        "Remux": 1.0,
        "BluRay": 0.9,
        "BDRip": 0.8,
        "WEB-DL": 0.7,
        "WEBRip": 0.5,
        None: 0.3,
    },
    codec_scores={
        "x265": 0.9,
        "HEVC": 0.9,
        "x264": 0.8,
        None: 0.4,
    },
    release_group_preferred=("VCB-Studio", "SweetSub", "CHD", "WiKi", "FRDS"),
)


def filter_candidates(
    candidates: Sequence[BTCandidate],
    context: BTScoringContext,
    *,
    rules: BTScoringRules = DEFAULT_BT_SCORING_RULES,
) -> list[ScoredCandidate]:
    seen_info_hashes = {info_hash.strip().lower() for info_hash in context.seen_info_hashes if info_hash.strip()}
    scored_items: list[tuple[int, ScoredCandidate]] = []
    for index, candidate in enumerate(candidates):
        drop_reason = _resolve_drop_reason(candidate=candidate, context=context, seen_info_hashes=seen_info_hashes)
        if drop_reason is None:
            info_hash = _extract_info_hash(candidate.magnet_or_torrent_url)
            if info_hash:
                seen_info_hashes.add(info_hash)
            score_breakdown = _build_score_breakdown(candidate=candidate, context=context, rules=rules)
            score = sum(score_breakdown[name] * rules.weights[name] for name in rules.weights)
        else:
            score_breakdown = {}
            score = 0.0
        scored_items.append(
            (
                index,
                ScoredCandidate(
                    candidate=candidate,
                    score=score,
                    score_breakdown=score_breakdown,
                    drop_reason=drop_reason,
                ),
            )
        )
    ranked_items = sorted(
        scored_items,
        key=lambda item: (item[1].drop_reason is None, item[1].score, -item[0]),
        reverse=True,
    )
    return [item[1] for item in ranked_items]


def pick_best(
    candidates: Sequence[BTCandidate],
    context: BTScoringContext,
    *,
    rules: BTScoringRules = DEFAULT_BT_SCORING_RULES,
) -> ScoredCandidate | None:
    for scored_candidate in filter_candidates(candidates, context, rules=rules):
        if scored_candidate.drop_reason is None:
            return scored_candidate
    return None


def _resolve_drop_reason(
    *,
    candidate: BTCandidate,
    context: BTScoringContext,
    seen_info_hashes: set[str],
) -> str | None:
    if not _looks_like_valid_download_source(candidate.magnet_or_torrent_url):
        return "invalid_source"
    if not _title_matches_query(candidate.title, context.query):
        return "title_mismatch"
    info_hash = _extract_info_hash(candidate.magnet_or_torrent_url)
    if info_hash and info_hash in seen_info_hashes:
        return "duplicate_info_hash"
    if _is_low_quality_title(candidate.title):
        return "low_quality_title"
    if context.single_item_mode and _looks_like_multi_item_release(candidate.title):
        return "multi_item_release"
    return None


def _build_score_breakdown(
    *,
    candidate: BTCandidate,
    context: BTScoringContext,
    rules: BTScoringRules,
) -> dict[str, float]:
    return {
        "resolution": _score_lookup(candidate.resolution, rules.resolution_scores),
        "source_type": _score_lookup(candidate.source_type, rules.source_type_scores),
        "seeders": _score_seeders(candidate.seeders),
        "size_fit": _score_size_fit(candidate=candidate, context=context),
        "codec": _score_lookup(candidate.codec, rules.codec_scores),
        "release_group": _score_release_group(candidate.release_group, rules.release_group_preferred),
    }


def _score_lookup(value: str | None, score_map: dict[str | None, float]) -> float:
    return score_map.get(value, score_map.get(None, 0.0))


def _score_seeders(seeders: int | None) -> float:
    if seeders is None or seeders <= 0:
        return 0.0
    if seeders >= 50:
        return 1.0
    if seeders >= 20:
        return 0.8
    if seeders >= 5:
        return 0.5
    return 0.2


def _score_size_fit(*, candidate: BTCandidate, context: BTScoringContext) -> float:
    size_bytes = candidate.size_bytes
    if size_bytes is None or size_bytes <= 0:
        return 0.0
    expected_range = _expected_size_range(context)
    if expected_range is None:
        return 0.5
    expected_min, expected_max = expected_range
    if expected_min <= size_bytes <= expected_max:
        return 1.0
    if size_bytes < expected_min:
        return max(0.0, min(1.0, size_bytes / expected_min))
    return max(0.0, min(1.0, expected_max / size_bytes))


def _expected_size_range(context: BTScoringContext) -> tuple[int, int] | None:
    if context.media_kind == "movie":
        return _DEFAULT_MOVIE_SIZE_RANGE
    if context.media_kind in {"series", "anime"}:
        return _DEFAULT_EPISODE_SIZE_RANGE
    if context.media_kind == "raw_bt" and context.single_item_mode:
        return _DEFAULT_EPISODE_SIZE_RANGE
    return None


def _score_release_group(release_group: str | None, preferred_groups: tuple[str, ...]) -> float:
    if not release_group:
        return 0.0
    if release_group in preferred_groups:
        return 1.0
    return 0.2


def _looks_like_valid_download_source(source: str) -> bool:
    cleaned_source = source.strip()
    if not cleaned_source:
        return False
    lowered_source = cleaned_source.lower()
    return lowered_source.startswith("magnet:?") or lowered_source.startswith("http://") or lowered_source.startswith(
        "https://"
    )


def _title_matches_query(title: str, query: str) -> bool:
    normalized_query = _normalize_text(query)
    if not normalized_query:
        return True
    normalized_title = _normalize_text(title)
    if not normalized_title:
        return False
    if normalized_query in normalized_title:
        return True

    query_tokens = [token for token in normalized_query.split() if token]
    if not query_tokens:
        return True
    matched_count = sum(1 for token in query_tokens if token in normalized_title)
    required_count = max(1, math.ceil(len(query_tokens) * 0.8))
    return matched_count >= required_count


def _normalize_text(text: str) -> str:
    normalized = _NORMALIZED_TEXT_PATTERN.sub(" ", text.strip().lower())
    return re.sub(r"\s+", " ", normalized).strip()


def _extract_info_hash(source: str) -> str:
    matched = _INFO_HASH_PATTERN.search(source)
    if matched is None:
        return ""
    return str(matched.group(1) or "").strip().lower()


def _is_low_quality_title(title: str) -> bool:
    return _LOW_QUALITY_PATTERN.search(title.strip()) is not None


def _looks_like_multi_item_release(title: str) -> bool:
    cleaned_title = title.strip()
    if not cleaned_title:
        return False
    return any(pattern.search(cleaned_title) is not None for pattern in _MULTI_ITEM_PATTERNS)

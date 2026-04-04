from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PureBtCandidate:
    index: int
    result: Mapping[str, Any]
    title: str
    source: str
    quality_rank: int
    seeders: int
    size_bytes: int


def extract_bt_search_query(text: str) -> str:
    cleaned_text = text.strip()
    if not cleaned_text or cleaned_text.lower().startswith("magnet:?"):
        return ""

    matched = re.match(r"^(?i:(下载这个|下载此))\s*(?i:(bt种子|bt|磁力))\s+(.+)$", cleaned_text)
    if matched is None:
        return ""
    return str(matched.group(3) or "").strip()


def pick_single_item_candidate(
    results: Sequence[Mapping[str, Any]],
    *,
    query: str,
) -> Mapping[str, Any] | None:
    ranked_candidates = sorted(
        _collect_single_item_candidates(results, query=query),
        key=_candidate_sort_key,
        reverse=True,
    )
    if not ranked_candidates:
        return None
    return ranked_candidates[0].result


def _collect_single_item_candidates(
    results: Sequence[Mapping[str, Any]],
    *,
    query: str,
) -> list[PureBtCandidate]:
    candidates: list[PureBtCandidate] = []
    for index, result in enumerate(results):
        source = _resolve_candidate_source(result)
        if not source:
            continue

        title = str(result.get("title", "")).strip()
        if not title:
            continue
        if not _title_matches_query(title=title, query=query):
            continue
        if _is_low_quality_title(title):
            continue
        if _looks_like_multi_item_release(title):
            continue

        candidates.append(
            PureBtCandidate(
                index=index,
                result=result,
                title=title,
                source=source,
                quality_rank=_quality_rank(title),
                seeders=_safe_int(result.get("seeders")),
                size_bytes=_safe_int(result.get("size")),
            )
        )
    return candidates


def _candidate_sort_key(candidate: PureBtCandidate) -> tuple[int, int, int, int]:
    return (
        candidate.quality_rank,
        candidate.seeders,
        candidate.size_bytes,
        -candidate.index,
    )


def _resolve_candidate_source(candidate: Mapping[str, Any]) -> str:
    for key in ("downloadUrl", "downloadurl", "magnetUrl", "magneturl", "guid"):
        value = candidate.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _title_matches_query(*, title: str, query: str) -> bool:
    normalized_title = _normalize_for_match(title)
    normalized_query = _normalize_for_match(query)
    if not normalized_title or not normalized_query:
        return False
    if normalized_query in normalized_title:
        return True

    query_tokens = [token for token in normalized_query.split() if len(token) >= 2 or token.isdigit()]
    if not query_tokens:
        return True

    matched_count = sum(1 for token in query_tokens if token in normalized_title)
    required_count = 1 if len(query_tokens) == 1 else 2
    return matched_count >= required_count


def _normalize_for_match(text: str) -> str:
    normalized = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", " ", text.strip().lower())
    return re.sub(r"\s+", " ", normalized).strip()


def _is_low_quality_title(title: str) -> bool:
    lowered_title = title.strip().lower()
    if not lowered_title:
        return False
    return re.search(r"\b(cam|hdcam|ts|tc|telesync|telecine|screener)\b", lowered_title) is not None


def _looks_like_multi_item_release(title: str) -> bool:
    lowered_title = title.strip().lower()
    if not lowered_title:
        return False
    patterns = (
        r"\bcomplete\b",
        r"\bcollection\b",
        r"\bbatch\b",
        r"\bpack\b",
        r"\b全集\b",
        r"\b合集\b",
        r"\b全季\b",
        r"\b打包\b",
        r"\bseason\s*\d+\b",
        r"\bs\d{1,2}\b(?!\s*e\d{1,3})",
        r"\be\d{1,3}\s*-\s*e?\d{1,3}\b",
        r"\b\d{1,3}\s*-\s*\d{1,3}\b",
    )
    return any(re.search(pattern, lowered_title) is not None for pattern in patterns)


def _quality_rank(title: str) -> int:
    lowered_title = title.strip().lower()
    if not lowered_title:
        return 0
    if re.search(r"\b(2160p|4k)\b", lowered_title):
        return 4
    if re.search(r"\b1080p\b", lowered_title):
        return 3
    if re.search(r"\b720p\b", lowered_title):
        return 2
    if re.search(r"\b480p\b", lowered_title):
        return 1
    return 0


def _safe_int(value: Any) -> int:
    try:
        resolved = int(value)
    except (TypeError, ValueError):
        return 0
    if resolved > 0:
        return resolved
    return 0

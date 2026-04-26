from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.search_title_normalization import compact_match_key, normalize_match_key
from app.services.adult_content import AdultContentMatch, extract_exact_adult_content_match

_SOURCE_PRIORITY = {
    "tokyotosho": 4.0,
    "sukebei": 3.5,
    "javbus": 3.0,
    "prowlarr": 1.0,
}
_SOURCE_PRIORITY_ALIASES = {
    "offkab": "sukebei",
    "sukebei.nyaa.si": "sukebei",
    "nyaa.si": "sukebei",
    "tokyotosho.info": "tokyotosho",
    "www.tokyotosho.info": "tokyotosho",
    "javbus.com": "javbus",
    "www.javbus.com": "javbus",
    "javlibrary.com": "javlibrary",
    "www.javlibrary.com": "javlibrary",
}
_TITLE_RELEVANCE_NOISE_TOKENS = frozenset(
    {
        "jav",
        "fc2",
        "ppv",
        "sample",
        "sub",
        "subtitle",
        "subbed",
        "uncensored",
        "censored",
        "中字",
        "字幕",
        "中文字幕",
        "中文",
        "无码",
        "有码",
        "流出",
        "破解",
        "合集",
        "complete",
        "edition",
    }
)


def order_adult_bt_candidates(
    results: Sequence[Mapping[str, Any]],
    *,
    query: str,
) -> list[dict[str, Any]]:
    query_match = extract_exact_adult_content_match(query)
    annotated_results = [_to_candidate_dict(item) for item in results]
    ranked = sorted(
        annotated_results,
        key=lambda item: _candidate_sort_key(item, query_match=query_match, query=query),
        reverse=True,
    )
    return ranked


def build_adult_history_text(*, status: str, archive_path: str) -> str:
    if status == "pending":
        return "历史: 该番号已有待确认下载记录。"
    if status == "downloading":
        return "历史: 该番号已有下载任务在运行。"
    if status == "archived_present":
        if archive_path:
            return f"历史: 该番号已归档保留：{archive_path}"
        return "历史: 该番号已归档保留。"
    if status == "archived_deleted":
        if archive_path:
            return f"历史: 该番号曾归档，当前源资源已清理：{archive_path}"
        return "历史: 该番号曾归档，当前源资源已清理。"
    return ""


def _candidate_sort_key(
    item: Mapping[str, Any],
    *,
    query_match: AdultContentMatch | None,
    query: str,
) -> tuple[float, float, float, float, float, str]:
    candidate_match = _resolve_candidate_match(item)
    exact_id_score = 1.0 if _content_id_matches(candidate_match, query_match=query_match) else 0.0
    title_relevance_score = _resolve_title_relevance_score(item, query=query)
    source_priority = _resolve_source_priority(item)
    seeders = float(_safe_int(item.get("seeders")))
    size_bytes = float(_safe_int(item.get("size")))
    return (
        exact_id_score,
        title_relevance_score,
        source_priority,
        seeders,
        size_bytes,
        str(item.get("title", "")).strip().lower(),
    )


def _resolve_candidate_match(item: Mapping[str, Any]) -> AdultContentMatch | None:
    raw_match = item.get("adult_content_match")
    if isinstance(raw_match, AdultContentMatch):
        return raw_match
    return extract_exact_adult_content_match(
        str(item.get("title", "")).strip(),
        source_site=str(item.get("sourceProvider", "")).strip() or str(item.get("indexerName", "")).strip(),
    )


def _content_id_matches(candidate_match: AdultContentMatch | None, *, query_match: AdultContentMatch | None) -> bool:
    if candidate_match is None or query_match is None:
        return False
    return candidate_match.normalized_content_id == query_match.normalized_content_id


def _resolve_source_priority(item: Mapping[str, Any]) -> float:
    source_provider = _canonicalize_source_name(str(item.get("sourceProvider", "")).strip())
    indexer_name = _canonicalize_source_name(str(item.get("indexerName", "")).strip())
    if source_provider in _SOURCE_PRIORITY:
        return _SOURCE_PRIORITY[source_provider]
    if indexer_name in _SOURCE_PRIORITY:
        return _SOURCE_PRIORITY[indexer_name]
    return 0.0


def _to_candidate_dict(item: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): value for key, value in item.items()}


def _safe_int(value: Any) -> int:
    try:
        resolved = int(value)
    except (TypeError, ValueError):
        return 0
    if resolved > 0:
        return resolved
    return 0


def _canonicalize_source_name(value: str) -> str:
    cleaned = value.strip().lower()
    if not cleaned:
        return ""
    return _SOURCE_PRIORITY_ALIASES.get(cleaned, cleaned)


def _resolve_title_relevance_score(item: Mapping[str, Any], *, query: str) -> float:
    query_tokens = _extract_relevance_tokens(query)
    if not query_tokens:
        return 0.0

    title = str(item.get("title", "")).strip()
    title_tokens = _extract_relevance_tokens(title)
    if not title_tokens:
        return 0.0

    overlap = len(query_tokens.intersection(title_tokens))
    if overlap <= 0:
        return 0.0

    query_compact = compact_match_key(normalize_match_key(query))
    title_compact = compact_match_key(normalize_match_key(title))
    if query_compact and title_compact and query_compact in title_compact:
        return float(overlap + len(query_tokens))
    return float(overlap)


def _extract_relevance_tokens(value: str) -> set[str]:
    normalized = normalize_match_key(value)
    if not normalized:
        return set()
    tokens: set[str] = set()
    for token in normalized.split():
        if token in _TITLE_RELEVANCE_NOISE_TOKENS:
            continue
        if len(token) <= 1:
            continue
        tokens.add(token)
    return tokens

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.services.adult_content import AdultContentMatch, extract_adult_content_match

_SOURCE_PRIORITY = {
    "tokyotosho": 4.0,
    "sukebei": 3.5,
    "javbus": 3.0,
    "prowlarr": 1.0,
}


def order_adult_bt_candidates(
    results: Sequence[Mapping[str, Any]],
    *,
    query: str,
) -> list[dict[str, Any]]:
    query_match = extract_adult_content_match(query)
    annotated_results = [_to_candidate_dict(item) for item in results]
    ranked = sorted(
        annotated_results,
        key=lambda item: _candidate_sort_key(item, query_match=query_match),
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
) -> tuple[float, float, float, float, str]:
    candidate_match = _resolve_candidate_match(item)
    exact_id_score = 1.0 if _content_id_matches(candidate_match, query_match=query_match) else 0.0
    source_priority = _resolve_source_priority(item)
    seeders = float(_safe_int(item.get("seeders")))
    size_bytes = float(_safe_int(item.get("size")))
    return (exact_id_score, source_priority, seeders, size_bytes, str(item.get("title", "")).strip().lower())


def _resolve_candidate_match(item: Mapping[str, Any]) -> AdultContentMatch | None:
    raw_match = item.get("adult_content_match")
    if isinstance(raw_match, AdultContentMatch):
        return raw_match
    return extract_adult_content_match(
        str(item.get("title", "")).strip(),
        source_site=str(item.get("sourceProvider", "")).strip() or str(item.get("indexerName", "")).strip(),
    )


def _content_id_matches(candidate_match: AdultContentMatch | None, *, query_match: AdultContentMatch | None) -> bool:
    if candidate_match is None or query_match is None:
        return False
    return candidate_match.normalized_content_id == query_match.normalized_content_id


def _resolve_source_priority(item: Mapping[str, Any]) -> float:
    source_provider = str(item.get("sourceProvider", "")).strip().lower()
    indexer_name = str(item.get("indexerName", "")).strip().lower()
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

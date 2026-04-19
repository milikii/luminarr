from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.services.bt_candidate_scorer import BTCandidate, BTScoringContext, load_bt_scoring_rules, pick_best
from app.services.bt_sources import resolve_bt_source

DEFAULT_BT_BATCH_PREVIEW_LIMIT = 5


@dataclass(frozen=True, slots=True)
class BTBatchPreviewRequest:
    query: str
    selected_indexes: tuple[int, ...] = ()
    selection_text: str = ""
    invalid_selection: bool = False


@dataclass(frozen=True, slots=True)
class BTBatchPreviewSelectionResult:
    candidates: tuple[Mapping[str, Any], ...]
    available_count: int
    selected_indexes: tuple[int, ...]
    out_of_range: bool = False


def extract_bt_search_query(text: str) -> str:
    cleaned_text = text.strip()
    if not cleaned_text or cleaned_text.lower().startswith("magnet:?"):
        return ""

    matched = re.match(r"^(?i:(下载这个|下载此))\s*(?i:(bt种子|bt|磁力))\s+(.+)$", cleaned_text)
    if matched is None:
        return ""
    return str(matched.group(3) or "").strip()


def extract_bt_batch_preview_request(text: str) -> BTBatchPreviewRequest | None:
    cleaned_text = re.sub(r"\s+", " ", text.strip())
    if not cleaned_text:
        return None

    lowered_text = cleaned_text.lower()
    for prefix in ("bt批量 ", "bt batch "):
        if lowered_text.startswith(prefix):
            body = cleaned_text[len(prefix) :].strip()
            return _build_bt_batch_preview_request(body)
    return None


def select_batch_preview_candidates(
    results: Sequence[Mapping[str, Any]],
    *,
    request: BTBatchPreviewRequest,
    default_limit: int = DEFAULT_BT_BATCH_PREVIEW_LIMIT,
) -> BTBatchPreviewSelectionResult:
    deduplicated_results = _deduplicate_batch_preview_results(results)
    if not deduplicated_results:
        return BTBatchPreviewSelectionResult(candidates=(), available_count=0, selected_indexes=())

    if request.selected_indexes:
        if any(index > len(deduplicated_results) for index in request.selected_indexes):
            return BTBatchPreviewSelectionResult(
                candidates=(),
                available_count=len(deduplicated_results),
                selected_indexes=request.selected_indexes,
                out_of_range=True,
            )
        selected_candidates = tuple(deduplicated_results[index - 1] for index in request.selected_indexes)
        return BTBatchPreviewSelectionResult(
            candidates=selected_candidates,
            available_count=len(deduplicated_results),
            selected_indexes=request.selected_indexes,
        )

    limited_candidates = tuple(deduplicated_results[: max(1, default_limit)])
    return BTBatchPreviewSelectionResult(
        candidates=limited_candidates,
        available_count=len(deduplicated_results),
        selected_indexes=tuple(range(1, len(limited_candidates) + 1)),
    )


def pick_single_item_candidate(
    results: Sequence[Mapping[str, Any]],
    *,
    query: str,
) -> Mapping[str, Any] | None:
    candidate_pairs: list[tuple[BTCandidate, Mapping[str, Any]]] = []
    for result in results:
        candidate = _build_bt_candidate(result)
        if candidate is not None:
            candidate_pairs.append((candidate, result))

    if not candidate_pairs:
        return None

    best = pick_best(
        [candidate for candidate, _ in candidate_pairs],
        BTScoringContext(query=query, media_kind="raw_bt", single_item_mode=True),
        rules=load_bt_scoring_rules(),
    )
    if best is None:
        return None
    for candidate, result in candidate_pairs:
        if candidate is best.candidate:
            return result
    return None


def _resolve_candidate_source(candidate: Mapping[str, Any]) -> str:
    return resolve_bt_source(candidate)


def _build_bt_batch_preview_request(body: str) -> BTBatchPreviewRequest:
    cleaned_body = body.strip()
    if not cleaned_body:
        return BTBatchPreviewRequest(query="")

    query_text = cleaned_body
    selection_text = ""
    if " " in cleaned_body:
        candidate_query, candidate_selection = cleaned_body.rsplit(" ", 1)
        if _looks_like_bt_batch_selection(candidate_selection):
            query_text = candidate_query.strip()
            selection_text = candidate_selection.strip()

    if not selection_text:
        return BTBatchPreviewRequest(query=query_text)

    selected_indexes = _parse_bt_batch_selection(selection_text)
    if selected_indexes is None:
        return BTBatchPreviewRequest(
            query=query_text,
            selection_text=selection_text,
            invalid_selection=True,
        )
    return BTBatchPreviewRequest(
        query=query_text,
        selected_indexes=selected_indexes,
        selection_text=selection_text,
    )


def _looks_like_bt_batch_selection(text: str) -> bool:
    cleaned_text = text.strip()
    if not cleaned_text:
        return False
    if "-" not in cleaned_text and "," not in cleaned_text:
        return False
    return all(character.isdigit() or character in {",", "-"} for character in cleaned_text)


def _parse_bt_batch_selection(selection_text: str) -> tuple[int, ...] | None:
    selected_indexes: list[int] = []
    seen_indexes: set[int] = set()
    for segment in selection_text.split(","):
        cleaned_segment = segment.strip()
        if not cleaned_segment:
            return None
        if "-" in cleaned_segment:
            start_text, end_text = cleaned_segment.split("-", 1)
            if not start_text or not end_text:
                return None
            try:
                start = int(start_text)
                end = int(end_text)
            except ValueError:
                return None
            if start < 1 or end < start:
                return None
            for index in range(start, end + 1):
                if index not in seen_indexes:
                    seen_indexes.add(index)
                    selected_indexes.append(index)
            continue
        try:
            index = int(cleaned_segment)
        except ValueError:
            return None
        if index < 1:
            return None
        if index not in seen_indexes:
            seen_indexes.add(index)
            selected_indexes.append(index)
    return tuple(selected_indexes) or None


def _deduplicate_batch_preview_results(results: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    deduplicated_results: list[Mapping[str, Any]] = []
    seen_sources: set[str] = set()
    for result in results:
        source = _resolve_candidate_source(result)
        title = str(result.get("title", "")).strip()
        if not source or not title or source in seen_sources:
            continue
        seen_sources.add(source)
        deduplicated_results.append(result)
    return deduplicated_results


def _build_bt_candidate(result: Mapping[str, Any]) -> BTCandidate | None:
    source = _resolve_candidate_source(result)
    title = str(result.get("title", "")).strip()
    if not source or not title:
        return None
    return BTCandidate(
        source_site=str(result.get("indexerName", "")).strip() or str(result.get("sourceProvider", "")).strip() or "unknown",
        title=title,
        magnet_or_torrent_url=source,
        size_bytes=_safe_optional_int(result.get("size")),
        seeders=_safe_optional_int(result.get("seeders")),
        leechers=_safe_optional_int(result.get("peers")),
        resolution=_extract_resolution(title),
        codec=_extract_codec(title),
        source_type=_extract_source_type(title),
        audio=(),
        release_group=_extract_release_group(title),
        age_days=None,
        media_kind="raw_bt",
    )


def _extract_resolution(title: str) -> str | None:
    lowered_title = title.lower()
    if re.search(r"\b(2160p|4k)\b", lowered_title):
        return "2160p"
    if re.search(r"\b1080p\b", lowered_title):
        return "1080p"
    if re.search(r"\b720p\b", lowered_title):
        return "720p"
    return None


def _extract_codec(title: str) -> str | None:
    lowered_title = title.lower()
    if re.search(r"\b(x265|hevc)\b", lowered_title):
        return "x265" if "x265" in lowered_title else "HEVC"
    if re.search(r"\b(x264|avc)\b", lowered_title):
        return "x264"
    return None


def _extract_source_type(title: str) -> str | None:
    lowered_title = title.lower()
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

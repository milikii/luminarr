from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from app.services.bt_candidate_scorer import BTCandidate, BTScoringContext, load_bt_scoring_rules, pick_best
from app.services.bt_sources import resolve_bt_source


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

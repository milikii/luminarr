from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.db.bt_subscription_repo import BtSubscriptionItem
from app.services.adult_content import extract_adult_content_match
from app.services.bt_candidate_metadata import (
    extract_codec,
    extract_release_group,
    extract_resolution,
    extract_source_type,
    safe_optional_int,
)
from app.services.bt_candidate_scorer import BTCandidate, BTScoringContext, load_bt_scoring_rules, pick_best
from app.services.bt_sources import resolve_bt_source
from app.services.media_item_display import format_title_year


def pick_subscription_candidate(
    results: Sequence[Mapping[str, Any]],
    *,
    item: BtSubscriptionItem,
    last_seen_source: str,
    last_seen_title: str,
) -> Mapping[str, Any] | None:
    candidate_pairs: list[tuple[BTCandidate, Mapping[str, Any]]] = []
    normalized_last_seen_source = last_seen_source.strip()
    normalized_last_seen_title = _normalize_subscription_seen_title(last_seen_title)
    for result in results:
        source = resolve_candidate_source(result)
        if not source or source == normalized_last_seen_source:
            continue
        title = resolve_candidate_title(result, item=item)
        if normalized_last_seen_title and _normalize_subscription_seen_title(title) == normalized_last_seen_title:
            continue
        candidate = build_subscription_bt_candidate(result, item=item)
        if candidate is not None:
            candidate_pairs.append((candidate, result))
    if not candidate_pairs:
        return None
    best = pick_best(
        [candidate for candidate, _ in candidate_pairs],
        BTScoringContext(query="", media_kind=item.media_kind),
        rules=load_bt_scoring_rules(),
    )
    if best is None:
        return None
    for candidate, result in candidate_pairs:
        if candidate is best.candidate:
            return result
    return None


def resolve_candidate_source(candidate: Mapping[str, Any]) -> str:
    return resolve_bt_source(candidate)


def resolve_candidate_title(candidate: Mapping[str, Any], *, item: BtSubscriptionItem) -> str:
    title = str(candidate.get("title", "")).strip()
    if title:
        return title
    return format_title_year(item.title, item.year)


def build_subscription_bt_candidate(result: Mapping[str, Any], *, item: BtSubscriptionItem) -> BTCandidate | None:
    source = resolve_candidate_source(result)
    title = resolve_candidate_title(result, item=item)
    if not source or not title:
        return None
    if item.media_kind != "adult":
        return None

    subscription_match = extract_adult_content_match(item.title)
    candidate_content_id = str(result.get("adult_content_id", "")).strip().lower()
    if subscription_match is None or not candidate_content_id:
        return None
    if candidate_content_id != subscription_match.normalized_content_id:
        return None

    return BTCandidate(
        source_site=str(result.get("indexerName", "")).strip() or str(result.get("sourceProvider", "")).strip() or "unknown",
        title=title,
        magnet_or_torrent_url=source,
        size_bytes=safe_optional_int(result.get("size")),
        seeders=safe_optional_int(result.get("seeders")),
        leechers=safe_optional_int(result.get("peers")),
        resolution=extract_resolution(title),
        codec=extract_codec(title),
        source_type=extract_source_type(title),
        audio=(),
        release_group=extract_release_group(title),
        age_days=None,
        media_kind=item.media_kind,
    )


def _normalize_subscription_seen_title(title: str) -> str:
    return " ".join(title.strip().casefold().split())

from __future__ import annotations

from app.db.bt_subscription_repo import BtSubscriptionItem
from app.services.bt_subscription_candidate_helpers import (
    build_subscription_bt_candidate,
    extract_codec,
    extract_release_group,
    extract_resolution,
    extract_source_type,
    pick_subscription_candidate,
    resolve_candidate_title,
)


def test_pick_subscription_candidate_skips_last_seen_source() -> None:
    item = _make_bt_subscription_item()
    results = [
        {
            "title": "Frieren S01E01 2160p WEB-DL x265-AAA",
            "downloadUrl": "https://example.com/seen.torrent",
            "seeders": 500,
            "size": 4_000_000_000,
        },
        {
            "title": "Frieren S01E01 1080p WEB-DL x265-BBB",
            "downloadUrl": "https://example.com/new.torrent",
            "seeders": 20,
            "size": 2_000_000_000,
        },
    ]

    selected = pick_subscription_candidate(results, item=item, last_seen_source="https://example.com/seen.torrent")

    assert selected == results[1]


def test_pick_subscription_candidate_prefers_higher_scored_candidate() -> None:
    item = _make_bt_subscription_item()
    results = [
        {
            "title": "Frieren S01E01 CAM",
            "downloadUrl": "https://example.com/cam.torrent",
            "seeders": 500,
            "size": 3_000_000_000,
        },
        {
            "title": "Frieren S01E01 1080p WEB-DL x265-GRP",
            "downloadUrl": "https://example.com/1080p.torrent",
            "seeders": 20,
            "size": 2_200_000_000,
        },
    ]

    selected = pick_subscription_candidate(results, item=item, last_seen_source="")

    assert selected == results[1]


def test_resolve_candidate_title_falls_back_to_subscription_title_year() -> None:
    item = _make_bt_subscription_item(title="葬送的芙莉莲", year="2023")

    assert resolve_candidate_title({}, item=item) == "葬送的芙莉莲 (2023)"


def test_subscription_candidate_helpers_extract_minimal_metadata() -> None:
    item = _make_bt_subscription_item()
    result = {
        "title": "Frieren S01E01 2160p WEB-DL x265-VCB-Studio",
        "downloadUrl": "https://example.com/frieren.torrent",
        "indexerName": "PTP",
        "size": "2147483648",
        "seeders": "12",
        "peers": "7",
    }

    candidate = build_subscription_bt_candidate(result, item=item)

    assert candidate is not None
    assert candidate.resolution == "2160p"
    assert candidate.codec == "x265"
    assert candidate.source_type == "WEB-DL"
    assert candidate.release_group == "VCB-Studio"
    assert candidate.size_bytes == 2147483648
    assert candidate.seeders == 12
    assert candidate.leechers == 7
    assert extract_resolution("Movie 1080p") == "1080p"
    assert extract_codec("Movie HEVC") == "HEVC"
    assert extract_source_type("Movie BluRay") == "BluRay"
    assert extract_release_group("Movie-CHD") == "CHD"


def _make_bt_subscription_item(
    *,
    title: str = "Frieren",
    year: str = "2023",
    media_kind: str = "anime",
) -> BtSubscriptionItem:
    return BtSubscriptionItem(
        item_id=1,
        chat_id=1001,
        title=title,
        year=year,
        media_kind=media_kind,
        last_seen_source="",
        last_seen_title="",
        created_at="2026-04-19 00:00:00",
        updated_at="2026-04-19 00:00:00",
    )

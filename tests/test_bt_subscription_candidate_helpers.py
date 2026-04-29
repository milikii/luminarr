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
        _adult_candidate("SSIS-123 2160p WEB-DL x265-AAA", "https://example.com/seen.torrent", seeders=500, size=4_000_000_000),
        _adult_candidate("SSIS-123 1080p WEB-DL x265-BBB", "https://example.com/new.torrent", seeders=20, size=2_000_000_000),
    ]

    selected = pick_subscription_candidate(
        results,
        item=item,
        last_seen_source="https://example.com/seen.torrent",
        last_seen_title="",
    )

    assert selected == results[1]


def test_pick_subscription_candidate_skips_last_seen_title_from_new_source() -> None:
    item = _make_bt_subscription_item()
    results = [
        _adult_candidate("SSIS-123 1080p WEB-DL x265-AAA", "https://example.com/mirror-1.torrent", seeders=500, size=4_000_000_000),
        _adult_candidate("SSIS-123 720p WEB-DL x265-BBB", "https://example.com/new.torrent", seeders=20, size=2_000_000_000),
    ]

    selected = pick_subscription_candidate(
        results,
        item=item,
        last_seen_source="https://example.com/seen.torrent",
        last_seen_title="SSIS-123 1080p WEB-DL x265-AAA",
    )

    assert selected == results[1]


def test_pick_subscription_candidate_prefers_higher_scored_candidate() -> None:
    item = _make_bt_subscription_item()
    results = [
        _adult_candidate("SSIS-123 CAM", "https://example.com/cam.torrent", seeders=500, size=3_000_000_000),
        _adult_candidate("SSIS-123 1080p WEB-DL x265-GRP", "https://example.com/1080p.torrent", seeders=20, size=2_200_000_000),
    ]

    selected = pick_subscription_candidate(results, item=item, last_seen_source="", last_seen_title="")

    assert selected == results[1]


def test_pick_subscription_candidate_rejects_mismatched_adult_identifier() -> None:
    item = _make_bt_subscription_item()
    results = [
        _adult_candidate("IPX-001 1080p", "https://example.com/ipx-001.torrent", content_id="censored:ipx-001", display_id="IPX-001"),
    ]

    selected = pick_subscription_candidate(results, item=item, last_seen_source="", last_seen_title="")

    assert selected is None


def test_resolve_candidate_title_falls_back_to_subscription_title_year() -> None:
    item = _make_bt_subscription_item(title="SSIS-123", year="")

    assert resolve_candidate_title({}, item=item) == "SSIS-123"


def test_subscription_candidate_helpers_extract_minimal_metadata() -> None:
    item = _make_bt_subscription_item()
    result = _adult_candidate(
        "SSIS-123 2160p WEB-DL x265-VCB-Studio",
        "https://example.com/ssis-123.torrent",
        seeders=12,
        size=2147483648,
    )
    result["indexerName"] = "adult-provider"
    result["peers"] = "7"

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


def test_subscription_candidate_helpers_return_none_for_non_adult_subscription_item() -> None:
    item = _make_bt_subscription_item(media_kind="anime", title="葬送的芙莉莲", year="2023")
    result = _adult_candidate("SSIS-123 2160p WEB-DL x265-VCB-Studio", "https://example.com/ssis-123.torrent")

    candidate = build_subscription_bt_candidate(result, item=item)

    assert candidate is None


def _make_bt_subscription_item(
    *,
    title: str = "SSIS-123",
    year: str = "",
    media_kind: str = "adult",
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


def _adult_candidate(
    title: str,
    download_url: str,
    *,
    seeders: int | None = None,
    size: int | None = None,
    content_id: str = "censored:ssis-123",
    display_id: str = "SSIS-123",
) -> dict[str, object]:
    candidate: dict[str, object] = {
        "title": title,
        "downloadUrl": download_url,
        "adult_content_id": content_id,
        "adult_archive_category": "censored",
        "adult_display_id": display_id,
    }
    if seeders is not None:
        candidate["seeders"] = str(seeders)
    if size is not None:
        candidate["size"] = str(size)
    return candidate

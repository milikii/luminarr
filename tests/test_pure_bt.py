from __future__ import annotations

from app.services.bt_candidate_scorer import BTScoringRules
from app.services.pure_bt import (
    BTBatchPreviewRequest,
    extract_bt_batch_preview_request,
    extract_bt_search_query,
    pick_single_item_candidate,
    select_batch_preview_candidates,
)


def test_extract_bt_search_query_returns_clean_query() -> None:
    assert extract_bt_search_query("下载这个 BT 沙丘 2021") == "沙丘 2021"
    assert extract_bt_search_query("magnet:?xt=urn:btih:abc") == ""


def test_extract_bt_batch_preview_request_parses_query_and_range() -> None:
    request = extract_bt_batch_preview_request("bt批量 Frieren S01E01 1-3")

    assert request == BTBatchPreviewRequest(
        query="Frieren S01E01",
        selected_indexes=(1, 2, 3),
        selection_text="1-3",
    )


def test_extract_bt_batch_preview_request_marks_invalid_selection() -> None:
    request = extract_bt_batch_preview_request("bt batch Frieren 3-1")

    assert request == BTBatchPreviewRequest(
        query="Frieren",
        selection_text="3-1",
        invalid_selection=True,
    )


def test_select_batch_preview_candidates_deduplicates_and_applies_indexes() -> None:
    selection = select_batch_preview_candidates(
        (
            {
                "title": "Frieren S01E01 1080p",
                "source": "magnet:?xt=urn:btih:aaaa",
            },
            {
                "title": "Frieren S01E01 1080p duplicate",
                "source": "magnet:?xt=urn:btih:aaaa",
            },
            {
                "title": "Frieren S01E02 1080p",
                "source": "magnet:?xt=urn:btih:bbbb",
            },
        ),
        request=BTBatchPreviewRequest(query="Frieren", selected_indexes=(2,)),
    )

    assert selection.available_count == 2
    assert selection.selected_indexes == (2,)
    assert not selection.out_of_range
    assert len(selection.candidates) == 1
    assert selection.candidates[0]["title"] == "Frieren S01E02 1080p"


def test_pick_single_item_candidate_uses_shared_scoring_baseline() -> None:
    selected = pick_single_item_candidate(
        (
            {
                "title": "Dune 2021 720p WEBRip x264",
                "downloadUrl": "https://example.com/720p.torrent",
                "seeders": 60,
                "size": 1_500_000_000,
            },
            {
                "title": "Dune 2021 1080p WEB-DL x265-CHD",
                "downloadUrl": "https://example.com/1080p.torrent",
                "seeders": 20,
                "size": 2_000_000_000,
            },
        ),
        query="Dune 2021",
    )

    assert selected is not None
    assert selected["title"] == "Dune 2021 1080p WEB-DL x265-CHD"


def test_pick_single_item_candidate_filters_low_quality_and_collection() -> None:
    selected = pick_single_item_candidate(
        (
            {
                "title": "Frieren S01 Complete 1080p",
                "downloadUrl": "https://example.com/complete.torrent",
                "seeders": 90,
                "size": 9_000_000_000,
            },
            {
                "title": "Frieren S01E01 CAM",
                "downloadUrl": "https://example.com/cam.torrent",
                "seeders": 200,
                "size": 3_000_000_000,
            },
            {
                "title": "Frieren S01E01 1080p WEB-DL",
                "downloadUrl": "https://example.com/e01.torrent",
                "seeders": 10,
                "size": 2_000_000_000,
            },
        ),
        query="Frieren",
    )

    assert selected is not None
    assert selected["title"] == "Frieren S01E01 1080p WEB-DL"


def test_pick_single_item_candidate_returns_none_when_all_results_are_filtered() -> None:
    selected = pick_single_item_candidate(
        (
            {"title": "Frieren S01 Complete 1080p", "downloadUrl": "https://example.com/complete.torrent"},
            {"title": "Frieren S01E01 CAM", "downloadUrl": "https://example.com/cam.torrent"},
        ),
        query="Frieren",
    )

    assert selected is None


def test_pick_single_item_candidate_respects_loaded_rules(monkeypatch) -> None:
    custom_rules = BTScoringRules(
        weights={
            "resolution": 1.0,
            "source_type": 1.0,
            "seeders": 8.0,
            "size_fit": 1.0,
            "codec": 1.0,
            "release_group": 0.0,
        },
        resolution_scores={"2160p": 1.0, "1080p": 0.8, "720p": 0.4, None: 0.2},
        source_type_scores={"Remux": 1.0, "BluRay": 0.9, "BDRip": 0.8, "WEB-DL": 0.7, "WEBRip": 0.5, None: 0.3},
        codec_scores={"x265": 0.9, "HEVC": 0.9, "x264": 0.8, None: 0.4},
        release_group_preferred=("CHD",),
    )
    monkeypatch.setattr("app.services.pure_bt.load_bt_scoring_rules", lambda: custom_rules)

    selected = pick_single_item_candidate(
        (
            {
                "title": "Dune 2021 1080p WEB-DL",
                "downloadUrl": "https://example.com/1080p.torrent",
                "seeders": 3,
                "size": 2_000_000_000,
            },
            {
                "title": "Dune 2021 720p WEBRip",
                "downloadUrl": "https://example.com/720p.torrent",
                "seeders": 80,
                "size": 1_500_000_000,
            },
        ),
        query="Dune 2021",
    )

    assert selected is not None
    assert selected["title"] == "Dune 2021 720p WEBRip"

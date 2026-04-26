from __future__ import annotations

from app.clients.javlibrary_helper import JavLibraryReadOnlyMatch
from app.services.bt_read_only_helper_selection import (
    prepare_bt_read_only_selection_candidates,
    should_apply_bt_read_only_helper,
)


def _build_helper_match(*, title: str = "SSIS-123 Secret Mission Nurse") -> JavLibraryReadOnlyMatch:
    return JavLibraryReadOnlyMatch(
        normalized_content_id="censored:ssis-123",
        display_id="SSIS-123",
        archive_category="censored",
        title=title,
        detail_url="https://www.javlibrary.com/tw/?v=javli0001",
    )


def test_prepare_bt_read_only_selection_candidates_prioritizes_display_id_match() -> None:
    reordered = prepare_bt_read_only_selection_candidates(
        [
            {"title": "Noise collection complete edition"},
            {"title": "SSIS-123 leaked cut"},
            {"title": "Another unrelated compilation"},
        ],
        helper_match=_build_helper_match(),
    )

    assert [item["title"] for item in reordered] == [
        "SSIS-123 leaked cut",
        "Noise collection complete edition",
        "Another unrelated compilation",
    ]


def test_should_apply_bt_read_only_helper_accepts_related_title_overlap() -> None:
    assert should_apply_bt_read_only_helper(
        {"title": "Secret Mission Nurse leaked cut"},
        helper_match=_build_helper_match(),
        candidate_count=2,
    )


def test_should_apply_bt_read_only_helper_rejects_unrelated_candidate_in_multi_result_set() -> None:
    assert not should_apply_bt_read_only_helper(
        {"title": "Unrelated comedy collection"},
        helper_match=_build_helper_match(),
        candidate_count=2,
    )

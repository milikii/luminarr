from __future__ import annotations

from app.bot.query_text_runtime import (
    extract_bt_batch_confirm_request,
    extract_bt_batch_preview_request,
    extract_bt_read_only_query,
    is_bt_direct_intent,
    is_frustration_text,
    parse_bt_classification_choice,
    parse_bt_processing_path_choice,
    parse_bt_processing_path_legacy_shortcut,
)
from app.services.pure_bt import BTBatchConfirmRequest, BTBatchPreviewRequest


def test_is_frustration_text_matches_known_aliases() -> None:
    assert is_frustration_text(" 换 一个 ")
    assert not is_frustration_text("继续")


def test_is_bt_direct_intent_accepts_magnet_and_bt_search_text() -> None:
    assert is_bt_direct_intent("magnet:?xt=urn:btih:abcdef")
    assert is_bt_direct_intent("下载这个 BT 1999")
    assert not is_bt_direct_intent("我想看 dune")


def test_extract_bt_read_only_query_trims_supported_prefixes() -> None:
    assert extract_bt_read_only_query("bt搜  The.Matrix ") == "The.Matrix"
    assert extract_bt_read_only_query("bt search Dune 2021") == "Dune 2021"
    assert extract_bt_read_only_query("status 1") == ""


def test_extract_bt_batch_request_wrappers_delegate_to_pure_bt_parser() -> None:
    preview_request = extract_bt_batch_preview_request("bt批量 Frieren S01E01 1-3")
    confirm_request = extract_bt_batch_confirm_request("bt批量确认 1-3")

    assert preview_request == BTBatchPreviewRequest(
        query="Frieren S01E01",
        selected_indexes=(1, 2, 3),
        selection_text="1-3",
    )
    assert confirm_request == BTBatchConfirmRequest(
        selection_text="1-3",
        selected_indexes=(1, 2, 3),
    )


def test_parse_bt_choices_resolve_supported_aliases() -> None:
    assert parse_bt_classification_choice(" 动漫 ") == "anime"
    assert parse_bt_processing_path_choice(" pure-bt ") == "pure_bt"
    assert parse_bt_processing_path_legacy_shortcut("电视剧") == ("media_import", "series")
    assert parse_bt_processing_path_legacy_shortcut("其他BT") == ("pure_bt", None)

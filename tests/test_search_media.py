from __future__ import annotations

from collections.abc import Awaitable
from pathlib import Path

import pytest

from app.clients.javlibrary_helper import JavLibraryReadOnlyMatch
from app.db.adult_content_registry_repo import AdultContentRegistryRepo
from app.clients.tmdb import TmdbMovie
from app.db.candidate_repo import CandidateMappingRepo
from app.db.clarification_repo import ClarificationPersistenceError, ClarificationRepo
from app.db.sqlite import SqliteDatabase
from app.services.bt_candidate_scorer import BTScoringRules, DEFAULT_BT_SCORING_RULES
from app.services.search_media import (
    BT_BATCH_PREVIEW_EMPTY_QUERY_TEXT,
    BT_BATCH_PREVIEW_INVALID_SELECTION_TEMPLATE,
    BT_BATCH_PREVIEW_NOTICE_TEMPLATE,
    BT_BATCH_PREVIEW_OUT_OF_RANGE_TEMPLATE,
    BT_READ_ONLY_EMPTY_QUERY_TEXT,
    BT_READ_ONLY_NOTICE_TEXT,
    BT_READ_ONLY_NO_RESULT_TEXT_TEMPLATE,
    CANDIDATE_STATE_UNAVAILABLE_TEXT,
    CLARIFICATION_CLEAR_STATE_UNAVAILABLE_TEXT,
    CLARIFICATION_PENDING_STATE_UNAVAILABLE_TEXT,
    EMPTY_QUERY_TEXT,
    NO_RESULT_TEXT_TEMPLATE,
    SearchMediaService,
    parse_movie_query,
)
from app.services.pure_bt import BTBatchPreviewRequest


async def _fake_search_with_results(query: str) -> list[dict[str, object]]:
    assert query == "dune"
    return [
        {
            "title": "Dune: Part Two",
            "year": 2024,
            "quality": "2160p",
            "size": 8 * 1024 * 1024 * 1024,
            "indexer": {"name": "IndexerA"},
        },
        {
            "title": "Dune (2021)",
            "year": 2021,
            "resolution": "1080p",
            "size": 2 * 1024 * 1024 * 1024,
            "indexerName": "IndexerB",
        },
    ]


async def _fake_search_empty(query: str) -> list[dict[str, object]]:
    assert query == "unknown"
    return []


async def _fake_raw_search(query: str) -> list[dict[str, object]]:
    assert query == "dune bt"
    return [
        {
            "title": "Dune 2021 1080p",
            "source": "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12",
            "seeders": 8,
        }
    ]


async def _fake_search_ambiguous(query: str) -> list[dict[str, object]]:
    assert query == "Dune"
    return [
        {"title": "Dune (1984) 1080p BluRay", "year": 1984, "size": 2 * 1024 * 1024 * 1024},
        {"title": "Dune (2000) 1080p WEB-DL", "year": 2000, "size": 3 * 1024 * 1024 * 1024},
        {"title": "Dune (2021) 2160p WEB-DL", "year": 2021, "size": 9 * 1024 * 1024 * 1024},
    ]


def test_search_and_format_with_results() -> None:
    service = SearchMediaService(_fake_search_with_results)
    text = _run(service.search_and_format("dune"))
    assert "电影海报卡片" in text
    assert "片名: dune" in text
    assert "年份: -" in text
    assert "别名: -" in text
    assert "海报: 暂未接入图片" in text
    assert "搜索结果：dune" in text
    assert "1. Dune: Part Two (2024)" in text
    assert "画质: 2160p | 大小: 8.0 GB | 站点: IndexerA" in text
    assert "2. Dune (2021) (2021)" in text
    assert "画质: 1080p | 大小: 2.0 GB | 站点: IndexerB" in text
    assert text.index("电影海报卡片") < text.index("搜索结果：dune")


def test_search_and_format_uses_delivery_renderer_for_personal_wechat_channel() -> None:
    service = SearchMediaService(_fake_search_with_results)

    text = _run(service.search_and_format("dune", chat_id=1001, channel="personal_wechat"))

    assert text.startswith("【搜索：dune】 ✓")
    assert "▸ 电影信息" in text
    assert "▸ 候选结果" in text
    assert "1. Dune: Part Two (2024)" in text
    assert "画质：2160p ｜ 大小：8.0 GB ｜ 站点：IndexerA" in text
    assert "开始下载：发送 select 1" in text


def test_search_and_format_uses_delivery_renderer_for_wecom_channel() -> None:
    service = SearchMediaService(_fake_search_with_results)

    text = _run(service.search_and_format("dune", chat_id=1001, channel="wecom"))

    assert text.startswith("搜索：dune ✓")
    assert "- 电影信息" in text
    assert "- 候选结果" in text
    assert "换关键词：发送 search dune" in text


def test_search_and_format_empty_query() -> None:
    service = SearchMediaService(_fake_search_with_results)
    text = _run(service.search_and_format("   "))
    assert text == EMPTY_QUERY_TEXT


def test_search_and_format_no_result() -> None:
    service = SearchMediaService(_fake_search_empty)
    text = _run(service.search_and_format("unknown"))
    assert text == NO_RESULT_TEXT_TEMPLATE.format(query="unknown")


def test_search_raw_candidates_uses_dedicated_raw_search_func() -> None:
    service = SearchMediaService(_fake_search_with_results, raw_search_func=_fake_raw_search)
    results = _run(service.search_raw_candidates("dune bt"))

    assert len(results) == 1
    assert results[0]["title"] == "Dune 2021 1080p"
    assert results[0]["source"].startswith("magnet:?xt=urn:btih:")


def test_search_bt_read_only_and_format_uses_raw_search_func() -> None:
    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        assert query == "dune bt"
        return [
            {
                "title": "Dune 2021 1080p",
                "source": "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12",
                "infoHash": "abcdef1234567890abcdef1234567890abcdef12",
                "seeders": 8,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    service = SearchMediaService(_fake_search_with_results, raw_search_func=fake_raw_search)
    text = _run(service.search_bt_read_only_and_format("dune bt"))

    assert "BT 只读探索结果：dune bt" in text
    assert "1. Dune 2021 1080p" in text
    assert "站点: Nyaa | 来源入口: nyaa | 做种: 8 | 大小: 2.0 GB" in text
    assert "链接参考: magnet | infoHash=abcdef1234567890abcdef1234567890abcdef12" in text
    assert BT_READ_ONLY_NOTICE_TEXT in text


def test_search_bt_read_only_and_format_empty_query() -> None:
    service = SearchMediaService(_fake_search_with_results, raw_search_func=_fake_raw_search)
    text = _run(service.search_bt_read_only_and_format("   "))

    assert text == BT_READ_ONLY_EMPTY_QUERY_TEXT


def test_search_bt_read_only_and_format_no_result() -> None:
    service = SearchMediaService(_fake_search_with_results, raw_search_func=_fake_search_empty)
    text = _run(service.search_bt_read_only_and_format("unknown"))

    assert text == BT_READ_ONLY_NO_RESULT_TEXT_TEMPLATE.format(query="unknown")


def test_search_bt_read_only_and_format_includes_adult_history_hint(tmp_path: Path) -> None:
    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        assert query == "SSIS-123"
        return [
            {
                "title": "SSIS-123 sample release",
                "source": "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12",
                "infoHash": "abcdef1234567890abcdef1234567890abcdef12",
                "seeders": 8,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "tokyotosho",
                "sourceProvider": "tokyotosho",
            }
        ]

    database = SqliteDatabase(str(tmp_path / "adult.sqlite3"))
    database.initialize()
    registry_repo = AdultContentRegistryRepo(database)
    registry_repo.upsert_pending(
        normalized_content_id="censored:ssis-123",
        content_id_kind="censored",
        archive_category="censored",
        display_title="SSIS-123",
        latest_source_site="tokyotosho",
        task_ref="1",
        task_id="selection:1",
        task_hash="candidate:hash",
        downloader_name="bt",
    )

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=fake_raw_search,
        adult_content_registry_repo=registry_repo,
    )
    text = _run(service.search_bt_read_only_and_format("SSIS-123"))

    assert "番号: SSIS-123 | 分类: censored" in text
    assert "历史: 该番号已有待确认下载记录。" in text


def test_search_bt_read_only_and_format_includes_javlibrary_helper_summary() -> None:
    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        assert query == "SSIS-123"
        return [
            {
                "title": "sample release without explicit id",
                "source": "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12",
                "infoHash": "abcdef1234567890abcdef1234567890abcdef12",
                "seeders": 8,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "tokyotosho",
                "sourceProvider": "tokyotosho",
            }
        ]

    async def fake_helper_lookup(lookup_query: str) -> JavLibraryReadOnlyMatch | None:
        assert lookup_query == "SSIS-123"
        return JavLibraryReadOnlyMatch(
            normalized_content_id="censored:ssis-123",
            display_id="SSIS-123",
            archive_category="censored",
            title="SSIS-123 Sample Title",
            detail_url="https://www.javlibrary.com/tw/?v=javli0001",
        )

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=fake_raw_search,
        adult_read_only_lookup_func=fake_helper_lookup,
    )
    text = _run(service.search_bt_read_only_and_format("SSIS-123"))

    assert "只读补全: javlibrary | 番号: SSIS-123 | 分类: censored" in text
    assert "只读标题: SSIS-123 Sample Title" in text


def test_search_bt_read_only_and_format_uses_javlibrary_helper_for_history_lookup(tmp_path: Path) -> None:
    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        assert query == "SSIS-123"
        return [
            {
                "title": "sample release without explicit id",
                "source": "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12",
                "infoHash": "abcdef1234567890abcdef1234567890abcdef12",
                "seeders": 8,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "tokyotosho",
                "sourceProvider": "tokyotosho",
            }
        ]

    async def fake_helper_lookup(lookup_query: str) -> JavLibraryReadOnlyMatch | None:
        assert lookup_query == "SSIS-123"
        return JavLibraryReadOnlyMatch(
            normalized_content_id="censored:ssis-123",
            display_id="SSIS-123",
            archive_category="censored",
            title="SSIS-123 Sample Title",
            detail_url="https://www.javlibrary.com/tw/?v=javli0001",
        )

    database = SqliteDatabase(str(tmp_path / "adult-helper.sqlite3"))
    database.initialize()
    registry_repo = AdultContentRegistryRepo(database)
    registry_repo.upsert_pending(
        normalized_content_id="censored:ssis-123",
        content_id_kind="censored",
        archive_category="censored",
        display_title="SSIS-123",
        latest_source_site="tokyotosho",
        task_ref="1",
        task_id="selection:1",
        task_hash="candidate:hash",
        downloader_name="bt",
    )

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=fake_raw_search,
        adult_content_registry_repo=registry_repo,
        adult_read_only_lookup_func=fake_helper_lookup,
    )
    text = _run(service.search_bt_read_only_and_format("SSIS-123"))

    assert "只读补全: javlibrary | 番号: SSIS-123 | 分类: censored" in text
    assert "历史: 该番号已有待确认下载记录。" in text


def test_search_bt_read_only_and_format_suppresses_duplicate_history_for_same_content_id(tmp_path: Path) -> None:
    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        assert query == "SSIS-123"
        return [
            {
                "title": "SSIS-123 first release",
                "source": "magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "infoHash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "seeders": 8,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "tokyotosho",
                "sourceProvider": "tokyotosho",
            },
            {
                "title": "SSIS-123 second release",
                "source": "magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "infoHash": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "seeders": 5,
                "size": 1 * 1024 * 1024 * 1024,
                "indexerName": "javbus",
                "sourceProvider": "javbus",
            },
        ]

    database = SqliteDatabase(str(tmp_path / "adult-history.sqlite3"))
    database.initialize()
    registry_repo = AdultContentRegistryRepo(database)
    registry_repo.upsert_pending(
        normalized_content_id="censored:ssis-123",
        content_id_kind="censored",
        archive_category="censored",
        display_title="SSIS-123",
        latest_source_site="tokyotosho",
        task_ref="1",
        task_id="selection:1",
        task_hash="candidate:hash",
        downloader_name="bt",
    )

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=fake_raw_search,
        adult_content_registry_repo=registry_repo,
    )
    text = _run(service.search_bt_read_only_and_format("SSIS-123"))

    assert text.count("历史: 该番号已有待确认下载记录。") == 1


def test_search_bt_read_only_and_format_skips_javlibrary_lookup_when_candidate_already_has_adult_id() -> None:
    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        assert query == "SSIS-123"
        return [
            {
                "title": "SSIS-123 sample release",
                "source": "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12",
                "infoHash": "abcdef1234567890abcdef1234567890abcdef12",
                "seeders": 8,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "tokyotosho",
                "sourceProvider": "tokyotosho",
            }
        ]

    async def fake_helper_lookup(_: str) -> JavLibraryReadOnlyMatch | None:
        raise AssertionError("helper lookup should be skipped when candidate already has adult id")

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=fake_raw_search,
        adult_read_only_lookup_func=fake_helper_lookup,
    )
    text = _run(service.search_bt_read_only_and_format("SSIS-123"))

    assert "番号: SSIS-123 | 分类: censored" in text
    assert "只读补全:" not in text


def test_search_bt_read_only_and_format_keeps_results_when_javlibrary_lookup_fails(
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        assert query == "SSIS-123"
        return [
            {
                "title": "sample release without explicit id",
                "source": "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12",
                "infoHash": "abcdef1234567890abcdef1234567890abcdef12",
                "seeders": 8,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "tokyotosho",
                "sourceProvider": "tokyotosho",
            }
        ]

    async def failing_helper_lookup(_: str) -> JavLibraryReadOnlyMatch | None:
        raise RuntimeError("timeout")

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=fake_raw_search,
        adult_read_only_lookup_func=failing_helper_lookup,
    )
    text = _run(service.search_bt_read_only_and_format("SSIS-123"))
    captured = capsys.readouterr()

    assert "1. sample release without explicit id" in text
    assert "只读补全:" not in text
    assert "[JavLibrary 只读补全失败]" in captured.out
    assert "timeout" in captured.out


def test_search_bt_read_only_and_format_skips_javlibrary_lookup_for_keyword_only_adult_guess() -> None:
    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        assert query == "麻豆 中文字幕 无码流出"
        return [
            {
                "title": "麻豆 中文字幕 无码流出 合集",
                "source": "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12",
                "infoHash": "abcdef1234567890abcdef1234567890abcdef12",
                "seeders": 8,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "tokyotosho",
                "sourceProvider": "tokyotosho",
            }
        ]

    async def fake_helper_lookup(_: str) -> JavLibraryReadOnlyMatch | None:
        raise AssertionError("helper lookup should be skipped when query has no exact adult id")

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=fake_raw_search,
        adult_read_only_lookup_func=fake_helper_lookup,
    )
    text = _run(service.search_bt_read_only_and_format("麻豆 中文字幕 无码流出"))

    assert "麻豆 中文字幕 无码流出 合集" in text
    assert "只读补全:" not in text


def test_search_bt_read_only_and_format_only_applies_helper_to_related_candidates() -> None:
    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        assert query == "SSIS-123"
        return [
            {
                "title": "Secret Mission Nurse complete edition",
                "source": "magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "infoHash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "seeders": 10,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "tokyotosho",
                "sourceProvider": "tokyotosho",
            },
            {
                "title": "Unrelated comedy collection",
                "source": "magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "infoHash": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "seeders": 5,
                "size": 1 * 1024 * 1024 * 1024,
                "indexerName": "tokyotosho",
                "sourceProvider": "tokyotosho",
            },
        ]

    async def fake_helper_lookup(lookup_query: str) -> JavLibraryReadOnlyMatch | None:
        assert lookup_query == "SSIS-123"
        return JavLibraryReadOnlyMatch(
            normalized_content_id="censored:ssis-123",
            display_id="SSIS-123",
            archive_category="censored",
            title="SSIS-123 Secret Mission Nurse",
            detail_url="https://www.javlibrary.com/tw/?v=javli0001",
        )

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=fake_raw_search,
        adult_read_only_lookup_func=fake_helper_lookup,
    )
    text = _run(service.search_bt_read_only_and_format("SSIS-123"))

    first_candidate_text, second_candidate_text = text.split("2. Unrelated comedy collection", 1)
    assert "只读补全: javlibrary | 番号: SSIS-123 | 分类: censored" in first_candidate_text
    assert "只读补全:" not in second_candidate_text


def test_search_bt_read_only_and_format_promotes_helper_related_candidate_before_top_n_slice() -> None:
    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        assert query == "SSIS-123"
        return [
            {
                "title": "Noise collection complete edition",
                "source": "magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "infoHash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "seeders": 999,
                "size": 3 * 1024 * 1024 * 1024,
                "indexerName": "tokyotosho",
                "sourceProvider": "tokyotosho",
            },
            {
                "title": "Another unrelated compilation",
                "source": "magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "infoHash": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "seeders": 888,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "tokyotosho",
                "sourceProvider": "tokyotosho",
            },
            {
                "title": "Secret Mission Nurse leaked cut",
                "source": "magnet:?xt=urn:btih:cccccccccccccccccccccccccccccccccccccccc",
                "infoHash": "cccccccccccccccccccccccccccccccccccccccc",
                "seeders": 1,
                "size": 1 * 1024 * 1024 * 1024,
                "indexerName": "prowlarr",
                "sourceProvider": "prowlarr",
            },
        ]

    async def fake_helper_lookup(lookup_query: str) -> JavLibraryReadOnlyMatch | None:
        assert lookup_query == "SSIS-123"
        return JavLibraryReadOnlyMatch(
            normalized_content_id="censored:ssis-123",
            display_id="SSIS-123",
            archive_category="censored",
            title="SSIS-123 Secret Mission Nurse",
            detail_url="https://www.javlibrary.com/tw/?v=javli0001",
        )

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=fake_raw_search,
        adult_read_only_lookup_func=fake_helper_lookup,
        limit=2,
    )
    text = _run(service.search_bt_read_only_and_format("SSIS-123"))

    assert "1. Secret Mission Nurse leaked cut" in text
    assert "2. Noise collection complete edition" in text
    assert "Another unrelated compilation" not in text
    assert "只读补全: javlibrary | 番号: SSIS-123 | 分类: censored" in text


def test_search_bt_read_only_and_format_suppresses_duplicate_helper_title_variants() -> None:
    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        assert query == "SSIS-123"
        return [
            {
                "title": "Secret-Mission Nurse",
                "source": "magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "infoHash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "seeders": 8,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "tokyotosho",
                "sourceProvider": "tokyotosho",
            }
        ]

    async def fake_helper_lookup(lookup_query: str) -> JavLibraryReadOnlyMatch | None:
        assert lookup_query == "SSIS-123"
        return JavLibraryReadOnlyMatch(
            normalized_content_id="censored:ssis-123",
            display_id="SSIS-123",
            archive_category="censored",
            title="Secret Mission Nurse",
            detail_url="https://www.javlibrary.com/tw/?v=javli0001",
        )

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=fake_raw_search,
        adult_read_only_lookup_func=fake_helper_lookup,
    )
    text = _run(service.search_bt_read_only_and_format("SSIS-123"))

    assert "只读补全: javlibrary | 番号: SSIS-123 | 分类: censored" in text
    assert "只读标题:" not in text


def test_search_bt_batch_preview_and_format_uses_raw_search_func() -> None:
    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        assert query == "dune bt"
        return [
            {
                "title": "Dune 2021 1080p",
                "source": "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12",
                "infoHash": "abcdef1234567890abcdef1234567890abcdef12",
                "seeders": 8,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
            {
                "title": "Dune 2021 720p",
                "source": "magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "seeders": 5,
                "size": 1 * 1024 * 1024 * 1024,
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
        ]

    service = SearchMediaService(_fake_search_with_results, raw_search_func=fake_raw_search)
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(query="dune bt", selected_indexes=(2,), selection_text="2")
        )
    )

    assert "BT 批量预览结果：dune bt" in text
    assert "1. Dune 2021 720p" in text
    assert BT_BATCH_PREVIEW_NOTICE_TEMPLATE.format(selection="2") in text


def test_search_bt_batch_preview_and_format_includes_javlibrary_helper_summary() -> None:
    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        assert query == "SSIS-123"
        return [
            {
                "title": "sample release without explicit id",
                "source": "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12",
                "infoHash": "abcdef1234567890abcdef1234567890abcdef12",
                "seeders": 8,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "tokyotosho",
                "sourceProvider": "tokyotosho",
            }
        ]

    async def fake_helper_lookup(lookup_query: str) -> JavLibraryReadOnlyMatch | None:
        assert lookup_query == "SSIS-123"
        return JavLibraryReadOnlyMatch(
            normalized_content_id="censored:ssis-123",
            display_id="SSIS-123",
            archive_category="censored",
            title="SSIS-123 Sample Title",
            detail_url="https://www.javlibrary.com/tw/?v=javli0001",
        )

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=fake_raw_search,
        adult_read_only_lookup_func=fake_helper_lookup,
    )
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(query="SSIS-123")
        )
    )

    assert "只读补全: javlibrary | 番号: SSIS-123 | 分类: censored" in text
    assert "只读标题: SSIS-123 Sample Title" in text


def test_search_bt_batch_preview_and_format_suppresses_duplicate_history_for_same_content_id(tmp_path: Path) -> None:
    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        assert query == "SSIS-123"
        return [
            {
                "title": "SSIS-123 first release",
                "source": "magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "infoHash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "seeders": 8,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "tokyotosho",
                "sourceProvider": "tokyotosho",
            },
            {
                "title": "SSIS-123 second release",
                "source": "magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "infoHash": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "seeders": 5,
                "size": 1 * 1024 * 1024 * 1024,
                "indexerName": "javbus",
                "sourceProvider": "javbus",
            },
        ]

    database = SqliteDatabase(str(tmp_path / "adult-batch-history.sqlite3"))
    database.initialize()
    registry_repo = AdultContentRegistryRepo(database)
    registry_repo.upsert_pending(
        normalized_content_id="censored:ssis-123",
        content_id_kind="censored",
        archive_category="censored",
        display_title="SSIS-123",
        latest_source_site="tokyotosho",
        task_ref="1",
        task_id="selection:1",
        task_hash="candidate:hash",
        downloader_name="bt",
    )

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=fake_raw_search,
        adult_content_registry_repo=registry_repo,
    )
    text = _run(service.search_bt_batch_preview_and_format(BTBatchPreviewRequest(query="SSIS-123")))

    assert text.count("历史: 该番号已有待确认下载记录。") == 1


def test_search_bt_batch_preview_and_format_uses_page_fetch_for_allowlist_url() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist page preview")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?f=0&c=1_2&u=subsplease"
        return [
            {
                "title": "Frieren S01E01 1080p",
                "source": "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12",
                "seeders": 8,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(
                query="https://nyaa.si/?f=0&c=1_2&u=subsplease",
                selected_indexes=(1,),
                selection_text="1",
            )
        )
    )

    assert "BT 批量预览结果：https://nyaa.si/?f=0&c=1_2&u=subsplease" in text
    assert "1. Frieren S01E01 1080p" in text
    assert BT_BATCH_PREVIEW_NOTICE_TEMPLATE.format(selection="1") in text


def test_search_bt_batch_preview_and_format_uses_page_fetch_for_uncategorized_user_page() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for uncategorized user page preview")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?u=subsplease"
        return [
            {
                "title": "Frieren S01E01 1080p",
                "source": "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12",
                "seeders": 8,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(
                query="https://nyaa.si/?u=subsplease",
                selected_indexes=(1,),
                selection_text="1",
            )
        )
    )

    assert "BT 批量预览结果：https://nyaa.si/?u=subsplease" in text
    assert "1. Frieren S01E01 1080p" in text
    assert BT_BATCH_PREVIEW_NOTICE_TEMPLATE.format(selection="1") in text


def test_search_bt_batch_preview_and_format_uses_page_fetch_for_allowlist_list_page_url() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist list page preview")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?f=0&c=1_2&p=2"
        return [
            {
                "title": "Frieren S01E03 1080p",
                "source": "magnet:?xt=urn:btih:cccccccccccccccccccccccccccccccccccccccc",
                "seeders": 9,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(
                query="https://nyaa.si/?f=0&c=1_2&p=2",
                selected_indexes=(1,),
                selection_text="1",
            )
        )
    )

    assert "BT 批量预览结果：https://nyaa.si/?f=0&c=1_2&p=2" in text
    assert "1. Frieren S01E03 1080p" in text
    assert BT_BATCH_PREVIEW_NOTICE_TEMPLATE.format(selection="1") in text


def test_search_bt_batch_preview_and_format_uses_page_fetch_for_allowlist_home_pagination_url() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist home pagination page preview")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?p=2"
        return [
            {
                "title": "Frieren S01E04 1080p",
                "source": "magnet:?xt=urn:btih:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
                "seeders": 7,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(
                query="https://nyaa.si/?p=2",
                selected_indexes=(1,),
                selection_text="1",
            )
        )
    )

    assert "BT 批量预览结果：https://nyaa.si/?p=2" in text
    assert "1. Frieren S01E04 1080p" in text
    assert BT_BATCH_PREVIEW_NOTICE_TEMPLATE.format(selection="1") in text


def test_search_bt_batch_preview_and_format_uses_page_fetch_for_allowlist_sort_page_url() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist sort page preview")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?s=seeders&o=desc"
        return [
            {
                "title": "Frieren S01E05 1080p",
                "source": "magnet:?xt=urn:btih:ffffffffffffffffffffffffffffffffffffffff",
                "seeders": 16,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(
                query="https://nyaa.si/?s=seeders&o=desc",
                selected_indexes=(1,),
                selection_text="1",
            )
        )
    )

    assert "BT 批量预览结果：https://nyaa.si/?s=seeders&o=desc" in text
    assert "1. Frieren S01E05 1080p" in text
    assert BT_BATCH_PREVIEW_NOTICE_TEMPLATE.format(selection="1") in text


def test_search_bt_batch_preview_and_format_uses_page_fetch_for_allowlist_category_sort_page_url() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist category sort page preview")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?c=1_2&s=seeders&o=desc"
        return [
            {
                "title": "Frieren S01E06 1080p",
                "source": "magnet:?xt=urn:btih:abababababababababababababababababababab",
                "seeders": 17,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(
                query="https://nyaa.si/?c=1_2&s=seeders&o=desc",
                selected_indexes=(1,),
                selection_text="1",
            )
        )
    )

    assert "BT 批量预览结果：https://nyaa.si/?c=1_2&s=seeders&o=desc" in text
    assert "1. Frieren S01E06 1080p" in text
    assert BT_BATCH_PREVIEW_NOTICE_TEMPLATE.format(selection="1") in text


def test_search_bt_batch_preview_and_format_uses_page_fetch_for_page_number_syntax() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist page number syntax")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?f=0&c=1_2&u=subsplease&p=2"
        return [
            {
                "title": "Frieren S01E11 1080p",
                "source": "magnet:?xt=urn:btih:dddddddddddddddddddddddddddddddddddddddd",
                "seeders": 12,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(
                query="https://nyaa.si/?f=0&c=1_2&u=subsplease p=2",
                selected_indexes=(1,),
                selection_text="1",
            )
        )
    )

    assert "BT 批量预览结果：https://nyaa.si/?f=0&c=1_2&u=subsplease p=2" in text
    assert "1. Frieren S01E11 1080p" in text
    assert BT_BATCH_PREVIEW_NOTICE_TEMPLATE.format(selection="1") in text


def test_search_bt_batch_preview_and_format_uses_page_fetch_for_page_number_url() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist page number url")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?f=0&c=1_2&u=subsplease&p=2"
        return [
            {
                "title": "Frieren S01E11 1080p",
                "source": "magnet:?xt=urn:btih:dddddddddddddddddddddddddddddddddddddddd",
                "seeders": 12,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(
                query="https://nyaa.si/?f=0&c=1_2&u=subsplease&p=2",
                selected_indexes=(1,),
                selection_text="1",
            )
        )
    )

    assert "BT 批量预览结果：https://nyaa.si/?f=0&c=1_2&u=subsplease&p=2" in text
    assert "1. Frieren S01E11 1080p" in text
    assert BT_BATCH_PREVIEW_NOTICE_TEMPLATE.format(selection="1") in text


def test_search_bt_batch_preview_and_format_uses_page_fetch_for_uncategorized_user_page_number_syntax() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for uncategorized user page number syntax")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?u=subsplease&p=2"
        return [
            {
                "title": "Frieren S01E11 1080p",
                "source": "magnet:?xt=urn:btih:dddddddddddddddddddddddddddddddddddddddd",
                "seeders": 12,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(
                query="https://nyaa.si/?u=subsplease p=2",
                selected_indexes=(1,),
                selection_text="1",
            )
        )
    )

    assert "BT 批量预览结果：https://nyaa.si/?u=subsplease p=2" in text
    assert "1. Frieren S01E11 1080p" in text
    assert BT_BATCH_PREVIEW_NOTICE_TEMPLATE.format(selection="1") in text


def test_search_bt_batch_preview_and_format_uses_page_fetch_for_uncategorized_user_page_number_url() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for uncategorized user page number url")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?u=subsplease&p=2"
        return [
            {
                "title": "Frieren S01E11 1080p",
                "source": "magnet:?xt=urn:btih:dddddddddddddddddddddddddddddddddddddddd",
                "seeders": 12,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(
                query="https://nyaa.si/?u=subsplease&p=2",
                selected_indexes=(1,),
                selection_text="1",
            )
        )
    )

    assert "BT 批量预览结果：https://nyaa.si/?u=subsplease&p=2" in text
    assert "1. Frieren S01E11 1080p" in text
    assert BT_BATCH_PREVIEW_NOTICE_TEMPLATE.format(selection="1") in text


def test_search_bt_batch_preview_and_format_uses_page_fetch_for_sort_page_number_syntax() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist sort page number syntax")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?s=seeders&o=desc&p=2"
        return [
            {
                "title": "Frieren S01E12 1080p",
                "source": "magnet:?xt=urn:btih:1111111111111111111111111111111111111111",
                "seeders": 18,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(
                query="https://nyaa.si/?s=seeders&o=desc p=2",
                selected_indexes=(1,),
                selection_text="1",
            )
        )
    )

    assert "BT 批量预览结果：https://nyaa.si/?s=seeders&o=desc p=2" in text
    assert "1. Frieren S01E12 1080p" in text
    assert BT_BATCH_PREVIEW_NOTICE_TEMPLATE.format(selection="1") in text


def test_search_bt_batch_preview_and_format_uses_page_fetch_for_sort_page_number_url() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist sort page number url")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?s=seeders&o=desc&p=2"
        return [
            {
                "title": "Frieren S01E13 1080p",
                "source": "magnet:?xt=urn:btih:1313131313131313131313131313131313131313",
                "seeders": 17,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(
                query="https://nyaa.si/?s=seeders&o=desc&p=2",
                selected_indexes=(1,),
                selection_text="1",
            )
        )
    )

    assert "BT 批量预览结果：https://nyaa.si/?s=seeders&o=desc&p=2" in text
    assert "1. Frieren S01E13 1080p" in text
    assert BT_BATCH_PREVIEW_NOTICE_TEMPLATE.format(selection="1") in text


def test_search_bt_batch_preview_and_format_uses_page_fetch_for_category_sort_page_number_syntax() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist category sort page number syntax")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?c=1_2&s=seeders&o=desc&p=2"
        return [
            {
                "title": "Frieren S01E14 1080p",
                "source": "magnet:?xt=urn:btih:1414141414141414141414141414141414141414",
                "seeders": 19,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(
                query="https://nyaa.si/?c=1_2&s=seeders&o=desc p=2",
                selected_indexes=(1,),
                selection_text="1",
            )
        )
    )

    assert "BT 批量预览结果：https://nyaa.si/?c=1_2&s=seeders&o=desc p=2" in text
    assert "1. Frieren S01E14 1080p" in text
    assert BT_BATCH_PREVIEW_NOTICE_TEMPLATE.format(selection="1") in text


def test_search_bt_batch_preview_and_format_uses_page_fetch_for_category_sort_page_number_url() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist category sort page number url")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?c=1_2&s=seeders&o=desc&p=2"
        return [
            {
                "title": "Frieren S01E15 1080p",
                "source": "magnet:?xt=urn:btih:1515151515151515151515151515151515151515",
                "seeders": 20,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(
                query="https://nyaa.si/?c=1_2&s=seeders&o=desc&p=2",
                selected_indexes=(1,),
                selection_text="1",
            )
        )
    )

    assert "BT 批量预览结果：https://nyaa.si/?c=1_2&s=seeders&o=desc&p=2" in text
    assert "1. Frieren S01E15 1080p" in text
    assert BT_BATCH_PREVIEW_NOTICE_TEMPLATE.format(selection="1") in text


def test_search_bt_batch_preview_and_format_uses_page_fetch_for_user_sort_page() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist user sort page")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?f=0&c=1_2&u=subsplease&s=seeders&o=desc"
        return [
            {
                "title": "Frieren S01E16 1080p",
                "source": "magnet:?xt=urn:btih:1616161616161616161616161616161616161616",
                "seeders": 22,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(
                query="https://nyaa.si/?f=0&c=1_2&u=subsplease&s=seeders&o=desc",
                selected_indexes=(1,),
                selection_text="1",
            )
        )
    )

    assert "BT 批量预览结果：https://nyaa.si/?f=0&c=1_2&u=subsplease&s=seeders&o=desc" in text
    assert "1. Frieren S01E16 1080p" in text
    assert BT_BATCH_PREVIEW_NOTICE_TEMPLATE.format(selection="1") in text


def test_search_bt_batch_preview_and_format_uses_page_fetch_for_uncategorized_user_sort_page() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for uncategorized user sort page")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?u=subsplease&s=seeders&o=desc"
        return [
            {
                "title": "Frieren S01E16 1080p",
                "source": "magnet:?xt=urn:btih:1616161616161616161616161616161616161616",
                "seeders": 22,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(
                query="https://nyaa.si/?u=subsplease&s=seeders&o=desc",
                selected_indexes=(1,),
                selection_text="1",
            )
        )
    )

    assert "BT 批量预览结果：https://nyaa.si/?u=subsplease&s=seeders&o=desc" in text
    assert "1. Frieren S01E16 1080p" in text
    assert BT_BATCH_PREVIEW_NOTICE_TEMPLATE.format(selection="1") in text


def test_search_bt_batch_preview_and_format_uses_page_fetch_for_uncategorized_user_sort_page_number_syntax() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for uncategorized user sort page number syntax")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?u=subsplease&s=seeders&o=desc&p=2"
        return [
            {
                "title": "Frieren S01E18 1080p",
                "source": "magnet:?xt=urn:btih:1818181818181818181818181818181818181818",
                "seeders": 24,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(
                query="https://nyaa.si/?u=subsplease&s=seeders&o=desc p=2",
                selected_indexes=(1,),
                selection_text="1",
            )
        )
    )

    assert "BT 批量预览结果：https://nyaa.si/?u=subsplease&s=seeders&o=desc p=2" in text
    assert "1. Frieren S01E18 1080p" in text
    assert BT_BATCH_PREVIEW_NOTICE_TEMPLATE.format(selection="1") in text


def test_search_bt_batch_preview_and_format_uses_page_fetch_for_uncategorized_user_sort_page_number_url() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for uncategorized user sort page number url")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?u=subsplease&s=seeders&o=desc&p=2"
        return [
            {
                "title": "Frieren S01E18 1080p",
                "source": "magnet:?xt=urn:btih:1818181818181818181818181818181818181818",
                "seeders": 24,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(
                query="https://nyaa.si/?u=subsplease&s=seeders&o=desc&p=2",
                selected_indexes=(1,),
                selection_text="1",
            )
        )
    )

    assert "BT 批量预览结果：https://nyaa.si/?u=subsplease&s=seeders&o=desc&p=2" in text
    assert "1. Frieren S01E18 1080p" in text
    assert BT_BATCH_PREVIEW_NOTICE_TEMPLATE.format(selection="1") in text


def test_search_bt_batch_preview_and_format_uses_page_fetch_for_user_sort_page_number_syntax() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist user sort page number syntax")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?f=0&c=1_2&u=subsplease&s=seeders&o=desc&p=2"
        return [
            {
                "title": "Frieren S01E18 1080p",
                "source": "magnet:?xt=urn:btih:1818181818181818181818181818181818181818",
                "seeders": 24,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(
                query="https://nyaa.si/?f=0&c=1_2&u=subsplease&s=seeders&o=desc p=2",
                selected_indexes=(1,),
                selection_text="1",
            )
        )
    )

    assert "BT 批量预览结果：https://nyaa.si/?f=0&c=1_2&u=subsplease&s=seeders&o=desc p=2" in text
    assert "1. Frieren S01E18 1080p" in text
    assert BT_BATCH_PREVIEW_NOTICE_TEMPLATE.format(selection="1") in text


def test_search_bt_batch_preview_and_format_uses_page_fetch_for_user_sort_page_number_url() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist user sort page number url")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?f=0&c=1_2&u=subsplease&s=seeders&o=desc&p=2"
        return [
            {
                "title": "Frieren S01E18 1080p",
                "source": "magnet:?xt=urn:btih:1818181818181818181818181818181818181818",
                "seeders": 24,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(
                query="https://nyaa.si/?f=0&c=1_2&u=subsplease&s=seeders&o=desc&p=2",
                selected_indexes=(1,),
                selection_text="1",
            )
        )
    )

    assert "BT 批量预览结果：https://nyaa.si/?f=0&c=1_2&u=subsplease&s=seeders&o=desc&p=2" in text
    assert "1. Frieren S01E18 1080p" in text
    assert BT_BATCH_PREVIEW_NOTICE_TEMPLATE.format(selection="1") in text


def test_search_bt_batch_preview_and_format_uses_page_fetch_for_search_sort_page() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist search sort page")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?f=0&c=1_2&q=frieren&s=seeders&o=desc"
        return [
            {
                "title": "Frieren S01E20 1080p",
                "source": "magnet:?xt=urn:btih:2020202020202020202020202020202020202020",
                "seeders": 28,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(
                query="https://nyaa.si/?f=0&c=1_2&q=frieren&s=seeders&o=desc",
                selected_indexes=(1,),
                selection_text="1",
            )
        )
    )

    assert "BT 批量预览结果：https://nyaa.si/?f=0&c=1_2&q=frieren&s=seeders&o=desc" in text
    assert "1. Frieren S01E20 1080p" in text
    assert BT_BATCH_PREVIEW_NOTICE_TEMPLATE.format(selection="1") in text


def test_search_bt_batch_preview_and_format_uses_page_fetch_for_search_page_number() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist search page number")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?f=0&c=1_2&q=frieren&p=2"
        return [
            {
                "title": "Frieren S01E24 1080p",
                "source": "magnet:?xt=urn:btih:2424242424242424242424242424242424242424",
                "seeders": 18,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(
                query="https://nyaa.si/?f=0&c=1_2&q=frieren&p=2",
                selected_indexes=(1,),
                selection_text="1",
            )
        )
    )

    assert "BT 批量预览结果：https://nyaa.si/?f=0&c=1_2&q=frieren&p=2" in text
    assert "1. Frieren S01E24 1080p" in text
    assert BT_BATCH_PREVIEW_NOTICE_TEMPLATE.format(selection="1") in text


def test_search_bt_batch_preview_and_format_uses_page_fetch_for_category_search_page_number_url() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist category search page number url")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?c=1_2&q=frieren&p=2"
        return [
            {
                "title": "Frieren S01E24 1080p",
                "source": "magnet:?xt=urn:btih:2424242424242424242424242424242424242424",
                "seeders": 18,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(
                query="https://nyaa.si/?c=1_2&q=frieren&p=2",
                selected_indexes=(1,),
                selection_text="1",
            )
        )
    )

    assert "BT 批量预览结果：https://nyaa.si/?c=1_2&q=frieren&p=2" in text
    assert "1. Frieren S01E24 1080p" in text
    assert BT_BATCH_PREVIEW_NOTICE_TEMPLATE.format(selection="1") in text


def test_search_bt_batch_preview_and_format_uses_page_fetch_for_uncategorized_search_page_number() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist uncategorized search page number")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?q=frieren&p=2"
        return [
            {
                "title": "Frieren S01E24 1080p",
                "source": "magnet:?xt=urn:btih:2424242424242424242424242424242424242424",
                "seeders": 18,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(query="https://nyaa.si/?q=frieren&p=2", selected_indexes=(1,), selection_text="1")
        )
    )

    assert "BT 批量预览结果：https://nyaa.si/?q=frieren&p=2" in text
    assert "1. Frieren S01E24 1080p" in text
    assert BT_BATCH_PREVIEW_NOTICE_TEMPLATE.format(selection="1") in text


def test_search_bt_batch_preview_and_format_uses_page_fetch_for_uncategorized_search_page() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist uncategorized search page")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?q=frieren"
        return [
            {
                "title": "Frieren S01E26 1080p",
                "source": "magnet:?xt=urn:btih:2626262626262626262626262626262626262626",
                "seeders": 16,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(query="https://nyaa.si/?q=frieren", selected_indexes=(1,), selection_text="1")
        )
    )

    assert "BT 批量预览结果：https://nyaa.si/?q=frieren" in text
    assert "1. Frieren S01E26 1080p" in text
    assert BT_BATCH_PREVIEW_NOTICE_TEMPLATE.format(selection="1") in text


def test_search_bt_batch_preview_and_format_uses_page_fetch_for_category_base_page() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist category base page")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?c=1_2"
        return [
            {
                "title": "Frieren S01E28 1080p",
                "source": "magnet:?xt=urn:btih:2828282828282828282828282828282828282828",
                "seeders": 14,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(query="https://nyaa.si/?c=1_2", selected_indexes=(1,), selection_text="1")
        )
    )

    assert "BT 批量预览结果：https://nyaa.si/?c=1_2" in text
    assert "1. Frieren S01E28 1080p" in text
    assert BT_BATCH_PREVIEW_NOTICE_TEMPLATE.format(selection="1") in text


def test_search_bt_batch_preview_and_format_uses_page_fetch_for_category_search_base_page() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist category search base page")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?f=0&c=1_2&q=frieren"
        return [
            {
                "title": "Frieren S01E30 1080p",
                "source": "magnet:?xt=urn:btih:3030303030303030303030303030303030303030",
                "seeders": 12,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(query="https://nyaa.si/?f=0&c=1_2&q=frieren", selected_indexes=(1,), selection_text="1")
        )
    )

    assert "BT 批量预览结果：https://nyaa.si/?f=0&c=1_2&q=frieren" in text
    assert "1. Frieren S01E30 1080p" in text
    assert BT_BATCH_PREVIEW_NOTICE_TEMPLATE.format(selection="1") in text


def test_search_bt_batch_preview_and_format_uses_page_fetch_for_category_search_exact_base_page() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist category search exact base page")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?c=1_2&q=frieren"
        return [
            {
                "title": "Frieren S01E30 1080p",
                "source": "magnet:?xt=urn:btih:3030303030303030303030303030303030303030",
                "seeders": 12,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(query="https://nyaa.si/?c=1_2&q=frieren", selected_indexes=(1,), selection_text="1")
        )
    )

    assert "BT 批量预览结果：https://nyaa.si/?c=1_2&q=frieren" in text
    assert "1. Frieren S01E30 1080p" in text
    assert BT_BATCH_PREVIEW_NOTICE_TEMPLATE.format(selection="1") in text


def test_search_bt_batch_preview_and_format_uses_page_fetch_for_home_base_page() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist home base page")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/"
        return [
            {
                "title": "Frieren S01E32 1080p",
                "source": "magnet:?xt=urn:btih:3232323232323232323232323232323232323232",
                "seeders": 10,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(query="https://nyaa.si/", selected_indexes=(1,), selection_text="1")
        )
    )

    assert "BT 批量预览结果：https://nyaa.si/" in text
    assert "1. Frieren S01E32 1080p" in text
    assert BT_BATCH_PREVIEW_NOTICE_TEMPLATE.format(selection="1") in text


def test_search_bt_batch_preview_and_format_uses_page_fetch_for_search_sort_page_number_syntax() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist search sort page number syntax")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?f=0&c=1_2&q=frieren&s=seeders&o=desc&p=2"
        return [
            {
                "title": "Frieren S01E22 1080p",
                "source": "magnet:?xt=urn:btih:2222222222222222222222222222222222222222",
                "seeders": 32,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(
                query="https://nyaa.si/?f=0&c=1_2&q=frieren&s=seeders&o=desc p=2",
                selected_indexes=(1,),
                selection_text="1",
            )
        )
    )

    assert "BT 批量预览结果：https://nyaa.si/?f=0&c=1_2&q=frieren&s=seeders&o=desc p=2" in text
    assert "1. Frieren S01E22 1080p" in text
    assert BT_BATCH_PREVIEW_NOTICE_TEMPLATE.format(selection="1") in text


def test_search_bt_batch_preview_and_format_uses_page_fetch_for_search_sort_page_number_url() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist search sort page number url")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?f=0&c=1_2&q=frieren&s=seeders&o=desc&p=2"
        return [
            {
                "title": "Frieren S01E23 1080p",
                "source": "magnet:?xt=urn:btih:2323232323232323232323232323232323232323",
                "seeders": 28,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(
                query="https://nyaa.si/?f=0&c=1_2&q=frieren&s=seeders&o=desc&p=2",
                selected_indexes=(1,),
                selection_text="1",
            )
        )
    )

    assert "BT 批量预览结果：https://nyaa.si/?f=0&c=1_2&q=frieren&s=seeders&o=desc&p=2" in text
    assert "1. Frieren S01E23 1080p" in text
    assert BT_BATCH_PREVIEW_NOTICE_TEMPLATE.format(selection="1") in text


def test_search_bt_batch_preview_and_format_rejects_unsupported_page_url() -> None:
    service = SearchMediaService(_fake_search_with_results, raw_search_func=_fake_raw_search)
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(query="https://example.com/list/42", selected_indexes=(1,), selection_text="1")
        )
    )

    assert text == "BT 批量预览暂不支持这个页面：https://example.com/list/42\n请提供当前 allowlist 站点已声明的用户页、列表页或搜索结果页 URL。"


def test_search_bt_batch_preview_and_format_rejects_unsupported_page_number_syntax_url() -> None:
    service = SearchMediaService(_fake_search_with_results, raw_search_func=_fake_raw_search)
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(query="https://example.com/list/42 p=2", selected_indexes=(1,), selection_text="1")
        )
    )

    assert text == "BT 批量预览暂不支持这个页面：https://example.com/list/42 p=2\n请提供当前 allowlist 站点已声明的用户页、列表页或搜索结果页 URL。"


def test_search_bt_batch_preview_and_format_rejects_category_sort_page_missing_order() -> None:
    service = SearchMediaService(_fake_search_with_results, raw_search_func=_fake_raw_search)
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(query="https://nyaa.si/?c=1_2&s=seeders", selected_indexes=(1,), selection_text="1")
        )
    )

    assert text == "BT 批量预览暂不支持这个页面：https://nyaa.si/?c=1_2&s=seeders\n请提供当前 allowlist 站点已声明的用户页、列表页或搜索结果页 URL。"


def test_search_bt_batch_preview_and_format_rejects_user_sort_page_missing_order() -> None:
    service = SearchMediaService(_fake_search_with_results, raw_search_func=_fake_raw_search)
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(
                query="https://nyaa.si/?f=0&c=1_2&u=subsplease&s=seeders",
                selected_indexes=(1,),
                selection_text="1",
            )
        )
    )

    assert text == "BT 批量预览暂不支持这个页面：https://nyaa.si/?f=0&c=1_2&u=subsplease&s=seeders\n请提供当前 allowlist 站点已声明的用户页、列表页或搜索结果页 URL。"


def test_search_bt_batch_preview_and_format_rejects_search_sort_page_missing_order() -> None:
    service = SearchMediaService(_fake_search_with_results, raw_search_func=_fake_raw_search)
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(
                query="https://nyaa.si/?f=0&c=1_2&q=frieren&s=seeders",
                selected_indexes=(1,),
                selection_text="1",
            )
        )
    )

    assert text == "BT 批量预览暂不支持这个页面：https://nyaa.si/?f=0&c=1_2&q=frieren&s=seeders\n请提供当前 allowlist 站点已声明的用户页、列表页或搜索结果页 URL。"


def test_search_bt_batch_preview_and_format_rejects_category_sort_page_number_syntax_missing_order() -> None:
    service = SearchMediaService(_fake_search_with_results, raw_search_func=_fake_raw_search)
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(query="https://nyaa.si/?c=1_2&s=seeders p=2", selected_indexes=(1,), selection_text="1")
        )
    )

    assert text == "BT 批量预览暂不支持这个页面：https://nyaa.si/?c=1_2&s=seeders p=2\n请提供当前 allowlist 站点已声明的用户页、列表页或搜索结果页 URL。"


def test_search_bt_batch_preview_and_format_rejects_user_sort_page_number_syntax_missing_order() -> None:
    service = SearchMediaService(_fake_search_with_results, raw_search_func=_fake_raw_search)
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(
                query="https://nyaa.si/?f=0&c=1_2&u=subsplease&s=seeders p=2",
                selected_indexes=(1,),
                selection_text="1",
            )
        )
    )

    assert text == "BT 批量预览暂不支持这个页面：https://nyaa.si/?f=0&c=1_2&u=subsplease&s=seeders p=2\n请提供当前 allowlist 站点已声明的用户页、列表页或搜索结果页 URL。"


def test_search_bt_batch_preview_and_format_rejects_search_sort_page_number_syntax_missing_order() -> None:
    service = SearchMediaService(_fake_search_with_results, raw_search_func=_fake_raw_search)
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(
                query="https://nyaa.si/?f=0&c=1_2&q=frieren&s=seeders p=2",
                selected_indexes=(1,),
                selection_text="1",
            )
        )
    )

    assert text == "BT 批量预览暂不支持这个页面：https://nyaa.si/?f=0&c=1_2&q=frieren&s=seeders p=2\n请提供当前 allowlist 站点已声明的用户页、列表页或搜索结果页 URL。"


def test_search_bt_batch_preview_and_format_rejects_invalid_selection() -> None:
    service = SearchMediaService(_fake_search_with_results, raw_search_func=_fake_raw_search)
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(query="dune bt", selection_text="3-1", invalid_selection=True)
        )
    )

    assert text == BT_BATCH_PREVIEW_INVALID_SELECTION_TEMPLATE.format(selection="3-1")


def test_search_bt_batch_preview_and_format_rejects_out_of_range_selection() -> None:
    service = SearchMediaService(_fake_search_with_results, raw_search_func=_fake_raw_search)
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(query="dune bt", selected_indexes=(2, 3), selection_text="2-3")
        )
    )

    assert text == BT_BATCH_PREVIEW_OUT_OF_RANGE_TEMPLATE.format(selection="2-3", available_count=1)


def test_search_bt_batch_preview_and_format_empty_query() -> None:
    service = SearchMediaService(_fake_search_with_results, raw_search_func=_fake_raw_search)
    text = _run(service.search_bt_batch_preview_and_format(BTBatchPreviewRequest(query="")))

    assert text == BT_BATCH_PREVIEW_EMPTY_QUERY_TEXT


def test_search_bt_batch_preview_and_format_for_chat_caches_candidates() -> None:
    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        assert query == "dune bt"
        return [
            {
                "title": "Dune 2021 1080p",
                "source": "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12",
            },
            {
                "title": "Dune 2021 720p",
                "source": "magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            },
        ]

    service = SearchMediaService(_fake_search_with_results, raw_search_func=fake_raw_search)
    _run(
        service.search_bt_batch_preview_and_format_for_chat(
            BTBatchPreviewRequest(query="dune bt", selected_indexes=(1, 2), selection_text="1-2"),
            chat_id=1001,
        )
    )

    assert service.get_cached_candidate(1001, 1) is not None
    assert service.get_cached_candidate(1001, 2) is not None


def test_search_bt_batch_preview_and_format_for_chat_does_not_cache_helper_only_fields() -> None:
    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        assert query == "SSIS-123"
        return [
            {
                "title": "sample release without explicit id",
                "source": "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12",
                "infoHash": "abcdef1234567890abcdef1234567890abcdef12",
                "indexerName": "tokyotosho",
                "sourceProvider": "tokyotosho",
            }
        ]

    async def fake_helper_lookup(lookup_query: str) -> JavLibraryReadOnlyMatch | None:
        assert lookup_query == "SSIS-123"
        return JavLibraryReadOnlyMatch(
            normalized_content_id="censored:ssis-123",
            display_id="SSIS-123",
            archive_category="censored",
            title="SSIS-123 Sample Title",
            detail_url="https://www.javlibrary.com/tw/?v=javli0001",
        )

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=fake_raw_search,
        adult_read_only_lookup_func=fake_helper_lookup,
    )
    text = _run(
        service.search_bt_batch_preview_and_format_for_chat(
            BTBatchPreviewRequest(query="SSIS-123"),
            chat_id=1001,
        )
    )

    cached = service.get_cached_candidate(1001, 1)

    assert cached is not None
    assert "只读补全: javlibrary | 番号: SSIS-123 | 分类: censored" in text
    assert "read_only_adult_content_id" not in cached
    assert "read_only_adult_display_id" not in cached
    assert "adult_content_id" not in cached


def test_search_bt_batch_preview_and_format_for_chat_caches_page_preview_candidates() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist page preview")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?f=0&c=1_2&u=subsplease"
        return [
            {
                "title": "Frieren S01E01 1080p",
                "source": "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12",
            },
            {
                "title": "Frieren S01E02 1080p",
                "source": "magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            },
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    _run(
        service.search_bt_batch_preview_and_format_for_chat(
            BTBatchPreviewRequest(
                query="https://nyaa.si/?f=0&c=1_2&u=subsplease",
                selected_indexes=(1, 2),
                selection_text="1-2",
            ),
            chat_id=1001,
        )
    )

    assert service.get_cached_candidate(1001, 1) is not None
    assert service.get_cached_candidate(1001, 2) is not None


def test_search_bt_batch_preview_and_format_for_chat_caches_page_number_url_candidates() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist page number url")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?f=0&c=1_2&u=subsplease&p=2"
        return [
            {
                "title": "Frieren S01E11 1080p",
                "source": "magnet:?xt=urn:btih:dddddddddddddddddddddddddddddddddddddddd",
            },
            {
                "title": "Frieren S01E12 1080p",
                "source": "magnet:?xt=urn:btih:1212121212121212121212121212121212121212",
            },
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    _run(
        service.search_bt_batch_preview_and_format_for_chat(
            BTBatchPreviewRequest(
                query="https://nyaa.si/?f=0&c=1_2&u=subsplease&p=2",
                selected_indexes=(1, 2),
                selection_text="1-2",
            ),
            chat_id=1001,
        )
    )

    assert service.get_cached_candidate(1001, 1) is not None
    assert service.get_cached_candidate(1001, 2) is not None


def test_search_bt_batch_preview_and_format_for_chat_caches_uncategorized_user_page_candidates() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for uncategorized user page preview")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?u=subsplease"
        return [
            {
                "title": "Frieren S01E01 1080p",
                "source": "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12",
            },
            {
                "title": "Frieren S01E02 1080p",
                "source": "magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            },
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    _run(
        service.search_bt_batch_preview_and_format_for_chat(
            BTBatchPreviewRequest(
                query="https://nyaa.si/?u=subsplease",
                selected_indexes=(1, 2),
                selection_text="1-2",
            ),
            chat_id=1001,
        )
    )

    assert service.get_cached_candidate(1001, 1) is not None
    assert service.get_cached_candidate(1001, 2) is not None


def test_search_bt_batch_preview_and_format_for_chat_caches_uncategorized_user_page_number_candidates() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for uncategorized user page number syntax")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?u=subsplease&p=2"
        return [
            {
                "title": "Frieren S01E11 1080p",
                "source": "magnet:?xt=urn:btih:dddddddddddddddddddddddddddddddddddddddd",
            },
            {
                "title": "Frieren S01E12 1080p",
                "source": "magnet:?xt=urn:btih:1212121212121212121212121212121212121212",
            },
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    _run(
        service.search_bt_batch_preview_and_format_for_chat(
            BTBatchPreviewRequest(
                query="https://nyaa.si/?u=subsplease p=2",
                selected_indexes=(1, 2),
                selection_text="1-2",
            ),
            chat_id=1001,
        )
    )

    assert service.get_cached_candidate(1001, 1) is not None
    assert service.get_cached_candidate(1001, 2) is not None


def test_search_bt_batch_preview_and_format_for_chat_caches_uncategorized_user_page_number_url_candidates() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for uncategorized user page number url")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?u=subsplease&p=2"
        return [
            {
                "title": "Frieren S01E11 1080p",
                "source": "magnet:?xt=urn:btih:dddddddddddddddddddddddddddddddddddddddd",
            },
            {
                "title": "Frieren S01E12 1080p",
                "source": "magnet:?xt=urn:btih:1212121212121212121212121212121212121212",
            },
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    _run(
        service.search_bt_batch_preview_and_format_for_chat(
            BTBatchPreviewRequest(
                query="https://nyaa.si/?u=subsplease&p=2",
                selected_indexes=(1, 2),
                selection_text="1-2",
            ),
            chat_id=1001,
        )
    )

    assert service.get_cached_candidate(1001, 1) is not None
    assert service.get_cached_candidate(1001, 2) is not None


def test_search_bt_batch_preview_and_format_for_chat_caches_uncategorized_search_page_candidates() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist uncategorized search page number")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?q=frieren&p=2"
        return [
            {
                "title": "Frieren S01E24 1080p",
                "source": "magnet:?xt=urn:btih:2424242424242424242424242424242424242424",
            },
            {
                "title": "Frieren S01E25 1080p",
                "source": "magnet:?xt=urn:btih:2525252525252525252525252525252525252525",
            },
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    _run(
        service.search_bt_batch_preview_and_format_for_chat(
            BTBatchPreviewRequest(query="https://nyaa.si/?q=frieren&p=2", selected_indexes=(1, 2), selection_text="1-2"),
            chat_id=1001,
        )
    )

    assert service.get_cached_candidate(1001, 1) is not None
    assert service.get_cached_candidate(1001, 2) is not None


def test_search_bt_batch_preview_and_format_for_chat_caches_uncategorized_search_page_base_candidates() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist uncategorized search page")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?q=frieren"
        return [
            {
                "title": "Frieren S01E26 1080p",
                "source": "magnet:?xt=urn:btih:2626262626262626262626262626262626262626",
            },
            {
                "title": "Frieren S01E27 1080p",
                "source": "magnet:?xt=urn:btih:2727272727272727272727272727272727272727",
            },
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    _run(
        service.search_bt_batch_preview_and_format_for_chat(
            BTBatchPreviewRequest(query="https://nyaa.si/?q=frieren", selected_indexes=(1, 2), selection_text="1-2"),
            chat_id=1001,
        )
    )

    assert service.get_cached_candidate(1001, 1) is not None
    assert service.get_cached_candidate(1001, 2) is not None


def test_search_bt_batch_preview_and_format_for_chat_caches_category_base_page_candidates() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist category base page")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?c=1_2"
        return [
            {
                "title": "Frieren S01E28 1080p",
                "source": "magnet:?xt=urn:btih:2828282828282828282828282828282828282828",
            },
            {
                "title": "Frieren S01E29 1080p",
                "source": "magnet:?xt=urn:btih:2929292929292929292929292929292929292929",
            },
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    _run(
        service.search_bt_batch_preview_and_format_for_chat(
            BTBatchPreviewRequest(query="https://nyaa.si/?c=1_2", selected_indexes=(1, 2), selection_text="1-2"),
            chat_id=1001,
        )
    )

    assert service.get_cached_candidate(1001, 1) is not None
    assert service.get_cached_candidate(1001, 2) is not None


def test_search_bt_batch_preview_and_format_for_chat_caches_sort_page_url_candidates() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist sort page url")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?s=seeders&o=desc"
        return [
            {
                "title": "Frieren S01E05 1080p",
                "source": "magnet:?xt=urn:btih:0505050505050505050505050505050505050505",
            },
            {
                "title": "Frieren S01E06 1080p",
                "source": "magnet:?xt=urn:btih:0606060606060606060606060606060606060606",
            },
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    _run(
        service.search_bt_batch_preview_and_format_for_chat(
            BTBatchPreviewRequest(
                query="https://nyaa.si/?s=seeders&o=desc",
                selected_indexes=(1, 2),
                selection_text="1-2",
            ),
            chat_id=1001,
        )
    )

    assert service.get_cached_candidate(1001, 1) is not None
    assert service.get_cached_candidate(1001, 2) is not None


def test_search_bt_batch_preview_and_format_for_chat_caches_uncategorized_user_sort_page_candidates() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for uncategorized user sort page")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?u=subsplease&s=seeders&o=desc"
        return [
            {
                "title": "Frieren S01E16 1080p",
                "source": "magnet:?xt=urn:btih:1616161616161616161616161616161616161616",
            },
            {
                "title": "Frieren S01E17 1080p",
                "source": "magnet:?xt=urn:btih:1717171717171717171717171717171717171717",
            },
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    _run(
        service.search_bt_batch_preview_and_format_for_chat(
            BTBatchPreviewRequest(
                query="https://nyaa.si/?u=subsplease&s=seeders&o=desc",
                selected_indexes=(1, 2),
                selection_text="1-2",
            ),
            chat_id=1001,
        )
    )

    assert service.get_cached_candidate(1001, 1) is not None
    assert service.get_cached_candidate(1001, 2) is not None


def test_search_bt_batch_preview_and_format_for_chat_caches_uncategorized_user_sort_page_number_candidates() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for uncategorized user sort page number syntax")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?u=subsplease&s=seeders&o=desc&p=2"
        return [
            {
                "title": "Frieren S01E18 1080p",
                "source": "magnet:?xt=urn:btih:1818181818181818181818181818181818181818",
            },
            {
                "title": "Frieren S01E19 1080p",
                "source": "magnet:?xt=urn:btih:1919191919191919191919191919191919191919",
            },
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    _run(
        service.search_bt_batch_preview_and_format_for_chat(
            BTBatchPreviewRequest(
                query="https://nyaa.si/?u=subsplease&s=seeders&o=desc p=2",
                selected_indexes=(1, 2),
                selection_text="1-2",
            ),
            chat_id=1001,
        )
    )

    assert service.get_cached_candidate(1001, 1) is not None
    assert service.get_cached_candidate(1001, 2) is not None


def test_search_bt_batch_preview_and_format_for_chat_caches_uncategorized_user_sort_page_number_url_candidates() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for uncategorized user sort page number url")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?u=subsplease&s=seeders&o=desc&p=2"
        return [
            {
                "title": "Frieren S01E18 1080p",
                "source": "magnet:?xt=urn:btih:1818181818181818181818181818181818181818",
            },
            {
                "title": "Frieren S01E19 1080p",
                "source": "magnet:?xt=urn:btih:1919191919191919191919191919191919191919",
            },
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    _run(
        service.search_bt_batch_preview_and_format_for_chat(
            BTBatchPreviewRequest(
                query="https://nyaa.si/?u=subsplease&s=seeders&o=desc&p=2",
                selected_indexes=(1, 2),
                selection_text="1-2",
            ),
            chat_id=1001,
        )
    )

    assert service.get_cached_candidate(1001, 1) is not None
    assert service.get_cached_candidate(1001, 2) is not None


def test_search_bt_batch_preview_and_format_for_chat_caches_user_sort_page_number_url_candidates() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist user sort page number url")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?f=0&c=1_2&u=subsplease&s=seeders&o=desc&p=2"
        return [
            {
                "title": "Frieren S01E18 1080p",
                "source": "magnet:?xt=urn:btih:1818181818181818181818181818181818181818",
            },
            {
                "title": "Frieren S01E19 1080p",
                "source": "magnet:?xt=urn:btih:1919191919191919191919191919191919191919",
            },
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    _run(
        service.search_bt_batch_preview_and_format_for_chat(
            BTBatchPreviewRequest(
                query="https://nyaa.si/?f=0&c=1_2&u=subsplease&s=seeders&o=desc&p=2",
                selected_indexes=(1, 2),
                selection_text="1-2",
            ),
            chat_id=1001,
        )
    )

    assert service.get_cached_candidate(1001, 1) is not None
    assert service.get_cached_candidate(1001, 2) is not None


def test_search_bt_batch_preview_and_format_for_chat_caches_category_search_base_page_candidates() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist category search base page")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?f=0&c=1_2&q=frieren"
        return [
            {
                "title": "Frieren S01E30 1080p",
                "source": "magnet:?xt=urn:btih:3030303030303030303030303030303030303030",
            },
            {
                "title": "Frieren S01E31 1080p",
                "source": "magnet:?xt=urn:btih:3131313131313131313131313131313131313131",
            },
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    _run(
        service.search_bt_batch_preview_and_format_for_chat(
            BTBatchPreviewRequest(
                query="https://nyaa.si/?f=0&c=1_2&q=frieren",
                selected_indexes=(1, 2),
                selection_text="1-2",
            ),
            chat_id=1001,
        )
    )

    assert service.get_cached_candidate(1001, 1) is not None
    assert service.get_cached_candidate(1001, 2) is not None


def test_search_bt_batch_preview_and_format_for_chat_caches_category_search_exact_base_page_candidates() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist category search exact base page")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?c=1_2&q=frieren"
        return [
            {
                "title": "Frieren S01E30 1080p",
                "source": "magnet:?xt=urn:btih:3030303030303030303030303030303030303030",
            },
            {
                "title": "Frieren S01E31 1080p",
                "source": "magnet:?xt=urn:btih:3131313131313131313131313131313131313131",
            },
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    _run(
        service.search_bt_batch_preview_and_format_for_chat(
            BTBatchPreviewRequest(
                query="https://nyaa.si/?c=1_2&q=frieren",
                selected_indexes=(1, 2),
                selection_text="1-2",
            ),
            chat_id=1001,
        )
    )

    assert service.get_cached_candidate(1001, 1) is not None
    assert service.get_cached_candidate(1001, 2) is not None


def test_search_bt_batch_preview_and_format_for_chat_caches_home_base_page_candidates() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist home base page")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/"
        return [
            {
                "title": "Frieren S01E32 1080p",
                "source": "magnet:?xt=urn:btih:3232323232323232323232323232323232323232",
            },
            {
                "title": "Frieren S01E33 1080p",
                "source": "magnet:?xt=urn:btih:3333333333333333333333333333333333333333",
            },
        ]

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
    )
    _run(
        service.search_bt_batch_preview_and_format_for_chat(
            BTBatchPreviewRequest(query="https://nyaa.si/", selected_indexes=(1, 2), selection_text="1-2"),
            chat_id=1001,
        )
    )

    assert service.get_cached_candidate(1001, 1) is not None
    assert service.get_cached_candidate(1001, 2) is not None


def test_search_bt_read_only_and_format_logs_raw_search_failure(capsys) -> None:
    async def fake_raw_search(_: str) -> list[dict[str, object]]:
        raise RuntimeError("bt source unavailable")

    service = SearchMediaService(_fake_search_with_results, raw_search_func=fake_raw_search)

    with pytest.raises(RuntimeError, match="bt source unavailable"):
        _run(service.search_bt_read_only_and_format("dune bt"))

    output = capsys.readouterr().out
    assert "[BT 只读搜索失败]" in output
    assert "query=dune bt" in output


def test_search_and_format_returns_clarification_for_ambiguous_query() -> None:
    service = SearchMediaService(_fake_search_ambiguous)
    text = _run(service.search_and_format("Dune", chat_id=1001))
    assert "片名可能有多个版本：Dune" in text
    assert "只读探索参考：" in text
    assert "- Dune (1984) 1080p BluRay (1984)" in text
    assert service.is_clarification_pending(1001)
    assert service.get_cached_candidate(1001, 1) is None


def test_clarification_pending_persists_for_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()

    before_restart_service = SearchMediaService(
        _fake_search_ambiguous,
        clarification_repo=ClarificationRepo(database),
    )
    _run(before_restart_service.search_and_format("Dune", chat_id=1001))

    after_restart_service = SearchMediaService(
        _fake_search_with_results,
        clarification_repo=ClarificationRepo(SqliteDatabase(str(db_path))),
    )
    assert after_restart_service.is_clarification_pending(1001)
    assert after_restart_service.clear_clarification_pending(1001)
    assert not after_restart_service.is_clarification_pending(1001)


def test_search_success_clears_persisted_clarification_pending(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()
    repo = ClarificationRepo(database)

    pending_service = SearchMediaService(_fake_search_empty, clarification_repo=repo)
    _run(pending_service.search_and_format("unknown", chat_id=1001))

    clear_service = SearchMediaService(
        _fake_search_with_results,
        clarification_repo=ClarificationRepo(SqliteDatabase(str(db_path))),
    )
    _run(clear_service.search_and_format("dune", chat_id=1001))

    verify_service = SearchMediaService(
        _fake_search_with_results,
        clarification_repo=ClarificationRepo(SqliteDatabase(str(db_path))),
    )
    assert not verify_service.is_clarification_pending(1001)


def test_search_success_returns_state_unavailable_when_clarification_clear_fails(tmp_path: Path, capsys) -> None:
    class ClearFailsClarificationRepo(ClarificationRepo):
        def clear_pending(self, *, chat_id: int) -> bool:
            raise RuntimeError(f"db down for {chat_id}")

    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()
    ClarificationRepo(database).upsert_pending(chat_id=1001, query="unknown")

    service = SearchMediaService(
        _fake_search_with_results,
        clarification_repo=ClearFailsClarificationRepo(SqliteDatabase(str(db_path))),
    )

    text = _run(service.search_and_format("dune", chat_id=1001))

    assert text == CLARIFICATION_CLEAR_STATE_UNAVAILABLE_TEXT
    assert service.get_cached_candidate(1001, 1) is None
    assert service.is_clarification_pending(1001)
    output = capsys.readouterr().out
    assert "[搜索澄清态清理失败]" in output
    assert "db down for 1001" in output


def test_search_clarification_pending_logs_persistence_failure(tmp_path: Path, capsys) -> None:
    class MissingRowClarificationRepo(ClarificationRepo):
        def get_pending_query(self, *, chat_id: int) -> str | None:
            _ = chat_id
            return None

    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    service = SearchMediaService(
        _fake_search_ambiguous,
        clarification_repo=MissingRowClarificationRepo(database),
    )

    text = _run(service.search_and_format("Dune", chat_id=1001))

    assert text == CLARIFICATION_PENDING_STATE_UNAVAILABLE_TEXT
    assert not service.is_clarification_pending(1001)
    output = capsys.readouterr().out
    assert "[搜索澄清态写入后记录缺失]" in output
    assert "[处理建议]" in output
    assert "clarification_state missing after upsert" in output


def test_search_no_result_returns_state_unavailable_when_clarification_persist_fails(tmp_path: Path, capsys) -> None:
    class MissingRowClarificationRepo(ClarificationRepo):
        def get_pending_query(self, *, chat_id: int) -> str | None:
            _ = chat_id
            return None

    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    service = SearchMediaService(
        _fake_search_empty,
        clarification_repo=MissingRowClarificationRepo(database),
    )

    text = _run(service.search_and_format("unknown", chat_id=1001))

    assert text == CLARIFICATION_PENDING_STATE_UNAVAILABLE_TEXT
    assert service.get_cached_candidate(1001, 1) is None
    assert not service.is_clarification_pending(1001)
    output = capsys.readouterr().out
    assert "[搜索澄清态写入后记录缺失]" in output
    assert "[处理建议]" in output
    assert "clarification_state missing after upsert" in output


def test_search_no_result_surfaces_clarification_row_corruption_after_upsert(
    tmp_path: Path,
    capsys,
) -> None:
    class CorruptedRowClarificationRepo(ClarificationRepo):
        def get_pending_query(self, *, chat_id: int) -> str | None:
            _ = chat_id
            raise ClarificationPersistenceError("clarification_state query empty after read")

    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    service = SearchMediaService(
        _fake_search_empty,
        clarification_repo=CorruptedRowClarificationRepo(database),
    )

    text = _run(service.search_and_format("unknown", chat_id=1001))

    assert text == CLARIFICATION_PENDING_STATE_UNAVAILABLE_TEXT
    assert service.get_cached_candidate(1001, 1) is None
    assert not service.is_clarification_pending(1001)
    output = capsys.readouterr().out
    assert "[搜索澄清态写入命中坏记录]" in output
    assert "[处理建议]" in output
    assert "clarification_state query empty after read" in output


def test_search_candidate_persist_logs_missing_count_result(tmp_path: Path, capsys) -> None:
    class MissingCandidateCountRepo(CandidateMappingRepo):
        def _load_candidate_count_row(self, *, chat_id: int):
            _ = chat_id
            return None

    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    service = SearchMediaService(
        _fake_search_with_results,
        candidate_repo=MissingCandidateCountRepo(database),
    )

    text = _run(service.search_and_format("dune", chat_id=1001))

    assert text == CANDIDATE_STATE_UNAVAILABLE_TEXT
    assert service.get_cached_candidate(1001, 1) is None
    output = capsys.readouterr().out
    assert "[搜索候选写入结果缺失]" in output
    assert "[处理建议]" in output
    assert "candidate_mapping count missing after query" in output


def test_search_candidate_persist_logs_count_mismatch_after_save(tmp_path: Path, capsys) -> None:
    class CountMismatchCandidateRepo(CandidateMappingRepo):
        def _count_candidates(self, *, chat_id: int) -> int:
            _ = chat_id
            return 1

    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    service = SearchMediaService(
        _fake_search_with_results,
        candidate_repo=CountMismatchCandidateRepo(database),
    )

    text = _run(service.search_and_format("dune", chat_id=1001))

    assert text == CANDIDATE_STATE_UNAVAILABLE_TEXT
    assert service.get_cached_candidate(1001, 1) is None
    output = capsys.readouterr().out
    assert "[搜索候选写入后记录不一致]" in output
    assert "[处理建议]" in output
    assert "candidate_mapping count mismatch after save" in output


def test_search_candidate_persist_rollback_logs_missing_clear_result(capsys) -> None:
    class RollbackMissingRepo:
        def save_candidates(self, chat_id: int, results) -> None:
            _ = (chat_id, results)
            raise RuntimeError("db down")

        def clear_candidates(self, chat_id: int):
            _ = chat_id
            return None

        def get_candidate(self, chat_id: int, index: int):
            _ = (chat_id, index)
            return None

    service = SearchMediaService(_fake_search_with_results, candidate_repo=RollbackMissingRepo())

    text = _run(service.search_and_format("dune", chat_id=1001))

    assert text == CANDIDATE_STATE_UNAVAILABLE_TEXT
    assert service.get_cached_candidate(1001, 1) is None
    output = capsys.readouterr().out
    assert "[搜索候选持久化失败]" in output
    assert "[搜索候选回滚清理结果缺失]" in output
    assert "candidate clear result missing during persist rollback" in output
    assert "[处理建议]" in output


def test_clear_clarification_pending_logs_persistence_failure(capsys) -> None:
    repo = type("BoomRepo", (), {"clear_pending": lambda self, chat_id: (_ for _ in ()).throw(RuntimeError("db down"))})()
    service = SearchMediaService(_fake_search_with_results, clarification_repo=repo)
    service._clarification_pending_by_chat[1001] = "Dune"
    assert service.clear_clarification_pending(1001) is False
    assert service._clarification_pending_by_chat[1001] == "Dune"
    assert "[搜索澄清态清理失败]" in capsys.readouterr().out


def test_clear_clarification_pending_logs_missing_clear_result(capsys) -> None:
    repo = type("MissingRepo", (), {"clear_pending": lambda self, chat_id: None})()
    service = SearchMediaService(_fake_search_with_results, clarification_repo=repo)
    service._clarification_pending_by_chat[1001] = "Dune"

    assert service.clear_clarification_pending(1001) is False
    assert service._clarification_pending_by_chat[1001] == "Dune"
    output = capsys.readouterr().out
    assert "[搜索澄清态清理结果缺失]" in output
    assert "clarification clear result missing" in output
    assert "[处理建议]" in output


def test_is_clarification_pending_logs_persistence_failure(capsys) -> None:
    repo = type("BoomRepo", (), {"get_pending_query": lambda self, chat_id: (_ for _ in ()).throw(RuntimeError("db down"))})()
    service = SearchMediaService(_fake_search_with_results, clarification_repo=repo)
    assert service.is_clarification_pending(1001) is None
    output = capsys.readouterr().out
    assert "[搜索澄清态读取失败]" in output
    assert "当前相关入口会按状态不可用处理" in output


def test_is_clarification_pending_logs_row_corruption(tmp_path: Path, capsys) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO clarification_state (chat_id, query, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            """,
            (1001, "   "),
        )
        connection.commit()

    service = SearchMediaService(
        _fake_search_with_results,
        clarification_repo=ClarificationRepo(database),
    )

    assert service.is_clarification_pending(1001) is None
    output = capsys.readouterr().out
    assert "[搜索澄清态记录损坏]" in output
    assert "[处理建议]" in output
    assert "clarification_state query empty after read" in output


def test_load_persisted_clarification_query_distinguishes_repo_failure_from_missing_state() -> None:
    missing_repo = type("MissingRepo", (), {"get_pending_query": lambda self, chat_id: None})()
    failed_repo = type("BoomRepo", (), {"get_pending_query": lambda self, chat_id: (_ for _ in ()).throw(RuntimeError("db down"))})()

    missing_service = SearchMediaService(_fake_search_with_results, clarification_repo=missing_repo)
    failed_service = SearchMediaService(_fake_search_with_results, clarification_repo=failed_repo)

    missing_result = missing_service._load_persisted_clarification_query(chat_id=1001)
    failed_result = failed_service._load_persisted_clarification_query(chat_id=1001)

    assert missing_result.query is None
    assert missing_result.load_failed is False
    assert failed_result.query is None
    assert failed_result.load_failed is True


def test_clear_cached_candidates_logs_candidate_persistence_failure(capsys) -> None:
    repo = type("BoomRepo", (), {"clear_candidates": lambda self, chat_id: (_ for _ in ()).throw(RuntimeError("db down"))})()
    service = SearchMediaService(_fake_search_with_results, candidate_repo=repo)
    service._recent_candidates_by_chat[1001] = [{"title": "Dune"}]

    assert service.clear_cached_candidates(1001) is False
    assert service._recent_candidates_by_chat[1001] == [{"title": "Dune"}]
    assert "[搜索候选清理失败]" in capsys.readouterr().out


def test_clear_cached_candidates_logs_missing_candidate_clear_result(capsys) -> None:
    repo = type("MissingRepo", (), {"clear_candidates": lambda self, chat_id: None})()
    service = SearchMediaService(_fake_search_with_results, candidate_repo=repo)
    service._recent_candidates_by_chat[1001] = [{"title": "Dune"}]

    assert service.clear_cached_candidates(1001) is False
    assert service._recent_candidates_by_chat[1001] == [{"title": "Dune"}]
    output = capsys.readouterr().out
    assert "[搜索候选清理结果缺失]" in output
    assert "candidate clear result missing" in output
    assert "[处理建议]" in output


def test_get_cached_candidate_logs_candidate_payload_corruption(tmp_path: Path, capsys) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO candidate_mapping (
                chat_id,
                selection_index,
                candidate_json,
                updated_at
            ) VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (1001, 1, "{"),
        )
        connection.commit()

    service = SearchMediaService(
        _fake_search_with_results,
        candidate_repo=CandidateMappingRepo(database),
    )

    assert service.get_cached_candidate(1001, 1) is None
    output = capsys.readouterr().out
    assert "[搜索候选载荷损坏]" in output
    assert "当前相关入口会按候选读取失败或状态不可用处理" in output


def test_has_cached_candidates_distinguishes_lookup_failure(capsys) -> None:
    repo = type("BoomRepo", (), {"get_candidate": lambda self, chat_id, index: (_ for _ in ()).throw(RuntimeError("db down"))})()
    service = SearchMediaService(_fake_search_with_results, candidate_repo=repo)

    assert service.has_cached_candidates(1001) is None

    output = capsys.readouterr().out
    assert "[搜索候选读取失败]" in output
    assert "chat_id=1001" in output
    assert "index=1" in output
    assert "[处理建议]" in output
    assert "当前相关入口会按候选读取失败或状态不可用处理" in output


async def _fake_search_quality_from_title(query: str) -> list[dict[str, object]]:
    assert query == "dune"
    return [
        {
            "title": "Dune 1984 1080p AMZN WEB-DL DDP 5.1 H.264-vase",
            "size": 10 * 1024 * 1024 * 1024,
            "indexerName": "BeyondHD",
        }
    ]


def test_search_and_format_guesses_quality_from_title() -> None:
    service = SearchMediaService(_fake_search_quality_from_title)
    text = _run(service.search_and_format("dune"))
    assert "画质: 1080p WEB-DL" in text


def test_search_and_format_orders_media_bt_candidates_with_shared_scorer(
    tmp_path: Path,
    monkeypatch,
) -> None:
    async def fake_search(query: str) -> list[dict[str, object]]:
        assert query == "Dune 2021"
        return [
            {
                "title": "Dune 2021 1080p WEB-DL",
                "year": 2021,
                "size": 3 * 1024 * 1024 * 1024,
                "seeders": 20,
                "downloadUrl": "https://example.com/dune-1080p.torrent",
                "indexerName": "IndexerA",
            },
            {
                "title": "Dune 2021 720p WEB-DL",
                "year": 2021,
                "size": 2 * 1024 * 1024 * 1024,
                "seeders": 20,
                "downloadUrl": "https://example.com/dune-720p.torrent",
                "indexerName": "IndexerB",
            },
        ]

    custom_rules = BTScoringRules(
        weights=dict(DEFAULT_BT_SCORING_RULES.weights),
        resolution_scores={
            "2160p": 0.0,
            "1080p": 0.1,
            "720p": 1.0,
            None: 0.0,
        },
        source_type_scores=dict(DEFAULT_BT_SCORING_RULES.source_type_scores),
        codec_scores=dict(DEFAULT_BT_SCORING_RULES.codec_scores),
        release_group_preferred=DEFAULT_BT_SCORING_RULES.release_group_preferred,
    )
    monkeypatch.setattr("app.services.search_media.load_bt_scoring_rules", lambda: custom_rules)

    _ = tmp_path
    service = SearchMediaService(fake_search)

    text = _run(service.search_and_format("Dune 2021", chat_id=1001))

    assert "1. Dune 2021 720p WEB-DL (2021)" in text
    assert "2. Dune 2021 1080p WEB-DL (2021)" in text
    cached_first = service.get_cached_candidate(1001, 1)
    assert cached_first is not None
    assert cached_first["downloadUrl"] == "https://example.com/dune-720p.torrent"


def test_search_and_format_derives_english_fallback_query_for_movie_title_ranking() -> None:
    async def fake_search(query: str) -> list[dict[str, object]]:
        assert query == "Devil in Dune 2021"
        return [
            {
                "title": "Dune: Part One 2021 2160p BluRay",
                "year": 2021,
                "size": 90 * 1024 * 1024 * 1024,
                "seeders": 5,
                "downloadUrl": "https://example.com/dune-part-one.torrent",
                "indexerName": "IndexerA",
            },
            {
                "title": "Dune 2021 1080p WEB-DL",
                "year": 2021,
                "size": 10 * 1024 * 1024 * 1024,
                "seeders": 5,
                "downloadUrl": "https://example.com/dune.torrent",
                "indexerName": "IndexerB",
            },
        ]

    async def fake_tmdb_lookup(_: str, __: str) -> TmdbMovie | None:
        return TmdbMovie(title="Devil in Dune", original_title="沙丘虫暴", year="2021")

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("沙丘 2021", chat_id=1001))

    assert "1. Dune 2021 1080p WEB-DL (2021)" in text
    assert "2. Dune: Part One 2021 2160p BluRay (2021)" in text


def test_search_and_format_derives_fallback_query_with_noisy_outlier_result() -> None:
    async def fake_search(query: str) -> list[dict[str, object]]:
        assert query == "Devil in Dune 2021"
        return [
            {
                "title": "Random Movie 2021 1080p WEB-DL",
                "year": 2021,
                "size": 2 * 1024 * 1024 * 1024,
                "seeders": 50,
                "downloadUrl": "https://example.com/random.torrent",
                "indexerName": "IndexerZ",
            },
            {
                "title": "Dune 2021 1080p WEB-DL",
                "year": 2021,
                "size": 10 * 1024 * 1024 * 1024,
                "seeders": 5,
                "downloadUrl": "https://example.com/dune.torrent",
                "indexerName": "IndexerB",
            },
            {
                "title": "Dune: Part One 2021 2160p BluRay",
                "year": 2021,
                "size": 90 * 1024 * 1024 * 1024,
                "seeders": 5,
                "downloadUrl": "https://example.com/dune-part-one.torrent",
                "indexerName": "IndexerA",
            },
        ]

    async def fake_tmdb_lookup(_: str, __: str) -> TmdbMovie | None:
        return TmdbMovie(title="Devil in Dune", original_title="沙丘虫暴", year="2021")

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("沙丘 2021", chat_id=1001))

    assert "1. Dune 2021 1080p WEB-DL (2021)" in text
    assert "2. Dune: Part One 2021 2160p BluRay (2021)" in text
    assert "Random Movie 2021 1080p WEB-DL (2021)" not in text


def test_search_and_format_derives_fallback_query_from_single_related_result() -> None:
    async def fake_search(query: str) -> list[dict[str, object]]:
        assert query == "Devil in Dune 2021"
        return [
            {
                "title": "Dune 2021 1080p WEB-DL",
                "year": 2021,
                "size": 10 * 1024 * 1024 * 1024,
                "seeders": 5,
                "downloadUrl": "https://example.com/dune.torrent",
                "indexerName": "IndexerB",
            }
        ]

    async def fake_tmdb_lookup(_: str, __: str) -> TmdbMovie | None:
        return TmdbMovie(title="Devil in Dune", original_title="沙丘虫暴", year="2021")

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("沙丘 2021", chat_id=1001))

    assert "1. Dune 2021 1080p WEB-DL (2021)" in text


def test_search_and_format_derives_fallback_query_from_two_related_results_among_noise() -> None:
    async def fake_search(query: str) -> list[dict[str, object]]:
        assert query == "Devil in Dune 2021"
        return [
            {
                "title": "Random Movie 2021 1080p WEB-DL",
                "year": 2021,
                "size": 2 * 1024 * 1024 * 1024,
                "seeders": 50,
                "downloadUrl": "https://example.com/random-a.torrent",
                "indexerName": "IndexerZ",
            },
            {
                "title": "Another Random Film 2021 1080p WEB-DL",
                "year": 2021,
                "size": 2 * 1024 * 1024 * 1024,
                "seeders": 40,
                "downloadUrl": "https://example.com/random-b.torrent",
                "indexerName": "IndexerY",
            },
            {
                "title": "Dune 2021 1080p WEB-DL",
                "year": 2021,
                "size": 10 * 1024 * 1024 * 1024,
                "seeders": 5,
                "downloadUrl": "https://example.com/dune.torrent",
                "indexerName": "IndexerB",
            },
            {
                "title": "Dune: Part One 2021 2160p BluRay",
                "year": 2021,
                "size": 90 * 1024 * 1024 * 1024,
                "seeders": 5,
                "downloadUrl": "https://example.com/dune-part-one.torrent",
                "indexerName": "IndexerA",
            },
            {
                "title": "Noise Title 2021 720p WEBRip",
                "year": 2021,
                "size": 1 * 1024 * 1024 * 1024,
                "seeders": 80,
                "downloadUrl": "https://example.com/random-c.torrent",
                "indexerName": "IndexerX",
            },
        ]

    async def fake_tmdb_lookup(_: str, __: str) -> TmdbMovie | None:
        return TmdbMovie(title="Devil in Dune", original_title="沙丘虫暴", year="2021")

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("沙丘 2021", chat_id=1001))

    assert "1. Dune 2021 1080p WEB-DL (2021)" in text
    assert "2. Dune: Part One 2021 2160p BluRay (2021)" in text


async def _fake_search_tmdb_hit(query: str) -> list[dict[str, object]]:
    assert query == "Interstellar 2014"
    return [
        {
            "title": "Interstellar 2014 1080p BluRay",
            "year": 2014,
            "size": 2 * 1024 * 1024 * 1024,
            "indexerName": "IndexerA",
        }
    ]


async def _fake_lookup_tmdb_movie(title: str, year: str) -> TmdbMovie | None:
    assert title == "星际穿越"
    assert year == "2014"
    return TmdbMovie(title="Interstellar", original_title="星际穿越", year="2014")


def test_search_and_format_uses_tmdb_first_when_available() -> None:
    service = SearchMediaService(
        _fake_search_tmdb_hit,
        lookup_movie_func=_fake_lookup_tmdb_movie,
    )
    text = _run(service.search_and_format("星际穿越 (2014)"))
    assert "电影海报卡片" in text
    assert "片名: 星际穿越" in text
    assert "年份: 2014" in text
    assert "别名: Interstellar" in text
    assert "搜索结果：星际穿越 (2014)" in text
    assert "Interstellar 2014 1080p BluRay" in text


def test_search_and_format_caches_confirmed_media_identity_for_candidates() -> None:
    service = SearchMediaService(
        _fake_search_tmdb_hit,
        lookup_movie_func=_fake_lookup_tmdb_movie,
    )

    _run(service.search_and_format("星际穿越 (2014)", chat_id=1001))
    candidate = service.get_cached_candidate(1001, 1)

    assert candidate is not None
    assert candidate["media_identity"] == {
        "media_type": "movie",
        "tmdb_id": "",
        "title": "Interstellar",
        "original_title": "星际穿越",
        "year": "2014",
        "source": "search_confirmed",
    }


def test_search_and_format_tmdb_english_hit_stops_before_original() -> None:
    seen_queries: list[str] = []

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        if query == "Interstellar 2014":
            return [
                {
                    "title": "Interstellar 2014 1080p BluRay",
                    "year": 2014,
                    "size": 2 * 1024 * 1024 * 1024,
                    "indexerName": "IndexerA",
                }
            ]
        return []

    async def fake_tmdb_lookup(_: str, __: str) -> TmdbMovie | None:
        return TmdbMovie(title="Interstellar", original_title="星际穿越", year="2014")

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("星际穿越 (2014)"))

    assert seen_queries == ["Interstellar 2014"]
    assert "电影海报卡片" in text
    assert "片名: 星际穿越" in text
    assert "年份: 2014" in text
    assert "别名: Interstellar" in text
    assert "Interstellar 2014 1080p BluRay" in text


def test_search_and_format_fallbacks_to_tmdb_original_when_english_miss() -> None:
    seen_queries: list[str] = []

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        if query == "Interstellar 2014":
            return []
        if query == "星际穿越 2014":
            return [
                {
                    "title": "星际穿越 2014 1080p BluRay",
                    "year": 2014,
                    "size": 2 * 1024 * 1024 * 1024,
                    "indexerName": "IndexerB",
                }
            ]
        return []

    async def fake_tmdb_lookup(_: str, __: str) -> TmdbMovie | None:
        return TmdbMovie(title="Interstellar", original_title="星际穿越", year="2014")

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("星际穿越 (2014)"))

    assert seen_queries == ["Interstellar 2014", "星际穿越 2014"]
    assert "星际穿越 2014 1080p BluRay" in text


def test_search_and_format_fallbacks_to_user_query_after_tmdb_titles_miss() -> None:
    seen_queries: list[str] = []

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        if query == "星际穿越":
            return [
                {
                    "title": "星际穿越 1080p BluRay",
                    "year": 2014,
                    "size": 2 * 1024 * 1024 * 1024,
                    "indexerName": "IndexerC",
                }
            ]
        return []

    async def fake_tmdb_lookup(_: str, __: str) -> TmdbMovie | None:
        return TmdbMovie(title="Interstellar", original_title="星际穿越", year="2014")

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("星际穿越 (2014)"))

    assert seen_queries == [
        "Interstellar 2014",
        "星际穿越 2014",
        "Interstellar",
        "星际穿越",
    ]
    assert "星际穿越 1080p BluRay" in text


def test_search_and_format_prefers_tmdb_english_first_when_tmdb_match_is_not_exact() -> None:
    seen_queries: list[str] = []

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        if query == "Devil in Dune 2021":
            return [
                {
                    "title": "Devil in Dune 2021 1080p BluRay",
                    "year": 2021,
                    "size": 2 * 1024 * 1024 * 1024,
                    "indexerName": "IndexerD",
                }
            ]
        return []

    async def fake_tmdb_lookup(_: str, __: str) -> TmdbMovie | None:
        return TmdbMovie(title="Devil in Dune", original_title="沙丘虫暴", year="2021")

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("沙丘 2021"))

    assert seen_queries == ["Devil in Dune 2021"]
    assert "片名: 沙丘" in text
    assert "别名: -" in text
    assert "Devil in Dune 2021 1080p BluRay" in text


def test_search_and_format_fallbacks_to_tmdb_original_after_tmdb_english_miss_when_tmdb_match_not_exact() -> None:
    seen_queries: list[str] = []

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        if query == "沙丘虫暴 2021":
            return [
                {
                    "title": "沙丘虫暴 2021 1080p WEB-DL",
                    "year": 2021,
                    "size": 2 * 1024 * 1024 * 1024,
                    "indexerName": "IndexerE",
                }
            ]
        return []

    async def fake_tmdb_lookup(_: str, __: str) -> TmdbMovie | None:
        return TmdbMovie(title="Devil in Dune", original_title="沙丘虫暴", year="2021")

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("沙丘 2021"))

    assert seen_queries == ["Devil in Dune 2021", "沙丘虫暴 2021"]
    assert "片名: 沙丘" in text
    assert "沙丘虫暴 2021 1080p WEB-DL" in text


def test_search_and_format_treats_space_insensitive_original_title_as_confident_tmdb_match() -> None:
    seen_queries: list[str] = []

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        if query == "Dune Part Two 2024":
            return [
                {
                    "title": "Dune Part Two 2024 2160p BluRay",
                    "year": 2024,
                    "size": 10 * 1024 * 1024 * 1024,
                    "indexerName": "IndexerPT",
                }
            ]
        return []

    async def fake_tmdb_lookup(_: str, __: str) -> TmdbMovie | None:
        return TmdbMovie(title="Dune Part Two", original_title="沙丘2", year="2024")

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("沙丘2 2024"))

    assert seen_queries == ["Dune Part Two 2024"]
    assert "片名: 沙丘2" in text
    assert "别名: Dune Part Two" in text
    assert "Dune Part Two 2024 2160p BluRay" in text


def test_search_and_format_treats_multiword_tmdb_subtitle_extension_as_confident_match() -> None:
    seen_queries: list[str] = []

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        if query == "Batman v Superman: Dawn of Justice 2016":
            return [
                {
                    "title": "Batman v Superman: Dawn of Justice 2016 2160p BluRay",
                    "year": 2016,
                    "size": 10 * 1024 * 1024 * 1024,
                    "indexerName": "IndexerDC",
                }
            ]
        return []

    async def fake_tmdb_lookup(title: str, year: str) -> TmdbMovie | None:
        assert title == "Batman v Superman"
        assert year == "2016"
        return TmdbMovie(
            title="Batman v Superman: Dawn of Justice",
            original_title="Batman v Superman: Dawn of Justice",
            year="2016",
        )

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("Batman v Superman 2016"))

    assert seen_queries == ["Batman v Superman: Dawn of Justice 2016"]
    assert "片名: Batman v Superman: Dawn of Justice" in text
    assert "Batman v Superman: Dawn of Justice 2016 2160p BluRay" in text


def test_search_and_format_treats_single_word_tmdb_subtitle_extension_as_confident_match() -> None:
    seen_queries: list[str] = []

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        if query == "Alien: Romulus 2024":
            return [
                {
                    "title": "Alien: Romulus 2024 2160p BluRay",
                    "year": 2024,
                    "size": 10 * 1024 * 1024 * 1024,
                    "indexerName": "IndexerAR",
                }
            ]
        return []

    async def fake_tmdb_lookup(title: str, year: str) -> TmdbMovie | None:
        assert title == "Alien"
        assert year == "2024"
        return TmdbMovie(title="Alien: Romulus", original_title="Alien: Romulus", year="2024")

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("Alien 2024"))

    assert seen_queries == ["Alien: Romulus 2024"]
    assert "片名: Alien: Romulus" in text
    assert "Alien: Romulus 2024 2160p BluRay" in text


def test_search_and_format_does_not_treat_sequel_suffix_as_confident_tmdb_match() -> None:
    seen_queries: list[str] = []

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        if query == "John Wick 2023":
            return [
                {
                    "title": "John Wick 2023 1080p BluRay",
                    "year": 2023,
                    "size": 2 * 1024 * 1024 * 1024,
                    "indexerName": "IndexerJW",
                }
            ]
        return []

    async def fake_tmdb_lookup(title: str, year: str) -> TmdbMovie | None:
        assert title == "John Wick"
        assert year == "2023"
        return TmdbMovie(title="John Wick: Chapter 4", original_title="John Wick: Chapter 4", year="2023")

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("John Wick 2023"))

    assert seen_queries == ["John Wick: Chapter 4 2023", "John Wick 2023"]
    assert "片名: John Wick" in text
    assert "别名: -" in text
    assert "John Wick 2023 1080p BluRay" in text


def test_search_and_format_treats_spaced_sequel_digit_as_confident_tmdb_match() -> None:
    seen_queries: list[str] = []

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        if query == "Dune Part Two 2024":
            return [
                {
                    "title": "Dune Part Two 2024 2160p BluRay",
                    "year": 2024,
                    "size": 10 * 1024 * 1024 * 1024,
                    "indexerName": "IndexerPT",
                }
            ]
        return []

    async def fake_tmdb_lookup(_: str, __: str) -> TmdbMovie | None:
        return TmdbMovie(title="Dune Part Two", original_title="沙丘2", year="2024")

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("沙丘 2 2024"))

    assert seen_queries == ["Dune Part Two 2024"]
    assert "片名: 沙丘2" in text
    assert "别名: Dune Part Two" in text
    assert "Dune Part Two 2024 2160p BluRay" in text


def test_search_and_format_treats_bracketed_year_spaced_sequel_digit_as_confident_tmdb_match() -> None:
    seen_queries: list[str] = []

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        if query == "Dune Part Two 2024":
            return [
                {
                    "title": "Dune Part Two 2024 2160p BluRay",
                    "year": 2024,
                    "size": 10 * 1024 * 1024 * 1024,
                    "indexerName": "IndexerPT",
                }
            ]
        return []

    async def fake_tmdb_lookup(_: str, __: str) -> TmdbMovie | None:
        return TmdbMovie(title="Dune Part Two", original_title="沙丘2", year="2024")

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("沙丘 2 (2024)"))

    assert seen_queries == ["Dune Part Two 2024"]
    assert "片名: 沙丘2" in text
    assert "别名: Dune Part Two" in text
    assert "Dune Part Two 2024 2160p BluRay" in text


def test_search_and_format_treats_fullwidth_bracketed_year_spaced_sequel_digit_as_confident_tmdb_match() -> None:
    seen_queries: list[str] = []

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        if query == "Dune Part Two 2024":
            return [
                {
                    "title": "Dune Part Two 2024 2160p BluRay",
                    "year": 2024,
                    "size": 10 * 1024 * 1024 * 1024,
                    "indexerName": "IndexerPT",
                }
            ]
        return []

    async def fake_tmdb_lookup(_: str, __: str) -> TmdbMovie | None:
        return TmdbMovie(title="Dune Part Two", original_title="沙丘2", year="2024")

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("沙丘 2（2024）"))

    assert seen_queries == ["Dune Part Two 2024"]
    assert "片名: 沙丘2" in text
    assert "别名: Dune Part Two" in text
    assert "Dune Part Two 2024 2160p BluRay" in text


def test_search_and_format_treats_chinese_ordinal_part_as_confident_tmdb_match() -> None:
    seen_queries: list[str] = []

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        if query == "Dune Part Two 2024":
            return [
                {
                    "title": "Dune Part Two 2024 2160p BluRay",
                    "year": 2024,
                    "size": 10 * 1024 * 1024 * 1024,
                    "indexerName": "IndexerPT",
                }
            ]
        return []

    async def fake_tmdb_lookup(title: str, year: str) -> TmdbMovie | None:
        assert title == "沙丘第二部"
        assert year == "2024"
        return TmdbMovie(title="Dune Part Two", original_title="沙丘2", year="2024")

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("沙丘第二部 2024"))

    assert seen_queries == ["Dune Part Two 2024"]
    assert "片名: 沙丘2" in text
    assert "别名: Dune Part Two" in text
    assert "Dune Part Two 2024 2160p BluRay" in text


def test_search_and_format_treats_roman_numeral_sequel_as_confident_tmdb_match() -> None:
    seen_queries: list[str] = []

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        if query == "Dune Part Two 2024":
            return [
                {
                    "title": "Dune Part Two 2024 2160p BluRay",
                    "year": 2024,
                    "size": 10 * 1024 * 1024 * 1024,
                    "indexerName": "IndexerPT",
                }
            ]
        return []

    async def fake_tmdb_lookup(title: str, year: str) -> TmdbMovie | None:
        assert title == "Dune II"
        assert year == "2024"
        return TmdbMovie(title="Dune Part Two", original_title="Dune Part Two", year="2024")

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("Dune II 2024"))

    assert seen_queries == ["Dune Part Two 2024"]
    assert "片名: Dune Part Two" in text
    assert "别名: -" in text
    assert "Dune Part Two 2024 2160p BluRay" in text


def test_search_and_format_treats_part_digit_alias_as_confident_tmdb_match() -> None:
    seen_queries: list[str] = []

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        if query == "Dune Part Two 2024":
            return [
                {
                    "title": "Dune Part Two 2024 2160p BluRay",
                    "year": 2024,
                    "size": 10 * 1024 * 1024 * 1024,
                    "indexerName": "IndexerPT",
                }
            ]
        return []

    async def fake_tmdb_lookup(title: str, year: str) -> TmdbMovie | None:
        assert title == "Dune Part 2"
        assert year == "2024"
        return TmdbMovie(title="Dune Part Two", original_title="Dune: Part Two", year="2024")

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("Dune Part 2 2024"))

    assert seen_queries == ["Dune Part Two 2024"]
    assert "片名: Dune: Part Two" in text
    assert "别名: Dune Part Two" in text
    assert "Dune Part Two 2024 2160p BluRay" in text


def test_search_and_format_treats_chapter_roman_alias_as_confident_tmdb_match() -> None:
    seen_queries: list[str] = []

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        if query == "John Wick: Chapter 4 2023":
            return [
                {
                    "title": "John Wick: Chapter 4 2023 2160p BluRay",
                    "year": 2023,
                    "size": 12 * 1024 * 1024 * 1024,
                    "indexerName": "IndexerJW",
                }
            ]
        return []

    async def fake_tmdb_lookup(title: str, year: str) -> TmdbMovie | None:
        assert title == "John Wick IV"
        assert year == "2023"
        return TmdbMovie(title="John Wick: Chapter 4", original_title="John Wick: Chapter 4", year="2023")

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("John Wick IV 2023"))

    assert seen_queries == ["John Wick: Chapter 4 2023"]
    assert "片名: John Wick: Chapter 4" in text
    assert "John Wick: Chapter 4 2023 2160p BluRay" in text


def test_search_and_format_treats_chapter_word_alias_as_confident_tmdb_match() -> None:
    seen_queries: list[str] = []

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        if query == "John Wick: Chapter 4 2023":
            return [
                {
                    "title": "John Wick: Chapter 4 2023 2160p BluRay",
                    "year": 2023,
                    "size": 12 * 1024 * 1024 * 1024,
                    "indexerName": "IndexerJW",
                }
            ]
        return []

    async def fake_tmdb_lookup(title: str, year: str) -> TmdbMovie | None:
        assert title == "John Wick Chapter Four"
        assert year == "2023"
        return TmdbMovie(title="John Wick: Chapter 4", original_title="John Wick: Chapter 4", year="2023")

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("John Wick Chapter Four 2023"))

    assert seen_queries == ["John Wick: Chapter 4 2023"]
    assert "片名: John Wick: Chapter 4" in text
    assert "John Wick: Chapter 4 2023 2160p BluRay" in text


def test_search_and_format_strips_trailing_noise_after_chapter_digit_alias() -> None:
    seen_queries: list[str] = []

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        if query == "John Wick: Chapter 4 2023":
            return [
                {
                    "title": "John Wick: Chapter 4 2023 2160p BluRay",
                    "year": 2023,
                    "size": 12 * 1024 * 1024 * 1024,
                    "indexerName": "IndexerJW",
                }
            ]
        return []

    async def fake_tmdb_lookup(title: str, year: str) -> TmdbMovie | None:
        assert title == "John Wick Chapter 4"
        assert year == "2023"
        return TmdbMovie(title="John Wick: Chapter 4", original_title="John Wick: Chapter 4", year="2023")

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("John Wick Chapter 4 Extended 2023"))

    assert seen_queries == ["John Wick: Chapter 4 2023"]
    assert "片名: John Wick: Chapter 4" in text
    assert "John Wick: Chapter 4 2023 2160p BluRay" in text


def test_search_and_format_strips_directors_cut_noise_before_tmdb_lookup() -> None:
    seen_queries: list[str] = []

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        if query == "Blade Runner 1982":
            return [
                {
                    "title": "Blade Runner 1982 Final Cut 2160p BluRay",
                    "year": 1982,
                    "size": 14 * 1024 * 1024 * 1024,
                    "indexerName": "IndexerBR",
                }
            ]
        return []

    async def fake_tmdb_lookup(title: str, year: str) -> TmdbMovie | None:
        assert title == "Blade Runner"
        assert year == "1982"
        return TmdbMovie(title="Blade Runner", original_title="Blade Runner", year="1982")

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("Blade Runner Final Cut 1982"))

    assert seen_queries == ["Blade Runner 1982"]
    assert "片名: Blade Runner" in text
    assert "Blade Runner 1982 Final Cut 2160p BluRay" in text


def test_search_and_format_strips_the_final_cut_noise_before_tmdb_lookup() -> None:
    seen_queries: list[str] = []

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        if query == "Blade Runner 1982":
            return [
                {
                    "title": "Blade Runner The Final Cut 1982 2160p BluRay",
                    "year": 1982,
                    "size": 14 * 1024 * 1024 * 1024,
                    "indexerName": "IndexerBR",
                }
            ]
        return []

    async def fake_tmdb_lookup(title: str, year: str) -> TmdbMovie | None:
        assert title == "Blade Runner"
        assert year == "1982"
        return TmdbMovie(title="Blade Runner", original_title="Blade Runner", year="1982")

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("Blade Runner The Final Cut 1982"))

    assert seen_queries == ["Blade Runner 1982"]
    assert "片名: Blade Runner" in text
    assert "Blade Runner The Final Cut 1982 2160p BluRay" in text


def test_search_and_format_strips_remastered_noise_after_chapter_digit_alias() -> None:
    seen_queries: list[str] = []

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        if query == "John Wick: Chapter 4 2023":
            return [
                {
                    "title": "John Wick: Chapter 4 Remastered 2023 2160p BluRay",
                    "year": 2023,
                    "size": 12 * 1024 * 1024 * 1024,
                    "indexerName": "IndexerJW",
                }
            ]
        return []

    async def fake_tmdb_lookup(title: str, year: str) -> TmdbMovie | None:
        assert title == "John Wick Chapter 4"
        assert year == "2023"
        return TmdbMovie(title="John Wick: Chapter 4", original_title="John Wick: Chapter 4", year="2023")

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("John Wick Chapter 4 Remastered 2023"))

    assert seen_queries == ["John Wick: Chapter 4 2023"]
    assert "片名: John Wick: Chapter 4" in text
    assert "John Wick: Chapter 4 Remastered 2023 2160p BluRay" in text


def test_search_and_format_strips_imax_enhanced_noise_after_part_digit_alias() -> None:
    seen_queries: list[str] = []

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        if query == "Dune Part Two 2024":
            return [
                {
                    "title": "Dune Part Two IMAX Enhanced 2024 2160p BluRay",
                    "year": 2024,
                    "size": 10 * 1024 * 1024 * 1024,
                    "indexerName": "IndexerPT",
                }
            ]
        return []

    async def fake_tmdb_lookup(title: str, year: str) -> TmdbMovie | None:
        assert title == "Dune Part 2"
        assert year == "2024"
        return TmdbMovie(title="Dune Part Two", original_title="Dune: Part Two", year="2024")

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("Dune Part 2 IMAX Enhanced 2024"))

    assert seen_queries == ["Dune Part Two 2024"]
    assert "片名: Dune: Part Two" in text
    assert "别名: Dune Part Two" in text
    assert "Dune Part Two IMAX Enhanced 2024 2160p BluRay" in text


def test_search_and_format_strips_anniversary_edition_noise_from_query_title() -> None:
    seen_queries: list[str] = []

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        if query == "Blade Runner 1982":
            return [
                {
                    "title": "Blade Runner Anniversary Edition 1982 2160p BluRay",
                    "year": 1982,
                    "size": 14 * 1024 * 1024 * 1024,
                    "indexerName": "IndexerBR",
                }
            ]
        return []

    async def fake_tmdb_lookup(title: str, year: str) -> TmdbMovie | None:
        assert title == "Blade Runner"
        assert year == "1982"
        return TmdbMovie(title="Blade Runner", original_title="Blade Runner", year="1982")

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("Blade Runner Anniversary Edition 1982"))

    assert seen_queries == ["Blade Runner 1982"]
    assert "片名: Blade Runner" in text
    assert "Blade Runner Anniversary Edition 1982 2160p BluRay" in text


def test_search_and_format_treats_trailing_word_number_alias_as_confident_tmdb_match() -> None:
    seen_queries: list[str] = []

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        if query == "Fast X 2023":
            return [
                {
                    "title": "Fast X 2023 2160p BluRay",
                    "year": 2023,
                    "size": 15 * 1024 * 1024 * 1024,
                    "indexerName": "IndexerFX",
                }
            ]
        return []

    async def fake_tmdb_lookup(title: str, year: str) -> TmdbMovie | None:
        assert title == "Fast Ten"
        assert year == "2023"
        return TmdbMovie(title="Fast X", original_title="Fast X", year="2023")

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("Fast Ten 2023"))

    assert seen_queries == ["Fast X 2023"]
    assert "片名: Fast X" in text
    assert "Fast X 2023 2160p BluRay" in text


def test_search_and_format_deduplicates_same_tmdb_titles() -> None:
    seen_queries: list[str] = []

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        return []

    async def fake_tmdb_lookup(_: str, __: str) -> TmdbMovie | None:
        return TmdbMovie(title="Interstellar", original_title="Interstellar", year="2014")

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("星际穿越 (2014)"))

    assert seen_queries == [
        "Interstellar 2014",
        "星际穿越 2014",
        "Interstellar",
        "星际穿越",
    ]
    assert text == NO_RESULT_TEXT_TEMPLATE.format(query="星际穿越 (2014)")


def test_search_and_format_deduplicates_normalization_equivalent_tmdb_titles() -> None:
    seen_queries: list[str] = []

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        return []

    async def fake_tmdb_lookup(_: str, __: str) -> TmdbMovie | None:
        return TmdbMovie(title="Dune Part Two", original_title="Dune: Part Two", year="2024")

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("Dune Part 2 2024"))

    assert seen_queries == ["Dune Part Two 2024", "Dune Part Two"]
    assert text == NO_RESULT_TEXT_TEMPLATE.format(query="Dune Part 2 2024")


def test_search_and_format_fallbacks_to_normalized_query_when_tmdb_empty() -> None:
    seen_queries: list[str] = []

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        return []

    async def fake_tmdb_lookup(title: str, year: str) -> TmdbMovie | None:
        assert title == "Dune"
        assert year == "2021"
        return None

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("Dune (2021)"))
    assert seen_queries == ["Dune 2021", "Dune"]
    assert text == NO_RESULT_TEXT_TEMPLATE.format(query="Dune (2021)")


def test_search_and_format_drops_series_episode_candidate_for_movie_query() -> None:
    async def fake_search(query: str) -> list[dict[str, object]]:
        assert query == "周处除三害 2024"
        return [
            {
                "title": "Zhou Chu Chu San Hai Zhi Su Ming 2024 S01 1080p WEB-DL H.264 AAC-GodDramas",
                "year": 2024,
                "size": 2 * 1024 * 1024 * 1024,
                "downloadUrl": "https://example.com/zhou.torrent",
                "indexerName": "IndexerDrama",
            }
        ]

    service = SearchMediaService(fake_search)
    text = _run(service.search_and_format("周处除三害 2024"))

    assert text == NO_RESULT_TEXT_TEMPLATE.format(query="周处除三害 2024")


def test_search_and_format_drops_movie_extra_candidate_for_movie_query() -> None:
    async def fake_search(query: str) -> list[dict[str, object]]:
        assert query == "Dune Part 2 2024"
        return [
            {
                "title": "Dune: Part Two 2024 Extras 1080p BluRay Remux AVC DD2.0-OPTIMUM",
                "year": 2024,
                "size": 10 * 1024 * 1024 * 1024,
                "downloadUrl": "https://example.com/dune-extras.torrent",
                "indexerName": "IndexerExtras",
            },
            {
                "title": "Dune: Part Two 2024 2160p UHD BluRay x265 10bit DoVi 2Audio TrueHD Atmos 7.1 mUHD-FRDS",
                "year": 2024,
                "size": 80 * 1024 * 1024 * 1024,
                "downloadUrl": "https://example.com/dune-main.torrent",
                "indexerName": "IndexerMain",
            },
        ]

    service = SearchMediaService(fake_search)
    text = _run(service.search_and_format("Dune Part 2 2024"))

    assert "Dune: Part Two 2024 2160p UHD BluRay x265 10bit DoVi 2Audio TrueHD Atmos 7.1 mUHD-FRDS" in text
    assert "Dune: Part Two 2024 Extras 1080p BluRay Remux AVC DD2.0-OPTIMUM" not in text


def test_search_and_format_keeps_sequel_alias_candidate_without_tmdb_lookup() -> None:
    async def fake_search(query: str) -> list[dict[str, object]]:
        assert query == "Dune Part 2 2024"
        return [
            {
                "title": "Dune: Part One 2024 2160p BluRay",
                "year": 2024,
                "size": 50 * 1024 * 1024 * 1024,
                "downloadUrl": "https://example.com/dune-part-one.torrent",
                "indexerName": "IndexerPartOne",
            },
            {
                "title": "Dune: Part Two 2024 1080p WEB-DL",
                "year": 2024,
                "size": 8 * 1024 * 1024 * 1024,
                "downloadUrl": "https://example.com/dune-part-two.torrent",
                "indexerName": "IndexerPartTwo",
            },
        ]

    service = SearchMediaService(fake_search)
    text = _run(service.search_and_format("Dune Part 2 2024"))

    assert "1. Dune: Part Two 2024 1080p WEB-DL" in text
    assert "2. Dune: Part One 2024 2160p BluRay" not in text


def test_search_and_format_deduplicates_streaming_provider_tag_variants() -> None:
    async def fake_search(query: str) -> list[dict[str, object]]:
        assert query == "Dune 2021"
        return [
            {
                "title": "Dune 2021 2160p BluRay x265-GRP3",
                "year": 2021,
                "size": 20 * 1024 * 1024 * 1024,
                "downloadUrl": "https://example.com/dune-2160.torrent",
                "indexerName": "Indexer2160",
            },
            {
                "title": "Dune 2021 1080p AMZN WEB-DL x265-GRP",
                "year": 2021,
                "size": 8 * 1024 * 1024 * 1024,
                "downloadUrl": "https://example.com/dune-amzn.torrent",
                "indexerName": "IndexerAmzn",
            },
            {
                "title": "Dune 2021 1080p DSNP WEB-DL x265-GRP2",
                "year": 2021,
                "size": 8 * 1024 * 1024 * 1024,
                "downloadUrl": "https://example.com/dune-dsnp.torrent",
                "indexerName": "IndexerDsnp",
            },
        ]

    service = SearchMediaService(fake_search)
    text = _run(service.search_and_format("Dune 2021"))

    assert "1. Dune 2021 2160p BluRay x265-GRP3" in text
    assert "2. Dune 2021 1080p AMZN WEB-DL x265-GRP" in text
    assert "Dune 2021 1080p DSNP WEB-DL x265-GRP2" not in text


def test_search_and_format_deduplicates_4k_and_2160p_variants() -> None:
    async def fake_search(query: str) -> list[dict[str, object]]:
        assert query == "Dune 2021"
        return [
            {
                "title": "Dune 2021 4K UHD BluRay x265-GRP1",
                "year": 2021,
                "size": 20 * 1024 * 1024 * 1024,
                "downloadUrl": "https://example.com/dune-4k.torrent",
                "indexerName": "Indexer4K",
            },
            {
                "title": "Dune 2021 2160p UHD BluRay x265-GRP2",
                "year": 2021,
                "size": 20 * 1024 * 1024 * 1024,
                "downloadUrl": "https://example.com/dune-2160p.torrent",
                "indexerName": "Indexer2160p",
            },
        ]

    service = SearchMediaService(fake_search)
    text = _run(service.search_and_format("Dune 2021"))

    assert "1. Dune 2021 4K UHD BluRay x265-GRP1" in text
    assert "Dune 2021 2160p UHD BluRay x265-GRP2" not in text


def test_search_and_format_deduplicates_same_title_after_movie_ordering() -> None:
    async def fake_search(query: str) -> list[dict[str, object]]:
        assert query == "流浪地球2 2023"
        return [
            {
                "title": "The Wandering Earth 2 2023 2160p UHD BluRay Remux HEVC DV DTS-HD MA 5.1-ADE",
                "year": 2023,
                "size": 80 * 1024 * 1024 * 1024,
                "downloadUrl": "https://example.com/a.torrent",
                "indexerName": "IndexerA",
            },
            {
                "title": "The Wandering Earth 2 2023 2160p UHD BluRay Remux HEVC DV DTS-HD MA 5.1-ADE",
                "year": 2023,
                "size": 80 * 1024 * 1024 * 1024,
                "downloadUrl": "https://example.com/b.torrent",
                "indexerName": "IndexerB",
            },
            {
                "title": "The Wandering Earth II 2023 GBR UHD BluRay 2160p x265 10bit HDR 2Audio DTS-HD MA 5.1-beAst",
                "year": 2023,
                "size": 70 * 1024 * 1024 * 1024,
                "downloadUrl": "https://example.com/c.torrent",
                "indexerName": "IndexerC",
            },
        ]

    service = SearchMediaService(fake_search)
    text = _run(service.search_and_format("流浪地球2 2023"))

    assert text.count("The Wandering Earth 2 2023 2160p UHD BluRay Remux HEVC DV DTS-HD MA 5.1-ADE") == 1
    assert "The Wandering Earth II 2023 GBR UHD BluRay 2160p x265 10bit HDR 2Audio DTS-HD MA 5.1-beAst" not in text


def test_search_and_format_deduplicates_near_duplicate_title_after_movie_ordering() -> None:
    async def fake_search(query: str) -> list[dict[str, object]]:
        assert query == "流浪地球2 2023"
        return [
            {
                "title": "The Wandering Earth 2 2023 2160p UHD BluRay Remux HEVC DV DTS-HD MA 5.1-ADE",
                "year": 2023,
                "size": 80 * 1024 * 1024 * 1024,
                "downloadUrl": "https://example.com/a.torrent",
                "indexerName": "IndexerA",
            },
            {
                "title": "The Wandering Earth II 2023 2160p UHD BluRay Remux HEVC DV DTS-HD MA 5.1-BEAST",
                "year": 2023,
                "size": 79 * 1024 * 1024 * 1024,
                "downloadUrl": "https://example.com/b.torrent",
                "indexerName": "IndexerB",
            },
            {
                "title": "The Wandering Earth II 2023 1080p BluRay DTS x264-WiKi",
                "year": 2023,
                "size": 20 * 1024 * 1024 * 1024,
                "downloadUrl": "https://example.com/c.torrent",
                "indexerName": "IndexerC",
            },
        ]

    service = SearchMediaService(fake_search)
    text = _run(service.search_and_format("流浪地球2 2023"))

    assert text.count("The Wandering Earth 2 2023 2160p UHD BluRay Remux HEVC DV DTS-HD MA 5.1-ADE") == 1
    assert "The Wandering Earth II 2023 2160p UHD BluRay Remux HEVC DV DTS-HD MA 5.1-BEAST" not in text
    assert "The Wandering Earth II 2023 1080p BluRay DTS x264-WiKi" in text

def test_search_and_format_fallbacks_to_normalized_query_when_tmdb_failed() -> None:
    seen_queries: list[str] = []

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        return []

    async def fake_tmdb_lookup(_: str, __: str) -> TmdbMovie | None:
        raise RuntimeError("tmdb unavailable")

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("Dune 2021"))
    assert seen_queries == ["Dune 2021", "Dune"]
    assert text == NO_RESULT_TEXT_TEMPLATE.format(query="Dune 2021")


def test_search_and_format_logs_tmdb_failure(capsys) -> None:
    seen_queries: list[str] = []

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        return []

    async def fake_tmdb_lookup(_: str, __: str) -> TmdbMovie | None:
        raise RuntimeError("tmdb unavailable")

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)

    text = _run(service.search_and_format("Dune 2021"))

    assert text == NO_RESULT_TEXT_TEMPLATE.format(query="Dune 2021")
    assert seen_queries == ["Dune 2021", "Dune"]
    output = capsys.readouterr().out
    assert "[TMDB 查询失败]" in output
    assert "query=Dune 2021" in output


def test_search_and_format_logs_search_backend_failure(capsys) -> None:
    async def fake_search(_: str) -> list[dict[str, object]]:
        raise RuntimeError("indexer unavailable")

    service = SearchMediaService(fake_search)

    with pytest.raises(RuntimeError, match="indexer unavailable"):
        _run(service.search_and_format("Dune 2021"))

    output = capsys.readouterr().out
    assert "[搜索源查询失败]" in output
    assert "query=Dune 2021" in output


def test_parse_movie_query_parentheses_year() -> None:
    parsed = parse_movie_query("Dune (2021)")
    assert parsed.title == "Dune"
    assert parsed.year == "2021"


def test_parse_movie_query_suffix_year() -> None:
    parsed = parse_movie_query("Dune 2021")
    assert parsed.title == "Dune"
    assert parsed.year == "2021"


def test_parse_movie_query_keeps_sequel_digit_before_year() -> None:
    parsed = parse_movie_query("沙丘2 2024")
    assert parsed.title == "沙丘2"
    assert parsed.year == "2024"


def test_parse_movie_query_keeps_spaced_sequel_digit_before_year() -> None:
    parsed = parse_movie_query("沙丘 2 2024")
    assert parsed.title == "沙丘2"
    assert parsed.year == "2024"


def test_parse_movie_query_keeps_spaced_sequel_digit_with_bracketed_year() -> None:
    parsed = parse_movie_query("沙丘 2 (2024)")
    assert parsed.title == "沙丘2"
    assert parsed.year == "2024"


def test_parse_movie_query_keeps_spaced_sequel_digit_with_fullwidth_bracketed_year() -> None:
    parsed = parse_movie_query("沙丘 2（2024）")
    assert parsed.title == "沙丘2"
    assert parsed.year == "2024"


def test_parse_movie_query_keeps_roman_numeral_sequel_before_year() -> None:
    parsed = parse_movie_query("Dune II 2024")
    assert parsed.title == "Dune II"
    assert parsed.year == "2024"


def test_parse_movie_query_keeps_spaced_digit_title_before_year() -> None:
    parsed = parse_movie_query("Mission Impossible 7 2023")
    assert parsed.title == "Mission Impossible 7"
    assert parsed.year == "2023"


def test_parse_movie_query_keeps_part_digit_alias_before_year() -> None:
    parsed = parse_movie_query("Dune Part 2 2024")
    assert parsed.title == "Dune Part 2"
    assert parsed.year == "2024"


def test_parse_movie_query_keeps_chapter_digit_before_trailing_noise_and_year() -> None:
    parsed = parse_movie_query("John Wick Chapter 4 Extended 2023")
    assert parsed.title == "John Wick Chapter 4"
    assert parsed.year == "2023"


def test_parse_movie_query_keeps_part_digit_before_trailing_noise_and_year() -> None:
    parsed = parse_movie_query("Dune Part 2 Extended 2024")
    assert parsed.title == "Dune Part 2"
    assert parsed.year == "2024"


def test_parse_movie_query_keeps_spaced_digit_title_before_trailing_noise_and_year() -> None:
    parsed = parse_movie_query("Mission Impossible 7 IMAX 2023")
    assert parsed.title == "Mission Impossible 7"
    assert parsed.year == "2023"


def test_parse_movie_query_strips_trailing_noise_from_roman_numeral_title() -> None:
    parsed = parse_movie_query("Fast X Special Edition 2023")
    assert parsed.title == "Fast X"
    assert parsed.year == "2023"


def test_parse_movie_query_strips_final_cut_noise() -> None:
    parsed = parse_movie_query("Blade Runner Final Cut 1982")
    assert parsed.title == "Blade Runner"
    assert parsed.year == "1982"


def test_parse_movie_query_strips_directors_cut_noise() -> None:
    parsed = parse_movie_query("Alien Director's Cut 1979")
    assert parsed.title == "Alien"
    assert parsed.year == "1979"


def test_parse_movie_query_strips_the_final_cut_noise() -> None:
    parsed = parse_movie_query("Blade Runner The Final Cut 1982")
    assert parsed.title == "Blade Runner"
    assert parsed.year == "1982"


def test_parse_movie_query_strips_the_directors_cut_noise() -> None:
    parsed = parse_movie_query("Alien The Director's Cut 1979")
    assert parsed.title == "Alien"
    assert parsed.year == "1979"


def test_parse_movie_query_strips_ultimate_edition_noise() -> None:
    parsed = parse_movie_query("Batman v Superman Ultimate Edition 2016")
    assert parsed.title == "Batman v Superman"
    assert parsed.year == "2016"


def test_parse_movie_query_keeps_actual_final_cut_title() -> None:
    parsed = parse_movie_query("The Final Cut 2004")
    assert parsed.title == "The Final Cut"
    assert parsed.year == "2004"


def test_parse_movie_query_strips_remastered_noise() -> None:
    parsed = parse_movie_query("Alien Remastered 1979")
    assert parsed.title == "Alien"
    assert parsed.year == "1979"


def test_parse_movie_query_strips_extended_cut_noise() -> None:
    parsed = parse_movie_query("Avatar Extended Cut 2009")
    assert parsed.title == "Avatar"
    assert parsed.year == "2009"


def test_parse_movie_query_strips_special_extended_edition_noise() -> None:
    parsed = parse_movie_query("Batman v Superman Special Extended Edition 2016")
    assert parsed.title == "Batman v Superman"
    assert parsed.year == "2016"


def test_parse_movie_query_strips_imax_enhanced_noise_after_part_digit() -> None:
    parsed = parse_movie_query("Dune Part 2 IMAX Enhanced 2024")
    assert parsed.title == "Dune Part 2"
    assert parsed.year == "2024"


def test_parse_movie_query_strips_theatrical_cut_noise_after_part_digit() -> None:
    parsed = parse_movie_query("Dune Part 2 Theatrical 2024")
    assert parsed.title == "Dune Part 2"
    assert parsed.year == "2024"


def test_parse_movie_query_strips_theatrical_version_noise() -> None:
    parsed = parse_movie_query("Blade Runner Theatrical Version 1982")
    assert parsed.title == "Blade Runner"
    assert parsed.year == "1982"


def test_parse_movie_query_strips_uncut_noise() -> None:
    parsed = parse_movie_query("Batman v Superman Uncut 2016")
    assert parsed.title == "Batman v Superman"
    assert parsed.year == "2016"


def test_parse_movie_query_strips_unrated_noise_after_part_digit() -> None:
    parsed = parse_movie_query("Dune Part 2 Unrated 2024")
    assert parsed.title == "Dune Part 2"
    assert parsed.year == "2024"


def test_parse_movie_query_strips_anniversary_edition_noise() -> None:
    parsed = parse_movie_query("Blade Runner Anniversary Edition 1982")
    assert parsed.title == "Blade Runner"
    assert parsed.year == "1982"


def test_parse_movie_query_strips_collectors_edition_noise() -> None:
    parsed = parse_movie_query("Avatar Collectors Edition 2009")
    assert parsed.title == "Avatar"
    assert parsed.year == "2009"


def test_parse_movie_query_strips_collector_edition_noise() -> None:
    parsed = parse_movie_query("Aliens Collector Edition 1986")
    assert parsed.title == "Aliens"
    assert parsed.year == "1986"


def test_parse_movie_query_keeps_title_when_no_year() -> None:
    parsed = parse_movie_query("  Dune   Part   Two  ")
    assert parsed.title == "Dune Part Two"
    assert parsed.year == ""


def test_parse_movie_query_uses_media_name_parser_for_episode_query() -> None:
    parsed = parse_movie_query("鬼灭之刃 S01E01")
    assert parsed.title == "鬼灭之刃"
    assert parsed.year == ""


def _run(coroutine: Awaitable[str]) -> str:
    import asyncio

    return asyncio.run(coroutine)

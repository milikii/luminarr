from __future__ import annotations

from collections.abc import Awaitable
import json
from pathlib import Path

import httpx
import pytest

from app.clients.javlibrary_helper import JavLibraryReadOnlyMatch
from app.db.adult_content_registry_repo import AdultContentRegistryRepo
from app.clients.tmdb import TmdbClient, TmdbMovie
from app.db.candidate_repo import CandidateMappingRepo
from app.db.candidate_repo import CandidatePersistenceError
from app.db.clarification_repo import ClarificationPersistenceError, ClarificationRepo
from app.db.sqlite import SqliteDatabase
from app.services.adult_metadata_translation import AdultMetadataTranslatorService
from app.services.bt_candidate_scorer import BTScoringRules, DEFAULT_BT_SCORING_RULES
from app.services.search_media_state import CandidateStateStore, ClarificationStateStore
from app.services.search_media import (
    ADULT_BT_SOURCE_EMPTY_TEXT_TEMPLATE,
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
)
from app.services.pure_bt import BTBatchPreviewRequest
from app.services.search_query_parser import parse_movie_query
from app.services.search_request_context import build_search_request_context


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


def test_search_bt_read_only_and_format_uses_adult_only_resource_fallback_when_enabled() -> None:
    fallback_queries: list[str] = []

    async def unexpected_pt_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("PT search should not be used for adult-only fallback")

    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        fallback_queries.append(query)
        if query == "SSIS-123":
            return [
                {
                    "title": "Dune 2021 1080p",
                    "source": "magnet:?xt=urn:btih:1111111111111111111111111111111111111111",
                    "infoHash": "1111111111111111111111111111111111111111",
                    "seeders": 4,
                    "size": 1 * 1024 * 1024 * 1024,
                    "indexerName": "Nyaa",
                    "sourceProvider": "nyaa",
                }
            ]
        if query == "SSIS 123":
            return [
                {
                    "title": "SSIS 123 resource release",
                    "source": "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12",
                    "infoHash": "abcdef1234567890abcdef1234567890abcdef12",
                    "seeders": 9,
                    "size": 2 * 1024 * 1024 * 1024,
                    "indexerName": "tokyotosho",
                    "sourceProvider": "tokyotosho",
                }
            ]
        return []

    service = SearchMediaService(unexpected_pt_search, raw_search_func=fake_raw_search)
    text = _run(service.search_bt_read_only_and_format("SSIS-123", adult_only=True))

    assert fallback_queries == ["SSIS-123", "SSIS 123"]
    assert "成人资源候选：SSIS-123" in text
    assert "1. SSIS 123 resource release" in text
    assert "Dune 2021 1080p" not in text
    assert BT_READ_ONLY_NO_RESULT_TEXT_TEMPLATE.format(query="SSIS-123") not in text


def test_search_bt_read_only_and_format_adult_only_direct_hit_uses_rich_resource_layout() -> None:
    magnet = "magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa&dn=ssis-123"
    helper_queries: list[str] = []

    async def unexpected_pt_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("PT search should not be used for adult-only results")

    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        assert query == "SSIS-123"
        return [
            {
                "title": "SSIS-123 Sample Title",
                "source": magnet,
                "infoHash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "seeders": 12,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "tokyotosho",
                "sourceProvider": "tokyotosho",
                "posterUrl": "https://img.example/ssis-123.jpg",
                "releaseDate": "2026-01-02",
                "runtime": "120 分钟",
                "maker": "Prestige",
                "actors": ["Actor A", "Actor B"],
                "metadataSource": "avmoo.shop",
            }
        ]

    async def fake_helper_lookup(lookup_query: str) -> JavLibraryReadOnlyMatch | None:
        helper_queries.append(lookup_query)
        return JavLibraryReadOnlyMatch(
            normalized_content_id="censored:ssis-123",
            display_id="SSIS-123",
            archive_category="censored",
            title="SSIS-123 Sample Title",
            detail_url="https://www.javlibrary.com/tw/?v=javli0001",
            poster_url="https://pics.example/backup-ssis-123.jpg",
            release_date="2020-01-01",
            runtime="98 分钟",
            maker="Backup Studio",
            actors=("Backup Actor",),
        )

    service = SearchMediaService(
        unexpected_pt_search,
        raw_search_func=fake_raw_search,
        adult_read_only_lookup_func=fake_helper_lookup,
    )
    text = _run(service.search_bt_read_only_and_format("SSIS-123", adult_only=True))

    assert helper_queries == ["SSIS-123"]
    assert text.startswith("成人资源候选：SSIS-123")
    assert "BT 只读探索结果：" not in text
    assert "海报: https://img.example/ssis-123.jpg" in text
    assert "标准信息: 标题: SSIS-123 Sample Title | 发行日: 2026-01-02 | 时长: 120 分钟" in text
    assert "制作信息: 制作商: Prestige | 演员: Actor A / Actor B" in text
    assert "Metadata源: avmoo | 角色: primary" in text
    assert "https://pics.example/backup-ssis-123.jpg" not in text
    assert "Backup Studio" not in text
    assert f"磁力链接: {magnet}" in text


def test_search_bt_read_only_and_format_applies_general_adult_metadata_translation() -> None:
    magnet = "magnet:?xt=urn:btih:dddddddddddddddddddddddddddddddddddddddd&dn=ssis-842"
    translated_queries: list[str] = []

    async def unexpected_pt_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("PT search should not be used for adult-only translation results")

    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        assert query == "SSIS-842"
        return [
            {
                "title": "SSIS-842 resource title",
                "source": magnet,
                "infoHash": "dddddddddddddddddddddddddddddddddddddddd",
                "seeders": 7,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "tokyotosho",
                "sourceProvider": "tokyotosho",
            }
        ]

    async def fake_helper_lookup(lookup_query: str) -> JavLibraryReadOnlyMatch | None:
        assert lookup_query == "SSIS-842"
        return JavLibraryReadOnlyMatch(
            normalized_content_id="censored:ssis-842",
            display_id="SSIS-842",
            archive_category="censored",
            title="SSIS-842 彼女のリアルで生々しい姿をお見せします",
            detail_url="https://avmoo.shop/cn/movie/842",
            source_site="avmoo.shop",
            poster_url="https://img.example/ssis-842.jpg",
            release_date="2024-02-02",
            runtime="120 分钟",
            maker="エスワン ナンバーワンスタイル",
            series="リアルSEXドキュメント",
            director="苺原",
            actors=("うんぱい",),
        )

    async def fake_translate(candidates):
        translated_queries.append(str(candidates[0].get("read_only_adult_title", "")))
        translated = dict(candidates[0])
        translated.update(
            {
                "adult_translation_title_zh": "SSIS-842 让你看到她真实而鲜活的一面",
                "adult_translation_overview_zh": "这是一段翻译后的中文简介，欲望与嫉妒在关系里彼此交错。",
                "adult_translation_series_zh": "真实性爱纪录",
                "adult_translation_maker_zh": "S1 顶级风格",
                "adult_translation_director_zh": "莓原",
            }
        )
        return [translated]

    service = SearchMediaService(
        unexpected_pt_search,
        raw_search_func=fake_raw_search,
        adult_read_only_lookup_func=fake_helper_lookup,
        adult_metadata_translate_func=fake_translate,
    )
    text = _run(service.search_bt_read_only_and_format("SSIS-842", adult_only=True))

    assert translated_queries == ["SSIS-842 彼女のリアルで生々しい姿をお見せします"]
    assert "标准信息: 标题: SSIS-842 让你看到她真实而鲜活的一面 | 原名: SSIS-842 彼女のリアルで生々しい姿をお見せします" in text
    assert "简介: 这是一段翻译后的中文简介，欲望与嫉妒在关系里彼此交错。" in text
    assert "制作信息: 制作商: S1 顶级风格 | 系列: 真实性爱纪录 | 原系列: リアルSEXドキュメント | 导演: 莓原 | 演员: うんぱい" in text
    assert "中文名未确认" not in text
    assert f"磁力链接: {magnet}" in text


def test_search_bt_read_only_and_format_shared_helper_metadata_reuses_one_translation_for_all_candidates() -> None:
    magnet_a = "magnet:?xt=urn:btih:1111111111111111111111111111111111111111&dn=ssis-491-a"
    magnet_b = "magnet:?xt=urn:btih:2222222222222222222222222222222222222222&dn=ssis-491-b"
    translation_batches: list[list[str]] = []

    async def unexpected_pt_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("PT search should not be used for adult-only translation reuse")

    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        assert query == "SSIS-491"
        return [
            {
                "title": "SSIS-491 release A",
                "source": magnet_a,
                "infoHash": "1111111111111111111111111111111111111111",
                "seeders": 8,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "tokyotosho",
                "sourceProvider": "tokyotosho",
            },
            {
                "title": "SSIS-491 release B",
                "source": magnet_b,
                "infoHash": "2222222222222222222222222222222222222222",
                "seeders": 6,
                "size": 3 * 1024 * 1024 * 1024,
                "indexerName": "javbus",
                "sourceProvider": "javbus",
            },
        ]

    async def fake_helper_lookup(lookup_query: str) -> JavLibraryReadOnlyMatch | None:
        assert lookup_query == "SSIS-491"
        return JavLibraryReadOnlyMatch(
            normalized_content_id="censored:ssis-491",
            display_id="SSIS-491",
            archive_category="censored",
            title="SSIS-491 日本語タイトル",
            detail_url="https://avmoo.shop/cn/movie/491",
            source_site="avmoo.shop",
            poster_url="https://img.example/ssis-491.jpg",
            release_date="2024-04-01",
            runtime="120 分钟",
            maker="S1",
            series="シリーズ名",
            actors=("うんぱい",),
        )

    def fake_request_chat_completion(_system_prompt: str, user_payload: dict[str, object]) -> str:
        requests = user_payload["requests"]
        assert isinstance(requests, list)
        translation_batches.append([str(item["request_id"]) for item in requests])
        assert len(requests) == 1
        return json.dumps(
            {
                "translations": [
                    {
                        "request_id": str(requests[0]["request_id"]),
                        "title_zh": "SSIS-491 中文标题",
                        "series_zh": "中文系列",
                        "maker_zh": "中文片商",
                    }
                ]
            },
            ensure_ascii=False,
        )

    translator = AdultMetadataTranslatorService(
        api_key="adult-translate-key",
        request_chat_completion_func=fake_request_chat_completion,
    )
    service = SearchMediaService(
        unexpected_pt_search,
        raw_search_func=fake_raw_search,
        adult_read_only_lookup_func=fake_helper_lookup,
        adult_metadata_translate_func=translator.translate_candidates,
    )

    text = _run(service.search_bt_read_only_and_format("SSIS-491", adult_only=True))

    assert translation_batches == [["candidate-1"]]
    assert text.count("标准信息: 标题: SSIS-491 中文标题 | 原名: SSIS-491 日本語タイトル | 发行日: 2024-04-01 | 时长: 120 分钟") == 2
    assert text.count("制作信息: 制作商: 中文片商 | 系列: 中文系列 | 原系列: シリーズ名 | 演员: うんぱい") == 2
    assert f"磁力链接: {magnet_a}" in text
    assert f"磁力链接: {magnet_b}" in text


def test_search_bt_read_only_and_format_adult_only_renders_backup_helper_metadata() -> None:
    magnet = "magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb&dn=ssis-123"

    async def unexpected_pt_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("PT search should not be used for adult-only helper metadata")

    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        assert query == "SSIS-123"
        return [
            {
                "title": "Secret Mission Nurse leaked cut",
                "source": magnet,
                "infoHash": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "seeders": 8,
                "size": 1 * 1024 * 1024 * 1024,
                "indexerName": "tokyotosho",
                "sourceProvider": "tokyotosho",
            }
        ]

    async def fake_helper_lookup(lookup_query: str) -> object:
        assert lookup_query == "SSIS-123"

        class HelperMatch:
            normalized_content_id = "censored:ssis-123"
            display_id = "SSIS-123"
            archive_category = "censored"
            title = "SSIS-123 Secret Mission Nurse"
            detail_url = "https://www.javlibrary.com/tw/?v=javli0001"
            source_site = "javlibrary"
            poster_url = "https://pics.example/javlibrary-ssis-123.jpg"
            release_date = "2025-12-31"
            runtime = "118 分钟"
            maker = "Backup Studio"
            actors = ("Actor C",)

        return HelperMatch()

    service = SearchMediaService(
        unexpected_pt_search,
        raw_search_func=fake_raw_search,
        adult_read_only_lookup_func=fake_helper_lookup,
    )
    text = _run(service.search_bt_read_only_and_format("SSIS-123", adult_only=True))

    assert "只读补全: javlibrary | 番号: SSIS-123 | 分类: censored" in text
    assert "海报: https://pics.example/javlibrary-ssis-123.jpg" in text
    assert "标准信息: 标题: SSIS-123 Secret Mission Nurse | 发行日: 2025-12-31 | 时长: 118 分钟" in text
    assert "制作信息: 制作商: Backup Studio | 演员: Actor C" in text
    assert "Metadata源: javlibrary | 角色: backup_cross_check" in text
    assert f"磁力链接: {magnet}" in text


def test_search_bt_read_only_and_format_adult_translation_failure_is_soft_and_logs(monkeypatch: pytest.MonkeyPatch) -> None:
    magnet = "magnet:?xt=urn:btih:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee&dn=ssis-842"
    logged: list[tuple[str, str]] = []

    async def unexpected_pt_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("PT search should not be used for adult-only translation failure")

    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        assert query == "SSIS-842"
        return [
            {
                "title": "SSIS-842 resource title",
                "source": magnet,
                "infoHash": "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
                "seeders": 4,
                "size": 1 * 1024 * 1024 * 1024,
                "indexerName": "tokyotosho",
                "sourceProvider": "tokyotosho",
            }
        ]

    async def fake_helper_lookup(lookup_query: str) -> JavLibraryReadOnlyMatch | None:
        assert lookup_query == "SSIS-842"
        return JavLibraryReadOnlyMatch(
            normalized_content_id="censored:ssis-842",
            display_id="SSIS-842",
            archive_category="censored",
            title="SSIS-842 日本語タイトル",
            detail_url="https://avmoo.shop/cn/movie/842",
            source_site="avmoo.shop",
            actors=("うんぱい",),
        )

    async def fake_translate(_candidates):
        raise RuntimeError("translator boom")

    monkeypatch.setattr(
        "app.services.search_media.emit_operational_log",
        lambda *, title, detail, fix_hint: logged.append((title, detail)),
    )

    service = SearchMediaService(
        unexpected_pt_search,
        raw_search_func=fake_raw_search,
        adult_read_only_lookup_func=fake_helper_lookup,
        adult_metadata_translate_func=fake_translate,
    )
    text = _run(service.search_bt_read_only_and_format("SSIS-842", adult_only=True))

    assert text.startswith("成人资源候选：SSIS-842")
    assert "标准信息: 标题: SSIS-842 日本語タイトル" in text
    assert f"磁力链接: {magnet}" in text
    assert logged
    assert logged[0][0] == "成人 metadata 翻译失败"
    assert "SSIS-842" in logged[0][1]


def test_search_bt_read_only_and_format_adult_translation_without_api_key_keeps_resources() -> None:
    magnet = "magnet:?xt=urn:btih:ffffffffffffffffffffffffffffffffffffffff&dn=ssis-842"

    async def unexpected_pt_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("PT search should not be used for adult-only no-key translation")

    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        assert query == "SSIS-842"
        return [
            {
                "title": "SSIS-842 resource title",
                "source": magnet,
                "infoHash": "ffffffffffffffffffffffffffffffffffffffff",
                "seeders": 5,
                "size": 1 * 1024 * 1024 * 1024,
                "indexerName": "tokyotosho",
                "sourceProvider": "tokyotosho",
                "read_only_adult_overview": "日本語のあらすじ",
            }
        ]

    async def fake_helper_lookup(lookup_query: str) -> JavLibraryReadOnlyMatch | None:
        assert lookup_query == "SSIS-842"
        return JavLibraryReadOnlyMatch(
            normalized_content_id="censored:ssis-842",
            display_id="SSIS-842",
            archive_category="censored",
            title="SSIS-842 日本語タイトル",
            detail_url="https://avmoo.shop/cn/movie/842",
            source_site="avmoo.shop",
            actors=("うんぱい",),
        )

    service = SearchMediaService(
        unexpected_pt_search,
        raw_search_func=fake_raw_search,
        adult_read_only_lookup_func=fake_helper_lookup,
        adult_metadata_translate_func=AdultMetadataTranslatorService(api_key="").translate_candidates,
    )
    text = _run(service.search_bt_read_only_and_format("SSIS-842", adult_only=True))

    assert text.startswith("成人资源候选：SSIS-842")
    assert "标准信息: 标题: SSIS-842 日本語タイトル" in text
    assert f"磁力链接: {magnet}" in text


def test_search_bt_read_only_and_format_adult_only_enriches_explicit_id_with_helper_metadata() -> None:
    magnet = "magnet:?xt=urn:btih:cccccccccccccccccccccccccccccccccccccccc&dn=ssis-123"

    async def unexpected_pt_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("PT search should not be used for adult-only explicit metadata")

    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        assert query == "SSIS-123"
        return [
            {
                "title": "SSIS-123 Sample Title",
                "source": magnet,
                "infoHash": "cccccccccccccccccccccccccccccccccccccccc",
                "seeders": 8,
                "size": 1 * 1024 * 1024 * 1024,
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
            poster_url="https://pics.example/explicit-ssis-123.jpg",
            release_date="2026-02-03",
            runtime="121 分钟",
            maker="Backup Studio",
            actors=("Actor D",),
        )

    service = SearchMediaService(
        unexpected_pt_search,
        raw_search_func=fake_raw_search,
        adult_read_only_lookup_func=fake_helper_lookup,
    )
    text = _run(service.search_bt_read_only_and_format("SSIS-123", adult_only=True))

    assert "海报: https://pics.example/explicit-ssis-123.jpg" in text
    assert "标准信息: 标题: SSIS-123 Sample Title | 发行日: 2026-02-03 | 时长: 121 分钟" in text
    assert "制作信息: 制作商: Backup Studio | 演员: Actor D" in text
    assert "Metadata源: javlibrary | 角色: backup_cross_check" in text
    assert f"磁力链接: {magnet}" in text


def test_search_bt_read_only_and_format_returns_explicit_adult_source_empty_text_when_fallback_stays_empty() -> None:
    fallback_queries: list[str] = []

    async def unexpected_pt_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("PT search should not be used for adult-only fallback")

    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        fallback_queries.append(query)
        if query == "SSIS-123":
            return [
                {
                    "title": "Dune 2021 1080p",
                    "source": "magnet:?xt=urn:btih:2222222222222222222222222222222222222222",
                    "infoHash": "2222222222222222222222222222222222222222",
                    "indexerName": "Nyaa",
                    "sourceProvider": "nyaa",
                }
            ]
        return []

    service = SearchMediaService(unexpected_pt_search, raw_search_func=fake_raw_search)
    text = _run(service.search_bt_read_only_and_format("SSIS-123", adult_only=True))

    assert fallback_queries == ["SSIS-123", "SSIS 123", "SSIS123"]
    assert text == ADULT_BT_SOURCE_EMPTY_TEXT_TEMPLATE.format(query="SSIS-123")
    assert "下一步" in text
    assert "成人 BT 站点或 Prowlarr 成人索引器" in text


def test_search_bt_read_only_and_format_rejects_helper_only_metadata_as_adult_resource() -> None:
    async def unexpected_pt_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("PT search should not be used for adult-only helper-only rejection")

    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        assert query in {"SSIS-123", "SSIS 123", "SSIS123"}
        return [
            {
                "title": f"{query} helper metadata page",
                "source": "https://www.javlibrary.com/tw/?v=javli0001",
                "indexerName": "javlibrary",
                "sourceProvider": "javlibrary",
                "read_only_adult_content_id": "censored:ssis-123",
                "read_only_adult_display_id": "SSIS-123",
                "read_only_adult_archive_category": "censored",
            }
        ]

    service = SearchMediaService(unexpected_pt_search, raw_search_func=fake_raw_search)
    text = _run(service.search_bt_read_only_and_format("SSIS-123", adult_only=True))

    assert text == ADULT_BT_SOURCE_EMPTY_TEXT_TEMPLATE.format(query="SSIS-123")
    assert "helper metadata page" not in text
    assert "成人资源候选：SSIS-123\n1." not in text


def test_search_bt_read_only_and_format_rejects_generic_prowlarr_indexer_for_adult_fallback() -> None:
    fallback_queries: list[str] = []

    async def unexpected_pt_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("PT search should not be used for adult-only fallback")

    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        fallback_queries.append(query)
        return [
            {
                "title": f"{query} generic PT release",
                "source": "magnet:?xt=urn:btih:3333333333333333333333333333333333333333",
                "infoHash": "3333333333333333333333333333333333333333",
                "indexerName": "IndexerPT",
                "sourceProvider": "prowlarr",
            }
        ]

    service = SearchMediaService(unexpected_pt_search, raw_search_func=fake_raw_search)
    text = _run(service.search_bt_read_only_and_format("SSIS-123", adult_only=True))

    assert fallback_queries == ["SSIS-123", "SSIS 123", "SSIS123"]
    assert text == ADULT_BT_SOURCE_EMPTY_TEXT_TEMPLATE.format(query="SSIS-123")
    assert "generic PT release" not in text


def test_search_bt_read_only_and_format_allows_adult_prowlarr_indexer_for_adult_fallback() -> None:
    fallback_queries: list[str] = []

    async def unexpected_pt_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("PT search should not be used for adult-only fallback")

    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        fallback_queries.append(query)
        if query != "SSIS 123":
            return []
        return [
            {
                "title": "SSIS 123 adult prowlarr release",
                "source": "magnet:?xt=urn:btih:4444444444444444444444444444444444444444",
                "infoHash": "4444444444444444444444444444444444444444",
                "indexerName": "sukebei.nyaa.si",
                "sourceProvider": "prowlarr",
            }
        ]

    service = SearchMediaService(unexpected_pt_search, raw_search_func=fake_raw_search)
    text = _run(service.search_bt_read_only_and_format("SSIS-123", adult_only=True))

    assert fallback_queries == ["SSIS-123", "SSIS 123"]
    assert "成人资源候选：SSIS-123" in text
    assert "SSIS 123 adult prowlarr release" in text


def test_search_bt_read_only_and_format_keeps_generic_no_result_when_adult_fallback_not_enabled() -> None:
    raw_queries: list[str] = []

    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        raw_queries.append(query)
        return []

    service = SearchMediaService(_fake_search_with_results, raw_search_func=fake_raw_search)
    text = _run(service.search_bt_read_only_and_format("SSIS-123"))

    assert raw_queries == ["SSIS-123"]
    assert text == BT_READ_ONLY_NO_RESULT_TEXT_TEMPLATE.format(query="SSIS-123")


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
    assert "只读详情: https://www.javlibrary.com/tw/?v=javli0001" in text


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
        raise httpx.ConnectError("timeout", request=httpx.Request("GET", "https://example.com"))

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


def test_search_bt_read_only_and_format_does_not_apply_helper_to_single_unrelated_candidate() -> None:
    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        assert query == "SSIS-123"
        return [
            {
                "title": "Unrelated comedy collection",
                "source": "magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "infoHash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "seeders": 10,
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
            title="SSIS-123 Secret Mission Nurse",
            detail_url="https://www.javlibrary.com/tw/?v=javli0001",
        )

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=fake_raw_search,
        adult_read_only_lookup_func=fake_helper_lookup,
    )
    text = _run(service.search_bt_read_only_and_format("SSIS-123"))

    assert "1. Unrelated comedy collection" in text
    assert "只读补全:" not in text
    assert "只读标题:" not in text


def test_search_bt_read_only_and_format_ignores_generic_helper_overlap_tokens() -> None:
    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        assert query == "SSIS-123"
        return [
            {
                "title": "Unrelated collection edition",
                "source": "magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "infoHash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "seeders": 10,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "tokyotosho",
                "sourceProvider": "tokyotosho",
            },
            {
                "title": "Another unrelated compilation",
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
            title="SSIS-123 Secret Collection Edition",
            detail_url="https://www.javlibrary.com/tw/?v=javli0001",
        )

    service = SearchMediaService(
        _fake_search_with_results,
        raw_search_func=fake_raw_search,
        adult_read_only_lookup_func=fake_helper_lookup,
    )
    text = _run(service.search_bt_read_only_and_format("SSIS-123"))

    assert "1. Unrelated collection edition" in text
    assert "2. Another unrelated compilation" in text
    assert "只读补全:" not in text
    assert "只读标题:" not in text


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
    assert "只读详情: https://www.javlibrary.com/tw/?v=javli0001" in text


def test_search_bt_batch_preview_and_format_promotes_helper_related_candidate_before_default_slice() -> None:
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
    text = _run(service.search_bt_batch_preview_and_format(BTBatchPreviewRequest(query="SSIS-123")))

    assert "1. Secret Mission Nurse leaked cut" in text
    assert "2. Noise collection complete edition" in text
    assert "Another unrelated compilation" not in text
    assert "只读补全: javlibrary | 番号: SSIS-123 | 分类: censored" in text
    assert BT_BATCH_PREVIEW_NOTICE_TEMPLATE.format(selection="1,2") in text


def test_search_bt_batch_preview_and_format_applies_selected_indexes_after_helper_reorder() -> None:
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
    text = _run(
        service.search_bt_batch_preview_and_format(
            BTBatchPreviewRequest(query="SSIS-123", selected_indexes=(2,), selection_text="2")
        )
    )

    assert "1. Noise collection complete edition" in text
    assert "Secret Mission Nurse leaked cut" not in text
    assert "Another unrelated compilation" not in text
    assert BT_BATCH_PREVIEW_NOTICE_TEMPLATE.format(selection="2") in text


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


def test_search_bt_batch_preview_and_format_for_chat_keeps_helper_reorder_out_of_cached_fields() -> None:
    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        assert query == "SSIS-123"
        return [
            {
                "title": "Noise collection complete edition",
                "source": "magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "infoHash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "indexerName": "tokyotosho",
                "sourceProvider": "tokyotosho",
            },
            {
                "title": "Another unrelated compilation",
                "source": "magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "infoHash": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "indexerName": "tokyotosho",
                "sourceProvider": "tokyotosho",
            },
            {
                "title": "Secret Mission Nurse leaked cut",
                "source": "magnet:?xt=urn:btih:cccccccccccccccccccccccccccccccccccccccc",
                "infoHash": "cccccccccccccccccccccccccccccccccccccccc",
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
    text = _run(
        service.search_bt_batch_preview_and_format_for_chat(
            BTBatchPreviewRequest(query="SSIS-123"),
            chat_id=1001,
        )
    )

    first_cached = service.get_cached_candidate(1001, 1)
    second_cached = service.get_cached_candidate(1001, 2)

    assert "只读补全: javlibrary | 番号: SSIS-123 | 分类: censored" in text
    assert first_cached is not None
    assert second_cached is not None
    assert first_cached["title"] == "Secret Mission Nurse leaked cut"
    assert second_cached["title"] == "Noise collection complete edition"
    assert "read_only_adult_content_id" not in first_cached
    assert "read_only_adult_display_id" not in first_cached
    assert "adult_content_id" not in first_cached
    assert "read_only_adult_content_id" not in second_cached
    assert "read_only_adult_display_id" not in second_cached
    assert "adult_content_id" not in second_cached


def test_search_bt_batch_preview_and_format_for_chat_selected_unrelated_candidate_stays_helper_free() -> None:
    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        assert query == "SSIS-123"
        return [
            {
                "title": "Noise collection complete edition",
                "source": "magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "infoHash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "indexerName": "tokyotosho",
                "sourceProvider": "tokyotosho",
            },
            {
                "title": "Another unrelated compilation",
                "source": "magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "infoHash": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "indexerName": "tokyotosho",
                "sourceProvider": "tokyotosho",
            },
            {
                "title": "Secret Mission Nurse leaked cut",
                "source": "magnet:?xt=urn:btih:cccccccccccccccccccccccccccccccccccccccc",
                "infoHash": "cccccccccccccccccccccccccccccccccccccccc",
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
    text = _run(
        service.search_bt_batch_preview_and_format_for_chat(
            BTBatchPreviewRequest(query="SSIS-123", selected_indexes=(2,), selection_text="2"),
            chat_id=1001,
        )
    )

    cached = service.get_cached_candidate(1001, 1)

    assert "1. Noise collection complete edition" in text
    assert "只读补全:" not in text
    assert "只读标题:" not in text
    assert cached is not None
    assert cached["title"] == "Noise collection complete edition"
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
        raise httpx.ConnectError("bt source unavailable", request=httpx.Request("GET", "https://example.com"))

    service = SearchMediaService(_fake_search_with_results, raw_search_func=fake_raw_search)

    with pytest.raises(httpx.ConnectError, match="bt source unavailable"):
        _run(service.search_bt_read_only_and_format("dune bt"))

    output = capsys.readouterr().out
    assert "[BT 只读搜索失败]" in output
    assert "query=dune bt" in output


def test_search_and_format_returns_relevance_candidates_for_title_only_ambiguous_query() -> None:
    service = SearchMediaService(_fake_search_ambiguous)
    text = _run(service.search_and_format("Dune", chat_id=1001))
    assert "片名可能有多个版本：Dune" not in text
    assert "请补充更具体信息" not in text
    assert "搜索结果：Dune" in text
    assert "Dune (1984) 1080p BluRay (1984)" in text
    assert "Dune (2000) 1080p WEB-DL (2000)" in text
    assert "Dune (2021) 2160p WEB-DL (2021)" in text
    assert not service.is_clarification_pending(1001)
    assert service.get_cached_candidate(1001, 1) is not None


def test_search_and_format_renders_tmdb_enriched_mixed_media_card() -> None:
    seen_queries: list[str] = []

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        if query == "Zombie Detective 2020":
            return [
                {
                    "title": "Zombie Detective S01 1080p WEB-DL",
                    "year": 2020,
                    "size": 2 * 1024 * 1024 * 1024,
                    "indexerName": "IndexerTV",
                    "downloadUrl": "https://example.com/zombie-detective.torrent",
                }
            ]
        return []

    async def fake_tmdb_candidates(title: str, year: str) -> list[TmdbMovie]:
        assert title == "丧尸"
        assert year == ""
        return [
            TmdbMovie(
                title="Zombie Detective",
                original_title="좀비탐정",
                year="2020",
                tmdb_id="111",
                media_type="tv",
                poster_path="/zombie-detective.jpg",
                overview="A detective story with a zombie lead.",
            ),
            TmdbMovie(
                title="Zombie for Sale",
                original_title="기묘한 가족",
                year="2019",
                tmdb_id="222",
                media_type="movie",
                poster_path="/zombie-for-sale.jpg",
                overview="A family comedy about zombies.",
            ),
            TmdbMovie(
                title="All of Us Are Dead",
                original_title="지금 우리 학교는",
                year="2022",
                tmdb_id="333",
                media_type="tv",
                poster_path="/all-of-us-are-dead.jpg",
                overview="A school zombie outbreak thriller.",
            ),
            TmdbMovie(
                title="Train to Busan",
                original_title="부산행",
                year="2016",
                tmdb_id="444",
                media_type="movie",
                poster_path="/train-to-busan.jpg",
                overview="Passengers fight for survival on a fast train.",
            ),
            TmdbMovie(
                title="Kingdom",
                original_title="킹덤",
                year="2019",
                tmdb_id="555",
                media_type="tv",
                poster_path="/kingdom.jpg",
                overview="A Joseon political thriller with zombies.",
            ),
            TmdbMovie(
                title="Zom 100: Bucket List of the Dead",
                original_title="ゾン100〜ゾンビになるまでにしたい100のこと〜",
                year="2023",
                tmdb_id="666",
                media_type="tv",
                poster_path="/zom-100.jpg",
                overview="A zombie comedy about reclaiming life.",
            ),
        ]

    service = SearchMediaService(
        fake_search,
        lookup_media_candidates_func=fake_tmdb_candidates,
    )

    text = _run(service.search_and_format("丧尸", chat_id=1001))

    assert seen_queries == []
    assert text.startswith("候选作品：丧尸 ✓")
    assert "先确认最可能的作品：" not in text
    assert "1. Zombie Detective (2020) | tv" in text
    assert "海报：https://image.tmdb.org/t/p/w500/zombie-detective.jpg" in text
    assert "原名：좀비탐정" in text
    assert "年份：2020" in text
    assert "类型：tv" in text
    assert "简介：A detective story with a zombie lead." in text
    assert "TMDB详情：https://www.themoviedb.org/tv/111" in text
    assert "2. Zombie for Sale (2019) | movie" in text
    assert "原名：기묘한 가족" in text
    assert "年份：2019" in text
    assert "类型：movie" in text
    assert "简介：A family comedy about zombies." in text
    assert "TMDB详情：https://www.themoviedb.org/movie/222" in text
    assert "3. All of Us Are Dead (2022) | tv" in text
    assert "简介：A school zombie outbreak thriller." in text
    assert "TMDB详情：https://www.themoviedb.org/tv/333" in text
    assert "4. Train to Busan (2016) | movie" in text
    assert "简介：Passengers fight for survival on a fast train." in text
    assert "TMDB详情：https://www.themoviedb.org/movie/444" in text
    assert "5. Kingdom (2019) | tv" in text
    assert "简介：A Joseon political thriller with zombies." in text
    assert "TMDB详情：https://www.themoviedb.org/tv/555" in text
    assert "6. Zom 100: Bucket List of the Dead (2023) | tv" not in text
    assert "海报：https://image.tmdb.org/t/p/w500/zombie-for-sale.jpg" in text
    assert "海报：https://image.tmdb.org/t/p/w500/all-of-us-are-dead.jpg" in text
    assert "海报：https://image.tmdb.org/t/p/w500/train-to-busan.jpg" in text
    assert "海报：https://image.tmdb.org/t/p/w500/kingdom.jpg" in text
    assert text.count("海报：https://image.tmdb.org/t/p/w500") == 5
    assert text.count("简介：") == 5
    assert text.count("TMDB详情：https://www.themoviedb.org/") == 5
    cached_candidate = service.get_cached_candidate(1001, 1)
    assert cached_candidate is not None
    assert cached_candidate["candidate_stage"] == "media_candidate"
    assert cached_candidate["media_identity"]["tmdb_id"] == "111"
    assert "downloadUrl" not in cached_candidate


def test_search_and_format_keeps_non_telegram_candidate_confirmation_layout_intact() -> None:
    seen_queries: list[str] = []

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        return []

    async def fake_tmdb_candidates(title: str, year: str) -> list[TmdbMovie]:
        assert title == "你的名字"
        assert year == ""
        return [
            TmdbMovie(
                title="你的名字。",
                original_title="君の名は。",
                year="2016",
                tmdb_id="101",
                media_type="movie",
                poster_path="/your-name.jpg",
                overview="Two teenagers share a supernatural connection.",
            ),
            TmdbMovie(
                title="你的名字 特别收藏版",
                original_title="君の名は。4K Collection",
                year="2017",
                tmdb_id="102",
                media_type="movie",
                poster_path="/your-name-collection.jpg",
                overview="A longer noisy collection title that should stay behind the exact film.",
            ),
        ]

    service = SearchMediaService(
        fake_search,
        lookup_media_candidates_func=fake_tmdb_candidates,
    )

    text = _run(service.search_and_format("你的名字", chat_id=1001, channel="personal_wechat"))

    assert seen_queries == []
    assert text.startswith("【候选作品：你的名字】 ✓")
    assert "候选作品（2 条）" in text
    assert "先确认最可能的作品：" not in text
    assert "▸ 1. 你的名字。 (2016) | movie" in text
    assert "海报：https://image.tmdb.org/t/p/w500/your-name.jpg" in text
    assert "原名：君の名は。" in text
    assert "年份：2016" in text
    assert "类型：movie" in text
    assert "简介：Two teenagers share a supernatural connection." in text
    assert "TMDB详情：https://www.themoviedb.org/movie/101" in text
    assert "▸ 2. 你的名字 特别收藏版 (2017) | movie" in text
    assert "海报：https://image.tmdb.org/t/p/w500/your-name-collection.jpg" in text
    assert "原名：君の名は。4K Collection" in text
    assert "年份：2017" in text
    assert "类型：movie" in text
    assert "简介：A longer noisy collection title that should stay behind the exact film." in text
    assert "TMDB详情：https://www.themoviedb.org/movie/102" in text
    assert "确认作品：直接回复序号，例如 1" in text
    assert "都不对：发送更详细的名称，或直接发送新的名字/关键词重新搜" in text


def test_search_and_format_prefers_media_confirmation_for_strong_cjk_title_before_resource_search() -> None:
    seen_queries: list[str] = []

    async def unexpected_resource_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        return [
            {
                "title": "Your Name 2016 1080p BluRay",
                "year": 2016,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "IndexerMovie",
                "downloadUrl": "https://example.com/your-name.torrent",
            }
        ]

    async def fake_tmdb_candidates(title: str, year: str) -> list[TmdbMovie]:
        assert title == "你的名字"
        assert year == ""
        return [
            TmdbMovie(
                title="你的名字。",
                original_title="君の名は。",
                year="2016",
                tmdb_id="101",
                media_type="movie",
                poster_path="/your-name.jpg",
                overview="Two teenagers share a supernatural connection.",
            ),
            TmdbMovie(
                title="你的名字 特别收藏版",
                original_title="君の名は。4K Collection",
                year="2017",
                tmdb_id="102",
                media_type="movie",
                poster_path="/your-name-collection.jpg",
                overview="A longer noisy collection title that should stay behind the exact film.",
            ),
            TmdbMovie(
                title="你的名字 剧场纪念版",
                original_title="君の名は。 Memorial Edition",
                year="2018",
                tmdb_id="103",
                media_type="movie",
                poster_path="/your-name-memorial.jpg",
                overview="A weaker commemorative release candidate.",
            ),
            TmdbMovie(
                title="你的名字 官方原声带",
                original_title="君の名は。 Original Soundtrack",
                year="2016",
                tmdb_id="104",
                media_type="movie",
                poster_path="/your-name-soundtrack.jpg",
                overview="A soundtrack result that should not stay in the first compact set.",
            ),
            TmdbMovie(
                title="你的名字 4K 修复合集",
                original_title="君の名は。 4K Restoration Collection",
                year="2020",
                tmdb_id="105",
                media_type="movie",
                poster_path="/your-name-4k-collection.jpg",
                overview="Another noisy collection candidate that should be trimmed.",
            ),
        ]

    service = SearchMediaService(
        unexpected_resource_search,
        lookup_media_candidates_func=fake_tmdb_candidates,
    )

    text = _run(service.search_and_format("你的名字", chat_id=1001))

    assert seen_queries == []
    assert "候选作品：你的名字 ✓" in text
    assert "先确认最可能的作品：" not in text
    assert "1. 你的名字。 (2016) | movie" in text
    assert "年份：2016" in text
    assert "类型：movie" in text
    assert "简介：Two teenagers share a supernatural connection." in text
    assert "TMDB详情：https://www.themoviedb.org/movie/101" in text
    assert "2. 你的名字 特别收藏版 (2017) | movie" in text
    assert "年份：2017" in text
    assert "类型：movie" in text
    assert "简介：A longer noisy collection title that should stay behind the exact film." in text
    assert "TMDB详情：https://www.themoviedb.org/movie/102" in text
    assert "3. 你的名字 剧场纪念版 (2018) | movie" in text
    assert "年份：2018" in text
    assert "类型：movie" in text
    assert "简介：A weaker commemorative release candidate." in text
    assert "TMDB详情：https://www.themoviedb.org/movie/103" in text
    assert "4. 你的名字 官方原声带 (2016) | movie" not in text
    assert "4. 你的名字 4K 修复合集 (2020) | movie" not in text
    assert "海报：https://image.tmdb.org/t/p/w500/your-name.jpg" in text
    assert "海报：https://image.tmdb.org/t/p/w500/your-name-collection.jpg" in text
    assert "海报：https://image.tmdb.org/t/p/w500/your-name-memorial.jpg" in text
    assert text.count("海报：https://image.tmdb.org/t/p/w500") == 3
    assert text.count("简介：") == 3
    assert text.count("TMDB详情：https://www.themoviedb.org/") == 3
    assert "站点:" not in text
    assert "链接参考:" not in text
    cached_candidate = service.get_cached_candidate(1001, 1)
    assert cached_candidate is not None
    assert cached_candidate["candidate_stage"] == "media_candidate"
    assert cached_candidate["media_identity"]["tmdb_id"] == "101"


def test_search_and_format_keeps_broad_confirmation_for_short_generic_cjk_query() -> None:
    seen_queries: list[str] = []

    async def unexpected_resource_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        return [
            {
                "title": "Legend 2015 1080p BluRay",
                "year": 2015,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "IndexerMovie",
                "downloadUrl": "https://example.com/legend-2015.torrent",
            }
        ]

    async def fake_tmdb_candidates(title: str, year: str) -> list[TmdbMovie]:
        assert title == "传奇"
        assert year == ""
        return [
            TmdbMovie(
                title="传奇",
                original_title="Legend",
                year="2015",
                tmdb_id="301",
                media_type="movie",
                poster_path="/legend-2015.jpg",
                overview="The Kray twins build a criminal empire in London.",
                popularity=42.0,
                vote_count=1800,
            ),
            TmdbMovie(
                title="传奇办公室",
                original_title="Le Bureau des Légendes",
                year="2015",
                tmdb_id="302",
                media_type="tv",
                poster_path="/legend-bureau.jpg",
                overview="French intelligence officers navigate covert missions.",
                popularity=24.0,
                vote_count=340,
            ),
            TmdbMovie(
                title="传奇联盟",
                original_title="Legend League",
                year="2016",
                tmdb_id="306",
                media_type="movie",
                poster_path="/legend-league.jpg",
                overview="A low-recognition prefix variant that should not crowd out mainstream hits.",
                popularity=5.0,
                vote_count=12,
            ),
            TmdbMovie(
                title="传奇少年",
                original_title="Legend Boy",
                year="2017",
                tmdb_id="307",
                media_type="movie",
                poster_path="/legend-boy.jpg",
                overview="Another weak prefix variant used to stress the candidate sampler.",
                popularity=4.0,
                vote_count=8,
            ),
            TmdbMovie(
                title="黑道传奇",
                original_title="Legend",
                year="2015",
                tmdb_id="303",
                media_type="movie",
                poster_path="/legend-gangster.jpg",
                overview="Another localized title variant for the Kray twins story.",
                popularity=18.0,
                vote_count=220,
            ),
            TmdbMovie(
                title="我是传奇",
                original_title="I Am Legend",
                year="2007",
                tmdb_id="304",
                media_type="movie",
                poster_path="/i-am-legend.jpg",
                overview="A lone survivor searches for a cure in a devastated world.",
                popularity=68.0,
                vote_count=9500,
            ),
            TmdbMovie(
                title="纳尼亚传奇：狮子、女巫和魔衣橱",
                original_title="The Chronicles of Narnia: The Lion, the Witch and the Wardrobe",
                year="2005",
                tmdb_id="305",
                media_type="movie",
                poster_path="/narnia.jpg",
                overview="Children enter a fantasy world through a wardrobe.",
                popularity=55.0,
                vote_count=8200,
            ),
        ]

    service = SearchMediaService(
        unexpected_resource_search,
        lookup_media_candidates_func=fake_tmdb_candidates,
    )

    text = _run(service.search_and_format("传奇", chat_id=1001))

    assert seen_queries == []
    assert text.startswith("候选作品：传奇")
    assert "1. 传奇 (2015) | movie" in text
    assert "我是传奇 (2007) | movie" in text
    assert "纳尼亚传奇" in text
    assert "传奇少年" not in text
    assert text.count("\n1. ") == 1
    assert service.get_cached_candidate(1001, 4) is not None
    assert service.get_cached_candidate(1001, 5) is not None


def test_search_and_format_real_chain_keeps_i_am_legend_in_top_five_for_crowded_legend_page() -> None:
    seen_queries: list[str] = []
    seen_paths: list[str] = []
    client = TmdbClient(api_key="tmdb-key")

    async def unexpected_resource_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        return [
            {
                "title": "Legend 2015 1080p BluRay",
                "year": 2015,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "IndexerMovie",
                "downloadUrl": "https://example.com/legend-2015.torrent",
            }
        ]

    class _FakeTmdbResponse:
        def __init__(self, payload: dict[str, object]) -> None:
            self._payload = payload

        def json(self) -> dict[str, object]:
            return self._payload

    async def fake_get(path: str, params: dict[str, str]) -> _FakeTmdbResponse:
        seen_paths.append(path)
        assert params["query"] == "传奇"
        if path == "/3/search/movie":
            return _FakeTmdbResponse(
                {
                    "results": [
                        {
                            "id": 301,
                            "title": "传奇",
                            "original_title": "Legend",
                            "release_date": "2015-11-20",
                            "poster_path": "/legend-2015.jpg",
                            "overview": "The Kray twins build a criminal empire in London.",
                            "popularity": 42.0,
                            "vote_count": 1800,
                        },
                        {
                            "id": 302,
                            "title": "传奇联盟",
                            "original_title": "Legend League",
                            "release_date": "2016-01-01",
                            "popularity": 5.0,
                            "vote_count": 12,
                        },
                        {
                            "id": 303,
                            "title": "传奇少年",
                            "original_title": "Legend Boy",
                            "release_date": "2017-01-01",
                            "popularity": 4.0,
                            "vote_count": 8,
                        },
                        {
                            "id": 304,
                            "title": "传奇风云",
                            "original_title": "Legend Storm",
                            "release_date": "2018-01-01",
                            "popularity": 3.0,
                            "vote_count": 6,
                        },
                        {
                            "id": 305,
                            "title": "传奇时刻",
                            "original_title": "Legend Moment",
                            "release_date": "2014-01-01",
                            "popularity": 2.8,
                            "vote_count": 5,
                        },
                        {
                            "id": 306,
                            "title": "传奇之路",
                            "original_title": "Road to Legend",
                            "release_date": "2013-01-01",
                            "popularity": 2.5,
                            "vote_count": 5,
                        },
                        {
                            "id": 307,
                            "title": "传奇再起",
                            "original_title": "Legend Reborn",
                            "release_date": "2012-01-01",
                            "popularity": 2.0,
                            "vote_count": 5,
                        },
                        {
                            "id": 308,
                            "title": "黑道传奇",
                            "original_title": "Legend",
                            "release_date": "2015-09-09",
                            "popularity": 18.0,
                            "vote_count": 220,
                        },
                        {
                            "id": 309,
                            "title": "我是传奇",
                            "original_title": "I Am Legend",
                            "release_date": "2007-12-14",
                            "poster_path": "/i-am-legend.jpg",
                            "overview": "A lone survivor searches for a cure in a devastated world.",
                            "popularity": 68.0,
                            "vote_count": 9500,
                        },
                        {
                            "id": 310,
                            "title": "纳尼亚传奇：狮子、女巫和魔衣橱",
                            "original_title": "The Chronicles of Narnia: The Lion, the Witch and the Wardrobe",
                            "release_date": "2005-12-07",
                            "popularity": 55.0,
                            "vote_count": 8200,
                        },
                        {
                            "id": 311,
                            "title": "浴血传奇",
                            "original_title": "Bloody Legend",
                            "release_date": "2011-01-01",
                            "popularity": 80.0,
                            "vote_count": 12000,
                        },
                        {
                            "id": 312,
                            "title": "传奇边缘",
                            "original_title": "Legend Edge",
                            "release_date": "2010-01-01",
                            "popularity": 2.3,
                            "vote_count": 4,
                        },
                    ]
                }
            )
        if path == "/3/search/tv":
            return _FakeTmdbResponse(
                {
                    "results": [
                        {
                            "id": 401,
                            "name": "传奇办公室",
                            "original_name": "Le Bureau des Légendes",
                            "first_air_date": "2015-04-27",
                            "poster_path": "/legend-bureau.jpg",
                            "overview": "French intelligence officers navigate covert missions.",
                            "popularity": 24.0,
                            "vote_count": 340,
                        },
                        {
                            "id": 402,
                            "name": "传奇训练营",
                            "original_name": "Legend Camp",
                            "first_air_date": "2019-02-01",
                            "popularity": 2.0,
                            "vote_count": 4,
                        },
                        {
                            "id": 403,
                            "name": "传奇探案",
                            "original_name": "Legend Detectives",
                            "first_air_date": "2020-01-01",
                            "popularity": 1.9,
                            "vote_count": 3,
                        },
                        {
                            "id": 404,
                            "name": "都市传奇",
                            "original_name": "Urban Legend Files",
                            "first_air_date": "2011-01-01",
                            "popularity": 40.0,
                            "vote_count": 2000,
                        },
                        {
                            "id": 405,
                            "name": "传奇现场",
                            "original_name": "Legend Live",
                            "first_air_date": "2018-01-01",
                            "popularity": 1.8,
                            "vote_count": 2,
                        },
                    ]
                }
            )
        raise AssertionError(f"unexpected TMDB path: {path}")

    client._get = fake_get  # type: ignore[method-assign]
    service = SearchMediaService(
        unexpected_resource_search,
        lookup_media_candidates_func=client.search_media_candidates,
    )

    text = _run(service.search_and_format("传奇", chat_id=1001))

    assert seen_queries == []
    assert seen_paths == ["/3/search/movie", "/3/search/tv"]
    assert text.startswith("候选作品：传奇")
    assert "1. 传奇 (2015) | movie" in text
    assert "2. 传奇办公室 (2015) | tv" in text
    assert "3. 传奇联盟 (2016) | movie" in text
    assert "4. 我是传奇 (2007) | movie" in text
    assert "纳尼亚传奇" in text
    assert "传奇少年" not in text
    assert "浴血传奇" not in text
    cached_candidate = service.get_cached_candidate(1001, 4)
    assert cached_candidate is not None
    assert cached_candidate["title"] == "我是传奇"
    assert service.get_cached_candidate(1001, 5) is not None
    assert service.get_cached_candidate(1001, 6) is None


def test_search_and_format_keeps_compact_confirmation_for_yearless_short_strong_cjk_title() -> None:
    seen_queries: list[str] = []

    async def unexpected_resource_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        return [
            {
                "title": "Lust, Caution 2007 1080p BluRay",
                "year": 2007,
                "size": 5 * 1024 * 1024 * 1024,
                "indexerName": "IndexerMovie",
                "downloadUrl": "https://example.com/lust-caution.torrent",
            }
        ]

    async def fake_tmdb_candidates(title: str, year: str) -> list[TmdbMovie]:
        assert title == "色戒"
        assert year == ""
        return [
            TmdbMovie(
                title="色戒",
                original_title="Lust, Caution",
                year="2007",
                tmdb_id="401",
                media_type="movie",
                poster_path="/lust-caution.jpg",
                overview="An espionage drama set in occupied Shanghai.",
                popularity=36.0,
                vote_count=1600,
            ),
            TmdbMovie(
                title="色戒 导演剪辑版",
                original_title="Lust, Caution Director's Cut",
                year="2007",
                tmdb_id="402",
                media_type="movie",
                poster_path="/lust-caution-director.jpg",
                overview="A lower-priority cut of the same film.",
                popularity=9.0,
                vote_count=40,
            ),
            TmdbMovie(
                title="色戒 幕后纪事",
                original_title="Lust, Caution Behind the Scenes",
                year="2008",
                tmdb_id="403",
                media_type="movie",
                poster_path="/lust-caution-behind.jpg",
                overview="A featurette that should stay behind the main film.",
                popularity=6.0,
                vote_count=18,
            ),
            TmdbMovie(
                title="色戒 十五周年纪念版",
                original_title="Lust, Caution 15th Anniversary Edition",
                year="2022",
                tmdb_id="404",
                media_type="movie",
                poster_path="/lust-caution-anniversary.jpg",
                overview="A commemorative re-release that should be trimmed from the compact set.",
                popularity=3.0,
                vote_count=9,
            ),
            TmdbMovie(
                title="色戒 原声带",
                original_title="Lust, Caution Original Soundtrack",
                year="2007",
                tmdb_id="405",
                media_type="movie",
                poster_path="/lust-caution-soundtrack.jpg",
                overview="A soundtrack item that should not make the first confirmation page.",
                popularity=2.0,
                vote_count=4,
            ),
            TmdbMovie(
                title="情陷色戒",
                original_title="Temptation Around Lust, Caution",
                year="2011",
                tmdb_id="406",
                media_type="movie",
                popularity=1.5,
                vote_count=3,
            ),
        ]

    service = SearchMediaService(
        unexpected_resource_search,
        lookup_media_candidates_func=fake_tmdb_candidates,
    )

    text = _run(service.search_and_format("色戒", chat_id=1001))

    assert seen_queries == []
    assert text.startswith("候选作品：色戒")
    assert "1. 色戒 (2007) | movie" in text
    assert "2. 色戒 导演剪辑版 (2007) | movie" in text
    assert "3. 色戒 幕后纪事 (2008) | movie" in text
    assert "4. 色戒 十五周年纪念版 (2022) | movie" not in text
    assert "5. 色戒 原声带 (2007) | movie" not in text
    assert "情陷色戒" not in text
    assert service.get_cached_candidate(1001, 3) is not None
    assert service.get_cached_candidate(1001, 4) is None
    assert service.get_cached_candidate(1001, 5) is None


def test_search_and_format_real_chain_keeps_compact_confirmation_for_short_strong_cjk_title() -> None:
    seen_queries: list[str] = []
    client = TmdbClient(api_key="tmdb-key")

    async def unexpected_resource_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        return [
            {
                "title": "Lust, Caution 2007 1080p BluRay",
                "year": 2007,
                "size": 5 * 1024 * 1024 * 1024,
                "indexerName": "IndexerMovie",
                "downloadUrl": "https://example.com/lust-caution.torrent",
            }
        ]

    class _FakeTmdbResponse:
        def __init__(self, payload: dict[str, object]) -> None:
            self._payload = payload

        def json(self) -> dict[str, object]:
            return self._payload

    async def fake_get(path: str, params: dict[str, str]) -> _FakeTmdbResponse:
        assert params["query"] == "色戒"
        if path == "/3/search/movie":
            return _FakeTmdbResponse(
                {
                    "results": [
                        {
                            "id": 401,
                            "title": "色戒",
                            "original_title": "Lust, Caution",
                            "release_date": "2007-11-01",
                            "poster_path": "/lust-caution.jpg",
                            "overview": "An espionage drama set in occupied Shanghai.",
                            "popularity": 36.0,
                            "vote_count": 1600,
                        },
                        {
                            "id": 402,
                            "title": "色戒 导演剪辑版",
                            "original_title": "Lust, Caution Director's Cut",
                            "release_date": "2007-12-01",
                            "poster_path": "/lust-caution-director.jpg",
                            "overview": "A lower-priority cut of the same film.",
                            "popularity": 9.0,
                            "vote_count": 40,
                        },
                        {
                            "id": 403,
                            "title": "色戒 幕后纪事",
                            "original_title": "Lust, Caution Behind the Scenes",
                            "release_date": "2008-01-01",
                            "poster_path": "/lust-caution-behind.jpg",
                            "overview": "A featurette that should stay behind the main film.",
                            "popularity": 6.0,
                            "vote_count": 18,
                        },
                        {
                            "id": 404,
                            "title": "色戒 十五周年纪念版",
                            "original_title": "Lust, Caution 15th Anniversary Edition",
                            "release_date": "2022-01-01",
                            "poster_path": "/lust-caution-anniversary.jpg",
                            "overview": "A commemorative re-release that should be trimmed from the compact set.",
                            "popularity": 3.0,
                            "vote_count": 9,
                        },
                        {
                            "id": 405,
                            "title": "情陷色戒",
                            "original_title": "Temptation Around Lust, Caution",
                            "release_date": "2011-01-01",
                            "poster_path": "/temptation-around-lust-caution.jpg",
                            "overview": "A mainstream contains-style title that should not blow the query back open.",
                            "popularity": 51.0,
                            "vote_count": 6200,
                        },
                    ]
                }
            )
        if path == "/3/search/tv":
            return _FakeTmdbResponse({"results": []})
        raise AssertionError(f"unexpected TMDB path: {path}")

    client._get = fake_get  # type: ignore[method-assign]
    service = SearchMediaService(
        unexpected_resource_search,
        lookup_media_candidates_func=client.search_media_candidates,
    )

    text = _run(service.search_and_format("色戒", chat_id=1001))

    assert seen_queries == []
    assert text.startswith("候选作品：色戒")
    assert "1. 色戒 (2007) | movie" in text
    assert "2. 色戒 导演剪辑版 (2007) | movie" in text
    assert "3. 色戒 幕后纪事 (2008) | movie" in text
    assert "4. 色戒 十五周年纪念版 (2022) | movie" not in text
    assert "情陷色戒" not in text
    assert service.get_cached_candidate(1001, 3) is not None
    assert service.get_cached_candidate(1001, 4) is None


@pytest.mark.parametrize("query", ["魔戒", "指环王", "Lord of the Rings"])
def test_search_and_format_prefers_lord_of_the_rings_franchise_for_explicit_alias_query(query: str) -> None:
    seen_queries: list[str] = []

    async def unexpected_resource_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        return [
            {
                "title": "The Lord of the Rings Trilogy 1080p BluRay",
                "year": 2001,
                "size": 18 * 1024 * 1024 * 1024,
                "indexerName": "IndexerMovie",
                "downloadUrl": "https://example.com/lotr-trilogy.torrent",
            }
        ]

    async def fake_tmdb_candidates(title: str, year: str) -> list[TmdbMovie]:
        assert title == query
        assert year == ""
        return [
            TmdbMovie(
                title="魔戒迷踪",
                original_title="Ringers: Lord of the Fans",
                year="2005",
                tmdb_id="201",
                media_type="movie",
                poster_path="/ringers.jpg",
                overview="A documentary about Tolkien fandom.",
            ),
            TmdbMovie(
                title="牙狼：魔戒之花",
                original_title="GARO: Makai no Hana",
                year="2014",
                tmdb_id="202",
                media_type="tv",
                poster_path="/garo-makai.jpg",
                overview="A GARO side story that should not outrank Lord of the Rings.",
            ),
            TmdbMovie(
                title="指环王：护戒使者",
                original_title="The Lord of the Rings: The Fellowship of the Ring",
                year="2001",
                tmdb_id="203",
                media_type="movie",
                poster_path="/lotr-fellowship.jpg",
                overview="Frodo begins the journey to destroy the One Ring.",
            ),
            TmdbMovie(
                title="指环王：双塔奇兵",
                original_title="The Lord of the Rings: The Two Towers",
                year="2002",
                tmdb_id="204",
                media_type="movie",
                poster_path="/lotr-two-towers.jpg",
                overview="The fellowship fights on across Middle-earth.",
            ),
            TmdbMovie(
                title="指环王：王者无敌",
                original_title="The Lord of the Rings: The Return of the King",
                year="2003",
                tmdb_id="205",
                media_type="movie",
                poster_path="/lotr-return-king.jpg",
                overview="Aragorn claims the throne as the final battle begins.",
            ),
        ]

    service = SearchMediaService(
        unexpected_resource_search,
        lookup_media_candidates_func=fake_tmdb_candidates,
    )

    text = _run(service.search_and_format(query, chat_id=1001))

    assert seen_queries == []
    assert text.startswith(f"候选作品：{query}")
    assert "1. 指环王:护戒使者 (2001) | movie" in text
    assert "2. 指环王:双塔奇兵 (2002) | movie" in text
    assert "3. 指环王:王者无敌 (2003) | movie" in text
    assert "魔戒迷踪" not in text
    assert "牙狼：魔戒之花" not in text
    assert "海报：https://image.tmdb.org/t/p/w500/lotr-fellowship.jpg" in text
    assert "站点:" not in text
    assert "链接参考:" not in text
    cached_candidate = service.get_cached_candidate(1001, 1)
    assert cached_candidate is not None
    assert cached_candidate["candidate_stage"] == "media_candidate"
    assert cached_candidate["media_identity"]["tmdb_id"] == "203"
    assert service.get_cached_candidate(1001, 4) is None
    assert service.get_cached_candidate(1001, 5) is None


def test_search_and_format_with_explicit_year_prefers_media_confirmation_before_resource_search() -> None:
    seen_queries: list[str] = []

    async def unexpected_resource_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        return [
            {
                "title": "Dune 2021 2160p WEB-DL",
                "year": 2021,
                "size": 8 * 1024 * 1024 * 1024,
                "indexerName": "IndexerMovie",
                "downloadUrl": "https://example.com/dune-2021.torrent",
            }
        ]

    async def fake_tmdb_candidates(title: str, year: str) -> list[TmdbMovie]:
        assert title == "Dune"
        assert year == "2021"
        return [
            TmdbMovie(
                title="Dune",
                original_title="Dune",
                year="2021",
                tmdb_id="438631",
                media_type="movie",
                poster_path="/dune.jpg",
                overview="Paul Atreides leads nomadic tribes in a battle to control Arrakis.",
            ),
            TmdbMovie(
                title="Children of Dune",
                original_title="Children of Dune",
                year="2003",
                tmdb_id="12345",
                media_type="tv",
                poster_path="/children-of-dune.jpg",
                overview="A lower relevance sequel candidate.",
            ),
        ]

    service = SearchMediaService(
        unexpected_resource_search,
        lookup_media_candidates_func=fake_tmdb_candidates,
    )

    text = _run(service.search_and_format("Dune 2021", chat_id=1001))

    assert seen_queries == []
    assert text.startswith("候选作品：Dune 2021")
    assert "1. Dune (2021) | movie" in text
    assert "海报：https://image.tmdb.org/t/p/w500/dune.jpg" in text
    cached_candidate = service.get_cached_candidate(1001, 1)
    assert cached_candidate is not None
    assert cached_candidate["candidate_stage"] == "media_candidate"
    assert cached_candidate["media_identity"]["tmdb_id"] == "438631"


def test_build_search_request_context_marks_low_confidence_year_query_as_needs_confirmation() -> None:
    seen_queries: list[str] = []

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        return []

    async def fake_tmdb_candidates(title: str, year: str) -> list[TmdbMovie]:
        assert title == "沙丘"
        assert year == "2021"
        return [
            TmdbMovie(
                title="Dune",
                original_title="Dune",
                year="2021",
                tmdb_id="438631",
                media_type="movie",
                poster_path="/dune.jpg",
                overview="Paul Atreides leads nomadic tribes in a battle to control Arrakis.",
            ),
            TmdbMovie(
                title="Children of Dune",
                original_title="Children of Dune",
                year="2003",
                tmdb_id="12345",
                media_type="tv",
                poster_path="/children-of-dune.jpg",
                overview="A lower relevance sequel candidate.",
            ),
        ]

    context = _run(
        build_search_request_context(
            user_query="沙丘 2021",
            search_func=fake_search,
            lookup_movie_func=None,
            lookup_media_candidates_func=fake_tmdb_candidates,
        )
    )

    assert context.media_identity_state == "needs_confirmation"
    assert context.tmdb_identity_movie is None
    assert context.resolved_query == ""
    assert context.raw_results == ()
    assert seen_queries == []


def test_search_and_format_with_explicit_year_but_low_confidence_tmdb_hit_prefers_confirmation() -> None:
    seen_queries: list[str] = []

    async def unexpected_resource_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        return [
            {
                "title": "Dune 2021 2160p WEB-DL",
                "year": 2021,
                "size": 8 * 1024 * 1024 * 1024,
                "indexerName": "IndexerMovie",
                "downloadUrl": "https://example.com/dune-2021.torrent",
            }
        ]

    async def fake_tmdb_candidates(title: str, year: str) -> list[TmdbMovie]:
        assert title == "沙丘"
        assert year == "2021"
        return [
            TmdbMovie(
                title="Dune",
                original_title="Dune",
                year="2021",
                tmdb_id="438631",
                media_type="movie",
                poster_path="/dune.jpg",
                overview="Paul Atreides leads nomadic tribes in a battle to control Arrakis.",
            ),
            TmdbMovie(
                title="Children of Dune",
                original_title="Children of Dune",
                year="2003",
                tmdb_id="12345",
                media_type="tv",
                poster_path="/children-of-dune.jpg",
                overview="A lower relevance sequel candidate.",
            ),
        ]

    service = SearchMediaService(
        unexpected_resource_search,
        lookup_media_candidates_func=fake_tmdb_candidates,
    )

    text = _run(service.search_and_format("沙丘 2021", chat_id=1001))

    assert seen_queries == []
    assert text.startswith("候选作品：沙丘 2021")
    assert "1. Dune (2021) | movie" in text
    assert "2. Children of Dune (2003) | tv" in text


def test_search_resources_for_selected_media_keeps_existing_related_title_order_after_confirmation() -> None:
    seen_queries: list[str] = []

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        if query == "Zombie Detective 2020":
            return [
                {
                    "title": "Zombie Detective S01 1080p WEB-DL",
                    "year": 2020,
                    "size": 2 * 1024 * 1024 * 1024,
                    "indexerName": "IndexerTV",
                    "downloadUrl": "https://example.com/zombie-detective.torrent",
                }
            ]
        return []

    async def fake_tmdb_candidates(title: str, year: str) -> list[TmdbMovie]:
        assert title == "Zombie Detective"
        assert year == "2020"
        return [
            TmdbMovie(
                title="Zombie Detective",
                original_title="좀비탐정",
                year="2020",
                tmdb_id="111",
                media_type="tv",
                poster_path="/zombie-detective.jpg",
                overview="A detective story with a zombie lead.",
            )
        ]

    service = SearchMediaService(
        fake_search,
        lookup_media_candidates_func=fake_tmdb_candidates,
    )

    confirmation_text = _run(service.search_and_format("Zombie Detective 2020", chat_id=1001))
    text = _run(service.search_resources_for_selected_media(1001, "1"))

    assert seen_queries == ["좀비탐정 2020", "좀비탐정", "Zombie Detective 2020"]
    assert confirmation_text.startswith("候选作品：Zombie Detective 2020")
    assert text.startswith("电影海报卡片")
    assert "候选作品：" not in text
    assert "片名: 좀비탐정" in text
    assert "别名: Zombie Detective" in text
    assert "- tv | 좀비탐정 / Zombie Detective | 2020" in text
    assert "- tv | Zombie Detective / 좀비탐정 | 2020" not in text


def test_search_and_format_falls_back_to_resource_search_when_tmdb_candidates_are_empty() -> None:
    seen_queries: list[str] = []

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        if query == "Dune 2021":
            return [
                {
                    "title": "Dune 2021 2160p WEB-DL",
                    "year": 2021,
                    "size": 8 * 1024 * 1024 * 1024,
                    "indexerName": "IndexerMovie",
                    "downloadUrl": "https://example.com/dune-2021.torrent",
                }
            ]
        return []

    async def fake_tmdb_candidates(title: str, year: str) -> list[TmdbMovie]:
        assert title == "Dune"
        assert year == "2021"
        return []

    service = SearchMediaService(
        fake_search,
        lookup_media_candidates_func=fake_tmdb_candidates,
    )

    text = _run(service.search_and_format("Dune 2021", chat_id=1001))

    assert seen_queries == ["Dune 2021"]
    assert text.startswith("电影海报卡片")
    assert "搜索结果：Dune 2021" in text
    assert "Dune 2021 2160p WEB-DL (2021)" in text
    assert "候选作品：Dune 2021" not in text


def test_search_resources_for_selected_media_returns_resource_results_after_confirmation() -> None:
    seen_queries: list[str] = []

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        if query == "좀비탐정 2020":
            return [
                {
                    "title": "Zombie Detective S01 1080p WEB-DL",
                    "year": 2020,
                    "size": 2 * 1024 * 1024 * 1024,
                    "indexerName": "IndexerTV",
                    "downloadUrl": "https://example.com/zombie-detective.torrent",
                }
            ]
        return []

    async def fake_tmdb_candidates(title: str, year: str) -> list[TmdbMovie]:
        assert title == "丧尸"
        assert year == ""
        return [
            TmdbMovie(
                title="Zombie Detective",
                original_title="좀비탐정",
                year="2020",
                tmdb_id="111",
                media_type="tv",
                poster_path="/zombie-detective.jpg",
                overview="A detective story with a zombie lead.",
            ),
        ]

    service = SearchMediaService(
        fake_search,
        lookup_media_candidates_func=fake_tmdb_candidates,
    )

    _run(service.search_and_format("丧尸", chat_id=1001))
    text = _run(service.search_resources_for_selected_media(1001, "1"))

    assert seen_queries == ["좀비탐정 2020"]
    assert "搜索结果：Zombie Detective" in text
    assert "Zombie Detective S01 1080p WEB-DL (2020)" in text
    cached_candidate = service.get_cached_candidate(1001, 1)
    assert cached_candidate is not None
    assert cached_candidate["downloadUrl"] == "https://example.com/zombie-detective.torrent"


def test_candidate_state_store_persists_candidates_for_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()

    before_restart_store = CandidateStateStore(repo=CandidateMappingRepo(database))
    assert before_restart_store.persist_search_candidates(
        chat_id=1001,
        candidates=[{"title": "Dune", "year": 2021}],
    )

    after_restart_store = CandidateStateStore(repo=CandidateMappingRepo(SqliteDatabase(str(db_path))))
    load_result = after_restart_store.get_cached_candidate_load_result(1001, 1)

    assert load_result.load_failed is False
    assert load_result.candidate == {"title": "Dune", "year": 2021}


def test_clarification_state_store_persists_query_for_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()

    before_restart_store = ClarificationStateStore(repo=ClarificationRepo(database))
    assert before_restart_store.set_pending(chat_id=1001, query="Dune")

    after_restart_store = ClarificationStateStore(repo=ClarificationRepo(SqliteDatabase(str(db_path))))

    assert after_restart_store.is_pending(1001) is True
    assert after_restart_store.pending_by_chat[1001] == "Dune"


def test_clarification_pending_persists_for_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()

    before_restart_service = SearchMediaService(
        _fake_search_empty,
        clarification_repo=ClarificationRepo(database),
    )
    _run(before_restart_service.search_and_format("unknown", chat_id=1001))

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
            raise ClarificationPersistenceError(f"db down for {chat_id}")

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
        _fake_search_empty,
        clarification_repo=MissingRowClarificationRepo(database),
    )

    text = _run(service.search_and_format("unknown", chat_id=1001))

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
            raise CandidatePersistenceError("db down")

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
    repo = type(
        "BoomRepo",
        (),
        {"clear_pending": lambda self, chat_id: (_ for _ in ()).throw(ClarificationPersistenceError("db down"))},
    )()
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
    repo = type(
        "BoomRepo",
        (),
        {"get_pending_query": lambda self, chat_id: (_ for _ in ()).throw(ClarificationPersistenceError("db down"))},
    )()
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
    failed_repo = type(
        "BoomRepo",
        (),
        {"get_pending_query": lambda self, chat_id: (_ for _ in ()).throw(ClarificationPersistenceError("db down"))},
    )()

    missing_service = SearchMediaService(_fake_search_with_results, clarification_repo=missing_repo)
    failed_service = SearchMediaService(_fake_search_with_results, clarification_repo=failed_repo)

    missing_result = missing_service._load_persisted_clarification_query(chat_id=1001)
    failed_result = failed_service._load_persisted_clarification_query(chat_id=1001)

    assert missing_result.query is None
    assert missing_result.load_failed is False
    assert failed_result.query is None
    assert failed_result.load_failed is True


def test_clear_cached_candidates_logs_candidate_persistence_failure(capsys) -> None:
    repo = type(
        "BoomRepo",
        (),
        {"clear_candidates": lambda self, chat_id: (_ for _ in ()).throw(CandidatePersistenceError("db down"))},
    )()
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
    repo = type(
        "BoomRepo",
        (),
        {"get_candidate": lambda self, chat_id, index: (_ for _ in ()).throw(CandidatePersistenceError("db down"))},
    )()
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
    monkeypatch.setattr("app.services.search_media._load_bt_scoring_rules", lambda: custom_rules)

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
        raise httpx.ConnectError("tmdb unavailable", request=httpx.Request("GET", "https://example.com"))

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
        raise httpx.ConnectError("tmdb unavailable", request=httpx.Request("GET", "https://example.com"))

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)

    text = _run(service.search_and_format("Dune 2021"))

    assert text == NO_RESULT_TEXT_TEMPLATE.format(query="Dune 2021")
    assert seen_queries == ["Dune 2021", "Dune"]
    output = capsys.readouterr().out
    assert "[TMDB 查询失败]" in output
    assert "query=Dune 2021" in output


def test_search_and_format_logs_search_backend_failure(capsys) -> None:
    async def fake_search(_: str) -> list[dict[str, object]]:
        raise httpx.ConnectError("indexer unavailable", request=httpx.Request("GET", "https://example.com"))

    service = SearchMediaService(fake_search)

    with pytest.raises(httpx.ConnectError, match="indexer unavailable"):
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

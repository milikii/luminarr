from __future__ import annotations

from collections.abc import Awaitable
from pathlib import Path

import pytest

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
    return TmdbMovie(title="Interstellar", original_title="Interstellar", year="2014")


def test_search_and_format_uses_tmdb_first_when_available() -> None:
    service = SearchMediaService(
        _fake_search_tmdb_hit,
        lookup_movie_func=_fake_lookup_tmdb_movie,
    )
    text = _run(service.search_and_format("星际穿越 (2014)"))
    assert "电影海报卡片" in text
    assert "片名: Interstellar" in text
    assert "年份: 2014" in text
    assert "别名: -" in text
    assert "搜索结果：星际穿越 (2014)" in text
    assert "Interstellar 2014 1080p BluRay" in text


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


def test_search_and_format_deduplicates_same_tmdb_titles() -> None:
    seen_queries: list[str] = []

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        return []

    async def fake_tmdb_lookup(_: str, __: str) -> TmdbMovie | None:
        return TmdbMovie(title="Interstellar", original_title="Interstellar", year="2014")

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("星际穿越 (2014)"))

    assert seen_queries == ["Interstellar 2014"]
    assert text == NO_RESULT_TEXT_TEMPLATE.format(query="星际穿越 (2014)")


def test_search_and_format_fallbacks_to_normalized_query_when_tmdb_empty() -> None:
    seen_query: dict[str, str] = {}

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_query["value"] = query
        return []

    async def fake_tmdb_lookup(title: str, year: str) -> TmdbMovie | None:
        assert title == "Dune"
        assert year == "2021"
        return None

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("Dune (2021)"))
    assert seen_query["value"] == "Dune 2021"
    assert text == NO_RESULT_TEXT_TEMPLATE.format(query="Dune (2021)")


def test_search_and_format_fallbacks_to_normalized_query_when_tmdb_failed() -> None:
    seen_query: dict[str, str] = {}

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_query["value"] = query
        return []

    async def fake_tmdb_lookup(_: str, __: str) -> TmdbMovie | None:
        raise RuntimeError("tmdb unavailable")

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("Dune 2021"))
    assert seen_query["value"] == "Dune 2021"
    assert text == NO_RESULT_TEXT_TEMPLATE.format(query="Dune 2021")


def test_search_and_format_logs_tmdb_failure(capsys) -> None:
    async def fake_search(query: str) -> list[dict[str, object]]:
        assert query == "Dune 2021"
        return []

    async def fake_tmdb_lookup(_: str, __: str) -> TmdbMovie | None:
        raise RuntimeError("tmdb unavailable")

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)

    text = _run(service.search_and_format("Dune 2021"))

    assert text == NO_RESULT_TEXT_TEMPLATE.format(query="Dune 2021")
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

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest

from app.bot.private_chat_search_runtime import (
    SEARCH_CAPABILITY_UNAVAILABLE_TEXT,
    SEARCH_CAPABILITY_UNAVAILABLE_TEXT_BOT_DATA_KEY,
)
from app.bot.private_chat_bt_read_only_runtime import handle_bt_read_only_query
from app.bot import telegram_bot as tg
from app.services.search_media import SearchMediaService


class _ExecutionGate:
    def __init__(self) -> None:
        self.actions: list[str] = []

    async def run(self, action: str, callback):
        self.actions.append(action)
        return await callback()


async def _fake_search(query: str) -> list[dict[str, object]]:
    return [
        {
            "title": f"title-{query}",
            "year": 2026,
            "quality": "1080p",
            "size": 1024,
            "indexerName": "idx",
            "downloadUrl": "https://example.com/sample.torrent",
        }
    ]


def test_handle_bt_read_only_query_returns_false_for_other_queries() -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()

    handled = asyncio.run(
        handle_bt_read_only_query(
            query="dune",
            bot_data={},
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            tg=tg,
        )
    )

    assert handled is False
    assert execution_gate.actions == []
    reply_func.assert_not_awaited()


def test_handle_bt_read_only_query_routes_to_raw_search() -> None:
    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        assert query == "Frieren S01E01"
        return [
            {
                "title": "title-Frieren S01E01",
                "source": "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12",
                "infoHash": "abcdef1234567890abcdef1234567890abcdef12",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()

    handled = asyncio.run(
        handle_bt_read_only_query(
            query="bt搜 Frieren S01E01",
            bot_data={tg.SEARCH_SERVICE_KEY: SearchMediaService(_fake_search, raw_search_func=fake_raw_search)},
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            tg=tg,
        )
    )

    assert handled is True
    assert execution_gate.actions == [tg.ACTION_BT_READ_ONLY_HELPER]
    reply_func.assert_awaited_once()
    sent_text = reply_func.await_args.args[0]
    assert "BT 只读探索结果：Frieren S01E01" in sent_text
    assert "title-Frieren S01E01" in sent_text


def test_handle_bt_read_only_query_uses_adult_only_fallback_for_adult_prefix() -> None:
    raw_queries: list[str] = []

    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        raw_queries.append(query)
        if query == "SSIS-123":
            return [
                {
                    "title": "Dune 2021 1080p",
                    "source": "magnet:?xt=urn:btih:1111111111111111111111111111111111111111",
                    "infoHash": "1111111111111111111111111111111111111111",
                    "indexerName": "Nyaa",
                    "sourceProvider": "nyaa",
                }
            ]
        if query == "SSIS 123":
            return [
                {
                    "title": "title-SSIS 123",
                    "source": "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12",
                    "infoHash": "abcdef1234567890abcdef1234567890abcdef12",
                    "indexerName": "tokyotosho",
                    "sourceProvider": "tokyotosho",
                }
            ]
        return []

    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()

    handled = asyncio.run(
        handle_bt_read_only_query(
            query="成人搜 SSIS-123",
            bot_data={tg.SEARCH_SERVICE_KEY: SearchMediaService(_fake_search, raw_search_func=fake_raw_search)},
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            tg=tg,
        )
    )

    assert handled is True
    assert execution_gate.actions == [tg.ACTION_BT_READ_ONLY_HELPER]
    assert raw_queries == ["SSIS-123", "SSIS 123"]
    reply_func.assert_awaited_once()
    sent_text = reply_func.await_args.args[0]
    assert "成人资源候选：SSIS-123" in sent_text
    assert "title-SSIS 123" in sent_text
    assert "Dune 2021 1080p" not in sent_text


def test_handle_bt_read_only_query_routes_batch_preview_to_search_service() -> None:
    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        assert query == "Frieren S01E01"
        return [
            {
                "title": "title-Frieren S01E01",
                "source": "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12",
                "infoHash": "abcdef1234567890abcdef1234567890abcdef12",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
            {
                "title": "title-Frieren S01E02",
                "source": "magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "infoHash": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
        ]

    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()

    handled = asyncio.run(
        handle_bt_read_only_query(
            query="bt批量 Frieren S01E01 1-2",
            bot_data={tg.SEARCH_SERVICE_KEY: SearchMediaService(_fake_search, raw_search_func=fake_raw_search)},
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            tg=tg,
        )
    )

    assert handled is True
    assert execution_gate.actions == [tg.ACTION_BT_READ_ONLY_HELPER]
    reply_func.assert_awaited_once()
    sent_text = reply_func.await_args.args[0]
    assert "BT 批量预览结果：Frieren S01E01" in sent_text
    assert "title-Frieren S01E01" in sent_text
    assert "title-Frieren S01E02" in sent_text


def test_handle_bt_read_only_query_still_routes_to_raw_search_when_general_search_capability_is_disabled() -> None:
    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        assert query == "Frieren S01E01"
        return [
            {
                "title": "title-Frieren S01E01",
                "source": "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12",
                "infoHash": "abcdef1234567890abcdef1234567890abcdef12",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()

    handled = asyncio.run(
        handle_bt_read_only_query(
            query="bt搜 Frieren S01E01",
            bot_data={
                tg.SEARCH_SERVICE_KEY: SearchMediaService(_fake_search, raw_search_func=fake_raw_search),
                SEARCH_CAPABILITY_UNAVAILABLE_TEXT_BOT_DATA_KEY: SEARCH_CAPABILITY_UNAVAILABLE_TEXT,
            },
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            tg=tg,
        )
    )

    assert handled is True
    assert execution_gate.actions == [tg.ACTION_BT_READ_ONLY_HELPER]
    reply_func.assert_awaited_once()
    sent_text = reply_func.await_args.args[0]
    assert "BT 只读探索结果：Frieren S01E01" in sent_text
    assert "title-Frieren S01E01" in sent_text


def test_handle_bt_batch_preview_still_routes_when_general_search_capability_is_disabled() -> None:
    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        assert query == "Frieren S01E01"
        return [
            {
                "title": "title-Frieren S01E01",
                "source": "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12",
                "infoHash": "abcdef1234567890abcdef1234567890abcdef12",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
            {
                "title": "title-Frieren S01E02",
                "source": "magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "infoHash": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
        ]

    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()

    handled = asyncio.run(
        handle_bt_read_only_query(
            query="bt批量 Frieren S01E01 1-2",
            bot_data={
                tg.SEARCH_SERVICE_KEY: SearchMediaService(_fake_search, raw_search_func=fake_raw_search),
                SEARCH_CAPABILITY_UNAVAILABLE_TEXT_BOT_DATA_KEY: SEARCH_CAPABILITY_UNAVAILABLE_TEXT,
            },
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            tg=tg,
        )
    )

    assert handled is True
    assert execution_gate.actions == [tg.ACTION_BT_READ_ONLY_HELPER]
    reply_func.assert_awaited_once()
    sent_text = reply_func.await_args.args[0]
    assert "BT 批量预览结果：Frieren S01E01" in sent_text
    assert "title-Frieren S01E01" in sent_text
    assert "title-Frieren S01E02" in sent_text


def test_handle_bt_read_only_query_replies_service_not_ready_without_search_service() -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()

    handled = asyncio.run(
        handle_bt_read_only_query(
            query="bt搜 Frieren S01E01",
            bot_data={},
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            tg=tg,
        )
    )

    assert handled is True
    assert execution_gate.actions == []
    reply_func.assert_awaited_once_with(tg.SERVICE_NOT_READY_TEXT)


def test_handle_bt_read_only_query_logs_failure_and_replies_safe_text(
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def failing_raw_search(_: str) -> list[dict[str, object]]:
        request = httpx.Request("GET", "https://example.com/search?q=Frieren")
        raise httpx.ConnectError("network down", request=request)

    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()

    handled = asyncio.run(
        handle_bt_read_only_query(
            query="bt search Frieren S01E01",
            bot_data={tg.SEARCH_SERVICE_KEY: SearchMediaService(_fake_search, raw_search_func=failing_raw_search)},
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            tg=tg,
        )
    )
    captured = capsys.readouterr()

    assert handled is True
    assert execution_gate.actions == [tg.ACTION_BT_READ_ONLY_HELPER]
    reply_func.assert_awaited_once_with(tg.BT_READ_ONLY_HELPER_FAILED_TEXT)
    assert "[BT 只读探索失败]" in captured.out
    assert "Frieren S01E01" in captured.out
    assert "network down" in captured.out

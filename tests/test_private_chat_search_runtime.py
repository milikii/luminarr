from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from app.bot import telegram_bot as tg
from app.bot.private_chat_search_runtime import (
    SEARCH_CAPABILITY_UNAVAILABLE_TEXT,
    SEARCH_CAPABILITY_UNAVAILABLE_TEXT_BOT_DATA_KEY,
    handle_search_query_fallback,
)
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
            "title": "Dune (2021)",
            "year": 2021,
            "quality": "1080p",
            "size": 1024,
            "indexerName": "idx",
            "downloadUrl": "https://example.com/sample.torrent",
        }
    ]


def test_handle_search_query_fallback_routes_to_search_service() -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()

    handled = asyncio.run(
        handle_search_query_fallback(
            query="dune",
            bot_data={tg.SEARCH_SERVICE_KEY: SearchMediaService(_fake_search)},
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            channel="personal_wechat",
            bt_processing_path_pending=False,
            bt_classification_pending=False,
            tg=tg,
        )
    )

    assert handled is True
    assert execution_gate.actions == [tg.ACTION_SEARCH_MEDIA]
    reply_func.assert_awaited_once()
    sent_text = reply_func.await_args.args[0]
    assert sent_text.startswith("【搜索：dune】 ✓")
    assert "Dune (2021)" in sent_text


def test_handle_search_query_fallback_replies_processing_path_reminder_first() -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()

    handled = asyncio.run(
        handle_search_query_fallback(
            query="dune",
            bot_data={tg.SEARCH_SERVICE_KEY: SearchMediaService(_fake_search)},
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            channel="telegram",
            bt_processing_path_pending=True,
            bt_classification_pending=False,
            tg=tg,
        )
    )

    assert handled is True
    assert execution_gate.actions == []
    reply_func.assert_awaited_once_with(tg.BT_PROCESSING_PATH_PENDING_REMINDER_TEXT)


def test_handle_search_query_fallback_replies_classification_reminder_when_needed() -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()

    handled = asyncio.run(
        handle_search_query_fallback(
            query="dune",
            bot_data={tg.SEARCH_SERVICE_KEY: SearchMediaService(_fake_search)},
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            channel="telegram",
            bt_processing_path_pending=False,
            bt_classification_pending=True,
            tg=tg,
        )
    )

    assert handled is True
    assert execution_gate.actions == []
    reply_func.assert_awaited_once_with(tg.BT_CLASSIFICATION_PENDING_REMINDER_TEXT)


def test_handle_search_query_fallback_replies_service_not_ready_without_search_service() -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()

    handled = asyncio.run(
        handle_search_query_fallback(
            query="dune",
            bot_data={},
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            channel="telegram",
            bt_processing_path_pending=False,
            bt_classification_pending=False,
            tg=tg,
        )
    )

    assert handled is True
    assert execution_gate.actions == []
    reply_func.assert_awaited_once_with(tg.SERVICE_NOT_READY_TEXT)


def test_handle_search_query_fallback_replies_explicit_unavailable_text_when_search_capability_is_disabled() -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()

    handled = asyncio.run(
        handle_search_query_fallback(
            query="dune",
            bot_data={
                tg.SEARCH_SERVICE_KEY: SearchMediaService(_fake_search),
                SEARCH_CAPABILITY_UNAVAILABLE_TEXT_BOT_DATA_KEY: SEARCH_CAPABILITY_UNAVAILABLE_TEXT,
            },
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            channel="telegram",
            bt_processing_path_pending=False,
            bt_classification_pending=False,
            tg=tg,
        )
    )

    assert handled is True
    assert execution_gate.actions == []
    reply_func.assert_awaited_once_with(SEARCH_CAPABILITY_UNAVAILABLE_TEXT)

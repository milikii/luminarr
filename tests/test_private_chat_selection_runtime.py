from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from app.bot import telegram_bot as tg
from app.bot.private_chat_selection_runtime import handle_digit_selection_query
from app.services.add_to_downloader import AddToDownloaderService
from app.services.search_media import SearchMediaService


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


class _ExecutionGateStub:
    def __init__(self) -> None:
        self.run = AsyncMock(side_effect=self._run)

    async def _run(self, _action: str, handler):
        result = handler()
        if asyncio.iscoroutine(result):
            return await result
        return result


def test_handle_digit_selection_query_blocks_when_clarification_pending() -> None:
    reply_text = AsyncMock()
    search_service = SearchMediaService(_fake_search)
    search_service.is_clarification_pending = Mock(return_value=True)  # type: ignore[method-assign]

    handled = asyncio.run(
        handle_digit_selection_query(
            bot_data={tg.SEARCH_SERVICE_KEY: search_service},
            execution_gate=_ExecutionGateStub(),
            reply_func=reply_text,
            query="1",
            chat_id=1001,
            user_id=2001,
            channel="telegram",
            resolve_downloader_execution=lambda: (None, None),
            tg=tg,
        )
    )

    assert handled is True
    reply_text.assert_awaited_once_with(tg.CLARIFICATION_SELECTION_BLOCKED_TEXT)


def test_handle_digit_selection_query_routes_add_by_selection() -> None:
    reply_text = AsyncMock()
    execution_gate = _ExecutionGateStub()
    search_service = SearchMediaService(_fake_search)
    search_service.is_clarification_pending = Mock(return_value=False)  # type: ignore[method-assign]
    add_service = AddToDownloaderService(search_service, AsyncMock())
    add_service.add_by_selection = AsyncMock(return_value="下载待确认")  # type: ignore[method-assign]

    handled = asyncio.run(
        handle_digit_selection_query(
            bot_data={
                tg.SEARCH_SERVICE_KEY: search_service,
                tg.ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
            },
            execution_gate=execution_gate,
            reply_func=reply_text,
            query="1",
            chat_id=1001,
            user_id=2001,
            channel="personal_wechat",
            resolve_downloader_execution=lambda: (
                SimpleNamespace(name="pt-main", downloader_type="transmission", download_dir="/downloads"),
                None,
            ),
            tg=tg,
        )
    )

    assert handled is True
    execution_gate.run.assert_awaited_once()
    add_service.add_by_selection.assert_awaited_once_with(
        1001,
        "1",
        user_id=2001,
        channel="personal_wechat",
        downloader_name="pt-main",
        downloader_type="transmission",
        download_dir="/downloads",
    )
    reply_text.assert_awaited_once_with("下载待确认")


def test_handle_digit_selection_query_stops_on_clarification_lookup_failure() -> None:
    reply_text = AsyncMock()
    search_service = SearchMediaService(_fake_search)
    search_service.is_clarification_pending = Mock(return_value=None)  # type: ignore[method-assign]

    handled = asyncio.run(
        handle_digit_selection_query(
            bot_data={tg.SEARCH_SERVICE_KEY: search_service},
            execution_gate=_ExecutionGateStub(),
            reply_func=reply_text,
            query="1",
            chat_id=1001,
            user_id=2001,
            channel="telegram",
            resolve_downloader_execution=lambda: (None, None),
            tg=tg,
        )
    )

    assert handled is True
    reply_text.assert_awaited_once_with(tg.SERVICE_NOT_READY_TEXT)

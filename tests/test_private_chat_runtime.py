from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from app.bot.private_chat_runtime import dispatch_private_chat_text
from app.bot.telegram_bot import (
    ADD_TO_DOWNLOADER_SERVICE_KEY,
    BT_PROCESSING_PATH_PROMPT_TEXT,
    GET_DOWNLOAD_STATUS_SERVICE_KEY,
    IMPORT_TO_LIBRARY_SERVICE_KEY,
    SEARCH_SERVICE_KEY,
)
from app.services.add_to_downloader import AddToDownloaderService
from app.services.get_download_status import GetDownloadStatusService
from app.services.import_to_library import ImportToLibraryService
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


def _build_bot_data() -> dict[str, object]:
    search_service = SearchMediaService(_fake_search)
    return {
        SEARCH_SERVICE_KEY: search_service,
        ADD_TO_DOWNLOADER_SERVICE_KEY: AddToDownloaderService(search_service, AsyncMock()),
        GET_DOWNLOAD_STATUS_SERVICE_KEY: GetDownloadStatusService(AsyncMock()),
        IMPORT_TO_LIBRARY_SERVICE_KEY: ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies"),
    }


def test_dispatch_private_chat_text_routes_search_without_telegram_update() -> None:
    reply_text = AsyncMock()

    asyncio.run(
        dispatch_private_chat_text(
            query="dune",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data=_build_bot_data(),
        )
    )

    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "搜索结果：dune" in sent_text
    assert "title-dune" in sent_text


def test_dispatch_private_chat_text_routes_bt_prompt_without_telegram_update() -> None:
    reply_text = AsyncMock()

    asyncio.run(
        dispatch_private_chat_text(
            query="magnet:?xt=urn:btih:abcdef1234567890",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data=_build_bot_data(),
        )
    )

    reply_text.assert_awaited_once_with(BT_PROCESSING_PATH_PROMPT_TEXT)

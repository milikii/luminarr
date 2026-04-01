from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.bot.telegram_bot import SEARCH_SERVICE_KEY, SERVICE_NOT_READY_TEXT, build_application, handle_message
from app.services.search_media import SearchMediaService


async def _fake_search(query: str) -> list[dict[str, object]]:
    return [
        {
            "title": f"title-{query}",
            "year": 2026,
            "quality": "1080p",
            "size": 1024,
            "indexerName": "idx",
        }
    ]


def test_handle_message_replies_search_result() -> None:
    reply_text = AsyncMock()
    message = SimpleNamespace(text="dune", reply_text=reply_text)
    update = SimpleNamespace(effective_message=message)
    search_service = SearchMediaService(_fake_search)
    context = SimpleNamespace(application=SimpleNamespace(bot_data={SEARCH_SERVICE_KEY: search_service}))

    asyncio.run(handle_message(update, context))

    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "搜索结果：dune" in sent_text
    assert "title-dune" in sent_text


def test_handle_message_replies_service_not_ready() -> None:
    reply_text = AsyncMock()
    message = SimpleNamespace(text="dune", reply_text=reply_text)
    update = SimpleNamespace(effective_message=message)
    context = SimpleNamespace(application=SimpleNamespace(bot_data={}))
    asyncio.run(handle_message(update, context))
    reply_text.assert_awaited_once_with(SERVICE_NOT_READY_TEXT)


def test_build_application_registers_service() -> None:
    service = SearchMediaService(_fake_search)
    application = build_application("token", service)
    assert application.bot_data[SEARCH_SERVICE_KEY] is service

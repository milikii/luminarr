from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from app.bot.channel_identity import project_channel_chat_id, project_channel_user_id
from app.bot.telegram_bot import (
    ADD_TO_DOWNLOADER_SERVICE_KEY,
    GET_DOWNLOAD_STATUS_SERVICE_KEY,
    IMPORT_TO_LIBRARY_SERVICE_KEY,
    SEARCH_SERVICE_KEY,
)
from app.bot.wecom_adapter import (
    WECOM_CHANNEL,
    WeComPrivateTextEvent,
    handle_wecom_private_text_event,
    parse_wecom_private_text_event,
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


def _build_wecom_private_text_xml(text: str) -> str:
    return (
        "<xml>"
        "<ToUserName><![CDATA[wwcorp123]]></ToUserName>"
        "<FromUserName><![CDATA[zhangsan]]></FromUserName>"
        "<CreateTime>1711111111</CreateTime>"
        "<MsgType><![CDATA[text]]></MsgType>"
        f"<Content><![CDATA[{text}]]></Content>"
        "<MsgId>9876543210123456</MsgId>"
        "<AgentID>1000002</AgentID>"
        "</xml>"
    )


def test_parse_wecom_private_text_event_reads_private_text_xml() -> None:
    event = parse_wecom_private_text_event(_build_wecom_private_text_xml("dune"))

    assert event == WeComPrivateTextEvent(
        corp_id="wwcorp123",
        user_id="zhangsan",
        msg_id="9876543210123456",
        agent_id="1000002",
        text="dune",
    )


def test_parse_wecom_private_text_event_ignores_non_text_or_missing_content() -> None:
    image_xml = _build_wecom_private_text_xml("dune").replace("><![CDATA[text]]>", "><![CDATA[image]]>")
    empty_content_xml = _build_wecom_private_text_xml("").replace("<Content><![CDATA[]]></Content>", "<Content></Content>")

    assert parse_wecom_private_text_event(image_xml) is None
    assert parse_wecom_private_text_event(empty_content_xml) is None


def test_handle_wecom_private_text_event_projects_ids_and_routes_into_shared_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatch_private_chat_text = AsyncMock()
    reply_text_func = AsyncMock()
    monkeypatch.setattr("app.bot.wecom_adapter.dispatch_private_chat_text", dispatch_private_chat_text)

    event = asyncio.run(
        handle_wecom_private_text_event(
            payload_xml=_build_wecom_private_text_xml("dune"),
            bot_data=_build_bot_data(),
            reply_text_func=reply_text_func,
        )
    )

    assert event == WeComPrivateTextEvent(
        corp_id="wwcorp123",
        user_id="zhangsan",
        msg_id="9876543210123456",
        agent_id="1000002",
        text="dune",
    )
    dispatch_private_chat_text.assert_awaited_once()
    assert dispatch_private_chat_text.await_args.kwargs["query"] == "dune"
    assert dispatch_private_chat_text.await_args.kwargs["chat_id"] == project_channel_chat_id(
        channel=WECOM_CHANNEL,
        external_chat_id="zhangsan",
    )
    assert dispatch_private_chat_text.await_args.kwargs["user_id"] == project_channel_user_id(
        channel=WECOM_CHANNEL,
        external_user_id="zhangsan",
    )


def test_handle_wecom_private_text_event_routes_into_shared_runtime() -> None:
    reply_text_func = AsyncMock()

    asyncio.run(
        handle_wecom_private_text_event(
            payload_xml=_build_wecom_private_text_xml("dune"),
            bot_data=_build_bot_data(),
            reply_text_func=reply_text_func,
        )
    )

    reply_text_func.assert_awaited_once()
    event, reply_text = reply_text_func.await_args.args
    assert isinstance(event, WeComPrivateTextEvent)
    assert event.user_id == "zhangsan"
    assert "搜索结果：dune" in reply_text
    assert "title-dune" in reply_text

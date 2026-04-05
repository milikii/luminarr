from __future__ import annotations

import asyncio
import json
import urllib.request
from unittest.mock import AsyncMock

import pytest

from app.bot.channel_identity import project_channel_chat_id, project_channel_user_id
from app.bot.feishu_adapter import (
    FEISHU_CHANNEL,
    FeishuPrivateTextEvent,
    build_feishu_reply_text_func,
    get_feishu_url_verification_challenge,
    handle_feishu_private_text_event,
    handle_feishu_webhook_http_request,
    parse_feishu_private_text_event,
)
from app.bot.feishu_webhook_server import (
    FeishuWebhookServerConfig,
    start_feishu_webhook_server,
    stop_feishu_webhook_server,
)
from app.bot.telegram_bot import (
    ADD_TO_DOWNLOADER_SERVICE_KEY,
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


def _build_feishu_private_text_payload(text: str) -> dict[str, object]:
    return {
        "schema": "2.0",
        "header": {
            "event_id": "feishu-event-1",
            "event_type": "im.message.receive_v1",
        },
        "event": {
            "sender": {
                "sender_id": {
                    "open_id": "ou_feishu_user_1",
                }
            },
            "message": {
                "message_id": "om_feishu_message_1",
                "chat_id": "oc_feishu_chat_1",
                "chat_type": "p2p",
                "message_type": "text",
                "content": f'{{"text":"{text}"}}',
            },
        },
    }


def test_project_channel_identity_is_stable_and_channel_scoped() -> None:
    projected_chat_id = project_channel_chat_id(channel=FEISHU_CHANNEL, external_chat_id="oc_feishu_chat_1")
    projected_chat_id_again = project_channel_chat_id(channel=FEISHU_CHANNEL, external_chat_id="oc_feishu_chat_1")
    projected_user_id = project_channel_user_id(channel=FEISHU_CHANNEL, external_user_id="ou_feishu_user_1")
    telegram_like_chat_id = project_channel_chat_id(channel="telegram", external_chat_id="oc_feishu_chat_1")

    assert projected_chat_id > 0
    assert projected_user_id > 0
    assert projected_chat_id == projected_chat_id_again
    assert projected_chat_id != projected_user_id
    assert projected_chat_id != telegram_like_chat_id


def test_get_feishu_url_verification_challenge_reads_challenge() -> None:
    challenge = get_feishu_url_verification_challenge(
        {
            "type": "url_verification",
            "challenge": "challenge-token",
        }
    )

    assert challenge == "challenge-token"


def test_parse_feishu_private_text_event_reads_private_text() -> None:
    event = parse_feishu_private_text_event(_build_feishu_private_text_payload("dune"))

    assert event == FeishuPrivateTextEvent(
        event_id="feishu-event-1",
        message_id="om_feishu_message_1",
        chat_id="oc_feishu_chat_1",
        user_open_id="ou_feishu_user_1",
        text="dune",
    )


def test_parse_feishu_private_text_event_ignores_non_private_or_non_text_messages() -> None:
    group_payload = _build_feishu_private_text_payload("dune")
    group_payload["event"]["message"]["chat_type"] = "group"  # type: ignore[index]

    file_payload = _build_feishu_private_text_payload("dune")
    file_payload["event"]["message"]["message_type"] = "file"  # type: ignore[index]

    assert parse_feishu_private_text_event(group_payload) is None
    assert parse_feishu_private_text_event(file_payload) is None


def test_handle_feishu_private_text_event_routes_into_shared_runtime() -> None:
    reply_text_func = AsyncMock()

    asyncio.run(
        handle_feishu_private_text_event(
            payload=_build_feishu_private_text_payload("dune"),
            bot_data=_build_bot_data(),
            reply_text_func=reply_text_func,
        )
    )

    reply_text_func.assert_awaited_once()
    event, reply_text = reply_text_func.await_args.args
    assert isinstance(event, FeishuPrivateTextEvent)
    assert event.chat_id == "oc_feishu_chat_1"
    assert "搜索结果：dune" in reply_text
    assert "title-dune" in reply_text


def test_build_feishu_reply_text_func_sends_back_to_original_chat() -> None:
    event = FeishuPrivateTextEvent(
        event_id="feishu-event-1",
        message_id="om_feishu_message_1",
        chat_id="oc_feishu_chat_1",
        user_open_id="ou_feishu_user_1",
        text="dune",
    )

    class FakeFeishuClient:
        def __init__(self) -> None:
            self.send_private_text = AsyncMock(return_value="om_reply_1")

    client = FakeFeishuClient()
    reply_text_func = build_feishu_reply_text_func(client)  # type: ignore[arg-type]

    message_id = asyncio.run(reply_text_func(event, "搜索结果：dune"))

    assert message_id == "om_reply_1"
    client.send_private_text.assert_awaited_once_with(chat_id="oc_feishu_chat_1", text="搜索结果：dune")


def test_handle_feishu_webhook_http_request_returns_challenge_json() -> None:
    response = asyncio.run(
        handle_feishu_webhook_http_request(
            body=json.dumps({"type": "url_verification", "challenge": "challenge-token"}),
            bot_data=_build_bot_data(),
            reply_text_func=AsyncMock(),
        )
    )

    assert response.status_code == 200
    assert json.loads(response.body.decode("utf-8")) == {"challenge": "challenge-token"}


def test_handle_feishu_webhook_http_request_rejects_invalid_json() -> None:
    response = asyncio.run(
        handle_feishu_webhook_http_request(
            body="{",
            bot_data=_build_bot_data(),
            reply_text_func=AsyncMock(),
        )
    )

    assert response.status_code == 400
    assert json.loads(response.body.decode("utf-8")) == {"code": 400, "msg": "invalid request body"}


def test_feishu_webhook_server_routes_real_http_post_into_shared_runtime() -> None:
    reply_text_func = AsyncMock()

    async def exercise() -> tuple[int, dict[str, object]]:
        try:
            runtime = start_feishu_webhook_server(
                loop=asyncio.get_running_loop(),
                config=FeishuWebhookServerConfig(host="127.0.0.1", port=0, path="/feishu/webhook"),
                bot_data=_build_bot_data(),
                reply_text_func=reply_text_func,
            )
        except PermissionError as error:
            pytest.skip(f"当前环境禁止本地端口监听：{error}")
        try:
            status_code, payload = await asyncio.to_thread(
                _post_json,
                f"http://127.0.0.1:{runtime.port}/feishu/webhook",
                _build_feishu_private_text_payload("dune"),
            )
            return status_code, payload
        finally:
            stop_feishu_webhook_server(runtime)

    status_code, payload = asyncio.run(exercise())

    assert status_code == 200
    assert payload == {"code": 0}
    reply_text_func.assert_awaited_once()


def _post_json(url: str, payload: dict[str, object]) -> tuple[int, dict[str, object]]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.status, json.loads(response.read().decode("utf-8"))

from __future__ import annotations

import asyncio
import hashlib
import json
import urllib.request
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.bot.channel_identity import project_channel_chat_id, project_channel_user_id
from app.bot.feishu_adapter import (
    FEISHU_CHANNEL,
    FEISHU_ENCRYPT_KEY_BOT_DATA_KEY,
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
    CLEANUP_DOWNLOADED_SOURCE_SERVICE_KEY,
    GET_DOWNLOAD_STATUS_SERVICE_KEY,
    IMPORT_TO_LIBRARY_SERVICE_KEY,
    SEARCH_SERVICE_KEY,
    SERVICE_NOT_READY_TEXT,
)
from app.db.job_event_repo import JobEventRepo
from app.db.sqlite import SqliteDatabase
from app.services.add_to_downloader import AddToDownloaderService
from app.services.cleanup_downloaded_source import CleanupDownloadedSourceService
from app.services.cleanup_downloaded_source import (
    CLEANUP_INSPECT_QUERY_USAGE_TEXT,
    CLEANUP_QUERY_USAGE_TEXT,
)
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


def _build_bot_data(
    *,
    cleanup_service: CleanupDownloadedSourceService | None = None,
) -> dict[str, object]:
    search_service = SearchMediaService(_fake_search)
    bot_data = {
        SEARCH_SERVICE_KEY: search_service,
        ADD_TO_DOWNLOADER_SERVICE_KEY: AddToDownloaderService(search_service, AsyncMock()),
        GET_DOWNLOAD_STATUS_SERVICE_KEY: GetDownloadStatusService(AsyncMock()),
        IMPORT_TO_LIBRARY_SERVICE_KEY: ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies"),
        FEISHU_ENCRYPT_KEY_BOT_DATA_KEY: "encrypt-key-42",
    }
    if cleanup_service is not None:
        bot_data[CLEANUP_DOWNLOADED_SOURCE_SERVICE_KEY] = cleanup_service
    return bot_data


def _build_cleanup_service(tmp_path: Path) -> tuple[CleanupDownloadedSourceService, Path, Path]:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    target_dir = tmp_path / "library"
    target_dir.mkdir(parents=True)
    target_file = target_dir / "Dune (2021).mkv"
    target_file.hardlink_to(source_file)

    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    event_repo = JobEventRepo(database)
    event_repo.append_event(
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message=str(target_file),
        source_path=str(source_file),
        target_path=str(target_file),
    )
    return CleanupDownloadedSourceService(event_repo), source_file, target_file


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


def test_handle_feishu_private_text_event_routes_cleanup_inspect_into_shared_runtime(
    tmp_path: Path,
) -> None:
    cleanup_service, source_file, target_file = _build_cleanup_service(tmp_path)
    reply_text_func = AsyncMock()

    asyncio.run(
        handle_feishu_private_text_event(
            payload=_build_feishu_private_text_payload("cleanup inspect 87"),
            bot_data=_build_bot_data(cleanup_service=cleanup_service),
            reply_text_func=reply_text_func,
        )
    )

    reply_text_func.assert_awaited_once()
    event, reply_text = reply_text_func.await_args.args
    assert isinstance(event, FeishuPrivateTextEvent)
    assert "清理预检结果：" in reply_text
    assert "当前 guardrail: 允许 cleanup" in reply_text
    assert "cleanup hash-87 / 清理 hash-87：实际清理下载源资产" in reply_text
    assert source_file.exists()
    assert target_file.exists()


def test_handle_feishu_private_text_event_routes_cleanup_execution_into_shared_runtime(
    tmp_path: Path,
) -> None:
    cleanup_service, source_file, target_file = _build_cleanup_service(tmp_path)
    reply_text_func = AsyncMock()

    asyncio.run(
        handle_feishu_private_text_event(
            payload=_build_feishu_private_text_payload("cleanup 87"),
            bot_data=_build_bot_data(cleanup_service=cleanup_service),
            reply_text_func=reply_text_func,
        )
    )

    reply_text_func.assert_awaited_once()
    event, reply_text = reply_text_func.await_args.args
    assert isinstance(event, FeishuPrivateTextEvent)
    assert "已清理下载源资产" in reply_text
    assert "cleanup inspect hash-87 / 清理检查 hash-87：只读预检，不删除任何文件" in reply_text
    assert not source_file.exists()
    assert target_file.exists()


def test_handle_feishu_private_text_event_routes_bare_cleanup_usage_into_shared_runtime(
    tmp_path: Path,
) -> None:
    reply_text_func = AsyncMock()

    asyncio.run(
        handle_feishu_private_text_event(
            payload=_build_feishu_private_text_payload("cleanup"),
            bot_data=_build_bot_data(cleanup_service=CleanupDownloadedSourceService(JobEventRepo(_make_database(tmp_path)))),
            reply_text_func=reply_text_func,
        )
    )

    reply_text_func.assert_awaited_once()
    event, reply_text = reply_text_func.await_args.args
    assert isinstance(event, FeishuPrivateTextEvent)
    assert reply_text == CLEANUP_QUERY_USAGE_TEXT


def test_handle_feishu_private_text_event_routes_bare_cleanup_inspect_usage_into_shared_runtime(
    tmp_path: Path,
) -> None:
    reply_text_func = AsyncMock()

    asyncio.run(
        handle_feishu_private_text_event(
            payload=_build_feishu_private_text_payload("cleanup inspect"),
            bot_data=_build_bot_data(cleanup_service=CleanupDownloadedSourceService(JobEventRepo(_make_database(tmp_path)))),
            reply_text_func=reply_text_func,
        )
    )

    reply_text_func.assert_awaited_once()
    event, reply_text = reply_text_func.await_args.args
    assert isinstance(event, FeishuPrivateTextEvent)
    assert reply_text == CLEANUP_INSPECT_QUERY_USAGE_TEXT


def test_handle_feishu_private_text_event_routes_bare_cleanup_usage_in_chinese_into_shared_runtime(
    tmp_path: Path,
) -> None:
    reply_text_func = AsyncMock()

    asyncio.run(
        handle_feishu_private_text_event(
            payload=_build_feishu_private_text_payload("清理"),
            bot_data=_build_bot_data(cleanup_service=CleanupDownloadedSourceService(JobEventRepo(_make_database(tmp_path)))),
            reply_text_func=reply_text_func,
        )
    )

    reply_text_func.assert_awaited_once()
    event, reply_text = reply_text_func.await_args.args
    assert isinstance(event, FeishuPrivateTextEvent)
    assert reply_text == CLEANUP_QUERY_USAGE_TEXT


def test_handle_feishu_private_text_event_routes_bare_cleanup_inspect_usage_in_chinese_into_shared_runtime(
    tmp_path: Path,
) -> None:
    reply_text_func = AsyncMock()

    asyncio.run(
        handle_feishu_private_text_event(
            payload=_build_feishu_private_text_payload("清理检查"),
            bot_data=_build_bot_data(cleanup_service=CleanupDownloadedSourceService(JobEventRepo(_make_database(tmp_path)))),
            reply_text_func=reply_text_func,
        )
    )

    reply_text_func.assert_awaited_once()
    event, reply_text = reply_text_func.await_args.args
    assert isinstance(event, FeishuPrivateTextEvent)
    assert reply_text == CLEANUP_INSPECT_QUERY_USAGE_TEXT


@pytest.mark.parametrize(
    ("query", "expected_action"),
    [
        ("cleanup hash-87", "cleanup"),
        ("cleanup inspect hash-87", "cleanup_inspect"),
    ],
)
def test_handle_feishu_private_text_event_logs_cleanup_service_not_ready(
    query: str,
    expected_action: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reply_text_func = AsyncMock()

    asyncio.run(
        handle_feishu_private_text_event(
            payload=_build_feishu_private_text_payload(query),
            bot_data=_build_bot_data(),
            reply_text_func=reply_text_func,
        )
    )
    captured = capsys.readouterr()

    reply_text_func.assert_awaited_once()
    event, reply_text = reply_text_func.await_args.args
    assert isinstance(event, FeishuPrivateTextEvent)
    assert reply_text == SERVICE_NOT_READY_TEXT
    assert "[cleanup 服务未就绪]" in captured.out
    assert f"动作={expected_action}" in captured.out
    assert query in captured.out
    assert "[处理建议]" in captured.out
    assert "cleanup_downloaded_source_service" in captured.out


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
            headers=None,
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
            headers=None,
            bot_data=_build_bot_data(),
            reply_text_func=AsyncMock(),
        )
    )

    assert response.status_code == 400
    assert json.loads(response.body.decode("utf-8")) == {"code": 400, "msg": "invalid request body"}


def test_handle_feishu_webhook_http_request_rejects_missing_signature() -> None:
    body = json.dumps(_build_feishu_private_text_payload("dune"), ensure_ascii=False)
    response = asyncio.run(
        handle_feishu_webhook_http_request(
            body=body,
            headers={
                "X-Lark-Request-Timestamp": "1711111111",
                "X-Lark-Request-Nonce": "nonce-1",
            },
            bot_data=_build_bot_data(),
            reply_text_func=AsyncMock(),
        )
    )

    assert response.status_code == 401
    assert json.loads(response.body.decode("utf-8")) == {"code": 401, "msg": "missing request signature"}


def test_handle_feishu_webhook_http_request_rejects_invalid_timestamp() -> None:
    body = json.dumps(_build_feishu_private_text_payload("dune"), ensure_ascii=False)
    response = asyncio.run(
        handle_feishu_webhook_http_request(
            body=body,
            headers={
                "X-Lark-Request-Timestamp": "abc",
                "X-Lark-Request-Nonce": "nonce-1",
                "X-Lark-Signature": "sig-1",
            },
            bot_data=_build_bot_data(),
            reply_text_func=AsyncMock(),
        )
    )

    assert response.status_code == 400
    assert json.loads(response.body.decode("utf-8")) == {"code": 400, "msg": "invalid request timestamp"}


def test_handle_feishu_webhook_http_request_rejects_invalid_signature() -> None:
    body = json.dumps(_build_feishu_private_text_payload("dune"), ensure_ascii=False)
    response = asyncio.run(
        handle_feishu_webhook_http_request(
            body=body,
            headers={
                "X-Lark-Request-Timestamp": "1711111111",
                "X-Lark-Request-Nonce": "nonce-1",
                "X-Lark-Signature": "bad-signature",
            },
            bot_data=_build_bot_data(),
            reply_text_func=AsyncMock(),
        )
    )

    assert response.status_code == 401
    assert json.loads(response.body.decode("utf-8")) == {"code": 401, "msg": "invalid request signature"}


def test_handle_feishu_webhook_http_request_routes_cleanup_execution_into_shared_runtime(
    tmp_path: Path,
) -> None:
    cleanup_service, source_file, target_file = _build_cleanup_service(tmp_path)
    reply_text_func = AsyncMock()
    body = json.dumps(_build_feishu_private_text_payload("cleanup 87"), ensure_ascii=False)

    response = asyncio.run(
        handle_feishu_webhook_http_request(
            body=body,
            headers=_build_signature_headers(body=body, encrypt_key="encrypt-key-42"),
            bot_data=_build_bot_data(cleanup_service=cleanup_service),
            reply_text_func=reply_text_func,
        )
    )

    assert response.status_code == 200
    assert json.loads(response.body.decode("utf-8")) == {"code": 0}
    reply_text_func.assert_awaited_once()
    event, reply_text = reply_text_func.await_args.args
    assert isinstance(event, FeishuPrivateTextEvent)
    assert "已清理下载源资产" in reply_text
    assert "cleanup inspect hash-87 / 清理检查 hash-87：只读预检，不删除任何文件" in reply_text
    assert not source_file.exists()
    assert target_file.exists()


def test_handle_feishu_webhook_http_request_routes_cleanup_execution_in_chinese_into_shared_runtime(
    tmp_path: Path,
) -> None:
    cleanup_service, source_file, target_file = _build_cleanup_service(tmp_path)
    reply_text_func = AsyncMock()
    body = json.dumps(_build_feishu_private_text_payload("清理 87"), ensure_ascii=False)

    response = asyncio.run(
        handle_feishu_webhook_http_request(
            body=body,
            headers=_build_signature_headers(body=body, encrypt_key="encrypt-key-42"),
            bot_data=_build_bot_data(cleanup_service=cleanup_service),
            reply_text_func=reply_text_func,
        )
    )

    assert response.status_code == 200
    assert json.loads(response.body.decode("utf-8")) == {"code": 0}
    reply_text_func.assert_awaited_once()
    event, reply_text = reply_text_func.await_args.args
    assert isinstance(event, FeishuPrivateTextEvent)
    assert "已清理下载源资产" in reply_text
    assert "cleanup inspect hash-87 / 清理检查 hash-87：只读预检，不删除任何文件" in reply_text
    assert not source_file.exists()
    assert target_file.exists()


def test_handle_feishu_webhook_http_request_routes_cleanup_inspect_into_shared_runtime(
    tmp_path: Path,
) -> None:
    cleanup_service, source_file, target_file = _build_cleanup_service(tmp_path)
    reply_text_func = AsyncMock()
    body = json.dumps(_build_feishu_private_text_payload("cleanup inspect 87"), ensure_ascii=False)

    response = asyncio.run(
        handle_feishu_webhook_http_request(
            body=body,
            headers=_build_signature_headers(body=body, encrypt_key="encrypt-key-42"),
            bot_data=_build_bot_data(cleanup_service=cleanup_service),
            reply_text_func=reply_text_func,
        )
    )

    assert response.status_code == 200
    assert json.loads(response.body.decode("utf-8")) == {"code": 0}
    reply_text_func.assert_awaited_once()
    event, reply_text = reply_text_func.await_args.args
    assert isinstance(event, FeishuPrivateTextEvent)
    assert "清理预检结果：" in reply_text
    assert "当前 guardrail: 允许 cleanup" in reply_text
    assert "cleanup hash-87 / 清理 hash-87：实际清理下载源资产" in reply_text
    assert source_file.exists()
    assert target_file.exists()


def test_handle_feishu_webhook_http_request_routes_cleanup_inspect_in_chinese_into_shared_runtime(
    tmp_path: Path,
) -> None:
    cleanup_service, source_file, target_file = _build_cleanup_service(tmp_path)
    reply_text_func = AsyncMock()
    body = json.dumps(_build_feishu_private_text_payload("清理检查 87"), ensure_ascii=False)

    response = asyncio.run(
        handle_feishu_webhook_http_request(
            body=body,
            headers=_build_signature_headers(body=body, encrypt_key="encrypt-key-42"),
            bot_data=_build_bot_data(cleanup_service=cleanup_service),
            reply_text_func=reply_text_func,
        )
    )

    assert response.status_code == 200
    assert json.loads(response.body.decode("utf-8")) == {"code": 0}
    reply_text_func.assert_awaited_once()
    event, reply_text = reply_text_func.await_args.args
    assert isinstance(event, FeishuPrivateTextEvent)
    assert "清理预检结果：" in reply_text
    assert "当前 guardrail: 允许 cleanup" in reply_text
    assert "cleanup hash-87 / 清理 hash-87：实际清理下载源资产" in reply_text
    assert source_file.exists()
    assert target_file.exists()


@pytest.mark.parametrize(
    ("query", "expected_action"),
    [
        ("cleanup hash-87", "cleanup"),
        ("cleanup inspect hash-87", "cleanup_inspect"),
    ],
)
def test_handle_feishu_webhook_http_request_logs_cleanup_service_not_ready(
    query: str,
    expected_action: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reply_text_func = AsyncMock()
    body = json.dumps(_build_feishu_private_text_payload(query), ensure_ascii=False)

    response = asyncio.run(
        handle_feishu_webhook_http_request(
            body=body,
            headers=_build_signature_headers(body=body, encrypt_key="encrypt-key-42"),
            bot_data=_build_bot_data(),
            reply_text_func=reply_text_func,
        )
    )
    captured = capsys.readouterr()

    assert response.status_code == 200
    assert json.loads(response.body.decode("utf-8")) == {"code": 0}
    reply_text_func.assert_awaited_once()
    event, reply_text = reply_text_func.await_args.args
    assert isinstance(event, FeishuPrivateTextEvent)
    assert reply_text == SERVICE_NOT_READY_TEXT
    assert "[cleanup 服务未就绪]" in captured.out
    assert f"动作={expected_action}" in captured.out
    assert query in captured.out
    assert "[处理建议]" in captured.out
    assert "cleanup_downloaded_source_service" in captured.out


@pytest.mark.parametrize(
    ("text", "expected_reply"),
    [
        ("cleanup", CLEANUP_QUERY_USAGE_TEXT),
        ("cleanup inspect", CLEANUP_INSPECT_QUERY_USAGE_TEXT),
        ("清理", CLEANUP_QUERY_USAGE_TEXT),
        ("清理检查", CLEANUP_INSPECT_QUERY_USAGE_TEXT),
    ],
)
def test_handle_feishu_webhook_http_request_routes_bare_cleanup_usage_into_shared_runtime(
    tmp_path: Path,
    text: str,
    expected_reply: str,
) -> None:
    reply_text_func = AsyncMock()
    body = json.dumps(_build_feishu_private_text_payload(text), ensure_ascii=False)

    response = asyncio.run(
        handle_feishu_webhook_http_request(
            body=body,
            headers=_build_signature_headers(body=body, encrypt_key="encrypt-key-42"),
            bot_data=_build_bot_data(cleanup_service=CleanupDownloadedSourceService(JobEventRepo(_make_database(tmp_path)))),
            reply_text_func=reply_text_func,
        )
    )

    assert response.status_code == 200
    assert json.loads(response.body.decode("utf-8")) == {"code": 0}
    reply_text_func.assert_awaited_once()
    _event, reply_text = reply_text_func.await_args.args
    assert reply_text == expected_reply


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
            payload = _build_feishu_private_text_payload("dune")
            body = json.dumps(payload, ensure_ascii=False)
            status_code, payload = await asyncio.to_thread(
                _post_json,
                f"http://127.0.0.1:{runtime.port}/feishu/webhook",
                body,
                _build_signature_headers(body=body, encrypt_key="encrypt-key-42"),
            )
            return status_code, payload
        finally:
            stop_feishu_webhook_server(runtime)

    status_code, payload = asyncio.run(exercise())

    assert status_code == 200
    assert payload == {"code": 0}
    reply_text_func.assert_awaited_once()


def _make_database(tmp_path: Path) -> SqliteDatabase:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    return database


def _build_signature_headers(*, body: str, encrypt_key: str) -> dict[str, str]:
    timestamp = "1711111111"
    nonce = "nonce-1"
    signature = hashlib.sha256((timestamp + nonce + encrypt_key + body).encode("utf-8")).hexdigest()
    return {
        "Content-Type": "application/json",
        "X-Lark-Request-Timestamp": timestamp,
        "X-Lark-Request-Nonce": nonce,
        "X-Lark-Signature": signature,
    }


def _post_json(url: str, body: str, headers: dict[str, str]) -> tuple[int, dict[str, object]]:
    request = urllib.request.Request(
        url,
        data=body.encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.status, json.loads(response.read().decode("utf-8"))

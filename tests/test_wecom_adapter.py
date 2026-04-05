from __future__ import annotations

import asyncio
import base64
import hashlib
from pathlib import Path
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from unittest.mock import AsyncMock

import pytest
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from app.bot.channel_identity import project_channel_chat_id, project_channel_user_id
from app.bot.telegram_bot import (
    ADD_TO_DOWNLOADER_SERVICE_KEY,
    CLEANUP_DOWNLOADED_SOURCE_SERVICE_KEY,
    GET_DOWNLOAD_STATUS_SERVICE_KEY,
    IMPORT_TO_LIBRARY_SERVICE_KEY,
    SEARCH_SERVICE_KEY,
)
from app.bot.wecom_adapter import (
    WECOM_CHANNEL,
    WECOM_ENCODING_AES_KEY_BOT_DATA_KEY,
    WECOM_RECEIVE_ID_BOT_DATA_KEY,
    WECOM_TEXT_CONTENT_TYPE,
    WECOM_TOKEN_BOT_DATA_KEY,
    WECOM_XML_CONTENT_TYPE,
    WeComPrivateTextEvent,
    handle_wecom_callback_http_request,
    handle_wecom_private_text_event,
    parse_wecom_private_text_event,
)
from app.db.job_event_repo import JobEventRepo
from app.db.sqlite import SqliteDatabase
from app.bot.wecom_webhook_server import (
    WeComWebhookServerConfig,
    start_wecom_webhook_server,
    stop_wecom_webhook_server,
)
from app.services.add_to_downloader import AddToDownloaderService
from app.services.cleanup_downloaded_source import CleanupDownloadedSourceService
from app.services.cleanup_downloaded_source import (
    CLEANUP_INSPECT_QUERY_USAGE_TEXT,
    CLEANUP_QUERY_USAGE_TEXT,
)
from app.services.get_download_status import GetDownloadStatusService
from app.services.import_to_library import ImportToLibraryService
from app.services.search_media import SearchMediaService

_TEST_AES_KEY = bytes(range(32))
_TEST_ENCODING_AES_KEY = base64.b64encode(_TEST_AES_KEY).decode("utf-8").rstrip("=")
_TEST_TOKEN = "wecom-token-42"
_TEST_TIMESTAMP = "1711111111"
_TEST_NONCE = "nonce-1"
_TEST_RECEIVE_ID = "wwcorp123"


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
        WECOM_TOKEN_BOT_DATA_KEY: _TEST_TOKEN,
        WECOM_ENCODING_AES_KEY_BOT_DATA_KEY: _TEST_ENCODING_AES_KEY,
        WECOM_RECEIVE_ID_BOT_DATA_KEY: _TEST_RECEIVE_ID,
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


def _build_wecom_private_text_xml(text: str) -> str:
    return (
        "<xml>"
        f"<ToUserName><![CDATA[{_TEST_RECEIVE_ID}]]></ToUserName>"
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
        corp_id=_TEST_RECEIVE_ID,
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
        corp_id=_TEST_RECEIVE_ID,
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


def test_handle_wecom_private_text_event_routes_cleanup_inspect_into_shared_runtime(
    tmp_path: Path,
) -> None:
    cleanup_service, source_file, target_file = _build_cleanup_service(tmp_path)
    reply_text_func = AsyncMock()

    asyncio.run(
        handle_wecom_private_text_event(
            payload_xml=_build_wecom_private_text_xml("cleanup inspect 87"),
            bot_data=_build_bot_data(cleanup_service=cleanup_service),
            reply_text_func=reply_text_func,
        )
    )

    reply_text_func.assert_awaited_once()
    event, reply_text = reply_text_func.await_args.args
    assert isinstance(event, WeComPrivateTextEvent)
    assert "清理预检结果：" in reply_text
    assert "当前 guardrail: 允许 cleanup" in reply_text
    assert "cleanup hash-87 / 清理 hash-87：实际清理下载源资产" in reply_text
    assert source_file.exists()
    assert target_file.exists()


def test_handle_wecom_private_text_event_routes_cleanup_execution_into_shared_runtime(
    tmp_path: Path,
) -> None:
    cleanup_service, source_file, target_file = _build_cleanup_service(tmp_path)
    reply_text_func = AsyncMock()

    asyncio.run(
        handle_wecom_private_text_event(
            payload_xml=_build_wecom_private_text_xml("cleanup 87"),
            bot_data=_build_bot_data(cleanup_service=cleanup_service),
            reply_text_func=reply_text_func,
        )
    )

    reply_text_func.assert_awaited_once()
    event, reply_text = reply_text_func.await_args.args
    assert isinstance(event, WeComPrivateTextEvent)
    assert "已清理下载源资产" in reply_text
    assert "cleanup inspect hash-87 / 清理检查 hash-87：只读预检，不删除任何文件" in reply_text
    assert not source_file.exists()
    assert target_file.exists()


def test_handle_wecom_private_text_event_routes_bare_cleanup_usage_into_shared_runtime(
    tmp_path: Path,
) -> None:
    reply_text_func = AsyncMock()

    asyncio.run(
        handle_wecom_private_text_event(
            payload_xml=_build_wecom_private_text_xml("cleanup"),
            bot_data=_build_bot_data(cleanup_service=CleanupDownloadedSourceService(JobEventRepo(_make_database(tmp_path)))),
            reply_text_func=reply_text_func,
        )
    )

    reply_text_func.assert_awaited_once()
    event, reply_text = reply_text_func.await_args.args
    assert isinstance(event, WeComPrivateTextEvent)
    assert reply_text == CLEANUP_QUERY_USAGE_TEXT


def test_handle_wecom_private_text_event_routes_bare_cleanup_inspect_usage_into_shared_runtime(
    tmp_path: Path,
) -> None:
    reply_text_func = AsyncMock()

    asyncio.run(
        handle_wecom_private_text_event(
            payload_xml=_build_wecom_private_text_xml("cleanup inspect"),
            bot_data=_build_bot_data(cleanup_service=CleanupDownloadedSourceService(JobEventRepo(_make_database(tmp_path)))),
            reply_text_func=reply_text_func,
        )
    )

    reply_text_func.assert_awaited_once()
    event, reply_text = reply_text_func.await_args.args
    assert isinstance(event, WeComPrivateTextEvent)
    assert reply_text == CLEANUP_INSPECT_QUERY_USAGE_TEXT


@pytest.mark.parametrize(
    ("text", "expected_reply"),
    [
        ("清理", CLEANUP_QUERY_USAGE_TEXT),
        ("清理检查", CLEANUP_INSPECT_QUERY_USAGE_TEXT),
    ],
)
def test_handle_wecom_private_text_event_routes_bare_cleanup_usage_in_chinese_into_shared_runtime(
    tmp_path: Path,
    text: str,
    expected_reply: str,
) -> None:
    reply_text_func = AsyncMock()

    asyncio.run(
        handle_wecom_private_text_event(
            payload_xml=_build_wecom_private_text_xml(text),
            bot_data=_build_bot_data(cleanup_service=CleanupDownloadedSourceService(JobEventRepo(_make_database(tmp_path)))),
            reply_text_func=reply_text_func,
        )
    )

    reply_text_func.assert_awaited_once()
    event, reply_text = reply_text_func.await_args.args
    assert isinstance(event, WeComPrivateTextEvent)
    assert reply_text == expected_reply


@pytest.mark.parametrize(
    ("text", "expect_source_exists", "expected_fragment"),
    [
        ("清理检查 87", True, "当前 guardrail: 允许 cleanup"),
        ("清理 87", False, "已清理下载源资产"),
    ],
)
def test_handle_wecom_private_text_event_routes_cleanup_protocol_in_chinese_into_shared_runtime(
    tmp_path: Path,
    text: str,
    expect_source_exists: bool,
    expected_fragment: str,
) -> None:
    cleanup_service, source_file, target_file = _build_cleanup_service(tmp_path)
    reply_text_func = AsyncMock()

    asyncio.run(
        handle_wecom_private_text_event(
            payload_xml=_build_wecom_private_text_xml(text),
            bot_data=_build_bot_data(cleanup_service=cleanup_service),
            reply_text_func=reply_text_func,
        )
    )

    reply_text_func.assert_awaited_once()
    event, reply_text = reply_text_func.await_args.args
    assert isinstance(event, WeComPrivateTextEvent)
    assert expected_fragment in reply_text
    assert source_file.exists() is expect_source_exists
    assert target_file.exists()


def test_handle_wecom_callback_http_request_returns_decrypted_echostr() -> None:
    echostr = _encrypt_wecom_plaintext("verify-challenge")

    response = asyncio.run(
        handle_wecom_callback_http_request(
            method="GET",
            query_params=_build_signed_query_params(encrypted_text=echostr),
            bot_data=_build_bot_data(),
        )
    )

    assert response.status_code == 200
    assert response.content_type == WECOM_TEXT_CONTENT_TYPE
    assert response.body.decode("utf-8") == "verify-challenge"


def test_handle_wecom_callback_http_request_rejects_invalid_signature() -> None:
    echostr = _encrypt_wecom_plaintext("verify-challenge")
    query_params = _build_signed_query_params(encrypted_text=echostr)
    query_params["msg_signature"] = "bad-signature"

    response = asyncio.run(
        handle_wecom_callback_http_request(
            method="GET",
            query_params=query_params,
            bot_data=_build_bot_data(),
        )
    )

    assert response.status_code == 401
    assert response.body == b"invalid msg_signature"


def test_handle_wecom_callback_http_request_routes_post_into_shared_runtime_and_returns_encrypted_reply() -> None:
    encrypted_text = _encrypt_wecom_plaintext(_build_wecom_private_text_xml("dune"))
    body = _build_wecom_encrypted_request_body(encrypted_text)
    query_params = _build_signed_query_params(encrypted_text=encrypted_text)

    response = asyncio.run(
        handle_wecom_callback_http_request(
            method="POST",
            query_params=query_params,
            body=body,
            bot_data=_build_bot_data(),
        )
    )

    assert response.status_code == 200
    assert response.content_type == WECOM_XML_CONTENT_TYPE
    encrypted_reply = _extract_encrypt_from_xml(response.body.decode("utf-8"))
    reply_xml = _decrypt_wecom_plaintext(encrypted_reply)
    reply_root = ET.fromstring(reply_xml)

    assert _read_xml_text(reply_root, "ToUserName") == "zhangsan"
    assert _read_xml_text(reply_root, "FromUserName") == _TEST_RECEIVE_ID
    assert _read_xml_text(reply_root, "MsgType") == "text"
    assert "搜索结果：dune" in _read_xml_text(reply_root, "Content")
    assert "title-dune" in _read_xml_text(reply_root, "Content")


def test_handle_wecom_callback_http_request_routes_cleanup_execution_into_shared_runtime_and_returns_encrypted_reply(
    tmp_path: Path,
) -> None:
    cleanup_service, source_file, target_file = _build_cleanup_service(tmp_path)
    encrypted_text = _encrypt_wecom_plaintext(_build_wecom_private_text_xml("cleanup 87"))
    body = _build_wecom_encrypted_request_body(encrypted_text)
    query_params = _build_signed_query_params(encrypted_text=encrypted_text)

    response = asyncio.run(
        handle_wecom_callback_http_request(
            method="POST",
            query_params=query_params,
            body=body,
            bot_data=_build_bot_data(cleanup_service=cleanup_service),
        )
    )

    assert response.status_code == 200
    assert response.content_type == WECOM_XML_CONTENT_TYPE
    encrypted_reply = _extract_encrypt_from_xml(response.body.decode("utf-8"))
    reply_xml = _decrypt_wecom_plaintext(encrypted_reply)
    reply_root = ET.fromstring(reply_xml)

    assert "已清理下载源资产" in _read_xml_text(reply_root, "Content")
    assert "cleanup inspect hash-87 / 清理检查 hash-87：只读预检，不删除任何文件" in _read_xml_text(
        reply_root,
        "Content",
    )
    assert not source_file.exists()
    assert target_file.exists()


def test_handle_wecom_callback_http_request_routes_cleanup_inspect_into_shared_runtime_and_returns_encrypted_reply(
    tmp_path: Path,
) -> None:
    cleanup_service, source_file, target_file = _build_cleanup_service(tmp_path)
    encrypted_text = _encrypt_wecom_plaintext(_build_wecom_private_text_xml("cleanup inspect 87"))
    body = _build_wecom_encrypted_request_body(encrypted_text)
    query_params = _build_signed_query_params(encrypted_text=encrypted_text)

    response = asyncio.run(
        handle_wecom_callback_http_request(
            method="POST",
            query_params=query_params,
            body=body,
            bot_data=_build_bot_data(cleanup_service=cleanup_service),
        )
    )

    assert response.status_code == 200
    assert response.content_type == WECOM_XML_CONTENT_TYPE
    encrypted_reply = _extract_encrypt_from_xml(response.body.decode("utf-8"))
    reply_xml = _decrypt_wecom_plaintext(encrypted_reply)
    reply_root = ET.fromstring(reply_xml)

    assert "清理预检结果：" in _read_xml_text(reply_root, "Content")
    assert "当前 guardrail: 允许 cleanup" in _read_xml_text(reply_root, "Content")
    assert "cleanup hash-87 / 清理 hash-87：实际清理下载源资产" in _read_xml_text(
        reply_root,
        "Content",
    )
    assert source_file.exists()
    assert target_file.exists()


@pytest.mark.parametrize(
    ("text", "expected_reply"),
    [
        ("cleanup", CLEANUP_QUERY_USAGE_TEXT),
        ("cleanup inspect", CLEANUP_INSPECT_QUERY_USAGE_TEXT),
        ("清理", CLEANUP_QUERY_USAGE_TEXT),
        ("清理检查", CLEANUP_INSPECT_QUERY_USAGE_TEXT),
    ],
)
def test_handle_wecom_callback_http_request_routes_bare_cleanup_usage_into_shared_runtime_and_returns_encrypted_reply(
    tmp_path: Path,
    text: str,
    expected_reply: str,
) -> None:
    encrypted_text = _encrypt_wecom_plaintext(_build_wecom_private_text_xml(text))
    body = _build_wecom_encrypted_request_body(encrypted_text)
    query_params = _build_signed_query_params(encrypted_text=encrypted_text)

    response = asyncio.run(
        handle_wecom_callback_http_request(
            method="POST",
            query_params=query_params,
            body=body,
            bot_data=_build_bot_data(cleanup_service=CleanupDownloadedSourceService(JobEventRepo(_make_database(tmp_path)))),
        )
    )

    assert response.status_code == 200
    assert response.content_type == WECOM_XML_CONTENT_TYPE
    encrypted_reply = _extract_encrypt_from_xml(response.body.decode("utf-8"))
    reply_xml = _decrypt_wecom_plaintext(encrypted_reply)
    reply_root = ET.fromstring(reply_xml)
    assert _read_xml_text(reply_root, "Content") == expected_reply


@pytest.mark.parametrize(
    ("text", "expect_source_exists", "expected_fragment"),
    [
        ("清理 87", False, "已清理下载源资产"),
        ("清理检查 87", True, "当前 guardrail: 允许 cleanup"),
    ],
)
def test_handle_wecom_callback_http_request_routes_cleanup_protocol_in_chinese_and_returns_encrypted_reply(
    tmp_path: Path,
    text: str,
    expect_source_exists: bool,
    expected_fragment: str,
) -> None:
    cleanup_service, source_file, target_file = _build_cleanup_service(tmp_path)
    encrypted_text = _encrypt_wecom_plaintext(_build_wecom_private_text_xml(text))
    body = _build_wecom_encrypted_request_body(encrypted_text)
    query_params = _build_signed_query_params(encrypted_text=encrypted_text)

    response = asyncio.run(
        handle_wecom_callback_http_request(
            method="POST",
            query_params=query_params,
            body=body,
            bot_data=_build_bot_data(cleanup_service=cleanup_service),
        )
    )

    assert response.status_code == 200
    assert response.content_type == WECOM_XML_CONTENT_TYPE
    encrypted_reply = _extract_encrypt_from_xml(response.body.decode("utf-8"))
    reply_xml = _decrypt_wecom_plaintext(encrypted_reply)
    reply_root = ET.fromstring(reply_xml)

    assert expected_fragment in _read_xml_text(reply_root, "Content")
    assert source_file.exists() is expect_source_exists
    assert target_file.exists()


def test_wecom_webhook_server_routes_real_http_get_and_post() -> None:
    async def exercise() -> tuple[str, str]:
        try:
            runtime = start_wecom_webhook_server(
                loop=asyncio.get_running_loop(),
                config=WeComWebhookServerConfig(host="127.0.0.1", port=0, path="/wecom/webhook"),
                bot_data=_build_bot_data(),
            )
        except PermissionError as error:
            pytest.skip(f"当前环境禁止本地端口监听：{error}")
        try:
            echostr = _encrypt_wecom_plaintext("verify-challenge")
            verification_text = await asyncio.to_thread(
                _http_get_text,
                f"http://127.0.0.1:{runtime.port}/wecom/webhook",
                _build_signed_query_params(encrypted_text=echostr),
            )

            encrypted_text = _encrypt_wecom_plaintext(_build_wecom_private_text_xml("dune"))
            reply_body = await asyncio.to_thread(
                _http_post_text,
                f"http://127.0.0.1:{runtime.port}/wecom/webhook",
                _build_signed_query_params(encrypted_text=encrypted_text),
                _build_wecom_encrypted_request_body(encrypted_text),
            )
            return verification_text, reply_body
        finally:
            stop_wecom_webhook_server(runtime)

    verification_text, reply_body = asyncio.run(exercise())

    assert verification_text == "verify-challenge"
    reply_xml = _decrypt_wecom_plaintext(_extract_encrypt_from_xml(reply_body))
    assert "搜索结果：dune" in reply_xml
    assert "title-dune" in reply_xml


def _make_database(tmp_path: Path) -> SqliteDatabase:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    return database


def _encrypt_wecom_plaintext(plaintext: str, *, receive_id: str = _TEST_RECEIVE_ID) -> str:
    plaintext_bytes = plaintext.encode("utf-8")
    raw_plaintext = (
        b"0123456789abcdef"
        + len(plaintext_bytes).to_bytes(4, byteorder="big")
        + plaintext_bytes
        + receive_id.encode("utf-8")
    )
    padded_plaintext = _add_pkcs7_padding(raw_plaintext)
    encryptor = Cipher(algorithms.AES(_TEST_AES_KEY), modes.CBC(_TEST_AES_KEY[:16])).encryptor()
    encrypted_bytes = encryptor.update(padded_plaintext) + encryptor.finalize()
    return base64.b64encode(encrypted_bytes).decode("utf-8")


def _decrypt_wecom_plaintext(encrypted_text: str, *, receive_id: str = _TEST_RECEIVE_ID) -> str:
    encrypted_bytes = base64.b64decode(encrypted_text)
    decryptor = Cipher(algorithms.AES(_TEST_AES_KEY), modes.CBC(_TEST_AES_KEY[:16])).decryptor()
    padded_plaintext = decryptor.update(encrypted_bytes) + decryptor.finalize()
    plaintext = _remove_pkcs7_padding(padded_plaintext)
    message_length = int.from_bytes(plaintext[16:20], byteorder="big")
    message_end = 20 + message_length
    assert plaintext[message_end:].decode("utf-8") == receive_id
    return plaintext[20:message_end].decode("utf-8")


def _add_pkcs7_padding(raw_value: bytes) -> bytes:
    padding_length = 32 - (len(raw_value) % 32)
    if padding_length == 0:
        padding_length = 32
    return raw_value + bytes([padding_length]) * padding_length


def _remove_pkcs7_padding(raw_value: bytes) -> bytes:
    padding_length = raw_value[-1]
    return raw_value[:-padding_length]


def _build_signed_query_params(*, encrypted_text: str) -> dict[str, str]:
    return {
        "msg_signature": _build_wecom_signature(encrypted_text=encrypted_text),
        "timestamp": _TEST_TIMESTAMP,
        "nonce": _TEST_NONCE,
        "echostr": encrypted_text,
    }


def _build_wecom_signature(*, encrypted_text: str) -> str:
    return hashlib.sha1("".join(sorted((_TEST_TOKEN, _TEST_TIMESTAMP, _TEST_NONCE, encrypted_text))).encode("utf-8")).hexdigest()


def _build_wecom_encrypted_request_body(encrypted_text: str) -> str:
    return (
        "<xml>"
        f"<ToUserName><![CDATA[{_TEST_RECEIVE_ID}]]></ToUserName>"
        f"<Encrypt><![CDATA[{encrypted_text}]]></Encrypt>"
        "<AgentID><![CDATA[1000002]]></AgentID>"
        "</xml>"
    )


def _extract_encrypt_from_xml(payload_xml: str) -> str:
    root = ET.fromstring(payload_xml)
    return _read_xml_text(root, "Encrypt")


def _read_xml_text(root: ET.Element, tag_name: str) -> str:
    element = root.find(tag_name)
    if element is None or element.text is None:
        return ""
    return element.text.strip()


def _http_get_text(url: str, query_params: dict[str, str]) -> str:
    request_url = f"{url}?{urllib.parse.urlencode(query_params)}"
    with urllib.request.urlopen(request_url, timeout=5) as response:
        return response.read().decode("utf-8")


def _http_post_text(url: str, query_params: dict[str, str], body: str) -> str:
    request = urllib.request.Request(
        f"{url}?{urllib.parse.urlencode(query_params)}",
        data=body.encode("utf-8"),
        headers={"Content-Type": "application/xml"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.read().decode("utf-8")

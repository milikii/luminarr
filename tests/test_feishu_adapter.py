from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

import app.bot.channel_contact_runtime as channel_contact_runtime
from app.bot.channel_identity import project_channel_chat_id, project_channel_user_id
from app.bot.feishu_adapter import (
    FEISHU_CHANNEL,
    FeishuPrivateTextEvent,
    build_feishu_reply_text_func,
    handle_feishu_private_text_event,
    parse_feishu_private_text_event,
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
from app.db.job_repo import JobRepo
from app.db.sqlite import SqliteDatabase
from app.services.add_to_downloader import AddToDownloaderService
from app.services.cleanup_downloaded_source import (
    CLEANUP_INSPECT_QUERY_USAGE_TEXT,
    CLEANUP_QUERY_USAGE_TEXT,
    CleanupDownloadedSourceService,
)
from app.services.get_download_status import GetDownloadStatusService
from app.services.import_to_library import ImportToLibraryService
from app.services.search_media import SearchMediaService

_CHAT_SCOPED_TASK_REF = "cleanup-shortcut"


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


def _build_bot_data(
    *,
    cleanup_service: CleanupDownloadedSourceService | None = None,
) -> dict[str, object]:
    search_service = SearchMediaService(_fake_search)
    channel_contact_registry = channel_contact_runtime.ChannelContactRegistry()
    bot_data = {
        SEARCH_SERVICE_KEY: search_service,
        ADD_TO_DOWNLOADER_SERVICE_KEY: AddToDownloaderService(search_service, AsyncMock()),
        GET_DOWNLOAD_STATUS_SERVICE_KEY: GetDownloadStatusService(AsyncMock()),
        IMPORT_TO_LIBRARY_SERVICE_KEY: ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies"),
        channel_contact_runtime.CHANNEL_CONTACT_REGISTRY_KEY: channel_contact_registry,
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


def _build_chat_scoped_cleanup_service(
    tmp_path: Path,
) -> tuple[CleanupDownloadedSourceService, Path, Path]:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    target_dir = tmp_path / "library"
    target_dir.mkdir(parents=True)
    target_file = target_dir / "Dune (2021).mkv"
    target_file.hardlink_to(source_file)

    database = _make_database(tmp_path)
    event_repo = JobEventRepo(database)
    job_repo = JobRepo(database)
    projected_chat_id = project_channel_chat_id(channel=FEISHU_CHANNEL, external_chat_id="oc_feishu_chat_1")
    projected_user_id = project_channel_user_id(channel=FEISHU_CHANNEL, external_user_id="ou_feishu_user_1")
    job_repo.upsert_import_job_pending(
        chat_id=projected_chat_id,
        user_id=projected_user_id,
        task_ref=_CHAT_SCOPED_TASK_REF,
        task_id="87",
        task_hash="hash-87",
    )
    event_repo.append_event(
        task_ref="hash-87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message=str(target_file),
        source_path=str(source_file),
        target_path=str(target_file),
    )
    return CleanupDownloadedSourceService(event_repo, job_repo=job_repo), source_file, target_file


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


def test_project_channel_identity_is_stable_and_channel_scoped(
    capsys: pytest.CaptureFixture[str],
) -> None:
    projected_chat_id = project_channel_chat_id(channel=FEISHU_CHANNEL, external_chat_id="oc_feishu_chat_1")
    projected_chat_id_again = project_channel_chat_id(channel=FEISHU_CHANNEL, external_chat_id="oc_feishu_chat_1")
    projected_user_id = project_channel_user_id(channel=FEISHU_CHANNEL, external_user_id="ou_feishu_user_1")
    telegram_like_chat_id = project_channel_chat_id(channel="telegram", external_chat_id="oc_feishu_chat_1")

    assert projected_chat_id > 0
    assert projected_user_id > 0
    assert projected_chat_id == projected_chat_id_again
    assert projected_chat_id != projected_user_id
    assert projected_chat_id != telegram_like_chat_id
    assert project_channel_chat_id(channel=FEISHU_CHANNEL, external_chat_id="") is None
    assert project_channel_user_id(channel="", external_user_id="ou_feishu_user_1") is None
    captured = capsys.readouterr()
    assert "[渠道身份缺失]" in captured.out
    assert "[处理建议]" in captured.out


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
    bot_data = _build_bot_data()
    reply_text_func = AsyncMock()

    asyncio.run(
        handle_feishu_private_text_event(
            payload=_build_feishu_private_text_payload("dune"),
            bot_data=bot_data,
            reply_text_func=reply_text_func,
        )
    )

    reply_text_func.assert_awaited_once()
    event, reply_text = reply_text_func.await_args.args
    assert isinstance(event, FeishuPrivateTextEvent)
    assert event.chat_id == "oc_feishu_chat_1"
    assert "搜索：dune ✓" in reply_text
    assert "候选结果（1 条）" in reply_text
    assert "开始下载：发送 select 1" in reply_text
    assert "Dune (2021)" in reply_text
    contact = channel_contact_runtime.resolve_channel_contact(
        bot_data,
        internal_chat_id=project_channel_chat_id(channel=FEISHU_CHANNEL, external_chat_id="oc_feishu_chat_1"),
    )
    assert contact is not None
    assert contact.external_chat_id == "oc_feishu_chat_1"
    assert contact.external_user_id == "ou_feishu_user_1"


def test_handle_feishu_private_text_event_records_external_chat_contact() -> None:
    bot_data = _build_bot_data()

    asyncio.run(
        handle_feishu_private_text_event(
            payload=_build_feishu_private_text_payload("dune"),
            bot_data=bot_data,
            reply_text_func=AsyncMock(),
        )
    )

    assert channel_contact_runtime.resolve_channel_contact(
        bot_data,
        internal_chat_id=project_channel_chat_id(channel=FEISHU_CHANNEL, external_chat_id="oc_feishu_chat_1"),
    ) == channel_contact_runtime.ChannelContact(
        channel=FEISHU_CHANNEL,
        internal_chat_id=project_channel_chat_id(channel=FEISHU_CHANNEL, external_chat_id="oc_feishu_chat_1"),
        external_chat_id="oc_feishu_chat_1",
        external_user_id="ou_feishu_user_1",
    )


def test_handle_feishu_private_text_event_routes_cleanup_inspect_into_shared_runtime(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
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
    captured = capsys.readouterr()
    assert "[cleanup 私聊 smoke]" in captured.out
    assert "channel=feishu" in captured.out
    assert "action=cleanup_inspect" in captured.out
    assert 'query="cleanup inspect 87"' in captured.out
    assert 'reply_head="清理预检结果："' in captured.out


def test_handle_feishu_private_text_event_routes_chat_scoped_cleanup_shortcut_into_shared_runtime(
    tmp_path: Path,
) -> None:
    cleanup_service, source_file, target_file = _build_chat_scoped_cleanup_service(tmp_path)
    reply_text_func = AsyncMock()

    asyncio.run(
        handle_feishu_private_text_event(
            payload=_build_feishu_private_text_payload(f"cleanup inspect {_CHAT_SCOPED_TASK_REF}"),
            bot_data=_build_bot_data(cleanup_service=cleanup_service),
            reply_text_func=reply_text_func,
        )
    )

    reply_text_func.assert_awaited_once()
    event, reply_text = reply_text_func.await_args.args
    assert isinstance(event, FeishuPrivateTextEvent)
    assert "查询引用: cleanup-shortcut" in reply_text
    assert "任务 ID: 87" in reply_text
    assert "任务 Hash: hash-87" in reply_text
    assert "cleanup hash-87 / 清理 hash-87：实际清理下载源资产" in reply_text
    assert source_file.exists()
    assert target_file.exists()


def test_handle_feishu_private_text_event_routes_cleanup_execution_into_shared_runtime(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
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
    captured = capsys.readouterr()
    assert "[cleanup 私聊 smoke]" in captured.out
    assert "channel=feishu" in captured.out
    assert "action=cleanup" in captured.out
    assert 'query="cleanup 87"' in captured.out
    assert 'reply_head="已清理下载源资产。"' in captured.out


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
        ("cleanup", "cleanup"),
        ("cleanup inspect", "cleanup_inspect"),
        ("清理", "cleanup"),
        ("清理检查", "cleanup_inspect"),
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


def _make_database(tmp_path: Path) -> SqliteDatabase:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    return database

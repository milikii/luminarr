from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.bot.channel_identity import project_channel_chat_id, project_channel_user_id
from app.bot.personal_wechat_text import (
    PERSONAL_WECHAT_CHANNEL,
    PersonalWeChatPrivateTextEvent,
    PersonalWeChatTextService,
    handle_personal_wechat_private_text_event,
    parse_personal_wechat_private_text_event,
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
from app.services.cleanup_downloaded_source import CleanupDownloadedSourceService
from app.services.cleanup_downloaded_source import (
    CLEANUP_INSPECT_QUERY_USAGE_TEXT,
    CLEANUP_QUERY_USAGE_TEXT,
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
    bot_data = {
        SEARCH_SERVICE_KEY: search_service,
        ADD_TO_DOWNLOADER_SERVICE_KEY: AddToDownloaderService(search_service, AsyncMock()),
        GET_DOWNLOAD_STATUS_SERVICE_KEY: GetDownloadStatusService(AsyncMock()),
        IMPORT_TO_LIBRARY_SERVICE_KEY: ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies"),
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
    projected_chat_id = project_channel_chat_id(channel=PERSONAL_WECHAT_CHANNEL, external_chat_id="wx-user-1")
    projected_user_id = project_channel_user_id(channel=PERSONAL_WECHAT_CHANNEL, external_user_id="wx-user-1")
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


def _build_text_message(
    text: str,
    *,
    from_user_id: str = "wx-user-1",
    context_token: str | None = "ctx-1",
    message_type: int = 1,
    group_id: str = "",
) -> object:
    return SimpleNamespace(
        message_type=message_type,
        group_id=group_id,
        from_user_id=from_user_id,
        message_id=987654321,
        context_token=context_token,
        item_list=[
            SimpleNamespace(
                type=1,
                text_item=SimpleNamespace(text=text),
            )
        ],
    )


def _run_personal_wechat_text_service_single_message_case(
    *,
    inbound_text: str,
    bot_data: dict[str, object],
    sync_path: Path,
) -> tuple[list[tuple[Path, str]], list[tuple[str, str, object]], Mock, Mock, AsyncMock]:
    saved_sync_buf: list[tuple[Path, str]] = []
    sent_messages: list[tuple[str, str, object]] = []
    reply_sent = asyncio.Event()
    restore_context_tokens = Mock()
    set_context_token = Mock()
    close_client = AsyncMock()

    async def get_updates_func(**_: object) -> object:
        if reply_sent.is_set():
            await asyncio.sleep(3600)
        return SimpleNamespace(
            ret=0,
            errcode=0,
            errmsg="",
            msgs=[_build_text_message(inbound_text)],
            get_updates_buf="buf-new",
            longpolling_timeout_ms=1500,
        )

    async def send_text_func(to: str, text: str, opts: object) -> object:
        sent_messages.append((to, text, opts))
        reply_sent.set()
        return {"messageId": "wx-msg-1"}

    service = PersonalWeChatTextService(
        list_account_ids_func=lambda: ["wx-account-1"],
        load_account_func=lambda _: SimpleNamespace(token="bot-token-1", base_url="https://wx.test"),
        restore_context_tokens_func=restore_context_tokens,
        get_context_token_func=Mock(return_value=None),
        set_context_token_func=set_context_token,
        get_sync_buf_file_path_func=lambda _: sync_path,
        load_sync_buf_func=lambda _: "buf-old",
        save_sync_buf_func=lambda path, buf: saved_sync_buf.append((path, buf)),
        get_updates_func=get_updates_func,
        send_text_func=send_text_func,
        close_client_func=close_client,
    )

    async def run_case() -> None:
        await service.start(bot_data=bot_data)
        await asyncio.wait_for(reply_sent.wait(), timeout=1)
        await service.shutdown()

    asyncio.run(run_case())
    return saved_sync_buf, sent_messages, restore_context_tokens, set_context_token, close_client


def test_parse_personal_wechat_private_text_event_reads_private_text() -> None:
    event = parse_personal_wechat_private_text_event(
        account_id="wx-account-1",
        message=_build_text_message("dune"),
    )

    assert event == PersonalWeChatPrivateTextEvent(
        account_id="wx-account-1",
        from_user_id="wx-user-1",
        message_id="987654321",
        text="dune",
        context_token="ctx-1",
    )


def test_parse_personal_wechat_private_text_event_ignores_non_user_group_or_non_text() -> None:
    non_user_message = _build_text_message("dune", message_type=2)
    group_message = _build_text_message("dune", group_id="group-1")
    empty_text_message = SimpleNamespace(
        message_type=1,
        group_id="",
        from_user_id="wx-user-1",
        message_id=1,
        context_token="ctx-1",
        item_list=[SimpleNamespace(type=1, text_item=SimpleNamespace(text=""))],
    )

    assert parse_personal_wechat_private_text_event(account_id="wx-account-1", message=non_user_message) is None
    assert parse_personal_wechat_private_text_event(account_id="wx-account-1", message=group_message) is None
    assert parse_personal_wechat_private_text_event(account_id="wx-account-1", message=empty_text_message) is None


def test_handle_personal_wechat_private_text_event_projects_ids_and_routes_into_shared_runtime(
    monkeypatch,
) -> None:
    dispatch_private_chat_text = AsyncMock()
    reply_text_func = AsyncMock()
    monkeypatch.setattr("app.bot.personal_wechat_text.dispatch_private_chat_text", dispatch_private_chat_text)

    event = asyncio.run(
        handle_personal_wechat_private_text_event(
            account_id="wx-account-1",
            message=_build_text_message("dune"),
            bot_data=_build_bot_data(),
            reply_text_func=reply_text_func,
        )
    )

    assert event == PersonalWeChatPrivateTextEvent(
        account_id="wx-account-1",
        from_user_id="wx-user-1",
        message_id="987654321",
        text="dune",
        context_token="ctx-1",
    )
    dispatch_private_chat_text.assert_awaited_once()
    assert dispatch_private_chat_text.await_args.kwargs["query"] == "dune"
    assert dispatch_private_chat_text.await_args.kwargs["chat_id"] == project_channel_chat_id(
        channel=PERSONAL_WECHAT_CHANNEL,
        external_chat_id="wx-user-1",
    )
    assert dispatch_private_chat_text.await_args.kwargs["user_id"] == project_channel_user_id(
        channel=PERSONAL_WECHAT_CHANNEL,
        external_user_id="wx-user-1",
    )


def test_handle_personal_wechat_private_text_event_routes_cleanup_inspect_into_shared_runtime(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cleanup_service, source_file, target_file = _build_cleanup_service(tmp_path)
    reply_text_func = AsyncMock()

    event = asyncio.run(
        handle_personal_wechat_private_text_event(
            account_id="wx-account-1",
            message=_build_text_message("cleanup inspect 87"),
            bot_data=_build_bot_data(cleanup_service=cleanup_service),
            reply_text_func=reply_text_func,
        )
    )

    assert event == PersonalWeChatPrivateTextEvent(
        account_id="wx-account-1",
        from_user_id="wx-user-1",
        message_id="987654321",
        text="cleanup inspect 87",
        context_token="ctx-1",
    )
    reply_text_func.assert_awaited_once()
    event, reply_text = reply_text_func.await_args.args
    assert isinstance(event, PersonalWeChatPrivateTextEvent)
    assert "清理预检结果：" in reply_text
    assert "当前 guardrail: 允许 cleanup" in reply_text
    assert "cleanup hash-87 / 清理 hash-87：实际清理下载源资产" in reply_text
    assert source_file.exists()
    assert target_file.exists()
    captured = capsys.readouterr()
    assert "[cleanup 私聊 smoke]" in captured.out
    assert "channel=personal_wechat" in captured.out
    assert "action=cleanup_inspect" in captured.out
    assert 'query="cleanup inspect 87"' in captured.out
    assert 'reply_head="清理预检结果："' in captured.out


def test_handle_personal_wechat_private_text_event_routes_chat_scoped_cleanup_shortcut_into_shared_runtime(
    tmp_path: Path,
) -> None:
    cleanup_service, source_file, target_file = _build_chat_scoped_cleanup_service(tmp_path)
    reply_text_func = AsyncMock()

    event = asyncio.run(
        handle_personal_wechat_private_text_event(
            account_id="wx-account-1",
            message=_build_text_message(f"cleanup inspect {_CHAT_SCOPED_TASK_REF}"),
            bot_data=_build_bot_data(cleanup_service=cleanup_service),
            reply_text_func=reply_text_func,
        )
    )

    assert event == PersonalWeChatPrivateTextEvent(
        account_id="wx-account-1",
        from_user_id="wx-user-1",
        message_id="987654321",
        text=f"cleanup inspect {_CHAT_SCOPED_TASK_REF}",
        context_token="ctx-1",
    )
    reply_text_func.assert_awaited_once()
    event, reply_text = reply_text_func.await_args.args
    assert isinstance(event, PersonalWeChatPrivateTextEvent)
    assert "查询引用: cleanup-shortcut" in reply_text
    assert "任务 ID: 87" in reply_text
    assert "任务 Hash: hash-87" in reply_text
    assert "cleanup hash-87 / 清理 hash-87：实际清理下载源资产" in reply_text
    assert source_file.exists()
    assert target_file.exists()


def test_handle_personal_wechat_private_text_event_routes_cleanup_execution_into_shared_runtime(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cleanup_service, source_file, target_file = _build_cleanup_service(tmp_path)
    reply_text_func = AsyncMock()

    event = asyncio.run(
        handle_personal_wechat_private_text_event(
            account_id="wx-account-1",
            message=_build_text_message("cleanup 87"),
            bot_data=_build_bot_data(cleanup_service=cleanup_service),
            reply_text_func=reply_text_func,
        )
    )

    assert event == PersonalWeChatPrivateTextEvent(
        account_id="wx-account-1",
        from_user_id="wx-user-1",
        message_id="987654321",
        text="cleanup 87",
        context_token="ctx-1",
    )
    reply_text_func.assert_awaited_once()
    event, reply_text = reply_text_func.await_args.args
    assert isinstance(event, PersonalWeChatPrivateTextEvent)
    assert "已清理下载源资产" in reply_text
    assert "cleanup inspect hash-87 / 清理检查 hash-87：只读预检，不删除任何文件" in reply_text
    assert not source_file.exists()
    assert target_file.exists()
    captured = capsys.readouterr()
    assert "[cleanup 私聊 smoke]" in captured.out
    assert "channel=personal_wechat" in captured.out
    assert "action=cleanup" in captured.out
    assert 'query="cleanup 87"' in captured.out
    assert 'reply_head="已清理下载源资产。"' in captured.out


def test_handle_personal_wechat_private_text_event_routes_bare_cleanup_usage_into_shared_runtime(
    tmp_path: Path,
) -> None:
    reply_text_func = AsyncMock()

    event = asyncio.run(
        handle_personal_wechat_private_text_event(
            account_id="wx-account-1",
            message=_build_text_message("cleanup"),
            bot_data=_build_bot_data(cleanup_service=CleanupDownloadedSourceService(JobEventRepo(_make_database(tmp_path)))),
            reply_text_func=reply_text_func,
        )
    )

    assert event == PersonalWeChatPrivateTextEvent(
        account_id="wx-account-1",
        from_user_id="wx-user-1",
        message_id="987654321",
        text="cleanup",
        context_token="ctx-1",
    )
    reply_text_func.assert_awaited_once()
    event, reply_text = reply_text_func.await_args.args
    assert isinstance(event, PersonalWeChatPrivateTextEvent)
    assert reply_text == CLEANUP_QUERY_USAGE_TEXT


def test_handle_personal_wechat_private_text_event_routes_bare_cleanup_inspect_usage_into_shared_runtime(
    tmp_path: Path,
) -> None:
    reply_text_func = AsyncMock()

    event = asyncio.run(
        handle_personal_wechat_private_text_event(
            account_id="wx-account-1",
            message=_build_text_message("cleanup inspect"),
            bot_data=_build_bot_data(cleanup_service=CleanupDownloadedSourceService(JobEventRepo(_make_database(tmp_path)))),
            reply_text_func=reply_text_func,
        )
    )

    assert event == PersonalWeChatPrivateTextEvent(
        account_id="wx-account-1",
        from_user_id="wx-user-1",
        message_id="987654321",
        text="cleanup inspect",
        context_token="ctx-1",
    )
    reply_text_func.assert_awaited_once()
    event, reply_text = reply_text_func.await_args.args
    assert isinstance(event, PersonalWeChatPrivateTextEvent)
    assert reply_text == CLEANUP_INSPECT_QUERY_USAGE_TEXT


@pytest.mark.parametrize(
    ("inbound_text", "expected_reply"),
    [
        ("清理", CLEANUP_QUERY_USAGE_TEXT),
        ("清理检查", CLEANUP_INSPECT_QUERY_USAGE_TEXT),
    ],
)
def test_handle_personal_wechat_private_text_event_routes_bare_cleanup_usage_in_chinese_into_shared_runtime(
    tmp_path: Path,
    inbound_text: str,
    expected_reply: str,
) -> None:
    reply_text_func = AsyncMock()

    event = asyncio.run(
        handle_personal_wechat_private_text_event(
            account_id="wx-account-1",
            message=_build_text_message(inbound_text),
            bot_data=_build_bot_data(cleanup_service=CleanupDownloadedSourceService(JobEventRepo(_make_database(tmp_path)))),
            reply_text_func=reply_text_func,
        )
    )

    assert event == PersonalWeChatPrivateTextEvent(
        account_id="wx-account-1",
        from_user_id="wx-user-1",
        message_id="987654321",
        text=inbound_text,
        context_token="ctx-1",
    )
    reply_text_func.assert_awaited_once()
    event, reply_text = reply_text_func.await_args.args
    assert isinstance(event, PersonalWeChatPrivateTextEvent)
    assert reply_text == expected_reply


@pytest.mark.parametrize(
    ("inbound_text", "expect_source_exists", "expected_fragment"),
    [
        ("清理检查 87", True, "当前 guardrail: 允许 cleanup"),
        ("清理 87", False, "已清理下载源资产"),
    ],
)
def test_handle_personal_wechat_private_text_event_routes_cleanup_protocol_in_chinese_into_shared_runtime(
    tmp_path: Path,
    inbound_text: str,
    expect_source_exists: bool,
    expected_fragment: str,
) -> None:
    cleanup_service, source_file, target_file = _build_cleanup_service(tmp_path)
    reply_text_func = AsyncMock()

    event = asyncio.run(
        handle_personal_wechat_private_text_event(
            account_id="wx-account-1",
            message=_build_text_message(inbound_text),
            bot_data=_build_bot_data(cleanup_service=cleanup_service),
            reply_text_func=reply_text_func,
        )
    )

    assert event == PersonalWeChatPrivateTextEvent(
        account_id="wx-account-1",
        from_user_id="wx-user-1",
        message_id="987654321",
        text=inbound_text,
        context_token="ctx-1",
    )
    reply_text_func.assert_awaited_once()
    event, reply_text = reply_text_func.await_args.args
    assert isinstance(event, PersonalWeChatPrivateTextEvent)
    assert expected_fragment in reply_text
    assert source_file.exists() is expect_source_exists
    assert target_file.exists()


@pytest.mark.parametrize(
    ("inbound_text", "expected_action"),
    [
        ("cleanup hash-87", "cleanup"),
        ("cleanup inspect hash-87", "cleanup_inspect"),
        ("cleanup", "cleanup"),
        ("cleanup inspect", "cleanup_inspect"),
        ("清理", "cleanup"),
        ("清理检查", "cleanup_inspect"),
    ],
)
def test_handle_personal_wechat_private_text_event_logs_cleanup_service_not_ready(
    inbound_text: str,
    expected_action: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reply_text_func = AsyncMock()

    event = asyncio.run(
        handle_personal_wechat_private_text_event(
            account_id="wx-account-1",
            message=_build_text_message(inbound_text),
            bot_data=_build_bot_data(),
            reply_text_func=reply_text_func,
        )
    )
    captured = capsys.readouterr()

    assert event == PersonalWeChatPrivateTextEvent(
        account_id="wx-account-1",
        from_user_id="wx-user-1",
        message_id="987654321",
        text=inbound_text,
        context_token="ctx-1",
    )
    reply_text_func.assert_awaited_once()
    _, reply_text = reply_text_func.await_args.args
    assert reply_text == SERVICE_NOT_READY_TEXT
    assert "[cleanup 服务未就绪]" in captured.out
    assert f"动作={expected_action}" in captured.out
    assert inbound_text in captured.out
    assert "[处理建议]" in captured.out
    assert "cleanup_downloaded_source_service" in captured.out


def test_personal_wechat_text_service_polls_single_saved_account_and_replies(tmp_path: Path) -> None:
    sync_path = tmp_path / "wx-account-1.sync.json"
    saved_sync_buf, sent_messages, restore_context_tokens, set_context_token, close_client = (
        _run_personal_wechat_text_service_single_message_case(
            inbound_text="dune",
            bot_data=_build_bot_data(),
            sync_path=sync_path,
        )
    )

    assert saved_sync_buf == [(sync_path, "buf-new")]
    restore_context_tokens.assert_called_once_with("wx-account-1")
    set_context_token.assert_called_once_with("wx-account-1", "wx-user-1", "ctx-1")
    assert len(sent_messages) == 1
    to, text, opts = sent_messages[0]
    assert to == "wx-user-1"
    assert "【搜索：dune】 ✓" in text
    assert "▸ 电影信息" in text
    assert "开始下载：发送 select 1" in text
    assert "Dune (2021)" in text
    assert getattr(opts, "base_url", "") == "https://wx.test"
    assert getattr(opts, "token", "") == "bot-token-1"
    assert getattr(opts, "context_token", "") == "ctx-1"
    close_client.assert_awaited_once()


def test_personal_wechat_text_service_routes_cleanup_inspect_and_keeps_files(tmp_path: Path) -> None:
    cleanup_service, source_file, target_file = _build_cleanup_service(tmp_path)
    sync_path = tmp_path / "wx-account-1.sync.json"
    saved_sync_buf, sent_messages, restore_context_tokens, set_context_token, close_client = (
        _run_personal_wechat_text_service_single_message_case(
            inbound_text="cleanup inspect 87",
            bot_data=_build_bot_data(cleanup_service=cleanup_service),
            sync_path=sync_path,
        )
    )

    assert saved_sync_buf == [(sync_path, "buf-new")]
    restore_context_tokens.assert_called_once_with("wx-account-1")
    set_context_token.assert_called_once_with("wx-account-1", "wx-user-1", "ctx-1")
    assert len(sent_messages) == 1
    to, text, opts = sent_messages[0]
    assert to == "wx-user-1"
    assert "清理预检结果：" in text
    assert "当前 guardrail: 允许 cleanup" in text
    assert "cleanup hash-87 / 清理 hash-87：实际清理下载源资产" in text
    assert getattr(opts, "base_url", "") == "https://wx.test"
    assert getattr(opts, "token", "") == "bot-token-1"
    assert getattr(opts, "context_token", "") == "ctx-1"
    assert source_file.exists()
    assert target_file.exists()
    close_client.assert_awaited_once()


def test_personal_wechat_text_service_routes_cleanup_execution_and_removes_source(tmp_path: Path) -> None:
    cleanup_service, source_file, target_file = _build_cleanup_service(tmp_path)
    sync_path = tmp_path / "wx-account-1.sync.json"
    saved_sync_buf, sent_messages, restore_context_tokens, set_context_token, close_client = (
        _run_personal_wechat_text_service_single_message_case(
            inbound_text="cleanup 87",
            bot_data=_build_bot_data(cleanup_service=cleanup_service),
            sync_path=sync_path,
        )
    )

    assert saved_sync_buf == [(sync_path, "buf-new")]
    restore_context_tokens.assert_called_once_with("wx-account-1")
    set_context_token.assert_called_once_with("wx-account-1", "wx-user-1", "ctx-1")
    assert len(sent_messages) == 1
    to, text, opts = sent_messages[0]
    assert to == "wx-user-1"
    assert "已清理下载源资产" in text
    assert "cleanup inspect hash-87 / 清理检查 hash-87：只读预检，不删除任何文件" in text
    assert getattr(opts, "base_url", "") == "https://wx.test"
    assert getattr(opts, "token", "") == "bot-token-1"
    assert getattr(opts, "context_token", "") == "ctx-1"
    assert not source_file.exists()
    assert target_file.exists()
    close_client.assert_awaited_once()


def test_personal_wechat_text_service_routes_bare_cleanup_usage(tmp_path: Path) -> None:
    sync_path = tmp_path / "wx-account-1.sync.json"
    saved_sync_buf, sent_messages, restore_context_tokens, set_context_token, close_client = (
        _run_personal_wechat_text_service_single_message_case(
            inbound_text="cleanup",
            bot_data=_build_bot_data(cleanup_service=CleanupDownloadedSourceService(JobEventRepo(_make_database(tmp_path)))),
            sync_path=sync_path,
        )
    )

    assert saved_sync_buf == [(sync_path, "buf-new")]
    restore_context_tokens.assert_called_once_with("wx-account-1")
    set_context_token.assert_called_once_with("wx-account-1", "wx-user-1", "ctx-1")
    assert len(sent_messages) == 1
    to, text, opts = sent_messages[0]
    assert to == "wx-user-1"
    assert text == CLEANUP_QUERY_USAGE_TEXT
    assert getattr(opts, "context_token", "") == "ctx-1"
    close_client.assert_awaited_once()


def test_personal_wechat_text_service_routes_bare_cleanup_inspect_usage(tmp_path: Path) -> None:
    sync_path = tmp_path / "wx-account-1.sync.json"
    saved_sync_buf, sent_messages, restore_context_tokens, set_context_token, close_client = (
        _run_personal_wechat_text_service_single_message_case(
            inbound_text="cleanup inspect",
            bot_data=_build_bot_data(cleanup_service=CleanupDownloadedSourceService(JobEventRepo(_make_database(tmp_path)))),
            sync_path=sync_path,
        )
    )

    assert saved_sync_buf == [(sync_path, "buf-new")]
    restore_context_tokens.assert_called_once_with("wx-account-1")
    set_context_token.assert_called_once_with("wx-account-1", "wx-user-1", "ctx-1")
    assert len(sent_messages) == 1
    to, text, opts = sent_messages[0]
    assert to == "wx-user-1"
    assert text == CLEANUP_INSPECT_QUERY_USAGE_TEXT
    assert getattr(opts, "context_token", "") == "ctx-1"
    close_client.assert_awaited_once()


@pytest.mark.parametrize(
    ("inbound_text", "expected_reply"),
    [
        ("清理", CLEANUP_QUERY_USAGE_TEXT),
        ("清理检查", CLEANUP_INSPECT_QUERY_USAGE_TEXT),
    ],
)
def test_personal_wechat_text_service_routes_bare_cleanup_usage_in_chinese(
    tmp_path: Path,
    inbound_text: str,
    expected_reply: str,
) -> None:
    sync_path = tmp_path / "wx-account-1.sync.json"
    saved_sync_buf, sent_messages, restore_context_tokens, set_context_token, close_client = (
        _run_personal_wechat_text_service_single_message_case(
            inbound_text=inbound_text,
            bot_data=_build_bot_data(cleanup_service=CleanupDownloadedSourceService(JobEventRepo(_make_database(tmp_path)))),
            sync_path=sync_path,
        )
    )

    assert saved_sync_buf == [(sync_path, "buf-new")]
    restore_context_tokens.assert_called_once_with("wx-account-1")
    set_context_token.assert_called_once_with("wx-account-1", "wx-user-1", "ctx-1")
    assert len(sent_messages) == 1
    to, text, opts = sent_messages[0]
    assert to == "wx-user-1"
    assert text == expected_reply
    assert getattr(opts, "context_token", "") == "ctx-1"
    close_client.assert_awaited_once()


@pytest.mark.parametrize(
    ("inbound_text", "expect_source_exists", "expected_fragment"),
    [
        ("清理检查 87", True, "当前 guardrail: 允许 cleanup"),
        ("清理 87", False, "已清理下载源资产"),
    ],
)
def test_personal_wechat_text_service_routes_cleanup_protocol_in_chinese(
    tmp_path: Path,
    inbound_text: str,
    expect_source_exists: bool,
    expected_fragment: str,
) -> None:
    cleanup_service, source_file, target_file = _build_cleanup_service(tmp_path)
    sync_path = tmp_path / "wx-account-1.sync.json"
    saved_sync_buf, sent_messages, restore_context_tokens, set_context_token, close_client = (
        _run_personal_wechat_text_service_single_message_case(
            inbound_text=inbound_text,
            bot_data=_build_bot_data(cleanup_service=cleanup_service),
            sync_path=sync_path,
        )
    )

    assert saved_sync_buf == [(sync_path, "buf-new")]
    restore_context_tokens.assert_called_once_with("wx-account-1")
    set_context_token.assert_called_once_with("wx-account-1", "wx-user-1", "ctx-1")
    assert len(sent_messages) == 1
    to, text, opts = sent_messages[0]
    assert to == "wx-user-1"
    assert expected_fragment in text
    assert getattr(opts, "base_url", "") == "https://wx.test"
    assert getattr(opts, "token", "") == "bot-token-1"
    assert getattr(opts, "context_token", "") == "ctx-1"
    assert source_file.exists() is expect_source_exists
    assert target_file.exists()
    close_client.assert_awaited_once()


@pytest.mark.parametrize(
    ("inbound_text", "expected_action"),
    [
        ("cleanup hash-87", "cleanup"),
        ("cleanup inspect hash-87", "cleanup_inspect"),
        ("cleanup", "cleanup"),
        ("cleanup inspect", "cleanup_inspect"),
        ("清理", "cleanup"),
        ("清理检查", "cleanup_inspect"),
    ],
)
def test_personal_wechat_text_service_logs_cleanup_service_not_ready(
    tmp_path: Path,
    inbound_text: str,
    expected_action: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    sync_path = tmp_path / "wx-account-1.sync.json"
    saved_sync_buf, sent_messages, restore_context_tokens, set_context_token, close_client = (
        _run_personal_wechat_text_service_single_message_case(
            inbound_text=inbound_text,
            bot_data=_build_bot_data(),
            sync_path=sync_path,
        )
    )
    captured = capsys.readouterr()

    assert saved_sync_buf == [(sync_path, "buf-new")]
    restore_context_tokens.assert_called_once_with("wx-account-1")
    set_context_token.assert_called_once_with("wx-account-1", "wx-user-1", "ctx-1")
    assert len(sent_messages) == 1
    to, text, opts = sent_messages[0]
    assert to == "wx-user-1"
    assert text == SERVICE_NOT_READY_TEXT
    assert getattr(opts, "context_token", "") == "ctx-1"
    assert "[cleanup 服务未就绪]" in captured.out
    assert f"动作={expected_action}" in captured.out
    assert inbound_text in captured.out
    assert "[处理建议]" in captured.out
    assert "cleanup_downloaded_source_service" in captured.out
    close_client.assert_awaited_once()


def test_personal_wechat_text_service_refuses_multiple_saved_accounts(capsys) -> None:
    get_updates_func = AsyncMock()
    close_client = AsyncMock()
    service = PersonalWeChatTextService(
        list_account_ids_func=lambda: ["wx-account-1", "wx-account-2"],
        load_account_func=lambda account_id: SimpleNamespace(
            token=f"bot-token-for-{account_id}",
            base_url="https://wx.test",
        ),
        restore_context_tokens_func=Mock(),
        get_context_token_func=Mock(return_value=None),
        set_context_token_func=Mock(),
        get_sync_buf_file_path_func=lambda account_id: Path(f"/tmp/{account_id}.sync.json"),
        load_sync_buf_func=lambda _: "",
        save_sync_buf_func=lambda _path, _buf: None,
        get_updates_func=get_updates_func,
        send_text_func=AsyncMock(),
        close_client_func=close_client,
    )

    asyncio.run(service.start(bot_data=_build_bot_data()))

    captured = capsys.readouterr()
    assert "[personal WeChat 私聊文本未启动]" in captured.out
    assert "多个已保存的 personal WeChat 账号" in captured.out
    assert service._poll_task is None
    get_updates_func.assert_not_awaited()
    close_client.assert_not_awaited()


def _make_database(tmp_path: Path) -> SqliteDatabase:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    return database

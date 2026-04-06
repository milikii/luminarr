from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.bot.feishu_adapter import handle_feishu_private_text_event
from app.bot.channel_identity import project_channel_chat_id
from app.bot.personal_wechat_text import handle_personal_wechat_private_text_event
from app.bot.telegram_bot import (
    ADD_TO_DOWNLOADER_SERVICE_KEY,
    CLEANUP_DOWNLOADED_SOURCE_SERVICE_KEY,
    GET_DOWNLOAD_STATUS_SERVICE_KEY,
    IMPORT_TO_LIBRARY_SERVICE_KEY,
    SEARCH_SERVICE_KEY,
    handle_message,
)
from app.bot.wecom_adapter import (
    WECOM_ENCODING_AES_KEY_BOT_DATA_KEY,
    WECOM_RECEIVE_ID_BOT_DATA_KEY,
    WECOM_TOKEN_BOT_DATA_KEY,
    handle_wecom_private_text_event,
)
from app.db.job_event_repo import JobEventRepo
from app.db.job_repo import JobRepo
from app.db.sqlite import SqliteDatabase
from app.services.add_to_downloader import AddToDownloaderService
from app.services import cleanup_downloaded_source as cleanup_module
from app.services.cleanup_downloaded_source import CleanupDownloadedSourceService
from app.services.cleanup_downloaded_source import (
    CLEANUP_INSPECT_QUERY_USAGE_TEXT,
    CLEANUP_QUERY_USAGE_TEXT,
    CLEANUP_SOURCE_TYPE_UNSUPPORTED_TEXT,
)
from app.services.get_download_status import GetDownloadStatusService
from app.services.import_to_library import ImportToLibraryService
from app.services.search_media import SearchMediaService

_TEST_WECOM_TOKEN = "wecom-token-42"
_TEST_WECOM_ENCODING_AES_KEY = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8"
_TEST_WECOM_RECEIVE_ID = "wwcorp123"
_CHAT_SCOPED_TASK_REF = "cleanup-shortcut"


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


def _make_database(base_dir: Path) -> SqliteDatabase:
    database = SqliteDatabase(str(base_dir / "state.sqlite3"))
    database.initialize()
    return database


def _build_cleanup_service(
    base_dir: Path,
    *,
    chat_id: int | None = None,
    chat_scoped_task_ref: str | None = None,
) -> tuple[CleanupDownloadedSourceService, Path, Path]:
    download_dir = base_dir / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    target_dir = base_dir / "library"
    target_dir.mkdir(parents=True)
    target_file = target_dir / "Dune (2021).mkv"
    target_file.hardlink_to(source_file)

    database = _make_database(base_dir)
    event_repo = JobEventRepo(database)
    job_repo = None
    if chat_id is not None and chat_scoped_task_ref is not None:
        job_repo = JobRepo(database)
        job_repo.upsert_import_job_pending(
            chat_id=chat_id,
            user_id=2001,
            task_ref=chat_scoped_task_ref,
            task_id="87",
            task_hash="hash-87",
        )
    event_repo.append_event(
        task_ref="hash-87" if job_repo is not None else "87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message=str(target_file),
        source_path=str(source_file),
        target_path=str(target_file),
    )
    return CleanupDownloadedSourceService(event_repo, job_repo=job_repo), source_file, target_file


def _build_guard_rejected_cleanup_service(
    base_dir: Path,
    *,
    chat_id: int | None = None,
    chat_scoped_task_ref: str | None = None,
) -> tuple[CleanupDownloadedSourceService, Path, Path]:
    source_dir = base_dir / "downloads" / "Dune.Part.Two.2024"
    source_dir.mkdir(parents=True)
    target_file = source_dir / "movie.mkv"
    target_file.write_bytes(b"demo")

    database = _make_database(base_dir)
    event_repo = JobEventRepo(database)
    job_repo = None
    if chat_id is not None and chat_scoped_task_ref is not None:
        job_repo = JobRepo(database)
        job_repo.upsert_import_job_pending(
            chat_id=chat_id,
            user_id=2001,
            task_ref=chat_scoped_task_ref,
            task_id="87",
            task_hash="hash-87",
        )
    event_repo.append_event(
        task_ref="hash-87" if job_repo is not None else "87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message=str(target_file),
        source_path=str(source_dir),
        target_path=str(target_file),
    )
    return CleanupDownloadedSourceService(event_repo, job_repo=job_repo), source_dir, target_file


def _expected_chat_id(channel: str) -> int:
    if channel == "telegram":
        return 1001
    if channel == "personal_wechat":
        return project_channel_chat_id(channel="personal_wechat", external_chat_id="wx-user-1")
    if channel == "feishu":
        return project_channel_chat_id(channel="feishu", external_chat_id="oc_feishu_chat_1")
    if channel == "wecom":
        return project_channel_chat_id(channel="wecom", external_chat_id="zhangsan")
    raise ValueError(f"unexpected channel: {channel}")


def _build_bot_data(cleanup_service: CleanupDownloadedSourceService) -> dict[str, object]:
    search_service = SearchMediaService(_fake_search)
    return {
        SEARCH_SERVICE_KEY: search_service,
        ADD_TO_DOWNLOADER_SERVICE_KEY: AddToDownloaderService(search_service, AsyncMock()),
        GET_DOWNLOAD_STATUS_SERVICE_KEY: GetDownloadStatusService(AsyncMock()),
        IMPORT_TO_LIBRARY_SERVICE_KEY: ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies"),
        CLEANUP_DOWNLOADED_SOURCE_SERVICE_KEY: cleanup_service,
        WECOM_TOKEN_BOT_DATA_KEY: _TEST_WECOM_TOKEN,
        WECOM_ENCODING_AES_KEY_BOT_DATA_KEY: _TEST_WECOM_ENCODING_AES_KEY,
        WECOM_RECEIVE_ID_BOT_DATA_KEY: _TEST_WECOM_RECEIVE_ID,
    }


def _run_telegram_cleanup_query(query: str, cleanup_service: CleanupDownloadedSourceService) -> str:
    reply_text = AsyncMock()
    message = SimpleNamespace(text=query, reply_text=reply_text)
    update = SimpleNamespace(
        effective_message=message,
        effective_chat=SimpleNamespace(id=1001),
        effective_user=SimpleNamespace(id=2001),
    )
    context = SimpleNamespace(application=SimpleNamespace(bot_data=_build_bot_data(cleanup_service)))

    asyncio.run(handle_message(update, context))

    reply_text.assert_awaited_once()
    return reply_text.await_args.args[0]


def _run_personal_wechat_cleanup_query(query: str, cleanup_service: CleanupDownloadedSourceService) -> str:
    reply_text_func = AsyncMock()
    message = SimpleNamespace(
        message_type=1,
        group_id="",
        from_user_id="wx-user-1",
        message_id=987654321,
        context_token="ctx-1",
        item_list=[SimpleNamespace(type=1, text_item=SimpleNamespace(text=query))],
    )

    asyncio.run(
        handle_personal_wechat_private_text_event(
            account_id="wx-account-1",
            message=message,
            bot_data=_build_bot_data(cleanup_service),
            reply_text_func=reply_text_func,
        )
    )

    reply_text_func.assert_awaited_once()
    return reply_text_func.await_args.args[1]


def _run_feishu_cleanup_query(query: str, cleanup_service: CleanupDownloadedSourceService) -> str:
    reply_text_func = AsyncMock()
    payload = {
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
                "content": f'{{"text":"{query}"}}',
            },
        },
    }

    asyncio.run(
        handle_feishu_private_text_event(
            payload=payload,
            bot_data=_build_bot_data(cleanup_service),
            reply_text_func=reply_text_func,
        )
    )

    reply_text_func.assert_awaited_once()
    return reply_text_func.await_args.args[1]


def _run_wecom_cleanup_query(query: str, cleanup_service: CleanupDownloadedSourceService) -> str:
    reply_text_func = AsyncMock()
    payload_xml = (
        "<xml>"
        f"<ToUserName><![CDATA[{_TEST_WECOM_RECEIVE_ID}]]></ToUserName>"
        "<FromUserName><![CDATA[zhangsan]]></FromUserName>"
        "<CreateTime>1711111111</CreateTime>"
        "<MsgType><![CDATA[text]]></MsgType>"
        f"<Content><![CDATA[{query}]]></Content>"
        "<MsgId>9876543210123456</MsgId>"
        "<AgentID>1000002</AgentID>"
        "</xml>"
    )

    asyncio.run(
        handle_wecom_private_text_event(
            payload_xml=payload_xml,
            bot_data=_build_bot_data(cleanup_service),
            reply_text_func=reply_text_func,
        )
    )

    reply_text_func.assert_awaited_once()
    return reply_text_func.await_args.args[1]


@pytest.mark.parametrize(
    "task_ref",
    [
        "87",
        "hash-87",
    ],
)
@pytest.mark.parametrize(
    ("channel", "runner"),
    [
        ("telegram", _run_telegram_cleanup_query),
        ("personal_wechat", _run_personal_wechat_cleanup_query),
        ("feishu", _run_feishu_cleanup_query),
        ("wecom", _run_wecom_cleanup_query),
    ],
)
def test_cleanup_inspect_smoke_across_private_chat_channels(
    tmp_path: Path,
    task_ref: str,
    channel: str,
    runner,
) -> None:
    cleanup_service, source_file, target_file = _build_cleanup_service(tmp_path / channel)

    reply_text = runner(f"cleanup inspect {task_ref}", cleanup_service)

    assert "清理预检结果：" in reply_text
    assert "当前 guardrail: 允许 cleanup" in reply_text
    assert "cleanup hash-87 / 清理 hash-87：实际清理下载源资产" in reply_text
    assert source_file.exists()
    assert target_file.exists()


@pytest.mark.parametrize(
    "query",
    [
        "cleanup inspect 87",
        "cleanup inspect hash-87",
        "清理检查 87",
        "清理检查 hash-87",
    ],
)
@pytest.mark.parametrize(
    ("channel", "runner"),
    [
        ("telegram", _run_telegram_cleanup_query),
        ("personal_wechat", _run_personal_wechat_cleanup_query),
        ("feishu", _run_feishu_cleanup_query),
        ("wecom", _run_wecom_cleanup_query),
    ],
)
def test_cleanup_inspect_source_type_unsupported_follow_up_smoke_across_private_chat_channels(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    query: str,
    channel: str,
    runner,
) -> None:
    cleanup_service, source_file, target_file = _build_cleanup_service(tmp_path / channel)
    monkeypatch.setattr(
        cleanup_module,
        "_validate_cleanup_paths",
        lambda **_: CLEANUP_SOURCE_TYPE_UNSUPPORTED_TEXT,
    )

    reply_text = runner(query, cleanup_service)

    assert "当前 guardrail: 拒绝 cleanup" in reply_text
    assert CLEANUP_SOURCE_TYPE_UNSUPPORTED_TEXT in reply_text
    assert "当前先不要执行 cleanup" in reply_text
    assert "cleanup inspect hash-87 / 清理检查 hash-87" in reply_text
    assert source_file.exists()
    assert target_file.exists()


@pytest.mark.parametrize(
    "query",
    [
        "cleanup inspect 87",
        "cleanup inspect hash-87",
        "清理检查 87",
        "清理检查 hash-87",
    ],
)
@pytest.mark.parametrize(
    ("channel", "runner"),
    [
        ("telegram", _run_telegram_cleanup_query),
        ("personal_wechat", _run_personal_wechat_cleanup_query),
        ("feishu", _run_feishu_cleanup_query),
        ("wecom", _run_wecom_cleanup_query),
    ],
)
def test_cleanup_inspect_guard_rejected_follow_up_smoke_across_private_chat_channels(
    tmp_path: Path,
    query: str,
    channel: str,
    runner,
) -> None:
    cleanup_service, source_dir, target_file = _build_guard_rejected_cleanup_service(tmp_path / channel)

    reply_text = runner(query, cleanup_service)

    assert "当前 guardrail: 拒绝 cleanup" in reply_text
    assert f"结论: 检测到 source/target 路径关系异常，已拒绝清理：{source_dir} -> {target_file}" in reply_text
    assert "当前先不要执行 cleanup" in reply_text
    assert "cleanup inspect hash-87 / 清理检查 hash-87" in reply_text
    assert source_dir.exists()
    assert target_file.exists()


@pytest.mark.parametrize(
    "task_ref",
    [
        "87",
        "hash-87",
    ],
)
@pytest.mark.parametrize(
    ("channel", "runner"),
    [
        ("telegram", _run_telegram_cleanup_query),
        ("personal_wechat", _run_personal_wechat_cleanup_query),
        ("feishu", _run_feishu_cleanup_query),
        ("wecom", _run_wecom_cleanup_query),
    ],
)
def test_cleanup_execution_smoke_across_private_chat_channels(
    tmp_path: Path,
    task_ref: str,
    channel: str,
    runner,
) -> None:
    cleanup_service, source_file, target_file = _build_cleanup_service(tmp_path / channel)

    reply_text = runner(f"cleanup {task_ref}", cleanup_service)

    assert "已清理下载源资产" in reply_text
    assert "cleanup inspect hash-87 / 清理检查 hash-87：只读预检，不删除任何文件" in reply_text
    assert not source_file.exists()
    assert target_file.exists()


@pytest.mark.parametrize(
    ("cleanup_query", "inspect_query"),
    [
        ("cleanup 87", "cleanup inspect hash-87"),
        ("清理 87", "清理检查 hash-87"),
    ],
)
@pytest.mark.parametrize(
    ("channel", "runner"),
    [
        ("telegram", _run_telegram_cleanup_query),
        ("personal_wechat", _run_personal_wechat_cleanup_query),
        ("feishu", _run_feishu_cleanup_query),
        ("wecom", _run_wecom_cleanup_query),
    ],
)
def test_cleanup_post_success_inspect_confirmation_smoke_across_private_chat_channels(
    tmp_path: Path,
    cleanup_query: str,
    inspect_query: str,
    channel: str,
    runner,
) -> None:
    cleanup_service, source_file, target_file = _build_cleanup_service(tmp_path / channel)

    cleanup_reply = runner(cleanup_query, cleanup_service)
    inspect_reply = runner(inspect_query, cleanup_service)

    assert "已清理下载源资产" in cleanup_reply
    assert "cleanup inspect hash-87 / 清理检查 hash-87：只读预检，不删除任何文件" in cleanup_reply
    assert "源路径状态: 不存在" in inspect_reply
    assert f"结论: 下载源资产已不存在，无需清理：{source_file}" in inspect_reply
    assert "当前先不要执行 cleanup" in inspect_reply
    assert "cleanup inspect hash-87 / 清理检查 hash-87" in inspect_reply
    assert not source_file.exists()
    assert target_file.exists()


@pytest.mark.parametrize(
    ("cleanup_query", "inspect_query"),
    [
        (f"cleanup {_CHAT_SCOPED_TASK_REF}", f"cleanup inspect {_CHAT_SCOPED_TASK_REF}"),
        (f"清理 {_CHAT_SCOPED_TASK_REF}", f"清理检查 {_CHAT_SCOPED_TASK_REF}"),
    ],
)
@pytest.mark.parametrize(
    ("channel", "runner"),
    [
        ("telegram", _run_telegram_cleanup_query),
        ("personal_wechat", _run_personal_wechat_cleanup_query),
        ("feishu", _run_feishu_cleanup_query),
        ("wecom", _run_wecom_cleanup_query),
    ],
)
def test_cleanup_chat_scoped_task_ref_post_success_inspect_confirmation_smoke_across_private_chat_channels(
    tmp_path: Path,
    cleanup_query: str,
    inspect_query: str,
    channel: str,
    runner,
) -> None:
    cleanup_service, source_file, target_file = _build_cleanup_service(
        tmp_path / channel,
        chat_id=_expected_chat_id(channel),
        chat_scoped_task_ref=_CHAT_SCOPED_TASK_REF,
    )

    cleanup_reply = runner(cleanup_query, cleanup_service)
    inspect_reply = runner(inspect_query, cleanup_service)

    assert "已清理下载源资产" in cleanup_reply
    assert "cleanup inspect hash-87 / 清理检查 hash-87：只读预检，不删除任何文件" in cleanup_reply
    assert "任务 ID: 87" in inspect_reply
    assert "任务 Hash: hash-87" in inspect_reply
    assert "源路径状态: 不存在" in inspect_reply
    assert f"结论: 下载源资产已不存在，无需清理：{source_file}" in inspect_reply
    assert "当前先不要执行 cleanup" in inspect_reply
    assert "cleanup inspect hash-87 / 清理检查 hash-87" in inspect_reply
    assert not source_file.exists()
    assert target_file.exists()


@pytest.mark.parametrize(
    "query",
    [
        f"cleanup inspect {_CHAT_SCOPED_TASK_REF}",
        f"清理检查 {_CHAT_SCOPED_TASK_REF}",
    ],
)
@pytest.mark.parametrize(
    ("channel", "runner"),
    [
        ("telegram", _run_telegram_cleanup_query),
        ("personal_wechat", _run_personal_wechat_cleanup_query),
        ("feishu", _run_feishu_cleanup_query),
        ("wecom", _run_wecom_cleanup_query),
    ],
)
def test_cleanup_chat_scoped_task_ref_target_missing_inspect_follow_up_smoke_across_private_chat_channels(
    tmp_path: Path,
    query: str,
    channel: str,
    runner,
) -> None:
    cleanup_service, source_file, target_file = _build_cleanup_service(
        tmp_path / channel,
        chat_id=_expected_chat_id(channel),
        chat_scoped_task_ref=_CHAT_SCOPED_TASK_REF,
    )
    target_file.unlink()

    reply_text = runner(query, cleanup_service)

    assert "任务 ID: 87" in reply_text
    assert "任务 Hash: hash-87" in reply_text
    assert "当前 guardrail: 拒绝 cleanup" in reply_text
    assert f"结论: 库内目标路径不存在，已拒绝清理下载源资产：{target_file}" in reply_text
    assert "当前先不要执行 cleanup" in reply_text
    assert "cleanup inspect hash-87 / 清理检查 hash-87" in reply_text
    assert source_file.exists()
    assert not target_file.exists()


@pytest.mark.parametrize(
    "query",
    [
        f"cleanup inspect {_CHAT_SCOPED_TASK_REF}",
        f"清理检查 {_CHAT_SCOPED_TASK_REF}",
    ],
)
@pytest.mark.parametrize(
    ("channel", "runner"),
    [
        ("telegram", _run_telegram_cleanup_query),
        ("personal_wechat", _run_personal_wechat_cleanup_query),
        ("feishu", _run_feishu_cleanup_query),
        ("wecom", _run_wecom_cleanup_query),
    ],
)
def test_cleanup_chat_scoped_task_ref_source_missing_inspect_follow_up_smoke_across_private_chat_channels(
    tmp_path: Path,
    query: str,
    channel: str,
    runner,
) -> None:
    cleanup_service, source_file, target_file = _build_cleanup_service(
        tmp_path / channel,
        chat_id=_expected_chat_id(channel),
        chat_scoped_task_ref=_CHAT_SCOPED_TASK_REF,
    )
    source_file.unlink()

    reply_text = runner(query, cleanup_service)

    assert "任务 ID: 87" in reply_text
    assert "任务 Hash: hash-87" in reply_text
    assert "当前 guardrail: 拒绝 cleanup" in reply_text
    assert f"结论: 下载源资产已不存在，无需清理：{source_file}" in reply_text
    assert "当前先不要执行 cleanup" in reply_text
    assert "cleanup inspect hash-87 / 清理检查 hash-87" in reply_text
    assert not source_file.exists()
    assert target_file.exists()


@pytest.mark.parametrize(
    ("query", "missing_target"),
    [
        (f"cleanup {_CHAT_SCOPED_TASK_REF}", True),
        (f"清理 {_CHAT_SCOPED_TASK_REF}", True),
        (f"cleanup {_CHAT_SCOPED_TASK_REF}", False),
        (f"清理 {_CHAT_SCOPED_TASK_REF}", False),
    ],
)
@pytest.mark.parametrize(
    ("channel", "runner"),
    [
        ("telegram", _run_telegram_cleanup_query),
        ("personal_wechat", _run_personal_wechat_cleanup_query),
        ("feishu", _run_feishu_cleanup_query),
        ("wecom", _run_wecom_cleanup_query),
    ],
)
def test_cleanup_chat_scoped_task_ref_missing_path_rejection_guidance_smoke_across_private_chat_channels(
    tmp_path: Path,
    query: str,
    missing_target: bool,
    channel: str,
    runner,
) -> None:
    cleanup_service, source_file, target_file = _build_cleanup_service(
        tmp_path / channel,
        chat_id=_expected_chat_id(channel),
        chat_scoped_task_ref=_CHAT_SCOPED_TASK_REF,
    )
    if missing_target:
        target_file.unlink()
    else:
        source_file.unlink()

    reply_text = runner(query, cleanup_service)

    if missing_target:
        assert f"库内目标路径不存在，已拒绝清理下载源资产：{target_file}" in reply_text
        assert source_file.exists()
        assert not target_file.exists()
    else:
        assert f"下载源资产已不存在，无需清理：{source_file}" in reply_text
        assert not source_file.exists()
        assert target_file.exists()
    assert "cleanup inspect hash-87 / 清理检查 hash-87：只读预检，不删除任何文件" in reply_text
    assert "cleanup hash-87 / 清理 hash-87：实际清理下载源资产" in reply_text
    assert f"cleanup inspect {_CHAT_SCOPED_TASK_REF}" not in reply_text
    assert f"cleanup {_CHAT_SCOPED_TASK_REF}：" not in reply_text


@pytest.mark.parametrize(
    "query",
    [
        f"cleanup {_CHAT_SCOPED_TASK_REF}",
        f"清理 {_CHAT_SCOPED_TASK_REF}",
    ],
)
@pytest.mark.parametrize(
    ("channel", "runner"),
    [
        ("telegram", _run_telegram_cleanup_query),
        ("personal_wechat", _run_personal_wechat_cleanup_query),
        ("feishu", _run_feishu_cleanup_query),
        ("wecom", _run_wecom_cleanup_query),
    ],
)
def test_cleanup_chat_scoped_task_ref_source_type_unsupported_rejection_guidance_smoke_across_private_chat_channels(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    query: str,
    channel: str,
    runner,
) -> None:
    cleanup_service, source_file, target_file = _build_cleanup_service(
        tmp_path / channel,
        chat_id=_expected_chat_id(channel),
        chat_scoped_task_ref=_CHAT_SCOPED_TASK_REF,
    )
    monkeypatch.setattr(
        cleanup_module,
        "_validate_cleanup_paths",
        lambda **_: CLEANUP_SOURCE_TYPE_UNSUPPORTED_TEXT,
    )

    reply_text = runner(query, cleanup_service)

    assert CLEANUP_SOURCE_TYPE_UNSUPPORTED_TEXT in reply_text
    assert "cleanup inspect hash-87 / 清理检查 hash-87：只读预检，不删除任何文件" in reply_text
    assert "cleanup hash-87 / 清理 hash-87：实际清理下载源资产" in reply_text
    assert f"cleanup inspect {_CHAT_SCOPED_TASK_REF}" not in reply_text
    assert f"cleanup {_CHAT_SCOPED_TASK_REF}：" not in reply_text
    assert source_file.exists()
    assert target_file.exists()


@pytest.mark.parametrize(
    "query",
    [
        f"cleanup {_CHAT_SCOPED_TASK_REF}",
        f"清理 {_CHAT_SCOPED_TASK_REF}",
    ],
)
@pytest.mark.parametrize(
    ("channel", "runner"),
    [
        ("telegram", _run_telegram_cleanup_query),
        ("personal_wechat", _run_personal_wechat_cleanup_query),
        ("feishu", _run_feishu_cleanup_query),
        ("wecom", _run_wecom_cleanup_query),
    ],
)
def test_cleanup_chat_scoped_task_ref_guard_rejected_rejection_guidance_smoke_across_private_chat_channels(
    tmp_path: Path,
    query: str,
    channel: str,
    runner,
) -> None:
    cleanup_service, source_dir, target_file = _build_guard_rejected_cleanup_service(
        tmp_path / channel,
        chat_id=_expected_chat_id(channel),
        chat_scoped_task_ref=_CHAT_SCOPED_TASK_REF,
    )

    reply_text = runner(query, cleanup_service)

    assert f"检测到 source/target 路径关系异常，已拒绝清理：{source_dir} -> {target_file}" in reply_text
    assert "cleanup inspect hash-87 / 清理检查 hash-87：只读预检，不删除任何文件" in reply_text
    assert "cleanup hash-87 / 清理 hash-87：实际清理下载源资产" in reply_text
    assert f"cleanup inspect {_CHAT_SCOPED_TASK_REF}" not in reply_text
    assert f"cleanup {_CHAT_SCOPED_TASK_REF}：" not in reply_text
    assert source_dir.exists()
    assert target_file.exists()


@pytest.mark.parametrize(
    "query",
    [
        "cleanup inspect 87",
        "cleanup inspect hash-87",
        "清理检查 87",
        "清理检查 hash-87",
    ],
)
@pytest.mark.parametrize(
    ("channel", "runner"),
    [
        ("telegram", _run_telegram_cleanup_query),
        ("personal_wechat", _run_personal_wechat_cleanup_query),
        ("feishu", _run_feishu_cleanup_query),
        ("wecom", _run_wecom_cleanup_query),
    ],
)
def test_cleanup_inspect_target_missing_follow_up_smoke_across_private_chat_channels(
    tmp_path: Path,
    query: str,
    channel: str,
    runner,
) -> None:
    cleanup_service, source_file, target_file = _build_cleanup_service(tmp_path / channel)
    target_file.unlink()

    reply_text = runner(query, cleanup_service)

    assert "当前 guardrail: 拒绝 cleanup" in reply_text
    assert f"结论: 库内目标路径不存在，已拒绝清理下载源资产：{target_file}" in reply_text
    assert "当前先不要执行 cleanup" in reply_text
    assert "cleanup inspect hash-87 / 清理检查 hash-87" in reply_text
    assert source_file.exists()
    assert not target_file.exists()


@pytest.mark.parametrize(
    "query",
    [
        "cleanup inspect 87",
        "cleanup inspect hash-87",
        "清理检查 87",
        "清理检查 hash-87",
    ],
)
@pytest.mark.parametrize(
    ("channel", "runner"),
    [
        ("telegram", _run_telegram_cleanup_query),
        ("personal_wechat", _run_personal_wechat_cleanup_query),
        ("feishu", _run_feishu_cleanup_query),
        ("wecom", _run_wecom_cleanup_query),
    ],
)
def test_cleanup_inspect_source_missing_follow_up_smoke_across_private_chat_channels(
    tmp_path: Path,
    query: str,
    channel: str,
    runner,
) -> None:
    cleanup_service, source_file, target_file = _build_cleanup_service(tmp_path / channel)
    source_file.unlink()

    reply_text = runner(query, cleanup_service)

    assert "当前 guardrail: 拒绝 cleanup" in reply_text
    assert f"结论: 下载源资产已不存在，无需清理：{source_file}" in reply_text
    assert "当前先不要执行 cleanup" in reply_text
    assert "cleanup inspect hash-87 / 清理检查 hash-87" in reply_text
    assert not source_file.exists()
    assert target_file.exists()


@pytest.mark.parametrize(
    "query",
    [
        "cleanup 87",
        "cleanup hash-87",
        "清理 87",
        "清理 hash-87",
    ],
)
@pytest.mark.parametrize(
    ("channel", "runner"),
    [
        ("telegram", _run_telegram_cleanup_query),
        ("personal_wechat", _run_personal_wechat_cleanup_query),
        ("feishu", _run_feishu_cleanup_query),
        ("wecom", _run_wecom_cleanup_query),
    ],
)
def test_cleanup_target_missing_rejection_guidance_smoke_across_private_chat_channels(
    tmp_path: Path,
    query: str,
    channel: str,
    runner,
) -> None:
    cleanup_service, source_file, target_file = _build_cleanup_service(tmp_path / channel)
    target_file.unlink()

    reply_text = runner(query, cleanup_service)

    assert f"库内目标路径不存在，已拒绝清理下载源资产：{target_file}" in reply_text
    assert "cleanup inspect hash-87 / 清理检查 hash-87：只读预检，不删除任何文件" in reply_text
    assert "cleanup hash-87 / 清理 hash-87：实际清理下载源资产" in reply_text
    assert source_file.exists()
    assert not target_file.exists()


@pytest.mark.parametrize(
    "query",
    [
        "cleanup 87",
        "cleanup hash-87",
        "清理 87",
        "清理 hash-87",
    ],
)
@pytest.mark.parametrize(
    ("channel", "runner"),
    [
        ("telegram", _run_telegram_cleanup_query),
        ("personal_wechat", _run_personal_wechat_cleanup_query),
        ("feishu", _run_feishu_cleanup_query),
        ("wecom", _run_wecom_cleanup_query),
    ],
)
def test_cleanup_source_missing_rejection_guidance_smoke_across_private_chat_channels(
    tmp_path: Path,
    query: str,
    channel: str,
    runner,
) -> None:
    cleanup_service, source_file, target_file = _build_cleanup_service(tmp_path / channel)
    source_file.unlink()

    reply_text = runner(query, cleanup_service)

    assert f"下载源资产已不存在，无需清理：{source_file}" in reply_text
    assert "cleanup inspect hash-87 / 清理检查 hash-87：只读预检，不删除任何文件" in reply_text
    assert "cleanup hash-87 / 清理 hash-87：实际清理下载源资产" in reply_text
    assert not source_file.exists()
    assert target_file.exists()


@pytest.mark.parametrize(
    "query",
    [
        "cleanup 87",
        "cleanup hash-87",
        "清理 87",
        "清理 hash-87",
    ],
)
@pytest.mark.parametrize(
    ("channel", "runner"),
    [
        ("telegram", _run_telegram_cleanup_query),
        ("personal_wechat", _run_personal_wechat_cleanup_query),
        ("feishu", _run_feishu_cleanup_query),
        ("wecom", _run_wecom_cleanup_query),
    ],
)
def test_cleanup_source_type_unsupported_rejection_guidance_smoke_across_private_chat_channels(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    query: str,
    channel: str,
    runner,
) -> None:
    cleanup_service, source_file, target_file = _build_cleanup_service(tmp_path / channel)
    monkeypatch.setattr(
        cleanup_module,
        "_validate_cleanup_paths",
        lambda **_: CLEANUP_SOURCE_TYPE_UNSUPPORTED_TEXT,
    )

    reply_text = runner(query, cleanup_service)

    assert CLEANUP_SOURCE_TYPE_UNSUPPORTED_TEXT in reply_text
    assert "cleanup inspect hash-87 / 清理检查 hash-87：只读预检，不删除任何文件" in reply_text
    assert "cleanup hash-87 / 清理 hash-87：实际清理下载源资产" in reply_text
    assert source_file.exists()
    assert target_file.exists()


@pytest.mark.parametrize(
    "query",
    [
        "cleanup 87",
        "cleanup hash-87",
        "清理 87",
        "清理 hash-87",
    ],
)
@pytest.mark.parametrize(
    ("channel", "runner"),
    [
        ("telegram", _run_telegram_cleanup_query),
        ("personal_wechat", _run_personal_wechat_cleanup_query),
        ("feishu", _run_feishu_cleanup_query),
        ("wecom", _run_wecom_cleanup_query),
    ],
)
def test_cleanup_guard_rejected_rejection_guidance_smoke_across_private_chat_channels(
    tmp_path: Path,
    query: str,
    channel: str,
    runner,
) -> None:
    cleanup_service, source_dir, target_file = _build_guard_rejected_cleanup_service(tmp_path / channel)

    reply_text = runner(query, cleanup_service)

    assert f"检测到 source/target 路径关系异常，已拒绝清理：{source_dir} -> {target_file}" in reply_text
    assert "cleanup inspect hash-87 / 清理检查 hash-87：只读预检，不删除任何文件" in reply_text
    assert "cleanup hash-87 / 清理 hash-87：实际清理下载源资产" in reply_text
    assert source_dir.exists()
    assert target_file.exists()


@pytest.mark.parametrize(
    ("query", "task_ref"),
    [
        ("cleanup 87", "87"),
        ("cleanup hash-87", "hash-87"),
        ("清理 87", "87"),
        ("清理 hash-87", "hash-87"),
    ],
)
@pytest.mark.parametrize(
    ("channel", "runner"),
    [
        ("telegram", _run_telegram_cleanup_query),
        ("personal_wechat", _run_personal_wechat_cleanup_query),
        ("feishu", _run_feishu_cleanup_query),
        ("wecom", _run_wecom_cleanup_query),
    ],
)
def test_cleanup_correlation_missing_rejection_guidance_smoke_across_private_chat_channels(
    tmp_path: Path,
    query: str,
    task_ref: str,
    channel: str,
    runner,
) -> None:
    database = _make_database(tmp_path / channel)
    event_repo = JobEventRepo(database)
    cleanup_service = CleanupDownloadedSourceService(event_repo)

    reply_text = runner(query, cleanup_service)

    assert "未找到带 source_path/target_path 的已导入关联，当前任务暂不能执行 cleanup。" in reply_text
    assert (
        f"cleanup inspect {task_ref} / 清理检查 {task_ref}：只读预检，不删除任何文件"
        in reply_text
    )
    assert (
        f"cleanup {task_ref} / 清理 {task_ref}：实际清理下载源资产"
        in reply_text
    )


@pytest.mark.parametrize(
    ("query", "expected_fragment", "expected_follow_up", "expect_source_exists"),
    [
        (
            "清理检查 87",
            "当前 guardrail: 允许 cleanup",
            "cleanup hash-87 / 清理 hash-87：实际清理下载源资产",
            True,
        ),
        (
            "清理检查 hash-87",
            "当前 guardrail: 允许 cleanup",
            "cleanup hash-87 / 清理 hash-87：实际清理下载源资产",
            True,
        ),
        (
            "清理 87",
            "已清理下载源资产",
            "cleanup inspect hash-87 / 清理检查 hash-87：只读预检，不删除任何文件",
            False,
        ),
        (
            "清理 hash-87",
            "已清理下载源资产",
            "cleanup inspect hash-87 / 清理检查 hash-87：只读预检，不删除任何文件",
            False,
        ),
    ],
)
@pytest.mark.parametrize(
    ("channel", "runner"),
    [
        ("telegram", _run_telegram_cleanup_query),
        ("personal_wechat", _run_personal_wechat_cleanup_query),
        ("feishu", _run_feishu_cleanup_query),
        ("wecom", _run_wecom_cleanup_query),
    ],
)
def test_cleanup_protocol_in_chinese_smoke_across_private_chat_channels(
    tmp_path: Path,
    query: str,
    expected_fragment: str,
    expected_follow_up: str,
    expect_source_exists: bool,
    channel: str,
    runner,
) -> None:
    cleanup_service, source_file, target_file = _build_cleanup_service(tmp_path / channel)

    reply_text = runner(query, cleanup_service)

    assert expected_fragment in reply_text
    assert expected_follow_up in reply_text
    assert source_file.exists() is expect_source_exists
    assert target_file.exists()


@pytest.mark.parametrize(
    ("query", "expected_fragment", "expected_follow_up", "expect_source_exists"),
    [
        (
            f"cleanup inspect {_CHAT_SCOPED_TASK_REF}",
            "当前 guardrail: 允许 cleanup",
            "cleanup hash-87 / 清理 hash-87：实际清理下载源资产",
            True,
        ),
        (
            f"cleanup {_CHAT_SCOPED_TASK_REF}",
            "已清理下载源资产",
            "cleanup inspect hash-87 / 清理检查 hash-87：只读预检，不删除任何文件",
            False,
        ),
    ],
)
@pytest.mark.parametrize(
    ("channel", "runner"),
    [
        ("telegram", _run_telegram_cleanup_query),
        ("personal_wechat", _run_personal_wechat_cleanup_query),
        ("feishu", _run_feishu_cleanup_query),
        ("wecom", _run_wecom_cleanup_query),
    ],
)
def test_cleanup_chat_scoped_task_ref_smoke_across_private_chat_channels(
    tmp_path: Path,
    query: str,
    expected_fragment: str,
    expected_follow_up: str,
    expect_source_exists: bool,
    channel: str,
    runner,
) -> None:
    cleanup_service, source_file, target_file = _build_cleanup_service(
        tmp_path / channel,
        chat_id=_expected_chat_id(channel),
        chat_scoped_task_ref=_CHAT_SCOPED_TASK_REF,
    )

    reply_text = runner(query, cleanup_service)

    assert expected_fragment in reply_text
    assert "任务 ID: 87" in reply_text
    assert "任务 Hash: hash-87" in reply_text
    assert expected_follow_up in reply_text
    assert source_file.exists() is expect_source_exists
    assert target_file.exists()


@pytest.mark.parametrize(
    ("query", "expected_fragment", "expected_follow_up", "expect_source_exists"),
    [
        (
            f"清理检查 {_CHAT_SCOPED_TASK_REF}",
            "当前 guardrail: 允许 cleanup",
            "cleanup hash-87 / 清理 hash-87：实际清理下载源资产",
            True,
        ),
        (
            f"清理 {_CHAT_SCOPED_TASK_REF}",
            "已清理下载源资产",
            "cleanup inspect hash-87 / 清理检查 hash-87：只读预检，不删除任何文件",
            False,
        ),
    ],
)
@pytest.mark.parametrize(
    ("channel", "runner"),
    [
        ("telegram", _run_telegram_cleanup_query),
        ("personal_wechat", _run_personal_wechat_cleanup_query),
        ("feishu", _run_feishu_cleanup_query),
        ("wecom", _run_wecom_cleanup_query),
    ],
)
def test_cleanup_chat_scoped_task_ref_in_chinese_smoke_across_private_chat_channels(
    tmp_path: Path,
    query: str,
    expected_fragment: str,
    expected_follow_up: str,
    expect_source_exists: bool,
    channel: str,
    runner,
) -> None:
    cleanup_service, source_file, target_file = _build_cleanup_service(
        tmp_path / channel,
        chat_id=_expected_chat_id(channel),
        chat_scoped_task_ref=_CHAT_SCOPED_TASK_REF,
    )

    reply_text = runner(query, cleanup_service)

    assert expected_fragment in reply_text
    assert "任务 ID: 87" in reply_text
    assert "任务 Hash: hash-87" in reply_text
    assert expected_follow_up in reply_text
    assert source_file.exists() is expect_source_exists
    assert target_file.exists()


@pytest.mark.parametrize(
    ("query", "expected_reply"),
    [
        ("cleanup", CLEANUP_QUERY_USAGE_TEXT),
        ("cleanup inspect", CLEANUP_INSPECT_QUERY_USAGE_TEXT),
        ("清理", CLEANUP_QUERY_USAGE_TEXT),
        ("清理检查", CLEANUP_INSPECT_QUERY_USAGE_TEXT),
    ],
)
@pytest.mark.parametrize(
    ("channel", "runner"),
    [
        ("telegram", _run_telegram_cleanup_query),
        ("personal_wechat", _run_personal_wechat_cleanup_query),
        ("feishu", _run_feishu_cleanup_query),
        ("wecom", _run_wecom_cleanup_query),
    ],
)
def test_cleanup_discoverability_smoke_across_private_chat_channels(
    tmp_path: Path,
    query: str,
    expected_reply: str,
    channel: str,
    runner,
) -> None:
    cleanup_service, _, _ = _build_cleanup_service(tmp_path / channel)

    reply_text = runner(query, cleanup_service)

    assert reply_text == expected_reply

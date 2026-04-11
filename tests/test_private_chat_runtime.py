from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.bot.private_chat_runtime import dispatch_private_chat_text
from app.bot.telegram_bot import (
    ADD_TO_DOWNLOADER_SERVICE_KEY,
    BT_PROCESSING_PATH_PROMPT_TEXT,
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
    }
    if cleanup_service is not None:
        bot_data[CLEANUP_DOWNLOADED_SOURCE_SERVICE_KEY] = cleanup_service
    return bot_data


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


def test_dispatch_private_chat_text_routes_cleanup_inspect_without_telegram_update(
    tmp_path: Path,
) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    target_dir = tmp_path / "library"
    target_dir.mkdir(parents=True)
    target_file = target_dir / "Dune (2021).mkv"
    target_file.hardlink_to(source_file)

    event_repo = JobEventRepo(_make_database(tmp_path))
    event_repo.append_event(
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message=str(target_file),
        source_path=str(source_file),
        target_path=str(target_file),
    )
    cleanup_service = CleanupDownloadedSourceService(event_repo)
    reply_text = AsyncMock()

    asyncio.run(
        dispatch_private_chat_text(
            query="cleanup inspect 87",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data=_build_bot_data(cleanup_service=cleanup_service),
        )
    )

    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "清理预检结果：" in sent_text
    assert "当前 guardrail: 允许 cleanup" in sent_text
    assert "cleanup hash-87 / 清理 hash-87：实际清理下载源资产" in sent_text
    assert source_file.exists()
    assert target_file.exists()


def test_dispatch_private_chat_text_routes_cleanup_inspect_in_chinese_without_telegram_update(
    tmp_path: Path,
) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    target_dir = tmp_path / "library"
    target_dir.mkdir(parents=True)
    target_file = target_dir / "Dune (2021).mkv"
    target_file.hardlink_to(source_file)

    event_repo = JobEventRepo(_make_database(tmp_path))
    event_repo.append_event(
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message=str(target_file),
        source_path=str(source_file),
        target_path=str(target_file),
    )
    cleanup_service = CleanupDownloadedSourceService(event_repo)
    reply_text = AsyncMock()

    asyncio.run(
        dispatch_private_chat_text(
            query="清理检查 87",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data=_build_bot_data(cleanup_service=cleanup_service),
        )
    )

    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "清理预检结果：" in sent_text
    assert "当前 guardrail: 允许 cleanup" in sent_text
    assert "cleanup hash-87 / 清理 hash-87：实际清理下载源资产" in sent_text
    assert source_file.exists()
    assert target_file.exists()


def test_dispatch_private_chat_text_routes_cleanup_execution_without_telegram_update(
    tmp_path: Path,
) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    target_dir = tmp_path / "library"
    target_dir.mkdir(parents=True)
    target_file = target_dir / "Dune (2021).mkv"
    target_file.hardlink_to(source_file)

    event_repo = JobEventRepo(_make_database(tmp_path))
    event_repo.append_event(
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message=str(target_file),
        source_path=str(source_file),
        target_path=str(target_file),
    )
    cleanup_service = CleanupDownloadedSourceService(event_repo)
    reply_text = AsyncMock()

    asyncio.run(
        dispatch_private_chat_text(
            query="cleanup 87",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data=_build_bot_data(cleanup_service=cleanup_service),
        )
    )

    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "已清理下载源资产" in sent_text
    assert "cleanup inspect hash-87 / 清理检查 hash-87：只读预检，不删除任何文件" in sent_text
    assert not source_file.exists()
    assert target_file.exists()


def test_dispatch_private_chat_text_routes_cleanup_execution_in_chinese_without_telegram_update(
    tmp_path: Path,
) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    target_dir = tmp_path / "library"
    target_dir.mkdir(parents=True)
    target_file = target_dir / "Dune (2021).mkv"
    target_file.hardlink_to(source_file)

    event_repo = JobEventRepo(_make_database(tmp_path))
    event_repo.append_event(
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message=str(target_file),
        source_path=str(source_file),
        target_path=str(target_file),
    )
    cleanup_service = CleanupDownloadedSourceService(event_repo)
    reply_text = AsyncMock()

    asyncio.run(
        dispatch_private_chat_text(
            query="清理 87",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data=_build_bot_data(cleanup_service=cleanup_service),
        )
    )

    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "已清理下载源资产" in sent_text
    assert "cleanup inspect hash-87 / 清理检查 hash-87：只读预检，不删除任何文件" in sent_text
    assert not source_file.exists()
    assert target_file.exists()


def test_dispatch_private_chat_text_routes_bare_cleanup_usage_without_telegram_update(
    tmp_path: Path,
) -> None:
    reply_text = AsyncMock()
    cleanup_service = CleanupDownloadedSourceService(JobEventRepo(_make_database(tmp_path)))

    asyncio.run(
        dispatch_private_chat_text(
            query="cleanup",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data=_build_bot_data(cleanup_service=cleanup_service),
        )
    )

    reply_text.assert_awaited_once_with(CLEANUP_QUERY_USAGE_TEXT)


def test_dispatch_private_chat_text_routes_bare_cleanup_inspect_usage_without_telegram_update(
    tmp_path: Path,
) -> None:
    reply_text = AsyncMock()
    cleanup_service = CleanupDownloadedSourceService(JobEventRepo(_make_database(tmp_path)))

    asyncio.run(
        dispatch_private_chat_text(
            query="cleanup inspect",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data=_build_bot_data(cleanup_service=cleanup_service),
        )
    )

    reply_text.assert_awaited_once_with(CLEANUP_INSPECT_QUERY_USAGE_TEXT)


def test_dispatch_private_chat_text_routes_bare_cleanup_usage_in_chinese_without_telegram_update(
    tmp_path: Path,
) -> None:
    reply_text = AsyncMock()
    cleanup_service = CleanupDownloadedSourceService(JobEventRepo(_make_database(tmp_path)))

    asyncio.run(
        dispatch_private_chat_text(
            query="清理",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data=_build_bot_data(cleanup_service=cleanup_service),
        )
    )

    reply_text.assert_awaited_once_with(CLEANUP_QUERY_USAGE_TEXT)


def test_dispatch_private_chat_text_routes_bare_cleanup_inspect_usage_in_chinese_without_telegram_update(
    tmp_path: Path,
) -> None:
    reply_text = AsyncMock()
    cleanup_service = CleanupDownloadedSourceService(JobEventRepo(_make_database(tmp_path)))

    asyncio.run(
        dispatch_private_chat_text(
            query="清理检查",
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data=_build_bot_data(cleanup_service=cleanup_service),
        )
    )

    reply_text.assert_awaited_once_with(CLEANUP_INSPECT_QUERY_USAGE_TEXT)


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
def test_dispatch_private_chat_text_logs_cleanup_service_not_ready_without_telegram_update(
    query: str,
    expected_action: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reply_text = AsyncMock()

    asyncio.run(
        dispatch_private_chat_text(
            query=query,
            reply_func=reply_text,
            chat_id=1001,
            user_id=2001,
            bot_data=_build_bot_data(),
        )
    )
    captured = capsys.readouterr()

    reply_text.assert_awaited_once_with(SERVICE_NOT_READY_TEXT)
    assert "[cleanup 服务未就绪]" in captured.out
    assert f"动作={expected_action}" in captured.out
    assert query in captured.out
    assert "[处理建议]" in captured.out
    assert "cleanup_downloaded_source_service" in captured.out


def _make_database(tmp_path: Path) -> SqliteDatabase:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    return database

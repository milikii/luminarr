from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

from app.bot.private_chat_runtime import dispatch_private_chat_text
from app.bot.telegram_bot import (
    ADD_TO_DOWNLOADER_SERVICE_KEY,
    BT_PROCESSING_PATH_PROMPT_TEXT,
    CLEANUP_DOWNLOADED_SOURCE_SERVICE_KEY,
    GET_DOWNLOAD_STATUS_SERVICE_KEY,
    IMPORT_TO_LIBRARY_SERVICE_KEY,
    SEARCH_SERVICE_KEY,
)
from app.db.job_event_repo import JobEventRepo
from app.db.sqlite import SqliteDatabase
from app.services.add_to_downloader import AddToDownloaderService
from app.services.cleanup_downloaded_source import CleanupDownloadedSourceService
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


def _make_database(tmp_path: Path) -> SqliteDatabase:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    return database

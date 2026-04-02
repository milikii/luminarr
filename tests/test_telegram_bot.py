from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.clients.transmission import TransmissionTaskStatus
from app.bot.telegram_bot import (
    ADD_TO_DOWNLOADER_SERVICE_KEY,
    FRUSTRATION_RESET_TEXT,
    GET_DOWNLOAD_STATUS_SERVICE_KEY,
    IMPORT_TO_LIBRARY_SERVICE_KEY,
    SEARCH_SERVICE_KEY,
    SERVICE_NOT_READY_TEXT,
    TELEGRAM_UPDATE_REPO_KEY,
    build_application,
    handle_message,
)
from app.clients.transmission import TransmissionImportSource
from app.db.approval_repo import ApprovalRepo
from app.db.job_repo import JobRepo
from app.db.sqlite import SqliteDatabase
from app.db.telegram_update_repo import TelegramUpdateRepo
from app.services.add_to_downloader import AddToDownloaderService
from app.services.get_download_status import GetDownloadStatusService
from app.services.import_to_library import IMPORT_CANCELLED_TEXT, ImportToLibraryService
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


def _build_update(
    text: str,
    *,
    chat_id: int = 1001,
    user_id: int = 2001,
    update_id: int = 1,
) -> tuple[SimpleNamespace, AsyncMock]:
    reply_text = AsyncMock()
    message = SimpleNamespace(text=text, reply_text=reply_text)
    update = SimpleNamespace(
        update_id=update_id,
        effective_message=message,
        effective_chat=SimpleNamespace(id=chat_id),
        effective_user=SimpleNamespace(id=user_id),
    )
    return update, reply_text


def test_handle_message_replies_search_result() -> None:
    reply_text = AsyncMock()
    message = SimpleNamespace(text="dune", reply_text=reply_text)
    update = SimpleNamespace(effective_message=message, effective_chat=SimpleNamespace(id=1001))
    search_service = SearchMediaService(_fake_search)
    add_service = AddToDownloaderService(search_service, AsyncMock())
    status_service = GetDownloadStatusService(AsyncMock())
    import_service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies")
    context = SimpleNamespace(application=SimpleNamespace(bot_data={SEARCH_SERVICE_KEY: search_service}))
    context.application.bot_data[ADD_TO_DOWNLOADER_SERVICE_KEY] = add_service
    context.application.bot_data[GET_DOWNLOAD_STATUS_SERVICE_KEY] = status_service
    context.application.bot_data[IMPORT_TO_LIBRARY_SERVICE_KEY] = import_service

    asyncio.run(handle_message(update, context))

    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "搜索结果：dune" in sent_text
    assert "title-dune" in sent_text


def test_handle_message_replies_service_not_ready() -> None:
    reply_text = AsyncMock()
    message = SimpleNamespace(text="dune", reply_text=reply_text)
    update = SimpleNamespace(effective_message=message, effective_chat=SimpleNamespace(id=1001))
    context = SimpleNamespace(application=SimpleNamespace(bot_data={}))
    asyncio.run(handle_message(update, context))
    reply_text.assert_awaited_once_with(SERVICE_NOT_READY_TEXT)


def test_handle_message_digit_routes_to_add_service() -> None:
    reply_text = AsyncMock()
    message = SimpleNamespace(text="1", reply_text=reply_text)
    update = SimpleNamespace(effective_message=message, effective_chat=SimpleNamespace(id=1001))
    search_service = SearchMediaService(_fake_search)
    _run(search_service.search_and_format("dune", chat_id=1001))
    add_service = AddToDownloaderService(
        search_service=search_service,
        add_torrent_func=AsyncMock(return_value=SimpleNamespace(task_id="11", task_hash="h11")),
    )
    status_service = GetDownloadStatusService(AsyncMock())
    import_service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies")
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                SEARCH_SERVICE_KEY: search_service,
                ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
                GET_DOWNLOAD_STATUS_SERVICE_KEY: status_service,
                IMPORT_TO_LIBRARY_SERVICE_KEY: import_service,
            }
        )
    )

    asyncio.run(handle_message(update, context))
    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "任务 ID: 11" in sent_text
    assert "任务 Hash: h11" in sent_text


def test_handle_message_digit_replies_service_not_ready() -> None:
    reply_text = AsyncMock()
    message = SimpleNamespace(text="1", reply_text=reply_text)
    update = SimpleNamespace(effective_message=message, effective_chat=SimpleNamespace(id=1001))
    search_service = SearchMediaService(_fake_search)
    status_service = GetDownloadStatusService(AsyncMock())
    import_service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies")
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                SEARCH_SERVICE_KEY: search_service,
                GET_DOWNLOAD_STATUS_SERVICE_KEY: status_service,
                IMPORT_TO_LIBRARY_SERVICE_KEY: import_service,
            }
        )
    )

    asyncio.run(handle_message(update, context))
    reply_text.assert_awaited_once_with(SERVICE_NOT_READY_TEXT)


def test_handle_message_status_routes_to_status_service() -> None:
    reply_text = AsyncMock()
    message = SimpleNamespace(text="status 87", reply_text=reply_text)
    update = SimpleNamespace(effective_message=message, effective_chat=SimpleNamespace(id=1001))
    search_service = SearchMediaService(_fake_search)
    add_service = AddToDownloaderService(search_service, AsyncMock())
    import_service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies")
    status_service = GetDownloadStatusService(
        AsyncMock(
            return_value=TransmissionTaskStatus(
                task_id="87",
                task_hash="b305bf",
                name="Dune 1984",
                status_code=4,
                percent_done=0.5,
                rate_download=1024,
                eta_seconds=30,
            )
        )
    )
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                SEARCH_SERVICE_KEY: search_service,
                ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
                GET_DOWNLOAD_STATUS_SERVICE_KEY: status_service,
                IMPORT_TO_LIBRARY_SERVICE_KEY: import_service,
            }
        )
    )

    asyncio.run(handle_message(update, context))
    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "下载状态：" in sent_text
    assert "任务 ID: 87" in sent_text


def test_handle_message_status_replies_service_not_ready() -> None:
    reply_text = AsyncMock()
    message = SimpleNamespace(text="status 87", reply_text=reply_text)
    update = SimpleNamespace(effective_message=message, effective_chat=SimpleNamespace(id=1001))
    search_service = SearchMediaService(_fake_search)
    add_service = AddToDownloaderService(search_service, AsyncMock())
    import_service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies")
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                SEARCH_SERVICE_KEY: search_service,
                ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
                IMPORT_TO_LIBRARY_SERVICE_KEY: import_service,
            }
        )
    )

    asyncio.run(handle_message(update, context))
    reply_text.assert_awaited_once_with(SERVICE_NOT_READY_TEXT)


def test_handle_message_status_without_ref_returns_usage() -> None:
    reply_text = AsyncMock()
    message = SimpleNamespace(text="status", reply_text=reply_text)
    update = SimpleNamespace(effective_message=message, effective_chat=SimpleNamespace(id=1001))
    search_service = SearchMediaService(_fake_search)
    add_service = AddToDownloaderService(search_service, AsyncMock())
    status_service = GetDownloadStatusService(AsyncMock())
    import_service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies")
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                SEARCH_SERVICE_KEY: search_service,
                ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
                GET_DOWNLOAD_STATUS_SERVICE_KEY: status_service,
                IMPORT_TO_LIBRARY_SERVICE_KEY: import_service,
            }
        )
    )

    asyncio.run(handle_message(update, context))
    reply_text.assert_awaited_once_with("状态查询格式：status <任务ID或Hash>")


def test_handle_message_import_routes_to_import_service() -> None:
    update, reply_text = _build_update("import 87")
    search_service = SearchMediaService(_fake_search)
    add_service = AddToDownloaderService(search_service, AsyncMock())
    status_service = GetDownloadStatusService(AsyncMock())
    import_service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies")
    import_service.import_by_task_ref = AsyncMock(return_value="导入待确认")
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                SEARCH_SERVICE_KEY: search_service,
                ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
                GET_DOWNLOAD_STATUS_SERVICE_KEY: status_service,
                IMPORT_TO_LIBRARY_SERVICE_KEY: import_service,
            }
        )
    )

    asyncio.run(handle_message(update, context))
    reply_text.assert_awaited_once_with("导入待确认")
    import_service.import_by_task_ref.assert_awaited_once_with("87", chat_id=1001, user_id=2001)


def test_handle_message_import_replies_service_not_ready() -> None:
    reply_text = AsyncMock()
    message = SimpleNamespace(text="import 87", reply_text=reply_text)
    update = SimpleNamespace(effective_message=message, effective_chat=SimpleNamespace(id=1001))
    search_service = SearchMediaService(_fake_search)
    add_service = AddToDownloaderService(search_service, AsyncMock())
    status_service = GetDownloadStatusService(AsyncMock())
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                SEARCH_SERVICE_KEY: search_service,
                ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
                GET_DOWNLOAD_STATUS_SERVICE_KEY: status_service,
            }
        )
    )

    asyncio.run(handle_message(update, context))
    reply_text.assert_awaited_once_with(SERVICE_NOT_READY_TEXT)


def test_handle_message_confirm_routes_to_import_service() -> None:
    update, reply_text = _build_update("confirm 87")
    search_service = SearchMediaService(_fake_search)
    add_service = AddToDownloaderService(search_service, AsyncMock())
    status_service = GetDownloadStatusService(AsyncMock())
    import_service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies")
    import_service.confirm_import_by_task_ref = AsyncMock(return_value="导入成功")
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                SEARCH_SERVICE_KEY: search_service,
                ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
                GET_DOWNLOAD_STATUS_SERVICE_KEY: status_service,
                IMPORT_TO_LIBRARY_SERVICE_KEY: import_service,
            }
        )
    )

    asyncio.run(handle_message(update, context))
    reply_text.assert_awaited_once_with("导入成功")
    import_service.confirm_import_by_task_ref.assert_awaited_once_with(
        "87",
        chat_id=1001,
        user_id=2001,
    )


def test_handle_message_confirm_without_ref_returns_usage() -> None:
    update, reply_text = _build_update("confirm")
    search_service = SearchMediaService(_fake_search)
    add_service = AddToDownloaderService(search_service, AsyncMock())
    status_service = GetDownloadStatusService(AsyncMock())
    import_service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies")
    import_service.confirm_import_by_task_ref = AsyncMock(return_value="确认格式：confirm <任务ID或Hash>")
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                SEARCH_SERVICE_KEY: search_service,
                ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
                GET_DOWNLOAD_STATUS_SERVICE_KEY: status_service,
                IMPORT_TO_LIBRARY_SERVICE_KEY: import_service,
            }
        )
    )

    asyncio.run(handle_message(update, context))
    reply_text.assert_awaited_once_with("确认格式：confirm <任务ID或Hash>")
    import_service.confirm_import_by_task_ref.assert_awaited_once_with(
        "",
        chat_id=1001,
        user_id=2001,
    )


def test_handle_message_confirm_replies_service_not_ready() -> None:
    reply_text = AsyncMock()
    message = SimpleNamespace(text="confirm 87", reply_text=reply_text)
    update = SimpleNamespace(effective_message=message, effective_chat=SimpleNamespace(id=1001))
    search_service = SearchMediaService(_fake_search)
    add_service = AddToDownloaderService(search_service, AsyncMock())
    status_service = GetDownloadStatusService(AsyncMock())
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                SEARCH_SERVICE_KEY: search_service,
                ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
                GET_DOWNLOAD_STATUS_SERVICE_KEY: status_service,
            }
        )
    )

    asyncio.run(handle_message(update, context))
    reply_text.assert_awaited_once_with(SERVICE_NOT_READY_TEXT)


def test_handle_message_deduplicates_update(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    update_repo = TelegramUpdateRepo(database)

    update, reply_text = _build_update("dune", update_id=9001)
    search_service = SearchMediaService(_fake_search)
    add_service = AddToDownloaderService(search_service, AsyncMock())
    status_service = GetDownloadStatusService(AsyncMock())
    import_service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies")
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                SEARCH_SERVICE_KEY: search_service,
                ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
                GET_DOWNLOAD_STATUS_SERVICE_KEY: status_service,
                IMPORT_TO_LIBRARY_SERVICE_KEY: import_service,
                TELEGRAM_UPDATE_REPO_KEY: update_repo,
            }
        )
    )

    asyncio.run(handle_message(update, context))
    asyncio.run(handle_message(update, context))

    reply_text.assert_awaited_once()


def test_handle_message_frustration_clears_candidates() -> None:
    update, reply_text = _build_update("算了")
    search_service = SearchMediaService(_fake_search)
    _run(search_service.search_and_format("dune", chat_id=1001))
    add_service = AddToDownloaderService(search_service, AsyncMock())
    status_service = GetDownloadStatusService(AsyncMock())
    import_service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies")
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                SEARCH_SERVICE_KEY: search_service,
                ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
                GET_DOWNLOAD_STATUS_SERVICE_KEY: status_service,
                IMPORT_TO_LIBRARY_SERVICE_KEY: import_service,
            }
        )
    )

    asyncio.run(handle_message(update, context))

    reply_text.assert_awaited_once_with(FRUSTRATION_RESET_TEXT)
    assert search_service.get_cached_candidate(1001, 1) is None


def test_handle_message_frustration_cancels_pending_import(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    approval_repo = ApprovalRepo(database)
    job_repo = JobRepo(database)

    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")
    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )

    search_service = SearchMediaService(_fake_search)
    add_service = AddToDownloaderService(search_service, AsyncMock())
    status_service = GetDownloadStatusService(AsyncMock())
    import_service = ImportToLibraryService(
        AsyncMock(return_value=import_source),
        str(tmp_path / "library"),
        approval_repo=approval_repo,
        job_repo=job_repo,
    )
    _run(import_service.import_by_task_ref("87", chat_id=1001, user_id=2001))

    update, reply_text = _build_update("取消", update_id=77)
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                SEARCH_SERVICE_KEY: search_service,
                ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
                GET_DOWNLOAD_STATUS_SERVICE_KEY: status_service,
                IMPORT_TO_LIBRARY_SERVICE_KEY: import_service,
            }
        )
    )

    asyncio.run(handle_message(update, context))

    reply_text.assert_awaited_once_with(IMPORT_CANCELLED_TEXT)


def test_build_application_registers_services() -> None:
    search_service = SearchMediaService(_fake_search)
    add_service = AddToDownloaderService(search_service, AsyncMock())
    status_service = GetDownloadStatusService(AsyncMock())
    import_service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies")
    application = build_application("token", search_service, add_service, status_service, import_service)
    assert application.bot_data[SEARCH_SERVICE_KEY] is search_service
    assert application.bot_data[ADD_TO_DOWNLOADER_SERVICE_KEY] is add_service
    assert application.bot_data[GET_DOWNLOAD_STATUS_SERVICE_KEY] is status_service
    assert application.bot_data[IMPORT_TO_LIBRARY_SERVICE_KEY] is import_service


def _run(coroutine: Awaitable[str]) -> str:
    return asyncio.run(coroutine)

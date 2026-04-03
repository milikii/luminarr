from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from telegram.ext import CallbackQueryHandler

from app.clients.transmission import TransmissionTaskStatus
from app.bot.telegram_bot import (
    ADD_TO_DOWNLOADER_SERVICE_KEY,
    BT_CLASSIFICATION_CANCELLED_TEXT,
    BT_CLASSIFICATION_PENDING_REMINDER_TEXT,
    BT_CLASSIFICATION_PROMPT_TEXT,
    BT_CLASSIFICATION_RESULT_TEXT_TEMPLATE,
    CLARIFICATION_SELECTION_BLOCKED_TEXT,
    CLARIFICATION_RESET_TEXT,
    FRUSTRATION_RESET_TEXT,
    GET_DOWNLOAD_STATUS_SERVICE_KEY,
    IMPORT_TO_LIBRARY_SERVICE_KEY,
    JOB_REPO_KEY,
    LLM_PHYSICAL_FAILURE_SAFE_TEXT,
    MANAGE_WATCHLIST_SERVICE_KEY,
    SEARCH_SERVICE_KEY,
    SERVICE_NOT_READY_TEXT,
    TELEGRAM_UPDATE_REPO_KEY,
    build_application,
    handle_callback_query,
    handle_message,
)
from app.clients.transmission import TransmissionImportSource
from app.db.approval_repo import ApprovalRepo
from app.db.clarification_repo import ClarificationRepo
from app.db.job_repo import JobRepo
from app.db.sqlite import SqliteDatabase
from app.db.telegram_update_repo import TelegramUpdateRepo
from app.db.watchlist_repo import WatchlistRepo
from app.services.add_to_downloader import ADD_CANCELLED_TEXT, AddToDownloaderService
from app.services.get_download_status import GetDownloadStatusService
from app.services.import_to_library import IMPORT_CANCELLED_TEXT, ImportToLibraryService
from app.services.manage_watchlist import ManageWatchlistService
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


async def _fake_search_empty(_: str) -> list[dict[str, object]]:
    return []


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


def _build_callback_update(
    data: str,
    *,
    chat_id: int = 1001,
    user_id: int = 2001,
    callback_query_id: str = "cb-1",
    include_effective_context: bool = True,
) -> tuple[SimpleNamespace, AsyncMock, AsyncMock]:
    reply_text = AsyncMock()
    answer = AsyncMock()
    message = SimpleNamespace(text="origin", reply_text=reply_text, chat=SimpleNamespace(id=chat_id))
    callback_query = SimpleNamespace(
        id=callback_query_id,
        data=data,
        message=message,
        answer=answer,
        from_user=SimpleNamespace(id=user_id),
    )
    update = SimpleNamespace(
        callback_query=callback_query,
        effective_message=message if include_effective_context else None,
        effective_chat=SimpleNamespace(id=chat_id) if include_effective_context else None,
        effective_user=SimpleNamespace(id=user_id) if include_effective_context else None,
    )
    return update, reply_text, answer


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


def test_handle_message_magnet_routes_to_bt_direct_split() -> None:
    update, reply_text = _build_update("magnet:?xt=urn:btih:abcdef1234567890")
    search_service = SearchMediaService(_fake_search)
    search_service.search_and_format = AsyncMock(return_value="不应进入搜索")
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

    reply_text.assert_awaited_once_with(BT_CLASSIFICATION_PROMPT_TEXT)
    search_service.search_and_format.assert_not_awaited()


def test_handle_message_explicit_bt_text_routes_to_bt_direct_split() -> None:
    update, reply_text = _build_update("下载这个 BT")
    search_service = SearchMediaService(_fake_search)
    search_service.search_and_format = AsyncMock(return_value="不应进入搜索")
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

    reply_text.assert_awaited_once_with(BT_CLASSIFICATION_PROMPT_TEXT)
    search_service.search_and_format.assert_not_awaited()


def test_handle_message_bt_classification_reply_when_pending() -> None:
    update, first_reply_text = _build_update("magnet:?xt=urn:btih:abcdef1234567890")
    follow_up_update, second_reply_text = _build_update("movie", update_id=2)
    search_service = SearchMediaService(_fake_search)
    search_service.search_and_format = AsyncMock(return_value="不应进入搜索")
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
    asyncio.run(handle_message(follow_up_update, context))

    first_reply_text.assert_awaited_once_with(BT_CLASSIFICATION_PROMPT_TEXT)
    second_reply_text.assert_awaited_once_with(
        BT_CLASSIFICATION_RESULT_TEXT_TEMPLATE.format(label="电影", kind="movie")
    )
    search_service.search_and_format.assert_not_awaited()


def test_handle_message_bt_classification_cancel_when_pending() -> None:
    update, first_reply_text = _build_update("下载这个 BT")
    cancel_update, second_reply_text = _build_update("取消", update_id=2)
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
    asyncio.run(handle_message(cancel_update, context))

    first_reply_text.assert_awaited_once_with(BT_CLASSIFICATION_PROMPT_TEXT)
    second_reply_text.assert_awaited_once_with(BT_CLASSIFICATION_CANCELLED_TEXT)


def test_handle_message_bt_classification_pending_returns_reminder_for_plain_text() -> None:
    update, first_reply_text = _build_update("magnet:?xt=urn:btih:abcdef1234567890")
    follow_up_update, second_reply_text = _build_update("沙丘", update_id=2)
    search_service = SearchMediaService(_fake_search)
    search_service.search_and_format = AsyncMock(return_value="不应进入搜索")
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
    asyncio.run(handle_message(follow_up_update, context))

    first_reply_text.assert_awaited_once_with(BT_CLASSIFICATION_PROMPT_TEXT)
    second_reply_text.assert_awaited_once_with(BT_CLASSIFICATION_PENDING_REMINDER_TEXT)
    search_service.search_and_format.assert_not_awaited()


def test_handle_message_replies_service_not_ready() -> None:
    reply_text = AsyncMock()
    message = SimpleNamespace(text="dune", reply_text=reply_text)
    update = SimpleNamespace(effective_message=message, effective_chat=SimpleNamespace(id=1001))
    context = SimpleNamespace(application=SimpleNamespace(bot_data={}))
    asyncio.run(handle_message(update, context))
    reply_text.assert_awaited_once_with(SERVICE_NOT_READY_TEXT)


def test_handle_message_search_retries_on_llm_physical_failure_then_succeeds() -> None:
    update, reply_text = _build_update("dune dune dune")
    search_service = SearchMediaService(_fake_search)
    search_service.search_and_format = AsyncMock(
        side_effect=[RuntimeError("413 Payload Too Large"), "搜索结果：dune"]
    )
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

    reply_text.assert_awaited_once_with("搜索结果：dune")
    assert search_service.search_and_format.await_count == 2


def test_handle_message_search_returns_safe_text_when_reactive_recovery_fails() -> None:
    update, reply_text = _build_update("dune dune dune")
    search_service = SearchMediaService(_fake_search)
    search_service.search_and_format = AsyncMock(
        side_effect=[
            RuntimeError("max_output_tokens truncated"),
            RuntimeError("response was truncated"),
        ]
    )
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

    reply_text.assert_awaited_once_with(LLM_PHYSICAL_FAILURE_SAFE_TEXT)
    assert search_service.search_and_format.await_count == 2


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
    assert "下载待确认" in sent_text
    assert "confirm 1" in sent_text


def test_handle_callback_query_digit_routes_to_add_service() -> None:
    update, reply_text, answer = _build_callback_update("1")
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

    asyncio.run(handle_callback_query(update, context))

    answer.assert_awaited_once()
    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "下载待确认" in sent_text
    assert "confirm 1" in sent_text


def test_handle_callback_query_magnet_routes_to_bt_direct_split() -> None:
    update, reply_text, answer = _build_callback_update("magnet:?xt=urn:btih:abcdef1234567890")
    search_service = SearchMediaService(_fake_search)
    search_service.search_and_format = AsyncMock(return_value="不应进入搜索")
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

    asyncio.run(handle_callback_query(update, context))

    answer.assert_awaited_once()
    reply_text.assert_awaited_once_with(BT_CLASSIFICATION_PROMPT_TEXT)


def test_handle_callback_query_bt_classification_reply_when_pending() -> None:
    update, first_reply_text, first_answer = _build_callback_update("magnet:?xt=urn:btih:abcdef1234567890")
    follow_up_update, second_reply_text, second_answer = _build_callback_update("raw_bt", callback_query_id="cb-2")
    search_service = SearchMediaService(_fake_search)
    search_service.search_and_format = AsyncMock(return_value="不应进入搜索")
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

    asyncio.run(handle_callback_query(update, context))
    asyncio.run(handle_callback_query(follow_up_update, context))

    first_answer.assert_awaited_once()
    second_answer.assert_awaited_once()
    first_reply_text.assert_awaited_once_with(BT_CLASSIFICATION_PROMPT_TEXT)
    second_reply_text.assert_awaited_once_with(
        BT_CLASSIFICATION_RESULT_TEXT_TEMPLATE.format(label="其他 BT 资源", kind="raw_bt")
    )
    search_service.search_and_format.assert_not_awaited()


def test_handle_callback_query_digit_uses_callback_context_when_effective_context_missing() -> None:
    update, reply_text, answer = _build_callback_update("1", include_effective_context=False)
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

    asyncio.run(handle_callback_query(update, context))

    answer.assert_awaited_once()
    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "下载待确认" in sent_text
    assert "confirm 1" in sent_text


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


def test_handle_message_digit_blocked_when_clarification_pending() -> None:
    update, reply_text = _build_update("1")
    search_service = SearchMediaService(_fake_search_empty)
    _run(search_service.search_and_format("unknown", chat_id=1001))
    assert search_service.is_clarification_pending(1001)

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
    reply_text.assert_awaited_once_with(CLARIFICATION_SELECTION_BLOCKED_TEXT)


def test_handle_message_digit_blocked_when_clarification_pending_after_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()

    before_restart_service = SearchMediaService(
        _fake_search_empty,
        clarification_repo=ClarificationRepo(database),
    )
    _run(before_restart_service.search_and_format("unknown", chat_id=1001))

    update, reply_text = _build_update("1")
    search_service = SearchMediaService(
        _fake_search,
        clarification_repo=ClarificationRepo(SqliteDatabase(str(db_path))),
    )
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
    reply_text.assert_awaited_once_with(CLARIFICATION_SELECTION_BLOCKED_TEXT)


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


def test_handle_message_watchlist_routes_to_watchlist_service(tmp_path: Path) -> None:
    update, reply_text = _build_update("watchlist add dune 2021")
    search_service = SearchMediaService(_fake_search)
    add_service = AddToDownloaderService(search_service, AsyncMock())
    status_service = GetDownloadStatusService(AsyncMock())
    import_service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies")
    watchlist_service = ManageWatchlistService(WatchlistRepo(_make_database(tmp_path)))
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                SEARCH_SERVICE_KEY: search_service,
                ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
                GET_DOWNLOAD_STATUS_SERVICE_KEY: status_service,
                IMPORT_TO_LIBRARY_SERVICE_KEY: import_service,
                MANAGE_WATCHLIST_SERVICE_KEY: watchlist_service,
            }
        )
    )

    asyncio.run(handle_message(update, context))
    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "已加入想看" in sent_text
    assert "dune" in sent_text


def test_handle_message_watchlist_series_routes_to_watchlist_service(tmp_path: Path) -> None:
    update, reply_text = _build_update("watchlist add series 三体 2023")
    search_service = SearchMediaService(_fake_search)
    add_service = AddToDownloaderService(search_service, AsyncMock())
    status_service = GetDownloadStatusService(AsyncMock())
    import_service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies")
    watchlist_service = ManageWatchlistService(WatchlistRepo(_make_database(tmp_path)))
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                SEARCH_SERVICE_KEY: search_service,
                ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
                GET_DOWNLOAD_STATUS_SERVICE_KEY: status_service,
                IMPORT_TO_LIBRARY_SERVICE_KEY: import_service,
                MANAGE_WATCHLIST_SERVICE_KEY: watchlist_service,
            }
        )
    )

    asyncio.run(handle_message(update, context))
    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "已加入想看" in sent_text
    assert "三体" in sent_text
    assert "类型: 剧集" in sent_text


def test_handle_message_watchlist_replies_service_not_ready() -> None:
    update, reply_text = _build_update("watchlist list")
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


def test_handle_message_confirm_routes_to_add_service_when_downloader_pending(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    approval_repo = ApprovalRepo(database)
    job_repo = JobRepo(database)

    update, reply_text = _build_update("confirm 1")
    search_service = SearchMediaService(_fake_search)
    _run(search_service.search_and_format("dune", chat_id=1001))
    add_service = AddToDownloaderService(
        search_service=search_service,
        add_torrent_func=AsyncMock(return_value=SimpleNamespace(task_id="11", task_hash="h11")),
        approval_repo=approval_repo,
        job_repo=job_repo,
    )
    _run(add_service.add_by_selection(1001, "1", user_id=2001))

    status_service = GetDownloadStatusService(AsyncMock())
    import_service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies")
    import_service.confirm_import_by_task_ref = AsyncMock(return_value="不应走到这里")
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                SEARCH_SERVICE_KEY: search_service,
                ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
                GET_DOWNLOAD_STATUS_SERVICE_KEY: status_service,
                IMPORT_TO_LIBRARY_SERVICE_KEY: import_service,
                JOB_REPO_KEY: job_repo,
            }
        )
    )

    asyncio.run(handle_message(update, context))

    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "任务 ID: 11" in sent_text
    assert "任务 Hash: h11" in sent_text
    import_service.confirm_import_by_task_ref.assert_not_called()


def test_handle_callback_query_confirm_routes_to_add_service_when_downloader_pending(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    approval_repo = ApprovalRepo(database)
    job_repo = JobRepo(database)

    search_service = SearchMediaService(_fake_search)
    _run(search_service.search_and_format("dune", chat_id=1001))
    add_service = AddToDownloaderService(
        search_service=search_service,
        add_torrent_func=AsyncMock(return_value=SimpleNamespace(task_id="11", task_hash="h11")),
        approval_repo=approval_repo,
        job_repo=job_repo,
    )
    _run(add_service.add_by_selection(1001, "1", user_id=2001))

    update, reply_text, answer = _build_callback_update("confirm 1")
    status_service = GetDownloadStatusService(AsyncMock())
    import_service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies")
    import_service.confirm_import_by_task_ref = AsyncMock(return_value="不应走到这里")
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                SEARCH_SERVICE_KEY: search_service,
                ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
                GET_DOWNLOAD_STATUS_SERVICE_KEY: status_service,
                IMPORT_TO_LIBRARY_SERVICE_KEY: import_service,
                JOB_REPO_KEY: job_repo,
            }
        )
    )

    asyncio.run(handle_callback_query(update, context))

    answer.assert_awaited_once()
    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "任务 ID: 11" in sent_text
    assert "任务 Hash: h11" in sent_text
    import_service.confirm_import_by_task_ref.assert_not_called()


def test_handle_message_confirm_routes_stale_downloader_confirm_to_add_service(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    approval_repo = ApprovalRepo(database)
    job_repo = JobRepo(database)

    search_service = SearchMediaService(_fake_search)
    _run(search_service.search_and_format("dune", chat_id=1001))
    add_service = AddToDownloaderService(
        search_service=search_service,
        add_torrent_func=AsyncMock(return_value=SimpleNamespace(task_id="11", task_hash="h11")),
        approval_repo=approval_repo,
        job_repo=job_repo,
    )
    _run(add_service.add_by_selection(1001, "1", user_id=2001))
    _run(add_service.confirm_add_by_task_ref("1", chat_id=1001, user_id=2001))

    update, reply_text = _build_update("confirm 1")
    status_service = GetDownloadStatusService(AsyncMock())
    import_service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies")
    import_service.confirm_import_by_task_ref = AsyncMock(return_value="不应走到这里")
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                SEARCH_SERVICE_KEY: search_service,
                ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
                GET_DOWNLOAD_STATUS_SERVICE_KEY: status_service,
                IMPORT_TO_LIBRARY_SERVICE_KEY: import_service,
                JOB_REPO_KEY: job_repo,
            }
        )
    )

    asyncio.run(handle_message(update, context))

    reply_text.assert_awaited_once_with("没有待确认的下载请求，请先重新发送序号。")
    import_service.confirm_import_by_task_ref.assert_not_called()


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


def test_handle_callback_query_deduplicates_update(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    update_repo = TelegramUpdateRepo(database)

    update, reply_text, answer = _build_callback_update("dune", callback_query_id="cb-9001")
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

    asyncio.run(handle_callback_query(update, context))
    asyncio.run(handle_callback_query(update, context))

    answer.assert_awaited_once()
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


def test_handle_message_frustration_resets_pending_clarification() -> None:
    update, reply_text = _build_update("重来")
    search_service = SearchMediaService(_fake_search_empty)
    _run(search_service.search_and_format("unknown", chat_id=1001))
    assert search_service.is_clarification_pending(1001)
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

    reply_text.assert_awaited_once_with(CLARIFICATION_RESET_TEXT)
    assert not search_service.is_clarification_pending(1001)


def test_handle_message_frustration_without_state_still_routes_to_search() -> None:
    update, reply_text = _build_update("算了")
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

    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "搜索结果：算了" in sent_text


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


def test_handle_message_frustration_cancels_pending_downloader(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    approval_repo = ApprovalRepo(database)
    job_repo = JobRepo(database)

    search_service = SearchMediaService(_fake_search)
    _run(search_service.search_and_format("dune", chat_id=1001))
    add_service = AddToDownloaderService(
        search_service,
        AsyncMock(return_value=SimpleNamespace(task_id="11", task_hash="h11")),
        approval_repo=approval_repo,
        job_repo=job_repo,
    )
    _run(add_service.add_by_selection(1001, "1", user_id=2001))

    status_service = GetDownloadStatusService(AsyncMock())
    import_service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies")

    update, reply_text = _build_update("取消", update_id=78)
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                SEARCH_SERVICE_KEY: search_service,
                ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
                GET_DOWNLOAD_STATUS_SERVICE_KEY: status_service,
                IMPORT_TO_LIBRARY_SERVICE_KEY: import_service,
                JOB_REPO_KEY: job_repo,
            }
        )
    )

    asyncio.run(handle_message(update, context))

    reply_text.assert_awaited_once_with(ADD_CANCELLED_TEXT)


def test_build_application_registers_services() -> None:
    search_service = SearchMediaService(_fake_search)
    add_service = AddToDownloaderService(search_service, AsyncMock())
    status_service = GetDownloadStatusService(AsyncMock())
    import_service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies")
    watchlist_db = SqliteDatabase(":memory:")
    watchlist_db.initialize()
    watchlist_service = ManageWatchlistService(WatchlistRepo(watchlist_db))
    database = SqliteDatabase(":memory:")
    database.initialize()
    job_repo = JobRepo(database)
    application = build_application(
        "token",
        search_service,
        add_service,
        status_service,
        import_service,
        watchlist_service,
        job_repo=job_repo,
    )
    assert application.bot_data[SEARCH_SERVICE_KEY] is search_service
    assert application.bot_data[ADD_TO_DOWNLOADER_SERVICE_KEY] is add_service
    assert application.bot_data[GET_DOWNLOAD_STATUS_SERVICE_KEY] is status_service
    assert application.bot_data[IMPORT_TO_LIBRARY_SERVICE_KEY] is import_service
    assert application.bot_data[MANAGE_WATCHLIST_SERVICE_KEY] is watchlist_service
    assert application.bot_data[JOB_REPO_KEY] is job_repo
    assert any(
        isinstance(handler, CallbackQueryHandler)
        for handlers in application.handlers.values()
        for handler in handlers
    )


def _run(coroutine: Awaitable[str]) -> str:
    return asyncio.run(coroutine)


def _make_database(tmp_path: Path) -> SqliteDatabase:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    return database

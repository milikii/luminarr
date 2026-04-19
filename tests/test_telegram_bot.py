from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call

import pytest
from telegram.ext import CallbackQueryHandler

from app.bot.personal_wechat_login import PERSONAL_WECHAT_LOGIN_SERVICE_KEY, PersonalWeChatLoginService
from app.config import DownloaderInstanceConfig, DownloaderRoleBinding, RawBtDestinationOption
from app.clients.tmdb import TmdbMovie
from app.clients.transmission import TransmissionTaskStatus
from app.db.bt_pending_repo import BtPendingPersistenceError
from app.bot.telegram_bot import (
    ADD_TO_DOWNLOADER_SERVICE_KEY,
    BT_READ_ONLY_HELPER_FAILED_TEXT,
    BT_PENDING_REPO_KEY,
    BT_CLASSIFICATION_PROMPT_TEXT,
    BT_PROCESSING_PATH_CANCELLED_TEXT,
    BT_PROCESSING_PATH_PENDING_REMINDER_TEXT,
    BT_PROCESSING_PATH_PROMPT_TEXT,
    DOWNLOAD_COMPLETION_POLLING_STOP_EVENT_KEY,
    DOWNLOAD_COMPLETION_POLLING_TASK_KEY,
    RAW_BT_DESTINATION_CANCELLED_TEXT,
    RAW_BT_DESTINATION_OPTIONS_KEY,
    RAW_BT_DESTINATION_SERVICE_NOT_READY_TEXT,
    BT_TMDB_ASSOCIATION_CANCELLED_TEXT,
    BT_TMDB_ASSOCIATION_SERVICE_NOT_READY_TEXT,
    BT_TMDB_MOVIE_CANDIDATES_LOOKUP_KEY,
    BT_TMDB_TV_CANDIDATES_LOOKUP_KEY,
    CLARIFICATION_SELECTION_BLOCKED_TEXT,
    CLARIFICATION_RESET_TEXT,
    CLEANUP_DOWNLOADED_SOURCE_SERVICE_KEY,
    DOWNLOADER_INSTANCES_KEY,
    DOWNLOADER_ROLE_BINDING_KEY,
    FRUSTRATION_RESET_TEXT,
    GET_DOWNLOAD_STATUS_SERVICE_KEY,
    IMPORT_TO_LIBRARY_SERVICE_KEY,
    JOB_REPO_KEY,
    LLM_PHYSICAL_FAILURE_SAFE_TEXT,
    MANAGE_BT_SUBSCRIPTION_SERVICE_KEY,
    MANAGE_WATCHLIST_SERVICE_KEY,
    POST_DOWNLOAD_AUTO_IMPORT_SERVICE_KEY,
    POST_DOWNLOAD_AUTO_IMPORT_STOP_EVENT_KEY,
    POST_DOWNLOAD_AUTO_IMPORT_TASK_KEY,
    SEARCH_SERVICE_KEY,
    SERVICE_NOT_READY_TEXT,
    TELEGRAM_UPDATE_REPO_KEY,
    TELEGRAM_SEND_MEDIA_FUNC_KEY,
    TELEGRAM_SEND_TEXT_FUNC_KEY,
    build_application,
    build_telegram_send_media_func,
    handle_callback_query,
    handle_message,
    _get_bt_tmdb_association_pending,
    _get_raw_bt_destination_pending,
    _clear_bt_classification_pending,
    _clear_bt_processing_path_pending,
    _clear_bt_tmdb_association_pending,
    _enter_media_import_bt_flow,
    _enter_pure_bt_flow,
    _is_bt_classification_pending,
    _is_bt_processing_path_pending,
    _pop_bt_classification_pending,
    _pop_bt_processing_path_pending,
    _set_bt_classification_pending,
    _set_bt_processing_path_pending,
    _set_bt_tmdb_association_pending,
    _set_raw_bt_destination_pending,
    _clear_raw_bt_destination_pending,
    _download_completion_polling_loop,
    _poll_pending_download_completion_once,
    _post_download_auto_import_scheduler_loop,
    _run_bt_subscription_scheduler_tick_once,
    _start_post_download_auto_import_scheduler,
    _stop_post_download_auto_import_scheduler,
    _log_bt_subscription_scheduler_config_error,
)
from app.clients.transmission import TransmissionImportSource
from app.db.approval_repo import ApprovalRepo
from app.db.bt_pending_repo import (
    BT_PENDING_STAGE_CLASSIFICATION,
    BT_PENDING_STAGE_PROCESSING_PATH,
    BT_PENDING_STAGE_RAW_BT_DESTINATION,
    BT_PENDING_STAGE_TMDB_ASSOCIATION,
    BtPendingRepo,
)
from app.db.bt_subscription_repo import BtSubscriptionRepo
from app.db.candidate_repo import CandidateMappingRepo
from app.db.clarification_repo import ClarificationRepo
from app.db.download_monitor_repo import DownloadMonitorPersistenceError, DownloadMonitorRepo
from app.db.job_event_repo import JobEventRepo
from app.db.job_repo import JobRepo
from app.db.sqlite import SqliteDatabase
from app.db.telegram_update_repo import TelegramUpdateRepo
from app.db.watchlist_repo import WatchlistRepo
from app.services.add_to_downloader import ADD_CANCELLED_TEXT, AddToDownloaderService
from app.services.cleanup_downloaded_source import CleanupDownloadedSourceService
from app.services.get_download_status import GetDownloadStatusService
from app.services.import_to_library import IMPORT_CANCELLED_TEXT, ImportToLibraryService
from app.services.manage_bt_subscription import ManageBtSubscriptionService
from app.services.manage_watchlist import ManageWatchlistService
from app.services.post_download_auto_import import AutoImportRunResult, PostDownloadAutoImportService
from app.services.search_media import SearchMediaService

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


def test_handle_message_routes_through_dispatch_private_chat_text(monkeypatch: pytest.MonkeyPatch) -> None:
    update, _ = _build_update("dune")
    context = SimpleNamespace(application=SimpleNamespace(bot_data={"key": "value"}))
    dispatch_private_chat_text = AsyncMock()
    monkeypatch.setattr("app.bot.private_chat_runtime.dispatch_private_chat_text", dispatch_private_chat_text)

    asyncio.run(handle_message(update, context))

    dispatch_private_chat_text.assert_awaited_once()
    kwargs = dispatch_private_chat_text.await_args.kwargs
    assert kwargs["query"] == "dune"
    assert kwargs["chat_id"] == 1001
    assert kwargs["user_id"] == 2001
    assert kwargs["bot_data"] is context.application.bot_data
    assert callable(kwargs["reply_func"])


def test_handle_callback_query_routes_through_dispatch_private_chat_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    update, _, answer = _build_callback_update("confirm 87")
    context = SimpleNamespace(application=SimpleNamespace(bot_data={"key": "value"}))
    dispatch_private_chat_text = AsyncMock()
    monkeypatch.setattr("app.bot.private_chat_runtime.dispatch_private_chat_text", dispatch_private_chat_text)

    asyncio.run(handle_callback_query(update, context))

    answer.assert_awaited_once()
    dispatch_private_chat_text.assert_awaited_once()
    kwargs = dispatch_private_chat_text.await_args.kwargs
    assert kwargs["query"] == "confirm 87"
    assert kwargs["chat_id"] == 1001
    assert kwargs["user_id"] == 2001
    assert kwargs["bot_data"] is context.application.bot_data
    assert callable(kwargs["reply_func"])


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
    assert "【电影卡片】" in sent_text
    assert "【搜索结果】 dune" in sent_text
    assert "title-dune" in sent_text
    assert "直接回复 1 继续，例如：1" in sent_text
    assert "电影海报卡片" not in sent_text


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

    reply_text.assert_awaited_once_with(BT_PROCESSING_PATH_PROMPT_TEXT)
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

    reply_text.assert_awaited_once_with(BT_PROCESSING_PATH_PROMPT_TEXT)
    search_service.search_and_format.assert_not_awaited()


def test_handle_message_bt_processing_path_media_import_choice_routes_to_classification_prompt() -> None:
    update, first_reply_text = _build_update("magnet:?xt=urn:btih:abcdef1234567890")
    follow_up_update, second_reply_text = _build_update("影视入库链", update_id=2)
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

    first_reply_text.assert_awaited_once_with(BT_PROCESSING_PATH_PROMPT_TEXT)
    second_reply_text.assert_awaited_once_with(BT_CLASSIFICATION_PROMPT_TEXT)
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

    first_reply_text.assert_awaited_once_with(BT_PROCESSING_PATH_PROMPT_TEXT)
    second_sent_text = second_reply_text.await_args.args[0]
    assert "已记录本次 BT 分类：电影（movie）。" in second_sent_text
    assert "请继续发送片名，可带年份" in second_sent_text
    search_service.search_and_format.assert_not_awaited()


def test_handle_message_bt_processing_path_pure_bt_choice_routes_to_destination_prompt() -> None:
    update, first_reply_text = _build_update("magnet:?xt=urn:btih:abcdef1234567890")
    follow_up_update, second_reply_text = _build_update("纯 BT 下载链", update_id=2)
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
                RAW_BT_DESTINATION_OPTIONS_KEY: (
                    RawBtDestinationOption(
                        key="downloads",
                        label="下载目录",
                        target_dir="/data/raw/downloads",
                    ),
                ),
            }
        )
    )

    asyncio.run(handle_message(update, context))
    asyncio.run(handle_message(follow_up_update, context))

    first_reply_text.assert_awaited_once_with(BT_PROCESSING_PATH_PROMPT_TEXT)
    second_sent_text = second_reply_text.await_args.args[0]
    assert "请选择预设目标目录：" in second_sent_text
    assert "1. 下载目录 [downloads] -> /data/raw/downloads" in second_sent_text
    search_service.search_and_format.assert_not_awaited()


def test_handle_message_bt_raw_classification_reply_when_pending() -> None:
    update, first_reply_text = _build_update("magnet:?xt=urn:btih:abcdef1234567890")
    follow_up_update, second_reply_text = _build_update("raw_bt", update_id=2)
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
                RAW_BT_DESTINATION_OPTIONS_KEY: (
                    RawBtDestinationOption(
                        key="downloads",
                        label="下载目录",
                        target_dir="/data/raw/downloads",
                    ),
                    RawBtDestinationOption(
                        key="archive",
                        label="归档目录",
                        target_dir="/data/raw/archive",
                    ),
                ),
            }
        )
    )

    asyncio.run(handle_message(update, context))
    asyncio.run(handle_message(follow_up_update, context))

    first_reply_text.assert_awaited_once_with(BT_PROCESSING_PATH_PROMPT_TEXT)
    second_sent_text = second_reply_text.await_args.args[0]
    assert "请选择预设目标目录：" in second_sent_text
    assert "1. 下载目录 [downloads] -> /data/raw/downloads" in second_sent_text
    search_service.search_and_format.assert_not_awaited()


def test_handle_message_bt_raw_classification_replies_service_not_ready_without_destinations() -> None:
    update, first_reply_text = _build_update("magnet:?xt=urn:btih:abcdef1234567890")
    follow_up_update, second_reply_text = _build_update("raw_bt", update_id=2)
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

    first_reply_text.assert_awaited_once_with(BT_PROCESSING_PATH_PROMPT_TEXT)
    second_reply_text.assert_awaited_once_with(RAW_BT_DESTINATION_SERVICE_NOT_READY_TEXT)
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

    first_reply_text.assert_awaited_once_with(BT_PROCESSING_PATH_PROMPT_TEXT)
    second_reply_text.assert_awaited_once_with(BT_PROCESSING_PATH_CANCELLED_TEXT)


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

    first_reply_text.assert_awaited_once_with(BT_PROCESSING_PATH_PROMPT_TEXT)
    second_reply_text.assert_awaited_once_with(BT_PROCESSING_PATH_PENDING_REMINDER_TEXT)
    search_service.search_and_format.assert_not_awaited()


def test_handle_message_bt_tmdb_association_succeeds_for_movie() -> None:
    update, first_reply_text = _build_update("magnet:?xt=urn:btih:abcdef1234567890")
    classify_update, second_reply_text = _build_update("movie", update_id=2)
    title_update, third_reply_text = _build_update("Dune 2021", update_id=3)
    search_service = SearchMediaService(_fake_search)
    search_service.search_and_format = AsyncMock(return_value="不应进入搜索")
    add_service = AddToDownloaderService(search_service, AsyncMock())
    status_service = GetDownloadStatusService(AsyncMock())
    import_service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies")

    async def fake_movie_lookup(title: str, year: str) -> list[TmdbMovie]:
        assert title == "Dune"
        assert year == "2021"
        return [TmdbMovie(title="Dune", original_title="Dune", year="2021", tmdb_id="438631")]

    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                SEARCH_SERVICE_KEY: search_service,
                ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
                GET_DOWNLOAD_STATUS_SERVICE_KEY: status_service,
                IMPORT_TO_LIBRARY_SERVICE_KEY: import_service,
                BT_TMDB_MOVIE_CANDIDATES_LOOKUP_KEY: fake_movie_lookup,
            }
        )
    )

    asyncio.run(handle_message(update, context))
    asyncio.run(handle_message(classify_update, context))
    asyncio.run(handle_message(title_update, context))

    first_reply_text.assert_awaited_once_with(BT_PROCESSING_PATH_PROMPT_TEXT)
    assert "请继续发送片名，可带年份" in second_reply_text.await_args.args[0]
    success_text = third_reply_text.await_args.args[0]
    assert "BT 电影 TMDB 关联成功。" in success_text
    assert "标题: Dune" in success_text
    assert "TMDB ID: 438631" in success_text
    search_service.search_and_format.assert_not_awaited()


def test_handle_message_bt_tmdb_association_returns_service_not_ready_when_clear_result_missing(
    tmp_path: Path,
) -> None:
    class _MissingClearResultPendingRepo(BtPendingRepo):
        def clear_pending(self, *, chat_id: int, expected_stage: str | None = None):
            if expected_stage == BT_PENDING_STAGE_TMDB_ASSOCIATION:
                pending_state = self.get_pending(chat_id=chat_id)
                if pending_state is not None and pending_state.stage == BT_PENDING_STAGE_TMDB_ASSOCIATION:
                    return None
            return super().clear_pending(chat_id=chat_id, expected_stage=expected_stage)

    update, first_reply_text = _build_update("magnet:?xt=urn:btih:abcdef1234567890")
    classify_update, second_reply_text = _build_update("movie", update_id=2)
    title_update, third_reply_text = _build_update("Dune 2021", update_id=3)
    search_service = SearchMediaService(_fake_search)
    search_service.search_and_format = AsyncMock(return_value="不应进入搜索")
    add_service = AddToDownloaderService(search_service, AsyncMock())
    status_service = GetDownloadStatusService(AsyncMock())
    import_service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies")

    async def fake_movie_lookup(title: str, year: str) -> list[TmdbMovie]:
        assert title == "Dune"
        assert year == "2021"
        return [TmdbMovie(title="Dune", original_title="Dune", year="2021", tmdb_id="438631")]

    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                SEARCH_SERVICE_KEY: search_service,
                ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
                GET_DOWNLOAD_STATUS_SERVICE_KEY: status_service,
                IMPORT_TO_LIBRARY_SERVICE_KEY: import_service,
                BT_TMDB_MOVIE_CANDIDATES_LOOKUP_KEY: fake_movie_lookup,
                BT_PENDING_REPO_KEY: _MissingClearResultPendingRepo(SqliteDatabase(str(db_path))),
            }
        )
    )

    asyncio.run(handle_message(update, context))
    asyncio.run(handle_message(classify_update, context))
    asyncio.run(handle_message(title_update, context))

    first_reply_text.assert_awaited_once_with(BT_PROCESSING_PATH_PROMPT_TEXT)
    assert "请继续发送片名，可带年份" in second_reply_text.await_args.args[0]
    third_reply_text.assert_awaited_once_with(SERVICE_NOT_READY_TEXT)


def test_handle_message_bt_tmdb_association_returns_ambiguous_text_without_year() -> None:
    update, first_reply_text = _build_update("magnet:?xt=urn:btih:abcdef1234567890")
    classify_update, second_reply_text = _build_update("series", update_id=2)
    title_update, third_reply_text = _build_update("三体", update_id=3)
    search_service = SearchMediaService(_fake_search)
    search_service.search_and_format = AsyncMock(return_value="不应进入搜索")
    add_service = AddToDownloaderService(search_service, AsyncMock())
    status_service = GetDownloadStatusService(AsyncMock())
    import_service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies")

    async def fake_tv_lookup(title: str, year: str) -> list[TmdbMovie]:
        assert title == "三体"
        assert year == ""
        return [
            TmdbMovie(title="三体", original_title="Three-Body", year="2023", tmdb_id="1001", media_type="tv"),
            TmdbMovie(title="三体", original_title="Three Body", year="2024", tmdb_id="1002", media_type="tv"),
        ]

    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                SEARCH_SERVICE_KEY: search_service,
                ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
                GET_DOWNLOAD_STATUS_SERVICE_KEY: status_service,
                IMPORT_TO_LIBRARY_SERVICE_KEY: import_service,
                BT_TMDB_TV_CANDIDATES_LOOKUP_KEY: fake_tv_lookup,
            }
        )
    )

    asyncio.run(handle_message(update, context))
    asyncio.run(handle_message(classify_update, context))
    asyncio.run(handle_message(title_update, context))

    first_reply_text.assert_awaited_once_with(BT_PROCESSING_PATH_PROMPT_TEXT)
    assert "请继续发送片名，可带年份" in second_reply_text.await_args.args[0]
    ambiguous_text = third_reply_text.await_args.args[0]
    assert "TMDB 关联存在多个候选：三体" in ambiguous_text
    assert "1. 三体 (2023) [TMDB ID: 1001]" in ambiguous_text
    assert "2. 三体 (2024) [TMDB ID: 1002]" in ambiguous_text
    search_service.search_and_format.assert_not_awaited()


def test_handle_message_bt_tmdb_association_allows_status_command_while_pending() -> None:
    update, first_reply_text = _build_update("magnet:?xt=urn:btih:abcdef1234567890")
    classify_update, second_reply_text = _build_update("movie", update_id=2)
    status_update, third_reply_text = _build_update("status 87", update_id=3)
    search_service = SearchMediaService(_fake_search)
    search_service.search_and_format = AsyncMock(return_value="不应进入搜索")
    add_service = AddToDownloaderService(search_service, AsyncMock())
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
    asyncio.run(handle_message(classify_update, context))
    asyncio.run(handle_message(status_update, context))

    first_reply_text.assert_awaited_once_with(BT_PROCESSING_PATH_PROMPT_TEXT)
    assert "请继续发送片名，可带年份" in second_reply_text.await_args.args[0]
    assert "任务 ID: 87" in third_reply_text.await_args.args[0]
    search_service.search_and_format.assert_not_awaited()


def test_handle_message_bt_tmdb_association_replies_service_not_ready_when_lookup_missing() -> None:
    update, first_reply_text = _build_update("magnet:?xt=urn:btih:abcdef1234567890")
    classify_update, second_reply_text = _build_update("anime", update_id=2)
    title_update, third_reply_text = _build_update("葬送的芙莉莲 2023", update_id=3)
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
    asyncio.run(handle_message(classify_update, context))
    asyncio.run(handle_message(title_update, context))

    first_reply_text.assert_awaited_once_with(BT_PROCESSING_PATH_PROMPT_TEXT)
    assert "请继续发送片名，可带年份" in second_reply_text.await_args.args[0]
    third_reply_text.assert_awaited_once_with(BT_TMDB_ASSOCIATION_SERVICE_NOT_READY_TEXT)


def test_handle_message_bt_tmdb_association_cancel_when_pending() -> None:
    update, first_reply_text = _build_update("下载这个 BT")
    classify_update, second_reply_text = _build_update("movie", update_id=2)
    cancel_update, third_reply_text = _build_update("取消", update_id=3)
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
    asyncio.run(handle_message(classify_update, context))
    asyncio.run(handle_message(cancel_update, context))

    first_reply_text.assert_awaited_once_with(BT_PROCESSING_PATH_PROMPT_TEXT)
    assert "请继续发送片名，可带年份" in second_reply_text.await_args.args[0]
    third_reply_text.assert_awaited_once_with(BT_TMDB_ASSOCIATION_CANCELLED_TEXT)


def test_handle_message_raw_bt_destination_selection_succeeds() -> None:
    update, first_reply_text = _build_update("下载这个 BT")
    classify_update, second_reply_text = _build_update("raw_bt", update_id=2)
    select_update, third_reply_text = _build_update("2", update_id=3)
    search_service = SearchMediaService(_fake_search)
    search_service.search_and_format = AsyncMock(return_value="不应进入搜索")
    add_service = AddToDownloaderService(search_service, AsyncMock())
    status_service = GetDownloadStatusService(AsyncMock())
    import_service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies")
    options = (
        RawBtDestinationOption(key="downloads", label="下载目录", target_dir="/data/raw/downloads"),
        RawBtDestinationOption(key="archive", label="归档目录", target_dir="/data/raw/archive"),
    )
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                SEARCH_SERVICE_KEY: search_service,
                ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
                GET_DOWNLOAD_STATUS_SERVICE_KEY: status_service,
                IMPORT_TO_LIBRARY_SERVICE_KEY: import_service,
                RAW_BT_DESTINATION_OPTIONS_KEY: options,
            }
        )
    )

    asyncio.run(handle_message(update, context))
    asyncio.run(handle_message(classify_update, context))
    asyncio.run(handle_message(select_update, context))

    first_reply_text.assert_awaited_once_with(BT_PROCESSING_PATH_PROMPT_TEXT)
    assert "请选择预设目标目录：" in second_reply_text.await_args.args[0]
    selected_text = third_reply_text.await_args.args[0]
    assert "已记录 raw_bt 目标目录。" in selected_text
    assert "目录键: archive" in selected_text
    assert "目标路径: /data/raw/archive" in selected_text
    assert "当前还缺少实际的磁力链接" in selected_text


def test_handle_message_raw_bt_destination_selection_returns_service_not_ready_when_clear_result_missing(
    tmp_path: Path,
) -> None:
    class _MissingClearResultPendingRepo(BtPendingRepo):
        def clear_pending(self, *, chat_id: int, expected_stage: str | None = None):
            if expected_stage == BT_PENDING_STAGE_RAW_BT_DESTINATION:
                pending_state = self.get_pending(chat_id=chat_id)
                if pending_state is not None and pending_state.stage == BT_PENDING_STAGE_RAW_BT_DESTINATION:
                    return None
            return super().clear_pending(chat_id=chat_id, expected_stage=expected_stage)

    update, first_reply_text = _build_update("下载这个 BT")
    classify_update, second_reply_text = _build_update("raw_bt", update_id=2)
    select_update, third_reply_text = _build_update("2", update_id=3)
    search_service = SearchMediaService(_fake_search)
    search_service.search_and_format = AsyncMock(return_value="不应进入搜索")
    add_service = AddToDownloaderService(search_service, AsyncMock())
    status_service = GetDownloadStatusService(AsyncMock())
    import_service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies")
    options = (
        RawBtDestinationOption(key="downloads", label="下载目录", target_dir="/data/raw/downloads"),
        RawBtDestinationOption(key="archive", label="归档目录", target_dir="/data/raw/archive"),
    )
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                SEARCH_SERVICE_KEY: search_service,
                ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
                GET_DOWNLOAD_STATUS_SERVICE_KEY: status_service,
                IMPORT_TO_LIBRARY_SERVICE_KEY: import_service,
                RAW_BT_DESTINATION_OPTIONS_KEY: options,
                BT_PENDING_REPO_KEY: _MissingClearResultPendingRepo(SqliteDatabase(str(db_path))),
            }
        )
    )

    asyncio.run(handle_message(update, context))
    asyncio.run(handle_message(classify_update, context))
    asyncio.run(handle_message(select_update, context))

    first_reply_text.assert_awaited_once_with(BT_PROCESSING_PATH_PROMPT_TEXT)
    assert "请选择预设目标目录：" in second_reply_text.await_args.args[0]
    third_reply_text.assert_awaited_once_with(SERVICE_NOT_READY_TEXT)


def test_handle_message_raw_bt_destination_invalid_text_returns_reminder() -> None:
    update, first_reply_text = _build_update("下载这个 BT")
    classify_update, second_reply_text = _build_update("raw_bt", update_id=2)
    invalid_update, third_reply_text = _build_update("随便放", update_id=3)
    search_service = SearchMediaService(_fake_search)
    search_service.search_and_format = AsyncMock(return_value="不应进入搜索")
    add_service = AddToDownloaderService(search_service, AsyncMock())
    status_service = GetDownloadStatusService(AsyncMock())
    import_service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies")
    options = (
        RawBtDestinationOption(key="downloads", label="下载目录", target_dir="/data/raw/downloads"),
        RawBtDestinationOption(key="archive", label="归档目录", target_dir="/data/raw/archive"),
    )
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                SEARCH_SERVICE_KEY: search_service,
                ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
                GET_DOWNLOAD_STATUS_SERVICE_KEY: status_service,
                IMPORT_TO_LIBRARY_SERVICE_KEY: import_service,
                RAW_BT_DESTINATION_OPTIONS_KEY: options,
            }
        )
    )

    asyncio.run(handle_message(update, context))
    asyncio.run(handle_message(classify_update, context))
    asyncio.run(handle_message(invalid_update, context))

    first_reply_text.assert_awaited_once_with(BT_PROCESSING_PATH_PROMPT_TEXT)
    assert "请选择预设目标目录：" in second_reply_text.await_args.args[0]
    invalid_text = third_reply_text.await_args.args[0]
    assert "未识别到有效的 raw_bt 目录选项：随便放" in invalid_text
    assert "1. 下载目录 [downloads] -> /data/raw/downloads" in invalid_text
    search_service.search_and_format.assert_not_awaited()


def test_handle_message_raw_bt_destination_cancel_when_pending() -> None:
    update, first_reply_text = _build_update("下载这个 BT")
    classify_update, second_reply_text = _build_update("raw_bt", update_id=2)
    cancel_update, third_reply_text = _build_update("取消", update_id=3)
    search_service = SearchMediaService(_fake_search)
    add_service = AddToDownloaderService(search_service, AsyncMock())
    status_service = GetDownloadStatusService(AsyncMock())
    import_service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies")
    options = (
        RawBtDestinationOption(key="downloads", label="下载目录", target_dir="/data/raw/downloads"),
    )
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                SEARCH_SERVICE_KEY: search_service,
                ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
                GET_DOWNLOAD_STATUS_SERVICE_KEY: status_service,
                IMPORT_TO_LIBRARY_SERVICE_KEY: import_service,
                RAW_BT_DESTINATION_OPTIONS_KEY: options,
            }
        )
    )

    asyncio.run(handle_message(update, context))
    asyncio.run(handle_message(classify_update, context))
    asyncio.run(handle_message(cancel_update, context))

    first_reply_text.assert_awaited_once_with(BT_PROCESSING_PATH_PROMPT_TEXT)
    assert "请选择预设目标目录：" in second_reply_text.await_args.args[0]
    third_reply_text.assert_awaited_once_with(RAW_BT_DESTINATION_CANCELLED_TEXT)


def test_handle_message_bt_classification_pending_survives_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()

    before_restart_context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                BT_PENDING_REPO_KEY: BtPendingRepo(database),
                SEARCH_SERVICE_KEY: SearchMediaService(_fake_search),
                ADD_TO_DOWNLOADER_SERVICE_KEY: AddToDownloaderService(SearchMediaService(_fake_search), AsyncMock()),
                GET_DOWNLOAD_STATUS_SERVICE_KEY: GetDownloadStatusService(AsyncMock()),
                IMPORT_TO_LIBRARY_SERVICE_KEY: ImportToLibraryService(
                    AsyncMock(return_value=None),
                    "/data/library/movies",
                ),
            }
        )
    )
    before_restart_update, before_restart_reply = _build_update("magnet:?xt=urn:btih:abcdef1234567890")
    asyncio.run(handle_message(before_restart_update, before_restart_context))
    before_restart_reply.assert_awaited_once_with(BT_PROCESSING_PATH_PROMPT_TEXT)

    after_restart_update, after_restart_reply = _build_update("沙丘", update_id=2)
    after_restart_context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                BT_PENDING_REPO_KEY: BtPendingRepo(SqliteDatabase(str(db_path))),
                SEARCH_SERVICE_KEY: SearchMediaService(_fake_search),
                ADD_TO_DOWNLOADER_SERVICE_KEY: AddToDownloaderService(SearchMediaService(_fake_search), AsyncMock()),
                GET_DOWNLOAD_STATUS_SERVICE_KEY: GetDownloadStatusService(AsyncMock()),
                IMPORT_TO_LIBRARY_SERVICE_KEY: ImportToLibraryService(
                    AsyncMock(return_value=None),
                    "/data/library/movies",
                ),
            }
        )
    )

    asyncio.run(handle_message(after_restart_update, after_restart_context))
    after_restart_reply.assert_awaited_once_with(BT_PROCESSING_PATH_PENDING_REMINDER_TEXT)


def test_handle_message_bt_tmdb_association_pending_survives_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()

    async def fake_movie_lookup(title: str, year: str) -> list[TmdbMovie]:
        assert title == "Dune"
        assert year == "2021"
        return [TmdbMovie(title="Dune", original_title="Dune", year="2021", tmdb_id="438631")]

    before_restart_context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                BT_PENDING_REPO_KEY: BtPendingRepo(database),
                SEARCH_SERVICE_KEY: SearchMediaService(_fake_search),
                ADD_TO_DOWNLOADER_SERVICE_KEY: AddToDownloaderService(SearchMediaService(_fake_search), AsyncMock()),
                GET_DOWNLOAD_STATUS_SERVICE_KEY: GetDownloadStatusService(AsyncMock()),
                IMPORT_TO_LIBRARY_SERVICE_KEY: ImportToLibraryService(
                    AsyncMock(return_value=None),
                    "/data/library/movies",
                ),
            }
        )
    )
    first_update, first_reply = _build_update("magnet:?xt=urn:btih:abcdef1234567890")
    second_update, second_reply = _build_update("movie", update_id=2)
    asyncio.run(handle_message(first_update, before_restart_context))
    asyncio.run(handle_message(second_update, before_restart_context))
    first_reply.assert_awaited_once_with(BT_PROCESSING_PATH_PROMPT_TEXT)
    assert "请继续发送片名，可带年份" in second_reply.await_args.args[0]

    after_restart_update, after_restart_reply = _build_update("Dune 2021", update_id=3)
    after_restart_context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                BT_PENDING_REPO_KEY: BtPendingRepo(SqliteDatabase(str(db_path))),
                SEARCH_SERVICE_KEY: SearchMediaService(_fake_search),
                ADD_TO_DOWNLOADER_SERVICE_KEY: AddToDownloaderService(SearchMediaService(_fake_search), AsyncMock()),
                GET_DOWNLOAD_STATUS_SERVICE_KEY: GetDownloadStatusService(AsyncMock()),
                IMPORT_TO_LIBRARY_SERVICE_KEY: ImportToLibraryService(
                    AsyncMock(return_value=None),
                    "/data/library/movies",
                ),
                BT_TMDB_MOVIE_CANDIDATES_LOOKUP_KEY: fake_movie_lookup,
            }
        )
    )

    asyncio.run(handle_message(after_restart_update, after_restart_context))
    success_text = after_restart_reply.await_args.args[0]
    assert "BT 电影 TMDB 关联成功。" in success_text
    assert "TMDB ID: 438631" in success_text


def test_handle_message_raw_bt_destination_pending_survives_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()

    options = (
        RawBtDestinationOption(key="downloads", label="下载目录", target_dir="/data/raw/downloads"),
        RawBtDestinationOption(key="archive", label="归档目录", target_dir="/data/raw/archive"),
    )
    before_restart_context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                BT_PENDING_REPO_KEY: BtPendingRepo(database),
                SEARCH_SERVICE_KEY: SearchMediaService(_fake_search),
                ADD_TO_DOWNLOADER_SERVICE_KEY: AddToDownloaderService(SearchMediaService(_fake_search), AsyncMock()),
                GET_DOWNLOAD_STATUS_SERVICE_KEY: GetDownloadStatusService(AsyncMock()),
                IMPORT_TO_LIBRARY_SERVICE_KEY: ImportToLibraryService(
                    AsyncMock(return_value=None),
                    "/data/library/movies",
                ),
                RAW_BT_DESTINATION_OPTIONS_KEY: options,
            }
        )
    )
    first_update, first_reply = _build_update("下载这个 BT")
    second_update, second_reply = _build_update("raw_bt", update_id=2)
    asyncio.run(handle_message(first_update, before_restart_context))
    asyncio.run(handle_message(second_update, before_restart_context))
    first_reply.assert_awaited_once_with(BT_PROCESSING_PATH_PROMPT_TEXT)
    assert "请选择预设目标目录：" in second_reply.await_args.args[0]

    after_restart_update, after_restart_reply = _build_update("downloads", update_id=3)
    after_restart_context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                BT_PENDING_REPO_KEY: BtPendingRepo(SqliteDatabase(str(db_path))),
                SEARCH_SERVICE_KEY: SearchMediaService(_fake_search),
                ADD_TO_DOWNLOADER_SERVICE_KEY: AddToDownloaderService(SearchMediaService(_fake_search), AsyncMock()),
                GET_DOWNLOAD_STATUS_SERVICE_KEY: GetDownloadStatusService(AsyncMock()),
                IMPORT_TO_LIBRARY_SERVICE_KEY: ImportToLibraryService(
                    AsyncMock(return_value=None),
                    "/data/library/movies",
                ),
                RAW_BT_DESTINATION_OPTIONS_KEY: options,
            }
        )
    )

    asyncio.run(handle_message(after_restart_update, after_restart_context))
    selected_text = after_restart_reply.await_args.args[0]
    assert "已记录 raw_bt 目标目录。" in selected_text
    assert "目录键: downloads" in selected_text
    assert "当前还缺少实际的磁力链接" in selected_text


def test_bt_processing_path_pending_logs_payload_corruption_after_restart(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()
    BtPendingRepo(database).upsert_pending(
        chat_id=1001,
        stage=BT_PENDING_STAGE_PROCESSING_PATH,
        payload_json="{",
    )
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={BT_PENDING_REPO_KEY: BtPendingRepo(SqliteDatabase(str(db_path)))}
        )
    )

    assert _is_bt_processing_path_pending(context=context, chat_id=1001) is None
    output = capsys.readouterr().out
    assert "[BT 待处理载荷损坏]" in output
    assert "stage=processing_path" in output
    assert "payload_json invalid json" in output


def test_bt_processing_path_pending_logs_missing_source_after_restart(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()
    BtPendingRepo(database).upsert_pending(
        chat_id=1001,
        stage=BT_PENDING_STAGE_PROCESSING_PATH,
        payload_json='{}',
    )
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={BT_PENDING_REPO_KEY: BtPendingRepo(SqliteDatabase(str(db_path)))}
        )
    )

    assert _is_bt_processing_path_pending(context=context, chat_id=1001) is None
    output = capsys.readouterr().out
    assert "[BT 待处理载荷损坏]" in output
    assert "stage=processing_path" in output
    assert "payload.source missing" in output


def test_bt_processing_path_pending_logs_read_failure(capsys: pytest.CaptureFixture[str]) -> None:
    class _FailingPendingRepo(BtPendingRepo):
        def get_pending(self, *, chat_id: int):
            raise RuntimeError("db down")

    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={BT_PENDING_REPO_KEY: _FailingPendingRepo(SqliteDatabase(":memory:"))}
        )
    )

    assert _is_bt_processing_path_pending(context=context, chat_id=1001) is None

    output = capsys.readouterr().out
    assert "[BT 待处理读取失败]" in output
    assert "stage=processing_path" in output
    assert "db down" in output
    assert "当前相关入口会按状态不可用处理" in output


def test_bt_processing_path_pending_logs_row_corruption_after_restart(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO bt_pending_state (chat_id, stage, payload_json, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (1001, "   ", '{"source":"magnet:?xt=urn:btih:abcdef"}'),
        )
        connection.commit()

    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={BT_PENDING_REPO_KEY: BtPendingRepo(SqliteDatabase(str(db_path)))}
        )
    )

    assert _is_bt_processing_path_pending(context=context, chat_id=1001) is None

    output = capsys.readouterr().out
    assert "[BT 待处理记录损坏]" in output
    assert "stage=processing_path" in output
    assert "bt_pending_state stage empty after read" in output


def test_pop_bt_processing_path_pending_logs_missing_source_after_restart(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()
    BtPendingRepo(database).upsert_pending(
        chat_id=1001,
        stage=BT_PENDING_STAGE_PROCESSING_PATH,
        payload_json='{}',
    )
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={BT_PENDING_REPO_KEY: BtPendingRepo(SqliteDatabase(str(db_path)))}
        )
    )

    assert _pop_bt_processing_path_pending(context=context, chat_id=1001) is None
    output = capsys.readouterr().out
    assert "[BT 待处理载荷损坏]" in output
    assert "stage=processing_path" in output
    assert "payload.source missing" in output


def test_set_bt_processing_path_pending_logs_persistence_failure(capsys: pytest.CaptureFixture[str]) -> None:
    class _FailingPendingRepo(BtPendingRepo):
        def upsert_pending(self, *, chat_id: int, stage: str, payload_json: str = "") -> None:
            raise RuntimeError("db down")

    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={BT_PENDING_REPO_KEY: _FailingPendingRepo(SqliteDatabase(":memory:"))}
        )
    )

    assert (
        _set_bt_processing_path_pending(
            context=context,
            chat_id=1001,
            source="magnet:?xt=urn:btih:abc",
        )
        is False
    )

    assert context.application.bot_data.get("bt_processing_path_pending_by_chat", {}) == {}
    output = capsys.readouterr().out
    assert "[BT 待处理持久化失败]" in output
    assert "stage=processing_path" in output
    assert "db down" in output


def test_set_bt_processing_path_pending_logs_missing_row_after_upsert(
    capsys: pytest.CaptureFixture[str],
) -> None:
    class _MissingRowPendingRepo(BtPendingRepo):
        def upsert_pending(self, *, chat_id: int, stage: str, payload_json: str = "") -> None:
            _ = (chat_id, stage, payload_json)
            raise BtPendingPersistenceError("bt_pending_state missing after upsert")

    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={BT_PENDING_REPO_KEY: _MissingRowPendingRepo(SqliteDatabase(":memory:"))}
        )
    )

    assert (
        _set_bt_processing_path_pending(
            context=context,
            chat_id=1001,
            source="magnet:?xt=urn:btih:abc",
        )
        is False
    )

    assert context.application.bot_data.get("bt_processing_path_pending_by_chat", {}) == {}
    output = capsys.readouterr().out
    assert "[BT 待处理写入后记录缺失]" in output
    assert "[处理建议]" in output
    assert "stage=processing_path" in output
    assert "bt_pending_state missing after upsert" in output


def test_clear_bt_processing_path_pending_logs_persistence_failure(capsys: pytest.CaptureFixture[str]) -> None:
    class _FailingPendingRepo(BtPendingRepo):
        def clear_pending(self, *, chat_id: int, expected_stage: str | None = None) -> bool:
            raise RuntimeError("db down")

    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                BT_PENDING_REPO_KEY: _FailingPendingRepo(SqliteDatabase(":memory:")),
                "bt_processing_path_pending_by_chat": {1001: "magnet:?xt=urn:btih:abc"},
            }
        )
    )

    assert _clear_bt_processing_path_pending(context=context, chat_id=1001) is None
    assert context.application.bot_data["bt_processing_path_pending_by_chat"][1001] == "magnet:?xt=urn:btih:abc"

    output = capsys.readouterr().out
    assert "[BT 待处理清理失败]" in output
    assert "stage=processing_path" in output
    assert "db down" in output


def test_clear_bt_processing_path_pending_logs_missing_clear_result(capsys: pytest.CaptureFixture[str]) -> None:
    class _MissingClearResultPendingRepo(BtPendingRepo):
        def clear_pending(self, *, chat_id: int, expected_stage: str | None = None):
            _ = (chat_id, expected_stage)
            return None

    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                BT_PENDING_REPO_KEY: _MissingClearResultPendingRepo(SqliteDatabase(":memory:")),
                "bt_processing_path_pending_by_chat": {1001: "magnet:?xt=urn:btih:abc"},
            }
        )
    )

    assert _clear_bt_processing_path_pending(context=context, chat_id=1001) is None
    assert context.application.bot_data["bt_processing_path_pending_by_chat"][1001] == "magnet:?xt=urn:btih:abc"

    output = capsys.readouterr().out
    assert "[BT 待处理清理结果缺失]" in output
    assert "[处理建议]" in output
    assert "stage=processing_path" in output
    assert "bt_pending_state clear result missing" in output


def test_pop_bt_processing_path_pending_logs_persistence_failure(capsys: pytest.CaptureFixture[str]) -> None:
    class _FailingPendingRepo(BtPendingRepo):
        def clear_pending(self, *, chat_id: int, expected_stage: str | None = None) -> bool:
            raise RuntimeError("db down")

    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                BT_PENDING_REPO_KEY: _FailingPendingRepo(SqliteDatabase(":memory:")),
                "bt_processing_path_pending_by_chat": {1001: "magnet:?xt=urn:btih:abc"},
            }
        )
    )

    assert _pop_bt_processing_path_pending(context=context, chat_id=1001) is False
    assert context.application.bot_data["bt_processing_path_pending_by_chat"][1001] == "magnet:?xt=urn:btih:abc"

    output = capsys.readouterr().out
    assert "[BT 待处理清理失败]" in output
    assert "stage=processing_path" in output
    assert "db down" in output


def test_pop_bt_processing_path_pending_logs_missing_clear_result_after_restart(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()
    repo = BtPendingRepo(database)
    repo.upsert_pending(
        chat_id=1001,
        stage=BT_PENDING_STAGE_PROCESSING_PATH,
        payload_json='{"source":"magnet:?xt=urn:btih:abc"}',
    )

    class _MissingClearResultPendingRepo(BtPendingRepo):
        def clear_pending(self, *, chat_id: int, expected_stage: str | None = None):
            _ = (chat_id, expected_stage)
            return None

    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={BT_PENDING_REPO_KEY: _MissingClearResultPendingRepo(SqliteDatabase(str(db_path)))}
        )
    )

    assert _pop_bt_processing_path_pending(context=context, chat_id=1001) is False
    assert context.application.bot_data["bt_processing_path_pending_by_chat"][1001] == "magnet:?xt=urn:btih:abc"

    output = capsys.readouterr().out
    assert "[BT 待处理清理结果缺失]" in output
    assert "[处理建议]" in output
    assert "stage=processing_path" in output
    assert "bt_pending_state clear result missing" in output


def test_pop_bt_processing_path_pending_logs_read_failure(capsys: pytest.CaptureFixture[str]) -> None:
    class _FailingPendingRepo(BtPendingRepo):
        def get_pending(self, *, chat_id: int):
            raise RuntimeError("db down")

    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={BT_PENDING_REPO_KEY: _FailingPendingRepo(SqliteDatabase(":memory:"))}
        )
    )

    assert _pop_bt_processing_path_pending(context=context, chat_id=1001) is None

    output = capsys.readouterr().out
    assert "[BT 待处理读取失败]" in output
    assert "stage=processing_path" in output
    assert "db down" in output


def test_bt_classification_pending_logs_payload_corruption_after_restart(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()
    BtPendingRepo(database).upsert_pending(
        chat_id=1001,
        stage=BT_PENDING_STAGE_CLASSIFICATION,
        payload_json="{",
    )
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={BT_PENDING_REPO_KEY: BtPendingRepo(SqliteDatabase(str(db_path)))}
        )
    )

    assert _is_bt_classification_pending(context=context, chat_id=1001) is None
    output = capsys.readouterr().out
    assert "[BT 待处理载荷损坏]" in output
    assert "stage=classification" in output
    assert "payload_json invalid json" in output


def test_bt_classification_pending_logs_missing_query_after_restart(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()
    BtPendingRepo(database).upsert_pending(
        chat_id=1001,
        stage=BT_PENDING_STAGE_CLASSIFICATION,
        payload_json='{}',
    )
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={BT_PENDING_REPO_KEY: BtPendingRepo(SqliteDatabase(str(db_path)))}
        )
    )

    assert _is_bt_classification_pending(context=context, chat_id=1001) is None
    output = capsys.readouterr().out
    assert "[BT 待处理载荷损坏]" in output
    assert "stage=classification" in output
    assert "payload.query missing" in output


def test_bt_classification_pending_logs_read_failure(capsys: pytest.CaptureFixture[str]) -> None:
    class _FailingPendingRepo(BtPendingRepo):
        def get_pending(self, *, chat_id: int):
            raise RuntimeError("db down")

    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={BT_PENDING_REPO_KEY: _FailingPendingRepo(SqliteDatabase(":memory:"))}
        )
    )

    assert _is_bt_classification_pending(context=context, chat_id=1001) is None

    output = capsys.readouterr().out
    assert "[BT 待处理读取失败]" in output
    assert "stage=classification" in output
    assert "db down" in output


def test_set_bt_classification_pending_logs_persistence_failure(capsys: pytest.CaptureFixture[str]) -> None:
    class _FailingPendingRepo(BtPendingRepo):
        def upsert_pending(self, *, chat_id: int, stage: str, payload_json: str = "") -> None:
            raise RuntimeError("db down")

    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={BT_PENDING_REPO_KEY: _FailingPendingRepo(SqliteDatabase(":memory:"))}
        )
    )

    assert (
        _set_bt_classification_pending(
            context=context,
            chat_id=1001,
            query="magnet:?xt=urn:btih:abc",
        )
        is False
    )

    assert context.application.bot_data.get("bt_classification_pending_by_chat", {}) == {}
    output = capsys.readouterr().out
    assert "[BT 待处理持久化失败]" in output
    assert "stage=classification" in output
    assert "db down" in output


def test_clear_bt_classification_pending_logs_persistence_failure(capsys: pytest.CaptureFixture[str]) -> None:
    class _FailingPendingRepo(BtPendingRepo):
        def clear_pending(self, *, chat_id: int, expected_stage: str | None = None) -> bool:
            raise RuntimeError("db down")

    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                BT_PENDING_REPO_KEY: _FailingPendingRepo(SqliteDatabase(":memory:")),
                "bt_classification_pending_by_chat": {1001: "magnet:?xt=urn:btih:abc"},
            }
        )
    )

    assert _clear_bt_classification_pending(context=context, chat_id=1001) is None
    assert context.application.bot_data["bt_classification_pending_by_chat"][1001] == "magnet:?xt=urn:btih:abc"

    output = capsys.readouterr().out
    assert "[BT 待处理清理失败]" in output
    assert "stage=classification" in output
    assert "db down" in output


def test_clear_bt_classification_pending_logs_missing_clear_result(capsys: pytest.CaptureFixture[str]) -> None:
    class _MissingClearResultPendingRepo(BtPendingRepo):
        def clear_pending(self, *, chat_id: int, expected_stage: str | None = None):
            _ = (chat_id, expected_stage)
            return None

    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                BT_PENDING_REPO_KEY: _MissingClearResultPendingRepo(SqliteDatabase(":memory:")),
                "bt_classification_pending_by_chat": {1001: "magnet:?xt=urn:btih:abc"},
            }
        )
    )

    assert _clear_bt_classification_pending(context=context, chat_id=1001) is None
    assert context.application.bot_data["bt_classification_pending_by_chat"][1001] == "magnet:?xt=urn:btih:abc"

    output = capsys.readouterr().out
    assert "[BT 待处理清理结果缺失]" in output
    assert "[处理建议]" in output
    assert "stage=classification" in output
    assert "bt_pending_state clear result missing" in output


def test_pop_bt_classification_pending_logs_missing_query_after_restart(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()
    BtPendingRepo(database).upsert_pending(
        chat_id=1001,
        stage=BT_PENDING_STAGE_CLASSIFICATION,
        payload_json='{}',
    )
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={BT_PENDING_REPO_KEY: BtPendingRepo(SqliteDatabase(str(db_path)))}
        )
    )

    assert _pop_bt_classification_pending(context=context, chat_id=1001) is None
    output = capsys.readouterr().out
    assert "[BT 待处理载荷损坏]" in output
    assert "stage=classification" in output
    assert "payload.query missing" in output


def test_pop_bt_classification_pending_logs_missing_clear_result_after_restart(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()
    repo = BtPendingRepo(database)
    repo.upsert_pending(
        chat_id=1001,
        stage=BT_PENDING_STAGE_CLASSIFICATION,
        payload_json='{"query":"magnet:?xt=urn:btih:abc"}',
    )

    class _MissingClearResultPendingRepo(BtPendingRepo):
        def clear_pending(self, *, chat_id: int, expected_stage: str | None = None):
            _ = (chat_id, expected_stage)
            return None

    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={BT_PENDING_REPO_KEY: _MissingClearResultPendingRepo(SqliteDatabase(str(db_path)))}
        )
    )

    assert _pop_bt_classification_pending(context=context, chat_id=1001) is False
    assert context.application.bot_data["bt_classification_pending_by_chat"][1001] == "magnet:?xt=urn:btih:abc"

    output = capsys.readouterr().out
    assert "[BT 待处理清理结果缺失]" in output
    assert "[处理建议]" in output
    assert "stage=classification" in output
    assert "bt_pending_state clear result missing" in output


def test_pop_bt_classification_pending_logs_persistence_failure(capsys: pytest.CaptureFixture[str]) -> None:
    class _FailingPendingRepo(BtPendingRepo):
        def clear_pending(self, *, chat_id: int, expected_stage: str | None = None) -> bool:
            raise RuntimeError("db down")

    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                BT_PENDING_REPO_KEY: _FailingPendingRepo(SqliteDatabase(":memory:")),
                "bt_classification_pending_by_chat": {1001: "magnet:?xt=urn:btih:abc"},
            }
        )
    )

    assert _pop_bt_classification_pending(context=context, chat_id=1001) is False
    assert context.application.bot_data["bt_classification_pending_by_chat"][1001] == "magnet:?xt=urn:btih:abc"

    output = capsys.readouterr().out
    assert "[BT 待处理清理失败]" in output
    assert "stage=classification" in output
    assert "db down" in output


def test_pop_bt_classification_pending_logs_read_failure(capsys: pytest.CaptureFixture[str]) -> None:
    class _FailingPendingRepo(BtPendingRepo):
        def get_pending(self, *, chat_id: int):
            raise RuntimeError("db down")

    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={BT_PENDING_REPO_KEY: _FailingPendingRepo(SqliteDatabase(":memory:"))}
        )
    )

    assert _pop_bt_classification_pending(context=context, chat_id=1001) is None

    output = capsys.readouterr().out
    assert "[BT 待处理读取失败]" in output
    assert "stage=classification" in output
    assert "db down" in output


def test_set_bt_tmdb_association_pending_logs_persistence_failure(capsys: pytest.CaptureFixture[str]) -> None:
    class _FailingPendingRepo(BtPendingRepo):
        def upsert_pending(self, *, chat_id: int, stage: str, payload_json: str = "") -> None:
            raise RuntimeError("db down")

    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={BT_PENDING_REPO_KEY: _FailingPendingRepo(SqliteDatabase(":memory:"))}
        )
    )

    assert (
        _set_bt_tmdb_association_pending(
            context=context,
            chat_id=1001,
            media_kind="movie",
            source="magnet:?xt=urn:btih:abc",
        )
        is False
    )

    assert context.application.bot_data.get("bt_tmdb_association_pending_by_chat", {}) == {}
    output = capsys.readouterr().out
    assert "[BT 待处理持久化失败]" in output
    assert "stage=tmdb_association" in output
    assert "db down" in output


def test_bt_tmdb_association_pending_logs_payload_corruption_after_restart(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()
    BtPendingRepo(database).upsert_pending(
        chat_id=1001,
        stage=BT_PENDING_STAGE_TMDB_ASSOCIATION,
        payload_json="{",
    )
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={BT_PENDING_REPO_KEY: BtPendingRepo(SqliteDatabase(str(db_path)))}
        )
    )

    assert _get_bt_tmdb_association_pending(context=context, chat_id=1001) is False
    output = capsys.readouterr().out
    assert "[BT 待处理载荷损坏]" in output
    assert "stage=tmdb_association" in output
    assert "payload_json invalid json" in output


def test_bt_tmdb_association_pending_logs_missing_media_kind_after_restart(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()
    BtPendingRepo(database).upsert_pending(
        chat_id=1001,
        stage=BT_PENDING_STAGE_TMDB_ASSOCIATION,
        payload_json='{"source":"magnet:?xt=urn:btih:abc"}',
    )
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={BT_PENDING_REPO_KEY: BtPendingRepo(SqliteDatabase(str(db_path)))}
        )
    )

    assert _get_bt_tmdb_association_pending(context=context, chat_id=1001) is False
    output = capsys.readouterr().out
    assert "[BT 待处理载荷损坏]" in output
    assert "stage=tmdb_association" in output
    assert "payload.media_kind missing" in output


def test_bt_tmdb_association_pending_logs_missing_source_after_restart(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()
    BtPendingRepo(database).upsert_pending(
        chat_id=1001,
        stage=BT_PENDING_STAGE_TMDB_ASSOCIATION,
        payload_json='{"media_kind":"movie"}',
    )
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={BT_PENDING_REPO_KEY: BtPendingRepo(SqliteDatabase(str(db_path)))}
        )
    )

    assert _get_bt_tmdb_association_pending(context=context, chat_id=1001) is False
    output = capsys.readouterr().out
    assert "[BT 待处理载荷损坏]" in output
    assert "stage=tmdb_association" in output
    assert "payload.source missing" in output


def test_bt_tmdb_association_pending_logs_read_failure(capsys: pytest.CaptureFixture[str]) -> None:
    class _FailingPendingRepo(BtPendingRepo):
        def get_pending(self, *, chat_id: int):
            raise RuntimeError("db down")

    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={BT_PENDING_REPO_KEY: _FailingPendingRepo(SqliteDatabase(":memory:"))}
        )
    )

    assert _get_bt_tmdb_association_pending(context=context, chat_id=1001) is False

    output = capsys.readouterr().out
    assert "[BT 待处理读取失败]" in output
    assert "stage=tmdb_association" in output
    assert "db down" in output


def test_bt_tmdb_association_pending_logs_row_corruption_after_restart(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO bt_pending_state (chat_id, stage, payload_json, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (1001, "   ", '{"media_kind":"movie","source":"magnet:?xt=urn:btih:abcdef"}'),
        )
        connection.commit()

    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={BT_PENDING_REPO_KEY: BtPendingRepo(SqliteDatabase(str(db_path)))}
        )
    )

    assert _get_bt_tmdb_association_pending(context=context, chat_id=1001) is False

    output = capsys.readouterr().out
    assert "[BT 待处理记录损坏]" in output
    assert "stage=tmdb_association" in output
    assert "bt_pending_state stage empty after read" in output


def test_clear_bt_tmdb_association_pending_logs_persistence_failure(capsys: pytest.CaptureFixture[str]) -> None:
    class _FailingPendingRepo(BtPendingRepo):
        def clear_pending(self, *, chat_id: int, expected_stage: str | None = None) -> bool:
            raise RuntimeError("db down")

    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                BT_PENDING_REPO_KEY: _FailingPendingRepo(SqliteDatabase(":memory:")),
                "bt_tmdb_association_pending_by_chat": {1001: SimpleNamespace(media_kind="movie", source="magnet:?xt=urn:btih:abc")},
            }
        )
    )

    assert _clear_bt_tmdb_association_pending(context=context, chat_id=1001) is None
    pending = context.application.bot_data["bt_tmdb_association_pending_by_chat"][1001]
    assert pending.media_kind == "movie"
    assert pending.source == "magnet:?xt=urn:btih:abc"

    output = capsys.readouterr().out
    assert "[BT 待处理清理失败]" in output
    assert "stage=tmdb_association" in output
    assert "db down" in output


def test_clear_bt_tmdb_association_pending_logs_missing_clear_result(capsys: pytest.CaptureFixture[str]) -> None:
    class _MissingClearResultPendingRepo(BtPendingRepo):
        def clear_pending(self, *, chat_id: int, expected_stage: str | None = None):
            _ = (chat_id, expected_stage)
            return None

    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                BT_PENDING_REPO_KEY: _MissingClearResultPendingRepo(SqliteDatabase(":memory:")),
                "bt_tmdb_association_pending_by_chat": {
                    1001: SimpleNamespace(media_kind="movie", source="magnet:?xt=urn:btih:abc")
                },
            }
        )
    )

    assert _clear_bt_tmdb_association_pending(context=context, chat_id=1001) is None
    pending = context.application.bot_data["bt_tmdb_association_pending_by_chat"][1001]
    assert pending.media_kind == "movie"
    assert pending.source == "magnet:?xt=urn:btih:abc"

    output = capsys.readouterr().out
    assert "[BT 待处理清理结果缺失]" in output
    assert "[处理建议]" in output
    assert "stage=tmdb_association" in output
    assert "bt_pending_state clear result missing" in output


def test_set_raw_bt_destination_pending_logs_persistence_failure(capsys: pytest.CaptureFixture[str]) -> None:
    class _FailingPendingRepo(BtPendingRepo):
        def upsert_pending(self, *, chat_id: int, stage: str, payload_json: str = "") -> None:
            raise RuntimeError("db down")

    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={BT_PENDING_REPO_KEY: _FailingPendingRepo(SqliteDatabase(":memory:"))}
        )
    )
    options = (
        RawBtDestinationOption(
            key="downloads",
            label="下载目录",
            target_dir="/downloads/raw",
        ),
    )

    assert (
        _set_raw_bt_destination_pending(
            context=context,
            chat_id=1001,
            options=options,
            source="magnet:?xt=urn:btih:abc",
        )
        is False
    )

    assert context.application.bot_data.get("raw_bt_destination_pending_by_chat", {}) == {}
    output = capsys.readouterr().out
    assert "[BT 待处理持久化失败]" in output
    assert "stage=raw_bt_destination" in output
    assert "db down" in output


def test_enter_media_import_bt_flow_returns_service_not_ready_when_classification_persist_fails() -> None:
    class _FailingPendingRepo(BtPendingRepo):
        def upsert_pending(self, *, chat_id: int, stage: str, payload_json: str = "") -> None:
            raise RuntimeError("db down")

    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={BT_PENDING_REPO_KEY: _FailingPendingRepo(SqliteDatabase(":memory:"))}
        )
    )

    reply = _enter_media_import_bt_flow(
        context=context,
        chat_id=1001,
        source="magnet:?xt=urn:btih:abc",
    )

    assert reply == SERVICE_NOT_READY_TEXT


def test_enter_media_import_bt_flow_returns_service_not_ready_when_tmdb_pending_persist_fails() -> None:
    class _FailingPendingRepo(BtPendingRepo):
        def upsert_pending(self, *, chat_id: int, stage: str, payload_json: str = "") -> None:
            raise RuntimeError("db down")

    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={BT_PENDING_REPO_KEY: _FailingPendingRepo(SqliteDatabase(":memory:"))}
        )
    )

    reply = _enter_media_import_bt_flow(
        context=context,
        chat_id=1001,
        source="magnet:?xt=urn:btih:abc",
        media_kind="movie",
    )

    assert reply == SERVICE_NOT_READY_TEXT


def test_enter_pure_bt_flow_returns_service_not_ready_when_destination_persist_fails() -> None:
    class _FailingPendingRepo(BtPendingRepo):
        def upsert_pending(self, *, chat_id: int, stage: str, payload_json: str = "") -> None:
            raise RuntimeError("db down")

    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                BT_PENDING_REPO_KEY: _FailingPendingRepo(SqliteDatabase(":memory:")),
                RAW_BT_DESTINATION_OPTIONS_KEY: (
                    RawBtDestinationOption(key="downloads", label="下载目录", target_dir="/downloads/raw"),
                ),
            }
        )
    )

    reply = _enter_pure_bt_flow(
        context=context,
        chat_id=1001,
        source="magnet:?xt=urn:btih:abc",
    )

    assert reply == SERVICE_NOT_READY_TEXT


def test_raw_bt_destination_pending_logs_payload_corruption_after_restart(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()
    BtPendingRepo(database).upsert_pending(
        chat_id=1001,
        stage=BT_PENDING_STAGE_RAW_BT_DESTINATION,
        payload_json="{",
    )
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={BT_PENDING_REPO_KEY: BtPendingRepo(SqliteDatabase(str(db_path)))}
        )
    )

    assert _get_raw_bt_destination_pending(context=context, chat_id=1001) is False
    output = capsys.readouterr().out
    assert "[BT 待处理载荷损坏]" in output
    assert "stage=raw_bt_destination" in output
    assert "payload_json invalid json" in output


def test_raw_bt_destination_pending_logs_options_structure_corruption_after_restart(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()
    BtPendingRepo(database).upsert_pending(
        chat_id=1001,
        stage=BT_PENDING_STAGE_RAW_BT_DESTINATION,
        payload_json='{"options":"bad","source":"magnet:?xt=urn:btih:abc"}',
    )
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={BT_PENDING_REPO_KEY: BtPendingRepo(SqliteDatabase(str(db_path)))}
        )
    )

    assert _get_raw_bt_destination_pending(context=context, chat_id=1001) is False
    output = capsys.readouterr().out
    assert "[BT 待处理载荷损坏]" in output
    assert "stage=raw_bt_destination" in output
    assert "payload.options missing or not list" in output


def test_raw_bt_destination_pending_logs_missing_source_after_restart(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()
    BtPendingRepo(database).upsert_pending(
        chat_id=1001,
        stage=BT_PENDING_STAGE_RAW_BT_DESTINATION,
        payload_json='{"options":[{"key":"downloads","label":"下载目录","target_dir":"/downloads/raw"}]}',
    )
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={BT_PENDING_REPO_KEY: BtPendingRepo(SqliteDatabase(str(db_path)))}
        )
    )

    assert _get_raw_bt_destination_pending(context=context, chat_id=1001) is False
    output = capsys.readouterr().out
    assert "[BT 待处理载荷损坏]" in output
    assert "stage=raw_bt_destination" in output
    assert "payload.source missing" in output


def test_raw_bt_destination_pending_logs_no_valid_options_after_restart(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()
    BtPendingRepo(database).upsert_pending(
        chat_id=1001,
        stage=BT_PENDING_STAGE_RAW_BT_DESTINATION,
        payload_json='{"options":[{"key":"","label":"下载目录","target_dir":"/downloads/raw"}],"source":"magnet:?xt=urn:btih:abc"}',
    )
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={BT_PENDING_REPO_KEY: BtPendingRepo(SqliteDatabase(str(db_path)))}
        )
    )

    assert _get_raw_bt_destination_pending(context=context, chat_id=1001) is False
    output = capsys.readouterr().out
    assert "[BT 待处理载荷损坏]" in output
    assert "stage=raw_bt_destination" in output
    assert "payload.options has no valid entries" in output


def test_raw_bt_destination_pending_logs_read_failure(capsys: pytest.CaptureFixture[str]) -> None:
    class _FailingPendingRepo(BtPendingRepo):
        def get_pending(self, *, chat_id: int):
            raise RuntimeError("db down")

    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={BT_PENDING_REPO_KEY: _FailingPendingRepo(SqliteDatabase(":memory:"))}
        )
    )

    assert _get_raw_bt_destination_pending(context=context, chat_id=1001) is False

    output = capsys.readouterr().out
    assert "[BT 待处理读取失败]" in output
    assert "stage=raw_bt_destination" in output
    assert "db down" in output


def test_clear_raw_bt_destination_pending_logs_persistence_failure(capsys: pytest.CaptureFixture[str]) -> None:
    class _FailingPendingRepo(BtPendingRepo):
        def clear_pending(self, *, chat_id: int, expected_stage: str | None = None) -> bool:
            raise RuntimeError("db down")

    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                BT_PENDING_REPO_KEY: _FailingPendingRepo(SqliteDatabase(":memory:")),
                "raw_bt_destination_pending_by_chat": {
                    1001: SimpleNamespace(options=(), source="magnet:?xt=urn:btih:abc")
                },
            }
        )
    )

    assert _clear_raw_bt_destination_pending(context=context, chat_id=1001) is None
    pending = context.application.bot_data["raw_bt_destination_pending_by_chat"][1001]
    assert pending.options == ()
    assert pending.source == "magnet:?xt=urn:btih:abc"

    output = capsys.readouterr().out
    assert "[BT 待处理清理失败]" in output
    assert "stage=raw_bt_destination" in output
    assert "db down" in output


def test_clear_raw_bt_destination_pending_logs_missing_clear_result(capsys: pytest.CaptureFixture[str]) -> None:
    class _MissingClearResultPendingRepo(BtPendingRepo):
        def clear_pending(self, *, chat_id: int, expected_stage: str | None = None):
            _ = (chat_id, expected_stage)
            return None

    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                BT_PENDING_REPO_KEY: _MissingClearResultPendingRepo(SqliteDatabase(":memory:")),
                "raw_bt_destination_pending_by_chat": {
                    1001: SimpleNamespace(options=(), source="magnet:?xt=urn:btih:abc")
                },
            }
        )
    )

    assert _clear_raw_bt_destination_pending(context=context, chat_id=1001) is None
    pending = context.application.bot_data["raw_bt_destination_pending_by_chat"][1001]
    assert pending.options == ()
    assert pending.source == "magnet:?xt=urn:btih:abc"

    output = capsys.readouterr().out
    assert "[BT 待处理清理结果缺失]" in output
    assert "[处理建议]" in output
    assert "stage=raw_bt_destination" in output
    assert "bt_pending_state clear result missing" in output


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
    assert "【下载审批】" in sent_text
    assert "标题: title-dune" in sent_text
    assert "选择序号: 1" in sent_text
    assert "确认命令: confirm 1" in sent_text
    assert "直接回复 confirm 1 执行下载" in sent_text
    assert "下载待确认：" not in sent_text


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
    assert "【下载审批】" in sent_text
    assert "标题: title-dune" in sent_text
    assert "选择序号: 1" in sent_text
    assert "确认命令: confirm 1" in sent_text
    assert "直接回复 confirm 1 执行下载" in sent_text


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
    reply_text.assert_awaited_once_with(BT_PROCESSING_PATH_PROMPT_TEXT)


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
                RAW_BT_DESTINATION_OPTIONS_KEY: (
                    RawBtDestinationOption(
                        key="downloads",
                        label="下载目录",
                        target_dir="/data/raw/downloads",
                    ),
                ),
            }
        )
    )

    asyncio.run(handle_callback_query(update, context))
    asyncio.run(handle_callback_query(follow_up_update, context))

    first_answer.assert_awaited_once()
    second_answer.assert_awaited_once()
    first_reply_text.assert_awaited_once_with(BT_PROCESSING_PATH_PROMPT_TEXT)
    second_sent_text = second_reply_text.await_args.args[0]
    assert "请选择预设目标目录：" in second_sent_text
    assert "1. 下载目录 [downloads] -> /data/raw/downloads" in second_sent_text
    search_service.search_and_format.assert_not_awaited()


def test_handle_callback_query_raw_bt_destination_selection_succeeds() -> None:
    update, first_reply_text, first_answer = _build_callback_update("magnet:?xt=urn:btih:abcdef1234567890")
    classify_update, second_reply_text, second_answer = _build_callback_update("raw_bt", callback_query_id="cb-2")
    select_update, third_reply_text, third_answer = _build_callback_update("downloads", callback_query_id="cb-3")
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
                RAW_BT_DESTINATION_OPTIONS_KEY: (
                    RawBtDestinationOption(
                        key="downloads",
                        label="下载目录",
                        target_dir="/data/raw/downloads",
                    ),
                    RawBtDestinationOption(
                        key="archive",
                        label="归档目录",
                        target_dir="/data/raw/archive",
                    ),
                ),
            }
        )
    )

    asyncio.run(handle_callback_query(update, context))
    asyncio.run(handle_callback_query(classify_update, context))
    asyncio.run(handle_callback_query(select_update, context))

    first_answer.assert_awaited_once()
    second_answer.assert_awaited_once()
    third_answer.assert_awaited_once()
    first_reply_text.assert_awaited_once_with(BT_PROCESSING_PATH_PROMPT_TEXT)
    assert "请选择预设目标目录：" in second_reply_text.await_args.args[0]
    selected_text = third_reply_text.await_args.args[0]
    assert "已记录 raw_bt 目标目录。" in selected_text
    assert "目录键: downloads" in selected_text


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
    assert "【下载审批】" in sent_text
    assert "标题: title-dune" in sent_text
    assert "选择序号: 1" in sent_text
    assert "确认命令: confirm 1" in sent_text


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


def test_handle_message_import_formats_import_approval_for_telegram() -> None:
    update, reply_text = _build_update("import hash-87")
    search_service = SearchMediaService(_fake_search)
    add_service = AddToDownloaderService(search_service, AsyncMock())
    status_service = GetDownloadStatusService(AsyncMock())
    import_service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies")
    import_service.import_by_task_ref = AsyncMock(
        return_value=(
            "导入待确认：Dune (2021).mkv\n"
            "任务 ID: 87\n"
            "任务 Hash: hash-87\n"
            "请发送 confirm hash-87 执行导入。"
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
    assert "【导入审批】" in sent_text
    assert "资源: Dune (2021).mkv" in sent_text
    assert "任务 ID: 87" in sent_text
    assert "任务 Hash: hash-87" in sent_text
    assert "确认命令: confirm hash-87" in sent_text
    assert "直接回复 confirm hash-87 执行导入" in sent_text
    assert "导入待确认：" not in sent_text
    import_service.import_by_task_ref.assert_awaited_once_with("hash-87", chat_id=1001, user_id=2001)


def test_handle_message_cleanup_routes_to_cleanup_service(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    update, reply_text = _build_update("cleanup hash-87")
    search_service = SearchMediaService(_fake_search)
    add_service = AddToDownloaderService(search_service, AsyncMock())
    status_service = GetDownloadStatusService(AsyncMock())
    import_service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies")
    cleanup_service = CleanupDownloadedSourceService(JobEventRepo(_make_database(tmp_path)))
    cleanup_service.cleanup_by_task_ref = Mock(return_value="已清理下载源资产。")
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                SEARCH_SERVICE_KEY: search_service,
                ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
                GET_DOWNLOAD_STATUS_SERVICE_KEY: status_service,
                IMPORT_TO_LIBRARY_SERVICE_KEY: import_service,
                CLEANUP_DOWNLOADED_SOURCE_SERVICE_KEY: cleanup_service,
            }
        )
    )

    asyncio.run(handle_message(update, context))

    reply_text.assert_awaited_once_with("已清理下载源资产。")
    cleanup_service.cleanup_by_task_ref.assert_called_once_with("hash-87", chat_id=1001)
    captured = capsys.readouterr()
    assert "[cleanup 私聊 smoke]" in captured.out
    assert "channel=telegram" in captured.out
    assert "action=cleanup" in captured.out
    assert 'query="cleanup hash-87"' in captured.out
    assert 'reply_head="已清理下载源资产。"' in captured.out


def test_handle_message_cleanup_inspect_routes_to_cleanup_service(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    update, reply_text = _build_update("cleanup inspect hash-87")
    search_service = SearchMediaService(_fake_search)
    add_service = AddToDownloaderService(search_service, AsyncMock())
    status_service = GetDownloadStatusService(AsyncMock())
    import_service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies")
    cleanup_service = CleanupDownloadedSourceService(JobEventRepo(_make_database(tmp_path)))
    cleanup_service.inspect_by_task_ref = Mock(return_value="清理预检结果。")
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                SEARCH_SERVICE_KEY: search_service,
                ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
                GET_DOWNLOAD_STATUS_SERVICE_KEY: status_service,
                IMPORT_TO_LIBRARY_SERVICE_KEY: import_service,
                CLEANUP_DOWNLOADED_SOURCE_SERVICE_KEY: cleanup_service,
            }
        )
    )

    asyncio.run(handle_message(update, context))

    reply_text.assert_awaited_once_with("清理预检结果。")
    cleanup_service.inspect_by_task_ref.assert_called_once_with("hash-87", chat_id=1001)
    captured = capsys.readouterr()
    assert "[cleanup 私聊 smoke]" in captured.out
    assert "channel=telegram" in captured.out
    assert "action=cleanup_inspect" in captured.out
    assert 'query="cleanup inspect hash-87"' in captured.out
    assert 'reply_head="清理预检结果。"' in captured.out


def test_handle_message_cleanup_inspect_routes_chat_scoped_shortcut_into_shared_runtime(tmp_path: Path) -> None:
    update, reply_text = _build_update(f"cleanup inspect {_CHAT_SCOPED_TASK_REF}")
    search_service = SearchMediaService(_fake_search)
    add_service = AddToDownloaderService(search_service, AsyncMock())
    status_service = GetDownloadStatusService(AsyncMock())
    import_service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies")
    database = _make_database(tmp_path)
    event_repo = JobEventRepo(database)
    job_repo = JobRepo(database)
    job_repo.upsert_import_job_pending(
        chat_id=1001,
        user_id=2001,
        task_ref=_CHAT_SCOPED_TASK_REF,
        task_id="87",
        task_hash="hash-87",
    )
    source_file = tmp_path / "downloads" / "Dune.2021.mkv"
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b"demo")
    target_file = tmp_path / "library" / "Dune (2021).mkv"
    target_file.parent.mkdir(parents=True)
    target_file.hardlink_to(source_file)
    event_repo.append_event(
        task_ref="hash-87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message=str(target_file),
        source_path=str(source_file),
        target_path=str(target_file),
    )
    cleanup_service = CleanupDownloadedSourceService(event_repo, job_repo=job_repo)
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                SEARCH_SERVICE_KEY: search_service,
                ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
                GET_DOWNLOAD_STATUS_SERVICE_KEY: status_service,
                IMPORT_TO_LIBRARY_SERVICE_KEY: import_service,
                CLEANUP_DOWNLOADED_SOURCE_SERVICE_KEY: cleanup_service,
            }
        )
    )

    asyncio.run(handle_message(update, context))

    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "查询引用: cleanup-shortcut" in sent_text
    assert "任务 ID: 87" in sent_text
    assert "任务 Hash: hash-87" in sent_text
    assert "cleanup hash-87 / 清理 hash-87：实际清理下载源资产" in sent_text
    assert source_file.exists()
    assert target_file.exists()


@pytest.mark.parametrize(
    ("query", "mock_reply", "service_attr", "expected_ref"),
    [
        ("cleanup", "cleanup 用法", "cleanup_by_task_ref", ""),
        ("cleanup inspect", "cleanup inspect 用法", "inspect_by_task_ref", ""),
        ("清理", "cleanup 用法", "cleanup_by_task_ref", ""),
        ("清理检查", "cleanup inspect 用法", "inspect_by_task_ref", ""),
    ],
)
def test_handle_message_cleanup_usage_variants_route_to_service(
    tmp_path: Path,
    query: str,
    mock_reply: str,
    service_attr: str,
    expected_ref: str,
) -> None:
    update, reply_text = _build_update(query)
    search_service = SearchMediaService(_fake_search)
    add_service = AddToDownloaderService(search_service, AsyncMock())
    status_service = GetDownloadStatusService(AsyncMock())
    import_service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies")
    cleanup_service = CleanupDownloadedSourceService(JobEventRepo(_make_database(tmp_path)))
    mocked_service_method = Mock(return_value=mock_reply)
    setattr(cleanup_service, service_attr, mocked_service_method)
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                SEARCH_SERVICE_KEY: search_service,
                ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
                GET_DOWNLOAD_STATUS_SERVICE_KEY: status_service,
                IMPORT_TO_LIBRARY_SERVICE_KEY: import_service,
                CLEANUP_DOWNLOADED_SOURCE_SERVICE_KEY: cleanup_service,
            }
        )
    )

    asyncio.run(handle_message(update, context))

    reply_text.assert_awaited_once_with(mock_reply)
    mocked_service_method.assert_called_once_with(expected_ref, chat_id=1001)


@pytest.mark.parametrize(
    ("query", "mock_reply", "service_attr"),
    [
        ("清理 hash-87", "已清理下载源资产。", "cleanup_by_task_ref"),
        ("清理检查 hash-87", "清理预检结果。", "inspect_by_task_ref"),
    ],
)
def test_handle_message_cleanup_chinese_routes_to_service(
    tmp_path: Path,
    query: str,
    mock_reply: str,
    service_attr: str,
) -> None:
    update, reply_text = _build_update(query)
    search_service = SearchMediaService(_fake_search)
    add_service = AddToDownloaderService(search_service, AsyncMock())
    status_service = GetDownloadStatusService(AsyncMock())
    import_service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies")
    cleanup_service = CleanupDownloadedSourceService(JobEventRepo(_make_database(tmp_path)))
    mocked_service_method = Mock(return_value=mock_reply)
    setattr(cleanup_service, service_attr, mocked_service_method)
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                SEARCH_SERVICE_KEY: search_service,
                ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
                GET_DOWNLOAD_STATUS_SERVICE_KEY: status_service,
                IMPORT_TO_LIBRARY_SERVICE_KEY: import_service,
                CLEANUP_DOWNLOADED_SOURCE_SERVICE_KEY: cleanup_service,
            }
        )
    )

    asyncio.run(handle_message(update, context))

    reply_text.assert_awaited_once_with(mock_reply)
    mocked_service_method.assert_called_once_with("hash-87", chat_id=1001)


@pytest.mark.parametrize(
    ("query", "mock_reply", "service_attr", "expected_ref"),
    [
        ("ClEaNuP HaSh-87", "已清理下载源资产。", "cleanup_by_task_ref", "HaSh-87"),
        ("cLeAnUp iNsPeCt hAsH-87", "清理预检结果。", "inspect_by_task_ref", "hAsH-87"),
    ],
)
def test_handle_message_cleanup_mixed_case_english_routes_to_service(
    tmp_path: Path,
    query: str,
    mock_reply: str,
    service_attr: str,
    expected_ref: str,
) -> None:
    update, reply_text = _build_update(query)
    search_service = SearchMediaService(_fake_search)
    add_service = AddToDownloaderService(search_service, AsyncMock())
    status_service = GetDownloadStatusService(AsyncMock())
    import_service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies")
    cleanup_service = CleanupDownloadedSourceService(JobEventRepo(_make_database(tmp_path)))
    mocked_service_method = Mock(return_value=mock_reply)
    setattr(cleanup_service, service_attr, mocked_service_method)
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                SEARCH_SERVICE_KEY: search_service,
                ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
                GET_DOWNLOAD_STATUS_SERVICE_KEY: status_service,
                IMPORT_TO_LIBRARY_SERVICE_KEY: import_service,
                CLEANUP_DOWNLOADED_SOURCE_SERVICE_KEY: cleanup_service,
            }
        )
    )

    asyncio.run(handle_message(update, context))

    reply_text.assert_awaited_once_with(mock_reply)
    mocked_service_method.assert_called_once_with(expected_ref, chat_id=1001)


def test_handle_message_cleanup_replies_service_not_ready(capsys: pytest.CaptureFixture[str]) -> None:
    update, reply_text = _build_update("cleanup hash-87")
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
    captured = capsys.readouterr()

    reply_text.assert_awaited_once_with(SERVICE_NOT_READY_TEXT)
    assert "[cleanup 服务未就绪]" in captured.out
    assert "动作=cleanup" in captured.out
    assert "cleanup hash-87" in captured.out
    assert "[处理建议]" in captured.out


@pytest.mark.parametrize(
    ("query", "expected_action"),
    [
        ("cleanup", "cleanup"),
        ("cleanup inspect hash-87", "cleanup_inspect"),
        ("cleanup inspect", "cleanup_inspect"),
        ("清理", "cleanup"),
        ("清理 hash-87", "cleanup"),
        ("清理检查", "cleanup_inspect"),
        ("清理检查 hash-87", "cleanup_inspect"),
    ],
)
def test_handle_message_cleanup_variants_reply_service_not_ready(
    query: str,
    expected_action: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    update, reply_text = _build_update(query)
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
    captured = capsys.readouterr()

    reply_text.assert_awaited_once_with(SERVICE_NOT_READY_TEXT)
    assert "[cleanup 服务未就绪]" in captured.out
    assert f"动作={expected_action}" in captured.out
    assert query in captured.out
    assert "[处理建议]" in captured.out


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


def test_handle_message_bt_subscription_routes_to_service(tmp_path: Path) -> None:
    update, reply_text = _build_update("btsub add anime 葬送的芙莉莲 2023")
    search_service = SearchMediaService(_fake_search)
    add_service = AddToDownloaderService(search_service, AsyncMock())
    status_service = GetDownloadStatusService(AsyncMock())
    import_service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies")
    bt_subscription_service = ManageBtSubscriptionService(
        bt_subscription_repo=BtSubscriptionRepo(_make_database(tmp_path)),
        search_func=_fake_search,
        add_to_downloader_service=add_service,
    )
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                SEARCH_SERVICE_KEY: search_service,
                ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
                GET_DOWNLOAD_STATUS_SERVICE_KEY: status_service,
                IMPORT_TO_LIBRARY_SERVICE_KEY: import_service,
                MANAGE_BT_SUBSCRIPTION_SERVICE_KEY: bt_subscription_service,
            }
        )
    )

    asyncio.run(handle_message(update, context))
    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "已加入 BT 订阅" in sent_text
    assert "葬送的芙莉莲" in sent_text


def test_handle_message_bt_read_only_helper_routes_to_raw_search() -> None:
    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        assert query == "Frieren S01E01"
        return [
            {
                "title": "title-Frieren S01E01",
                "source": "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12",
                "infoHash": "abcdef1234567890abcdef1234567890abcdef12",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    update, reply_text = _build_update("bt搜 Frieren S01E01")
    search_service = SearchMediaService(_fake_search, raw_search_func=fake_raw_search)
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
    assert "BT 只读探索结果：Frieren S01E01" in sent_text
    assert "title-Frieren S01E01" in sent_text
    assert "只读说明：" in sent_text


def test_handle_message_bt_read_only_helper_search_failure_returns_safe_text() -> None:
    async def failing_raw_search(_: str) -> list[dict[str, object]]:
        raise RuntimeError("network down")

    update, reply_text = _build_update("bt search Frieren S01E01")
    search_service = SearchMediaService(_fake_search, raw_search_func=failing_raw_search)
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

    reply_text.assert_awaited_once_with(BT_READ_ONLY_HELPER_FAILED_TEXT)


def test_handle_message_bt_batch_preview_routes_to_raw_search() -> None:
    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        assert query == "Frieren S01E01"
        return [
            {
                "title": "title-Frieren S01E01",
                "source": "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12",
                "infoHash": "abcdef1234567890abcdef1234567890abcdef12",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
            {
                "title": "title-Frieren S01E02",
                "source": "magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "infoHash": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
        ]

    update, reply_text = _build_update("bt批量 Frieren S01E01 1-2")
    search_service = SearchMediaService(_fake_search, raw_search_func=fake_raw_search)
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
    assert "BT 批量预览结果：Frieren S01E01" in sent_text
    assert "title-Frieren S01E01" in sent_text
    assert "title-Frieren S01E02" in sent_text
    assert "当前预览范围：1,2" in sent_text


def test_handle_message_bt_batch_preview_page_url_routes_to_page_fetch() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist page preview")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?f=0&c=1_2&u=subsplease"
        return [
            {
                "title": "title-Frieren S01E01",
                "source": "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12",
                "infoHash": "abcdef1234567890abcdef1234567890abcdef12",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
            {
                "title": "title-Frieren S01E02",
                "source": "magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "infoHash": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
        ]

    update, reply_text = _build_update("bt批量 https://nyaa.si/?f=0&c=1_2&u=subsplease 1-2")
    search_service = SearchMediaService(
        _fake_search,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
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

    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "BT 批量预览结果：https://nyaa.si/?f=0&c=1_2&u=subsplease" in sent_text
    assert "title-Frieren S01E01" in sent_text
    assert "title-Frieren S01E02" in sent_text
    assert "当前预览范围：1,2" in sent_text


def test_handle_message_bt_batch_preview_uncategorized_user_page_routes_to_page_fetch() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for uncategorized user page preview")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?u=subsplease"
        return [
            {
                "title": "title-Frieren S01E01",
                "source": "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12",
                "infoHash": "abcdef1234567890abcdef1234567890abcdef12",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
            {
                "title": "title-Frieren S01E02",
                "source": "magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "infoHash": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
        ]

    update, reply_text = _build_update("bt批量 https://nyaa.si/?u=subsplease 1-2")
    search_service = SearchMediaService(
        _fake_search,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
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

    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "BT 批量预览结果：https://nyaa.si/?u=subsplease" in sent_text
    assert "title-Frieren S01E01" in sent_text
    assert "title-Frieren S01E02" in sent_text
    assert "当前预览范围：1,2" in sent_text


def test_handle_message_bt_batch_confirm_reuses_page_preview_candidates() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist page preview")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?f=0&c=1_2&u=subsplease"
        return [
            {
                "title": "title-Frieren S01E01",
                "source": "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12",
                "infoHash": "abcdef1234567890abcdef1234567890abcdef12",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
            {
                "title": "title-Frieren S01E02",
                "source": "magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "infoHash": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
        ]

    search_service = SearchMediaService(
        _fake_search,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
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
                DOWNLOADER_ROLE_BINDING_KEY: DownloaderRoleBinding(pt_downloader="", bt_downloader=""),
                DOWNLOADER_INSTANCES_KEY: (
                    DownloaderInstanceConfig(name="", downloader_type="transmission", base_url="", download_dir="/downloads"),
                ),
            }
        )
    )

    preview_update, preview_reply = _build_update("bt批量 https://nyaa.si/?f=0&c=1_2&u=subsplease 1-2")
    asyncio.run(handle_message(preview_update, context))
    assert preview_reply.await_count == 1

    confirm_update, confirm_reply = _build_update("bt批量确认 1-2")
    asyncio.run(handle_message(confirm_update, context))

    confirm_reply.assert_awaited_once()
    sent_text = confirm_reply.await_args.args[0]
    assert sent_text.count("待确认：下载 ⏳") == 2
    assert "片名：title-Frieren S01E01" in sent_text
    assert "片名：title-Frieren S01E02" in sent_text
    assert "确认下载：发送 confirm 1" in sent_text
    assert "确认下载：发送 confirm 2" in sent_text


def test_handle_message_bt_batch_confirm_reuses_uncategorized_user_page_preview_candidates() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for uncategorized user page preview")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?u=subsplease"
        return [
            {
                "title": "title-Frieren S01E01",
                "source": "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12",
                "infoHash": "abcdef1234567890abcdef1234567890abcdef12",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
            {
                "title": "title-Frieren S01E02",
                "source": "magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "infoHash": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
        ]

    search_service = SearchMediaService(
        _fake_search,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
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
                DOWNLOADER_ROLE_BINDING_KEY: DownloaderRoleBinding(pt_downloader="", bt_downloader=""),
                DOWNLOADER_INSTANCES_KEY: (
                    DownloaderInstanceConfig(name="", downloader_type="transmission", base_url="", download_dir="/downloads"),
                ),
            }
        )
    )

    preview_update, preview_reply = _build_update("bt批量 https://nyaa.si/?u=subsplease 1-2")
    asyncio.run(handle_message(preview_update, context))
    assert preview_reply.await_count == 1

    confirm_update, confirm_reply = _build_update("bt批量确认 1-2")
    asyncio.run(handle_message(confirm_update, context))

    confirm_reply.assert_awaited_once()
    sent_text = confirm_reply.await_args.args[0]
    assert sent_text.count("待确认：下载 ⏳") == 2
    assert "片名：title-Frieren S01E01" in sent_text
    assert "片名：title-Frieren S01E02" in sent_text
    assert "确认下载：发送 confirm 1" in sent_text
    assert "确认下载：发送 confirm 2" in sent_text


def test_handle_message_bt_batch_preview_sort_page_number_syntax_routes_to_page_fetch() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist sort page number syntax")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?s=seeders&o=desc&p=2"
        return [
            {
                "title": "title-Frieren S01E12",
                "source": "magnet:?xt=urn:btih:1212121212121212121212121212121212121212",
                "infoHash": "1212121212121212121212121212121212121212",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    update, reply_text = _build_update("bt批量 https://nyaa.si/?s=seeders&o=desc p=2 1-1")
    search_service = SearchMediaService(
        _fake_search,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
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

    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "BT 批量预览结果：https://nyaa.si/?s=seeders&o=desc p=2" in sent_text
    assert "title-Frieren S01E12" in sent_text
    assert "当前预览范围：1" in sent_text


def test_handle_message_bt_batch_preview_category_sort_page_routes_to_page_fetch() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist category sort page")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?c=1_2&s=seeders&o=desc"
        return [
            {
                "title": "title-Frieren S01E06",
                "source": "magnet:?xt=urn:btih:1616161616161616161616161616161616161616",
                "infoHash": "1616161616161616161616161616161616161616",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    update, reply_text = _build_update("bt批量 https://nyaa.si/?c=1_2&s=seeders&o=desc 1-1")
    search_service = SearchMediaService(
        _fake_search,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
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

    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "BT 批量预览结果：https://nyaa.si/?c=1_2&s=seeders&o=desc" in sent_text
    assert "title-Frieren S01E06" in sent_text
    assert "当前预览范围：1" in sent_text


def test_handle_message_bt_batch_preview_category_sort_page_number_syntax_routes_to_page_fetch() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist category sort page number syntax")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?c=1_2&s=seeders&o=desc&p=2"
        return [
            {
                "title": "title-Frieren S01E14",
                "source": "magnet:?xt=urn:btih:1414141414141414141414141414141414141414",
                "infoHash": "1414141414141414141414141414141414141414",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    update, reply_text = _build_update("bt批量 https://nyaa.si/?c=1_2&s=seeders&o=desc p=2 1-1")
    search_service = SearchMediaService(
        _fake_search,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
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

    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "BT 批量预览结果：https://nyaa.si/?c=1_2&s=seeders&o=desc p=2" in sent_text
    assert "title-Frieren S01E14" in sent_text
    assert "当前预览范围：1" in sent_text


def test_handle_message_bt_batch_preview_user_sort_page_routes_to_page_fetch() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist user sort page")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?f=0&c=1_2&u=subsplease&s=seeders&o=desc"
        return [
            {
                "title": "title-Frieren S01E16",
                "source": "magnet:?xt=urn:btih:1616161616161616161616161616161616161616",
                "infoHash": "1616161616161616161616161616161616161616",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    update, reply_text = _build_update("bt批量 https://nyaa.si/?f=0&c=1_2&u=subsplease&s=seeders&o=desc 1-1")
    search_service = SearchMediaService(
        _fake_search,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
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

    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "BT 批量预览结果：https://nyaa.si/?f=0&c=1_2&u=subsplease&s=seeders&o=desc" in sent_text
    assert "title-Frieren S01E16" in sent_text
    assert "当前预览范围：1" in sent_text


def test_handle_message_bt_batch_preview_uncategorized_user_sort_page_routes_to_page_fetch() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for uncategorized user sort page")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?u=subsplease&s=seeders&o=desc"
        return [
            {
                "title": "title-Frieren S01E16",
                "source": "magnet:?xt=urn:btih:1616161616161616161616161616161616161616",
                "infoHash": "1616161616161616161616161616161616161616",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    update, reply_text = _build_update("bt批量 https://nyaa.si/?u=subsplease&s=seeders&o=desc 1-1")
    search_service = SearchMediaService(
        _fake_search,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
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

    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "BT 批量预览结果：https://nyaa.si/?u=subsplease&s=seeders&o=desc" in sent_text
    assert "title-Frieren S01E16" in sent_text
    assert "当前预览范围：1" in sent_text


def test_handle_message_bt_batch_preview_user_sort_page_number_syntax_routes_to_page_fetch() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist user sort page number syntax")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?f=0&c=1_2&u=subsplease&s=seeders&o=desc&p=2"
        return [
            {
                "title": "title-Frieren S01E18",
                "source": "magnet:?xt=urn:btih:1818181818181818181818181818181818181818",
                "infoHash": "1818181818181818181818181818181818181818",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    update, reply_text = _build_update("bt批量 https://nyaa.si/?f=0&c=1_2&u=subsplease&s=seeders&o=desc p=2 1-1")
    search_service = SearchMediaService(
        _fake_search,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
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

    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "BT 批量预览结果：https://nyaa.si/?f=0&c=1_2&u=subsplease&s=seeders&o=desc p=2" in sent_text
    assert "title-Frieren S01E18" in sent_text
    assert "当前预览范围：1" in sent_text


def test_handle_message_bt_batch_preview_uncategorized_user_page_number_routes_to_page_fetch() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for uncategorized user page number syntax")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?u=subsplease&p=2"
        return [
            {
                "title": "title-Frieren S01E11",
                "source": "magnet:?xt=urn:btih:1111111111111111111111111111111111111111",
                "infoHash": "1111111111111111111111111111111111111111",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    update, reply_text = _build_update("bt批量 https://nyaa.si/?u=subsplease p=2 1-1")
    search_service = SearchMediaService(
        _fake_search,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
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

    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "BT 批量预览结果：https://nyaa.si/?u=subsplease p=2" in sent_text
    assert "title-Frieren S01E11" in sent_text
    assert "当前预览范围：1" in sent_text


def test_handle_message_bt_batch_preview_uncategorized_user_sort_page_number_routes_to_page_fetch() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for uncategorized user sort page number syntax")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?u=subsplease&s=seeders&o=desc&p=2"
        return [
            {
                "title": "title-Frieren S01E18",
                "source": "magnet:?xt=urn:btih:1818181818181818181818181818181818181818",
                "infoHash": "1818181818181818181818181818181818181818",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    update, reply_text = _build_update("bt批量 https://nyaa.si/?u=subsplease&s=seeders&o=desc p=2 1-1")
    search_service = SearchMediaService(
        _fake_search,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
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

    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "BT 批量预览结果：https://nyaa.si/?u=subsplease&s=seeders&o=desc p=2" in sent_text
    assert "title-Frieren S01E18" in sent_text
    assert "当前预览范围：1" in sent_text


def test_handle_message_bt_batch_preview_uncategorized_user_sort_page_number_url_routes_to_page_fetch() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for uncategorized user sort page number url")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?u=subsplease&s=seeders&o=desc&p=2"
        return [
            {
                "title": "title-Frieren S01E18",
                "source": "magnet:?xt=urn:btih:1818181818181818181818181818181818181818",
                "infoHash": "1818181818181818181818181818181818181818",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    update, reply_text = _build_update("bt批量 https://nyaa.si/?u=subsplease&s=seeders&o=desc&p=2 1-1")
    search_service = SearchMediaService(
        _fake_search,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
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

    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "BT 批量预览结果：https://nyaa.si/?u=subsplease&s=seeders&o=desc&p=2" in sent_text
    assert "title-Frieren S01E18" in sent_text
    assert "当前预览范围：1" in sent_text


def test_handle_message_bt_batch_preview_search_sort_page_routes_to_page_fetch() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist search sort page")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?f=0&c=1_2&q=frieren&s=seeders&o=desc"
        return [
            {
                "title": "title-Frieren S01E20",
                "source": "magnet:?xt=urn:btih:2020202020202020202020202020202020202020",
                "infoHash": "2020202020202020202020202020202020202020",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    update, reply_text = _build_update("bt批量 https://nyaa.si/?f=0&c=1_2&q=frieren&s=seeders&o=desc 1-1")
    search_service = SearchMediaService(
        _fake_search,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
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

    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "BT 批量预览结果：https://nyaa.si/?f=0&c=1_2&q=frieren&s=seeders&o=desc" in sent_text
    assert "title-Frieren S01E20" in sent_text
    assert "当前预览范围：1" in sent_text


def test_handle_message_bt_batch_preview_search_page_number_routes_to_page_fetch() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist search page number")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?f=0&c=1_2&q=frieren&p=2"
        return [
            {
                "title": "title-Frieren S01E24",
                "source": "magnet:?xt=urn:btih:2424242424242424242424242424242424242424",
                "infoHash": "2424242424242424242424242424242424242424",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    update, reply_text = _build_update("bt批量 https://nyaa.si/?f=0&c=1_2&q=frieren&p=2 1-1")
    search_service = SearchMediaService(
        _fake_search,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
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

    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "BT 批量预览结果：https://nyaa.si/?f=0&c=1_2&q=frieren&p=2" in sent_text
    assert "title-Frieren S01E24" in sent_text
    assert "当前预览范围：1" in sent_text


def test_handle_message_bt_batch_preview_uncategorized_search_page_number_routes_to_page_fetch() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist uncategorized search page number")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?q=frieren&p=2"
        return [
            {
                "title": "title-Frieren S01E24",
                "source": "magnet:?xt=urn:btih:2424242424242424242424242424242424242424",
                "infoHash": "2424242424242424242424242424242424242424",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    update, reply_text = _build_update("bt批量 https://nyaa.si/?q=frieren&p=2 1-1")
    search_service = SearchMediaService(
        _fake_search,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
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

    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "BT 批量预览结果：https://nyaa.si/?q=frieren&p=2" in sent_text
    assert "title-Frieren S01E24" in sent_text
    assert "当前预览范围：1" in sent_text


def test_handle_message_bt_batch_preview_uncategorized_search_page_routes_to_page_fetch() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist uncategorized search page")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?q=frieren"
        return [
            {
                "title": "title-Frieren S01E26",
                "source": "magnet:?xt=urn:btih:2626262626262626262626262626262626262626",
                "infoHash": "2626262626262626262626262626262626262626",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    update, reply_text = _build_update("bt批量 https://nyaa.si/?q=frieren 1-1")
    search_service = SearchMediaService(
        _fake_search,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
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

    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "BT 批量预览结果：https://nyaa.si/?q=frieren" in sent_text
    assert "title-Frieren S01E26" in sent_text
    assert "当前预览范围：1" in sent_text


def test_handle_message_bt_batch_preview_category_base_page_routes_to_page_fetch() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist category base page")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?c=1_2"
        return [
            {
                "title": "title-Frieren S01E28",
                "source": "magnet:?xt=urn:btih:2828282828282828282828282828282828282828",
                "infoHash": "2828282828282828282828282828282828282828",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    update, reply_text = _build_update("bt批量 https://nyaa.si/?c=1_2 1-1")
    search_service = SearchMediaService(
        _fake_search,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
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

    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "BT 批量预览结果：https://nyaa.si/?c=1_2" in sent_text
    assert "title-Frieren S01E28" in sent_text
    assert "当前预览范围：1" in sent_text


def test_handle_message_bt_batch_preview_category_search_base_page_routes_to_page_fetch() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist category search base page")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?f=0&c=1_2&q=frieren"
        return [
            {
                "title": "title-Frieren S01E30",
                "source": "magnet:?xt=urn:btih:3030303030303030303030303030303030303030",
                "infoHash": "3030303030303030303030303030303030303030",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    update, reply_text = _build_update("bt批量 https://nyaa.si/?f=0&c=1_2&q=frieren 1-1")
    search_service = SearchMediaService(
        _fake_search,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
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

    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "BT 批量预览结果：https://nyaa.si/?f=0&c=1_2&q=frieren" in sent_text
    assert "title-Frieren S01E30" in sent_text
    assert "当前预览范围：1" in sent_text


def test_handle_message_bt_batch_preview_home_base_page_routes_to_page_fetch() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist home base page")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/"
        return [
            {
                "title": "title-Frieren S01E32",
                "source": "magnet:?xt=urn:btih:3232323232323232323232323232323232323232",
                "infoHash": "3232323232323232323232323232323232323232",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    update, reply_text = _build_update("bt批量 https://nyaa.si/ 1-1")
    search_service = SearchMediaService(
        _fake_search,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
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

    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "BT 批量预览结果：https://nyaa.si/" in sent_text
    assert "title-Frieren S01E32" in sent_text
    assert "当前预览范围：1" in sent_text


def test_handle_message_bt_batch_preview_search_sort_page_number_syntax_routes_to_page_fetch() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist search sort page number syntax")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?f=0&c=1_2&q=frieren&s=seeders&o=desc&p=2"
        return [
            {
                "title": "title-Frieren S01E22",
                "source": "magnet:?xt=urn:btih:2222222222222222222222222222222222222222",
                "infoHash": "2222222222222222222222222222222222222222",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    update, reply_text = _build_update("bt批量 https://nyaa.si/?f=0&c=1_2&q=frieren&s=seeders&o=desc p=2 1-1")
    search_service = SearchMediaService(
        _fake_search,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
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

    reply_text.assert_awaited_once()
    sent_text = reply_text.await_args.args[0]
    assert "BT 批量预览结果：https://nyaa.si/?f=0&c=1_2&q=frieren&s=seeders&o=desc p=2" in sent_text
    assert "title-Frieren S01E22" in sent_text
    assert "当前预览范围：1" in sent_text


def test_handle_message_bt_batch_confirm_reuses_sort_page_number_syntax_preview_candidates() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist sort page number syntax")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?s=seeders&o=desc&p=2"
        return [
            {
                "title": "title-Frieren S01E12",
                "source": "magnet:?xt=urn:btih:1212121212121212121212121212121212121212",
                "infoHash": "1212121212121212121212121212121212121212",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
            {
                "title": "title-Frieren S01E13",
                "source": "magnet:?xt=urn:btih:1313131313131313131313131313131313131313",
                "infoHash": "1313131313131313131313131313131313131313",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
        ]

    search_service = SearchMediaService(
        _fake_search,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
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
                DOWNLOADER_ROLE_BINDING_KEY: DownloaderRoleBinding(pt_downloader="", bt_downloader=""),
                DOWNLOADER_INSTANCES_KEY: (
                    DownloaderInstanceConfig(name="", downloader_type="transmission", base_url="", download_dir="/downloads"),
                ),
            }
        )
    )

    preview_update, preview_reply = _build_update("bt批量 https://nyaa.si/?s=seeders&o=desc p=2 1-2")
    asyncio.run(handle_message(preview_update, context))
    assert preview_reply.await_count == 1

    confirm_update, confirm_reply = _build_update("bt批量确认 1-2")
    asyncio.run(handle_message(confirm_update, context))

    confirm_reply.assert_awaited_once()
    sent_text = confirm_reply.await_args.args[0]
    assert sent_text.count("待确认：下载 ⏳") == 2
    assert "片名：title-Frieren S01E12" in sent_text
    assert "片名：title-Frieren S01E13" in sent_text
    assert "确认下载：发送 confirm 1" in sent_text
    assert "确认下载：发送 confirm 2" in sent_text


def test_handle_message_bt_batch_confirm_reuses_user_sort_page_preview_candidates() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist user sort page")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?f=0&c=1_2&u=subsplease&s=seeders&o=desc"
        return [
            {
                "title": "title-Frieren S01E16",
                "source": "magnet:?xt=urn:btih:1616161616161616161616161616161616161616",
                "infoHash": "1616161616161616161616161616161616161616",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
            {
                "title": "title-Frieren S01E17",
                "source": "magnet:?xt=urn:btih:1717171717171717171717171717171717171717",
                "infoHash": "1717171717171717171717171717171717171717",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
        ]

    search_service = SearchMediaService(
        _fake_search,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
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
                DOWNLOADER_ROLE_BINDING_KEY: DownloaderRoleBinding(pt_downloader="", bt_downloader=""),
                DOWNLOADER_INSTANCES_KEY: (
                    DownloaderInstanceConfig(name="", downloader_type="transmission", base_url="", download_dir="/downloads"),
                ),
            }
        )
    )

    preview_update, preview_reply = _build_update("bt批量 https://nyaa.si/?f=0&c=1_2&u=subsplease&s=seeders&o=desc 1-2")
    asyncio.run(handle_message(preview_update, context))
    assert preview_reply.await_count == 1

    confirm_update, confirm_reply = _build_update("bt批量确认 1-2")
    asyncio.run(handle_message(confirm_update, context))

    confirm_reply.assert_awaited_once()
    sent_text = confirm_reply.await_args.args[0]
    assert sent_text.count("待确认：下载 ⏳") == 2
    assert "片名：title-Frieren S01E16" in sent_text
    assert "片名：title-Frieren S01E17" in sent_text
    assert "确认下载：发送 confirm 1" in sent_text
    assert "确认下载：发送 confirm 2" in sent_text


def test_handle_message_bt_batch_confirm_reuses_uncategorized_user_sort_page_preview_candidates() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for uncategorized user sort page")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?u=subsplease&s=seeders&o=desc"
        return [
            {
                "title": "title-Frieren S01E16",
                "source": "magnet:?xt=urn:btih:1616161616161616161616161616161616161616",
                "infoHash": "1616161616161616161616161616161616161616",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
            {
                "title": "title-Frieren S01E17",
                "source": "magnet:?xt=urn:btih:1717171717171717171717171717171717171717",
                "infoHash": "1717171717171717171717171717171717171717",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
        ]

    search_service = SearchMediaService(
        _fake_search,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
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
                DOWNLOADER_ROLE_BINDING_KEY: DownloaderRoleBinding(pt_downloader="", bt_downloader=""),
                DOWNLOADER_INSTANCES_KEY: (
                    DownloaderInstanceConfig(name="", downloader_type="transmission", base_url="", download_dir="/downloads"),
                ),
            }
        )
    )

    preview_update, preview_reply = _build_update("bt批量 https://nyaa.si/?u=subsplease&s=seeders&o=desc 1-2")
    asyncio.run(handle_message(preview_update, context))
    assert preview_reply.await_count == 1

    confirm_update, confirm_reply = _build_update("bt批量确认 1-2")
    asyncio.run(handle_message(confirm_update, context))

    confirm_reply.assert_awaited_once()
    sent_text = confirm_reply.await_args.args[0]
    assert sent_text.count("待确认：下载 ⏳") == 2
    assert "片名：title-Frieren S01E16" in sent_text
    assert "片名：title-Frieren S01E17" in sent_text
    assert "确认下载：发送 confirm 1" in sent_text
    assert "确认下载：发送 confirm 2" in sent_text


def test_handle_message_bt_batch_confirm_reuses_user_sort_page_number_syntax_preview_candidates() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist user sort page number syntax")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?f=0&c=1_2&u=subsplease&s=seeders&o=desc&p=2"
        return [
            {
                "title": "title-Frieren S01E18",
                "source": "magnet:?xt=urn:btih:1818181818181818181818181818181818181818",
                "infoHash": "1818181818181818181818181818181818181818",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
            {
                "title": "title-Frieren S01E19",
                "source": "magnet:?xt=urn:btih:1919191919191919191919191919191919191919",
                "infoHash": "1919191919191919191919191919191919191919",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
        ]

    search_service = SearchMediaService(
        _fake_search,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
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
                DOWNLOADER_ROLE_BINDING_KEY: DownloaderRoleBinding(pt_downloader="", bt_downloader=""),
                DOWNLOADER_INSTANCES_KEY: (
                    DownloaderInstanceConfig(name="", downloader_type="transmission", base_url="", download_dir="/downloads"),
                ),
            }
        )
    )

    preview_update, preview_reply = _build_update("bt批量 https://nyaa.si/?f=0&c=1_2&u=subsplease&s=seeders&o=desc p=2 1-2")
    asyncio.run(handle_message(preview_update, context))
    assert preview_reply.await_count == 1

    confirm_update, confirm_reply = _build_update("bt批量确认 1-2")
    asyncio.run(handle_message(confirm_update, context))

    confirm_reply.assert_awaited_once()
    sent_text = confirm_reply.await_args.args[0]
    assert sent_text.count("待确认：下载 ⏳") == 2
    assert "片名：title-Frieren S01E18" in sent_text
    assert "片名：title-Frieren S01E19" in sent_text
    assert "确认下载：发送 confirm 1" in sent_text
    assert "确认下载：发送 confirm 2" in sent_text


def test_handle_message_bt_batch_confirm_reuses_uncategorized_user_page_number_preview_candidates() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for uncategorized user page number syntax")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?u=subsplease&p=2"
        return [
            {
                "title": "title-Frieren S01E11",
                "source": "magnet:?xt=urn:btih:1111111111111111111111111111111111111111",
                "infoHash": "1111111111111111111111111111111111111111",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
            {
                "title": "title-Frieren S01E12",
                "source": "magnet:?xt=urn:btih:1212121212121212121212121212121212121212",
                "infoHash": "1212121212121212121212121212121212121212",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
        ]

    search_service = SearchMediaService(
        _fake_search,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
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
                DOWNLOADER_ROLE_BINDING_KEY: DownloaderRoleBinding(pt_downloader="", bt_downloader=""),
                DOWNLOADER_INSTANCES_KEY: (
                    DownloaderInstanceConfig(name="", downloader_type="transmission", base_url="", download_dir="/downloads"),
                ),
            }
        )
    )

    preview_update, preview_reply = _build_update("bt批量 https://nyaa.si/?u=subsplease p=2 1-2")
    asyncio.run(handle_message(preview_update, context))
    assert preview_reply.await_count == 1

    confirm_update, confirm_reply = _build_update("bt批量确认 1-2")
    asyncio.run(handle_message(confirm_update, context))

    confirm_reply.assert_awaited_once()
    sent_text = confirm_reply.await_args.args[0]
    assert sent_text.count("待确认：下载 ⏳") == 2
    assert "片名：title-Frieren S01E11" in sent_text
    assert "片名：title-Frieren S01E12" in sent_text
    assert "确认下载：发送 confirm 1" in sent_text
    assert "确认下载：发送 confirm 2" in sent_text


def test_handle_message_bt_batch_confirm_reuses_uncategorized_user_sort_page_number_preview_candidates() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for uncategorized user sort page number syntax")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?u=subsplease&s=seeders&o=desc&p=2"
        return [
            {
                "title": "title-Frieren S01E18",
                "source": "magnet:?xt=urn:btih:1818181818181818181818181818181818181818",
                "infoHash": "1818181818181818181818181818181818181818",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
            {
                "title": "title-Frieren S01E19",
                "source": "magnet:?xt=urn:btih:1919191919191919191919191919191919191919",
                "infoHash": "1919191919191919191919191919191919191919",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
        ]

    search_service = SearchMediaService(
        _fake_search,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
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
                DOWNLOADER_ROLE_BINDING_KEY: DownloaderRoleBinding(pt_downloader="", bt_downloader=""),
                DOWNLOADER_INSTANCES_KEY: (
                    DownloaderInstanceConfig(name="", downloader_type="transmission", base_url="", download_dir="/downloads"),
                ),
            }
        )
    )

    preview_update, preview_reply = _build_update("bt批量 https://nyaa.si/?u=subsplease&s=seeders&o=desc p=2 1-2")
    asyncio.run(handle_message(preview_update, context))
    assert preview_reply.await_count == 1

    confirm_update, confirm_reply = _build_update("bt批量确认 1-2")
    asyncio.run(handle_message(confirm_update, context))

    confirm_reply.assert_awaited_once()
    sent_text = confirm_reply.await_args.args[0]
    assert sent_text.count("待确认：下载 ⏳") == 2
    assert "片名：title-Frieren S01E18" in sent_text
    assert "片名：title-Frieren S01E19" in sent_text
    assert "确认下载：发送 confirm 1" in sent_text
    assert "确认下载：发送 confirm 2" in sent_text


def test_handle_message_bt_batch_confirm_reuses_uncategorized_user_sort_page_number_url_preview_candidates() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for uncategorized user sort page number url")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?u=subsplease&s=seeders&o=desc&p=2"
        return [
            {
                "title": "title-Frieren S01E18",
                "source": "magnet:?xt=urn:btih:1818181818181818181818181818181818181818",
                "infoHash": "1818181818181818181818181818181818181818",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
            {
                "title": "title-Frieren S01E19",
                "source": "magnet:?xt=urn:btih:1919191919191919191919191919191919191919",
                "infoHash": "1919191919191919191919191919191919191919",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
        ]

    search_service = SearchMediaService(
        _fake_search,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
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
                DOWNLOADER_ROLE_BINDING_KEY: DownloaderRoleBinding(pt_downloader="", bt_downloader=""),
                DOWNLOADER_INSTANCES_KEY: (
                    DownloaderInstanceConfig(name="", downloader_type="transmission", base_url="", download_dir="/downloads"),
                ),
            }
        )
    )

    preview_update, preview_reply = _build_update("bt批量 https://nyaa.si/?u=subsplease&s=seeders&o=desc&p=2 1-2")
    asyncio.run(handle_message(preview_update, context))
    assert preview_reply.await_count == 1

    confirm_update, confirm_reply = _build_update("bt批量确认 1-2")
    asyncio.run(handle_message(confirm_update, context))

    confirm_reply.assert_awaited_once()
    sent_text = confirm_reply.await_args.args[0]
    assert sent_text.count("待确认：下载 ⏳") == 2
    assert "片名：title-Frieren S01E18" in sent_text
    assert "片名：title-Frieren S01E19" in sent_text
    assert "确认下载：发送 confirm 1" in sent_text
    assert "确认下载：发送 confirm 2" in sent_text


def test_handle_message_bt_batch_confirm_reuses_search_sort_page_preview_candidates() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist search sort page")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?f=0&c=1_2&q=frieren&s=seeders&o=desc"
        return [
            {
                "title": "title-Frieren S01E20",
                "source": "magnet:?xt=urn:btih:2020202020202020202020202020202020202020",
                "infoHash": "2020202020202020202020202020202020202020",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
            {
                "title": "title-Frieren S01E21",
                "source": "magnet:?xt=urn:btih:2121212121212121212121212121212121212121",
                "infoHash": "2121212121212121212121212121212121212121",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
        ]

    search_service = SearchMediaService(
        _fake_search,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
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
                DOWNLOADER_ROLE_BINDING_KEY: DownloaderRoleBinding(pt_downloader="", bt_downloader=""),
                DOWNLOADER_INSTANCES_KEY: (
                    DownloaderInstanceConfig(name="", downloader_type="transmission", base_url="", download_dir="/downloads"),
                ),
            }
        )
    )

    preview_update, preview_reply = _build_update("bt批量 https://nyaa.si/?f=0&c=1_2&q=frieren&s=seeders&o=desc 1-2")
    asyncio.run(handle_message(preview_update, context))
    assert preview_reply.await_count == 1

    confirm_update, confirm_reply = _build_update("bt批量确认 1-2")
    asyncio.run(handle_message(confirm_update, context))

    confirm_reply.assert_awaited_once()
    sent_text = confirm_reply.await_args.args[0]
    assert sent_text.count("待确认：下载 ⏳") == 2
    assert "片名：title-Frieren S01E20" in sent_text
    assert "片名：title-Frieren S01E21" in sent_text
    assert "确认下载：发送 confirm 1" in sent_text
    assert "确认下载：发送 confirm 2" in sent_text


def test_handle_message_bt_batch_confirm_reuses_search_page_number_preview_candidates() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist search page number")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?f=0&c=1_2&q=frieren&p=2"
        return [
            {
                "title": "title-Frieren S01E24",
                "source": "magnet:?xt=urn:btih:2424242424242424242424242424242424242424",
                "infoHash": "2424242424242424242424242424242424242424",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
            {
                "title": "title-Frieren S01E25",
                "source": "magnet:?xt=urn:btih:2525252525252525252525252525252525252525",
                "infoHash": "2525252525252525252525252525252525252525",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
        ]

    search_service = SearchMediaService(
        _fake_search,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
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
                DOWNLOADER_ROLE_BINDING_KEY: DownloaderRoleBinding(pt_downloader="", bt_downloader=""),
                DOWNLOADER_INSTANCES_KEY: (
                    DownloaderInstanceConfig(name="", downloader_type="transmission", base_url="", download_dir="/downloads"),
                ),
            }
        )
    )

    preview_update, preview_reply = _build_update("bt批量 https://nyaa.si/?f=0&c=1_2&q=frieren&p=2 1-2")
    asyncio.run(handle_message(preview_update, context))
    assert preview_reply.await_count == 1

    confirm_update, confirm_reply = _build_update("bt批量确认 1-2")
    asyncio.run(handle_message(confirm_update, context))

    confirm_reply.assert_awaited_once()
    sent_text = confirm_reply.await_args.args[0]
    assert sent_text.count("待确认：下载 ⏳") == 2
    assert "片名：title-Frieren S01E24" in sent_text
    assert "片名：title-Frieren S01E25" in sent_text
    assert "确认下载：发送 confirm 1" in sent_text
    assert "确认下载：发送 confirm 2" in sent_text


def test_handle_message_bt_batch_confirm_reuses_uncategorized_search_page_number_preview_candidates() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist uncategorized search page number")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?q=frieren&p=2"
        return [
            {
                "title": "title-Frieren S01E24",
                "source": "magnet:?xt=urn:btih:2424242424242424242424242424242424242424",
                "infoHash": "2424242424242424242424242424242424242424",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
            {
                "title": "title-Frieren S01E25",
                "source": "magnet:?xt=urn:btih:2525252525252525252525252525252525252525",
                "infoHash": "2525252525252525252525252525252525252525",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
        ]

    search_service = SearchMediaService(
        _fake_search,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
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
                DOWNLOADER_ROLE_BINDING_KEY: DownloaderRoleBinding(pt_downloader="", bt_downloader=""),
                DOWNLOADER_INSTANCES_KEY: (
                    DownloaderInstanceConfig(name="", downloader_type="transmission", base_url="", download_dir="/downloads"),
                ),
            }
        )
    )

    preview_update, preview_reply = _build_update("bt批量 https://nyaa.si/?q=frieren&p=2 1-2")
    asyncio.run(handle_message(preview_update, context))
    assert preview_reply.await_count == 1

    confirm_update, confirm_reply = _build_update("bt批量确认 1-2")
    asyncio.run(handle_message(confirm_update, context))

    confirm_reply.assert_awaited_once()
    sent_text = confirm_reply.await_args.args[0]
    assert sent_text.count("待确认：下载 ⏳") == 2
    assert "片名：title-Frieren S01E24" in sent_text
    assert "片名：title-Frieren S01E25" in sent_text
    assert "确认下载：发送 confirm 1" in sent_text
    assert "确认下载：发送 confirm 2" in sent_text


def test_handle_message_bt_batch_confirm_reuses_uncategorized_search_page_preview_candidates() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist uncategorized search page")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?q=frieren"
        return [
            {
                "title": "title-Frieren S01E26",
                "source": "magnet:?xt=urn:btih:2626262626262626262626262626262626262626",
                "infoHash": "2626262626262626262626262626262626262626",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
            {
                "title": "title-Frieren S01E27",
                "source": "magnet:?xt=urn:btih:2727272727272727272727272727272727272727",
                "infoHash": "2727272727272727272727272727272727272727",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
        ]

    search_service = SearchMediaService(
        _fake_search,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
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
                DOWNLOADER_ROLE_BINDING_KEY: DownloaderRoleBinding(pt_downloader="", bt_downloader=""),
                DOWNLOADER_INSTANCES_KEY: (
                    DownloaderInstanceConfig(name="", downloader_type="transmission", base_url="", download_dir="/downloads"),
                ),
            }
        )
    )

    preview_update, preview_reply = _build_update("bt批量 https://nyaa.si/?q=frieren 1-2")
    asyncio.run(handle_message(preview_update, context))
    assert preview_reply.await_count == 1

    confirm_update, confirm_reply = _build_update("bt批量确认 1-2")
    asyncio.run(handle_message(confirm_update, context))

    confirm_reply.assert_awaited_once()
    sent_text = confirm_reply.await_args.args[0]
    assert sent_text.count("待确认：下载 ⏳") == 2
    assert "片名：title-Frieren S01E26" in sent_text
    assert "片名：title-Frieren S01E27" in sent_text
    assert "确认下载：发送 confirm 1" in sent_text
    assert "确认下载：发送 confirm 2" in sent_text


def test_handle_message_bt_batch_confirm_reuses_category_base_page_preview_candidates() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist category base page")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?c=1_2"
        return [
            {
                "title": "title-Frieren S01E28",
                "source": "magnet:?xt=urn:btih:2828282828282828282828282828282828282828",
                "infoHash": "2828282828282828282828282828282828282828",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
            {
                "title": "title-Frieren S01E29",
                "source": "magnet:?xt=urn:btih:2929292929292929292929292929292929292929",
                "infoHash": "2929292929292929292929292929292929292929",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
        ]

    search_service = SearchMediaService(
        _fake_search,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
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
                DOWNLOADER_ROLE_BINDING_KEY: DownloaderRoleBinding(pt_downloader="", bt_downloader=""),
                DOWNLOADER_INSTANCES_KEY: (
                    DownloaderInstanceConfig(name="", downloader_type="transmission", base_url="", download_dir="/downloads"),
                ),
            }
        )
    )

    preview_update, preview_reply = _build_update("bt批量 https://nyaa.si/?c=1_2 1-2")
    asyncio.run(handle_message(preview_update, context))
    assert preview_reply.await_count == 1

    confirm_update, confirm_reply = _build_update("bt批量确认 1-2")
    asyncio.run(handle_message(confirm_update, context))

    confirm_reply.assert_awaited_once()
    sent_text = confirm_reply.await_args.args[0]
    assert sent_text.count("待确认：下载 ⏳") == 2
    assert "片名：title-Frieren S01E28" in sent_text
    assert "片名：title-Frieren S01E29" in sent_text
    assert "确认下载：发送 confirm 1" in sent_text
    assert "确认下载：发送 confirm 2" in sent_text


def test_handle_message_bt_batch_confirm_reuses_category_search_base_page_preview_candidates() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist category search base page")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?f=0&c=1_2&q=frieren"
        return [
            {
                "title": "title-Frieren S01E30",
                "source": "magnet:?xt=urn:btih:3030303030303030303030303030303030303030",
                "infoHash": "3030303030303030303030303030303030303030",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
            {
                "title": "title-Frieren S01E31",
                "source": "magnet:?xt=urn:btih:3131313131313131313131313131313131313131",
                "infoHash": "3131313131313131313131313131313131313131",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
        ]

    search_service = SearchMediaService(
        _fake_search,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
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
                DOWNLOADER_ROLE_BINDING_KEY: DownloaderRoleBinding(pt_downloader="", bt_downloader=""),
                DOWNLOADER_INSTANCES_KEY: (
                    DownloaderInstanceConfig(name="", downloader_type="transmission", base_url="", download_dir="/downloads"),
                ),
            }
        )
    )

    preview_update, preview_reply = _build_update("bt批量 https://nyaa.si/?f=0&c=1_2&q=frieren 1-2")
    asyncio.run(handle_message(preview_update, context))
    assert preview_reply.await_count == 1

    confirm_update, confirm_reply = _build_update("bt批量确认 1-2")
    asyncio.run(handle_message(confirm_update, context))

    confirm_reply.assert_awaited_once()
    sent_text = confirm_reply.await_args.args[0]
    assert sent_text.count("待确认：下载 ⏳") == 2
    assert "片名：title-Frieren S01E30" in sent_text
    assert "片名：title-Frieren S01E31" in sent_text
    assert "确认下载：发送 confirm 1" in sent_text
    assert "确认下载：发送 confirm 2" in sent_text


def test_handle_message_bt_batch_confirm_reuses_home_base_page_preview_candidates() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist home base page")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/"
        return [
            {
                "title": "title-Frieren S01E32",
                "source": "magnet:?xt=urn:btih:3232323232323232323232323232323232323232",
                "infoHash": "3232323232323232323232323232323232323232",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
            {
                "title": "title-Frieren S01E33",
                "source": "magnet:?xt=urn:btih:3333333333333333333333333333333333333333",
                "infoHash": "3333333333333333333333333333333333333333",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
        ]

    search_service = SearchMediaService(
        _fake_search,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
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
                DOWNLOADER_ROLE_BINDING_KEY: DownloaderRoleBinding(pt_downloader="", bt_downloader=""),
                DOWNLOADER_INSTANCES_KEY: (
                    DownloaderInstanceConfig(name="", downloader_type="transmission", base_url="", download_dir="/downloads"),
                ),
            }
        )
    )

    preview_update, preview_reply = _build_update("bt批量 https://nyaa.si/ 1-2")
    asyncio.run(handle_message(preview_update, context))
    assert preview_reply.await_count == 1

    confirm_update, confirm_reply = _build_update("bt批量确认 1-2")
    asyncio.run(handle_message(confirm_update, context))

    confirm_reply.assert_awaited_once()
    sent_text = confirm_reply.await_args.args[0]
    assert sent_text.count("待确认：下载 ⏳") == 2
    assert "片名：title-Frieren S01E32" in sent_text
    assert "片名：title-Frieren S01E33" in sent_text
    assert "确认下载：发送 confirm 1" in sent_text
    assert "确认下载：发送 confirm 2" in sent_text


def test_handle_message_bt_batch_confirm_reuses_search_sort_page_number_syntax_preview_candidates() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist search sort page number syntax")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?f=0&c=1_2&q=frieren&s=seeders&o=desc&p=2"
        return [
            {
                "title": "title-Frieren S01E22",
                "source": "magnet:?xt=urn:btih:2222222222222222222222222222222222222222",
                "infoHash": "2222222222222222222222222222222222222222",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
            {
                "title": "title-Frieren S01E23",
                "source": "magnet:?xt=urn:btih:2323232323232323232323232323232323232323",
                "infoHash": "2323232323232323232323232323232323232323",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
        ]

    search_service = SearchMediaService(
        _fake_search,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
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
                DOWNLOADER_ROLE_BINDING_KEY: DownloaderRoleBinding(pt_downloader="", bt_downloader=""),
                DOWNLOADER_INSTANCES_KEY: (
                    DownloaderInstanceConfig(name="", downloader_type="transmission", base_url="", download_dir="/downloads"),
                ),
            }
        )
    )

    preview_update, preview_reply = _build_update("bt批量 https://nyaa.si/?f=0&c=1_2&q=frieren&s=seeders&o=desc p=2 1-2")
    asyncio.run(handle_message(preview_update, context))
    assert preview_reply.await_count == 1

    confirm_update, confirm_reply = _build_update("bt批量确认 1-2")
    asyncio.run(handle_message(confirm_update, context))

    confirm_reply.assert_awaited_once()
    sent_text = confirm_reply.await_args.args[0]
    assert sent_text.count("待确认：下载 ⏳") == 2
    assert "片名：title-Frieren S01E22" in sent_text
    assert "片名：title-Frieren S01E23" in sent_text
    assert "确认下载：发送 confirm 1" in sent_text
    assert "确认下载：发送 confirm 2" in sent_text


def test_handle_message_bt_batch_confirm_reuses_category_sort_page_preview_candidates() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist category sort page")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?c=1_2&s=seeders&o=desc"
        return [
            {
                "title": "title-Frieren S01E06",
                "source": "magnet:?xt=urn:btih:1616161616161616161616161616161616161616",
                "infoHash": "1616161616161616161616161616161616161616",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
            {
                "title": "title-Frieren S01E07",
                "source": "magnet:?xt=urn:btih:1717171717171717171717171717171717171717",
                "infoHash": "1717171717171717171717171717171717171717",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
        ]

    search_service = SearchMediaService(
        _fake_search,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
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
                DOWNLOADER_ROLE_BINDING_KEY: DownloaderRoleBinding(pt_downloader="", bt_downloader=""),
                DOWNLOADER_INSTANCES_KEY: (
                    DownloaderInstanceConfig(name="", downloader_type="transmission", base_url="", download_dir="/downloads"),
                ),
            }
        )
    )

    preview_update, preview_reply = _build_update("bt批量 https://nyaa.si/?c=1_2&s=seeders&o=desc 1-2")
    asyncio.run(handle_message(preview_update, context))
    assert preview_reply.await_count == 1

    confirm_update, confirm_reply = _build_update("bt批量确认 1-2")
    asyncio.run(handle_message(confirm_update, context))

    confirm_reply.assert_awaited_once()
    sent_text = confirm_reply.await_args.args[0]
    assert sent_text.count("待确认：下载 ⏳") == 2
    assert "片名：title-Frieren S01E06" in sent_text
    assert "片名：title-Frieren S01E07" in sent_text
    assert "确认下载：发送 confirm 1" in sent_text
    assert "确认下载：发送 confirm 2" in sent_text


def test_handle_message_bt_batch_confirm_reuses_category_sort_page_number_syntax_preview_candidates() -> None:
    async def unexpected_raw_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("keyword raw search should not be used for allowlist category sort page number syntax")

    async def fake_page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?c=1_2&s=seeders&o=desc&p=2"
        return [
            {
                "title": "title-Frieren S01E14",
                "source": "magnet:?xt=urn:btih:1414141414141414141414141414141414141414",
                "infoHash": "1414141414141414141414141414141414141414",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
            {
                "title": "title-Frieren S01E15",
                "source": "magnet:?xt=urn:btih:1515151515151515151515151515151515151515",
                "infoHash": "1515151515151515151515151515151515151515",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
        ]

    search_service = SearchMediaService(
        _fake_search,
        raw_search_func=unexpected_raw_search,
        raw_page_search_func=fake_page_search,
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
                DOWNLOADER_ROLE_BINDING_KEY: DownloaderRoleBinding(pt_downloader="", bt_downloader=""),
                DOWNLOADER_INSTANCES_KEY: (
                    DownloaderInstanceConfig(name="", downloader_type="transmission", base_url="", download_dir="/downloads"),
                ),
            }
        )
    )

    preview_update, preview_reply = _build_update("bt批量 https://nyaa.si/?c=1_2&s=seeders&o=desc p=2 1-2")
    asyncio.run(handle_message(preview_update, context))
    assert preview_reply.await_count == 1

    confirm_update, confirm_reply = _build_update("bt批量确认 1-2")
    asyncio.run(handle_message(confirm_update, context))

    confirm_reply.assert_awaited_once()
    sent_text = confirm_reply.await_args.args[0]
    assert sent_text.count("待确认：下载 ⏳") == 2
    assert "片名：title-Frieren S01E14" in sent_text
    assert "片名：title-Frieren S01E15" in sent_text
    assert "确认下载：发送 confirm 1" in sent_text
    assert "确认下载：发送 confirm 2" in sent_text


def test_handle_message_bt_batch_confirm_routes_to_pending_downloads() -> None:
    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        assert query == "Frieren S01E01"
        return [
            {
                "title": "title-Frieren S01E01",
                "source": "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12",
                "infoHash": "abcdef1234567890abcdef1234567890abcdef12",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
            {
                "title": "title-Frieren S01E02",
                "source": "magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "infoHash": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            },
        ]

    search_service = SearchMediaService(_fake_search, raw_search_func=fake_raw_search)
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
                DOWNLOADER_ROLE_BINDING_KEY: DownloaderRoleBinding(pt_downloader="", bt_downloader=""),
                DOWNLOADER_INSTANCES_KEY: (
                    DownloaderInstanceConfig(name="", downloader_type="transmission", base_url="", download_dir="/downloads"),
                ),
            }
        )
    )

    preview_update, preview_reply = _build_update("bt批量 Frieren S01E01 1-2")
    asyncio.run(handle_message(preview_update, context))
    assert preview_reply.await_count == 1

    confirm_update, confirm_reply = _build_update("bt批量确认 1-2")
    asyncio.run(handle_message(confirm_update, context))

    confirm_reply.assert_awaited_once()
    sent_text = confirm_reply.await_args.args[0]
    assert sent_text.count("待确认：下载 ⏳") == 2
    assert "片名：title-Frieren S01E01" in sent_text
    assert "片名：title-Frieren S01E02" in sent_text
    assert "确认下载：发送 confirm 1" in sent_text
    assert "确认下载：发送 confirm 2" in sent_text


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

    reply_text.assert_awaited_once_with("下载确认状态读取失败，请稍后重试。")
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


def test_handle_message_stops_when_update_dedup_persist_fails(tmp_path: Path, capsys) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    update_repo = TelegramUpdateRepo(database)

    def _crash_record_message_update(**_: object) -> bool:
        raise RuntimeError("db down")

    update_repo.record_message_update = _crash_record_message_update  # type: ignore[method-assign]
    update, reply_text = _build_update("dune", update_id=9002)
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

    reply_text.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[Telegram 更新去重落盘失败]" in output
    assert "source_type=message" in output
    assert "source_id=9002" in output
    assert "[处理建议]" in output


def test_handle_message_stops_when_update_dedup_result_missing(tmp_path: Path, capsys) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    update_repo = TelegramUpdateRepo(database)

    def _missing_record_message_update(**_: object) -> None:
        return None

    update_repo.record_message_update = _missing_record_message_update  # type: ignore[method-assign]
    update, reply_text = _build_update("dune", update_id=9003)
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

    reply_text.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[Telegram 更新去重结果缺失]" in output
    assert "source_type=message" in output
    assert "source_id=9003" in output
    assert "telegram update record result missing" in output
    assert "[处理建议]" in output


def test_handle_callback_query_stops_when_update_dedup_persist_fails(tmp_path: Path, capsys) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    update_repo = TelegramUpdateRepo(database)

    def _crash_record_callback_update(**_: object) -> bool:
        raise RuntimeError("db down")

    update_repo.record_callback_update = _crash_record_callback_update  # type: ignore[method-assign]
    update, reply_text, answer = _build_callback_update("dune", callback_query_id="cb-9002")
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

    answer.assert_not_awaited()
    reply_text.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[Telegram 更新去重落盘失败]" in output
    assert "source_type=callback" in output
    assert "source_id=cb-9002" in output
    assert "[处理建议]" in output


def test_handle_callback_query_stops_when_update_dedup_result_missing(tmp_path: Path, capsys) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    update_repo = TelegramUpdateRepo(database)

    def _missing_record_callback_update(**_: object) -> None:
        return None

    update_repo.record_callback_update = _missing_record_callback_update  # type: ignore[method-assign]
    update, reply_text, answer = _build_callback_update("dune", callback_query_id="cb-9003")
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

    answer.assert_not_awaited()
    reply_text.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[Telegram 更新去重结果缺失]" in output
    assert "source_type=callback" in output
    assert "source_id=cb-9003" in output
    assert "telegram update record result missing" in output
    assert "[处理建议]" in output


def test_handle_message_stops_when_update_id_invalid(tmp_path: Path, capsys) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    update_repo = TelegramUpdateRepo(database)
    update, reply_text = _build_update("dune", update_id=0)
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

    reply_text.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[Telegram 更新去重落盘失败]" in output
    assert "source_type=message" in output
    assert "source_id=0" in output
    assert "message update_id missing or invalid" in output


def test_handle_callback_query_stops_when_callback_id_missing(tmp_path: Path, capsys) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    update_repo = TelegramUpdateRepo(database)
    update, reply_text, answer = _build_callback_update("dune", callback_query_id="")
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

    answer.assert_not_awaited()
    reply_text.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[Telegram 更新去重落盘失败]" in output
    assert "source_type=callback" in output
    assert "source_id=-" in output
    assert "callback_query_id missing" in output


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


def test_handle_message_frustration_does_not_reply_when_candidate_clear_fails(capsys) -> None:
    class BoomRepo:
        def save_candidates(self, chat_id: int, candidates: object) -> None:
            _ = (chat_id, candidates)

        def clear_candidates(self, chat_id: int) -> bool:
            raise RuntimeError("db down")

    update, reply_text = _build_update("算了")
    search_service = SearchMediaService(_fake_search, candidate_repo=BoomRepo())
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

    reply_text.assert_awaited_once_with(SERVICE_NOT_READY_TEXT)
    assert search_service.get_cached_candidate(1001, 1) is not None
    output = capsys.readouterr().out
    assert "[搜索候选清理失败]" in output
    assert "chat_id=1001" in output
    assert "db down" in output


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


def test_handle_message_frustration_does_not_reply_when_clarification_clear_fails(capsys) -> None:
    class BoomRepo:
        def upsert_pending(self, *, chat_id: int, query: str) -> None:
            _ = (chat_id, query)

        def clear_pending(self, chat_id: int) -> bool:
            raise RuntimeError("db down")

    update, reply_text = _build_update("重来")
    search_service = SearchMediaService(_fake_search_empty, clarification_repo=BoomRepo())
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

    reply_text.assert_awaited_once_with(SERVICE_NOT_READY_TEXT)
    assert search_service.is_clarification_pending(1001)
    output = capsys.readouterr().out
    assert "[搜索澄清态清理失败]" in output
    assert "chat_id=1001" in output
    assert "db down" in output


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
    assert "【搜索结果】 算了" in sent_text
    assert "直接回复 1 继续，例如：1" in sent_text


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
    cleanup_db = SqliteDatabase(":memory:")
    cleanup_db.initialize()
    cleanup_service = CleanupDownloadedSourceService(JobEventRepo(cleanup_db))
    watchlist_db = SqliteDatabase(":memory:")
    watchlist_db.initialize()
    watchlist_service = ManageWatchlistService(WatchlistRepo(watchlist_db))
    bt_subscription_db = SqliteDatabase(":memory:")
    bt_subscription_db.initialize()
    bt_subscription_service = ManageBtSubscriptionService(
        BtSubscriptionRepo(bt_subscription_db),
        _fake_search,
        add_service,
    )
    database = SqliteDatabase(":memory:")
    database.initialize()
    job_repo = JobRepo(database)
    bt_pending_repo = BtPendingRepo(database)
    downloader_instances = (
        DownloaderInstanceConfig(
            name="tr-main",
            downloader_type="transmission",
            base_url="http://transmission:9091",
            download_dir="/data/downloads/tr",
        ),
    )
    downloader_role_binding = DownloaderRoleBinding(
        pt_downloader="tr-main",
        bt_downloader="tr-main",
    )
    application = build_application(
        "token",
        search_service,
        add_service,
        status_service,
        import_service,
        cleanup_service,
        watchlist_service,
        bt_subscription_service,
        job_repo=job_repo,
        bt_pending_repo=bt_pending_repo,
        raw_bt_destination_options=(
            RawBtDestinationOption(key="downloads", label="下载目录", target_dir="/data/raw/downloads"),
        ),
        downloader_instances=downloader_instances,
        downloader_role_binding=downloader_role_binding,
    )
    assert application.bot_data[SEARCH_SERVICE_KEY] is search_service
    assert application.bot_data[ADD_TO_DOWNLOADER_SERVICE_KEY] is add_service
    assert application.bot_data[GET_DOWNLOAD_STATUS_SERVICE_KEY] is status_service
    assert application.bot_data[IMPORT_TO_LIBRARY_SERVICE_KEY] is import_service
    assert application.bot_data[CLEANUP_DOWNLOADED_SOURCE_SERVICE_KEY] is cleanup_service
    assert application.bot_data[MANAGE_WATCHLIST_SERVICE_KEY] is watchlist_service
    assert application.bot_data[MANAGE_BT_SUBSCRIPTION_SERVICE_KEY] is bt_subscription_service
    assert application.bot_data[JOB_REPO_KEY] is job_repo
    assert application.bot_data[BT_PENDING_REPO_KEY] is bt_pending_repo
    assert application.bot_data[RAW_BT_DESTINATION_OPTIONS_KEY][0].key == "downloads"
    assert application.bot_data[DOWNLOADER_INSTANCES_KEY] == downloader_instances
    assert application.bot_data[DOWNLOADER_ROLE_BINDING_KEY] is downloader_role_binding
    assert callable(application.bot_data[TELEGRAM_SEND_MEDIA_FUNC_KEY])
    assert callable(application.bot_data[TELEGRAM_SEND_TEXT_FUNC_KEY])
    assert any(
        isinstance(handler, CallbackQueryHandler)
        for handlers in application.handlers.values()
        for handler in handlers
    )


def test_log_bt_subscription_scheduler_config_error_prints_fix_hint(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _log_bt_subscription_scheduler_config_error(reason="未配置 BT 下载器角色绑定，后台自动扫描不会启动。")

    captured = capsys.readouterr()
    assert "[BT 订阅后台扫描未启动]" in captured.out
    assert "[处理建议]" in captured.out


def test_run_bt_subscription_scheduler_tick_once_skips_none_notifications() -> None:
    execution_gate = SimpleNamespace(run=AsyncMock(return_value=None))
    application = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))
    service = SimpleNamespace(run_scheduler_tick=AsyncMock(return_value=None))

    asyncio.run(
        _run_bt_subscription_scheduler_tick_once(
            application=application,
            bt_subscription_service=service,
            execution_gate=execution_gate,
            dispatch_context=SimpleNamespace(),
        )
    )

    application.bot.send_message.assert_not_awaited()


def test_run_bt_subscription_scheduler_tick_once_logs_result_unavailable(capsys: pytest.CaptureFixture[str]) -> None:
    execution_gate = SimpleNamespace(run=AsyncMock(return_value=None))
    application = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))
    service = SimpleNamespace(run_scheduler_tick=AsyncMock(return_value=None))

    asyncio.run(
        _run_bt_subscription_scheduler_tick_once(
            application=application,
            bt_subscription_service=service,
            execution_gate=execution_gate,
            dispatch_context=SimpleNamespace(),
        )
    )

    output = capsys.readouterr().out
    assert "[BT 订阅后台扫描结果不可用]" in output
    assert "[处理建议]" in output
    application.bot.send_message.assert_not_awaited()


def test_post_download_auto_import_scheduler_loop_runs_once_and_stops() -> None:
    stop_event = asyncio.Event()

    async def run_once() -> AutoImportRunResult:
        stop_event.set()
        return AutoImportRunResult(scanned=1, progressed=1, replies=("导入待确认",))

    service = SimpleNamespace(run_once=AsyncMock(side_effect=run_once))

    asyncio.run(_post_download_auto_import_scheduler_loop(service=service, stop_event=stop_event))

    service.run_once.assert_awaited_once()


def test_post_download_auto_import_scheduler_loop_logs_state_unavailable(capsys: pytest.CaptureFixture[str]) -> None:
    stop_event = asyncio.Event()

    async def run_once() -> AutoImportRunResult:
        stop_event.set()
        return AutoImportRunResult(scanned=2, progressed=0, replies=(), state_unavailable=True)

    service = SimpleNamespace(run_once=AsyncMock(side_effect=run_once))

    asyncio.run(_post_download_auto_import_scheduler_loop(service=service, stop_event=stop_event))

    output = capsys.readouterr().out
    assert "[下载完成后台轮询状态读取失败]" in output
    assert "scanned=2" in output
    assert "[处理建议]" in output


def test_poll_pending_download_completion_once_reuses_status_service() -> None:
    repo = SimpleNamespace(
        list_pending_completion=Mock(
            return_value=(SimpleNamespace(task_hash="hash-41", chat_id=1001), SimpleNamespace(task_hash="hash-42", chat_id=1002))
        )
    )
    status_service = SimpleNamespace(get_status_text=AsyncMock())
    asyncio.run(_poll_pending_download_completion_once(download_monitor_repo=repo, status_service=status_service))
    assert status_service.get_status_text.await_args_list == [call("hash-41", chat_id=1001), call("hash-42", chat_id=1002)]


def test_poll_pending_download_completion_once_logs_pending_list_failure(capsys: pytest.CaptureFixture[str]) -> None:
    repo = SimpleNamespace(list_pending_completion=Mock(side_effect=RuntimeError("db down")))
    status_service = SimpleNamespace(get_status_text=AsyncMock())

    asyncio.run(_poll_pending_download_completion_once(download_monitor_repo=repo, status_service=status_service))

    output = capsys.readouterr().out
    assert "[下载完成待轮询列表读取失败]" in output
    assert "db down" in output
    assert "[处理建议]" in output
    status_service.get_status_text.assert_not_awaited()


def test_poll_pending_download_completion_once_logs_pending_list_missing_result(
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = SimpleNamespace(list_pending_completion=Mock(return_value=None))
    status_service = SimpleNamespace(get_status_text=AsyncMock())

    asyncio.run(_poll_pending_download_completion_once(download_monitor_repo=repo, status_service=status_service))

    output = capsys.readouterr().out
    assert "[下载完成待轮询列表结果缺失]" in output
    assert "download completion pending list result missing" in output
    assert "[处理建议]" in output
    status_service.get_status_text.assert_not_awaited()


def test_poll_pending_download_completion_once_logs_pending_list_row_corruption(
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = SimpleNamespace(
        list_pending_completion=Mock(
            side_effect=DownloadMonitorPersistenceError("download monitor chat identity corrupted after read")
        )
    )
    status_service = SimpleNamespace(get_status_text=AsyncMock())

    asyncio.run(_poll_pending_download_completion_once(download_monitor_repo=repo, status_service=status_service))

    output = capsys.readouterr().out
    assert "[下载完成待轮询列表记录损坏]" in output
    assert "download monitor chat identity corrupted after read" in output
    assert "[处理建议]" in output
    status_service.get_status_text.assert_not_awaited()


def test_download_completion_polling_loop_runs_once_and_stops() -> None:
    stop_event = asyncio.Event()

    def list_pending_completion():
        stop_event.set()
        return ()

    repo = SimpleNamespace(list_pending_completion=Mock(side_effect=list_pending_completion))
    asyncio.run(
        _download_completion_polling_loop(
            download_monitor_repo=repo,
            status_service=SimpleNamespace(get_status_text=AsyncMock()),
            stop_event=stop_event,
        )
    )
    repo.list_pending_completion.assert_called_once_with()


def test_download_completion_polling_loop_logs_fix_hint_on_error(capsys: pytest.CaptureFixture[str]) -> None:
    stop_event = asyncio.Event()
    repo = SimpleNamespace(
        list_pending_completion=Mock(return_value=(SimpleNamespace(task_hash="hash-41", chat_id=1001),))
    )

    async def _boom(*args, **kwargs):
        stop_event.set()
        raise RuntimeError("boom")

    asyncio.run(
        _download_completion_polling_loop(
            download_monitor_repo=repo,
            status_service=SimpleNamespace(get_status_text=AsyncMock(side_effect=_boom)),
            stop_event=stop_event,
        )
    )
    captured = capsys.readouterr()
    assert "[下载完成状态轮询失败]" in captured.out
    assert "[处理建议]" in captured.out


def test_start_post_download_auto_import_scheduler_also_starts_download_completion_polling() -> None:
    database = SqliteDatabase(":memory:")
    database.initialize()
    monitor_repo = DownloadMonitorRepo(database)
    status_service = GetDownloadStatusService(AsyncMock(), download_monitor_repo=monitor_repo)
    app = SimpleNamespace(
        bot_data={
            GET_DOWNLOAD_STATUS_SERVICE_KEY: status_service,
            POST_DOWNLOAD_AUTO_IMPORT_SERVICE_KEY: PostDownloadAutoImportService(monitor_repo, JobEventRepo(database), AsyncMock()),
        },
        create_task=Mock(return_value=SimpleNamespace()),
    )
    _start_post_download_auto_import_scheduler(app)
    assert [item.kwargs["name"] for item in app.create_task.call_args_list] == [
        "post_download_auto_import_scheduler",
        "download_completion_polling_scheduler",
    ]
    for item in app.create_task.call_args_list:
        item.args[0].close()


def test_start_post_download_auto_import_scheduler_starts_completion_polling_without_auto_import_service() -> None:
    database = SqliteDatabase(":memory:")
    database.initialize()
    monitor_repo = DownloadMonitorRepo(database)
    app = SimpleNamespace(
        bot_data={GET_DOWNLOAD_STATUS_SERVICE_KEY: GetDownloadStatusService(AsyncMock(), download_monitor_repo=monitor_repo)},
        create_task=Mock(return_value=SimpleNamespace()),
    )
    _start_post_download_auto_import_scheduler(app)
    assert [item.kwargs["name"] for item in app.create_task.call_args_list] == ["download_completion_polling_scheduler"]
    app.create_task.call_args_list[0].args[0].close()


def test_start_post_download_auto_import_scheduler_logs_fix_hint_when_completion_polling_missing_repo(
    capsys: pytest.CaptureFixture[str],
) -> None:
    app = SimpleNamespace(
        bot_data={GET_DOWNLOAD_STATUS_SERVICE_KEY: GetDownloadStatusService(AsyncMock())},
        create_task=Mock(return_value=SimpleNamespace()),
    )
    _start_post_download_auto_import_scheduler(app)
    captured = capsys.readouterr()
    assert "[下载完成状态轮询未启动]" in captured.out
    assert "[处理建议]" in captured.out


def test_stop_post_download_auto_import_scheduler_stops_download_completion_polling_task() -> None:
    async def run() -> None:
        first_stop_event = asyncio.Event()
        first_task = asyncio.create_task(first_stop_event.wait())
        second_stop_event = asyncio.Event()
        second_task = asyncio.create_task(second_stop_event.wait())
        application = SimpleNamespace(
            bot_data={
                POST_DOWNLOAD_AUTO_IMPORT_STOP_EVENT_KEY: first_stop_event,
                POST_DOWNLOAD_AUTO_IMPORT_TASK_KEY: first_task,
                DOWNLOAD_COMPLETION_POLLING_STOP_EVENT_KEY: second_stop_event,
                DOWNLOAD_COMPLETION_POLLING_TASK_KEY: second_task,
            }
        )
        await _stop_post_download_auto_import_scheduler(application)
        assert first_stop_event.is_set() and second_stop_event.is_set()
        assert first_task.done() and second_task.done()

    asyncio.run(run())


def test_stop_post_download_auto_import_scheduler_logs_fix_hint_when_completion_polling_task_fails(
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def boom() -> None:
        raise RuntimeError("boom")

    async def run() -> None:
        failing_task = asyncio.create_task(boom())
        application = SimpleNamespace(
            bot_data={
                DOWNLOAD_COMPLETION_POLLING_STOP_EVENT_KEY: asyncio.Event(),
                DOWNLOAD_COMPLETION_POLLING_TASK_KEY: failing_task,
            }
        )
        with pytest.raises(RuntimeError, match="boom"):
            await _stop_post_download_auto_import_scheduler(application)

    asyncio.run(run())
    captured = capsys.readouterr()
    assert "[下载完成状态轮询停止失败]" in captured.out
    assert "[处理建议]" in captured.out


def test_build_application_applies_outbound_proxy_to_telegram_requests() -> None:
    search_db = SqliteDatabase(":memory:")
    search_db.initialize()
    search_service = SearchMediaService(
        _fake_search,
        _fake_search,
        candidate_repo=CandidateMappingRepo(search_db),
    )
    add_db = SqliteDatabase(":memory:")
    add_db.initialize()
    add_service = AddToDownloaderService(
        search_service=search_service,
        add_torrent_func=lambda source, downloader_name="", download_dir="": (_ for _ in ()).throw(
            AssertionError(f"unexpected add_torrent call: {source} {downloader_name} {download_dir}")
        ),
        approval_repo=ApprovalRepo(add_db),
        job_repo=JobRepo(add_db),
        job_event_repo=JobEventRepo(add_db),
        download_monitor_repo=DownloadMonitorRepo(add_db),
    )
    import_db = SqliteDatabase(":memory:")
    import_db.initialize()
    import_service = ImportToLibraryService(
        get_import_source_func=lambda *_args, **_kwargs: None,
        library_target_dir="/data/library/movies",
        job_event_repo=JobEventRepo(import_db),
        approval_repo=ApprovalRepo(import_db),
        job_repo=JobRepo(import_db),
    )
    cleanup_service = CleanupDownloadedSourceService(job_event_repo=JobEventRepo(import_db), job_repo=JobRepo(import_db))
    status_service = GetDownloadStatusService(lambda *_args, **_kwargs: None)
    watchlist_db = SqliteDatabase(":memory:")
    watchlist_db.initialize()
    watchlist_service = ManageWatchlistService(WatchlistRepo(watchlist_db))
    bt_subscription_db = SqliteDatabase(":memory:")
    bt_subscription_db.initialize()
    bt_subscription_service = ManageBtSubscriptionService(
        BtSubscriptionRepo(bt_subscription_db),
        _fake_search,
        add_service,
    )

    application = build_application(
        "token",
        search_service,
        add_service,
        status_service,
        import_service,
        cleanup_service,
        watchlist_service,
        bt_subscription_service,
        outbound_proxy_url="http://192.168.2.110:7890",
    )

    assert application.bot._request[0]._client_kwargs["proxy"] == "http://192.168.2.110:7890"
    assert application.bot._request[1]._client_kwargs["proxy"] == "http://192.168.2.110:7890"


def test_handle_message_routes_personal_wechat_login_and_sends_qr_result(
    tmp_path: Path,
) -> None:
    async def start_login_func(**_: object) -> object:
        return SimpleNamespace(
            qrcode_url="https://login.example/qr/telegram",
            session_key="session-telegram",
            message="ok",
        )

    async def wait_login_func(**_: object) -> object:
        return SimpleNamespace(
            connected=True,
            account_id="wx-account-telegram",
            bot_token="bot-token-telegram",
            base_url="https://ilinkai.weixin.qq.com",
            user_id="wx-user-telegram",
        )

    send_message = AsyncMock()
    send_media = AsyncMock(return_value="document-ok")

    def build_qr_artifact(_: str):
        qr_dir = tmp_path / "telegram-qr"
        qr_dir.mkdir()
        file_path = qr_dir / "wechat-login.png"
        file_path.write_bytes(b"png")
        return SimpleNamespace(dir_path=qr_dir, file_path=file_path)

    async def close_client() -> None:
        return None

    service = PersonalWeChatLoginService(
        start_login_func=start_login_func,
        wait_login_func=wait_login_func,
        save_account_func=Mock(),
        register_account_func=Mock(),
        clear_stale_accounts_func=Mock(),
        close_client_func=close_client,
        qr_artifact_builder=build_qr_artifact,
    )

    update, reply_text = _build_update("微信登录", update_id=79)
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
                TELEGRAM_SEND_MEDIA_FUNC_KEY: send_media,
                TELEGRAM_SEND_TEXT_FUNC_KEY: send_message,
                PERSONAL_WECHAT_LOGIN_SERVICE_KEY: service,
            },
        )
    )

    asyncio.run(handle_message(update, context))
    if service._wait_task is not None:
        asyncio.run(service._wait_task)

    reply_text.assert_awaited_once_with(
        "已发起 personal WeChat 登录。\n二维码文件已回传到当前 Telegram 私聊，请直接打开并扫码。\n当前这一步只补登录入口，暂不接微信私聊文本命令。"
    )
    send_media.assert_awaited_once()
    send_message.assert_awaited_once_with(
        chat_id=1001,
        text="personal WeChat 登录成功。\n账号 ID: wx-account-telegram\n用户 ID: wx-user-telegram",
    )


def test_telegram_media_sender_uses_photo_for_image_path(
    tmp_path: Path,
) -> None:
    send_photo = AsyncMock(return_value="photo-message")
    sender = build_telegram_send_media_func(
        SimpleNamespace(
            bot=SimpleNamespace(
                send_photo=send_photo,
                send_document=AsyncMock(),
            )
        )
    )
    file_path = tmp_path / "wechat-login.png"
    file_path.write_bytes(b"fake-png")

    result = asyncio.run(sender(1001, file_path, "微信登录二维码"))

    assert result == "photo-message"
    send_photo.assert_awaited_once_with(
        chat_id=1001,
        photo=file_path,
        caption="微信登录二维码",
    )


def test_telegram_media_sender_uses_document_for_non_image_path(
    tmp_path: Path,
) -> None:
    send_document = AsyncMock(return_value="document-message")
    sender = build_telegram_send_media_func(
        SimpleNamespace(
            bot=SimpleNamespace(
                send_photo=AsyncMock(),
                send_document=send_document,
            )
        )
    )
    file_path = tmp_path / "wechat-login.txt"
    file_path.write_text("login-token", encoding="utf-8")

    result = asyncio.run(sender(1001, file_path, "登录辅助文件"))

    assert result == "document-message"
    send_document.assert_awaited_once_with(
        chat_id=1001,
        document=file_path,
        caption="登录辅助文件",
        filename="wechat-login.txt",
    )


def test_telegram_media_sender_logs_missing_file_and_raises(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    sender = build_telegram_send_media_func(
        SimpleNamespace(
            bot=SimpleNamespace(
                send_photo=AsyncMock(),
                send_document=AsyncMock(),
            )
        )
    )
    missing_path = tmp_path / "missing-qr.png"

    with pytest.raises(FileNotFoundError):
        asyncio.run(sender(1001, missing_path, "微信登录二维码"))

    captured = capsys.readouterr()
    assert "[Telegram 媒资发送失败]" in captured.out
    assert "文件不存在" in captured.out
    assert "[处理建议]" in captured.out


def test_telegram_media_sender_logs_api_failure_and_reraises(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    send_photo = AsyncMock(side_effect=RuntimeError("telegram api down"))
    sender = build_telegram_send_media_func(
        SimpleNamespace(
            bot=SimpleNamespace(
                send_photo=send_photo,
                send_document=AsyncMock(),
            )
        )
    )
    file_path = tmp_path / "wechat-login.png"
    file_path.write_bytes(b"fake-png")

    with pytest.raises(RuntimeError, match="telegram api down"):
        asyncio.run(sender(1001, file_path, "微信登录二维码"))

    captured = capsys.readouterr()
    assert "[Telegram 媒资发送失败]" in captured.out
    assert "chat_id=1001" in captured.out
    assert "telegram api down" in captured.out
    assert "[处理建议]" in captured.out


def _run(coroutine: Awaitable[str]) -> str:
    return asyncio.run(coroutine)


def _make_database(tmp_path: Path) -> SqliteDatabase:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    return database

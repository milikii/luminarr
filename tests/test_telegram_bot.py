from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from telegram.ext import CallbackQueryHandler

from app.bot.personal_wechat_login import PERSONAL_WECHAT_LOGIN_SERVICE_KEY, PersonalWeChatLoginService
from app.config import DownloaderInstanceConfig, DownloaderRoleBinding, RawBtDestinationOption
from app.clients.tmdb import TmdbMovie
from app.clients.transmission import TransmissionTaskStatus
from app.bot.telegram_bot import (
    ADD_TO_DOWNLOADER_SERVICE_KEY,
    BT_READ_ONLY_HELPER_FAILED_TEXT,
    BT_PENDING_REPO_KEY,
    BT_CLASSIFICATION_PROMPT_TEXT,
    BT_PROCESSING_PATH_CANCELLED_TEXT,
    BT_PROCESSING_PATH_PENDING_REMINDER_TEXT,
    BT_PROCESSING_PATH_PROMPT_TEXT,
    RAW_BT_DESTINATION_CANCELLED_TEXT,
    RAW_BT_DESTINATION_OPTIONS_KEY,
    RAW_BT_DESTINATION_SERVICE_NOT_READY_TEXT,
    BT_TMDB_ASSOCIATION_CANCELLED_TEXT,
    BT_TMDB_ASSOCIATION_SERVICE_NOT_READY_TEXT,
    BT_TMDB_MOVIE_CANDIDATES_LOOKUP_KEY,
    BT_TMDB_TV_CANDIDATES_LOOKUP_KEY,
    CLARIFICATION_SELECTION_BLOCKED_TEXT,
    CLARIFICATION_RESET_TEXT,
    DOWNLOADER_INSTANCES_KEY,
    DOWNLOADER_ROLE_BINDING_KEY,
    FRUSTRATION_RESET_TEXT,
    GET_DOWNLOAD_STATUS_SERVICE_KEY,
    IMPORT_TO_LIBRARY_SERVICE_KEY,
    JOB_REPO_KEY,
    LLM_PHYSICAL_FAILURE_SAFE_TEXT,
    MANAGE_BT_SUBSCRIPTION_SERVICE_KEY,
    MANAGE_WATCHLIST_SERVICE_KEY,
    SEARCH_SERVICE_KEY,
    SERVICE_NOT_READY_TEXT,
    TELEGRAM_UPDATE_REPO_KEY,
    TELEGRAM_SEND_MEDIA_FUNC_KEY,
    build_application,
    build_telegram_send_media_func,
    handle_callback_query,
    handle_message,
)
from app.clients.transmission import TransmissionImportSource
from app.db.approval_repo import ApprovalRepo
from app.db.bt_pending_repo import BtPendingRepo
from app.db.bt_subscription_repo import BtSubscriptionRepo
from app.db.clarification_repo import ClarificationRepo
from app.db.job_repo import JobRepo
from app.db.sqlite import SqliteDatabase
from app.db.telegram_update_repo import TelegramUpdateRepo
from app.db.watchlist_repo import WatchlistRepo
from app.services.add_to_downloader import ADD_CANCELLED_TEXT, AddToDownloaderService
from app.services.get_download_status import GetDownloadStatusService
from app.services.import_to_library import IMPORT_CANCELLED_TEXT, ImportToLibraryService
from app.services.manage_bt_subscription import ManageBtSubscriptionService
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
    assert application.bot_data[MANAGE_WATCHLIST_SERVICE_KEY] is watchlist_service
    assert application.bot_data[MANAGE_BT_SUBSCRIPTION_SERVICE_KEY] is bt_subscription_service
    assert application.bot_data[JOB_REPO_KEY] is job_repo
    assert application.bot_data[BT_PENDING_REPO_KEY] is bt_pending_repo
    assert application.bot_data[RAW_BT_DESTINATION_OPTIONS_KEY][0].key == "downloads"
    assert application.bot_data[DOWNLOADER_INSTANCES_KEY] == downloader_instances
    assert application.bot_data[DOWNLOADER_ROLE_BINDING_KEY] is downloader_role_binding
    assert callable(application.bot_data[TELEGRAM_SEND_MEDIA_FUNC_KEY])
    assert any(
        isinstance(handler, CallbackQueryHandler)
        for handlers in application.handlers.values()
        for handler in handlers
    )


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
        file_path = qr_dir / "wechat-login.svg"
        file_path.write_text("<svg />", encoding="utf-8")
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
            bot=SimpleNamespace(send_message=send_message),
            bot_data={
                SEARCH_SERVICE_KEY: search_service,
                ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
                GET_DOWNLOAD_STATUS_SERVICE_KEY: status_service,
                IMPORT_TO_LIBRARY_SERVICE_KEY: import_service,
                TELEGRAM_SEND_MEDIA_FUNC_KEY: send_media,
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

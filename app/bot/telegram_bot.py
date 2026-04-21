from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from functools import partial
from pathlib import Path

from telegram import Update
from telegram.ext import Application, ContextTypes

from app.bot.bt_classification_runtime import (
    BT_CLASSIFICATION_CANCELLED_TEXT,
    BT_CLASSIFICATION_PENDING_REMINDER_TEXT,
    BT_CLASSIFICATION_PROMPT_TEXT,
)
from app.bot.bt_processing_path_runtime import (
    BT_PROCESSING_PATH_CANCELLED_TEXT,
    BT_PROCESSING_PATH_PENDING_REMINDER_TEXT,
    BT_PROCESSING_PATH_PROMPT_TEXT,
)
from app.bot.bt_tmdb_association_runtime import (
    BT_TMDB_ASSOCIATION_CANCELLED_TEXT,
    BT_TMDB_ASSOCIATION_SERVICE_NOT_READY_TEXT,
    BT_CLASSIFICATION_LABELS,
    enter_media_import_bt_flow as enter_shared_media_import_bt_flow,
    format_bt_tmdb_association_pending_reminder as _format_bt_tmdb_association_pending_reminder,
)
from app.bot.telegram_bt_pending_runtime import (
    clear_bt_classification_pending as clear_shared_telegram_bt_classification_pending,
    clear_bt_processing_path_pending as clear_shared_telegram_bt_processing_path_pending,
    clear_bt_tmdb_association_pending as clear_shared_telegram_bt_tmdb_association_pending,
    clear_raw_bt_destination_pending as clear_shared_telegram_raw_bt_destination_pending,
    get_bt_tmdb_association_pending as get_shared_telegram_bt_tmdb_association_pending,
    get_raw_bt_destination_pending as get_shared_telegram_raw_bt_destination_pending,
    is_bt_classification_pending as is_shared_telegram_bt_classification_pending,
    is_bt_processing_path_pending as is_shared_telegram_bt_processing_path_pending,
    pop_bt_classification_pending as pop_shared_telegram_bt_classification_pending,
    pop_bt_processing_path_pending as pop_shared_telegram_bt_processing_path_pending,
    set_bt_classification_pending as set_shared_telegram_bt_classification_pending,
    set_bt_processing_path_pending as set_shared_telegram_bt_processing_path_pending,
    set_bt_tmdb_association_pending as set_shared_telegram_bt_tmdb_association_pending,
    set_raw_bt_destination_pending as set_shared_telegram_raw_bt_destination_pending,
)
from app.bot.raw_bt_destination_runtime import (
    PURE_BT_CANDIDATE_SELECTED_TEMPLATE,
    RAW_BT_DESTINATION_CANCELLED_TEXT,
    RAW_BT_DESTINATION_SERVICE_NOT_READY_TEXT,
    enter_pure_bt_flow as enter_shared_pure_bt_flow,
)
from app.bot.personal_wechat_login import (
    PERSONAL_WECHAT_LOGIN_SERVICE_KEY,
    PersonalWeChatLoginService,
    parse_personal_wechat_login_query,
)
from app.bot.telegram_delivery_runtime import (
    build_telegram_send_media_func as _shared_build_telegram_send_media_func,
    build_telegram_send_text_func as _shared_build_telegram_send_text_func,
)
from app.bot.telegram_reply_formatter import format_telegram_reply as _shared_format_telegram_reply
from app.bot.download_follow_up_runtime import (
    download_completion_polling_loop,
    poll_pending_download_completion_once,
    post_download_auto_import_scheduler_loop,
)
from app.bot.telegram_sidecar_runtime import _log_bt_subscription_scheduler_config_error, _run_bt_subscription_scheduler_tick_once
from app.config import DownloaderInstanceConfig, DownloaderRoleBinding, RawBtDestinationOption
from app.clients.tmdb import TmdbMovie
from app.db.bt_pending_repo import (
    BtPendingRepo,
)
from app.db.download_monitor_repo import DownloadMonitorRepo
from app.db.job_repo import JobRepo, WORKFLOW_ADD_TO_DOWNLOADER, WORKFLOW_IMPORT_TO_LIBRARY
from app.db.telegram_update_repo import TelegramUpdateRepo
from app.runtime.execution_policy import (
    ACTION_BT_READ_ONLY_HELPER,
    ACTION_ADD_TO_DOWNLOADER,
    ACTION_CANCEL_PENDING_APPROVAL,
    ACTION_CLEANUP_INSPECT,
    ACTION_PERSONAL_WECHAT_LOGIN,
    ACTION_CONFIRM_ADD_TO_DOWNLOADER,
    ACTION_CLEANUP_DOWNLOADER_SOURCE,
    ACTION_CONFIRM_IMPORT_TO_LIBRARY,
    ACTION_GET_DOWNLOAD_STATUS,
    ACTION_IMPORT_TO_LIBRARY,
    ACTION_RESET_CANDIDATES,
    ACTION_RESET_CLARIFICATION,
    ACTION_SEARCH_MEDIA,
)
from app.services.add_to_downloader import (
    ADD_CANCELLED_TEXT,
    AddToDownloaderService,
)
from app.services.cleanup_downloaded_source import (
    CleanupDownloadedSourceService,
    parse_cleanup_inspect_query,
    parse_cleanup_query,
)
from app.services.get_download_status import GetDownloadStatusService, parse_status_query
from app.services.manage_bt_subscription import ManageBtSubscriptionService, parse_bt_subscription_query
from app.services.import_to_library import (
    IMPORT_CANCELLED_TEXT,
    ImportToLibraryService,
    parse_confirm_query,
    parse_import_query,
)
from app.services.manage_watchlist import ManageWatchlistService, parse_watchlist_query
from app.services.post_download_auto_import import PostDownloadAutoImportService
from app.services.search_media import SearchMediaService

FRUSTRATION_RESET_TEXT = "已清除当前候选，请重新搜索。"
CLARIFICATION_RESET_TEXT = "已取消当前澄清，请重新描述片名后搜索。"
CLARIFICATION_SELECTION_BLOCKED_TEXT = "当前处于片名澄清中，请先补充片名或年份后再搜索。"
BT_CLASSIFICATION_RESULT_TEXT_TEMPLATE = (
    "已记录本次 BT 媒体类型：{label}（{kind}）。\n"
    "当前这一步只完成媒体类型 follow-up，暂不执行 TMDB 关联或下载投递。"
)
DOWNLOADER_EXECUTION_CONFIG_MISSING_TEMPLATE = "下载器角色 {role} 绑定的实例不存在：{name}。请检查配置后重试。"
BT_SOURCE_REQUIRED_TEXT = "当前还缺少实际的磁力链接，请直接发送 magnet:? 链接后重试。"
PURE_BT_CANDIDATE_NOT_FOUND_TEMPLATE = (
    "当前没有找到可用于 pure BT 下载链的单片候选：{query}\n"
    "请补充更具体的标题/编号后重试，或直接发送 magnet:? 链接。"
)
PURE_BT_SEARCH_FAILED_TEXT = "pure BT 搜索暂不可用，请稍后重试。"
BT_READ_ONLY_HELPER_FAILED_TEXT = "BT 只读探索暂不可用，请稍后重试。"
SERVICE_NOT_READY_TEXT = "服务未就绪，请稍后重试。"
LLM_PHYSICAL_FAILURE_SAFE_TEXT = "请求过长或响应被截断，系统已自动重试一次。请简化描述后重试。"
SEARCH_SERVICE_KEY = "search_media_service"
ADD_TO_DOWNLOADER_SERVICE_KEY = "add_to_downloader_service"
GET_DOWNLOAD_STATUS_SERVICE_KEY = "get_download_status_service"
IMPORT_TO_LIBRARY_SERVICE_KEY = "import_to_library_service"
CLEANUP_DOWNLOADED_SOURCE_SERVICE_KEY = "cleanup_downloaded_source_service"
MANAGE_WATCHLIST_SERVICE_KEY = "manage_watchlist_service"
MANAGE_BT_SUBSCRIPTION_SERVICE_KEY = "manage_bt_subscription_service"
JOB_REPO_KEY = "job_repo"
TELEGRAM_UPDATE_REPO_KEY = "telegram_update_repo"
EXECUTION_GATE_KEY = "execution_gate"
BT_PENDING_REPO_KEY = "bt_pending_repo"
BT_TMDB_MOVIE_CANDIDATES_LOOKUP_KEY = "bt_tmdb_movie_candidates_lookup_func"
BT_TMDB_TV_CANDIDATES_LOOKUP_KEY = "bt_tmdb_tv_candidates_lookup_func"
RAW_BT_DESTINATION_OPTIONS_KEY = "raw_bt_destination_options"
DOWNLOADER_INSTANCES_KEY = "downloader_instances"
DOWNLOADER_ROLE_BINDING_KEY = "downloader_role_binding"
BT_SUBSCRIPTION_SCHEDULER_TASK_KEY = "bt_subscription_scheduler_task"
BT_SUBSCRIPTION_SCHEDULER_STOP_EVENT_KEY = "bt_subscription_scheduler_stop_event"
POST_DOWNLOAD_AUTO_IMPORT_TASK_KEY = "post_download_auto_import_task"
POST_DOWNLOAD_AUTO_IMPORT_STOP_EVENT_KEY = "post_download_auto_import_stop_event"
DOWNLOAD_COMPLETION_POLLING_TASK_KEY = "download_completion_polling_task"
DOWNLOAD_COMPLETION_POLLING_STOP_EVENT_KEY = "download_completion_polling_stop_event"
FEISHU_WEBHOOK_SERVER_CONFIG_KEY = "feishu_webhook_server_config"
FEISHU_WEBHOOK_REPLY_TEXT_FUNC_KEY = "feishu_webhook_reply_text_func"
FEISHU_WEBHOOK_SERVER_RUNTIME_KEY = "feishu_webhook_server_runtime"
WECOM_WEBHOOK_SERVER_CONFIG_KEY = "wecom_webhook_server_config"
WECOM_WEBHOOK_SERVER_RUNTIME_KEY = "wecom_webhook_server_runtime"
TELEGRAM_SEND_MEDIA_FUNC_KEY = "telegram_send_media_func"
TELEGRAM_SEND_TEXT_FUNC_KEY = "telegram_send_text_func"
POST_DOWNLOAD_AUTO_IMPORT_SERVICE_KEY = "post_download_auto_import_service"
POST_DOWNLOAD_AUTO_IMPORT_INTERVAL_SECONDS = 300.0
LookupTmdbCandidatesFunc = Callable[[str, str], Awaitable[list[TmdbMovie]]]
TelegramSendMediaFunc = Callable[[int, str | Path, str | None], Awaitable[object]]
TelegramSendTextFunc = Callable[..., Awaitable[object]]
_set_bt_processing_path_pending = partial(
    set_shared_telegram_bt_processing_path_pending,
    bt_pending_repo_key=BT_PENDING_REPO_KEY,
)
_is_bt_processing_path_pending = partial(
    is_shared_telegram_bt_processing_path_pending,
    bt_pending_repo_key=BT_PENDING_REPO_KEY,
)
_clear_bt_processing_path_pending = partial(
    clear_shared_telegram_bt_processing_path_pending,
    bt_pending_repo_key=BT_PENDING_REPO_KEY,
)
_pop_bt_processing_path_pending = partial(
    pop_shared_telegram_bt_processing_path_pending,
    bt_pending_repo_key=BT_PENDING_REPO_KEY,
)
_set_bt_classification_pending = partial(
    set_shared_telegram_bt_classification_pending,
    bt_pending_repo_key=BT_PENDING_REPO_KEY,
)
_is_bt_classification_pending = partial(
    is_shared_telegram_bt_classification_pending,
    bt_pending_repo_key=BT_PENDING_REPO_KEY,
)
_clear_bt_classification_pending = partial(
    clear_shared_telegram_bt_classification_pending,
    bt_pending_repo_key=BT_PENDING_REPO_KEY,
)
_pop_bt_classification_pending = partial(
    pop_shared_telegram_bt_classification_pending,
    bt_pending_repo_key=BT_PENDING_REPO_KEY,
)
_set_bt_tmdb_association_pending = partial(
    set_shared_telegram_bt_tmdb_association_pending,
    bt_pending_repo_key=BT_PENDING_REPO_KEY,
)
_get_bt_tmdb_association_pending = partial(
    get_shared_telegram_bt_tmdb_association_pending,
    bt_pending_repo_key=BT_PENDING_REPO_KEY,
)
_clear_bt_tmdb_association_pending = partial(
    clear_shared_telegram_bt_tmdb_association_pending,
    bt_pending_repo_key=BT_PENDING_REPO_KEY,
)
_set_raw_bt_destination_pending = partial(
    set_shared_telegram_raw_bt_destination_pending,
    bt_pending_repo_key=BT_PENDING_REPO_KEY,
)
_get_raw_bt_destination_pending = partial(
    get_shared_telegram_raw_bt_destination_pending,
    bt_pending_repo_key=BT_PENDING_REPO_KEY,
)
_clear_raw_bt_destination_pending = partial(
    clear_shared_telegram_raw_bt_destination_pending,
    bt_pending_repo_key=BT_PENDING_REPO_KEY,
)
BT_CLASSIFICATION_LABELS["raw_bt"] = "其他 BT 资源"

# Compatibility re-exports for existing tests and narrow module consumers.
_COMPAT_REEXPORTS = (
    BT_CLASSIFICATION_CANCELLED_TEXT,
    BT_CLASSIFICATION_PENDING_REMINDER_TEXT,
    BT_PROCESSING_PATH_CANCELLED_TEXT,
    BT_PROCESSING_PATH_PENDING_REMINDER_TEXT,
    BT_PROCESSING_PATH_PROMPT_TEXT,
    BT_TMDB_ASSOCIATION_CANCELLED_TEXT,
    _format_bt_tmdb_association_pending_reminder,
    RAW_BT_DESTINATION_CANCELLED_TEXT,
    parse_personal_wechat_login_query,
    WORKFLOW_ADD_TO_DOWNLOADER,
    WORKFLOW_IMPORT_TO_LIBRARY,
    ACTION_BT_READ_ONLY_HELPER,
    ACTION_ADD_TO_DOWNLOADER,
    ACTION_CANCEL_PENDING_APPROVAL,
    ACTION_CLEANUP_INSPECT,
    ACTION_PERSONAL_WECHAT_LOGIN,
    ACTION_CONFIRM_ADD_TO_DOWNLOADER,
    ACTION_CLEANUP_DOWNLOADER_SOURCE,
    ACTION_CONFIRM_IMPORT_TO_LIBRARY,
    ACTION_GET_DOWNLOAD_STATUS,
    ACTION_IMPORT_TO_LIBRARY,
    ACTION_RESET_CANDIDATES,
    ACTION_RESET_CLARIFICATION,
    ACTION_SEARCH_MEDIA,
    ADD_CANCELLED_TEXT,
    parse_cleanup_inspect_query,
    parse_cleanup_query,
    parse_status_query,
    parse_bt_subscription_query,
    IMPORT_CANCELLED_TEXT,
    parse_confirm_query,
    parse_import_query,
    parse_watchlist_query,
)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from app.bot.telegram_runtime_adapter import handle_telegram_message

    await handle_telegram_message(update, context)


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from app.bot.telegram_runtime_adapter import handle_telegram_callback_query

    await handle_telegram_callback_query(update, context)


def build_application(
    token: str,
    search_service: SearchMediaService,
    add_to_downloader_service: AddToDownloaderService,
    get_download_status_service: GetDownloadStatusService,
    import_to_library_service: ImportToLibraryService,
    cleanup_downloaded_source_service: CleanupDownloadedSourceService,
    manage_watchlist_service: ManageWatchlistService,
    manage_bt_subscription_service: ManageBtSubscriptionService,
    post_download_auto_import_service: PostDownloadAutoImportService | None = None,
    telegram_update_repo: TelegramUpdateRepo | None = None,
    job_repo: JobRepo | None = None,
    execution_gate: ExecutionGate | None = None,
    bt_pending_repo: BtPendingRepo | None = None,
    bt_tmdb_movie_candidates_lookup_func: LookupTmdbCandidatesFunc | None = None,
    bt_tmdb_tv_candidates_lookup_func: LookupTmdbCandidatesFunc | None = None,
    raw_bt_destination_options: tuple[RawBtDestinationOption, ...] = (),
    downloader_instances: tuple[DownloaderInstanceConfig, ...] = (),
    downloader_role_binding: DownloaderRoleBinding | None = None,
    outbound_proxy_url: str = "",
) -> Application:
    from app.bot.telegram_runtime_adapter import build_telegram_application

    return build_telegram_application(
        token=token,
        search_service=search_service,
        add_to_downloader_service=add_to_downloader_service,
        get_download_status_service=get_download_status_service,
        import_to_library_service=import_to_library_service,
        cleanup_downloaded_source_service=cleanup_downloaded_source_service,
        manage_watchlist_service=manage_watchlist_service,
        manage_bt_subscription_service=manage_bt_subscription_service,
        post_download_auto_import_service=post_download_auto_import_service,
        telegram_update_repo=telegram_update_repo,
        job_repo=job_repo,
        execution_gate=execution_gate,
        bt_pending_repo=bt_pending_repo,
        bt_tmdb_movie_candidates_lookup_func=bt_tmdb_movie_candidates_lookup_func,
        bt_tmdb_tv_candidates_lookup_func=bt_tmdb_tv_candidates_lookup_func,
        raw_bt_destination_options=raw_bt_destination_options,
        downloader_instances=downloader_instances,
        downloader_role_binding=downloader_role_binding,
        outbound_proxy_url=outbound_proxy_url,
    )


def build_telegram_send_media_func(application: Application) -> TelegramSendMediaFunc:
    return _shared_build_telegram_send_media_func(application)


def build_telegram_send_text_func(application: Application) -> TelegramSendTextFunc:
    return _shared_build_telegram_send_text_func(application)

async def _post_download_auto_import_scheduler_loop(
    *,
    service: PostDownloadAutoImportService,
    stop_event: asyncio.Event,
) -> None:
    await post_download_auto_import_scheduler_loop(
        service=service,
        stop_event=stop_event,
        interval_seconds=POST_DOWNLOAD_AUTO_IMPORT_INTERVAL_SECONDS,
    )


async def _poll_pending_download_completion_once(
    *, download_monitor_repo: DownloadMonitorRepo, status_service: GetDownloadStatusService
) -> None:
    await poll_pending_download_completion_once(
        download_monitor_repo=download_monitor_repo,
        status_service=status_service,
    )


async def _download_completion_polling_loop(
    *, download_monitor_repo: DownloadMonitorRepo, status_service: GetDownloadStatusService, stop_event: asyncio.Event
) -> None:
    await download_completion_polling_loop(
        download_monitor_repo=download_monitor_repo,
        status_service=status_service,
        stop_event=stop_event,
        interval_seconds=POST_DOWNLOAD_AUTO_IMPORT_INTERVAL_SECONDS,
    )


def _format_bt_classification_result(media_kind: str) -> str:
    label = BT_CLASSIFICATION_LABELS.get(media_kind, BT_CLASSIFICATION_LABELS["raw_bt"])
    return BT_CLASSIFICATION_RESULT_TEXT_TEMPLATE.format(label=label, kind=media_kind)


def _enter_pure_bt_flow(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
    source: str,
) -> str:
    return enter_shared_pure_bt_flow(
        bot_data=context.application.bot_data,
        chat_id=chat_id,
        source=source,
        raw_bt_destination_options_key=RAW_BT_DESTINATION_OPTIONS_KEY,
        bt_pending_repo_key=BT_PENDING_REPO_KEY,
        raw_bt_destination_service_not_ready_text=RAW_BT_DESTINATION_SERVICE_NOT_READY_TEXT,
        service_not_ready_text=SERVICE_NOT_READY_TEXT,
    )


def _enter_media_import_bt_flow(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
    source: str,
    media_kind: str | None = None,
) -> str:
    return enter_shared_media_import_bt_flow(
        bot_data=context.application.bot_data,
        chat_id=chat_id,
        source=source,
        media_kind=media_kind,
        bt_pending_repo_key=BT_PENDING_REPO_KEY,
        service_not_ready_text=SERVICE_NOT_READY_TEXT,
        bt_classification_prompt_text=BT_CLASSIFICATION_PROMPT_TEXT,
    )


async def handle_private_chat_query_text(
    *,
    query: str,
    reply_func: Callable[[str], Awaitable[object]],
    chat_id: int | None,
    user_id: int | None,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    from app.bot.private_chat_runtime import handle_private_chat_query_text as shared_handle_private_chat_query_text

    await shared_handle_private_chat_query_text(
        query=query,
        reply_func=reply_func,
        chat_id=chat_id,
        user_id=user_id,
        channel="telegram",
        bot_data=context.application.bot_data,
    )


def _format_telegram_reply(text: str) -> str:
    return _shared_format_telegram_reply(text)

from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Literal

from telegram import Update
from telegram.ext import Application, ContextTypes

from app.bot.bt_classification_runtime import (
    BT_CLASSIFICATION_CANCELLED_TEXT,
    BT_CLASSIFICATION_PENDING_REMINDER_TEXT,
    BT_CLASSIFICATION_PROMPT_TEXT,
    clear_bt_classification_pending as clear_shared_bt_classification_pending,
    is_bt_classification_pending as is_shared_bt_classification_pending,
    pop_bt_classification_pending as pop_shared_bt_classification_pending,
    set_bt_classification_pending as set_shared_bt_classification_pending,
)
from app.bot.bt_processing_path_runtime import (
    BT_PROCESSING_PATH_CANCELLED_TEXT,
    BT_PROCESSING_PATH_PENDING_REMINDER_TEXT,
    BT_PROCESSING_PATH_PROMPT_TEXT,
    clear_bt_processing_path_pending as clear_shared_bt_processing_path_pending,
    is_bt_processing_path_pending as is_shared_bt_processing_path_pending,
    pop_bt_processing_path_pending as pop_shared_bt_processing_path_pending,
    set_bt_processing_path_pending as set_shared_bt_processing_path_pending,
)
from app.bot.bt_tmdb_association_runtime import (
    BT_TMDB_ASSOCIATION_CANCELLED_TEXT,
    BT_TMDB_ASSOCIATION_SERVICE_NOT_READY_TEXT,
    BT_CLASSIFICATION_LABELS,
    BtTmdbAssociationPending,
    clear_bt_tmdb_association_pending as clear_shared_bt_tmdb_association_pending,
    enter_media_import_bt_flow as enter_shared_media_import_bt_flow,
    format_bt_tmdb_association_pending_reminder as _format_bt_tmdb_association_pending_reminder,
    get_bt_tmdb_association_pending as get_shared_bt_tmdb_association_pending,
    handle_bt_tmdb_association_query as handle_shared_bt_tmdb_association_query,
    log_bt_tmdb_association_error as log_shared_bt_tmdb_association_error,
    resolve_bt_tmdb_candidates_lookup as resolve_shared_bt_tmdb_candidates_lookup,
    set_bt_tmdb_association_pending as set_shared_bt_tmdb_association_pending,
)
from app.bot.downloader_execution_runtime import (
    ResolvedDownloaderExecution,
    resolve_bound_downloader_execution as resolve_shared_bound_downloader_execution,
    resolve_downloader_instances as resolve_shared_downloader_instances,
)
from app.bot.execution_runtime import resolve_execution_gate
from app.bot.raw_bt_destination_runtime import (
    PURE_BT_CANDIDATE_SELECTED_TEMPLATE,
    RAW_BT_DESTINATION_CANCELLED_TEXT,
    RAW_BT_DESTINATION_SERVICE_NOT_READY_TEXT,
    RawBtDestinationPending,
    clear_raw_bt_destination_pending as clear_shared_raw_bt_destination_pending,
    enter_pure_bt_flow as enter_shared_pure_bt_flow,
    get_raw_bt_destination_pending as get_shared_raw_bt_destination_pending,
    handle_raw_bt_destination_query as handle_shared_raw_bt_destination_query,
    log_pure_bt_search_error as log_shared_pure_bt_search_error,
    set_raw_bt_destination_pending as set_shared_raw_bt_destination_pending,
)
from app.bot.personal_wechat_login import (
    PERSONAL_WECHAT_LOGIN_SERVICE_KEY,
    PersonalWeChatLoginService,
    parse_personal_wechat_login_query,
)
from app.bot.download_follow_up_runtime import (
    download_completion_polling_loop,
    poll_pending_download_completion_once,
    post_download_auto_import_scheduler_loop,
)
from app.bot.telegram_sidecar_runtime import (
    TelegramSidecarRuntimeConfig,
)
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
    ACTION_BT_SUBSCRIPTION_RUN,
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
    ExecutionGate,
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
from app.services.manage_bt_subscription import (
    BtSubscriptionDispatchContext,
    ManageBtSubscriptionService,
    parse_bt_subscription_query,
)
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
TELEGRAM_MOVIE_CARD_HEADER_TEXT = "电影海报卡片"
TELEGRAM_SEARCH_RESULT_PREFIX = "搜索结果："
TELEGRAM_ADD_APPROVAL_PREFIX = "下载待确认："
TELEGRAM_ADD_APPROVAL_TASK_REF_PREFIX = "选择序号:"
TELEGRAM_IMPORT_APPROVAL_PREFIX = "导入待确认："
TELEGRAM_IMPORT_APPROVAL_TASK_ID_PREFIX = "任务 ID:"
TELEGRAM_IMPORT_APPROVAL_TASK_HASH_PREFIX = "任务 Hash:"
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
BT_SUBSCRIPTION_SCHEDULER_INTERVAL_SECONDS = 300.0
POST_DOWNLOAD_AUTO_IMPORT_INTERVAL_SECONDS = 300.0
TELEGRAM_SIDECAR_RUNTIME_CONFIG = TelegramSidecarRuntimeConfig(
    post_download_auto_import_service_key=POST_DOWNLOAD_AUTO_IMPORT_SERVICE_KEY,
    post_download_auto_import_stop_event_key=POST_DOWNLOAD_AUTO_IMPORT_STOP_EVENT_KEY,
    post_download_auto_import_task_key=POST_DOWNLOAD_AUTO_IMPORT_TASK_KEY,
    get_download_status_service_key=GET_DOWNLOAD_STATUS_SERVICE_KEY,
    download_completion_polling_stop_event_key=DOWNLOAD_COMPLETION_POLLING_STOP_EVENT_KEY,
    download_completion_polling_task_key=DOWNLOAD_COMPLETION_POLLING_TASK_KEY,
    feishu_webhook_server_config_key=FEISHU_WEBHOOK_SERVER_CONFIG_KEY,
    feishu_webhook_reply_text_func_key=FEISHU_WEBHOOK_REPLY_TEXT_FUNC_KEY,
    feishu_webhook_server_runtime_key=FEISHU_WEBHOOK_SERVER_RUNTIME_KEY,
    wecom_webhook_server_config_key=WECOM_WEBHOOK_SERVER_CONFIG_KEY,
    wecom_webhook_server_runtime_key=WECOM_WEBHOOK_SERVER_RUNTIME_KEY,
    personal_wechat_login_service_key=PERSONAL_WECHAT_LOGIN_SERVICE_KEY,
    post_download_auto_import_interval_seconds=POST_DOWNLOAD_AUTO_IMPORT_INTERVAL_SECONDS,
)
TELEGRAM_PHOTO_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif"})
LookupTmdbCandidatesFunc = Callable[[str, str], Awaitable[list[TmdbMovie]]]
TelegramSendMediaFunc = Callable[[int, str | Path, str | None], Awaitable[object]]
TelegramSendTextFunc = Callable[..., Awaitable[object]]
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
    async def send_media(chat_id: int, file_path: str | Path, caption: str | None = None) -> object:
        return await _send_telegram_media(
            application=application,
            chat_id=chat_id,
            file_path=Path(file_path).expanduser(),
            caption=caption,
        )

    return send_media


def build_telegram_send_text_func(application: Application) -> TelegramSendTextFunc:
    async def send_text(*, chat_id: int, text: str) -> object:
        return await application.bot.send_message(chat_id=chat_id, text=text)

    return send_text


async def _send_telegram_media(
    *,
    application: Application,
    chat_id: int,
    file_path: Path,
    caption: str | None,
) -> object:
    if not file_path.is_file():
        print(
            f"\033[31m[Telegram 媒资发送失败]\033[0m chat_id={chat_id} 文件不存在={file_path}\n"
            "\033[33m[处理建议]\033[0m 检查二维码/文件是否已生成到本地路径，并确认当前进程对该路径有读取权限。"
        )
        raise FileNotFoundError(str(file_path))

    try:
        if _is_telegram_photo_path(file_path):
            return await application.bot.send_photo(
                chat_id=chat_id,
                photo=file_path,
                caption=caption,
            )
        return await application.bot.send_document(
            chat_id=chat_id,
            document=file_path,
            caption=caption,
            filename=file_path.name,
        )
    except Exception as error:
        print(
            f"\033[31m[Telegram 媒资发送失败]\033[0m chat_id={chat_id} 文件={file_path} 原因={error}\n"
            "\033[33m[处理建议]\033[0m 检查 Telegram chat_id 是否仍有效、Bot 是否具备发送媒资权限，以及本地文件是否可被 Telegram API 正常读取。"
        )
        raise


def _is_telegram_photo_path(file_path: Path) -> bool:
    return file_path.suffix.lower() in TELEGRAM_PHOTO_SUFFIXES

def _resolve_execution_gate_for_application(application: Application) -> ExecutionGate:
    return resolve_execution_gate(
        bot_data=application.bot_data,
        execution_gate_key=EXECUTION_GATE_KEY,
    )


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


async def _bt_subscription_scheduler_loop(
    *,
    application: Application,
    bt_subscription_service: ManageBtSubscriptionService,
    execution_gate: ExecutionGate,
    stop_event: asyncio.Event,
    dispatch_context: BtSubscriptionDispatchContext,
) -> None:
    while not stop_event.is_set():
        try:
            await _run_bt_subscription_scheduler_tick_once(
                application=application,
                bt_subscription_service=bt_subscription_service,
                execution_gate=execution_gate,
                dispatch_context=dispatch_context,
            )
        except Exception as error:
            _log_bt_subscription_scheduler_loop_error(error=error)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=BT_SUBSCRIPTION_SCHEDULER_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            continue


async def _run_bt_subscription_scheduler_tick_once(
    *,
    application: Application,
    bt_subscription_service: ManageBtSubscriptionService,
    execution_gate: ExecutionGate,
    dispatch_context: BtSubscriptionDispatchContext,
) -> None:
    notifications = await execution_gate.run(
        ACTION_BT_SUBSCRIPTION_RUN,
        lambda: bt_subscription_service.run_scheduler_tick(
            dispatch_context=dispatch_context,
        ),
    )
    if notifications is None:
        _log_bt_subscription_scheduler_result_unavailable()
        return
    for chat_id, reply_text in notifications:
        await _send_bt_subscription_scheduler_message(
            application=application,
            chat_id=chat_id,
            text=reply_text,
        )


async def _send_bt_subscription_scheduler_message(
    *,
    application: Application,
    chat_id: int,
    text: str,
) -> None:
    try:
        await application.bot.send_message(chat_id=chat_id, text=text)
    except Exception as error:
        _log_bt_subscription_scheduler_send_error(chat_id=chat_id, error=error)


def _set_bt_processing_path_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
    source: str,
) -> bool:
    return set_shared_bt_processing_path_pending(
        bot_data=context.application.bot_data,
        chat_id=chat_id,
        source=source,
        bt_pending_repo_key=BT_PENDING_REPO_KEY,
    )


def _is_bt_processing_path_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
) -> bool | None:
    return is_shared_bt_processing_path_pending(
        bot_data=context.application.bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=BT_PENDING_REPO_KEY,
    )


def _clear_bt_processing_path_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
) -> bool | None:
    return clear_shared_bt_processing_path_pending(
        bot_data=context.application.bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=BT_PENDING_REPO_KEY,
    )


def _pop_bt_processing_path_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
) -> str | Literal[False] | None:
    return pop_shared_bt_processing_path_pending(
        bot_data=context.application.bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=BT_PENDING_REPO_KEY,
    )


def _set_bt_classification_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
    query: str,
) -> bool:
    return set_shared_bt_classification_pending(
        bot_data=context.application.bot_data,
        chat_id=chat_id,
        query=query,
        bt_pending_repo_key=BT_PENDING_REPO_KEY,
    )


def _is_bt_classification_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
) -> bool | None:
    return is_shared_bt_classification_pending(
        bot_data=context.application.bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=BT_PENDING_REPO_KEY,
    )


def _clear_bt_classification_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
) -> bool | None:
    return clear_shared_bt_classification_pending(
        bot_data=context.application.bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=BT_PENDING_REPO_KEY,
    )


def _pop_bt_classification_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
) -> str | Literal[False] | None:
    return pop_shared_bt_classification_pending(
        bot_data=context.application.bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=BT_PENDING_REPO_KEY,
    )


def _set_bt_tmdb_association_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
    media_kind: str,
    source: str,
) -> bool:
    return set_shared_bt_tmdb_association_pending(
        bot_data=context.application.bot_data,
        chat_id=chat_id,
        media_kind=media_kind,
        source=source,
        bt_pending_repo_key=BT_PENDING_REPO_KEY,
    )


def _get_bt_tmdb_association_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
) -> BtTmdbAssociationPending | None | Literal[False]:
    return get_shared_bt_tmdb_association_pending(
        bot_data=context.application.bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=BT_PENDING_REPO_KEY,
    )


def _clear_bt_tmdb_association_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
) -> bool | None:
    return clear_shared_bt_tmdb_association_pending(
        bot_data=context.application.bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=BT_PENDING_REPO_KEY,
    )


def _set_raw_bt_destination_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
    options: tuple[RawBtDestinationOption, ...],
    source: str,
) -> bool:
    return set_shared_raw_bt_destination_pending(
        bot_data=context.application.bot_data,
        chat_id=chat_id,
        options=options,
        source=source,
        bt_pending_repo_key=BT_PENDING_REPO_KEY,
    )


def _get_raw_bt_destination_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
) -> RawBtDestinationPending | None | Literal[False]:
    return get_shared_raw_bt_destination_pending(
        bot_data=context.application.bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=BT_PENDING_REPO_KEY,
    )


def _clear_raw_bt_destination_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
) -> bool | None:
    return clear_shared_raw_bt_destination_pending(
        bot_data=context.application.bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=BT_PENDING_REPO_KEY,
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


def _resolve_bt_tmdb_candidates_lookup(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    media_kind: str,
) -> LookupTmdbCandidatesFunc | None:
    return resolve_shared_bt_tmdb_candidates_lookup(
        bot_data=context.application.bot_data,
        media_kind=media_kind,
        bt_tmdb_movie_candidates_lookup_key=BT_TMDB_MOVIE_CANDIDATES_LOOKUP_KEY,
        bt_tmdb_tv_candidates_lookup_key=BT_TMDB_TV_CANDIDATES_LOOKUP_KEY,
    )


def _resolve_downloader_instances(
    context: ContextTypes.DEFAULT_TYPE,
) -> dict[str, DownloaderInstanceConfig]:
    return resolve_shared_downloader_instances(
        bot_data=context.application.bot_data,
        downloader_instances_key=DOWNLOADER_INSTANCES_KEY,
    )


def _resolve_bound_downloader_execution(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    role: str,
) -> tuple[ResolvedDownloaderExecution | None, str | None]:
    return resolve_shared_bound_downloader_execution(
        bot_data=context.application.bot_data,
        role=role,
        downloader_role_binding_key=DOWNLOADER_ROLE_BINDING_KEY,
        downloader_instances_key=DOWNLOADER_INSTANCES_KEY,
        config_missing_template=DOWNLOADER_EXECUTION_CONFIG_MISSING_TEMPLATE,
    )


def _resolve_bound_downloader_execution_for_application(
    *,
    application: Application,
    role: str,
) -> tuple[ResolvedDownloaderExecution | None, str | None]:
    return resolve_shared_bound_downloader_execution(
        bot_data=application.bot_data,
        role=role,
        downloader_role_binding_key=DOWNLOADER_ROLE_BINDING_KEY,
        downloader_instances_key=DOWNLOADER_INSTANCES_KEY,
        config_missing_template=DOWNLOADER_EXECUTION_CONFIG_MISSING_TEMPLATE,
    )


def _resolve_downloader_instances_for_application(
    application: Application,
) -> dict[str, DownloaderInstanceConfig]:
    return resolve_shared_downloader_instances(
        bot_data=application.bot_data,
        downloader_instances_key=DOWNLOADER_INSTANCES_KEY,
    )


async def _handle_raw_bt_destination_query(
    *,
    query: str,
    pending: RawBtDestinationPending,
    chat_id: int | None,
    user_id: int | None,
    context: ContextTypes.DEFAULT_TYPE,
) -> str:
    return await handle_shared_raw_bt_destination_query(
        query=query,
        pending=pending,
        chat_id=chat_id,
        user_id=user_id,
        bot_data=context.application.bot_data,
        add_to_downloader_service_key=ADD_TO_DOWNLOADER_SERVICE_KEY,
        search_service_key=SEARCH_SERVICE_KEY,
        clear_pending=lambda: _clear_raw_bt_destination_pending(context=context, chat_id=chat_id),
        resolve_downloader_execution=lambda: _resolve_bound_downloader_execution(context=context, role="bt"),
        log_pure_bt_search_error=lambda bt_query, error: _log_pure_bt_search_error(query=bt_query, error=error),
        service_not_ready_text=SERVICE_NOT_READY_TEXT,
        bt_source_required_text=BT_SOURCE_REQUIRED_TEXT,
        pure_bt_search_failed_text=PURE_BT_SEARCH_FAILED_TEXT,
        pure_bt_candidate_selected_template=PURE_BT_CANDIDATE_SELECTED_TEMPLATE,
        pure_bt_candidate_not_found_template=PURE_BT_CANDIDATE_NOT_FOUND_TEMPLATE,
    )


def _log_bt_tmdb_association_error(*, media_kind: str, query: str, error: Exception) -> None:
    log_shared_bt_tmdb_association_error(media_kind=media_kind, query=query, error=error)


def _log_pure_bt_search_error(*, query: str, error: Exception) -> None:
    log_shared_pure_bt_search_error(query=query, error=error)


def _log_bt_subscription_scheduler_config_error(*, reason: str) -> None:
    print(
        f"\033[31m[BT 订阅后台扫描未启动]\033[0m 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 BT 下载器角色绑定和下载器实例配置后重启应用。"
    )


def _log_bt_subscription_scheduler_loop_error(*, error: Exception) -> None:
    print(
        f"\033[31m[BT 订阅后台扫描失败]\033[0m 原因={error}\n"
        "\033[33m[处理建议]\033[0m 检查 Prowlarr、SQLite 和 Telegram 发送链路后等待下一轮自动扫描。"
    )


def _log_bt_subscription_scheduler_result_unavailable() -> None:
    print(
        "\033[31m[BT 订阅后台扫描结果不可用]\033[0m 本轮未生成可发送通知。\n"
        "\033[33m[处理建议]\033[0m 检查 Prowlarr、SQLite、approval_record/jobs 和前面的后台扫描明细日志；当前这轮通知已跳过，下一轮自动扫描仍会继续尝试。"
    )


def _log_bt_subscription_scheduler_send_error(*, chat_id: int, error: Exception) -> None:
    print(
        f"\033[31m[BT 订阅后台通知失败]\033[0m chat_id={chat_id} 原因={error}\n"
        "\033[33m[处理建议]\033[0m 检查 Telegram Bot Token、聊天可达性和网络连通性后等待下一轮自动扫描。"
    )


async def _handle_bt_tmdb_association_query(
    *,
    query: str,
    pending: BtTmdbAssociationPending,
    chat_id: int | None,
    user_id: int | None,
    context: ContextTypes.DEFAULT_TYPE,
) -> str:
    return await handle_shared_bt_tmdb_association_query(
        query=query,
        pending=pending,
        chat_id=chat_id,
        user_id=user_id,
        bot_data=context.application.bot_data,
        add_to_downloader_service_key=ADD_TO_DOWNLOADER_SERVICE_KEY,
        clear_pending=lambda: _clear_bt_tmdb_association_pending(context=context, chat_id=chat_id),
        resolve_candidates_lookup=lambda media_kind: _resolve_bt_tmdb_candidates_lookup(
            context=context,
            media_kind=media_kind,
        ),
        resolve_downloader_execution=lambda: _resolve_bound_downloader_execution(context=context, role="bt"),
        log_bt_tmdb_association_error=lambda media_kind, raw_query, error: _log_bt_tmdb_association_error(
            media_kind=media_kind,
            query=raw_query,
            error=error,
        ),
        service_not_ready_text=SERVICE_NOT_READY_TEXT,
        bt_tmdb_association_service_not_ready_text=BT_TMDB_ASSOCIATION_SERVICE_NOT_READY_TEXT,
        bt_source_required_text=BT_SOURCE_REQUIRED_TEXT,
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
    return _format_telegram_import_approval_reply(
        _format_telegram_add_approval_reply(_format_telegram_search_reply(text))
    )


def _format_telegram_search_reply(text: str) -> str:
    stripped_text = text.strip()
    if (
        not stripped_text
        or TELEGRAM_MOVIE_CARD_HEADER_TEXT not in stripped_text
        or TELEGRAM_SEARCH_RESULT_PREFIX not in stripped_text
    ):
        return text

    sections = re.split(r"\n\s*\n", stripped_text)
    card_section = next(
        (section for section in sections if section.startswith(TELEGRAM_MOVIE_CARD_HEADER_TEXT)),
        "",
    )
    result_section = next(
        (section for section in sections if section.startswith(TELEGRAM_SEARCH_RESULT_PREFIX)),
        "",
    )
    if not card_section or not result_section:
        return text

    card_lines = [line.strip() for line in card_section.splitlines() if line.strip()]
    result_lines = [line.strip() for line in result_section.splitlines() if line.strip()]
    if len(card_lines) < 2 or len(result_lines) < 2:
        return text

    query = result_lines[0].removeprefix(TELEGRAM_SEARCH_RESULT_PREFIX).strip()
    candidate_count = sum(1 for line in result_lines[1:] if re.match(r"^\d+\.\s", line))
    if candidate_count <= 0:
        return text

    formatted_lines = ["【电影卡片】", *card_lines[1:], "", f"【搜索结果】 {query}".rstrip()]
    formatted_lines.extend(result_lines[1:])
    formatted_lines.extend(("", _format_telegram_selection_hint(candidate_count)))
    return "\n".join(formatted_lines)


def _format_telegram_selection_hint(candidate_count: int) -> str:
    if candidate_count <= 1:
        return "直接回复 1 继续，例如：1"
    return f"直接回复 1-{candidate_count} 中的序号继续，例如：1"


def _format_telegram_add_approval_reply(text: str) -> str:
    stripped_text = text.strip()
    if not stripped_text.startswith(TELEGRAM_ADD_APPROVAL_PREFIX):
        return text

    lines = [line.strip() for line in stripped_text.splitlines() if line.strip()]
    if len(lines) < 3:
        return text

    title = lines[0].removeprefix(TELEGRAM_ADD_APPROVAL_PREFIX).strip()
    task_ref = lines[1].removeprefix(TELEGRAM_ADD_APPROVAL_TASK_REF_PREFIX).strip()
    confirm_line = lines[2]
    expected_confirm = f"confirm {task_ref}"
    if not title or not task_ref or expected_confirm not in confirm_line:
        return text

    return "\n".join(
        [
            "【下载审批】",
            f"标题: {title}",
            f"选择序号: {task_ref}",
            f"确认命令: {expected_confirm}",
            "",
            f"直接回复 {expected_confirm} 执行下载",
        ]
    )


def _format_telegram_import_approval_reply(text: str) -> str:
    stripped_text = text.strip()
    if not stripped_text.startswith(TELEGRAM_IMPORT_APPROVAL_PREFIX):
        return text

    lines = [line.strip() for line in stripped_text.splitlines() if line.strip()]
    if len(lines) < 4:
        return text

    name = lines[0].removeprefix(TELEGRAM_IMPORT_APPROVAL_PREFIX).strip()
    task_id = lines[1].removeprefix(TELEGRAM_IMPORT_APPROVAL_TASK_ID_PREFIX).strip()
    task_hash = lines[2].removeprefix(TELEGRAM_IMPORT_APPROVAL_TASK_HASH_PREFIX).strip()
    confirm_line = lines[3]
    confirm_match = re.match(r"^请发送\s+(confirm\s+.+?)\s+执行导入。?$", confirm_line)
    if not name or not task_id or not task_hash or confirm_match is None:
        return text

    confirm_command = confirm_match.group(1).strip()
    return "\n".join(
        [
            "【导入审批】",
            f"资源: {name}",
            f"任务 ID: {task_id}",
            f"任务 Hash: {task_hash}",
            f"确认命令: {confirm_command}",
            "",
            f"直接回复 {confirm_command} 执行导入",
        ]
    )

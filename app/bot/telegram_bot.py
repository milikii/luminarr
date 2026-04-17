from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeVar

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes, MessageHandler, filters

from app.bot.feishu_webhook_server import (
    FeishuWebhookServerConfig,
    FeishuWebhookServerRuntime,
    start_feishu_webhook_server,
    stop_feishu_webhook_server,
)
from app.bot.feishu_long_connection import (
    FEISHU_LONG_CONNECTION_SERVICE_KEY,
    FeishuLongConnectionService,
)
from app.bot.personal_wechat_login import (
    PERSONAL_WECHAT_LOGIN_SERVICE_KEY,
    PersonalWeChatLoginService,
    parse_personal_wechat_login_query,
)
from app.bot.wecom_webhook_server import (
    WeComWebhookServerConfig,
    WeComWebhookServerRuntime,
    start_wecom_webhook_server,
    stop_wecom_webhook_server,
)
from app.config import DownloaderInstanceConfig, DownloaderRoleBinding, RawBtDestinationOption
from app.clients.tmdb import TmdbMovie
from app.db.bt_pending_repo import (
    BT_PENDING_STAGE_PROCESSING_PATH,
    BT_PENDING_STAGE_CLASSIFICATION,
    BT_PENDING_STAGE_RAW_BT_DESTINATION,
    BT_PENDING_STAGE_TMDB_ASSOCIATION,
    BtPendingPersistenceError,
    BtPendingRepo,
)
from app.db.download_monitor_repo import DownloadMonitorRepo
from app.db.job_repo import JobRepo, WORKFLOW_ADD_TO_DOWNLOADER, WORKFLOW_IMPORT_TO_LIBRARY
from app.db.telegram_update_repo import TelegramUpdateRepo
from app.runtime.execution_policy import (
    ACTION_BT_READ_ONLY_HELPER,
    ACTION_BT_SUBSCRIPTION_LIST,
    ACTION_BT_SUBSCRIPTION_MUTATION,
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
    ACTION_WATCHLIST_LIST,
    ACTION_WATCHLIST_MUTATION,
    ExecutionGate,
)
from app.services.add_to_downloader import (
    ADD_CANCELLED_TEXT,
    BT_SOURCE_UNSUPPORTED_TEXT,
    AddToDownloaderService,
)
from app.services.cleanup_downloaded_source import (
    CleanupDownloadedSourceService,
    parse_cleanup_inspect_query,
    parse_cleanup_query,
)
from app.services.get_download_status import GetDownloadStatusService, parse_status_query
from app.services.manage_bt_subscription import (
    BtSubscriptionCommand,
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
from app.services.pure_bt import extract_bt_search_query, pick_single_item_candidate
from app.services.search_media import SearchMediaService, parse_movie_query

FRUSTRATION_RESET_TEXT = "已清除当前候选，请重新搜索。"
CLARIFICATION_RESET_TEXT = "已取消当前澄清，请重新描述片名后搜索。"
CLARIFICATION_SELECTION_BLOCKED_TEXT = "当前处于片名澄清中，请先补充片名或年份后再搜索。"
BT_PROCESSING_PATH_PROMPT_TEXT = (
    "已识别为直接 BT/磁力下载需求。\n"
    "请回复以下处理链之一：影视入库链 / 纯 BT 下载链\n"
    "对应含义：按影视资源处理并入库 / 仅下载并放到预设目录"
)
BT_PROCESSING_PATH_CANCELLED_TEXT = "已取消当前 BT 处理链选择，请重新发送磁力或 BT 指令。"
BT_PROCESSING_PATH_PENDING_REMINDER_TEXT = (
    "当前正在等待 BT 处理链选择。\n"
    "请回复：影视入库链 / 纯 BT 下载链"
)
BT_CLASSIFICATION_PROMPT_TEXT = (
    "已记录后续处理链：影视入库链。\n"
    "请回复以下媒体类型之一：movie / series / anime\n"
    "对应含义：电影 / 剧集 / 动漫"
)
BT_CLASSIFICATION_CANCELLED_TEXT = "已取消当前 BT 媒体类型选择，请重新发送磁力或 BT 指令。"
BT_CLASSIFICATION_PENDING_REMINDER_TEXT = (
    "当前正在等待 BT 媒体类型选择。\n"
    "请回复：movie / series / anime"
)
BT_CLASSIFICATION_RESULT_TEXT_TEMPLATE = (
    "已记录本次 BT 媒体类型：{label}（{kind}）。\n"
    "当前这一步只完成媒体类型 follow-up，暂不执行 TMDB 关联或下载投递。"
)
BT_TMDB_ASSOCIATION_PROMPT_TEXT_TEMPLATE = (
    "已记录本次 BT 分类：{label}（{kind}）。\n"
    "请继续发送片名，可带年份，例如：{example}\n"
    "当前这一步只做 TMDB 关联，不会执行下载投递。"
)
BT_TMDB_ASSOCIATION_PENDING_REMINDER_TEMPLATE = (
    "当前正在等待 {label} 的 TMDB 关联标题。\n"
    "请发送：片名 或 片名 + 年份，例如：{example}"
)
BT_TMDB_ASSOCIATION_CANCELLED_TEXT = "已取消当前 BT TMDB 关联，请重新发送磁力或 BT 指令。"
BT_TMDB_ASSOCIATION_NOT_FOUND_TEMPLATE = (
    "未找到可用的 TMDB 关联：{query}\n"
    "请补充更准确的片名，可带年份，例如：{example}\n"
    "如果这不是影视资源，请改选 raw_bt。"
)
BT_TMDB_ASSOCIATION_AMBIGUOUS_TEMPLATE = (
    "TMDB 关联存在多个候选：{query}\n"
    "请补充年份或更完整片名后重试。\n"
    "参考候选：\n"
    "{options}"
)
BT_TMDB_ASSOCIATION_SUCCESS_TEMPLATE = (
    "BT {label} TMDB 关联成功。\n"
    "标题: {title}\n"
    "原始标题: {original_title}\n"
    "年份: {year}\n"
    "TMDB ID: {tmdb_id}"
)
BT_TMDB_ASSOCIATION_SERVICE_NOT_READY_TEXT = "TMDB 关联服务未就绪，请稍后重试。"
RAW_BT_DESTINATION_PROMPT_TEXT_TEMPLATE = (
    "已记录本次 BT 分类：其他 BT 资源（raw_bt）。\n"
    "请选择预设目标目录：\n"
    "{options}\n"
    "请回复目录编号或目录键，例如：1 或 downloads\n"
    "当前这一步只记录目录 follow-up，不会执行下载投递。"
)
RAW_BT_DESTINATION_PENDING_REMINDER_TEMPLATE = (
    "当前正在等待 raw_bt 目标目录。\n"
    "请回复目录编号或目录键，例如：{example}"
)
RAW_BT_DESTINATION_SELECTED_TEMPLATE = (
    "已记录 raw_bt 目标目录。\n"
    "目录键: {key}\n"
    "目录说明: {label}\n"
    "目标路径: {target_dir}"
)
RAW_BT_DESTINATION_CANCELLED_TEXT = "已取消当前 raw_bt 目录选择，请重新发送磁力或 BT 指令。"
RAW_BT_DESTINATION_INVALID_TEMPLATE = (
    "未识别到有效的 raw_bt 目录选项：{query}\n"
    "请回复目录编号或目录键，例如：{example}\n"
    "可选目录：\n"
    "{options}"
)
RAW_BT_DESTINATION_SERVICE_NOT_READY_TEXT = "raw_bt 目录选择未就绪，请先配置预设目标目录后重试。"
DOWNLOADER_EXECUTION_CONFIG_MISSING_TEMPLATE = "下载器角色 {role} 绑定的实例不存在：{name}。请检查配置后重试。"
BT_SOURCE_REQUIRED_TEXT = "当前还缺少实际的磁力链接，请直接发送 magnet:? 链接后重试。"
PURE_BT_CANDIDATE_SELECTED_TEMPLATE = (
    "pure BT 最小优选已命中单片资源。\n"
    "搜索词: {query}\n"
    "命中资源: {title}"
)
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
BT_PROCESSING_PATH_PENDING_BY_CHAT_KEY = "bt_processing_path_pending_by_chat"
BT_CLASSIFICATION_PENDING_BY_CHAT_KEY = "bt_classification_pending_by_chat"
BT_TMDB_ASSOCIATION_PENDING_BY_CHAT_KEY = "bt_tmdb_association_pending_by_chat"
BT_TMDB_MOVIE_CANDIDATES_LOOKUP_KEY = "bt_tmdb_movie_candidates_lookup_func"
BT_TMDB_TV_CANDIDATES_LOOKUP_KEY = "bt_tmdb_tv_candidates_lookup_func"
RAW_BT_DESTINATION_PENDING_BY_CHAT_KEY = "raw_bt_destination_pending_by_chat"
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
TELEGRAM_PHOTO_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif"})
T = TypeVar("T")
LookupTmdbCandidatesFunc = Callable[[str, str], Awaitable[list[TmdbMovie]]]
TelegramSendMediaFunc = Callable[[int, str | Path, str | None], Awaitable[object]]
TelegramSendTextFunc = Callable[..., Awaitable[object]]
BT_PENDING_MISSING_AFTER_UPSERT_REASON = "bt_pending_state missing after upsert"
BT_PENDING_CLEAR_RESULT_MISSING_REASON = "bt_pending_state clear result missing"

BT_PROCESSING_PATH_ALIASES = {
    "影视入库链": "media_import",
    "影视入库": "media_import",
    "入库链": "media_import",
    "影视": "media_import",
    "mediaimport": "media_import",
    "media-import": "media_import",
    "media_import": "media_import",
    "纯bt下载链": "pure_bt",
    "纯bt下载": "pure_bt",
    "纯bt": "pure_bt",
    "纯磁力下载链": "pure_bt",
    "purebt": "pure_bt",
    "pure-bt": "pure_bt",
    "pure_bt": "pure_bt",
}
BT_CLASSIFICATION_ALIASES = {
    "movie": "movie",
    "film": "movie",
    "电影": "movie",
    "series": "series",
    "tv": "series",
    "show": "series",
    "电视剧": "series",
    "剧集": "series",
    "anime": "anime",
    "动漫": "anime",
    "动画": "anime",
}
BT_CLASSIFICATION_LABELS = {
    "movie": "电影",
    "series": "剧集",
    "anime": "动漫",
    "raw_bt": "其他 BT 资源",
}
BT_TMDB_ASSOCIATION_EXAMPLES = {
    "movie": "Dune 2021",
    "series": "三体 2023",
    "anime": "葬送的芙莉莲 2023",
}


@dataclass(frozen=True, slots=True)
class BtTmdbAssociationPending:
    media_kind: str
    source: str


@dataclass(frozen=True, slots=True)
class RawBtDestinationPending:
    options: tuple[RawBtDestinationOption, ...]
    source: str


@dataclass(frozen=True, slots=True)
class ResolvedDownloaderExecution:
    name: str
    downloader_type: str
    download_dir: str


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from app.bot.private_chat_runtime import dispatch_private_chat_text

    message = update.effective_message
    if message is None:
        return

    chat_id = _resolve_chat_id(update)
    user_id = _resolve_user_id(update)
    if not _record_message_update(update=update, context=context):
        return

    await dispatch_private_chat_text(
        query=(message.text or "").strip(),
        reply_func=_build_telegram_reply_func(message.reply_text),
        chat_id=chat_id,
        user_id=user_id,
        channel="telegram",
        bot_data=context.application.bot_data,
    )


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from app.bot.private_chat_runtime import dispatch_private_chat_text

    callback_query = getattr(update, "callback_query", None)
    if callback_query is None:
        return

    chat_id = _resolve_chat_id(update, callback_query=callback_query)
    user_id = _resolve_user_id(update, callback_query=callback_query)
    callback_query_id = str(getattr(callback_query, "id", "") or "").strip()
    if not _record_callback_update(
        callback_query_id=callback_query_id,
        chat_id=chat_id,
        user_id=user_id,
        context=context,
    ):
        return

    answer_func = getattr(callback_query, "answer", None)
    if callable(answer_func):
        await answer_func()

    message = _resolve_callback_message(update, callback_query)
    if message is None:
        return

    query = str(getattr(callback_query, "data", "") or "").strip()
    if not query:
        return

    await dispatch_private_chat_text(
        query=query,
        reply_func=_build_telegram_reply_func(message.reply_text),
        chat_id=chat_id,
        user_id=user_id,
        channel="telegram",
        bot_data=context.application.bot_data,
    )


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
    builder = (
        Application.builder()
        .token(token)
        .post_init(_start_bt_subscription_scheduler)
        .post_shutdown(_stop_bt_subscription_scheduler)
    )
    cleaned_proxy_url = outbound_proxy_url.strip()
    if cleaned_proxy_url:
        builder = builder.proxy(cleaned_proxy_url).get_updates_proxy(cleaned_proxy_url)
    application = builder.build()
    application.bot_data[SEARCH_SERVICE_KEY] = search_service
    application.bot_data[ADD_TO_DOWNLOADER_SERVICE_KEY] = add_to_downloader_service
    application.bot_data[GET_DOWNLOAD_STATUS_SERVICE_KEY] = get_download_status_service
    application.bot_data[IMPORT_TO_LIBRARY_SERVICE_KEY] = import_to_library_service
    if post_download_auto_import_service is not None:
        application.bot_data[POST_DOWNLOAD_AUTO_IMPORT_SERVICE_KEY] = post_download_auto_import_service
    application.bot_data[CLEANUP_DOWNLOADED_SOURCE_SERVICE_KEY] = cleanup_downloaded_source_service
    application.bot_data[MANAGE_WATCHLIST_SERVICE_KEY] = manage_watchlist_service
    application.bot_data[MANAGE_BT_SUBSCRIPTION_SERVICE_KEY] = manage_bt_subscription_service
    application.bot_data[EXECUTION_GATE_KEY] = execution_gate or ExecutionGate()
    application.bot_data[DOWNLOADER_INSTANCES_KEY] = downloader_instances
    application.bot_data[DOWNLOADER_ROLE_BINDING_KEY] = downloader_role_binding
    application.bot_data[TELEGRAM_SEND_MEDIA_FUNC_KEY] = build_telegram_send_media_func(application)
    application.bot_data[TELEGRAM_SEND_TEXT_FUNC_KEY] = build_telegram_send_text_func(application)
    if bt_tmdb_movie_candidates_lookup_func is not None:
        application.bot_data[BT_TMDB_MOVIE_CANDIDATES_LOOKUP_KEY] = bt_tmdb_movie_candidates_lookup_func
    if bt_tmdb_tv_candidates_lookup_func is not None:
        application.bot_data[BT_TMDB_TV_CANDIDATES_LOOKUP_KEY] = bt_tmdb_tv_candidates_lookup_func
    application.bot_data[RAW_BT_DESTINATION_OPTIONS_KEY] = raw_bt_destination_options
    if bt_pending_repo is not None:
        application.bot_data[BT_PENDING_REPO_KEY] = bt_pending_repo
    if telegram_update_repo is not None:
        application.bot_data[TELEGRAM_UPDATE_REPO_KEY] = telegram_update_repo
    if job_repo is not None:
        application.bot_data[JOB_REPO_KEY] = job_repo
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    return application


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


def _build_telegram_reply_func(
    reply_func: Callable[[str], Awaitable[object]],
) -> Callable[[str], Awaitable[object]]:
    async def wrapped(text: str) -> object:
        return await reply_func(_format_telegram_reply(text))

    return wrapped


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


def _resolve_execution_gate(context: ContextTypes.DEFAULT_TYPE) -> ExecutionGate:
    gate = context.application.bot_data.get(EXECUTION_GATE_KEY)
    if isinstance(gate, ExecutionGate):
        return gate
    resolved_gate = ExecutionGate()
    context.application.bot_data[EXECUTION_GATE_KEY] = resolved_gate
    return resolved_gate


def _resolve_execution_gate_for_application(application: Application) -> ExecutionGate:
    gate = application.bot_data.get(EXECUTION_GATE_KEY)
    if isinstance(gate, ExecutionGate):
        return gate
    resolved_gate = ExecutionGate()
    application.bot_data[EXECUTION_GATE_KEY] = resolved_gate
    return resolved_gate


async def _start_bt_subscription_scheduler(application: Application) -> None:
    _start_feishu_webhook_server_if_configured(application)
    _start_wecom_webhook_server_if_configured(application)
    await _start_feishu_long_connection_if_configured(application)
    await _start_personal_wechat_text_service_if_available(application)
    _start_post_download_auto_import_scheduler(application)

    existing_task = application.bot_data.get(BT_SUBSCRIPTION_SCHEDULER_TASK_KEY)
    if isinstance(existing_task, asyncio.Task) and not existing_task.done():
        return

    bt_subscription_service = application.bot_data.get(MANAGE_BT_SUBSCRIPTION_SERVICE_KEY)
    if not isinstance(bt_subscription_service, ManageBtSubscriptionService):
        return

    downloader_execution, resolution_error = _resolve_bound_downloader_execution_for_application(
        application=application,
        role="bt",
    )
    if resolution_error is not None:
        _log_bt_subscription_scheduler_config_error(reason=resolution_error)
        return
    if downloader_execution is None:
        _log_bt_subscription_scheduler_config_error(reason="未配置 BT 下载器角色绑定，后台自动扫描不会启动。")
        return

    stop_event = asyncio.Event()
    application.bot_data[BT_SUBSCRIPTION_SCHEDULER_STOP_EVENT_KEY] = stop_event
    application.bot_data[BT_SUBSCRIPTION_SCHEDULER_TASK_KEY] = application.create_task(
        _bt_subscription_scheduler_loop(
            application=application,
            bt_subscription_service=bt_subscription_service,
            execution_gate=_resolve_execution_gate_for_application(application),
            stop_event=stop_event,
            dispatch_context=BtSubscriptionDispatchContext(
                downloader_name=downloader_execution.name,
                downloader_type=downloader_execution.downloader_type,
                download_dir=downloader_execution.download_dir,
            ),
        ),
        name="bt_subscription_scheduler",
    )


async def _stop_bt_subscription_scheduler(application: Application) -> None:
    _stop_feishu_webhook_server_if_running(application)
    _stop_wecom_webhook_server_if_running(application)
    await _shutdown_feishu_long_connection_if_running(application)
    await _shutdown_personal_wechat_text_service_if_running(application)
    await _shutdown_personal_wechat_login_service_if_running(application)
    await _stop_post_download_auto_import_scheduler(application)

    stop_event = application.bot_data.pop(BT_SUBSCRIPTION_SCHEDULER_STOP_EVENT_KEY, None)
    task = application.bot_data.pop(BT_SUBSCRIPTION_SCHEDULER_TASK_KEY, None)
    if isinstance(stop_event, asyncio.Event):
        stop_event.set()
    if not isinstance(task, asyncio.Task):
        return
    try:
        await task
    except Exception as error:
        _log_bt_subscription_scheduler_loop_error(error=error)


def _start_post_download_auto_import_scheduler(application: Application) -> None:
    service = application.bot_data.get(POST_DOWNLOAD_AUTO_IMPORT_SERVICE_KEY)
    existing_task = application.bot_data.get(POST_DOWNLOAD_AUTO_IMPORT_TASK_KEY)
    if isinstance(service, PostDownloadAutoImportService) and not (
        isinstance(existing_task, asyncio.Task) and not existing_task.done()
    ):
        stop_event = asyncio.Event()
        application.bot_data[POST_DOWNLOAD_AUTO_IMPORT_STOP_EVENT_KEY] = stop_event
        application.bot_data[POST_DOWNLOAD_AUTO_IMPORT_TASK_KEY] = application.create_task(
            _post_download_auto_import_scheduler_loop(service=service, stop_event=stop_event),
            name="post_download_auto_import_scheduler",
    )
    status_service = application.bot_data.get(GET_DOWNLOAD_STATUS_SERVICE_KEY)
    download_monitor_repo = getattr(status_service, "download_monitor_repo", None)
    existing_task = application.bot_data.get(DOWNLOAD_COMPLETION_POLLING_TASK_KEY)
    if isinstance(existing_task, asyncio.Task) and not existing_task.done():
        return
    if not isinstance(status_service, GetDownloadStatusService):
        _log_download_completion_polling_config_error(reason="未注入有效的 get_download_status_service。")
        return
    if not isinstance(download_monitor_repo, DownloadMonitorRepo):
        _log_download_completion_polling_config_error(reason="get_download_status_service 未暴露有效的 download_monitor_repo。")
        return
    if not (isinstance(existing_task, asyncio.Task) and not existing_task.done()):
        stop_event = asyncio.Event()
        application.bot_data[DOWNLOAD_COMPLETION_POLLING_STOP_EVENT_KEY] = stop_event
        application.bot_data[DOWNLOAD_COMPLETION_POLLING_TASK_KEY] = application.create_task(
            _download_completion_polling_loop(download_monitor_repo=download_monitor_repo, status_service=status_service, stop_event=stop_event),
            name="download_completion_polling_scheduler",
        )


async def _stop_post_download_auto_import_scheduler(application: Application) -> None:
    stop_event = application.bot_data.pop(POST_DOWNLOAD_AUTO_IMPORT_STOP_EVENT_KEY, None)
    task = application.bot_data.pop(POST_DOWNLOAD_AUTO_IMPORT_TASK_KEY, None)
    if isinstance(stop_event, asyncio.Event):
        stop_event.set()
    if isinstance(task, asyncio.Task):
        await task
    stop_event = application.bot_data.pop(DOWNLOAD_COMPLETION_POLLING_STOP_EVENT_KEY, None)
    task = application.bot_data.pop(DOWNLOAD_COMPLETION_POLLING_TASK_KEY, None)
    if isinstance(stop_event, asyncio.Event):
        stop_event.set()
    if isinstance(task, asyncio.Task):
        try:
            await task
        except Exception as error:
            _log_download_completion_polling_stop_error(error=error)
            raise


def _start_feishu_webhook_server_if_configured(application: Application) -> None:
    existing_runtime = application.bot_data.get(FEISHU_WEBHOOK_SERVER_RUNTIME_KEY)
    if isinstance(existing_runtime, FeishuWebhookServerRuntime):
        return

    config = application.bot_data.get(FEISHU_WEBHOOK_SERVER_CONFIG_KEY)
    reply_text_func = application.bot_data.get(FEISHU_WEBHOOK_REPLY_TEXT_FUNC_KEY)
    if config is None and reply_text_func is None:
        return
    if not isinstance(config, FeishuWebhookServerConfig) or not callable(reply_text_func):
        print(
            "\033[31m[Feishu webhook 配置不完整]\033[0m 缺少 server config 或 reply sender。\n"
            "\033[33m[处理建议]\033[0m 同时配置 FEISHU_APP_ID/FEISHU_APP_SECRET，并在启动阶段注入 webhook host/port/path。"
        )
        return
    try:
        runtime = start_feishu_webhook_server(
            loop=asyncio.get_running_loop(),
            config=config,
            bot_data=application.bot_data,
            reply_text_func=reply_text_func,
        )
    except OSError as error:
        print(
            f"\033[31m[Feishu webhook 启动失败]\033[0m 原因={error}\n"
            "\033[33m[处理建议]\033[0m 检查 FEISHU_WEBHOOK_HOST/PORT 是否可绑定，或确认端口未被占用。"
        )
        raise
    application.bot_data[FEISHU_WEBHOOK_SERVER_RUNTIME_KEY] = runtime


def _stop_feishu_webhook_server_if_running(application: Application) -> None:
    runtime = application.bot_data.pop(FEISHU_WEBHOOK_SERVER_RUNTIME_KEY, None)
    if not isinstance(runtime, FeishuWebhookServerRuntime):
        return
    stop_feishu_webhook_server(runtime)


async def _start_feishu_long_connection_if_configured(application: Application) -> None:
    service = application.bot_data.get(FEISHU_LONG_CONNECTION_SERVICE_KEY)
    if not isinstance(service, FeishuLongConnectionService):
        return
    await service.start(bot_data=application.bot_data)


async def _shutdown_feishu_long_connection_if_running(application: Application) -> None:
    service = application.bot_data.get(FEISHU_LONG_CONNECTION_SERVICE_KEY)
    if not isinstance(service, FeishuLongConnectionService):
        return
    await service.shutdown()


def _start_wecom_webhook_server_if_configured(application: Application) -> None:
    existing_runtime = application.bot_data.get(WECOM_WEBHOOK_SERVER_RUNTIME_KEY)
    if isinstance(existing_runtime, WeComWebhookServerRuntime):
        return

    config = application.bot_data.get(WECOM_WEBHOOK_SERVER_CONFIG_KEY)
    if config is None:
        return
    if not isinstance(config, WeComWebhookServerConfig):
        print(
            "\033[31m[WeCom webhook 配置不完整]\033[0m 缺少有效的 server config。\n"
            "\033[33m[处理建议]\033[0m 同时配置 WECOM_TOKEN/WECOM_ENCODING_AES_KEY/WECOM_RECEIVE_ID，并在启动阶段注入 webhook host/port/path。"
        )
        return
    try:
        runtime = start_wecom_webhook_server(
            loop=asyncio.get_running_loop(),
            config=config,
            bot_data=application.bot_data,
        )
    except OSError as error:
        print(
            f"\033[31m[WeCom webhook 启动失败]\033[0m 原因={error}\n"
            "\033[33m[处理建议]\033[0m 检查 WECOM_WEBHOOK_HOST/PORT 是否可绑定，或确认端口未被占用。"
        )
        raise
    application.bot_data[WECOM_WEBHOOK_SERVER_RUNTIME_KEY] = runtime


def _stop_wecom_webhook_server_if_running(application: Application) -> None:
    runtime = application.bot_data.pop(WECOM_WEBHOOK_SERVER_RUNTIME_KEY, None)
    if not isinstance(runtime, WeComWebhookServerRuntime):
        return
    stop_wecom_webhook_server(runtime)


async def _start_personal_wechat_text_service_if_available(application: Application) -> None:
    from app.bot.personal_wechat_text import (
        PERSONAL_WECHAT_TEXT_SERVICE_KEY,
        PersonalWeChatTextService,
    )

    service = application.bot_data.get(PERSONAL_WECHAT_TEXT_SERVICE_KEY)
    if service is None:
        service = PersonalWeChatTextService()
        application.bot_data[PERSONAL_WECHAT_TEXT_SERVICE_KEY] = service
    if not isinstance(service, PersonalWeChatTextService):
        print(
            "\033[31m[personal WeChat 私聊文本服务配置无效]\033[0m bot_data 中的 personal_wechat_text_service 不是有效服务实例。\n"
            "\033[33m[处理建议]\033[0m 删除错误注入值，或改为 PersonalWeChatTextService 实例后重启服务。"
        )
        return
    await service.start(bot_data=application.bot_data)


async def _shutdown_personal_wechat_text_service_if_running(application: Application) -> None:
    from app.bot.personal_wechat_text import (
        PERSONAL_WECHAT_TEXT_SERVICE_KEY,
        PersonalWeChatTextService,
    )

    service = application.bot_data.get(PERSONAL_WECHAT_TEXT_SERVICE_KEY)
    if not isinstance(service, PersonalWeChatTextService):
        return
    await service.shutdown()


async def _shutdown_personal_wechat_login_service_if_running(application: Application) -> None:
    service = application.bot_data.get(PERSONAL_WECHAT_LOGIN_SERVICE_KEY)
    if not isinstance(service, PersonalWeChatLoginService):
        return
    await service.shutdown()


async def _post_download_auto_import_scheduler_loop(
    *,
    service: PostDownloadAutoImportService,
    stop_event: asyncio.Event,
) -> None:
    while not stop_event.is_set():
        try:
            result = await service.run_once()
            if result.state_unavailable:
                _log_post_download_auto_import_scheduler_state_unavailable(scanned=result.scanned)
        except Exception as error:
            _log_post_download_auto_import_scheduler_error(error=error)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=POST_DOWNLOAD_AUTO_IMPORT_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            continue


async def _poll_pending_download_completion_once(
    *, download_monitor_repo: DownloadMonitorRepo, status_service: GetDownloadStatusService
) -> None:
    try:
        pending_records = download_monitor_repo.list_pending_completion()
    except Exception as error:
        _log_download_completion_pending_list_error(error=error)
        return
    for record in pending_records:
        await status_service.get_status_text(record.task_hash, chat_id=record.chat_id)


async def _download_completion_polling_loop(
    *, download_monitor_repo: DownloadMonitorRepo, status_service: GetDownloadStatusService, stop_event: asyncio.Event
) -> None:
    while not stop_event.is_set():
        try:
            await _poll_pending_download_completion_once(download_monitor_repo=download_monitor_repo, status_service=status_service)
        except Exception as error:
            _log_download_completion_polling_loop_error(error=error)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=POST_DOWNLOAD_AUTO_IMPORT_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            continue


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


def _resolve_bt_pending_repo(context: ContextTypes.DEFAULT_TYPE) -> BtPendingRepo | None:
    pending_repo = context.application.bot_data.get(BT_PENDING_REPO_KEY)
    if isinstance(pending_repo, BtPendingRepo):
        return pending_repo
    return None


async def _run_sync_with_policy(
    gate: ExecutionGate,
    action: str,
    operation: Callable[[], T],
) -> T:
    async def _runner() -> T:
        return operation()

    return await gate.run(action, _runner)


def _watchlist_policy_action(action: str) -> str:
    if action == "list":
        return ACTION_WATCHLIST_LIST
    return ACTION_WATCHLIST_MUTATION


def _bt_subscription_policy_action(command: BtSubscriptionCommand) -> str:
    if command.action == "list":
        return ACTION_BT_SUBSCRIPTION_LIST
    if command.action == "run":
        return ACTION_BT_SUBSCRIPTION_RUN
    return ACTION_BT_SUBSCRIPTION_MUTATION


def _resolve_chat_id(
    update: Update,
    *,
    callback_query: object | None = None,
) -> int | None:
    chat = getattr(update, "effective_chat", None)
    chat_id = getattr(chat, "id", None)
    if isinstance(chat_id, int):
        return chat_id

    if callback_query is None:
        return None

    message = getattr(callback_query, "message", None)
    callback_chat = getattr(message, "chat", None)
    callback_chat_id = getattr(callback_chat, "id", None)
    if isinstance(callback_chat_id, int):
        return callback_chat_id
    return None


def _resolve_user_id(
    update: Update,
    *,
    callback_query: object | None = None,
) -> int | None:
    user = getattr(update, "effective_user", None)
    user_id = getattr(user, "id", None)
    if isinstance(user_id, int):
        return user_id

    if callback_query is None:
        return None

    callback_user = getattr(callback_query, "from_user", None)
    callback_user_id = getattr(callback_user, "id", None)
    if isinstance(callback_user_id, int):
        return callback_user_id
    return None


def _resolve_callback_message(update: Update, callback_query: object) -> object | None:
    message = getattr(update, "effective_message", None)
    if message is not None:
        return message
    return getattr(callback_query, "message", None)


def _is_frustration_text(text: str) -> bool:
    cleaned_text = re.sub(r"\s+", "", text.strip())
    if not cleaned_text:
        return False
    return cleaned_text in {"不对", "停", "重来", "换一个", "算了", "取消"}


def _is_bt_direct_intent(text: str) -> bool:
    stripped_text = text.strip()
    if not stripped_text:
        return False
    lowered_text = stripped_text.lower()
    if lowered_text.startswith("magnet:?"):
        return True

    normalized_text = re.sub(r"\s+", "", stripped_text).lower()
    return normalized_text in {
        "下载这个bt",
        "下载这个bt种子",
        "下载这个磁力",
        "下载此bt",
        "下载此bt种子",
        "下载此磁力",
    } or bool(extract_bt_search_query(stripped_text))


def _extract_bt_read_only_query(text: str) -> str:
    cleaned_text = re.sub(r"\s+", " ", text.strip())
    if not cleaned_text:
        return ""

    lowered_text = cleaned_text.lower()
    for prefix in ("bt搜 ", "bt search "):
        if lowered_text.startswith(prefix):
            return cleaned_text[len(prefix) :].strip()
    return ""


def _log_telegram_update_record_failed(
    *,
    source_type: str,
    source_id: str,
    chat_id: int | None,
    user_id: int | None,
    reason: str,
) -> None:
    print(
        f"\033[31m[Telegram 更新去重落盘失败]\033[0m source_type={source_type} "
        f"source_id={source_id.strip() or '-'} chat_id={chat_id if chat_id is not None else '-'} "
        f"user_id={user_id if user_id is not None else '-'} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 SQLite/telegram_updates 表写入是否正常；"
        "当前 update 会停止继续处理，避免在去重真相缺失时重复执行副作用。",
        flush=True,
    )


def _record_message_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    update_repo = context.application.bot_data.get(TELEGRAM_UPDATE_REPO_KEY)
    if not isinstance(update_repo, TelegramUpdateRepo):
        return True

    update_id = getattr(update, "update_id", 0)
    if not isinstance(update_id, int):
        return True

    chat = getattr(update, "effective_chat", None)
    user = getattr(update, "effective_user", None)
    chat_id = chat.id if chat is not None else None
    user_id = user.id if user is not None else None
    try:
        return update_repo.record_message_update(
            update_id=update_id,
            chat_id=chat_id,
            user_id=user_id,
        )
    except Exception as error:
        _log_telegram_update_record_failed(
            source_type="message",
            source_id=str(update_id),
            chat_id=chat_id,
            user_id=user_id,
            reason=str(error),
        )
        return False


def _record_callback_update(
    *,
    callback_query_id: str,
    chat_id: int | None,
    user_id: int | None,
    context: ContextTypes.DEFAULT_TYPE,
) -> bool:
    update_repo = context.application.bot_data.get(TELEGRAM_UPDATE_REPO_KEY)
    if not isinstance(update_repo, TelegramUpdateRepo):
        return True

    try:
        return update_repo.record_callback_update(
            callback_query_id=callback_query_id,
            chat_id=chat_id,
            user_id=user_id,
        )
    except Exception as error:
        _log_telegram_update_record_failed(
            source_type="callback",
            source_id=callback_query_id,
            chat_id=chat_id,
            user_id=user_id,
            reason=str(error),
        )
        return False


def _resolve_bt_processing_path_pending_by_chat(context: ContextTypes.DEFAULT_TYPE) -> dict[int, str]:
    pending_by_chat = context.application.bot_data.get(BT_PROCESSING_PATH_PENDING_BY_CHAT_KEY)
    if isinstance(pending_by_chat, dict):
        return pending_by_chat
    resolved_pending_by_chat: dict[int, str] = {}
    context.application.bot_data[BT_PROCESSING_PATH_PENDING_BY_CHAT_KEY] = resolved_pending_by_chat
    return resolved_pending_by_chat


def _resolve_bt_classification_pending_by_chat(context: ContextTypes.DEFAULT_TYPE) -> dict[int, str]:
    pending_by_chat = context.application.bot_data.get(BT_CLASSIFICATION_PENDING_BY_CHAT_KEY)
    if isinstance(pending_by_chat, dict):
        return pending_by_chat
    resolved_pending_by_chat: dict[int, str] = {}
    context.application.bot_data[BT_CLASSIFICATION_PENDING_BY_CHAT_KEY] = resolved_pending_by_chat
    return resolved_pending_by_chat


def _serialize_bt_pending_payload(payload: dict[str, object]) -> str:
    try:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return "{}"


def _deserialize_bt_pending_payload(payload_json: str) -> tuple[dict[str, object], str | None]:
    if not payload_json.strip():
        return {}, "payload_json empty"
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError:
        return {}, "payload_json invalid json"
    if not isinstance(payload, dict):
        return {}, "payload_json not object"
    return payload, None


def _log_bt_pending_payload_corruption(*, chat_id: int | None, stage: str, reason: str) -> None:
    print(
        f"\033[31m[BT 待处理载荷损坏]\033[0m chat_id={chat_id if chat_id is not None else '-'} stage={stage} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 bt_pending_state.payload_json 是否仍是合法 JSON，且包含当前 stage 需要的字段。",
        flush=True,
    )


def _log_bt_pending_clear_failed(*, chat_id: int | None, stage: str, reason: str) -> None:
    print(
        f"\033[31m[BT 待处理清理失败]\033[0m chat_id={chat_id if chat_id is not None else '-'} stage={stage} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 bt_pending_state 表删除是否正常；当前进程内待处理状态已尽量清掉，但重启后旧状态可能仍残留。",
        flush=True,
    )


def _log_bt_pending_clear_result_missing(*, chat_id: int | None, stage: str, reason: str) -> None:
    print(
        f"\033[31m[BT 待处理清理结果缺失]\033[0m chat_id={chat_id if chat_id is not None else '-'} stage={stage} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 bt_pending_state 删除返回是否仍带有明确结果；当前进程内待处理状态已尽量回滚，避免把缺失真相误判成已清理成功。",
        flush=True,
    )


def _log_bt_pending_read_failed(*, chat_id: int | None, stage: str, reason: str) -> None:
    print(
        f"\033[31m[BT 待处理读取失败]\033[0m chat_id={chat_id if chat_id is not None else '-'} stage={stage} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 bt_pending_state 表读取是否正常；当前相关入口会按状态不可用处理，避免把 SQLite 读取异常误判成“没有待处理状态”。",
        flush=True,
    )


def _log_bt_pending_persist_failed(*, chat_id: int | None, stage: str, reason: str) -> None:
    print(
        f"\033[31m[BT 待处理持久化失败]\033[0m chat_id={chat_id if chat_id is not None else '-'} stage={stage} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 bt_pending_state 表写入是否正常；当前进程内待处理状态仍保留，但重启后可能丢失这一步的上下文。",
        flush=True,
    )


def _log_bt_pending_missing_after_upsert(*, chat_id: int | None, stage: str, reason: str) -> None:
    print(
        f"\033[31m[BT 待处理写入后记录缺失]\033[0m chat_id={chat_id if chat_id is not None else '-'} stage={stage} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 bt_pending_state 表是否被并发删除或触发器回滚；"
        "如需继续当前 BT follow-up，请先确认 SQLite 写入后能立即回读该记录。",
        flush=True,
    )


def _set_bt_processing_path_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
    source: str,
) -> bool:
    if chat_id is None or chat_id <= 0:
        return False
    pending_by_chat = _resolve_bt_processing_path_pending_by_chat(context)
    cleaned_source = source.strip()
    pending_by_chat[chat_id] = cleaned_source
    pending_repo = _resolve_bt_pending_repo(context)
    if pending_repo is None:
        return True
    try:
        pending_repo.upsert_pending(
            chat_id=chat_id,
            stage=BT_PENDING_STAGE_PROCESSING_PATH,
            payload_json=_serialize_bt_pending_payload({"source": cleaned_source}),
        )
    except BtPendingPersistenceError as error:
        if str(error) == BT_PENDING_MISSING_AFTER_UPSERT_REASON:
            _log_bt_pending_missing_after_upsert(
                chat_id=chat_id,
                stage=BT_PENDING_STAGE_PROCESSING_PATH,
                reason=str(error),
            )
        else:
            _log_bt_pending_persist_failed(
                chat_id=chat_id,
                stage=BT_PENDING_STAGE_PROCESSING_PATH,
                reason=str(error),
            )
        pending_by_chat.pop(chat_id, None)
        return False
    except Exception as error:
        _log_bt_pending_persist_failed(
            chat_id=chat_id,
            stage=BT_PENDING_STAGE_PROCESSING_PATH,
            reason=str(error),
        )
        pending_by_chat.pop(chat_id, None)
        return False
    return True


def _is_bt_processing_path_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
) -> bool | None:
    if chat_id is None or chat_id <= 0:
        return False
    pending_by_chat = _resolve_bt_processing_path_pending_by_chat(context)
    if chat_id in pending_by_chat:
        return True
    pending_repo = _resolve_bt_pending_repo(context)
    if pending_repo is None:
        return False
    try:
        pending_state = pending_repo.get_pending(chat_id=chat_id)
    except Exception as error:
        _log_bt_pending_read_failed(
            chat_id=chat_id,
            stage=BT_PENDING_STAGE_PROCESSING_PATH,
            reason=str(error),
        )
        return None
    if pending_state is None or pending_state.stage != BT_PENDING_STAGE_PROCESSING_PATH:
        return False
    payload, payload_error = _deserialize_bt_pending_payload(pending_state.payload_json)
    if payload_error is not None:
        _log_bt_pending_payload_corruption(chat_id=chat_id, stage=pending_state.stage, reason=payload_error)
        return None
    pending_source = str(payload.get("source", "")).strip()
    if not pending_source:
        _log_bt_pending_payload_corruption(
            chat_id=chat_id,
            stage=pending_state.stage,
            reason="payload.source missing",
        )
        return None
    pending_by_chat[chat_id] = pending_source
    return True


def _clear_bt_processing_path_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
) -> bool | None:
    if chat_id is None or chat_id <= 0:
        return False
    pending_by_chat = _resolve_bt_processing_path_pending_by_chat(context)
    pending_source = pending_by_chat.pop(chat_id, None)
    cleared = pending_source is not None
    pending_repo = _resolve_bt_pending_repo(context)
    if pending_repo is None:
        return cleared
    try:
        cleared_result = pending_repo.clear_pending(chat_id=chat_id, expected_stage=BT_PENDING_STAGE_PROCESSING_PATH)
        if cleared_result is None:
            raise BtPendingPersistenceError(BT_PENDING_CLEAR_RESULT_MISSING_REASON)
        return cleared_result or cleared
    except Exception as error:
        if str(error) == BT_PENDING_CLEAR_RESULT_MISSING_REASON:
            _log_bt_pending_clear_result_missing(
                chat_id=chat_id,
                stage=BT_PENDING_STAGE_PROCESSING_PATH,
                reason=str(error),
            )
        else:
            _log_bt_pending_clear_failed(chat_id=chat_id, stage=BT_PENDING_STAGE_PROCESSING_PATH, reason=str(error))
        if isinstance(pending_source, str):
            pending_by_chat[chat_id] = pending_source
        return None


def _pop_bt_processing_path_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
) -> str | Literal[False] | None:
    if chat_id is None or chat_id <= 0:
        return None
    pending_by_chat = _resolve_bt_processing_path_pending_by_chat(context)
    pending_source = pending_by_chat.pop(chat_id, None)
    if isinstance(pending_source, str):
        pending_repo = _resolve_bt_pending_repo(context)
        if pending_repo is not None:
            try:
                cleared_result = pending_repo.clear_pending(
                    chat_id=chat_id,
                    expected_stage=BT_PENDING_STAGE_PROCESSING_PATH,
                )
                if cleared_result is None:
                    raise BtPendingPersistenceError(BT_PENDING_CLEAR_RESULT_MISSING_REASON)
            except Exception as error:
                pending_by_chat[chat_id] = pending_source
                if str(error) == BT_PENDING_CLEAR_RESULT_MISSING_REASON:
                    _log_bt_pending_clear_result_missing(
                        chat_id=chat_id,
                        stage=BT_PENDING_STAGE_PROCESSING_PATH,
                        reason=str(error),
                    )
                else:
                    _log_bt_pending_clear_failed(
                        chat_id=chat_id,
                        stage=BT_PENDING_STAGE_PROCESSING_PATH,
                        reason=str(error),
                    )
                return False
        return pending_source

    pending_repo = _resolve_bt_pending_repo(context)
    if pending_repo is None:
        return None
    try:
        pending_state = pending_repo.get_pending(chat_id=chat_id)
    except Exception as error:
        _log_bt_pending_read_failed(
            chat_id=chat_id,
            stage=BT_PENDING_STAGE_PROCESSING_PATH,
            reason=str(error),
        )
        return None
    if pending_state is None or pending_state.stage != BT_PENDING_STAGE_PROCESSING_PATH:
        return None
    payload, payload_error = _deserialize_bt_pending_payload(pending_state.payload_json)
    if payload_error is not None:
        _log_bt_pending_payload_corruption(chat_id=chat_id, stage=pending_state.stage, reason=payload_error)
        return None
    pending_source = str(payload.get("source", "")).strip()
    if not pending_source:
        _log_bt_pending_payload_corruption(
            chat_id=chat_id,
            stage=pending_state.stage,
            reason="payload.source missing",
        )
        return None
    try:
        cleared_result = pending_repo.clear_pending(chat_id=chat_id, expected_stage=BT_PENDING_STAGE_PROCESSING_PATH)
        if cleared_result is None:
            raise BtPendingPersistenceError(BT_PENDING_CLEAR_RESULT_MISSING_REASON)
    except Exception as error:
        pending_by_chat[chat_id] = pending_source
        if str(error) == BT_PENDING_CLEAR_RESULT_MISSING_REASON:
            _log_bt_pending_clear_result_missing(
                chat_id=chat_id,
                stage=BT_PENDING_STAGE_PROCESSING_PATH,
                reason=str(error),
            )
        else:
            _log_bt_pending_clear_failed(chat_id=chat_id, stage=BT_PENDING_STAGE_PROCESSING_PATH, reason=str(error))
        return False
    return pending_source


def _set_bt_classification_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
    query: str,
) -> bool:
    if chat_id is None or chat_id <= 0:
        return False
    pending_by_chat = _resolve_bt_classification_pending_by_chat(context)
    cleaned_query = query.strip()
    pending_by_chat[chat_id] = cleaned_query
    pending_repo = _resolve_bt_pending_repo(context)
    if pending_repo is None:
        return True
    try:
        pending_repo.upsert_pending(
            chat_id=chat_id,
            stage=BT_PENDING_STAGE_CLASSIFICATION,
            payload_json=_serialize_bt_pending_payload({"query": cleaned_query}),
        )
    except BtPendingPersistenceError as error:
        if str(error) == BT_PENDING_MISSING_AFTER_UPSERT_REASON:
            _log_bt_pending_missing_after_upsert(
                chat_id=chat_id,
                stage=BT_PENDING_STAGE_CLASSIFICATION,
                reason=str(error),
            )
        else:
            _log_bt_pending_persist_failed(
                chat_id=chat_id,
                stage=BT_PENDING_STAGE_CLASSIFICATION,
                reason=str(error),
            )
        pending_by_chat.pop(chat_id, None)
        return False
    except Exception as error:
        _log_bt_pending_persist_failed(
            chat_id=chat_id,
            stage=BT_PENDING_STAGE_CLASSIFICATION,
            reason=str(error),
        )
        pending_by_chat.pop(chat_id, None)
        return False
    return True


def _is_bt_classification_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
) -> bool | None:
    if chat_id is None or chat_id <= 0:
        return False
    pending_by_chat = _resolve_bt_classification_pending_by_chat(context)
    if chat_id in pending_by_chat:
        return True
    pending_repo = _resolve_bt_pending_repo(context)
    if pending_repo is None:
        return False
    try:
        pending_state = pending_repo.get_pending(chat_id=chat_id)
    except Exception as error:
        _log_bt_pending_read_failed(
            chat_id=chat_id,
            stage=BT_PENDING_STAGE_CLASSIFICATION,
            reason=str(error),
        )
        return None
    if pending_state is None or pending_state.stage != BT_PENDING_STAGE_CLASSIFICATION:
        return False
    payload, payload_error = _deserialize_bt_pending_payload(pending_state.payload_json)
    if payload_error is not None:
        _log_bt_pending_payload_corruption(chat_id=chat_id, stage=pending_state.stage, reason=payload_error)
        return None
    pending_query = str(payload.get("query", "")).strip()
    if not pending_query:
        _log_bt_pending_payload_corruption(
            chat_id=chat_id,
            stage=pending_state.stage,
            reason="payload.query missing",
        )
        return None
    pending_by_chat[chat_id] = pending_query
    return True


def _clear_bt_classification_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
) -> bool | None:
    if chat_id is None or chat_id <= 0:
        return False
    pending_by_chat = _resolve_bt_classification_pending_by_chat(context)
    pending_query = pending_by_chat.pop(chat_id, None)
    cleared = pending_query is not None
    pending_repo = _resolve_bt_pending_repo(context)
    if pending_repo is None:
        return cleared
    try:
        cleared_result = pending_repo.clear_pending(chat_id=chat_id, expected_stage=BT_PENDING_STAGE_CLASSIFICATION)
        if cleared_result is None:
            raise BtPendingPersistenceError(BT_PENDING_CLEAR_RESULT_MISSING_REASON)
        return cleared_result or cleared
    except Exception as error:
        if str(error) == BT_PENDING_CLEAR_RESULT_MISSING_REASON:
            _log_bt_pending_clear_result_missing(
                chat_id=chat_id,
                stage=BT_PENDING_STAGE_CLASSIFICATION,
                reason=str(error),
            )
        else:
            _log_bt_pending_clear_failed(chat_id=chat_id, stage=BT_PENDING_STAGE_CLASSIFICATION, reason=str(error))
        if isinstance(pending_query, str):
            pending_by_chat[chat_id] = pending_query
        return None


def _pop_bt_classification_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
) -> str | Literal[False] | None:
    if chat_id is None or chat_id <= 0:
        return None
    pending_by_chat = _resolve_bt_classification_pending_by_chat(context)
    pending_query = pending_by_chat.pop(chat_id, None)
    if isinstance(pending_query, str):
        pending_repo = _resolve_bt_pending_repo(context)
        if pending_repo is not None:
            try:
                cleared_result = pending_repo.clear_pending(
                    chat_id=chat_id,
                    expected_stage=BT_PENDING_STAGE_CLASSIFICATION,
                )
                if cleared_result is None:
                    raise BtPendingPersistenceError(BT_PENDING_CLEAR_RESULT_MISSING_REASON)
            except Exception as error:
                pending_by_chat[chat_id] = pending_query
                if str(error) == BT_PENDING_CLEAR_RESULT_MISSING_REASON:
                    _log_bt_pending_clear_result_missing(
                        chat_id=chat_id,
                        stage=BT_PENDING_STAGE_CLASSIFICATION,
                        reason=str(error),
                    )
                else:
                    _log_bt_pending_clear_failed(
                        chat_id=chat_id,
                        stage=BT_PENDING_STAGE_CLASSIFICATION,
                        reason=str(error),
                    )
                return False
        return pending_query

    pending_repo = _resolve_bt_pending_repo(context)
    if pending_repo is None:
        return None
    try:
        pending_state = pending_repo.get_pending(chat_id=chat_id)
    except Exception as error:
        _log_bt_pending_read_failed(
            chat_id=chat_id,
            stage=BT_PENDING_STAGE_CLASSIFICATION,
            reason=str(error),
        )
        return None
    if pending_state is None or pending_state.stage != BT_PENDING_STAGE_CLASSIFICATION:
        return None
    payload, payload_error = _deserialize_bt_pending_payload(pending_state.payload_json)
    if payload_error is not None:
        _log_bt_pending_payload_corruption(chat_id=chat_id, stage=pending_state.stage, reason=payload_error)
        return None
    pending_query = str(payload.get("query", "")).strip()
    if not pending_query:
        _log_bt_pending_payload_corruption(
            chat_id=chat_id,
            stage=pending_state.stage,
            reason="payload.query missing",
        )
        return None
    try:
        cleared_result = pending_repo.clear_pending(chat_id=chat_id, expected_stage=BT_PENDING_STAGE_CLASSIFICATION)
        if cleared_result is None:
            raise BtPendingPersistenceError(BT_PENDING_CLEAR_RESULT_MISSING_REASON)
    except Exception as error:
        pending_by_chat[chat_id] = pending_query
        if str(error) == BT_PENDING_CLEAR_RESULT_MISSING_REASON:
            _log_bt_pending_clear_result_missing(
                chat_id=chat_id,
                stage=BT_PENDING_STAGE_CLASSIFICATION,
                reason=str(error),
            )
        else:
            _log_bt_pending_clear_failed(chat_id=chat_id, stage=BT_PENDING_STAGE_CLASSIFICATION, reason=str(error))
        return False
    return pending_query


def _resolve_bt_tmdb_association_pending_by_chat(
    context: ContextTypes.DEFAULT_TYPE,
) -> dict[int, BtTmdbAssociationPending]:
    pending_by_chat = context.application.bot_data.get(BT_TMDB_ASSOCIATION_PENDING_BY_CHAT_KEY)
    if isinstance(pending_by_chat, dict):
        return pending_by_chat
    resolved_pending_by_chat: dict[int, BtTmdbAssociationPending] = {}
    context.application.bot_data[BT_TMDB_ASSOCIATION_PENDING_BY_CHAT_KEY] = resolved_pending_by_chat
    return resolved_pending_by_chat


def _resolve_raw_bt_destination_pending_by_chat(
    context: ContextTypes.DEFAULT_TYPE,
) -> dict[int, RawBtDestinationPending]:
    pending_by_chat = context.application.bot_data.get(RAW_BT_DESTINATION_PENDING_BY_CHAT_KEY)
    if isinstance(pending_by_chat, dict):
        return pending_by_chat
    resolved_pending_by_chat: dict[int, RawBtDestinationPending] = {}
    context.application.bot_data[RAW_BT_DESTINATION_PENDING_BY_CHAT_KEY] = resolved_pending_by_chat
    return resolved_pending_by_chat


def _set_bt_tmdb_association_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
    media_kind: str,
    source: str,
) -> bool:
    if chat_id is None or chat_id <= 0:
        return False
    pending_by_chat = _resolve_bt_tmdb_association_pending_by_chat(context)
    pending_by_chat[chat_id] = BtTmdbAssociationPending(media_kind=media_kind, source=source.strip())
    pending_repo = _resolve_bt_pending_repo(context)
    if pending_repo is None:
        return True
    try:
        pending_repo.upsert_pending(
            chat_id=chat_id,
            stage=BT_PENDING_STAGE_TMDB_ASSOCIATION,
            payload_json=_serialize_bt_pending_payload({"media_kind": media_kind, "source": source.strip()}),
        )
    except BtPendingPersistenceError as error:
        if str(error) == BT_PENDING_MISSING_AFTER_UPSERT_REASON:
            _log_bt_pending_missing_after_upsert(
                chat_id=chat_id,
                stage=BT_PENDING_STAGE_TMDB_ASSOCIATION,
                reason=str(error),
            )
        else:
            _log_bt_pending_persist_failed(
                chat_id=chat_id,
                stage=BT_PENDING_STAGE_TMDB_ASSOCIATION,
                reason=str(error),
            )
        pending_by_chat.pop(chat_id, None)
        return False
    except Exception as error:
        _log_bt_pending_persist_failed(
            chat_id=chat_id,
            stage=BT_PENDING_STAGE_TMDB_ASSOCIATION,
            reason=str(error),
        )
        pending_by_chat.pop(chat_id, None)
        return False
    return True


def _get_bt_tmdb_association_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
) -> BtTmdbAssociationPending | None | Literal[False]:
    if chat_id is None or chat_id <= 0:
        return None
    pending_by_chat = _resolve_bt_tmdb_association_pending_by_chat(context)
    pending = pending_by_chat.get(chat_id)
    if isinstance(pending, BtTmdbAssociationPending):
        return pending
    pending_repo = _resolve_bt_pending_repo(context)
    if pending_repo is None:
        return None
    try:
        pending_state = pending_repo.get_pending(chat_id=chat_id)
    except Exception as error:
        _log_bt_pending_read_failed(
            chat_id=chat_id,
            stage=BT_PENDING_STAGE_TMDB_ASSOCIATION,
            reason=str(error),
        )
        return False
    if pending_state is None or pending_state.stage != BT_PENDING_STAGE_TMDB_ASSOCIATION:
        return None
    payload, payload_error = _deserialize_bt_pending_payload(pending_state.payload_json)
    if payload_error is not None:
        _log_bt_pending_payload_corruption(chat_id=chat_id, stage=pending_state.stage, reason=payload_error)
        return False
    media_kind = str(payload.get("media_kind", "")).strip()
    source = str(payload.get("source", "")).strip()
    if not media_kind:
        _log_bt_pending_payload_corruption(
            chat_id=chat_id,
            stage=pending_state.stage,
            reason="payload.media_kind missing",
        )
        return False
    if not source:
        _log_bt_pending_payload_corruption(
            chat_id=chat_id,
            stage=pending_state.stage,
            reason="payload.source missing",
        )
        return False
    resolved_pending = BtTmdbAssociationPending(media_kind=media_kind, source=source)
    pending_by_chat[chat_id] = resolved_pending
    return resolved_pending


def _clear_bt_tmdb_association_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
) -> bool | None:
    if chat_id is None or chat_id <= 0:
        return False
    pending_by_chat = _resolve_bt_tmdb_association_pending_by_chat(context)
    pending = pending_by_chat.pop(chat_id, None)
    cleared = pending is not None
    pending_repo = _resolve_bt_pending_repo(context)
    if pending_repo is None:
        return cleared
    try:
        return pending_repo.clear_pending(chat_id=chat_id, expected_stage=BT_PENDING_STAGE_TMDB_ASSOCIATION) or cleared
    except Exception as error:
        _log_bt_pending_clear_failed(chat_id=chat_id, stage=BT_PENDING_STAGE_TMDB_ASSOCIATION, reason=str(error))
        if pending is not None:
            pending_by_chat[chat_id] = pending
        return None


def _set_raw_bt_destination_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
    options: tuple[RawBtDestinationOption, ...],
    source: str,
) -> bool:
    if chat_id is None or chat_id <= 0:
        return False
    pending_by_chat = _resolve_raw_bt_destination_pending_by_chat(context)
    pending_by_chat[chat_id] = RawBtDestinationPending(options=options, source=source.strip())
    pending_repo = _resolve_bt_pending_repo(context)
    if pending_repo is None:
        return True
    try:
        pending_repo.upsert_pending(
            chat_id=chat_id,
            stage=BT_PENDING_STAGE_RAW_BT_DESTINATION,
            payload_json=_serialize_bt_pending_payload(
                {
                    "options": [
                        {
                            "key": option.key,
                            "label": option.label,
                            "target_dir": option.target_dir,
                        }
                        for option in options
                    ],
                    "source": source.strip(),
                }
            ),
        )
    except BtPendingPersistenceError as error:
        if str(error) == BT_PENDING_MISSING_AFTER_UPSERT_REASON:
            _log_bt_pending_missing_after_upsert(
                chat_id=chat_id,
                stage=BT_PENDING_STAGE_RAW_BT_DESTINATION,
                reason=str(error),
            )
        else:
            _log_bt_pending_persist_failed(
                chat_id=chat_id,
                stage=BT_PENDING_STAGE_RAW_BT_DESTINATION,
                reason=str(error),
            )
        pending_by_chat.pop(chat_id, None)
        return False
    except Exception as error:
        _log_bt_pending_persist_failed(
            chat_id=chat_id,
            stage=BT_PENDING_STAGE_RAW_BT_DESTINATION,
            reason=str(error),
        )
        pending_by_chat.pop(chat_id, None)
        return False
    return True


def _get_raw_bt_destination_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
) -> RawBtDestinationPending | None | Literal[False]:
    if chat_id is None or chat_id <= 0:
        return None
    pending_by_chat = _resolve_raw_bt_destination_pending_by_chat(context)
    pending = pending_by_chat.get(chat_id)
    if isinstance(pending, RawBtDestinationPending):
        return pending
    pending_repo = _resolve_bt_pending_repo(context)
    if pending_repo is None:
        return None
    try:
        pending_state = pending_repo.get_pending(chat_id=chat_id)
    except Exception as error:
        _log_bt_pending_read_failed(
            chat_id=chat_id,
            stage=BT_PENDING_STAGE_RAW_BT_DESTINATION,
            reason=str(error),
        )
        return False
    if pending_state is None or pending_state.stage != BT_PENDING_STAGE_RAW_BT_DESTINATION:
        return None
    payload, payload_error = _deserialize_bt_pending_payload(pending_state.payload_json)
    if payload_error is not None:
        _log_bt_pending_payload_corruption(chat_id=chat_id, stage=pending_state.stage, reason=payload_error)
        return False
    raw_options = payload.get("options")
    source = str(payload.get("source", "")).strip()
    if not source:
        _log_bt_pending_payload_corruption(
            chat_id=chat_id,
            stage=pending_state.stage,
            reason="payload.source missing",
        )
        return False
    if not isinstance(raw_options, list):
        _log_bt_pending_payload_corruption(
            chat_id=chat_id,
            stage=pending_state.stage,
            reason="payload.options missing or not list",
        )
        return False
    options: list[RawBtDestinationOption] = []
    for raw_option in raw_options:
        if not isinstance(raw_option, dict):
            continue
        key = str(raw_option.get("key", "")).strip()
        label = str(raw_option.get("label", "")).strip()
        target_dir = str(raw_option.get("target_dir", "")).strip()
        if not key or not label or not target_dir:
            continue
        options.append(RawBtDestinationOption(key=key, label=label, target_dir=target_dir))
    if not options:
        _log_bt_pending_payload_corruption(
            chat_id=chat_id,
            stage=pending_state.stage,
            reason="payload.options has no valid entries",
        )
        return False
    resolved_pending = RawBtDestinationPending(options=tuple(options), source=source)
    pending_by_chat[chat_id] = resolved_pending
    return resolved_pending


def _clear_raw_bt_destination_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
) -> bool | None:
    if chat_id is None or chat_id <= 0:
        return False
    pending_by_chat = _resolve_raw_bt_destination_pending_by_chat(context)
    pending = pending_by_chat.pop(chat_id, None)
    cleared = pending is not None
    pending_repo = _resolve_bt_pending_repo(context)
    if pending_repo is None:
        return cleared
    try:
        return pending_repo.clear_pending(chat_id=chat_id, expected_stage=BT_PENDING_STAGE_RAW_BT_DESTINATION) or cleared
    except Exception as error:
        _log_bt_pending_clear_failed(chat_id=chat_id, stage=BT_PENDING_STAGE_RAW_BT_DESTINATION, reason=str(error))
        if pending is not None:
            pending_by_chat[chat_id] = pending
        return None


def _parse_bt_classification_choice(text: str) -> str | None:
    normalized_text = re.sub(r"\s+", "", text.strip()).lower()
    if not normalized_text:
        return None
    return BT_CLASSIFICATION_ALIASES.get(normalized_text)


def _parse_bt_processing_path_choice(text: str) -> str | None:
    normalized_text = re.sub(r"\s+", "", text.strip()).lower()
    if not normalized_text:
        return None
    return BT_PROCESSING_PATH_ALIASES.get(normalized_text)


def _parse_bt_processing_path_legacy_shortcut(text: str) -> tuple[str, str | None] | None:
    normalized_text = re.sub(r"\s+", "", text.strip()).lower()
    if not normalized_text:
        return None
    media_kind = BT_CLASSIFICATION_ALIASES.get(normalized_text)
    if media_kind is not None:
        return ("media_import", media_kind)
    if normalized_text in {"raw_bt", "rawbt", "raw", "其他bt资源", "其他bt"}:
        return ("pure_bt", None)
    return None


def _format_bt_classification_result(media_kind: str) -> str:
    label = BT_CLASSIFICATION_LABELS.get(media_kind, BT_CLASSIFICATION_LABELS["raw_bt"])
    return BT_CLASSIFICATION_RESULT_TEXT_TEMPLATE.format(label=label, kind=media_kind)


def _enter_pure_bt_flow(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
    source: str,
) -> str:
    raw_bt_destination_options = _resolve_raw_bt_destination_options(context)
    if not raw_bt_destination_options:
        return RAW_BT_DESTINATION_SERVICE_NOT_READY_TEXT
    if not _set_raw_bt_destination_pending(
        context=context,
        chat_id=chat_id,
        options=raw_bt_destination_options,
        source=source,
    ):
        return SERVICE_NOT_READY_TEXT
    return _format_raw_bt_destination_prompt(raw_bt_destination_options)


def _enter_media_import_bt_flow(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
    source: str,
    media_kind: str | None = None,
) -> str:
    if media_kind is not None:
        if not _set_bt_tmdb_association_pending(
            context=context,
            chat_id=chat_id,
            media_kind=media_kind,
            source=source,
        ):
            return SERVICE_NOT_READY_TEXT
        return _format_bt_tmdb_association_prompt(media_kind)
    if not _set_bt_classification_pending(
        context=context,
        chat_id=chat_id,
        query=source,
    ):
        return SERVICE_NOT_READY_TEXT
    return BT_CLASSIFICATION_PROMPT_TEXT


def _format_bt_tmdb_association_prompt(media_kind: str) -> str:
    label = BT_CLASSIFICATION_LABELS.get(media_kind, media_kind)
    example = BT_TMDB_ASSOCIATION_EXAMPLES.get(media_kind, "Dune 2021")
    return BT_TMDB_ASSOCIATION_PROMPT_TEXT_TEMPLATE.format(label=label, kind=media_kind, example=example)


def _format_bt_tmdb_association_pending_reminder(media_kind: str) -> str:
    label = BT_CLASSIFICATION_LABELS.get(media_kind, media_kind)
    example = BT_TMDB_ASSOCIATION_EXAMPLES.get(media_kind, "Dune 2021")
    return BT_TMDB_ASSOCIATION_PENDING_REMINDER_TEMPLATE.format(label=label, example=example)


def _resolve_bt_tmdb_candidates_lookup(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    media_kind: str,
) -> LookupTmdbCandidatesFunc | None:
    key = BT_TMDB_MOVIE_CANDIDATES_LOOKUP_KEY
    if media_kind in {"series", "anime"}:
        key = BT_TMDB_TV_CANDIDATES_LOOKUP_KEY
    lookup_func = context.application.bot_data.get(key)
    if callable(lookup_func):
        return lookup_func
    return None


def _format_bt_tmdb_association_options(options: list[TmdbMovie]) -> str:
    lines: list[str] = []
    for index, option in enumerate(options, start=1):
        title = option.title or option.original_title or "-"
        year = option.year or "-"
        lines.append(f"{index}. {title} ({year}) [TMDB ID: {option.tmdb_id or '-'}]")
    return "\n".join(lines) if lines else "- 暂无可区分候选，请直接补充年份。"


def _format_bt_tmdb_association_success(media_kind: str, match: TmdbMovie) -> str:
    label = BT_CLASSIFICATION_LABELS.get(media_kind, media_kind)
    title = match.title or match.original_title or "-"
    original_title = match.original_title or title
    year = match.year or "-"
    tmdb_id = match.tmdb_id or "-"
    return BT_TMDB_ASSOCIATION_SUCCESS_TEMPLATE.format(
        label=label,
        title=title,
        original_title=original_title,
        year=year,
        tmdb_id=tmdb_id,
    )


def _format_bt_dispatch_title(match: TmdbMovie) -> str:
    title = match.title or match.original_title or "(no title)"
    year = match.year.strip()
    if not year:
        return title
    return f"{title} ({year})"


def _can_dispatch_bt_source(source: str) -> bool:
    return source.strip().lower().startswith("magnet:?")


def _resolve_search_candidate_source(candidate: dict[str, object] | Mapping[str, object]) -> str:
    for key in ("downloadUrl", "downloadurl", "magnetUrl", "magneturl", "guid"):
        value = candidate.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _resolve_raw_bt_destination_options(
    context: ContextTypes.DEFAULT_TYPE,
) -> tuple[RawBtDestinationOption, ...]:
    options = context.application.bot_data.get(RAW_BT_DESTINATION_OPTIONS_KEY)
    if not isinstance(options, tuple):
        return ()
    resolved_options: list[RawBtDestinationOption] = []
    for option in options:
        if isinstance(option, RawBtDestinationOption):
            resolved_options.append(option)
    return tuple(resolved_options)


def _resolve_downloader_instances(
    context: ContextTypes.DEFAULT_TYPE,
) -> dict[str, DownloaderInstanceConfig]:
    return _resolve_downloader_instances_for_application(context.application)


def _resolve_bound_downloader_execution(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    role: str,
) -> tuple[ResolvedDownloaderExecution | None, str | None]:
    return _resolve_bound_downloader_execution_for_application(
        application=context.application,
        role=role,
    )


def _resolve_bound_downloader_execution_for_application(
    *,
    application: Application,
    role: str,
) -> tuple[ResolvedDownloaderExecution | None, str | None]:
    role_binding = application.bot_data.get(DOWNLOADER_ROLE_BINDING_KEY)
    if not isinstance(role_binding, DownloaderRoleBinding):
        return None, None

    role_name = "PT" if role == "pt" else "BT"
    downloader_name = role_binding.pt_downloader if role == "pt" else role_binding.bt_downloader
    cleaned_name = downloader_name.strip()
    if not cleaned_name:
        return None, None

    instances_by_name = _resolve_downloader_instances_for_application(application)
    instance = instances_by_name.get(cleaned_name)
    if instance is None:
        return None, DOWNLOADER_EXECUTION_CONFIG_MISSING_TEMPLATE.format(role=role_name, name=cleaned_name)

    return (
        ResolvedDownloaderExecution(
            name=instance.name,
            downloader_type=instance.downloader_type,
            download_dir=instance.download_dir,
        ),
        None,
    )


def _resolve_downloader_instances_for_application(
    application: Application,
) -> dict[str, DownloaderInstanceConfig]:
    raw_instances = application.bot_data.get(DOWNLOADER_INSTANCES_KEY)
    resolved_instances: dict[str, DownloaderInstanceConfig] = {}
    if not isinstance(raw_instances, tuple):
        return resolved_instances
    for instance in raw_instances:
        if isinstance(instance, DownloaderInstanceConfig):
            resolved_instances[instance.name] = instance
    return resolved_instances


def _format_raw_bt_destination_options(options: tuple[RawBtDestinationOption, ...]) -> str:
    lines: list[str] = []
    for index, option in enumerate(options, start=1):
        lines.append(f"{index}. {option.label} [{option.key}] -> {option.target_dir}")
    return "\n".join(lines) if lines else "- 暂无可用目录。"


def _format_raw_bt_destination_prompt(options: tuple[RawBtDestinationOption, ...]) -> str:
    return RAW_BT_DESTINATION_PROMPT_TEXT_TEMPLATE.format(
        options=_format_raw_bt_destination_options(options),
    )


def _resolve_raw_bt_destination_example(options: tuple[RawBtDestinationOption, ...]) -> str:
    if not options:
        return "downloads"
    first_option = options[0]
    return first_option.key or "1"


def _format_raw_bt_destination_selected(option: RawBtDestinationOption) -> str:
    return RAW_BT_DESTINATION_SELECTED_TEMPLATE.format(
        key=option.key,
        label=option.label,
        target_dir=option.target_dir,
    )


def _parse_raw_bt_destination_choice(
    query: str,
    options: tuple[RawBtDestinationOption, ...],
) -> RawBtDestinationOption | None:
    normalized_text = query.strip().lower()
    if not normalized_text:
        return None
    if normalized_text.isdigit():
        index = int(normalized_text)
        if 1 <= index <= len(options):
            return options[index - 1]
    for option in options:
        if normalized_text == option.key.lower():
            return option
    return None


def _format_raw_bt_destination_invalid(
    query: str,
    options: tuple[RawBtDestinationOption, ...],
) -> str:
    return RAW_BT_DESTINATION_INVALID_TEMPLATE.format(
        query=query.strip(),
        example=_resolve_raw_bt_destination_example(options),
        options=_format_raw_bt_destination_options(options),
    )


async def _handle_raw_bt_destination_query(
    *,
    query: str,
    pending: RawBtDestinationPending,
    chat_id: int | None,
    user_id: int | None,
    context: ContextTypes.DEFAULT_TYPE,
) -> str:
    if chat_id is None:
        return SERVICE_NOT_READY_TEXT
    selected_option = _parse_raw_bt_destination_choice(query, pending.options)
    if selected_option is None:
        return _format_raw_bt_destination_invalid(query, pending.options)

    _clear_raw_bt_destination_pending(context=context, chat_id=chat_id)
    selected_text = _format_raw_bt_destination_selected(selected_option)
    add_service = context.application.bot_data.get(ADD_TO_DOWNLOADER_SERVICE_KEY)
    if not isinstance(add_service, AddToDownloaderService):
        return SERVICE_NOT_READY_TEXT
    downloader_execution, resolution_error = _resolve_bound_downloader_execution(context=context, role="bt")
    if resolution_error is not None:
        return resolution_error
    if _can_dispatch_bt_source(pending.source):
        pending_text = await add_service.add_bt_source(
            chat_id=chat_id,
            user_id=user_id,
            source=pending.source,
            title=f"raw_bt -> {selected_option.label}",
            downloader_name=downloader_execution.name if downloader_execution is not None else "",
            downloader_type=downloader_execution.downloader_type if downloader_execution is not None else "transmission",
            download_dir=selected_option.target_dir,
            auto_import_enabled=False,
        )
        if pending_text == BT_SOURCE_UNSUPPORTED_TEXT:
            return pending_text
        return f"{selected_text}\n\n{pending_text}"

    pure_bt_query = extract_bt_search_query(pending.source)
    if not pure_bt_query:
        return f"{selected_text}\n\n{BT_SOURCE_REQUIRED_TEXT}"

    search_service = context.application.bot_data.get(SEARCH_SERVICE_KEY)
    if not isinstance(search_service, SearchMediaService):
        return SERVICE_NOT_READY_TEXT
    try:
        raw_results = await search_service.search_raw_candidates(pure_bt_query)
    except Exception as error:
        _log_pure_bt_search_error(query=pure_bt_query, error=error)
        return f"{selected_text}\n\n{PURE_BT_SEARCH_FAILED_TEXT}"

    selected_candidate = pick_single_item_candidate(raw_results, query=pure_bt_query)
    if selected_candidate is None:
        return f"{selected_text}\n\n{PURE_BT_CANDIDATE_NOT_FOUND_TEMPLATE.format(query=pure_bt_query)}"

    candidate_source = _resolve_search_candidate_source(selected_candidate)
    candidate_title = str(selected_candidate.get("title", "")).strip() or pure_bt_query
    pending_text = await add_service.add_candidate_source(
        chat_id=chat_id,
        user_id=user_id,
        source=candidate_source,
        title=candidate_title,
        downloader_name=downloader_execution.name if downloader_execution is not None else "",
        downloader_type=downloader_execution.downloader_type if downloader_execution is not None else "transmission",
        download_dir=selected_option.target_dir,
        auto_import_enabled=False,
    )
    return (
        f"{selected_text}\n\n"
        f"{PURE_BT_CANDIDATE_SELECTED_TEMPLATE.format(query=pure_bt_query, title=candidate_title)}\n\n"
        f"{pending_text}"
    )


def _log_bt_tmdb_association_error(*, media_kind: str, query: str, error: Exception) -> None:
    print(
        f"\033[31m[BT TMDB 关联失败]\033[0m 类型={media_kind} 查询={query} 原因={error}\n"
        "\033[33m[处理建议]\033[0m 检查 TMDB_API_KEY、TMDB_BASE_URL 和网络连通性后重试。"
    )


def _log_pure_bt_search_error(*, query: str, error: Exception) -> None:
    print(
        f"\033[31m[pure BT 搜索失败]\033[0m 查询={query} 原因={error}\n"
        "\033[33m[处理建议]\033[0m 检查 Prowlarr 地址、API Key 和网络连通性后重试。"
    )


def _log_bt_read_only_helper_error(*, query: str, error: Exception) -> None:
    print(
        f"\033[31m[BT 只读探索失败]\033[0m 查询={query} 原因={error}\n"
        "\033[33m[处理建议]\033[0m 检查 BT 来源配置、站点可达性和网络连通性后重试。"
    )


def _log_cleanup_service_not_ready(*, action: str, query: str) -> None:
    print(
        f"\033[31m[cleanup 服务未就绪]\033[0m 动作={action} 查询={query.strip() or '-'}\n"
        "\033[33m[处理建议]\033[0m 检查应用启动阶段是否已注入 cleanup_downloaded_source_service，"
        "并确认 CleanupDownloadedSourceService 实例创建成功后重试。"
    )


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


def _log_post_download_auto_import_scheduler_error(*, error: Exception) -> None:
    print(
        f"\033[31m[下载完成后台轮询失败]\033[0m 原因={error}\n"
        "\033[33m[处理建议]\033[0m 检查 download_monitor、SQLite 和导入审批链路后等待下一轮自动轮询。"
    )


def _log_post_download_auto_import_scheduler_state_unavailable(*, scanned: int) -> None:
    print(
        f"\033[31m[下载完成后台轮询状态读取失败]\033[0m scanned={scanned}\n"
        "\033[33m[处理建议]\033[0m 检查 download_monitor、job_event 和导入审批链路的持久化状态；当前这轮自动导入已跳过异常记录，下一轮仍会继续尝试。",
    )


def _log_download_completion_polling_loop_error(*, error: Exception) -> None:
    print(
        f"\033[31m[下载完成状态轮询失败]\033[0m 原因={error}\n"
        "\033[33m[处理建议]\033[0m 检查下载器状态查询、download_monitor 和 SQLite 后等待下一轮自动轮询。"
    )


def _log_download_completion_pending_list_error(*, error: Exception) -> None:
    print(
        f"\033[31m[下载完成待轮询列表读取失败]\033[0m 原因={error}\n"
        "\033[33m[处理建议]\033[0m 检查 download_monitor 表读取和 SQLite 连通性；当前这轮不会继续逐条查状态，但下一轮轮询仍会继续尝试。"
    )


def _log_download_completion_polling_config_error(*, reason: str) -> None:
    print(
        f"\033[31m[下载完成状态轮询未启动]\033[0m 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查应用启动阶段是否已注入 get_download_status_service，并确认它携带有效的 download_monitor_repo。"
    )


def _log_download_completion_polling_stop_error(*, error: Exception) -> None:
    print(
        f"\033[31m[下载完成状态轮询停止失败]\033[0m 原因={error}\n"
        "\033[33m[处理建议]\033[0m 检查下载完成轮询 task 的退出路径、SQLite 连接状态，以及 stop_event 触发后的清理逻辑。"
    )


async def _handle_bt_tmdb_association_query(
    *,
    query: str,
    pending: BtTmdbAssociationPending,
    chat_id: int | None,
    user_id: int | None,
    context: ContextTypes.DEFAULT_TYPE,
) -> str:
    if chat_id is None:
        return SERVICE_NOT_READY_TEXT
    parsed_query = parse_movie_query(query)
    if not parsed_query.title:
        return _format_bt_tmdb_association_pending_reminder(pending.media_kind)

    lookup_func = _resolve_bt_tmdb_candidates_lookup(context=context, media_kind=pending.media_kind)
    if lookup_func is None:
        return BT_TMDB_ASSOCIATION_SERVICE_NOT_READY_TEXT

    try:
        matches = await lookup_func(parsed_query.title, parsed_query.year)
    except Exception as error:
        _log_bt_tmdb_association_error(media_kind=pending.media_kind, query=query, error=error)
        return BT_TMDB_ASSOCIATION_SERVICE_NOT_READY_TEXT

    if not matches:
        example = BT_TMDB_ASSOCIATION_EXAMPLES.get(pending.media_kind, "Dune 2021")
        return BT_TMDB_ASSOCIATION_NOT_FOUND_TEMPLATE.format(query=query.strip(), example=example)

    if not parsed_query.year and len(matches) > 1:
        return BT_TMDB_ASSOCIATION_AMBIGUOUS_TEMPLATE.format(
            query=query.strip(),
            options=_format_bt_tmdb_association_options(matches),
        )

    _clear_bt_tmdb_association_pending(context=context, chat_id=chat_id)
    association_text = _format_bt_tmdb_association_success(pending.media_kind, matches[0])
    if not _can_dispatch_bt_source(pending.source):
        return f"{association_text}\n\n{BT_SOURCE_REQUIRED_TEXT}"
    add_service = context.application.bot_data.get(ADD_TO_DOWNLOADER_SERVICE_KEY)
    if not isinstance(add_service, AddToDownloaderService):
        return SERVICE_NOT_READY_TEXT
    downloader_execution, resolution_error = _resolve_bound_downloader_execution(context=context, role="bt")
    if resolution_error is not None:
        return resolution_error
    pending_text = await add_service.add_bt_source(
        chat_id=chat_id,
        user_id=user_id,
        source=pending.source,
        title=_format_bt_dispatch_title(matches[0]),
        downloader_name=downloader_execution.name if downloader_execution is not None else "",
        downloader_type=downloader_execution.downloader_type if downloader_execution is not None else "transmission",
        download_dir=downloader_execution.download_dir if downloader_execution is not None else "",
        auto_import_enabled=True,
    )
    if pending_text == BT_SOURCE_UNSUPPORTED_TEXT:
        return pending_text
    return f"{association_text}\n\n{pending_text}"


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


async def _search_with_reactive_recovery(
    *,
    search_service: SearchMediaService,
    query: str,
    chat_id: int | None,
) -> str:
    try:
        return await search_service.search_and_format(query, chat_id=chat_id)
    except Exception as error:
        if not _is_llm_physical_failure(error):
            raise

    recovery_context = _build_recovery_context(query=query, chat_id=chat_id)
    compact_query = recovery_context["current_job_context"]
    try:
        return await search_service.search_and_format(compact_query, chat_id=chat_id)
    except Exception as error:
        if _is_llm_physical_failure(error):
            return LLM_PHYSICAL_FAILURE_SAFE_TEXT
        raise


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


def _build_recovery_context(*, query: str, chat_id: int | None) -> dict[str, str]:
    compact_query = re.sub(r"\s+", " ", query.strip())
    if len(compact_query) > 160:
        compact_query = compact_query[:160]
    return {
        "system_base": "telegram_private_chat",
        "project_rules": "parser_first_llm_fallback",
        "current_job_context": compact_query if compact_query else f"chat:{chat_id or 0}",
    }


def _is_llm_physical_failure(error: Exception) -> bool:
    status_code = getattr(error, "status_code", None)
    if status_code == 413:
        return True

    message = str(error).lower()
    patterns = (
        "413",
        "payload too large",
        "max_output_tokens",
        "maximum context length",
        "context length exceeded",
        "response was truncated",
        "truncated",
    )
    return any(pattern in message for pattern in patterns)

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes, MessageHandler, filters

from app.bot.feishu_webhook_server import (
    FeishuWebhookServerConfig,
    FeishuWebhookServerRuntime,
    start_feishu_webhook_server,
    stop_feishu_webhook_server,
)
from app.config import DownloaderInstanceConfig, DownloaderRoleBinding, RawBtDestinationOption
from app.clients.tmdb import TmdbMovie
from app.db.bt_pending_repo import (
    BT_PENDING_STAGE_PROCESSING_PATH,
    BT_PENDING_STAGE_CLASSIFICATION,
    BT_PENDING_STAGE_RAW_BT_DESTINATION,
    BT_PENDING_STAGE_TMDB_ASSOCIATION,
    BtPendingRepo,
)
from app.db.job_repo import JobRepo, WORKFLOW_ADD_TO_DOWNLOADER, WORKFLOW_IMPORT_TO_LIBRARY
from app.db.telegram_update_repo import TelegramUpdateRepo
from app.runtime.execution_policy import (
    ACTION_BT_READ_ONLY_HELPER,
    ACTION_BT_SUBSCRIPTION_LIST,
    ACTION_BT_SUBSCRIPTION_MUTATION,
    ACTION_BT_SUBSCRIPTION_RUN,
    ACTION_ADD_TO_DOWNLOADER,
    ACTION_CANCEL_PENDING_APPROVAL,
    ACTION_CONFIRM_ADD_TO_DOWNLOADER,
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
SEARCH_SERVICE_KEY = "search_media_service"
ADD_TO_DOWNLOADER_SERVICE_KEY = "add_to_downloader_service"
GET_DOWNLOAD_STATUS_SERVICE_KEY = "get_download_status_service"
IMPORT_TO_LIBRARY_SERVICE_KEY = "import_to_library_service"
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
FEISHU_WEBHOOK_SERVER_CONFIG_KEY = "feishu_webhook_server_config"
FEISHU_WEBHOOK_REPLY_TEXT_FUNC_KEY = "feishu_webhook_reply_text_func"
FEISHU_WEBHOOK_SERVER_RUNTIME_KEY = "feishu_webhook_server_runtime"
BT_SUBSCRIPTION_SCHEDULER_INTERVAL_SECONDS = 300.0
T = TypeVar("T")
LookupTmdbCandidatesFunc = Callable[[str, str], Awaitable[list[TmdbMovie]]]

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
    message = update.effective_message
    if message is None:
        return

    chat_id = _resolve_chat_id(update)
    user_id = _resolve_user_id(update)
    if not _record_message_update(update=update, context=context):
        return

    await handle_private_chat_query_text(
        query=(message.text or "").strip(),
        reply_func=message.reply_text,
        chat_id=chat_id,
        user_id=user_id,
        context=context,
    )


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

    await handle_private_chat_query_text(
        query=query,
        reply_func=message.reply_text,
        chat_id=chat_id,
        user_id=user_id,
        context=context,
    )


def build_application(
    token: str,
    search_service: SearchMediaService,
    add_to_downloader_service: AddToDownloaderService,
    get_download_status_service: GetDownloadStatusService,
    import_to_library_service: ImportToLibraryService,
    manage_watchlist_service: ManageWatchlistService,
    manage_bt_subscription_service: ManageBtSubscriptionService,
    telegram_update_repo: TelegramUpdateRepo | None = None,
    job_repo: JobRepo | None = None,
    execution_gate: ExecutionGate | None = None,
    bt_pending_repo: BtPendingRepo | None = None,
    bt_tmdb_movie_candidates_lookup_func: LookupTmdbCandidatesFunc | None = None,
    bt_tmdb_tv_candidates_lookup_func: LookupTmdbCandidatesFunc | None = None,
    raw_bt_destination_options: tuple[RawBtDestinationOption, ...] = (),
    downloader_instances: tuple[DownloaderInstanceConfig, ...] = (),
    downloader_role_binding: DownloaderRoleBinding | None = None,
) -> Application:
    application = (
        Application.builder()
        .token(token)
        .post_init(_start_bt_subscription_scheduler)
        .post_shutdown(_stop_bt_subscription_scheduler)
        .build()
    )
    application.bot_data[SEARCH_SERVICE_KEY] = search_service
    application.bot_data[ADD_TO_DOWNLOADER_SERVICE_KEY] = add_to_downloader_service
    application.bot_data[GET_DOWNLOAD_STATUS_SERVICE_KEY] = get_download_status_service
    application.bot_data[IMPORT_TO_LIBRARY_SERVICE_KEY] = import_to_library_service
    application.bot_data[MANAGE_WATCHLIST_SERVICE_KEY] = manage_watchlist_service
    application.bot_data[MANAGE_BT_SUBSCRIPTION_SERVICE_KEY] = manage_bt_subscription_service
    application.bot_data[EXECUTION_GATE_KEY] = execution_gate or ExecutionGate()
    application.bot_data[DOWNLOADER_INSTANCES_KEY] = downloader_instances
    application.bot_data[DOWNLOADER_ROLE_BINDING_KEY] = downloader_role_binding
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


def _record_message_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    update_repo = context.application.bot_data.get(TELEGRAM_UPDATE_REPO_KEY)
    if not isinstance(update_repo, TelegramUpdateRepo):
        return True

    update_id = getattr(update, "update_id", 0)
    if not isinstance(update_id, int):
        return True

    chat = getattr(update, "effective_chat", None)
    user = getattr(update, "effective_user", None)
    return update_repo.record_message_update(
        update_id=update_id,
        chat_id=chat.id if chat is not None else None,
        user_id=user.id if user is not None else None,
    )


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

    return update_repo.record_callback_update(
        callback_query_id=callback_query_id,
        chat_id=chat_id,
        user_id=user_id,
    )


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


def _deserialize_bt_pending_payload(payload_json: str) -> dict[str, object]:
    if not payload_json.strip():
        return {}
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def _set_bt_processing_path_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
    source: str,
) -> None:
    if chat_id is None or chat_id <= 0:
        return
    pending_by_chat = _resolve_bt_processing_path_pending_by_chat(context)
    cleaned_source = source.strip()
    pending_by_chat[chat_id] = cleaned_source
    pending_repo = _resolve_bt_pending_repo(context)
    if pending_repo is None:
        return
    pending_repo.upsert_pending(
        chat_id=chat_id,
        stage=BT_PENDING_STAGE_PROCESSING_PATH,
        payload_json=_serialize_bt_pending_payload({"source": cleaned_source}),
    )


def _is_bt_processing_path_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
) -> bool:
    if chat_id is None or chat_id <= 0:
        return False
    pending_by_chat = _resolve_bt_processing_path_pending_by_chat(context)
    if chat_id in pending_by_chat:
        return True
    pending_repo = _resolve_bt_pending_repo(context)
    if pending_repo is None:
        return False
    pending_state = pending_repo.get_pending(chat_id=chat_id)
    if pending_state is None or pending_state.stage != BT_PENDING_STAGE_PROCESSING_PATH:
        return False
    payload = _deserialize_bt_pending_payload(pending_state.payload_json)
    pending_by_chat[chat_id] = str(payload.get("source", "")).strip()
    return True


def _clear_bt_processing_path_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
) -> bool:
    cleared = False
    if chat_id is None or chat_id <= 0:
        return False
    pending_by_chat = _resolve_bt_processing_path_pending_by_chat(context)
    if pending_by_chat.pop(chat_id, None) is not None:
        cleared = True
    pending_repo = _resolve_bt_pending_repo(context)
    if pending_repo is None:
        return cleared
    return pending_repo.clear_pending(chat_id=chat_id, expected_stage=BT_PENDING_STAGE_PROCESSING_PATH) or cleared


def _pop_bt_processing_path_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
) -> str | None:
    if chat_id is None or chat_id <= 0:
        return None
    pending_by_chat = _resolve_bt_processing_path_pending_by_chat(context)
    pending_source = pending_by_chat.pop(chat_id, None)
    if isinstance(pending_source, str):
        pending_repo = _resolve_bt_pending_repo(context)
        if pending_repo is not None:
            pending_repo.clear_pending(chat_id=chat_id, expected_stage=BT_PENDING_STAGE_PROCESSING_PATH)
        return pending_source

    pending_repo = _resolve_bt_pending_repo(context)
    if pending_repo is None:
        return None
    pending_state = pending_repo.get_pending(chat_id=chat_id)
    if pending_state is None or pending_state.stage != BT_PENDING_STAGE_PROCESSING_PATH:
        return None
    payload = _deserialize_bt_pending_payload(pending_state.payload_json)
    pending_repo.clear_pending(chat_id=chat_id, expected_stage=BT_PENDING_STAGE_PROCESSING_PATH)
    return str(payload.get("source", "")).strip() or None


def _set_bt_classification_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
    query: str,
) -> None:
    if chat_id is None or chat_id <= 0:
        return
    pending_by_chat = _resolve_bt_classification_pending_by_chat(context)
    cleaned_query = query.strip()
    pending_by_chat[chat_id] = cleaned_query
    pending_repo = _resolve_bt_pending_repo(context)
    if pending_repo is None:
        return
    pending_repo.upsert_pending(
        chat_id=chat_id,
        stage=BT_PENDING_STAGE_CLASSIFICATION,
        payload_json=_serialize_bt_pending_payload({"query": cleaned_query}),
    )


def _is_bt_classification_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
) -> bool:
    if chat_id is None or chat_id <= 0:
        return False
    pending_by_chat = _resolve_bt_classification_pending_by_chat(context)
    if chat_id in pending_by_chat:
        return True
    pending_repo = _resolve_bt_pending_repo(context)
    if pending_repo is None:
        return False
    pending_state = pending_repo.get_pending(chat_id=chat_id)
    if pending_state is None or pending_state.stage != BT_PENDING_STAGE_CLASSIFICATION:
        return False
    payload = _deserialize_bt_pending_payload(pending_state.payload_json)
    pending_by_chat[chat_id] = str(payload.get("query", "")).strip()
    return True


def _clear_bt_classification_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
) -> bool:
    cleared = False
    if chat_id is None or chat_id <= 0:
        return False
    pending_by_chat = _resolve_bt_classification_pending_by_chat(context)
    if pending_by_chat.pop(chat_id, None) is not None:
        cleared = True
    pending_repo = _resolve_bt_pending_repo(context)
    if pending_repo is None:
        return cleared
    return pending_repo.clear_pending(chat_id=chat_id, expected_stage=BT_PENDING_STAGE_CLASSIFICATION) or cleared


def _pop_bt_classification_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
) -> str | None:
    if chat_id is None or chat_id <= 0:
        return None
    pending_by_chat = _resolve_bt_classification_pending_by_chat(context)
    pending_query = pending_by_chat.pop(chat_id, None)
    if isinstance(pending_query, str):
        pending_repo = _resolve_bt_pending_repo(context)
        if pending_repo is not None:
            pending_repo.clear_pending(chat_id=chat_id, expected_stage=BT_PENDING_STAGE_CLASSIFICATION)
        return pending_query

    pending_repo = _resolve_bt_pending_repo(context)
    if pending_repo is None:
        return None
    pending_state = pending_repo.get_pending(chat_id=chat_id)
    if pending_state is None or pending_state.stage != BT_PENDING_STAGE_CLASSIFICATION:
        return None
    payload = _deserialize_bt_pending_payload(pending_state.payload_json)
    pending_repo.clear_pending(chat_id=chat_id, expected_stage=BT_PENDING_STAGE_CLASSIFICATION)
    return str(payload.get("query", "")).strip() or None


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
) -> None:
    if chat_id is None or chat_id <= 0:
        return
    pending_by_chat = _resolve_bt_tmdb_association_pending_by_chat(context)
    pending_by_chat[chat_id] = BtTmdbAssociationPending(media_kind=media_kind, source=source.strip())
    pending_repo = _resolve_bt_pending_repo(context)
    if pending_repo is None:
        return
    pending_repo.upsert_pending(
        chat_id=chat_id,
        stage=BT_PENDING_STAGE_TMDB_ASSOCIATION,
        payload_json=_serialize_bt_pending_payload({"media_kind": media_kind, "source": source.strip()}),
    )


def _get_bt_tmdb_association_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
) -> BtTmdbAssociationPending | None:
    if chat_id is None or chat_id <= 0:
        return None
    pending_by_chat = _resolve_bt_tmdb_association_pending_by_chat(context)
    pending = pending_by_chat.get(chat_id)
    if isinstance(pending, BtTmdbAssociationPending):
        return pending
    pending_repo = _resolve_bt_pending_repo(context)
    if pending_repo is None:
        return None
    pending_state = pending_repo.get_pending(chat_id=chat_id)
    if pending_state is None or pending_state.stage != BT_PENDING_STAGE_TMDB_ASSOCIATION:
        return None
    payload = _deserialize_bt_pending_payload(pending_state.payload_json)
    media_kind = str(payload.get("media_kind", "")).strip()
    source = str(payload.get("source", "")).strip()
    if not media_kind:
        return None
    resolved_pending = BtTmdbAssociationPending(media_kind=media_kind, source=source)
    pending_by_chat[chat_id] = resolved_pending
    return resolved_pending


def _clear_bt_tmdb_association_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
) -> bool:
    cleared = False
    if chat_id is None or chat_id <= 0:
        return False
    pending_by_chat = _resolve_bt_tmdb_association_pending_by_chat(context)
    if pending_by_chat.pop(chat_id, None) is not None:
        cleared = True
    pending_repo = _resolve_bt_pending_repo(context)
    if pending_repo is None:
        return cleared
    return pending_repo.clear_pending(chat_id=chat_id, expected_stage=BT_PENDING_STAGE_TMDB_ASSOCIATION) or cleared


def _set_raw_bt_destination_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
    options: tuple[RawBtDestinationOption, ...],
    source: str,
) -> None:
    if chat_id is None or chat_id <= 0:
        return
    pending_by_chat = _resolve_raw_bt_destination_pending_by_chat(context)
    pending_by_chat[chat_id] = RawBtDestinationPending(options=options, source=source.strip())
    pending_repo = _resolve_bt_pending_repo(context)
    if pending_repo is None:
        return
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


def _get_raw_bt_destination_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
) -> RawBtDestinationPending | None:
    if chat_id is None or chat_id <= 0:
        return None
    pending_by_chat = _resolve_raw_bt_destination_pending_by_chat(context)
    pending = pending_by_chat.get(chat_id)
    if isinstance(pending, RawBtDestinationPending):
        return pending
    pending_repo = _resolve_bt_pending_repo(context)
    if pending_repo is None:
        return None
    pending_state = pending_repo.get_pending(chat_id=chat_id)
    if pending_state is None or pending_state.stage != BT_PENDING_STAGE_RAW_BT_DESTINATION:
        return None
    payload = _deserialize_bt_pending_payload(pending_state.payload_json)
    raw_options = payload.get("options")
    source = str(payload.get("source", "")).strip()
    if not isinstance(raw_options, list):
        return None
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
        return None
    resolved_pending = RawBtDestinationPending(options=tuple(options), source=source)
    pending_by_chat[chat_id] = resolved_pending
    return resolved_pending


def _clear_raw_bt_destination_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
) -> bool:
    cleared = False
    if chat_id is None or chat_id <= 0:
        return False
    pending_by_chat = _resolve_raw_bt_destination_pending_by_chat(context)
    if pending_by_chat.pop(chat_id, None) is not None:
        cleared = True
    pending_repo = _resolve_bt_pending_repo(context)
    if pending_repo is None:
        return cleared
    return pending_repo.clear_pending(chat_id=chat_id, expected_stage=BT_PENDING_STAGE_RAW_BT_DESTINATION) or cleared


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
    _set_raw_bt_destination_pending(
        context=context,
        chat_id=chat_id,
        options=raw_bt_destination_options,
        source=source,
    )
    return _format_raw_bt_destination_prompt(raw_bt_destination_options)


def _enter_media_import_bt_flow(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
    source: str,
    media_kind: str | None = None,
) -> str:
    if media_kind is not None:
        _set_bt_tmdb_association_pending(
            context=context,
            chat_id=chat_id,
            media_kind=media_kind,
            source=source,
        )
        return _format_bt_tmdb_association_prompt(media_kind)
    _set_bt_classification_pending(
        context=context,
        chat_id=chat_id,
        query=source,
    )
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
    execution_gate = _resolve_execution_gate(context)
    if _is_frustration_text(query):
        if chat_id is not None:
            job_repo = context.application.bot_data.get(JOB_REPO_KEY)
            if isinstance(job_repo, JobRepo):
                try:
                    pending_job = job_repo.get_latest_pending_job(chat_id=chat_id)
                except Exception:
                    pending_job = None
                if pending_job is not None:
                    if pending_job.workflow_type == WORKFLOW_IMPORT_TO_LIBRARY:
                        import_service = context.application.bot_data.get(IMPORT_TO_LIBRARY_SERVICE_KEY)
                        if isinstance(import_service, ImportToLibraryService):
                            cancelled_text = await _run_sync_with_policy(
                                execution_gate,
                                ACTION_CANCEL_PENDING_APPROVAL,
                                lambda: import_service.cancel_pending_import(chat_id),
                            )
                            if cancelled_text == IMPORT_CANCELLED_TEXT:
                                await reply_func(cancelled_text)
                                return
                    if pending_job.workflow_type == WORKFLOW_ADD_TO_DOWNLOADER:
                        add_service = context.application.bot_data.get(ADD_TO_DOWNLOADER_SERVICE_KEY)
                        if isinstance(add_service, AddToDownloaderService):
                            cancelled_text = await _run_sync_with_policy(
                                execution_gate,
                                ACTION_CANCEL_PENDING_APPROVAL,
                                lambda: add_service.cancel_pending_add(chat_id),
                            )
                            if cancelled_text == ADD_CANCELLED_TEXT:
                                await reply_func(cancelled_text)
                                return

        import_service = context.application.bot_data.get(IMPORT_TO_LIBRARY_SERVICE_KEY)
        if isinstance(import_service, ImportToLibraryService) and chat_id is not None:
            cancelled_text = await _run_sync_with_policy(
                execution_gate,
                ACTION_CANCEL_PENDING_APPROVAL,
                lambda: import_service.cancel_pending_import(chat_id),
            )
            if cancelled_text == IMPORT_CANCELLED_TEXT:
                await reply_func(cancelled_text)
                return

        add_service = context.application.bot_data.get(ADD_TO_DOWNLOADER_SERVICE_KEY)
        if isinstance(add_service, AddToDownloaderService) and chat_id is not None:
            cancelled_text = await _run_sync_with_policy(
                execution_gate,
                ACTION_CANCEL_PENDING_APPROVAL,
                lambda: add_service.cancel_pending_add(chat_id),
            )
            if cancelled_text == ADD_CANCELLED_TEXT:
                await reply_func(cancelled_text)
                return

        search_service = context.application.bot_data.get(SEARCH_SERVICE_KEY)
        if isinstance(search_service, SearchMediaService) and chat_id is not None:
            if search_service.is_clarification_pending(chat_id):
                await _run_sync_with_policy(
                    execution_gate,
                    ACTION_RESET_CLARIFICATION,
                    lambda: search_service.clear_clarification_pending(chat_id),
                )
                await reply_func(CLARIFICATION_RESET_TEXT)
                return
            if await _run_sync_with_policy(
                execution_gate,
                ACTION_RESET_CANDIDATES,
                lambda: search_service.clear_cached_candidates(chat_id),
            ):
                await reply_func(FRUSTRATION_RESET_TEXT)
                return
        if _clear_raw_bt_destination_pending(context=context, chat_id=chat_id):
            await reply_func(RAW_BT_DESTINATION_CANCELLED_TEXT)
            return
        if _clear_bt_tmdb_association_pending(context=context, chat_id=chat_id):
            await reply_func(BT_TMDB_ASSOCIATION_CANCELLED_TEXT)
            return
        if _clear_bt_classification_pending(context=context, chat_id=chat_id):
            await reply_func(BT_CLASSIFICATION_CANCELLED_TEXT)
            return
        if _clear_bt_processing_path_pending(context=context, chat_id=chat_id):
            await reply_func(BT_PROCESSING_PATH_CANCELLED_TEXT)
            return

    if _is_bt_direct_intent(query):
        _clear_bt_processing_path_pending(context=context, chat_id=chat_id)
        _clear_raw_bt_destination_pending(context=context, chat_id=chat_id)
        _clear_bt_tmdb_association_pending(context=context, chat_id=chat_id)
        _clear_bt_classification_pending(context=context, chat_id=chat_id)
        _set_bt_processing_path_pending(
            context=context,
            chat_id=chat_id,
            source=query,
        )
        await reply_func(BT_PROCESSING_PATH_PROMPT_TEXT)
        return

    bt_read_only_query = _extract_bt_read_only_query(query)
    if bt_read_only_query:
        search_service = context.application.bot_data.get(SEARCH_SERVICE_KEY)
        if not isinstance(search_service, SearchMediaService):
            await reply_func(SERVICE_NOT_READY_TEXT)
            return
        try:
            reply = await execution_gate.run(
                ACTION_BT_READ_ONLY_HELPER,
                lambda: search_service.search_bt_read_only_and_format(bt_read_only_query),
            )
        except Exception as error:
            _log_bt_read_only_helper_error(query=bt_read_only_query, error=error)
            await reply_func(BT_READ_ONLY_HELPER_FAILED_TEXT)
            return
        await reply_func(reply)
        return

    bt_classification = _parse_bt_classification_choice(query)
    bt_processing_path = _parse_bt_processing_path_choice(query)
    bt_processing_shortcut = _parse_bt_processing_path_legacy_shortcut(query)
    if _is_bt_processing_path_pending(context=context, chat_id=chat_id) and (
        bt_processing_path is not None or bt_processing_shortcut is not None
    ):
        bt_source = _pop_bt_processing_path_pending(context=context, chat_id=chat_id) or ""
        _clear_raw_bt_destination_pending(context=context, chat_id=chat_id)
        _clear_bt_tmdb_association_pending(context=context, chat_id=chat_id)
        _clear_bt_classification_pending(context=context, chat_id=chat_id)
        if bt_processing_path == "media_import":
            await reply_func(
                _enter_media_import_bt_flow(
                    context=context,
                    chat_id=chat_id,
                    source=bt_source,
                )
            )
            return
        if bt_processing_path == "pure_bt":
            await reply_func(
                _enter_pure_bt_flow(
                    context=context,
                    chat_id=chat_id,
                    source=bt_source,
                )
            )
            return
        if bt_processing_shortcut is not None:
            shortcut_path, shortcut_media_kind = bt_processing_shortcut
            if shortcut_path == "pure_bt":
                await reply_func(
                    _enter_pure_bt_flow(
                        context=context,
                        chat_id=chat_id,
                        source=bt_source,
                    )
                )
                return
            await reply_func(
                _enter_media_import_bt_flow(
                    context=context,
                    chat_id=chat_id,
                    source=bt_source,
                    media_kind=shortcut_media_kind,
                )
            )
            return

    if bt_classification is not None and _is_bt_classification_pending(context=context, chat_id=chat_id):
        bt_source = _pop_bt_classification_pending(context=context, chat_id=chat_id) or ""
        _clear_raw_bt_destination_pending(context=context, chat_id=chat_id)
        _clear_bt_tmdb_association_pending(context=context, chat_id=chat_id)
        await reply_func(
            _enter_media_import_bt_flow(
                context=context,
                chat_id=chat_id,
                source=bt_source,
                media_kind=bt_classification,
            )
        )
        return

    task_ref = parse_status_query(query)
    if task_ref is not None:
        status_service = context.application.bot_data.get(GET_DOWNLOAD_STATUS_SERVICE_KEY)
        if not isinstance(status_service, GetDownloadStatusService):
            await reply_func(SERVICE_NOT_READY_TEXT)
            return
        reply = await execution_gate.run(
            ACTION_GET_DOWNLOAD_STATUS,
            lambda: status_service.get_status_text(task_ref, chat_id=chat_id),
        )
        await reply_func(reply)
        return

    watchlist_command = parse_watchlist_query(query)
    if watchlist_command is not None:
        watchlist_service = context.application.bot_data.get(MANAGE_WATCHLIST_SERVICE_KEY)
        if not isinstance(watchlist_service, ManageWatchlistService):
            await reply_func(SERVICE_NOT_READY_TEXT)
            return
        reply = await _run_sync_with_policy(
            execution_gate,
            _watchlist_policy_action(watchlist_command.action),
            lambda: watchlist_service.handle(
                watchlist_command,
                chat_id=chat_id,
            ),
        )
        await reply_func(reply)
        return

    bt_subscription_command = parse_bt_subscription_query(query)
    if bt_subscription_command is not None:
        bt_subscription_service = context.application.bot_data.get(MANAGE_BT_SUBSCRIPTION_SERVICE_KEY)
        if not isinstance(bt_subscription_service, ManageBtSubscriptionService):
            await reply_func(SERVICE_NOT_READY_TEXT)
            return
        if bt_subscription_command.action == "run":
            downloader_execution, resolution_error = _resolve_bound_downloader_execution(context=context, role="bt")
            if resolution_error is not None:
                await reply_func(resolution_error)
                return
            if downloader_execution is None:
                await reply_func(SERVICE_NOT_READY_TEXT)
                return
            reply = await execution_gate.run(
                _bt_subscription_policy_action(bt_subscription_command),
                lambda: bt_subscription_service.run_once(
                    chat_id=chat_id,
                    user_id=user_id,
                    dispatch_context=BtSubscriptionDispatchContext(
                        downloader_name=downloader_execution.name,
                        downloader_type=downloader_execution.downloader_type,
                        download_dir=downloader_execution.download_dir,
                    ),
                ),
            )
            await reply_func(reply)
            return
        reply = await _run_sync_with_policy(
            execution_gate,
            _bt_subscription_policy_action(bt_subscription_command),
            lambda: bt_subscription_service.handle(
                bt_subscription_command,
                chat_id=chat_id,
            ),
        )
        await reply_func(reply)
        return

    import_ref = parse_import_query(query)
    if import_ref is not None:
        import_service = context.application.bot_data.get(IMPORT_TO_LIBRARY_SERVICE_KEY)
        if not isinstance(import_service, ImportToLibraryService):
            await reply_func(SERVICE_NOT_READY_TEXT)
            return
        reply = await execution_gate.run(
            ACTION_IMPORT_TO_LIBRARY,
            lambda: import_service.import_by_task_ref(
                import_ref,
                chat_id=chat_id,
                user_id=user_id,
            ),
        )
        await reply_func(reply)
        return

    confirm_ref = parse_confirm_query(query)
    if confirm_ref is not None:
        if chat_id is not None and confirm_ref:
            job_repo = context.application.bot_data.get(JOB_REPO_KEY)
            if isinstance(job_repo, JobRepo):
                try:
                    matched_job = job_repo.get_job_for_chat_ref(chat_id=chat_id, task_ref=confirm_ref)
                except Exception:
                    matched_job = None
                if matched_job is not None and matched_job.workflow_type == WORKFLOW_ADD_TO_DOWNLOADER:
                    add_service = context.application.bot_data.get(ADD_TO_DOWNLOADER_SERVICE_KEY)
                    if not isinstance(add_service, AddToDownloaderService):
                        await reply_func(SERVICE_NOT_READY_TEXT)
                        return
                    reply = await execution_gate.run(
                        ACTION_CONFIRM_ADD_TO_DOWNLOADER,
                        lambda: add_service.confirm_add_by_task_ref(
                            confirm_ref,
                            chat_id=chat_id,
                            user_id=user_id,
                        ),
                    )
                    await reply_func(reply)
                    return
                if matched_job is not None and matched_job.workflow_type == WORKFLOW_IMPORT_TO_LIBRARY:
                    import_service = context.application.bot_data.get(IMPORT_TO_LIBRARY_SERVICE_KEY)
                    if not isinstance(import_service, ImportToLibraryService):
                        await reply_func(SERVICE_NOT_READY_TEXT)
                        return
                    reply = await execution_gate.run(
                        ACTION_CONFIRM_IMPORT_TO_LIBRARY,
                        lambda: import_service.confirm_import_by_task_ref(
                            confirm_ref,
                            chat_id=chat_id,
                            user_id=user_id,
                        ),
                    )
                    await reply_func(reply)
                    return

        add_service = context.application.bot_data.get(ADD_TO_DOWNLOADER_SERVICE_KEY)
        if (
            isinstance(add_service, AddToDownloaderService)
            and chat_id is not None
            and add_service.has_pending_add(chat_id, confirm_ref)
        ):
            reply = await execution_gate.run(
                ACTION_CONFIRM_ADD_TO_DOWNLOADER,
                lambda: add_service.confirm_add_by_task_ref(
                    confirm_ref,
                    chat_id=chat_id,
                    user_id=user_id,
                ),
            )
            await reply_func(reply)
            return

        import_service = context.application.bot_data.get(IMPORT_TO_LIBRARY_SERVICE_KEY)
        if not isinstance(import_service, ImportToLibraryService):
            await reply_func(SERVICE_NOT_READY_TEXT)
            return
        reply = await execution_gate.run(
            ACTION_CONFIRM_IMPORT_TO_LIBRARY,
            lambda: import_service.confirm_import_by_task_ref(
                confirm_ref,
                chat_id=chat_id,
                user_id=user_id,
            ),
        )
        await reply_func(reply)
        return

    bt_tmdb_pending = _get_bt_tmdb_association_pending(context=context, chat_id=chat_id)
    if bt_tmdb_pending is not None:
        reply = await _handle_bt_tmdb_association_query(
            query=query,
            pending=bt_tmdb_pending,
            chat_id=chat_id,
            user_id=user_id,
            context=context,
        )
        await reply_func(reply)
        return

    raw_bt_destination_pending = _get_raw_bt_destination_pending(context=context, chat_id=chat_id)
    if raw_bt_destination_pending is not None:
        reply = await _handle_raw_bt_destination_query(
            query=query,
            pending=raw_bt_destination_pending,
            chat_id=chat_id,
            user_id=user_id,
            context=context,
        )
        await reply_func(reply)
        return

    if query.isdigit():
        search_service = context.application.bot_data.get(SEARCH_SERVICE_KEY)
        if (
            isinstance(search_service, SearchMediaService)
            and chat_id is not None
            and search_service.is_clarification_pending(chat_id)
        ):
            await reply_func(CLARIFICATION_SELECTION_BLOCKED_TEXT)
            return

        add_service = context.application.bot_data.get(ADD_TO_DOWNLOADER_SERVICE_KEY)
        if not isinstance(add_service, AddToDownloaderService):
            await reply_func(SERVICE_NOT_READY_TEXT)
            return

        if chat_id is None:
            await reply_func(SERVICE_NOT_READY_TEXT)
            return
        downloader_execution, resolution_error = _resolve_bound_downloader_execution(context=context, role="pt")
        if resolution_error is not None:
            await reply_func(resolution_error)
            return
        reply = await execution_gate.run(
            ACTION_ADD_TO_DOWNLOADER,
            lambda: add_service.add_by_selection(
                chat_id,
                query,
                user_id=user_id,
                downloader_name=downloader_execution.name if downloader_execution is not None else "",
                downloader_type=downloader_execution.downloader_type if downloader_execution is not None else "transmission",
                download_dir=downloader_execution.download_dir if downloader_execution is not None else "",
            ),
        )
        await reply_func(reply)
        return

    search_service = context.application.bot_data.get(SEARCH_SERVICE_KEY)
    if not isinstance(search_service, SearchMediaService):
        await reply_func(SERVICE_NOT_READY_TEXT)
        return

    if _is_bt_processing_path_pending(context=context, chat_id=chat_id):
        await reply_func(BT_PROCESSING_PATH_PENDING_REMINDER_TEXT)
        return

    if _is_bt_classification_pending(context=context, chat_id=chat_id):
        await reply_func(BT_CLASSIFICATION_PENDING_REMINDER_TEXT)
        return

    reply = await execution_gate.run(
        ACTION_SEARCH_MEDIA,
        lambda: _search_with_reactive_recovery(
            search_service=search_service,
            query=query,
            chat_id=chat_id,
        ),
    )
    await reply_func(reply)


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

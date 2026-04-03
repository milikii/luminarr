from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from typing import TypeVar

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes, MessageHandler, filters

from app.db.job_repo import JobRepo, WORKFLOW_ADD_TO_DOWNLOADER, WORKFLOW_IMPORT_TO_LIBRARY
from app.db.telegram_update_repo import TelegramUpdateRepo
from app.runtime.execution_policy import (
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
    AddToDownloaderService,
)
from app.services.get_download_status import GetDownloadStatusService, parse_status_query
from app.services.import_to_library import (
    IMPORT_CANCELLED_TEXT,
    ImportToLibraryService,
    parse_confirm_query,
    parse_import_query,
)
from app.services.manage_watchlist import ManageWatchlistService, parse_watchlist_query
from app.services.search_media import SearchMediaService

FRUSTRATION_RESET_TEXT = "已清除当前候选，请重新搜索。"
CLARIFICATION_RESET_TEXT = "已取消当前澄清，请重新描述片名后搜索。"
CLARIFICATION_SELECTION_BLOCKED_TEXT = "当前处于片名澄清中，请先补充片名或年份后再搜索。"
BT_CLASSIFICATION_PROMPT_TEXT = (
    "已识别为直接 BT/磁力下载需求。\n"
    "请回复以下分类之一：movie / series / anime / raw_bt\n"
    "对应含义：电影 / 剧集 / 动漫 / 其他 BT 资源"
)
BT_CLASSIFICATION_CANCELLED_TEXT = "已取消当前 BT 分类，请重新发送磁力或 BT 指令。"
BT_CLASSIFICATION_PENDING_REMINDER_TEXT = (
    "当前正在等待 BT 分类。\n"
    "请回复：movie / series / anime / raw_bt"
)
BT_CLASSIFICATION_RESULT_TEXT_TEMPLATE = (
    "已记录本次 BT 分类：{label}（{kind}）。\n"
    "当前这一步只完成分类 follow-up，暂不执行 TMDB 关联、下载投递或目录选择。"
)
SERVICE_NOT_READY_TEXT = "服务未就绪，请稍后重试。"
LLM_PHYSICAL_FAILURE_SAFE_TEXT = "请求过长或响应被截断，系统已自动重试一次。请简化描述后重试。"
SEARCH_SERVICE_KEY = "search_media_service"
ADD_TO_DOWNLOADER_SERVICE_KEY = "add_to_downloader_service"
GET_DOWNLOAD_STATUS_SERVICE_KEY = "get_download_status_service"
IMPORT_TO_LIBRARY_SERVICE_KEY = "import_to_library_service"
MANAGE_WATCHLIST_SERVICE_KEY = "manage_watchlist_service"
JOB_REPO_KEY = "job_repo"
TELEGRAM_UPDATE_REPO_KEY = "telegram_update_repo"
EXECUTION_GATE_KEY = "execution_gate"
BT_CLASSIFICATION_PENDING_BY_CHAT_KEY = "bt_classification_pending_by_chat"
T = TypeVar("T")

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
    "raw_bt": "raw_bt",
    "rawbt": "raw_bt",
    "raw": "raw_bt",
    "其他bt资源": "raw_bt",
    "其他bt": "raw_bt",
}
BT_CLASSIFICATION_LABELS = {
    "movie": "电影",
    "series": "剧集",
    "anime": "动漫",
    "raw_bt": "其他 BT 资源",
}


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return

    chat_id = _resolve_chat_id(update)
    user_id = _resolve_user_id(update)
    if not _record_message_update(update=update, context=context):
        return

    await _handle_query_text(
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

    await _handle_query_text(
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
    telegram_update_repo: TelegramUpdateRepo | None = None,
    job_repo: JobRepo | None = None,
    execution_gate: ExecutionGate | None = None,
) -> Application:
    application = Application.builder().token(token).build()
    application.bot_data[SEARCH_SERVICE_KEY] = search_service
    application.bot_data[ADD_TO_DOWNLOADER_SERVICE_KEY] = add_to_downloader_service
    application.bot_data[GET_DOWNLOAD_STATUS_SERVICE_KEY] = get_download_status_service
    application.bot_data[IMPORT_TO_LIBRARY_SERVICE_KEY] = import_to_library_service
    application.bot_data[MANAGE_WATCHLIST_SERVICE_KEY] = manage_watchlist_service
    application.bot_data[EXECUTION_GATE_KEY] = execution_gate or ExecutionGate()
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
    }


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


def _resolve_bt_classification_pending_by_chat(context: ContextTypes.DEFAULT_TYPE) -> dict[int, str]:
    pending_by_chat = context.application.bot_data.get(BT_CLASSIFICATION_PENDING_BY_CHAT_KEY)
    if isinstance(pending_by_chat, dict):
        return pending_by_chat
    resolved_pending_by_chat: dict[int, str] = {}
    context.application.bot_data[BT_CLASSIFICATION_PENDING_BY_CHAT_KEY] = resolved_pending_by_chat
    return resolved_pending_by_chat


def _set_bt_classification_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
    query: str,
) -> None:
    if chat_id is None or chat_id <= 0:
        return
    pending_by_chat = _resolve_bt_classification_pending_by_chat(context)
    pending_by_chat[chat_id] = query.strip()


def _is_bt_classification_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
) -> bool:
    if chat_id is None or chat_id <= 0:
        return False
    pending_by_chat = _resolve_bt_classification_pending_by_chat(context)
    return chat_id in pending_by_chat


def _clear_bt_classification_pending(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | None,
) -> bool:
    if chat_id is None or chat_id <= 0:
        return False
    pending_by_chat = _resolve_bt_classification_pending_by_chat(context)
    return pending_by_chat.pop(chat_id, None) is not None


def _parse_bt_classification_choice(text: str) -> str | None:
    normalized_text = re.sub(r"\s+", "", text.strip()).lower()
    if not normalized_text:
        return None
    return BT_CLASSIFICATION_ALIASES.get(normalized_text)


def _format_bt_classification_result(media_kind: str) -> str:
    label = BT_CLASSIFICATION_LABELS.get(media_kind, BT_CLASSIFICATION_LABELS["raw_bt"])
    return BT_CLASSIFICATION_RESULT_TEXT_TEMPLATE.format(label=label, kind=media_kind)


async def _handle_query_text(
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
        if _clear_bt_classification_pending(context=context, chat_id=chat_id):
            await reply_func(BT_CLASSIFICATION_CANCELLED_TEXT)
            return

    if _is_bt_direct_intent(query):
        _set_bt_classification_pending(
            context=context,
            chat_id=chat_id,
            query=query,
        )
        await reply_func(BT_CLASSIFICATION_PROMPT_TEXT)
        return

    bt_classification = _parse_bt_classification_choice(query)
    if bt_classification is not None and _is_bt_classification_pending(context=context, chat_id=chat_id):
        _clear_bt_classification_pending(context=context, chat_id=chat_id)
        await reply_func(_format_bt_classification_result(bt_classification))
        return

    task_ref = parse_status_query(query)
    if task_ref is not None:
        status_service = context.application.bot_data.get(GET_DOWNLOAD_STATUS_SERVICE_KEY)
        if not isinstance(status_service, GetDownloadStatusService):
            await reply_func(SERVICE_NOT_READY_TEXT)
            return
        reply = await execution_gate.run(
            ACTION_GET_DOWNLOAD_STATUS,
            lambda: status_service.get_status_text(task_ref),
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
        reply = await execution_gate.run(
            ACTION_ADD_TO_DOWNLOADER,
            lambda: add_service.add_by_selection(
                chat_id,
                query,
                user_id=user_id,
            ),
        )
        await reply_func(reply)
        return

    search_service = context.application.bot_data.get(SEARCH_SERVICE_KEY)
    if not isinstance(search_service, SearchMediaService):
        await reply_func(SERVICE_NOT_READY_TEXT)
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

from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping
from dataclasses import dataclass

from app.bot.bt_classification_runtime import (
    BT_CLASSIFICATION_CANCELLED_TEXT,
    BT_CLASSIFICATION_PENDING_REMINDER_TEXT,
    clear_bt_classification_pending,
    is_bt_classification_pending,
    pop_bt_classification_pending,
)
from app.bot.bt_processing_path_runtime import (
    BT_PROCESSING_PATH_CANCELLED_TEXT,
    BT_PROCESSING_PATH_PENDING_REMINDER_TEXT,
    BT_PROCESSING_PATH_PROMPT_TEXT,
    clear_bt_processing_path_pending,
    is_bt_processing_path_pending,
    pop_bt_processing_path_pending,
    set_bt_processing_path_pending,
)
from app.bot.bt_tmdb_association_runtime import (
    clear_bt_tmdb_association_pending,
    enter_media_import_bt_flow,
    get_bt_tmdb_association_pending,
    handle_bt_tmdb_association_query as handle_shared_bt_tmdb_association_query,
    log_bt_tmdb_association_error,
    resolve_bt_tmdb_candidates_lookup,
)
from app.bot.downloader_execution_runtime import resolve_bound_downloader_execution as resolve_shared_bound_downloader_execution
from app.bot.execution_runtime import (
    bt_subscription_policy_action,
    resolve_execution_gate,
    run_sync_with_policy,
    watchlist_policy_action,
)
from app.bot.query_text_runtime import (
    extract_bt_batch_confirm_request,
    extract_bt_batch_preview_request,
    extract_bt_read_only_query,
    is_bt_direct_intent,
    is_frustration_text,
    parse_bt_classification_choice,
    parse_bt_processing_path_choice,
    parse_bt_processing_path_legacy_shortcut,
)
from app.bot.private_chat_confirm_runtime import handle_confirm_query as handle_shared_confirm_query
from app.bot.private_chat_selection_runtime import handle_digit_selection_query as handle_shared_digit_selection_query
from app.bot.raw_bt_destination_runtime import (
    clear_raw_bt_destination_pending,
    enter_pure_bt_flow,
    get_raw_bt_destination_pending,
    handle_raw_bt_destination_query as handle_shared_raw_bt_destination_query,
    log_pure_bt_search_error,
)
from app.bot.search_recovery_runtime import search_with_reactive_recovery
from app.bot import telegram_bot as telegram_runtime
from app.bot.cleanup_smoke_logging import log_cleanup_private_chat_smoke
from app.bot.private_chat_login_runtime import handle_personal_wechat_login_query as handle_shared_personal_wechat_login_query
from app.bot.private_chat_status_runtime import handle_status_query as handle_shared_status_query
from app.bot.private_chat_trace_runtime import prepare_private_chat_reply_with_trace

PrivateChatReplyFunc = Callable[[str], Awaitable[object]]


@dataclass(slots=True)
class _PrivateChatRuntimeApplication:
    bot_data: MutableMapping[str, object]


@dataclass(slots=True)
class _PrivateChatRuntimeContext:
    application: _PrivateChatRuntimeApplication


def _log_pending_job_lookup_failed(*, chat_id: int | None, reason: str) -> None:
    print(
        f"\033[31m[待处理任务查询失败]\033[0m chat_id={chat_id if chat_id is not None else '-'} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 SQLite 是否可读，以及 jobs 表和当前待处理任务记录是否正常。"
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


async def _handle_bt_read_only_request(
    *,
    bot_data: MutableMapping[str, object],
    execution_gate,
    reply_func: PrivateChatReplyFunc,
    search_runner: Callable[[object], object],
    helper_query: str,
    tg,
) -> bool:
    search_service = bot_data.get(tg.SEARCH_SERVICE_KEY)
    if not isinstance(search_service, tg.SearchMediaService):
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True
    try:
        reply = await execution_gate.run(
            tg.ACTION_BT_READ_ONLY_HELPER,
            lambda: search_runner(search_service),
        )
    except Exception as error:
        _log_bt_read_only_helper_error(query=helper_query, error=error)
        await reply_func(tg.BT_READ_ONLY_HELPER_FAILED_TEXT)
        return True
    await reply_func(reply)
    return True


async def _handle_cleanup_request(
    *,
    bot_data: MutableMapping[str, object],
    execution_gate,
    reply_func: PrivateChatReplyFunc,
    action: str,
    query: str,
    chat_id: int | None,
    user_id: int | None,
    channel: str,
    cleanup_runner: Callable[[object], str],
    tg,
) -> bool:
    cleanup_service = bot_data.get(tg.CLEANUP_DOWNLOADED_SOURCE_SERVICE_KEY)
    if not isinstance(cleanup_service, tg.CleanupDownloadedSourceService):
        _log_cleanup_service_not_ready(action=action, query=query)
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True
    reply = await run_sync_with_policy(
        execution_gate,
        action,
        lambda: cleanup_runner(cleanup_service),
    )
    await reply_func(reply)
    log_cleanup_private_chat_smoke(
        channel=channel,
        query=query,
        reply_text=reply,
        chat_id=chat_id,
        user_id=user_id,
    )
    return True


async def _handle_bt_batch_confirm_request(
    *,
    bot_data: MutableMapping[str, object],
    execution_gate,
    reply_func: PrivateChatReplyFunc,
    batch_confirm_request,
    chat_id: int | None,
    user_id: int | None,
    channel: str,
    tg,
) -> bool:
    if not batch_confirm_request.selection_text:
        await reply_func("BT 批量确认格式：bt批量确认 1-3")
        return True
    if batch_confirm_request.invalid_selection:
        await reply_func(
            f"BT 批量确认编号格式无效：{batch_confirm_request.selection_text}\n"
            "请使用 1-3 或 2,4,6 这类范围表达。"
        )
        return True
    add_service = bot_data.get(tg.ADD_TO_DOWNLOADER_SERVICE_KEY)
    if not isinstance(add_service, tg.AddToDownloaderService) or chat_id is None:
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True
    downloader_execution, resolution_error = _resolve_bound_downloader_execution(
        bot_data=bot_data,
        role="bt",
        tg=tg,
    )
    if resolution_error is not None:
        await reply_func(resolution_error)
        return True
    reply = await execution_gate.run(
        tg.ACTION_ADD_TO_DOWNLOADER,
        lambda: add_service.add_by_batch_selection(
            chat_id,
            batch_confirm_request.selected_indexes,
            user_id=user_id,
            channel=channel,
            downloader_name=downloader_execution.name if downloader_execution is not None else "",
            downloader_type=downloader_execution.downloader_type if downloader_execution is not None else "transmission",
            download_dir=downloader_execution.download_dir if downloader_execution is not None else "",
            auto_import_enabled=False,
        ),
    )
    await reply_func(reply)
    return True


async def _handle_bt_direct_intent(
    *,
    bot_data: MutableMapping[str, object],
    reply_func: PrivateChatReplyFunc,
    chat_id: int | None,
    query: str,
    tg,
) -> bool:
    cleared_processing_path = clear_bt_processing_path_pending(
        bot_data=bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=tg.BT_PENDING_REPO_KEY,
    )
    if cleared_processing_path is None:
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True
    cleared_raw_bt_destination = clear_raw_bt_destination_pending(
        bot_data=bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=tg.BT_PENDING_REPO_KEY,
    )
    if cleared_raw_bt_destination is None:
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True
    cleared_tmdb_association = clear_bt_tmdb_association_pending(
        bot_data=bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=tg.BT_PENDING_REPO_KEY,
    )
    if cleared_tmdb_association is None:
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True
    cleared_classification = clear_bt_classification_pending(
        bot_data=bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=tg.BT_PENDING_REPO_KEY,
    )
    if cleared_classification is None:
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True
    if not set_bt_processing_path_pending(
        bot_data=bot_data,
        chat_id=chat_id,
        source=query,
        bt_pending_repo_key=tg.BT_PENDING_REPO_KEY,
    ):
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True
    await reply_func(BT_PROCESSING_PATH_PROMPT_TEXT)
    return True


def _resolve_bound_downloader_execution(
    *,
    bot_data: MutableMapping[str, object],
    role: str,
    tg,
):
    return resolve_shared_bound_downloader_execution(
        bot_data=bot_data,
        role=role,
        downloader_role_binding_key=tg.DOWNLOADER_ROLE_BINDING_KEY,
        downloader_instances_key=tg.DOWNLOADER_INSTANCES_KEY,
        config_missing_template=tg.DOWNLOADER_EXECUTION_CONFIG_MISSING_TEMPLATE,
    )


async def _cancel_pending_import_for_frustration(
    *,
    bot_data: MutableMapping[str, object],
    execution_gate,
    reply_func: PrivateChatReplyFunc,
    chat_id: int | None,
    tg,
) -> bool:
    if chat_id is None:
        return False
    import_service = bot_data.get(tg.IMPORT_TO_LIBRARY_SERVICE_KEY)
    if not isinstance(import_service, tg.ImportToLibraryService):
        return False
    cancelled_text = await run_sync_with_policy(
        execution_gate,
        tg.ACTION_CANCEL_PENDING_APPROVAL,
        lambda: import_service.cancel_pending_import(chat_id),
    )
    if cancelled_text is None:
        return False
    await reply_func(cancelled_text)
    return True


async def _cancel_pending_add_for_frustration(
    *,
    bot_data: MutableMapping[str, object],
    execution_gate,
    reply_func: PrivateChatReplyFunc,
    chat_id: int | None,
    tg,
) -> bool:
    if chat_id is None:
        return False
    add_service = bot_data.get(tg.ADD_TO_DOWNLOADER_SERVICE_KEY)
    if not isinstance(add_service, tg.AddToDownloaderService):
        return False
    cancelled_text = await run_sync_with_policy(
        execution_gate,
        tg.ACTION_CANCEL_PENDING_APPROVAL,
        lambda: add_service.cancel_pending_add(chat_id),
    )
    if cancelled_text is None:
        return False
    await reply_func(cancelled_text)
    return True


async def _cancel_pending_job_for_frustration(
    *,
    bot_data: MutableMapping[str, object],
    execution_gate,
    reply_func: PrivateChatReplyFunc,
    chat_id: int | None,
    tg,
) -> bool:
    if chat_id is None:
        return False
    job_repo = bot_data.get(tg.JOB_REPO_KEY)
    if not isinstance(job_repo, tg.JobRepo):
        return False
    try:
        pending_job = job_repo.get_latest_pending_job(chat_id=chat_id)
    except Exception as error:
        _log_pending_job_lookup_failed(chat_id=chat_id, reason=str(error))
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True
    if pending_job is None:
        return False
    if pending_job.workflow_type == tg.WORKFLOW_IMPORT_TO_LIBRARY:
        return await _cancel_pending_import_for_frustration(
            bot_data=bot_data,
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=chat_id,
            tg=tg,
        )
    if pending_job.workflow_type == tg.WORKFLOW_ADD_TO_DOWNLOADER:
        return await _cancel_pending_add_for_frustration(
            bot_data=bot_data,
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=chat_id,
            tg=tg,
        )
    return False


async def _reset_search_state_for_frustration(
    *,
    bot_data: MutableMapping[str, object],
    execution_gate,
    reply_func: PrivateChatReplyFunc,
    chat_id: int | None,
    tg,
) -> bool:
    if chat_id is None:
        return False
    search_service = bot_data.get(tg.SEARCH_SERVICE_KEY)
    if not isinstance(search_service, tg.SearchMediaService):
        return False
    clarification_pending = search_service.is_clarification_pending(chat_id)
    if clarification_pending is None:
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True
    if clarification_pending:
        clarification_cleared = await run_sync_with_policy(
            execution_gate,
            tg.ACTION_RESET_CLARIFICATION,
            lambda: search_service.clear_clarification_pending(chat_id),
        )
        if clarification_cleared:
            await reply_func(tg.CLARIFICATION_RESET_TEXT)
            return True
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True
    has_cached_candidates = search_service.has_cached_candidates(chat_id)
    if has_cached_candidates is None:
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True
    if not has_cached_candidates:
        return False
    candidates_cleared = await run_sync_with_policy(
        execution_gate,
        tg.ACTION_RESET_CANDIDATES,
        lambda: search_service.clear_cached_candidates(chat_id),
    )
    if candidates_cleared:
        await reply_func(tg.FRUSTRATION_RESET_TEXT)
        return True
    await reply_func(tg.SERVICE_NOT_READY_TEXT)
    return True


async def _clear_bt_pending_for_frustration(
    *,
    bot_data: MutableMapping[str, object],
    reply_func: PrivateChatReplyFunc,
    chat_id: int | None,
    tg,
) -> bool:
    for clear_pending, cancelled_text in (
        (clear_raw_bt_destination_pending, tg.RAW_BT_DESTINATION_CANCELLED_TEXT),
        (clear_bt_tmdb_association_pending, tg.BT_TMDB_ASSOCIATION_CANCELLED_TEXT),
        (clear_bt_classification_pending, BT_CLASSIFICATION_CANCELLED_TEXT),
        (clear_bt_processing_path_pending, BT_PROCESSING_PATH_CANCELLED_TEXT),
    ):
        cleared = clear_pending(
            bot_data=bot_data,
            chat_id=chat_id,
            bt_pending_repo_key=tg.BT_PENDING_REPO_KEY,
        )
        if cleared is None:
            await reply_func(tg.SERVICE_NOT_READY_TEXT)
            return True
        if cleared:
            await reply_func(cancelled_text)
            return True
    return False


async def _handle_frustration_text(
    *,
    bot_data: MutableMapping[str, object],
    execution_gate,
    reply_func: PrivateChatReplyFunc,
    chat_id: int | None,
    tg,
) -> bool:
    if await _cancel_pending_job_for_frustration(
        bot_data=bot_data,
        execution_gate=execution_gate,
        reply_func=reply_func,
        chat_id=chat_id,
        tg=tg,
    ):
        return True
    if await _cancel_pending_import_for_frustration(
        bot_data=bot_data,
        execution_gate=execution_gate,
        reply_func=reply_func,
        chat_id=chat_id,
        tg=tg,
    ):
        return True
    if await _cancel_pending_add_for_frustration(
        bot_data=bot_data,
        execution_gate=execution_gate,
        reply_func=reply_func,
        chat_id=chat_id,
        tg=tg,
    ):
        return True
    if await _reset_search_state_for_frustration(
        bot_data=bot_data,
        execution_gate=execution_gate,
        reply_func=reply_func,
        chat_id=chat_id,
        tg=tg,
    ):
        return True
    return await _clear_bt_pending_for_frustration(
        bot_data=bot_data,
        reply_func=reply_func,
        chat_id=chat_id,
        tg=tg,
    )


def _clear_bt_follow_up_conflicts(
    *,
    bot_data: MutableMapping[str, object],
    chat_id: int | None,
    tg,
    clear_classification_pending: bool = False,
) -> bool | None:
    cleared_raw_bt_destination = clear_raw_bt_destination_pending(
        bot_data=bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=tg.BT_PENDING_REPO_KEY,
    )
    if cleared_raw_bt_destination is None:
        return None
    cleared_tmdb_association = clear_bt_tmdb_association_pending(
        bot_data=bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=tg.BT_PENDING_REPO_KEY,
    )
    if cleared_tmdb_association is None:
        return None
    if clear_classification_pending:
        clear_bt_classification_pending(
            bot_data=bot_data,
            chat_id=chat_id,
            bt_pending_repo_key=tg.BT_PENDING_REPO_KEY,
        )
    return True


def _build_media_import_bt_flow_reply(
    *,
    bot_data: MutableMapping[str, object],
    chat_id: int | None,
    source: str,
    media_kind: str | None,
    tg,
) -> str:
    return enter_media_import_bt_flow(
        bot_data=bot_data,
        chat_id=chat_id,
        source=source,
        media_kind=media_kind,
        bt_pending_repo_key=tg.BT_PENDING_REPO_KEY,
        service_not_ready_text=tg.SERVICE_NOT_READY_TEXT,
    )


def _build_pure_bt_flow_reply(
    *,
    bot_data: MutableMapping[str, object],
    chat_id: int | None,
    source: str,
    tg,
) -> str:
    return enter_pure_bt_flow(
        bot_data=bot_data,
        chat_id=chat_id,
        source=source,
        raw_bt_destination_options_key=tg.RAW_BT_DESTINATION_OPTIONS_KEY,
        bt_pending_repo_key=tg.BT_PENDING_REPO_KEY,
        raw_bt_destination_service_not_ready_text=tg.RAW_BT_DESTINATION_SERVICE_NOT_READY_TEXT,
        service_not_ready_text=tg.SERVICE_NOT_READY_TEXT,
    )


async def _handle_bt_processing_path_follow_up(
    *,
    bot_data: MutableMapping[str, object],
    reply_func: PrivateChatReplyFunc,
    chat_id: int | None,
    bt_processing_path_pending: bool,
    bt_processing_path: str | None,
    bt_processing_shortcut: tuple[str, str | None] | None,
    tg,
) -> bool:
    if not bt_processing_path_pending:
        return False
    if bt_processing_path is None and bt_processing_shortcut is None:
        return False
    bt_source = pop_bt_processing_path_pending(
        bot_data=bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=tg.BT_PENDING_REPO_KEY,
    )
    if bt_source is False or not bt_source:
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True
    if _clear_bt_follow_up_conflicts(
        bot_data=bot_data,
        chat_id=chat_id,
        tg=tg,
        clear_classification_pending=True,
    ) is None:
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True
    if bt_processing_path == "media_import":
        await reply_func(
            _build_media_import_bt_flow_reply(
                bot_data=bot_data,
                chat_id=chat_id,
                source=bt_source,
                media_kind=None,
                tg=tg,
            )
        )
        return True
    if bt_processing_path == "pure_bt":
        await reply_func(
            _build_pure_bt_flow_reply(
                bot_data=bot_data,
                chat_id=chat_id,
                source=bt_source,
                tg=tg,
            )
        )
        return True
    if bt_processing_shortcut is None:
        return False
    shortcut_path, shortcut_media_kind = bt_processing_shortcut
    if shortcut_path == "pure_bt":
        await reply_func(
            _build_pure_bt_flow_reply(
                bot_data=bot_data,
                chat_id=chat_id,
                source=bt_source,
                tg=tg,
            )
        )
        return True
    await reply_func(
        _build_media_import_bt_flow_reply(
            bot_data=bot_data,
            chat_id=chat_id,
            source=bt_source,
            media_kind=shortcut_media_kind,
            tg=tg,
        )
    )
    return True


async def _handle_bt_classification_follow_up(
    *,
    bot_data: MutableMapping[str, object],
    reply_func: PrivateChatReplyFunc,
    chat_id: int | None,
    bt_classification_pending: bool,
    bt_classification: str | None,
    tg,
) -> bool:
    if bt_classification is None or not bt_classification_pending:
        return False
    bt_source = pop_bt_classification_pending(
        bot_data=bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=tg.BT_PENDING_REPO_KEY,
    )
    if bt_source is False or not bt_source:
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True
    if _clear_bt_follow_up_conflicts(
        bot_data=bot_data,
        chat_id=chat_id,
        tg=tg,
    ) is None:
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True
    await reply_func(
        _build_media_import_bt_flow_reply(
            bot_data=bot_data,
            chat_id=chat_id,
            source=bt_source,
            media_kind=bt_classification,
            tg=tg,
        )
    )
    return True


async def _handle_bt_tmdb_follow_up(
    *,
    bot_data: MutableMapping[str, object],
    reply_func: PrivateChatReplyFunc,
    query: str,
    chat_id: int | None,
    user_id: int | None,
    tg,
) -> bool:
    bt_tmdb_pending = get_bt_tmdb_association_pending(
        bot_data=bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=tg.BT_PENDING_REPO_KEY,
    )
    if bt_tmdb_pending is False:
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True
    if bt_tmdb_pending is None:
        return False
    reply = await handle_shared_bt_tmdb_association_query(
        query=query,
        pending=bt_tmdb_pending,
        chat_id=chat_id,
        user_id=user_id,
        bot_data=bot_data,
        add_to_downloader_service_key=tg.ADD_TO_DOWNLOADER_SERVICE_KEY,
        clear_pending=lambda: clear_bt_tmdb_association_pending(
            bot_data=bot_data,
            chat_id=chat_id,
            bt_pending_repo_key=tg.BT_PENDING_REPO_KEY,
        ),
        resolve_candidates_lookup=lambda media_kind: resolve_bt_tmdb_candidates_lookup(
            bot_data=bot_data,
            media_kind=media_kind,
            bt_tmdb_movie_candidates_lookup_key=tg.BT_TMDB_MOVIE_CANDIDATES_LOOKUP_KEY,
            bt_tmdb_tv_candidates_lookup_key=tg.BT_TMDB_TV_CANDIDATES_LOOKUP_KEY,
        ),
        resolve_downloader_execution=lambda: _resolve_bound_downloader_execution(
            bot_data=bot_data,
            role="bt",
            tg=tg,
        ),
        log_bt_tmdb_association_error=lambda media_kind, raw_query, error: log_bt_tmdb_association_error(
            media_kind=media_kind,
            query=raw_query,
            error=error,
        ),
        service_not_ready_text=tg.SERVICE_NOT_READY_TEXT,
        bt_tmdb_association_service_not_ready_text=tg.BT_TMDB_ASSOCIATION_SERVICE_NOT_READY_TEXT,
        bt_source_required_text=tg.BT_SOURCE_REQUIRED_TEXT,
    )
    await reply_func(reply)
    return True


async def _handle_raw_bt_destination_follow_up(
    *,
    bot_data: MutableMapping[str, object],
    reply_func: PrivateChatReplyFunc,
    query: str,
    chat_id: int | None,
    user_id: int | None,
    tg,
) -> bool:
    raw_bt_destination_pending = get_raw_bt_destination_pending(
        bot_data=bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=tg.BT_PENDING_REPO_KEY,
    )
    if raw_bt_destination_pending is False:
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True
    if raw_bt_destination_pending is None:
        return False
    reply = await handle_shared_raw_bt_destination_query(
        query=query,
        pending=raw_bt_destination_pending,
        chat_id=chat_id,
        user_id=user_id,
        bot_data=bot_data,
        add_to_downloader_service_key=tg.ADD_TO_DOWNLOADER_SERVICE_KEY,
        search_service_key=tg.SEARCH_SERVICE_KEY,
        clear_pending=lambda: clear_raw_bt_destination_pending(
            bot_data=bot_data,
            chat_id=chat_id,
            bt_pending_repo_key=tg.BT_PENDING_REPO_KEY,
        ),
        resolve_downloader_execution=lambda: _resolve_bound_downloader_execution(
            bot_data=bot_data,
            role="bt",
            tg=tg,
        ),
        log_pure_bt_search_error=lambda pure_bt_query, error: log_pure_bt_search_error(
            query=pure_bt_query,
            error=error,
        ),
        service_not_ready_text=tg.SERVICE_NOT_READY_TEXT,
        bt_source_required_text=tg.BT_SOURCE_REQUIRED_TEXT,
        pure_bt_search_failed_text=tg.PURE_BT_SEARCH_FAILED_TEXT,
        pure_bt_candidate_selected_template=tg.PURE_BT_CANDIDATE_SELECTED_TEMPLATE,
        pure_bt_candidate_not_found_template=tg.PURE_BT_CANDIDATE_NOT_FOUND_TEMPLATE,
    )
    await reply_func(reply)
    return True


async def _handle_bt_pending_reminders(
    *,
    reply_func: PrivateChatReplyFunc,
    bt_processing_path_pending: bool,
    bt_classification_pending: bool,
) -> bool:
    if bt_processing_path_pending:
        await reply_func(BT_PROCESSING_PATH_PENDING_REMINDER_TEXT)
        return True
    if bt_classification_pending:
        await reply_func(BT_CLASSIFICATION_PENDING_REMINDER_TEXT)
        return True
    return False


async def _handle_confirm_query(
    *,
    bot_data: MutableMapping[str, object],
    execution_gate,
    reply_func: PrivateChatReplyFunc,
    confirm_ref: str | None,
    chat_id: int | None,
    user_id: int | None,
    tg,
) -> bool:
    return await handle_shared_confirm_query(
        bot_data=bot_data,
        execution_gate=execution_gate,
        reply_func=reply_func,
        confirm_ref=confirm_ref,
        chat_id=chat_id,
        user_id=user_id,
        tg=tg,
    )


async def _handle_digit_selection_query(
    *,
    bot_data: MutableMapping[str, object],
    execution_gate,
    reply_func: PrivateChatReplyFunc,
    query: str,
    chat_id: int | None,
    user_id: int | None,
    channel: str,
    tg,
) -> bool:
    return await handle_shared_digit_selection_query(
        bot_data=bot_data,
        execution_gate=execution_gate,
        reply_func=reply_func,
        query=query,
        chat_id=chat_id,
        user_id=user_id,
        channel=channel,
        resolve_downloader_execution=lambda: _resolve_bound_downloader_execution(bot_data=bot_data, role="pt", tg=tg),
        tg=tg,
    )


async def _handle_search_query_fallback(
    *,
    bot_data: MutableMapping[str, object],
    execution_gate,
    reply_func: PrivateChatReplyFunc,
    query: str,
    chat_id: int | None,
    channel: str,
    bt_processing_path_pending: bool,
    bt_classification_pending: bool,
    tg,
) -> bool:
    search_service = bot_data.get(tg.SEARCH_SERVICE_KEY)
    if not isinstance(search_service, tg.SearchMediaService):
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True
    if await _handle_bt_pending_reminders(
        reply_func=reply_func,
        bt_processing_path_pending=bt_processing_path_pending,
        bt_classification_pending=bt_classification_pending,
    ):
        return True
    reply = await execution_gate.run(
        tg.ACTION_SEARCH_MEDIA,
        lambda: search_with_reactive_recovery(
            search_service=search_service,
            query=query,
            chat_id=chat_id,
            channel=channel,
            safe_text=tg.LLM_PHYSICAL_FAILURE_SAFE_TEXT,
        ),
    )
    await reply_func(reply)
    return True


async def dispatch_private_chat_text(
    *,
    query: str,
    reply_func: Callable[[str], Awaitable[object]],
    chat_id: int | None,
    user_id: int | None,
    channel: str = "unknown",
    bot_data: MutableMapping[str, object],
) -> None:
    await handle_private_chat_query_text(
        query=query,
        reply_func=reply_func,
        chat_id=chat_id,
        user_id=user_id,
        channel=channel,
        bot_data=bot_data,
    )


async def handle_private_chat_query_text(
    *,
    query: str,
    reply_func: Callable[[str], Awaitable[object]],
    chat_id: int | None,
    user_id: int | None,
    channel: str = "unknown",
    bot_data: MutableMapping[str, object],
) -> None:
    tg = telegram_runtime
    context = _PrivateChatRuntimeContext(
        application=_PrivateChatRuntimeApplication(bot_data=bot_data),
    )
    execution_gate = resolve_execution_gate(
        bot_data=bot_data,
        execution_gate_key=tg.EXECUTION_GATE_KEY,
    )
    reply_func = prepare_private_chat_reply_with_trace(
        bot_data=bot_data,
        reply_func=reply_func,
        channel=channel,
        chat_id=chat_id,
        user_id=user_id,
        query=query,
    )
    if is_frustration_text(query):
        if await _handle_frustration_text(
            bot_data=bot_data,
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=chat_id,
            tg=tg,
        ):
            return

    if is_bt_direct_intent(query):
        if await _handle_bt_direct_intent(
            bot_data=bot_data,
            reply_func=reply_func,
            chat_id=chat_id,
            query=query,
            tg=tg,
        ):
            return
        return

    if await handle_shared_personal_wechat_login_query(
        query=query,
        bot_data=bot_data,
        execution_gate=execution_gate,
        reply_func=reply_func,
        chat_id=chat_id,
        tg=tg,
    ):
        return

    bt_read_only_query = extract_bt_read_only_query(query)
    if bt_read_only_query:
        if await _handle_bt_read_only_request(
            bot_data=bot_data,
            execution_gate=execution_gate,
            reply_func=reply_func,
            search_runner=lambda search_service: search_service.search_bt_read_only_and_format(bt_read_only_query),
            helper_query=bt_read_only_query,
            tg=tg,
        ):
            return
        return

    bt_batch_preview_request = extract_bt_batch_preview_request(query)
    if bt_batch_preview_request is not None:
        if await _handle_bt_read_only_request(
            bot_data=bot_data,
            execution_gate=execution_gate,
            reply_func=reply_func,
            search_runner=lambda search_service: search_service.search_bt_batch_preview_and_format_for_chat(
                bt_batch_preview_request,
                chat_id=chat_id,
            ),
            helper_query=bt_batch_preview_request.query,
            tg=tg,
        ):
            return
        return

    bt_batch_confirm_request = extract_bt_batch_confirm_request(query)
    if bt_batch_confirm_request is not None:
        if await _handle_bt_batch_confirm_request(
            bot_data=bot_data,
            execution_gate=execution_gate,
            reply_func=reply_func,
            batch_confirm_request=bt_batch_confirm_request,
            chat_id=chat_id,
            user_id=user_id,
            channel=channel,
            tg=tg,
        ):
            return
        return

    bt_classification = parse_bt_classification_choice(query)
    bt_processing_path = parse_bt_processing_path_choice(query)
    bt_processing_shortcut = parse_bt_processing_path_legacy_shortcut(query)
    bt_processing_path_pending = is_bt_processing_path_pending(
        bot_data=bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=tg.BT_PENDING_REPO_KEY,
    )
    if bt_processing_path_pending is None:
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return
    bt_classification_pending = is_bt_classification_pending(
        bot_data=bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=tg.BT_PENDING_REPO_KEY,
    )
    if bt_classification_pending is None:
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return
    if await _handle_bt_processing_path_follow_up(
        bot_data=bot_data,
        reply_func=reply_func,
        chat_id=chat_id,
        bt_processing_path_pending=bt_processing_path_pending,
        bt_processing_path=bt_processing_path,
        bt_processing_shortcut=bt_processing_shortcut,
        tg=tg,
    ):
        return

    if await _handle_bt_classification_follow_up(
        bot_data=bot_data,
        reply_func=reply_func,
        chat_id=chat_id,
        bt_classification_pending=bt_classification_pending,
        bt_classification=bt_classification,
        tg=tg,
    ):
        return

    if await handle_shared_status_query(
        query=query,
        bot_data=bot_data,
        execution_gate=execution_gate,
        reply_func=reply_func,
        chat_id=chat_id,
        channel=channel,
        tg=tg,
    ):
        return

    watchlist_command = tg.parse_watchlist_query(query)
    if watchlist_command is not None:
        watchlist_service = bot_data.get(tg.MANAGE_WATCHLIST_SERVICE_KEY)
        if not isinstance(watchlist_service, tg.ManageWatchlistService):
            await reply_func(tg.SERVICE_NOT_READY_TEXT)
            return
        reply = await run_sync_with_policy(
            execution_gate,
            watchlist_policy_action(watchlist_command.action),
            lambda: watchlist_service.handle(
                watchlist_command,
                chat_id=chat_id,
            ),
        )
        await reply_func(reply)
        return

    bt_subscription_command = tg.parse_bt_subscription_query(query)
    if bt_subscription_command is not None:
        bt_subscription_service = bot_data.get(tg.MANAGE_BT_SUBSCRIPTION_SERVICE_KEY)
        if not isinstance(bt_subscription_service, tg.ManageBtSubscriptionService):
            await reply_func(tg.SERVICE_NOT_READY_TEXT)
            return
        if bt_subscription_command.action == "run":
            downloader_execution, resolution_error = _resolve_bound_downloader_execution(
                bot_data=bot_data,
                role="bt",
                tg=tg,
            )
            if resolution_error is not None:
                await reply_func(resolution_error)
                return
            if downloader_execution is None:
                await reply_func(tg.SERVICE_NOT_READY_TEXT)
                return
            reply = await execution_gate.run(
                bt_subscription_policy_action(bt_subscription_command),
                lambda: bt_subscription_service.run_once(
                    chat_id=chat_id,
                    user_id=user_id,
                    dispatch_context=tg.BtSubscriptionDispatchContext(
                        downloader_name=downloader_execution.name,
                        downloader_type=downloader_execution.downloader_type,
                        download_dir=downloader_execution.download_dir,
                    ),
                ),
            )
            await reply_func(reply)
            return
        reply = await run_sync_with_policy(
            execution_gate,
            bt_subscription_policy_action(bt_subscription_command),
            lambda: bt_subscription_service.handle(
                bt_subscription_command,
                chat_id=chat_id,
            ),
        )
        await reply_func(reply)
        return

    import_ref = tg.parse_import_query(query)
    if import_ref is not None:
        import_service = bot_data.get(tg.IMPORT_TO_LIBRARY_SERVICE_KEY)
        if not isinstance(import_service, tg.ImportToLibraryService):
            await reply_func(tg.SERVICE_NOT_READY_TEXT)
            return
        reply = await execution_gate.run(
            tg.ACTION_IMPORT_TO_LIBRARY,
            lambda: import_service.import_by_task_ref(
                import_ref,
                chat_id=chat_id,
                user_id=user_id,
            ),
        )
        await reply_func(reply)
        return

    cleanup_inspect_ref = tg.parse_cleanup_inspect_query(query)
    if cleanup_inspect_ref is not None:
        if await _handle_cleanup_request(
            bot_data=bot_data,
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=chat_id,
            user_id=user_id,
            channel=channel,
            action=tg.ACTION_CLEANUP_INSPECT,
            query=query,
            cleanup_runner=lambda cleanup_service: cleanup_service.inspect_by_task_ref(
                cleanup_inspect_ref,
                chat_id=chat_id,
            ),
            tg=tg,
        ):
            return

    cleanup_ref = tg.parse_cleanup_query(query)
    if cleanup_ref is not None:
        if await _handle_cleanup_request(
            bot_data=bot_data,
            execution_gate=execution_gate,
            reply_func=reply_func,
            action=tg.ACTION_CLEANUP_DOWNLOADER_SOURCE,
            query=query,
            chat_id=chat_id,
            user_id=user_id,
            channel=channel,
            cleanup_runner=lambda cleanup_service: cleanup_service.cleanup_by_task_ref(
                cleanup_ref,
                chat_id=chat_id,
            ),
            tg=tg,
        ):
            return

    if await _handle_confirm_query(
        bot_data=bot_data,
        execution_gate=execution_gate,
        reply_func=reply_func,
        confirm_ref=tg.parse_confirm_query(query),
        chat_id=chat_id,
        user_id=user_id,
        tg=tg,
    ):
        return

    if await _handle_bt_tmdb_follow_up(
        bot_data=bot_data,
        reply_func=reply_func,
        query=query,
        chat_id=chat_id,
        user_id=user_id,
        tg=tg,
    ):
        return

    if await _handle_raw_bt_destination_follow_up(
        bot_data=bot_data,
        reply_func=reply_func,
        query=query,
        chat_id=chat_id,
        user_id=user_id,
        tg=tg,
    ):
        return

    if await _handle_digit_selection_query(
        bot_data=bot_data,
        execution_gate=execution_gate,
        reply_func=reply_func,
        query=query,
        chat_id=chat_id,
        user_id=user_id,
        channel=channel,
        tg=tg,
    ):
        return

    await _handle_search_query_fallback(
        bot_data=bot_data,
        execution_gate=execution_gate,
        reply_func=reply_func,
        query=query,
        chat_id=chat_id,
        channel=channel,
        bt_processing_path_pending=bt_processing_path_pending,
        bt_classification_pending=bt_classification_pending,
        tg=tg,
    )

from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping
from dataclasses import dataclass
from pathlib import Path

from app.bot import telegram_bot as telegram_runtime
from app.bot.cleanup_smoke_logging import log_cleanup_private_chat_smoke
from app.trace_logging import TRACE_LOG_PATH_BOT_DATA_KEY, log_trace_event

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


def _log_confirm_job_lookup_failed(*, chat_id: int | None, task_ref: str, reason: str) -> None:
    print(
        f"\033[31m[确认关联任务查询失败]\033[0m chat_id={chat_id if chat_id is not None else '-'} "
        f"task_ref={task_ref.strip() or '-'} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 SQLite 是否可读，以及 jobs 表和当前确认任务关联记录是否正常。"
    )


def _resolve_trace_log_path(bot_data: MutableMapping[str, object]) -> Path | None:
    trace_log_path = bot_data.get(TRACE_LOG_PATH_BOT_DATA_KEY)
    if isinstance(trace_log_path, Path):
        return trace_log_path
    return None


def _log_private_chat_inbound(
    *,
    trace_log_path: Path | None,
    channel: str,
    chat_id: int | None,
    user_id: int | None,
    query: str,
) -> None:
    log_trace_event(
        scope="private_chat",
        event="inbound",
        result="received",
        log_path=trace_log_path,
        channel=channel,
        action="query",
        chat_id=chat_id,
        user_id=user_id,
        query=query,
    )


def _wrap_reply_with_trace(
    *,
    reply_func: PrivateChatReplyFunc,
    trace_log_path: Path | None,
    channel: str,
    chat_id: int | None,
    user_id: int | None,
    query: str,
) -> PrivateChatReplyFunc:
    async def reply_with_trace(reply_text: str) -> object:
        result = await reply_func(reply_text)
        log_trace_event(
            scope="private_chat",
            event="reply",
            result="sent",
            log_path=trace_log_path,
            channel=channel,
            action="reply",
            chat_id=chat_id,
            user_id=user_id,
            query=query,
            reply_text=reply_text,
        )
        return result

    return reply_with_trace


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
    execution_gate = tg._resolve_execution_gate(context)
    trace_log_path = _resolve_trace_log_path(bot_data)
    _log_private_chat_inbound(
        trace_log_path=trace_log_path,
        channel=channel,
        chat_id=chat_id,
        user_id=user_id,
        query=query,
    )
    reply_func = _wrap_reply_with_trace(
        reply_func=reply_func,
        trace_log_path=trace_log_path,
        channel=channel,
        chat_id=chat_id,
        user_id=user_id,
        query=query,
    )
    if tg._is_frustration_text(query):
        if chat_id is not None:
            job_repo = bot_data.get(tg.JOB_REPO_KEY)
            if isinstance(job_repo, tg.JobRepo):
                pending_job_lookup_failed = False
                try:
                    pending_job = job_repo.get_latest_pending_job(chat_id=chat_id)
                except Exception as error:
                    _log_pending_job_lookup_failed(chat_id=chat_id, reason=str(error))
                    pending_job = None
                    pending_job_lookup_failed = True
                if pending_job is not None:
                    if pending_job.workflow_type == tg.WORKFLOW_IMPORT_TO_LIBRARY:
                        import_service = bot_data.get(tg.IMPORT_TO_LIBRARY_SERVICE_KEY)
                        if isinstance(import_service, tg.ImportToLibraryService):
                            cancelled_text = await tg._run_sync_with_policy(
                                execution_gate,
                                tg.ACTION_CANCEL_PENDING_APPROVAL,
                                lambda: import_service.cancel_pending_import(chat_id),
                            )
                            if cancelled_text is not None:
                                await reply_func(cancelled_text)
                                return
                    if pending_job.workflow_type == tg.WORKFLOW_ADD_TO_DOWNLOADER:
                        add_service = bot_data.get(tg.ADD_TO_DOWNLOADER_SERVICE_KEY)
                        if isinstance(add_service, tg.AddToDownloaderService):
                            cancelled_text = await tg._run_sync_with_policy(
                                execution_gate,
                                tg.ACTION_CANCEL_PENDING_APPROVAL,
                                lambda: add_service.cancel_pending_add(chat_id),
                            )
                            if cancelled_text is not None:
                                await reply_func(cancelled_text)
                                return
                if pending_job_lookup_failed:
                    await reply_func(tg.SERVICE_NOT_READY_TEXT)
                    return

        import_service = bot_data.get(tg.IMPORT_TO_LIBRARY_SERVICE_KEY)
        if isinstance(import_service, tg.ImportToLibraryService) and chat_id is not None:
            cancelled_text = await tg._run_sync_with_policy(
                execution_gate,
                tg.ACTION_CANCEL_PENDING_APPROVAL,
                lambda: import_service.cancel_pending_import(chat_id),
            )
            if cancelled_text is not None:
                await reply_func(cancelled_text)
                return

        add_service = bot_data.get(tg.ADD_TO_DOWNLOADER_SERVICE_KEY)
        if isinstance(add_service, tg.AddToDownloaderService) and chat_id is not None:
            cancelled_text = await tg._run_sync_with_policy(
                execution_gate,
                tg.ACTION_CANCEL_PENDING_APPROVAL,
                lambda: add_service.cancel_pending_add(chat_id),
            )
            if cancelled_text is not None:
                await reply_func(cancelled_text)
                return

        search_service = bot_data.get(tg.SEARCH_SERVICE_KEY)
        if isinstance(search_service, tg.SearchMediaService) and chat_id is not None:
            clarification_pending = search_service.is_clarification_pending(chat_id)
            if clarification_pending is None:
                await reply_func(tg.SERVICE_NOT_READY_TEXT)
                return
            if clarification_pending:
                clarification_cleared = await tg._run_sync_with_policy(
                    execution_gate,
                    tg.ACTION_RESET_CLARIFICATION,
                    lambda: search_service.clear_clarification_pending(chat_id),
                )
                if clarification_cleared:
                    await reply_func(tg.CLARIFICATION_RESET_TEXT)
                    return
                await reply_func(tg.SERVICE_NOT_READY_TEXT)
                return
            has_cached_candidates = search_service.has_cached_candidates(chat_id)
            if has_cached_candidates is None:
                await reply_func(tg.SERVICE_NOT_READY_TEXT)
                return
            if has_cached_candidates:
                candidates_cleared = await tg._run_sync_with_policy(
                    execution_gate,
                    tg.ACTION_RESET_CANDIDATES,
                    lambda: search_service.clear_cached_candidates(chat_id),
                )
                if candidates_cleared:
                    await reply_func(tg.FRUSTRATION_RESET_TEXT)
                    return
                await reply_func(tg.SERVICE_NOT_READY_TEXT)
                return
        cleared_raw_bt_destination = tg._clear_raw_bt_destination_pending(context=context, chat_id=chat_id)
        if cleared_raw_bt_destination is None:
            await reply_func(tg.SERVICE_NOT_READY_TEXT)
            return
        if cleared_raw_bt_destination:
            await reply_func(tg.RAW_BT_DESTINATION_CANCELLED_TEXT)
            return
        cleared_tmdb_association = tg._clear_bt_tmdb_association_pending(context=context, chat_id=chat_id)
        if cleared_tmdb_association is None:
            await reply_func(tg.SERVICE_NOT_READY_TEXT)
            return
        if cleared_tmdb_association:
            await reply_func(tg.BT_TMDB_ASSOCIATION_CANCELLED_TEXT)
            return
        cleared_classification = tg._clear_bt_classification_pending(context=context, chat_id=chat_id)
        if cleared_classification is None:
            await reply_func(tg.SERVICE_NOT_READY_TEXT)
            return
        if cleared_classification:
            await reply_func(tg.BT_CLASSIFICATION_CANCELLED_TEXT)
            return
        cleared_processing_path = tg._clear_bt_processing_path_pending(context=context, chat_id=chat_id)
        if cleared_processing_path is None:
            await reply_func(tg.SERVICE_NOT_READY_TEXT)
            return
        if cleared_processing_path:
            await reply_func(tg.BT_PROCESSING_PATH_CANCELLED_TEXT)
            return

    if tg._is_bt_direct_intent(query):
        cleared_processing_path = tg._clear_bt_processing_path_pending(context=context, chat_id=chat_id)
        if cleared_processing_path is None:
            await reply_func(tg.SERVICE_NOT_READY_TEXT)
            return
        cleared_raw_bt_destination = tg._clear_raw_bt_destination_pending(context=context, chat_id=chat_id)
        if cleared_raw_bt_destination is None:
            await reply_func(tg.SERVICE_NOT_READY_TEXT)
            return
        cleared_tmdb_association = tg._clear_bt_tmdb_association_pending(context=context, chat_id=chat_id)
        if cleared_tmdb_association is None:
            await reply_func(tg.SERVICE_NOT_READY_TEXT)
            return
        cleared_classification = tg._clear_bt_classification_pending(context=context, chat_id=chat_id)
        if cleared_classification is None:
            await reply_func(tg.SERVICE_NOT_READY_TEXT)
            return
        if not tg._set_bt_processing_path_pending(
            context=context,
            chat_id=chat_id,
            source=query,
        ):
            await reply_func(tg.SERVICE_NOT_READY_TEXT)
            return
        await reply_func(tg.BT_PROCESSING_PATH_PROMPT_TEXT)
        return

    if tg.parse_personal_wechat_login_query(query):
        personal_wechat_login_service = bot_data.get(tg.PERSONAL_WECHAT_LOGIN_SERVICE_KEY)
        telegram_send_media_func = bot_data.get(tg.TELEGRAM_SEND_MEDIA_FUNC_KEY)
        telegram_send_text_func = bot_data.get(tg.TELEGRAM_SEND_TEXT_FUNC_KEY)
        if (
            not isinstance(personal_wechat_login_service, tg.PersonalWeChatLoginService)
            or not callable(telegram_send_media_func)
            or chat_id is None
        ):
            await reply_func(tg.SERVICE_NOT_READY_TEXT)
            return
        reply = await execution_gate.run(
            tg.ACTION_PERSONAL_WECHAT_LOGIN,
            lambda: personal_wechat_login_service.start_login(
                chat_id=chat_id,
                send_media_func=telegram_send_media_func,
                send_text_func=telegram_send_text_func if callable(telegram_send_text_func) else None,
            ),
        )
        await reply_func(reply)
        return

    bt_read_only_query = tg._extract_bt_read_only_query(query)
    if bt_read_only_query:
        search_service = bot_data.get(tg.SEARCH_SERVICE_KEY)
        if not isinstance(search_service, tg.SearchMediaService):
            await reply_func(tg.SERVICE_NOT_READY_TEXT)
            return
        try:
            reply = await execution_gate.run(
                tg.ACTION_BT_READ_ONLY_HELPER,
                lambda: search_service.search_bt_read_only_and_format(bt_read_only_query),
            )
        except Exception as error:
            tg._log_bt_read_only_helper_error(query=bt_read_only_query, error=error)
            await reply_func(tg.BT_READ_ONLY_HELPER_FAILED_TEXT)
            return
        await reply_func(reply)
        return

    bt_batch_preview_request = tg._extract_bt_batch_preview_request(query)
    if bt_batch_preview_request is not None:
        search_service = bot_data.get(tg.SEARCH_SERVICE_KEY)
        if not isinstance(search_service, tg.SearchMediaService):
            await reply_func(tg.SERVICE_NOT_READY_TEXT)
            return
        try:
            reply = await execution_gate.run(
                tg.ACTION_BT_READ_ONLY_HELPER,
                lambda: search_service.search_bt_batch_preview_and_format_for_chat(
                    bt_batch_preview_request,
                    chat_id=chat_id,
                ),
            )
        except Exception as error:
            tg._log_bt_read_only_helper_error(query=bt_batch_preview_request.query, error=error)
            await reply_func(tg.BT_READ_ONLY_HELPER_FAILED_TEXT)
            return
        await reply_func(reply)
        return

    bt_batch_confirm_request = tg._extract_bt_batch_confirm_request(query)
    if bt_batch_confirm_request is not None:
        if not bt_batch_confirm_request.selection_text:
            await reply_func("BT 批量确认格式：bt批量确认 1-3")
            return
        if bt_batch_confirm_request.invalid_selection:
            await reply_func(
                f"BT 批量确认编号格式无效：{bt_batch_confirm_request.selection_text}\n"
                "请使用 1-3 或 2,4,6 这类范围表达。"
            )
            return
        add_service = bot_data.get(tg.ADD_TO_DOWNLOADER_SERVICE_KEY)
        if not isinstance(add_service, tg.AddToDownloaderService):
            await reply_func(tg.SERVICE_NOT_READY_TEXT)
            return
        if chat_id is None:
            await reply_func(tg.SERVICE_NOT_READY_TEXT)
            return
        downloader_execution, resolution_error = tg._resolve_bound_downloader_execution(context=context, role="bt")
        if resolution_error is not None:
            await reply_func(resolution_error)
            return
        reply = await execution_gate.run(
            tg.ACTION_ADD_TO_DOWNLOADER,
            lambda: add_service.add_by_batch_selection(
                chat_id,
                bt_batch_confirm_request.selected_indexes,
                user_id=user_id,
                channel=channel,
                downloader_name=downloader_execution.name if downloader_execution is not None else "",
                downloader_type=downloader_execution.downloader_type if downloader_execution is not None else "transmission",
                download_dir=downloader_execution.download_dir if downloader_execution is not None else "",
                auto_import_enabled=False,
            ),
        )
        await reply_func(reply)
        return

    bt_classification = tg._parse_bt_classification_choice(query)
    bt_processing_path = tg._parse_bt_processing_path_choice(query)
    bt_processing_shortcut = tg._parse_bt_processing_path_legacy_shortcut(query)
    bt_processing_path_pending = tg._is_bt_processing_path_pending(context=context, chat_id=chat_id)
    if bt_processing_path_pending is None:
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return
    bt_classification_pending = tg._is_bt_classification_pending(context=context, chat_id=chat_id)
    if bt_classification_pending is None:
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return
    if bt_processing_path_pending and (
        bt_processing_path is not None or bt_processing_shortcut is not None
    ):
        bt_source = tg._pop_bt_processing_path_pending(context=context, chat_id=chat_id)
        if bt_source is False or not bt_source:
            await reply_func(tg.SERVICE_NOT_READY_TEXT)
            return
        cleared_raw_bt_destination = tg._clear_raw_bt_destination_pending(context=context, chat_id=chat_id)
        if cleared_raw_bt_destination is None:
            await reply_func(tg.SERVICE_NOT_READY_TEXT)
            return
        cleared_tmdb_association = tg._clear_bt_tmdb_association_pending(context=context, chat_id=chat_id)
        if cleared_tmdb_association is None:
            await reply_func(tg.SERVICE_NOT_READY_TEXT)
            return
        tg._clear_bt_classification_pending(context=context, chat_id=chat_id)
        if bt_processing_path == "media_import":
            await reply_func(
                tg._enter_media_import_bt_flow(
                    context=context,
                    chat_id=chat_id,
                    source=bt_source,
                )
            )
            return
        if bt_processing_path == "pure_bt":
            await reply_func(
                tg._enter_pure_bt_flow(
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
                    tg._enter_pure_bt_flow(
                        context=context,
                        chat_id=chat_id,
                        source=bt_source,
                    )
                )
                return
            await reply_func(
                tg._enter_media_import_bt_flow(
                    context=context,
                    chat_id=chat_id,
                    source=bt_source,
                    media_kind=shortcut_media_kind,
                )
            )
            return

    if bt_classification is not None and bt_classification_pending:
        bt_source = tg._pop_bt_classification_pending(context=context, chat_id=chat_id)
        if bt_source is False or not bt_source:
            await reply_func(tg.SERVICE_NOT_READY_TEXT)
            return
        cleared_raw_bt_destination = tg._clear_raw_bt_destination_pending(context=context, chat_id=chat_id)
        if cleared_raw_bt_destination is None:
            await reply_func(tg.SERVICE_NOT_READY_TEXT)
            return
        cleared_tmdb_association = tg._clear_bt_tmdb_association_pending(context=context, chat_id=chat_id)
        if cleared_tmdb_association is None:
            await reply_func(tg.SERVICE_NOT_READY_TEXT)
            return
        await reply_func(
            tg._enter_media_import_bt_flow(
                context=context,
                chat_id=chat_id,
                source=bt_source,
                media_kind=bt_classification,
            )
        )
        return

    task_ref = tg.parse_status_query(query)
    if task_ref is not None:
        status_service = bot_data.get(tg.GET_DOWNLOAD_STATUS_SERVICE_KEY)
        if not isinstance(status_service, tg.GetDownloadStatusService):
            await reply_func(tg.SERVICE_NOT_READY_TEXT)
            return
        reply = await execution_gate.run(
            tg.ACTION_GET_DOWNLOAD_STATUS,
            lambda: status_service.get_status_text(task_ref, chat_id=chat_id, channel=channel),
        )
        await reply_func(reply)
        return

    watchlist_command = tg.parse_watchlist_query(query)
    if watchlist_command is not None:
        watchlist_service = bot_data.get(tg.MANAGE_WATCHLIST_SERVICE_KEY)
        if not isinstance(watchlist_service, tg.ManageWatchlistService):
            await reply_func(tg.SERVICE_NOT_READY_TEXT)
            return
        reply = await tg._run_sync_with_policy(
            execution_gate,
            tg._watchlist_policy_action(watchlist_command.action),
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
            downloader_execution, resolution_error = tg._resolve_bound_downloader_execution(context=context, role="bt")
            if resolution_error is not None:
                await reply_func(resolution_error)
                return
            if downloader_execution is None:
                await reply_func(tg.SERVICE_NOT_READY_TEXT)
                return
            reply = await execution_gate.run(
                tg._bt_subscription_policy_action(bt_subscription_command),
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
        reply = await tg._run_sync_with_policy(
            execution_gate,
            tg._bt_subscription_policy_action(bt_subscription_command),
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
        cleanup_service = bot_data.get(tg.CLEANUP_DOWNLOADED_SOURCE_SERVICE_KEY)
        if not isinstance(cleanup_service, tg.CleanupDownloadedSourceService):
            tg._log_cleanup_service_not_ready(action="cleanup_inspect", query=query)
            await reply_func(tg.SERVICE_NOT_READY_TEXT)
            return
        reply = await tg._run_sync_with_policy(
            execution_gate,
            tg.ACTION_CLEANUP_INSPECT,
            lambda: cleanup_service.inspect_by_task_ref(
                cleanup_inspect_ref,
                chat_id=chat_id,
            ),
        )
        await reply_func(reply)
        log_cleanup_private_chat_smoke(
            channel="telegram",
            query=query,
            reply_text=reply,
            chat_id=chat_id,
            user_id=user_id,
        )
        return

    cleanup_ref = tg.parse_cleanup_query(query)
    if cleanup_ref is not None:
        cleanup_service = bot_data.get(tg.CLEANUP_DOWNLOADED_SOURCE_SERVICE_KEY)
        if not isinstance(cleanup_service, tg.CleanupDownloadedSourceService):
            tg._log_cleanup_service_not_ready(action="cleanup", query=query)
            await reply_func(tg.SERVICE_NOT_READY_TEXT)
            return
        reply = await tg._run_sync_with_policy(
            execution_gate,
            tg.ACTION_CLEANUP_DOWNLOADER_SOURCE,
            lambda: cleanup_service.cleanup_by_task_ref(
                cleanup_ref,
                chat_id=chat_id,
            ),
        )
        await reply_func(reply)
        log_cleanup_private_chat_smoke(
            channel="telegram",
            query=query,
            reply_text=reply,
            chat_id=chat_id,
            user_id=user_id,
        )
        return

    confirm_ref = tg.parse_confirm_query(query)
    if confirm_ref is not None:
        if chat_id is not None and confirm_ref:
            job_repo = bot_data.get(tg.JOB_REPO_KEY)
            if isinstance(job_repo, tg.JobRepo):
                matched_job_lookup_failed = False
                try:
                    matched_job = job_repo.get_job_for_chat_ref(chat_id=chat_id, task_ref=confirm_ref)
                except Exception as error:
                    _log_confirm_job_lookup_failed(
                        chat_id=chat_id,
                        task_ref=confirm_ref,
                        reason=str(error),
                    )
                    matched_job = None
                    matched_job_lookup_failed = True
                if matched_job is not None and matched_job.workflow_type == tg.WORKFLOW_ADD_TO_DOWNLOADER:
                    add_service = bot_data.get(tg.ADD_TO_DOWNLOADER_SERVICE_KEY)
                    if not isinstance(add_service, tg.AddToDownloaderService):
                        await reply_func(tg.SERVICE_NOT_READY_TEXT)
                        return
                    reply = await execution_gate.run(
                        tg.ACTION_CONFIRM_ADD_TO_DOWNLOADER,
                        lambda: add_service.confirm_add_by_task_ref(
                            confirm_ref,
                            chat_id=chat_id,
                            user_id=user_id,
                        ),
                    )
                    await reply_func(reply)
                    return
                if matched_job is not None and matched_job.workflow_type == tg.WORKFLOW_IMPORT_TO_LIBRARY:
                    import_service = bot_data.get(tg.IMPORT_TO_LIBRARY_SERVICE_KEY)
                    if not isinstance(import_service, tg.ImportToLibraryService):
                        await reply_func(tg.SERVICE_NOT_READY_TEXT)
                        return
                    reply = await execution_gate.run(
                        tg.ACTION_CONFIRM_IMPORT_TO_LIBRARY,
                        lambda: import_service.confirm_import_by_task_ref(
                            confirm_ref,
                            chat_id=chat_id,
                            user_id=user_id,
                        ),
                        )
                    await reply_func(reply)
                    return
                if matched_job_lookup_failed:
                    await reply_func(tg.SERVICE_NOT_READY_TEXT)
                    return

        add_service = bot_data.get(tg.ADD_TO_DOWNLOADER_SERVICE_KEY)
        has_pending_add: bool | None = False
        if isinstance(add_service, tg.AddToDownloaderService) and chat_id is not None:
            has_pending_add = add_service.has_pending_add(chat_id, confirm_ref)
        if has_pending_add is None:
            await reply_func(tg.SERVICE_NOT_READY_TEXT)
            return
        if isinstance(add_service, tg.AddToDownloaderService) and chat_id is not None and has_pending_add:
            reply = await execution_gate.run(
                tg.ACTION_CONFIRM_ADD_TO_DOWNLOADER,
                lambda: add_service.confirm_add_by_task_ref(
                    confirm_ref,
                    chat_id=chat_id,
                    user_id=user_id,
                ),
            )
            await reply_func(reply)
            return

        import_service = bot_data.get(tg.IMPORT_TO_LIBRARY_SERVICE_KEY)
        if not isinstance(import_service, tg.ImportToLibraryService):
            await reply_func(tg.SERVICE_NOT_READY_TEXT)
            return
        reply = await execution_gate.run(
            tg.ACTION_CONFIRM_IMPORT_TO_LIBRARY,
            lambda: import_service.confirm_import_by_task_ref(
                confirm_ref,
                chat_id=chat_id,
                user_id=user_id,
            ),
        )
        await reply_func(reply)
        return

    bt_tmdb_pending = tg._get_bt_tmdb_association_pending(context=context, chat_id=chat_id)
    if bt_tmdb_pending is False:
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return
    if bt_tmdb_pending is not None:
        reply = await tg._handle_bt_tmdb_association_query(
            query=query,
            pending=bt_tmdb_pending,
            chat_id=chat_id,
            user_id=user_id,
            context=context,
        )
        await reply_func(reply)
        return

    raw_bt_destination_pending = tg._get_raw_bt_destination_pending(context=context, chat_id=chat_id)
    if raw_bt_destination_pending is False:
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return
    if raw_bt_destination_pending is not None:
        reply = await tg._handle_raw_bt_destination_query(
            query=query,
            pending=raw_bt_destination_pending,
            chat_id=chat_id,
            user_id=user_id,
            context=context,
        )
        await reply_func(reply)
        return

    if query.isdigit():
        search_service = bot_data.get(tg.SEARCH_SERVICE_KEY)
        if isinstance(search_service, tg.SearchMediaService) and chat_id is not None:
            clarification_pending = search_service.is_clarification_pending(chat_id)
            if clarification_pending is None:
                await reply_func(tg.SERVICE_NOT_READY_TEXT)
                return
            if clarification_pending:
                await reply_func(tg.CLARIFICATION_SELECTION_BLOCKED_TEXT)
                return

        add_service = bot_data.get(tg.ADD_TO_DOWNLOADER_SERVICE_KEY)
        if not isinstance(add_service, tg.AddToDownloaderService):
            await reply_func(tg.SERVICE_NOT_READY_TEXT)
            return

        if chat_id is None:
            await reply_func(tg.SERVICE_NOT_READY_TEXT)
            return
        downloader_execution, resolution_error = tg._resolve_bound_downloader_execution(context=context, role="pt")
        if resolution_error is not None:
            await reply_func(resolution_error)
            return
        reply = await execution_gate.run(
            tg.ACTION_ADD_TO_DOWNLOADER,
            lambda: add_service.add_by_selection(
                chat_id,
                query,
                user_id=user_id,
                channel=channel,
                downloader_name=downloader_execution.name if downloader_execution is not None else "",
                downloader_type=downloader_execution.downloader_type if downloader_execution is not None else "transmission",
                download_dir=downloader_execution.download_dir if downloader_execution is not None else "",
            ),
        )
        await reply_func(reply)
        return

    search_service = bot_data.get(tg.SEARCH_SERVICE_KEY)
    if not isinstance(search_service, tg.SearchMediaService):
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return

    if bt_processing_path_pending:
        await reply_func(tg.BT_PROCESSING_PATH_PENDING_REMINDER_TEXT)
        return

    if bt_classification_pending:
        await reply_func(tg.BT_CLASSIFICATION_PENDING_REMINDER_TEXT)
        return

    reply = await execution_gate.run(
        tg.ACTION_SEARCH_MEDIA,
        lambda: tg._search_with_reactive_recovery(
            search_service=search_service,
            query=query,
            chat_id=chat_id,
            channel=channel,
        ),
    )
    await reply_func(reply)

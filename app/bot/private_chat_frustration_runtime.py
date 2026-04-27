from __future__ import annotations

import sqlite3
from collections.abc import Awaitable, Callable, MutableMapping

from app.bot.bt_classification_runtime import (
    BT_CLASSIFICATION_CANCELLED_TEXT,
    clear_bt_classification_pending,
)
from app.bot.bt_processing_path_runtime import (
    BT_PROCESSING_PATH_CANCELLED_TEXT,
    clear_bt_processing_path_pending,
)
from app.bot.execution_runtime import run_sync_with_policy
from app.bot.query_text_runtime import is_frustration_text
from app.bot.raw_bt_destination_runtime import clear_raw_bt_destination_pending
from app.bot.bt_tmdb_association_runtime import clear_bt_tmdb_association_pending
from app.db.job_repo import JobPersistenceError
from app.operational_logging import format_operational_log_message

PrivateChatReplyFunc = Callable[[str], Awaitable[object]]


def _log_pending_job_lookup_failed(*, chat_id: int | None, reason: str) -> None:
    print(
        format_operational_log_message(
            title="待处理任务查询失败",
            detail=f"chat_id={chat_id if chat_id is not None else '-'} 原因={reason}",
            fix_hint="检查 SQLite 是否可读，以及 jobs 表和当前待处理任务记录是否正常。",
        )
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
    except (JobPersistenceError, sqlite3.Error) as error:
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


async def handle_frustration_query(
    *,
    query: str,
    bot_data: MutableMapping[str, object],
    execution_gate,
    reply_func: PrivateChatReplyFunc,
    chat_id: int | None,
    tg,
) -> bool:
    if not is_frustration_text(query):
        return False
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

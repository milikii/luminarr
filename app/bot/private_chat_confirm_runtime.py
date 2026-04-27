from __future__ import annotations

import sqlite3
from collections.abc import Awaitable, Callable, MutableMapping

from app.db.job_repo import JobPersistenceError
from app.operational_logging import format_operational_log_message

PrivateChatReplyFunc = Callable[[str], Awaitable[object]]


def log_confirm_job_lookup_failed(*, chat_id: int | None, task_ref: str, reason: str) -> None:
    print(
        format_operational_log_message(
            title="确认关联任务查询失败",
            detail=(
                f"chat_id={chat_id if chat_id is not None else '-'} "
                f"task_ref={task_ref.strip() or '-'} 原因={reason}"
            ),
            fix_hint="检查 SQLite 是否可读，以及 jobs 表和当前确认任务关联记录是否正常。",
        )
    )


async def reply_confirm_add(
    *,
    bot_data: MutableMapping[str, object],
    execution_gate,
    reply_func: PrivateChatReplyFunc,
    confirm_ref: str,
    chat_id: int | None,
    user_id: int | None,
    tg,
) -> bool:
    add_service = bot_data.get(tg.ADD_TO_DOWNLOADER_SERVICE_KEY)
    if not isinstance(add_service, tg.AddToDownloaderService):
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True
    reply = await execution_gate.run(
        tg.ACTION_CONFIRM_ADD_TO_DOWNLOADER,
        lambda: add_service.confirm_add_by_task_ref(
            confirm_ref,
            chat_id=chat_id,
            user_id=user_id,
        ),
    )
    await reply_func(reply)
    return True


async def reply_confirm_import(
    *,
    bot_data: MutableMapping[str, object],
    execution_gate,
    reply_func: PrivateChatReplyFunc,
    confirm_ref: str,
    chat_id: int | None,
    user_id: int | None,
    tg,
) -> bool:
    import_service = bot_data.get(tg.IMPORT_TO_LIBRARY_SERVICE_KEY)
    if not isinstance(import_service, tg.ImportToLibraryService):
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True
    reply = await execution_gate.run(
        tg.ACTION_CONFIRM_IMPORT_TO_LIBRARY,
        lambda: import_service.confirm_import_by_task_ref(
            confirm_ref,
            chat_id=chat_id,
            user_id=user_id,
        ),
    )
    await reply_func(reply)
    return True


async def handle_confirm_query(
    *,
    bot_data: MutableMapping[str, object],
    execution_gate,
    reply_func: PrivateChatReplyFunc,
    confirm_ref: str | None,
    chat_id: int | None,
    user_id: int | None,
    tg,
) -> bool:
    if confirm_ref is None:
        return False
    if chat_id is not None and confirm_ref:
        job_repo = bot_data.get(tg.JOB_REPO_KEY)
        if isinstance(job_repo, tg.JobRepo):
            matched_job_lookup_failed = False
            try:
                matched_job = job_repo.get_job_for_chat_ref(chat_id=chat_id, task_ref=confirm_ref)
            except (JobPersistenceError, sqlite3.Error) as error:
                log_confirm_job_lookup_failed(
                    chat_id=chat_id,
                    task_ref=confirm_ref,
                    reason=str(error),
                )
                matched_job = None
                matched_job_lookup_failed = True
            if matched_job is not None and matched_job.workflow_type == tg.WORKFLOW_ADD_TO_DOWNLOADER:
                return await reply_confirm_add(
                    bot_data=bot_data,
                    execution_gate=execution_gate,
                    reply_func=reply_func,
                    confirm_ref=confirm_ref,
                    chat_id=chat_id,
                    user_id=user_id,
                    tg=tg,
                )
            if matched_job is not None and matched_job.workflow_type == tg.WORKFLOW_IMPORT_TO_LIBRARY:
                return await reply_confirm_import(
                    bot_data=bot_data,
                    execution_gate=execution_gate,
                    reply_func=reply_func,
                    confirm_ref=confirm_ref,
                    chat_id=chat_id,
                    user_id=user_id,
                    tg=tg,
                )
            if matched_job_lookup_failed:
                await reply_func(tg.SERVICE_NOT_READY_TEXT)
                return True

    add_service = bot_data.get(tg.ADD_TO_DOWNLOADER_SERVICE_KEY)
    has_pending_add: bool | None = False
    if isinstance(add_service, tg.AddToDownloaderService) and chat_id is not None:
        has_pending_add = add_service.has_pending_add(chat_id, confirm_ref)
    if has_pending_add is None:
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True
    if isinstance(add_service, tg.AddToDownloaderService) and chat_id is not None and has_pending_add:
        return await reply_confirm_add(
            bot_data=bot_data,
            execution_gate=execution_gate,
            reply_func=reply_func,
            confirm_ref=confirm_ref,
            chat_id=chat_id,
            user_id=user_id,
            tg=tg,
        )
    return await reply_confirm_import(
        bot_data=bot_data,
        execution_gate=execution_gate,
        reply_func=reply_func,
        confirm_ref=confirm_ref,
        chat_id=chat_id,
        user_id=user_id,
        tg=tg,
    )

from __future__ import annotations

import sqlite3
from collections.abc import Callable

from app.db.job_repo import JOB_STATE_PENDING_APPROVAL, JobPersistenceError, JobRepo
from app.operational_logging import emit_operational_log
from app.services.add_pending_context import PendingAddContext

GetInMemoryPendingFunc = Callable[..., PendingAddContext | None]
LogPendingJobResultMissingFunc = Callable[..., None]


class AddPendingPresenceState:
    def __init__(self, *, job_repo: JobRepo | None) -> None:
        self._job_repo = job_repo

    def has_pending_add(
        self,
        *,
        chat_id: int,
        task_ref: str,
        get_in_memory_pending: GetInMemoryPendingFunc,
        log_pending_job_result_missing: LogPendingJobResultMissingFunc,
    ) -> bool | None:
        cleaned_ref = task_ref.strip()
        if chat_id <= 0 or not cleaned_ref:
            return False
        in_memory_pending = get_in_memory_pending(chat_id=chat_id, task_ref=cleaned_ref)
        if self._job_repo is None:
            return in_memory_pending is not None
        try:
            job = self._job_repo.get_downloader_job_for_chat_ref(chat_id=chat_id, task_ref=cleaned_ref)
        except (JobPersistenceError, sqlite3.Error) as error:
            emit_operational_log(
                title="下载待确认查询失败",
                detail=f"chat_id={chat_id} task_ref={cleaned_ref} 错误={error}",
                fix_hint="检查 SQLite/jobs 表查询是否正常；若当前进程里也没有待确认上下文，这次请求会直接返回服务未就绪，避免把持久化异常误判成“没有待确认下载”。",
            )
            return True if in_memory_pending is not None else None
        if job is not None and job.state == JOB_STATE_PENDING_APPROVAL:
            return True
        if in_memory_pending is not None:
            log_pending_job_result_missing(
                chat_id=chat_id,
                task_ref=cleaned_ref,
                task_id=in_memory_pending.task_id,
                task_hash=in_memory_pending.task_hash,
                stage="lookup",
            )
            return None
        return False

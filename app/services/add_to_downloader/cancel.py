from __future__ import annotations

import sqlite3
from collections.abc import Callable

from app.db.job_repo import WORKFLOW_ADD_TO_DOWNLOADER, JobPersistenceError, JobRecord, JobRepo
from app.operational_logging import emit_operational_log
from app.services.add_pending_context import PendingAddContext, pending_add_from_json

ADD_CANCELLED_TEXT = "已取消当前下载确认。请重新发送序号。"
ADD_CANCEL_STATE_UNAVAILABLE_TEXT = "下载取消状态读取失败，请稍后重试。"

class AddCancelState:
    def __init__(
        self,
        *,
        job_repo: JobRepo | None,
        add_cancel_state_unavailable_text: str,
        add_cancelled_text: str,
        pending_lease_lookup_failed: int,
        downloader_cancel_pending_job_result_missing_reason: str,
        downloader_cancel_pending_job_row_missing_reason: str,
    ) -> None:
        self._job_repo = job_repo
        self._add_cancel_state_unavailable_text = add_cancel_state_unavailable_text
        self._add_cancelled_text = add_cancelled_text
        self._pending_lease_lookup_failed = pending_lease_lookup_failed
        self._downloader_cancel_pending_job_result_missing_reason = downloader_cancel_pending_job_result_missing_reason
        self._downloader_cancel_pending_job_row_missing_reason = downloader_cancel_pending_job_row_missing_reason

    def cancel_pending_add(
        self,
        *,
        chat_id: int,
        resolve_pending_lease_version: Callable[..., int],
        get_latest_pending_task_ref: Callable[[int], str],
        get_in_memory_pending: Callable[..., PendingAddContext | None],
        log_pending_job_result_missing: Callable[..., None],
        cancel_pending_approval: Callable[..., bool],
        clear_pending_context: Callable[..., None],
        record_event: Callable[..., None],
    ) -> str | None:
        if chat_id <= 0:
            return None

        pending_job: JobRecord | None = None
        pending_lookup_failed = False
        if self._job_repo is not None:
            try:
                pending_job = self._job_repo.get_latest_pending_downloader_job(chat_id=chat_id)
            except (JobPersistenceError, sqlite3.Error) as error:
                emit_operational_log(
                    title="下载取消查询失败",
                    detail=f"chat_id={chat_id} 错误={error}",
                    fix_hint="检查 SQLite/jobs 表查询是否正常；若当前进程里也没有待确认上下文，当前取消会直接返回状态读取失败，避免把持久化异常误判成“没有待取消下载”。",
                )
                pending_lookup_failed = True

        if pending_job is None:
            task_ref = get_latest_pending_task_ref(chat_id).strip()
            if not task_ref:
                if pending_lookup_failed:
                    return self._add_cancel_state_unavailable_text
                return None
            pending_add = get_in_memory_pending(chat_id=chat_id, task_ref=task_ref)
            if pending_add is None:
                if pending_lookup_failed:
                    return self._add_cancel_state_unavailable_text
                return None
            if pending_lookup_failed:
                return self._add_cancel_state_unavailable_text
            if self._job_repo is not None:
                log_pending_job_result_missing(
                    chat_id=chat_id,
                    task_ref=task_ref,
                    task_id=pending_add.task_id,
                    task_hash=pending_add.task_hash,
                    stage="cancel",
                )
                return self._add_cancel_state_unavailable_text
            expected_lease_version = resolve_pending_lease_version(
                task_id=pending_add.task_id,
                task_hash=pending_add.task_hash,
                allow_in_memory_fallback_on_error=False,
            )
            if expected_lease_version == self._pending_lease_lookup_failed:
                self._log_cancel_state_unavailable(
                    task_ref=task_ref,
                    task_id=pending_add.task_id,
                    task_hash=pending_add.task_hash,
                    reason="downloader approval pending lease lookup failed",
                )
                return self._add_cancel_state_unavailable_text
            if expected_lease_version <= 0:
                self._log_cancel_state_unavailable(
                    task_ref=task_ref,
                    task_id=pending_add.task_id,
                    task_hash=pending_add.task_hash,
                    reason="downloader approval pending lease missing",
                )
                return self._add_cancel_state_unavailable_text
            approval_cancelled = cancel_pending_approval(
                task_ref=task_ref,
                task_id=pending_add.task_id,
                task_hash=pending_add.task_hash,
                expected_lease_version=expected_lease_version,
            )
            if not approval_cancelled:
                return self._add_cancel_state_unavailable_text
            clear_pending_context(chat_id=chat_id, task_ref=task_ref)
            record_event(
                task_ref=task_ref,
                task_id=pending_add.task_id,
                task_hash=pending_add.task_hash,
                event_type="downloader.cancelled",
                message=self._add_cancelled_text,
            )
            return self._add_cancelled_text

        pending_add, payload_problem = pending_add_from_json(pending_job.payload_json)
        if pending_add is None:
            emit_operational_log(
                title="下载取消载荷损坏",
                detail=f"chat_id={chat_id} task_ref={pending_job.task_ref} job_id={pending_job.job_id} task_id={pending_job.task_id} task_hash={pending_job.task_hash} 载荷={payload_problem or 'unknown'}",
                fix_hint="检查 SQLite/jobs 表里的 payload_json 是否仍是完整待确认下载上下文；当前取消会直接返回状态读取失败，避免把持久化坏数据误判成“没有待取消下载”。",
            )
            return self._add_cancel_state_unavailable_text

        expected_lease_version = resolve_pending_lease_version(
            task_id=pending_job.task_id,
            task_hash=pending_job.task_hash,
            allow_in_memory_fallback_on_error=False,
        )
        if expected_lease_version == self._pending_lease_lookup_failed:
            self._log_cancel_state_unavailable(
                task_ref=pending_job.task_ref,
                task_id=pending_job.task_id,
                task_hash=pending_job.task_hash,
                reason="downloader approval pending lease lookup failed",
            )
            return self._add_cancel_state_unavailable_text
        if expected_lease_version <= 0:
            self._log_cancel_state_unavailable(
                task_ref=pending_job.task_ref,
                task_id=pending_job.task_id,
                task_hash=pending_job.task_hash,
                reason="downloader approval pending lease missing",
            )
            return self._add_cancel_state_unavailable_text

        approval_cancelled = cancel_pending_approval(
            task_ref=pending_job.task_ref,
            task_id=pending_job.task_id,
            task_hash=pending_job.task_hash,
            expected_lease_version=expected_lease_version,
        )
        if not approval_cancelled:
            return self._add_cancel_state_unavailable_text
        assert self._job_repo is not None
        try:
            cancelled = self._job_repo.cancel_pending_job(
                job_id=pending_job.job_id,
                expected_version=pending_job.version,
                workflow_type=WORKFLOW_ADD_TO_DOWNLOADER,
            )
            if cancelled is None:
                raise JobPersistenceError(self._downloader_cancel_pending_job_result_missing_reason)
        except (JobPersistenceError, sqlite3.Error) as error:
            if str(error) in {
                self._downloader_cancel_pending_job_result_missing_reason,
                self._downloader_cancel_pending_job_row_missing_reason,
            }:
                self._log_cancel_pending_job_result_missing(pending_job=pending_job, reason=str(error))
            else:
                emit_operational_log(
                    title="下载取消任务更新失败",
                    detail=f"task_ref={pending_job.task_ref} job_id={pending_job.job_id} task_id={pending_job.task_id} task_hash={pending_job.task_hash} version={pending_job.version} 错误={error}",
                    fix_hint="检查 SQLite/jobs 表更新是否正常；当前审批可能已取消，但任务真相可能仍残留在待确认状态。",
                )
            return self._add_cancel_state_unavailable_text
        if not cancelled:
            emit_operational_log(
                title="下载取消任务更新失败",
                detail=f"task_ref={pending_job.task_ref} job_id={pending_job.job_id} task_id={pending_job.task_id} task_hash={pending_job.task_hash} version={pending_job.version} 错误=jobs.cancel_pending_job rejected current state",
                fix_hint="检查该任务是否已被其他路径抢先取消、确认或完结；当前审批可能已取消，但待确认任务真相可能已被其他状态迁移抢先改写。",
            )
            return self._add_cancel_state_unavailable_text
        clear_pending_context(chat_id=chat_id, task_ref=pending_job.task_ref)
        record_event(
            task_ref=pending_job.task_ref,
            task_id=pending_job.task_id,
            task_hash=pending_job.task_hash,
            event_type="downloader.cancelled",
            message=self._add_cancelled_text,
        )
        return self._add_cancelled_text

    def _log_cancel_state_unavailable(
        self,
        *,
        task_ref: str,
        task_id: str,
        task_hash: str,
        reason: str,
    ) -> None:
        emit_operational_log(
            title="下载取消状态读取失败",
            detail=f"task_ref={task_ref} task_id={task_id} task_hash={task_hash} 原因={reason}",
            fix_hint="检查 SQLite/approval_record 表里的待确认下载审批是否仍存在；当前取消会直接返回状态读取失败，避免把审批真相缺口误判成“没有待取消下载”。",
        )

    def _log_cancel_pending_job_result_missing(self, *, pending_job: JobRecord, reason: str) -> None:
        emit_operational_log(
            title="下载取消任务结果缺失",
            detail=f"task_ref={pending_job.task_ref} job_id={pending_job.job_id} task_id={pending_job.task_id} task_hash={pending_job.task_hash} version={pending_job.version} 原因={reason}",
            fix_hint="检查 jobs 表里该待确认任务是否仍存在，以及取消更新后是否还能回读到最新状态；当前审批可能已取消，但任务真相还没有确认取消成功。",
        )


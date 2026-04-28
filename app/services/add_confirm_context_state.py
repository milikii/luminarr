from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from app.db.approval_repo import ApprovalPersistenceError, ApprovalRecord
from app.db.job_repo import (
    JOB_STATE_PENDING_APPROVAL,
    JobPersistenceError,
    JobRecord,
    JobRepo,
    WORKFLOW_ADD_TO_DOWNLOADER,
)
from app.operational_logging import emit_operational_log
from app.services.add_pending_context import PendingAddContext, pending_add_from_json

CancelPendingApprovalFunc = Callable[..., bool]
ClearPendingContextFunc = Callable[..., None]
RecordEventFunc = Callable[..., None]
IsPendingApprovalExpiredFunc = Callable[..., bool | None]


def _log_add_confirm_context_error(*, title: str, detail: str, fix_hint: str) -> None:
    emit_operational_log(title=title, detail=detail, fix_hint=fix_hint)


@dataclass(frozen=True, slots=True)
class ConfirmExecutionContext:
    job: JobRecord
    approval_record: ApprovalRecord | None
    pending_add: PendingAddContext
    approval_lookup_failed: bool = False


class ConfirmApprovalStateProtocol(Protocol):
    approval_repo: object | None


class AddConfirmContextState:
    def __init__(
        self,
        *,
        job_repo: JobRepo | None,
        confirm_approval_state: ConfirmApprovalStateProtocol,
        add_confirm_expired_text: str,
        add_confirm_state_unavailable_text: str,
        job_row_corrupted_reasons: frozenset[str],
        downloader_cancel_pending_job_result_missing_reason: str,
        downloader_cancel_pending_job_row_missing_reason: str,
    ) -> None:
        self._job_repo = job_repo
        self._confirm_approval_state = confirm_approval_state
        self._add_confirm_expired_text = add_confirm_expired_text
        self._add_confirm_state_unavailable_text = add_confirm_state_unavailable_text
        self._job_row_corrupted_reasons = job_row_corrupted_reasons
        self._downloader_cancel_pending_job_result_missing_reason = (
            downloader_cancel_pending_job_result_missing_reason
        )
        self._downloader_cancel_pending_job_row_missing_reason = downloader_cancel_pending_job_row_missing_reason

    def rebuild_confirm_context(
        self,
        *,
        task_ref: str,
        chat_id: int | None,
    ) -> tuple[ConfirmExecutionContext | None, bool]:
        if self._job_repo is None or chat_id is None or chat_id <= 0:
            return None, False
        try:
            job = self._job_repo.get_downloader_job_for_chat_ref(chat_id=chat_id, task_ref=task_ref)
        except (JobPersistenceError, sqlite3.Error) as error:
            if str(error) in self._job_row_corrupted_reasons:
                _log_add_confirm_context_error(
                    title="下载确认上下文记录损坏",
                    detail=f"chat_id={chat_id} task_ref={task_ref} 错误={error}",
                    fix_hint="检查 SQLite/jobs 表里该待确认下载任务的 job_id / chat_id / task_id / task_hash / version 是否仍是完整真相；当前 confirm 会直接返回状态读取失败，避免把坏记录误判成“没有待确认下载”。",
                )
            else:
                _log_add_confirm_context_error(
                    title="下载确认上下文查询失败",
                    detail=f"chat_id={chat_id} task_ref={task_ref} 错误={error}",
                    fix_hint="检查 SQLite/jobs 表查询是否正常；当前 confirm 会直接返回状态读取失败，避免把持久化异常误判成“没有待确认下载”。",
                )
            return None, True
        if job is None:
            return None, False

        pending_add, payload_problem = pending_add_from_json(job.payload_json)
        if pending_add is None:
            _log_add_confirm_context_error(
                title="下载确认上下文载荷损坏",
                detail=f"chat_id={chat_id} task_ref={task_ref} task_id={job.task_id} task_hash={job.task_hash} 载荷={payload_problem or 'unknown'}",
                fix_hint="检查 SQLite/jobs 表里的 payload_json 是否仍是完整待确认下载上下文；若当前进程里也没有待确认上下文，当前 confirm 会直接返回状态读取失败，避免把持久化坏数据误判成“没有待确认下载”。",
            )
            return None, True

        approval_record: ApprovalRecord | None = None
        approval_lookup_failed = False
        if self._confirm_approval_state.approval_repo is not None:
            try:
                approval_record = self._confirm_approval_state.approval_repo.get_downloader_approval(
                    task_id=job.task_id,
                    task_hash=job.task_hash,
                )
            except (ApprovalPersistenceError, sqlite3.Error) as error:
                _log_add_confirm_context_error(
                    title="下载确认审批查询失败",
                    detail=f"task_ref={task_ref} task_id={job.task_id} task_hash={job.task_hash} 错误={error}",
                    fix_hint="检查 SQLite/approval_record 表查询是否正常；当前 confirm 会直接返回状态读取失败，避免把审批真相缺口误判成普通未确认状态。",
                )
                approval_lookup_failed = True
        return (
            ConfirmExecutionContext(
                job=job,
                approval_record=approval_record,
                pending_add=pending_add,
                approval_lookup_failed=approval_lookup_failed,
            ),
            False,
        )

    def handle_expired_pending_confirm(
        self,
        *,
        task_ref: str,
        context: ConfirmExecutionContext,
        chat_id: int | None,
        is_pending_approval_expired: IsPendingApprovalExpiredFunc,
        cancel_pending_approval: CancelPendingApprovalFunc,
        clear_pending_context: ClearPendingContextFunc,
        record_event: RecordEventFunc,
    ) -> str | None:
        approval_record = context.approval_record
        if approval_record is None:
            return None
        approval_expired = is_pending_approval_expired(
            task_id=context.pending_add.task_id,
            task_hash=context.pending_add.task_hash,
            expected_lease_version=approval_record.lease_version,
        )
        if approval_expired is None:
            return self._add_confirm_state_unavailable_text
        if not approval_expired:
            return None
        approval_cancelled = cancel_pending_approval(
            task_ref=task_ref,
            task_id=context.pending_add.task_id,
            task_hash=context.pending_add.task_hash,
            expected_lease_version=approval_record.lease_version,
        )
        if not approval_cancelled:
            return self._add_confirm_state_unavailable_text
        if self._job_repo is not None and context.job.state == JOB_STATE_PENDING_APPROVAL:
            try:
                cancelled = self._job_repo.cancel_pending_job(
                    job_id=context.job.job_id,
                    expected_version=context.job.version,
                    workflow_type=WORKFLOW_ADD_TO_DOWNLOADER,
                )
                if cancelled is None:
                    raise JobPersistenceError(self._downloader_cancel_pending_job_result_missing_reason)
            except (JobPersistenceError, sqlite3.Error) as error:
                if str(error) in {
                    self._downloader_cancel_pending_job_result_missing_reason,
                    self._downloader_cancel_pending_job_row_missing_reason,
                }:
                    self._log_expired_cancel_pending_job_result_missing(
                        job=context.job,
                        task_ref=task_ref,
                        reason=str(error),
                    )
                else:
                    _log_add_confirm_context_error(
                        title="下载确认超时任务取消失败",
                        detail=f"task_ref={task_ref} job_id={context.job.job_id} task_id={context.job.task_id} task_hash={context.job.task_hash} version={context.job.version} 错误={error}",
                        fix_hint="检查 SQLite/jobs 表更新是否正常；当前 confirm 会直接返回状态读取失败，避免把任务真相缺口误判成普通“下载确认已超时”。",
                    )
                return self._add_confirm_state_unavailable_text
            if not cancelled:
                _log_add_confirm_context_error(
                    title="下载确认超时任务取消失败",
                    detail=f"task_ref={task_ref} job_id={context.job.job_id} task_id={context.job.task_id} task_hash={context.job.task_hash} version={context.job.version} 错误=jobs.cancel_pending_job rejected current state",
                    fix_hint="检查该任务是否已被其他路径抢先取消、确认或完结；当前 confirm 会直接返回状态读取失败，避免把任务状态迁移冲突误判成普通“下载确认已超时”。",
                )
                return self._add_confirm_state_unavailable_text
        clear_pending_context(chat_id=chat_id, task_ref=task_ref)
        record_event(
            task_ref=task_ref,
            task_id=context.pending_add.task_id,
            task_hash=context.pending_add.task_hash,
            event_type="downloader.approval_expired",
            message=self._add_confirm_expired_text,
        )
        return self._add_confirm_expired_text

    def _log_expired_cancel_pending_job_result_missing(self, *, job: JobRecord, task_ref: str, reason: str) -> None:
        _log_add_confirm_context_error(
            title="下载确认超时任务结果缺失",
            detail=f"task_ref={task_ref} job_id={job.job_id} task_id={job.task_id} task_hash={job.task_hash} version={job.version} 原因={reason}",
            fix_hint="检查 jobs 表里该待确认任务是否仍存在，以及超时取消后是否还能回读到最新状态；当前 confirm 会直接返回状态读取失败，避免把缺失真相误判成普通“下载确认已超时”。",
        )

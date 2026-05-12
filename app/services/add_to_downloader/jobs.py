from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass

from app.db.approval_repo import (
    ApprovalPersistenceError,
    ApprovalRecord,
)
from app.db.job_repo import (
    JOB_STATE_PENDING_APPROVAL,
    WORKFLOW_ADD_TO_DOWNLOADER,
    JobPersistenceError,
    JobRecord,
    JobRepo,
)
from app.operational_logging import emit_operational_log
from app.services.add_pending_context import PendingAddContext, pending_add_from_json, pending_add_to_json
from app.services.add_to_downloader.approval import AddConfirmApprovalState

DOWNLOADER_PENDING_JOB_RESULT_MISSING_REASON = "job missing after pending upsert"
DOWNLOADER_PENDING_JOB_NONE_REASON = "downloader pending job result missing"
DOWNLOADER_CANCEL_PENDING_JOB_RESULT_MISSING_REASON = "downloader cancel pending job result missing"
DOWNLOADER_CANCEL_PENDING_JOB_ROW_MISSING_REASON = "job missing during cancel"

DOWNLOADER_CONFIRM_CONTEXT_JOB_ROW_CORRUPTED_REASONS = frozenset(
    {
        "job row identity corrupted after read",
        "job row chat identity corrupted after read",
        "job row user identity corrupted after read",
        "job row version corrupted after read",
    }
)

@dataclass(frozen=True, slots=True)
class ConfirmPreparationState:
    pending_add: PendingAddContext
    expected_lease_version: int
    claimed_job: bool
    claimed_job_id: str
    claimed_job_version: int
    lease_owner: str


def _log_add_confirm_context_error(*, title: str, detail: str, fix_hint: str) -> None:
    emit_operational_log(title=title, detail=detail, fix_hint=fix_hint)


@dataclass(frozen=True, slots=True)
class ConfirmExecutionContext:
    job: JobRecord
    approval_record: ApprovalRecord | None
    pending_add: PendingAddContext
    approval_lookup_failed: bool = False


@dataclass(frozen=True, slots=True)
class ConfirmAvailabilityResolution:
    confirm_context: ConfirmExecutionContext | None
    in_memory_pending: PendingAddContext | None


class AddConfirmContextState:
    def __init__(
        self,
        *,
        job_repo: JobRepo | None,
        confirm_approval_state: AddConfirmApprovalState,
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
        is_pending_approval_expired: Callable[..., bool | None],
        cancel_pending_approval: Callable[..., bool],
        clear_pending_context: Callable[..., None],
        record_event: Callable[..., None],
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



DOWNLOADER_CLAIM_PENDING_JOB_RESULT_MISSING_REASON = "job missing during lease claim"
DOWNLOADER_RESTORE_PENDING_JOB_RESULT_MISSING_REASON = "job missing during state transition"
DOWNLOADER_MARK_COMPLETED_JOB_RESULT_MISSING_REASON = "downloader completed job result missing"
JOB_LEASE_OWNER = "downloader_confirm"

def _log_add_confirm_job_state_error(*, title: str, detail: str, fix_hint: str) -> None:
    emit_operational_log(title=title, detail=detail, fix_hint=fix_hint)


class AddConfirmJobState:
    def __init__(self, *, job_repo: JobRepo | None) -> None:
        self._job_repo = job_repo

    def claim_pending_job(self, *, job: JobRecord, lease_owner: str) -> bool | None:
        if self._job_repo is None:
            return False
        try:
            claimed = self._job_repo.claim_lease(
                job_id=job.job_id,
                expected_version=job.version,
                lease_owner=lease_owner,
                workflow_type=WORKFLOW_ADD_TO_DOWNLOADER,
            )
        except (JobPersistenceError, sqlite3.Error) as error:
            if str(error) == DOWNLOADER_CLAIM_PENDING_JOB_RESULT_MISSING_REASON:
                _log_add_confirm_job_state_error(
                    title="下载确认任务抢占结果缺失",
                    detail=f"job_id={job.job_id} task_ref={job.task_ref} task_id={job.task_id} task_hash={job.task_hash} version={job.version} lease_owner={lease_owner} 错误={error}",
                    fix_hint="检查 jobs 表里该待确认任务是否仍存在，并确认抢占前后的 version/lease_owner 没有被其他路径改写；当前 confirm 会直接返回状态读取失败，避免把任务真相缺口误判成普通未持有执行权。",
                )
            else:
                _log_add_confirm_job_state_error(
                    title="下载确认任务抢占失败",
                    detail=f"job_id={job.job_id} task_ref={job.task_ref} task_id={job.task_id} task_hash={job.task_hash} version={job.version} lease_owner={lease_owner} 错误={error}",
                    fix_hint="检查 SQLite/jobs 表 lease 更新是否正常；当前 confirm 会直接返回状态读取失败，避免把持久化异常继续混成普通未持有执行权。",
                )
            return None
        if claimed is False:
            _log_add_confirm_job_state_error(
                title="下载确认任务抢占失败",
                detail=f"job_id={job.job_id} task_ref={job.task_ref} task_id={job.task_id} task_hash={job.task_hash} version={job.version} lease_owner={lease_owner} 错误=jobs.claim_lease rejected current state",
                fix_hint="检查 SQLite/jobs 表里的任务行是否仍存在、version/lease_owner 是否匹配，或是否已被其他路径抢先确认/取消；当前 confirm 会继续按 stale check 处理，避免把任务真相冲突静默混成普通未确认。",
            )
            return False
        return True

    def restore_pending_job(
        self,
        *,
        job_id: str,
        expected_version: int,
        lease_owner: str,
    ) -> None:
        if self._job_repo is None:
            return
        try:
            restored = self._job_repo.release_lease_to_pending(
                job_id=job_id,
                expected_version=expected_version,
                lease_owner=lease_owner,
                workflow_type=WORKFLOW_ADD_TO_DOWNLOADER,
            )
        except (JobPersistenceError, sqlite3.Error) as error:
            if str(error) == DOWNLOADER_RESTORE_PENDING_JOB_RESULT_MISSING_REASON:
                _log_add_confirm_job_state_error(
                    title="下载确认任务回退结果缺失",
                    detail=f"job_id={job_id} version={expected_version} lease_owner={lease_owner} 错误={error}",
                    fix_hint="检查 jobs 表里该待确认任务是否仍存在，以及 lease 回退后是否还能回读到待确认状态；当前审批已尝试退回待确认，但任务真相还没有确认回退成功。",
                )
            else:
                _log_add_confirm_job_state_error(
                    title="下载确认任务回退失败",
                    detail=f"job_id={job_id} version={expected_version} lease_owner={lease_owner} 错误={error}",
                    fix_hint="检查 SQLite/jobs 表 lease 回退是否正常；当前审批已尝试退回待确认，但持久化状态可能仍停在执行中。",
                )
            return
        if restored is False:
            _log_add_confirm_job_state_error(
                title="下载确认任务回退失败",
                detail=f"job_id={job_id} version={expected_version} lease_owner={lease_owner} 错误=jobs.release_lease_to_pending rejected current state",
                fix_hint="检查 SQLite/jobs 表里的任务行是否仍存在、version/lease_owner 是否匹配；当前审批已尝试退回待确认，但持久化状态可能仍停在执行中。",
            )

    def mark_completed_job(
        self,
        *,
        job_id: str,
        expected_version: int,
        lease_owner: str,
        completed_add: PendingAddContext,
    ) -> bool | None:
        if self._job_repo is None:
            return True
        try:
            marked = self._job_repo.mark_downloader_completed(
                job_id=job_id,
                expected_version=expected_version,
                lease_owner=lease_owner,
                task_id=completed_add.task_id,
                task_hash=completed_add.task_hash,
                payload_json=pending_add_to_json(completed_add),
            )
            if marked is None:
                raise JobPersistenceError(DOWNLOADER_MARK_COMPLETED_JOB_RESULT_MISSING_REASON)
        except (JobPersistenceError, sqlite3.Error) as error:
            if str(error) == DOWNLOADER_MARK_COMPLETED_JOB_RESULT_MISSING_REASON:
                _log_add_confirm_job_state_error(
                    title="下载确认任务完结结果缺失",
                    detail=f"job_id={job_id} task_ref={completed_add.task_ref} task_id={completed_add.task_id} task_hash={completed_add.task_hash} version={expected_version} lease_owner={lease_owner} 错误={error}",
                    fix_hint="检查 jobs 表里该任务是否仍存在，以及完成态更新后是否还能回读到最新状态；当前下载结果已返回，但任务真相还没有确认完结成功。",
                )
            else:
                _log_add_confirm_job_state_error(
                    title="下载确认任务完结失败",
                    detail=f"job_id={job_id} task_ref={completed_add.task_ref} task_id={completed_add.task_id} task_hash={completed_add.task_hash} version={expected_version} lease_owner={lease_owner} 错误={error}",
                    fix_hint="检查 SQLite/jobs 表完成态更新是否正常；当前下载结果已返回，但任务真相可能仍停留在待确认或执行中。",
                )
            return None
        if marked is False:
            _log_add_confirm_job_state_error(
                title="下载确认任务完结失败",
                detail=f"job_id={job_id} task_ref={completed_add.task_ref} task_id={completed_add.task_id} task_hash={completed_add.task_hash} version={expected_version} lease_owner={lease_owner} 错误=jobs.mark_downloader_completed rejected current state",
                fix_hint="检查 SQLite/jobs 表里的任务行是否仍存在、version/lease_owner 是否匹配；当前下载结果已返回，但任务真相可能仍停留在待确认或执行中。",
            )
            return False
        return True

    def build_job_lease_owner(self, task_ref: str) -> str:
        cleaned_ref = task_ref.strip()
        if not cleaned_ref:
            return JOB_LEASE_OWNER
        return f"{JOB_LEASE_OWNER}:{cleaned_ref}"


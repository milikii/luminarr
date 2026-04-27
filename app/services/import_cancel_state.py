from __future__ import annotations

import sqlite3
from collections.abc import Callable

from app.db.approval_repo import ApprovalPersistenceError, ApprovalRepo
from app.db.job_repo import JobPersistenceError, JobRecord, JobRepo, WORKFLOW_IMPORT_TO_LIBRARY

ResolvePendingLeaseVersionFunc = Callable[..., int]
ClearPendingCopyFallbackFunc = Callable[..., None]
RecordImportEventFunc = Callable[..., None]


class ImportCancelState:
    def __init__(
        self,
        *,
        job_repo: JobRepo | None,
        approval_repo: ApprovalRepo | None,
        import_cancel_state_unavailable_text: str,
        import_cancelled_text: str,
        pending_lease_lookup_failed: int,
        import_cancel_pending_job_result_missing_reason: str,
        import_cancel_pending_job_row_missing_reason: str,
        import_cancel_approval_result_missing_reason: str,
        import_cancel_approval_none_reason: str,
    ) -> None:
        self._job_repo = job_repo
        self._approval_repo = approval_repo
        self._import_cancel_state_unavailable_text = import_cancel_state_unavailable_text
        self._import_cancelled_text = import_cancelled_text
        self._pending_lease_lookup_failed = pending_lease_lookup_failed
        self._import_cancel_pending_job_result_missing_reason = import_cancel_pending_job_result_missing_reason
        self._import_cancel_pending_job_row_missing_reason = import_cancel_pending_job_row_missing_reason
        self._import_cancel_approval_result_missing_reason = import_cancel_approval_result_missing_reason
        self._import_cancel_approval_none_reason = import_cancel_approval_none_reason

    def cancel_pending_import(
        self,
        *,
        chat_id: int,
        resolve_pending_lease_version: ResolvePendingLeaseVersionFunc,
        clear_pending_copy_fallback: ClearPendingCopyFallbackFunc,
        record_event: RecordImportEventFunc,
    ) -> str | None:
        if chat_id <= 0 or self._job_repo is None:
            return None

        pending_job, pending_lookup_failed = self._lookup_pending_job(chat_id=chat_id)
        if pending_job is None:
            if pending_lookup_failed:
                return self._import_cancel_state_unavailable_text
            return None

        expected_lease_version = resolve_pending_lease_version(
            task_id=pending_job.task_id,
            task_hash=pending_job.task_hash,
            allow_in_memory_fallback_on_error=False,
        )
        if expected_lease_version == self._pending_lease_lookup_failed:
            print(
                f"\033[31m[导入取消状态读取失败]\033[0m task_ref={pending_job.task_ref} task_id={pending_job.task_id} task_hash={pending_job.task_hash} 原因=import approval pending lease lookup failed\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表查询是否正常；当前取消会直接返回状态读取失败，避免把审批查询异常误判成“没有待取消导入”。",
                flush=True,
            )
            return self._import_cancel_state_unavailable_text
        if expected_lease_version <= 0:
            print(
                f"\033[31m[导入取消状态读取失败]\033[0m task_ref={pending_job.task_ref} task_id={pending_job.task_id} task_hash={pending_job.task_hash} 原因=import approval pending lease missing\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表里的待确认导入审批是否仍存在；当前取消会直接返回状态读取失败，避免把审批真相缺口误判成“没有待取消导入”。",
                flush=True,
            )
            return self._import_cancel_state_unavailable_text

        approval_cancelled = self._cancel_pending_approval(
            job=pending_job,
            expected_lease_version=expected_lease_version,
        )
        if approval_cancelled is not True:
            return self._import_cancel_state_unavailable_text

        job_cancelled = self._cancel_pending_job(job=pending_job)
        if job_cancelled is not True:
            return self._import_cancel_state_unavailable_text

        clear_pending_copy_fallback(
            task_id=pending_job.task_id,
            task_hash=pending_job.task_hash,
        )
        record_event(
            task_ref=pending_job.task_ref,
            task_id=pending_job.task_id,
            task_hash=pending_job.task_hash,
            event_type="import.cancelled",
            message=self._import_cancelled_text,
        )
        return self._import_cancelled_text

    def _lookup_pending_job(self, *, chat_id: int) -> tuple[JobRecord | None, bool]:
        assert self._job_repo is not None
        pending_lookup_failed = False
        try:
            pending_job = self._job_repo.get_latest_pending_import_job(chat_id=chat_id)
        except (JobPersistenceError, sqlite3.Error) as error:
            print(
                f"\033[31m[导入取消查询失败]\033[0m chat_id={chat_id} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表读取是否正常；当前取消会直接返回状态读取失败，避免把查询异常误判成“没有待取消导入”。",
                flush=True,
            )
            pending_job = None
            pending_lookup_failed = True
        return pending_job, pending_lookup_failed

    def _cancel_pending_approval(
        self,
        *,
        job: JobRecord,
        expected_lease_version: int,
    ) -> bool | None:
        if self._approval_repo is None:
            return True
        try:
            approval_cancelled = self._approval_repo.cancel_import(
                task_id=job.task_id,
                task_hash=job.task_hash,
                task_ref=job.task_ref,
                expected_lease_version=expected_lease_version,
            )
            if approval_cancelled is None:
                raise ApprovalPersistenceError(self._import_cancel_approval_none_reason)
        except (ApprovalPersistenceError, sqlite3.Error) as error:
            if str(error) in {
                self._import_cancel_approval_result_missing_reason,
                self._import_cancel_approval_none_reason,
            }:
                print(
                    f"\033[31m[导入取消审批结果缺失]\033[0m task_ref={job.task_ref} task_id={job.task_id} task_hash={job.task_hash} lease_version={expected_lease_version} 错误={error}\n"
                    "\033[33m[处理建议]\033[0m 检查 approval_record 表里该待确认导入审批是否仍存在，以及取消更新后是否还能回读到该行；"
                    "当前取消会直接返回状态读取失败，避免把缺失真相误判成普通状态冲突或普通“没有待取消导入”。",
                    flush=True,
                )
            else:
                print(
                    f"\033[31m[导入取消审批更新失败]\033[0m task_ref={job.task_ref} task_id={job.task_id} task_hash={job.task_hash} lease_version={expected_lease_version} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表更新是否正常；当前取消会直接失败返回，待确认导入状态可能仍残留。",
                    flush=True,
                )
            return None
        if not approval_cancelled:
            print(
                f"\033[31m[导入取消审批更新失败]\033[0m task_ref={job.task_ref} task_id={job.task_id} task_hash={job.task_hash} lease_version={expected_lease_version} 错误=approval_record missing or lease_version mismatch\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表里的待确认导入审批是否仍存在，或是否已被其他路径抢先取消/确认；当前取消会直接返回状态读取失败，避免把审批真相缺口误判成“没有待取消导入”。",
                flush=True,
            )
            return False
        return True

    def _cancel_pending_job(self, *, job: JobRecord) -> bool | None:
        assert self._job_repo is not None
        try:
            cancelled = self._job_repo.cancel_pending_job(
                job_id=job.job_id,
                expected_version=job.version,
                workflow_type=WORKFLOW_IMPORT_TO_LIBRARY,
            )
            if cancelled is None:
                raise JobPersistenceError(self._import_cancel_pending_job_result_missing_reason)
        except (JobPersistenceError, sqlite3.Error) as error:
            if str(error) in {
                self._import_cancel_pending_job_result_missing_reason,
                self._import_cancel_pending_job_row_missing_reason,
            }:
                self._log_cancel_pending_job_result_missing(job=job, reason=str(error))
            else:
                print(
                    f"\033[31m[导入取消任务更新失败]\033[0m task_ref={job.task_ref} job_id={job.job_id} task_id={job.task_id} task_hash={job.task_hash} version={job.version} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表更新是否正常；当前审批可能已取消，但任务真相可能仍残留在待确认状态。",
                    flush=True,
                )
            return None
        if not cancelled:
            print(
                f"\033[31m[导入取消任务更新失败]\033[0m task_ref={job.task_ref} job_id={job.job_id} task_id={job.task_id} task_hash={job.task_hash} version={job.version} 错误=jobs.cancel_pending_job rejected current state\n\033[33m[处理建议]\033[0m 检查该任务是否已被其他路径抢先取消、确认或完结；当前审批可能已取消，但待确认任务真相可能已被其他状态迁移抢先改写。",
                flush=True,
            )
            return False
        return True

    def _log_cancel_pending_job_result_missing(self, *, job: JobRecord, reason: str) -> None:
        print(
            f"\033[31m[导入取消任务结果缺失]\033[0m task_ref={job.task_ref} job_id={job.job_id} task_id={job.task_id} task_hash={job.task_hash} version={job.version} 原因={reason}\n\033[33m[处理建议]\033[0m 检查 jobs 表里该待确认导入任务是否仍存在，以及取消更新后是否还能回读到最新状态；当前审批可能已取消，但任务真相还没有确认取消成功。",
            flush=True,
        )

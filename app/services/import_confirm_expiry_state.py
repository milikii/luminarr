from __future__ import annotations

from collections.abc import Callable

from app.db.approval_repo import ApprovalRepo
from app.db.job_repo import JobRepo
from app.services.import_context_lookup import ConfirmExecutionContext

ClearPendingCopyFallbackFunc = Callable[..., None]
IsPendingApprovalExpiredFunc = Callable[..., bool | None]
LogExpiredCancelPendingJobResultMissingFunc = Callable[..., None]
RecordEventFunc = Callable[..., None]


class ImportConfirmExpiryState:
    def __init__(
        self,
        *,
        approval_repo: ApprovalRepo | None,
        job_repo: JobRepo | None,
        import_confirm_state_unavailable_text: str,
        import_confirm_expired_text: str,
        import_cancel_pending_job_result_missing_reason: str,
        import_cancel_pending_job_row_missing_reason: str,
        job_state_pending_approval: str,
        workflow_import_to_library: str,
    ) -> None:
        self._approval_repo = approval_repo
        self._job_repo = job_repo
        self._import_confirm_state_unavailable_text = import_confirm_state_unavailable_text
        self._import_confirm_expired_text = import_confirm_expired_text
        self._import_cancel_pending_job_result_missing_reason = import_cancel_pending_job_result_missing_reason
        self._import_cancel_pending_job_row_missing_reason = import_cancel_pending_job_row_missing_reason
        self._job_state_pending_approval = job_state_pending_approval
        self._workflow_import_to_library = workflow_import_to_library

    def handle_expired_pending_confirm(
        self,
        *,
        task_ref: str,
        context: ConfirmExecutionContext,
        is_pending_approval_expired: IsPendingApprovalExpiredFunc,
        clear_pending_copy_fallback: ClearPendingCopyFallbackFunc,
        record_event: RecordEventFunc,
        log_expired_cancel_pending_job_result_missing: LogExpiredCancelPendingJobResultMissingFunc,
    ) -> str | None:
        approval_record = context.approval_record
        if approval_record is None:
            return None
        approval_expired = is_pending_approval_expired(
            task_id=context.job.task_id,
            task_hash=context.job.task_hash,
            expected_lease_version=approval_record.lease_version,
        )
        if approval_expired is None:
            return self._import_confirm_state_unavailable_text
        if not approval_expired:
            return None
        if not self._cancel_pending_approval(task_ref=task_ref, context=context, lease_version=approval_record.lease_version):
            return self._import_confirm_state_unavailable_text
        if not self._cancel_pending_job(
            task_ref=task_ref,
            context=context,
            log_expired_cancel_pending_job_result_missing=log_expired_cancel_pending_job_result_missing,
        ):
            return self._import_confirm_state_unavailable_text
        clear_pending_copy_fallback(
            task_id=context.job.task_id,
            task_hash=context.job.task_hash,
        )
        record_event(
            task_ref=task_ref,
            task_id=context.job.task_id,
            task_hash=context.job.task_hash,
            event_type="import.approval_expired",
            message=self._import_confirm_expired_text,
        )
        return self._import_confirm_expired_text

    def _cancel_pending_approval(
        self,
        *,
        task_ref: str,
        context: ConfirmExecutionContext,
        lease_version: int,
    ) -> bool:
        if self._approval_repo is None:
            return True
        try:
            approval_cancelled = self._approval_repo.cancel_import(
                task_id=context.job.task_id,
                task_hash=context.job.task_hash,
                task_ref=task_ref,
                expected_lease_version=lease_version,
            )
        except Exception as error:
            print(
                f"\033[31m[导入确认超时审批取消失败]\033[0m task_ref={task_ref} task_id={context.job.task_id} task_hash={context.job.task_hash} lease_version={lease_version} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表更新是否正常；当前 confirm 会直接返回状态读取失败，避免把审批真相缺口误判成普通“导入确认已超时”。",
                flush=True,
            )
            return False
        if approval_cancelled:
            return True
        print(
            f"\033[31m[导入确认超时审批取消失败]\033[0m task_ref={task_ref} task_id={context.job.task_id} task_hash={context.job.task_hash} lease_version={lease_version} 错误=approval_record missing or lease_version mismatch\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表里的待确认导入审批是否仍存在，或是否已被其他路径抢先取消/确认；当前 confirm 会直接返回状态读取失败，避免把审批真相缺口误判成普通“导入确认已超时”。",
            flush=True,
        )
        return False

    def _cancel_pending_job(
        self,
        *,
        task_ref: str,
        context: ConfirmExecutionContext,
        log_expired_cancel_pending_job_result_missing: LogExpiredCancelPendingJobResultMissingFunc,
    ) -> bool:
        if self._job_repo is None or context.job.state != self._job_state_pending_approval:
            return True
        try:
            cancelled = self._job_repo.cancel_pending_job(
                job_id=context.job.job_id,
                expected_version=context.job.version,
                workflow_type=self._workflow_import_to_library,
            )
            if cancelled is None:
                raise RuntimeError(self._import_cancel_pending_job_result_missing_reason)
        except Exception as error:
            if str(error) in {
                self._import_cancel_pending_job_result_missing_reason,
                self._import_cancel_pending_job_row_missing_reason,
            }:
                log_expired_cancel_pending_job_result_missing(
                    job=context.job,
                    task_ref=task_ref,
                    reason=str(error),
                )
            else:
                print(
                    f"\033[31m[导入确认超时任务取消失败]\033[0m task_ref={task_ref} job_id={context.job.job_id} task_id={context.job.task_id} task_hash={context.job.task_hash} version={context.job.version} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表更新是否正常；当前 confirm 会直接返回状态读取失败，避免把任务真相缺口误判成普通“导入确认已超时”。",
                    flush=True,
                )
            return False
        if cancelled:
            return True
        print(
            f"\033[31m[导入确认超时任务取消失败]\033[0m task_ref={task_ref} job_id={context.job.job_id} task_id={context.job.task_id} task_hash={context.job.task_hash} version={context.job.version} 错误=jobs.cancel_pending_job rejected current state\n\033[33m[处理建议]\033[0m 检查该任务是否已被其他路径抢先取消、确认或完结；当前 confirm 会直接返回状态读取失败，避免把任务状态迁移冲突误判成普通“导入确认已超时”。",
            flush=True,
        )
        return False

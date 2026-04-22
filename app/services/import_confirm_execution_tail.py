from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.services.import_context_lookup import ConfirmExecutionContext
from app.services.import_transfer_execution import ImportExecutionResult

LogTraceFunc = Callable[..., None]
RestorePendingApprovalFunc = Callable[..., bool | None]
RestorePendingJobFunc = Callable[..., None]
RecordExecutedLeaseVersionFunc = Callable[..., bool | None]
MarkCompletedJobFunc = Callable[..., bool | None]
RecordPendingJobFunc = Callable[..., bool]
RecordCopyFallbackPendingFunc = Callable[..., None]
ClearPendingCopyFallbackFunc = Callable[..., None]
CopyFallbackPendingToJsonFunc = Callable[[], str]


@dataclass(frozen=True, slots=True)
class ImportConfirmExecutionRequest:
    task_ref: str
    task_id: str
    task_hash: str
    chat_id: int | None
    user_id: int | None
    execution: ImportExecutionResult
    execution_mode: str
    expected_lease_version: int
    claimed_job: bool
    claimed_job_id: str
    claimed_job_version: int
    lease_owner: str
    confirm_context: ConfirmExecutionContext | None


class ImportConfirmExecutionTail:
    def __init__(
        self,
        *,
        import_confirm_state_unavailable_text: str,
        import_finalization_warning_text: str,
        import_execution_mode_copy: str,
    ) -> None:
        self._import_confirm_state_unavailable_text = import_confirm_state_unavailable_text
        self._import_finalization_warning_text = import_finalization_warning_text
        self._import_execution_mode_copy = import_execution_mode_copy

    def finalize(
        self,
        *,
        request: ImportConfirmExecutionRequest,
        log_trace: LogTraceFunc,
        restore_pending_approval: RestorePendingApprovalFunc,
        restore_pending_job: RestorePendingJobFunc,
        record_executed_lease_version: RecordExecutedLeaseVersionFunc,
        mark_completed_job: MarkCompletedJobFunc,
        record_pending_job: RecordPendingJobFunc,
        record_copy_fallback_pending: RecordCopyFallbackPendingFunc,
        clear_pending_copy_fallback: ClearPendingCopyFallbackFunc,
        copy_fallback_pending_to_json: CopyFallbackPendingToJsonFunc,
    ) -> str:
        if request.execution.imported:
            return self._finalize_imported_execution(
                request=request,
                log_trace=log_trace,
                record_executed_lease_version=record_executed_lease_version,
                mark_completed_job=mark_completed_job,
                clear_pending_copy_fallback=clear_pending_copy_fallback,
            )
        if request.execution.pending_copy_approval:
            return self._finalize_copy_fallback_pending(
                request=request,
                log_trace=log_trace,
                restore_pending_approval=restore_pending_approval,
                restore_pending_job=restore_pending_job,
                record_pending_job=record_pending_job,
                record_copy_fallback_pending=record_copy_fallback_pending,
                copy_fallback_pending_to_json=copy_fallback_pending_to_json,
            )
        return self._finalize_failed_execution(
            request=request,
            log_trace=log_trace,
            restore_pending_approval=restore_pending_approval,
            restore_pending_job=restore_pending_job,
            record_pending_job=record_pending_job,
            record_copy_fallback_pending=record_copy_fallback_pending,
            clear_pending_copy_fallback=clear_pending_copy_fallback,
            copy_fallback_pending_to_json=copy_fallback_pending_to_json,
        )

    def _finalize_imported_execution(
        self,
        *,
        request: ImportConfirmExecutionRequest,
        log_trace: LogTraceFunc,
        record_executed_lease_version: RecordExecutedLeaseVersionFunc,
        mark_completed_job: MarkCompletedJobFunc,
        clear_pending_copy_fallback: ClearPendingCopyFallbackFunc,
    ) -> str:
        log_trace(
            event="confirm_execute",
            result="imported",
            stage="execute",
            chat_id=request.chat_id,
            user_id=request.user_id,
            task_ref=request.task_ref,
            task_id=request.task_id,
            task_hash=request.task_hash,
            detail=request.execution.reply,
        )
        finalization_warning = ""
        lease_recorded = record_executed_lease_version(
            task_ref=request.task_ref,
            task_id=request.task_id,
            task_hash=request.task_hash,
            executed_lease_version=request.expected_lease_version,
        )
        if lease_recorded is not True:
            finalization_warning = self._import_finalization_warning_text
        clear_pending_copy_fallback(task_id=request.task_id, task_hash=request.task_hash)
        if request.claimed_job:
            job_completed = mark_completed_job(
                job_id=request.claimed_job_id,
                expected_version=request.claimed_job_version,
                lease_owner=request.lease_owner,
            )
            if job_completed is not True:
                finalization_warning = self._import_finalization_warning_text
        if finalization_warning:
            log_trace(
                event="confirm_finalize",
                result="warning",
                stage="completed",
                chat_id=request.chat_id,
                user_id=request.user_id,
                task_ref=request.task_ref,
                task_id=request.task_id,
                task_hash=request.task_hash,
                detail=self._import_finalization_warning_text,
            )
            return f"{request.execution.reply}\n\n{finalization_warning}"
        log_trace(
            event="confirm_finalize",
            result="succeeded",
            stage="completed",
            chat_id=request.chat_id,
            user_id=request.user_id,
            task_ref=request.task_ref,
            task_id=request.task_id,
            task_hash=request.task_hash,
            detail=request.execution.reply,
        )
        return request.execution.reply

    def _finalize_copy_fallback_pending(
        self,
        *,
        request: ImportConfirmExecutionRequest,
        log_trace: LogTraceFunc,
        restore_pending_approval: RestorePendingApprovalFunc,
        restore_pending_job: RestorePendingJobFunc,
        record_pending_job: RecordPendingJobFunc,
        record_copy_fallback_pending: RecordCopyFallbackPendingFunc,
        copy_fallback_pending_to_json: CopyFallbackPendingToJsonFunc,
    ) -> str:
        log_trace(
            event="confirm_execute",
            result="copy_fallback_pending",
            stage="execute",
            chat_id=request.chat_id,
            user_id=request.user_id,
            task_ref=request.task_ref,
            task_id=request.task_id,
            task_hash=request.task_hash,
            detail=request.execution.reply,
        )
        approval_restored = restore_pending_approval(
            task_ref=request.task_ref,
            task_id=request.task_id,
            task_hash=request.task_hash,
            expected_lease_version=request.expected_lease_version,
        )
        if approval_restored is not True:
            self._restore_claimed_job_if_needed(
                request=request,
                restore_pending_job=restore_pending_job,
            )
            return self._import_confirm_state_unavailable_text
        record_copy_fallback_pending(task_id=request.task_id, task_hash=request.task_hash)
        if request.confirm_context is not None:
            persisted = record_pending_job(
                chat_id=request.confirm_context.job.chat_id,
                user_id=request.confirm_context.job.user_id,
                task_ref=request.confirm_context.job.task_ref or request.task_ref,
                task_id=request.task_id,
                task_hash=request.task_hash,
                payload_json=copy_fallback_pending_to_json(),
            )
            if not persisted:
                self._restore_claimed_job_if_needed(
                    request=request,
                    restore_pending_job=restore_pending_job,
                )
        return request.execution.reply

    def _finalize_failed_execution(
        self,
        *,
        request: ImportConfirmExecutionRequest,
        log_trace: LogTraceFunc,
        restore_pending_approval: RestorePendingApprovalFunc,
        restore_pending_job: RestorePendingJobFunc,
        record_pending_job: RecordPendingJobFunc,
        record_copy_fallback_pending: RecordCopyFallbackPendingFunc,
        clear_pending_copy_fallback: ClearPendingCopyFallbackFunc,
        copy_fallback_pending_to_json: CopyFallbackPendingToJsonFunc,
    ) -> str:
        approval_restored = restore_pending_approval(
            task_ref=request.task_ref,
            task_id=request.task_id,
            task_hash=request.task_hash,
            expected_lease_version=request.expected_lease_version,
        )
        if approval_restored is not True:
            self._restore_claimed_job_if_needed(
                request=request,
                restore_pending_job=restore_pending_job,
            )
            return self._import_confirm_state_unavailable_text
        if request.execution_mode == self._import_execution_mode_copy:
            record_copy_fallback_pending(task_id=request.task_id, task_hash=request.task_hash)
        else:
            clear_pending_copy_fallback(task_id=request.task_id, task_hash=request.task_hash)
        if request.claimed_job:
            if request.execution_mode == self._import_execution_mode_copy:
                persisted = record_pending_job(
                    chat_id=request.confirm_context.job.chat_id if request.confirm_context is not None else request.chat_id,
                    user_id=request.confirm_context.job.user_id if request.confirm_context is not None else request.user_id,
                    task_ref=request.confirm_context.job.task_ref if request.confirm_context is not None else request.task_ref,
                    task_id=request.task_id,
                    task_hash=request.task_hash,
                    payload_json=copy_fallback_pending_to_json(),
                )
                if not persisted:
                    self._restore_claimed_job_if_needed(
                        request=request,
                        restore_pending_job=restore_pending_job,
                    )
            else:
                self._restore_claimed_job_if_needed(
                    request=request,
                    restore_pending_job=restore_pending_job,
                )
        log_trace(
            event="confirm_execute",
            result="failed",
            stage="execute",
            chat_id=request.chat_id,
            user_id=request.user_id,
            task_ref=request.task_ref,
            task_id=request.task_id,
            task_hash=request.task_hash,
            detail=request.execution.reply,
        )
        return request.execution.reply

    def _restore_claimed_job_if_needed(
        self,
        *,
        request: ImportConfirmExecutionRequest,
        restore_pending_job: RestorePendingJobFunc,
    ) -> None:
        if not request.claimed_job:
            return
        restore_pending_job(
            job_id=request.claimed_job_id,
            expected_version=request.claimed_job_version,
            lease_owner=request.lease_owner,
        )

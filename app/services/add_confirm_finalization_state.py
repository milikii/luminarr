from __future__ import annotations

from collections.abc import Callable

from app.services.add_execution_follow_up import AddResult
from app.services.add_pending_context import PendingAddContext, to_completed_pending_add_context

RecordExecutedLeaseVersionFunc = Callable[..., bool | None]
MoveCompletedApprovalIdentityFunc = Callable[..., bool | None]
MarkCompletedJobFunc = Callable[..., bool | None]
ClearPendingContextFunc = Callable[..., None]
LogTraceFunc = Callable[..., None]


class AddConfirmFinalizationState:
    def __init__(
        self,
        *,
        add_finalization_warning_text: str,
        log_trace_func: LogTraceFunc,
    ) -> None:
        self._add_finalization_warning_text = add_finalization_warning_text
        self._log_trace = log_trace_func

    def finalize_confirmation(
        self,
        *,
        task_ref: str,
        pending_add: PendingAddContext,
        result: AddResult,
        reply: str,
        chat_id: int | None,
        user_id: int | None,
        expected_lease_version: int,
        claimed_job: bool,
        claimed_job_id: str,
        claimed_job_version: int,
        lease_owner: str,
        record_executed_lease_version: RecordExecutedLeaseVersionFunc,
        move_completed_approval_identity: MoveCompletedApprovalIdentityFunc,
        mark_completed_job: MarkCompletedJobFunc,
        clear_pending_context: ClearPendingContextFunc,
    ) -> str:
        finalization_warning = ""
        lease_recorded = record_executed_lease_version(
            task_ref=task_ref,
            task_id=pending_add.task_id,
            task_hash=pending_add.task_hash,
            executed_lease_version=expected_lease_version,
        )
        if lease_recorded is not True:
            finalization_warning = self._add_finalization_warning_text
        approval_identity_moved = move_completed_approval_identity(
            current_task_id=pending_add.task_id,
            current_task_hash=pending_add.task_hash,
            new_task_id=pending_add.task_id,
            new_task_hash=result.task_hash,
        )
        if approval_identity_moved is not True:
            finalization_warning = self._add_finalization_warning_text
        if claimed_job:
            completed_context = to_completed_pending_add_context(
                pending_add,
                actual_task_id=pending_add.task_id,
                actual_task_hash=result.task_hash,
            )
            job_completed = mark_completed_job(
                job_id=claimed_job_id,
                expected_version=claimed_job_version,
                lease_owner=lease_owner,
                completed_add=completed_context,
            )
            if job_completed is not True:
                finalization_warning = self._add_finalization_warning_text
        clear_pending_context(chat_id=chat_id, task_ref=task_ref)
        if finalization_warning:
            self._log_trace(
                event="confirm_finalize",
                result="warning",
                stage="completed",
                chat_id=chat_id,
                user_id=user_id,
                task_ref=task_ref,
                task_id=result.task_id,
                task_hash=result.task_hash,
                detail=self._add_finalization_warning_text,
            )
            return f"{reply}\n\n{finalization_warning}"
        self._log_trace(
            event="confirm_finalize",
            result="succeeded",
            stage="completed",
            chat_id=chat_id,
            user_id=user_id,
            task_ref=task_ref,
            task_id=result.task_id,
            task_hash=result.task_hash,
            detail=result.title,
        )
        return reply

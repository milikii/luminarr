from __future__ import annotations

from collections.abc import Callable

from app.services.add_confirm_finalization_state import AddConfirmFinalizationState
from app.services.add_execution_follow_up import AddExecutionFollowUpService
from app.services.add_pending_context import PendingAddContext

RecordEventFunc = Callable[..., None]
RestorePendingApprovalFunc = Callable[..., bool | None]
RestorePendingJobFunc = Callable[..., None]
RecordExecutedLeaseVersionFunc = Callable[..., bool | None]
MoveCompletedApprovalIdentityFunc = Callable[..., bool | None]
MarkCompletedJobFunc = Callable[..., bool | None]
ClearPendingContextFunc = Callable[..., None]


class AddConfirmExecutionTail:
    def __init__(
        self,
        *,
        execution_follow_up: AddExecutionFollowUpService,
        confirm_finalization_state: AddConfirmFinalizationState,
        add_confirm_state_unavailable_text: str,
    ) -> None:
        self._execution_follow_up = execution_follow_up
        self._confirm_finalization_state = confirm_finalization_state
        self._add_confirm_state_unavailable_text = add_confirm_state_unavailable_text

    async def run(
        self,
        *,
        task_ref: str,
        pending_add: PendingAddContext,
        chat_id: int | None,
        user_id: int | None,
        expected_lease_version: int,
        claimed_job: bool,
        claimed_job_id: str,
        claimed_job_version: int,
        lease_owner: str,
        record_event: RecordEventFunc,
        restore_pending_approval: RestorePendingApprovalFunc,
        restore_pending_job: RestorePendingJobFunc,
        record_executed_lease_version: RecordExecutedLeaseVersionFunc,
        move_completed_approval_identity: MoveCompletedApprovalIdentityFunc,
        mark_completed_job: MarkCompletedJobFunc,
        clear_pending_context: ClearPendingContextFunc,
    ) -> str:
        record_event(
            task_ref=task_ref,
            task_id=pending_add.task_id,
            task_hash=pending_add.task_hash,
            event_type="downloader.approval_confirmed",
            message=pending_add.title,
        )

        execution = await self._execution_follow_up.dispatch(
            task_ref=task_ref,
            pending_add=pending_add,
            chat_id=chat_id,
            user_id=user_id,
        )
        if execution.result is None:
            approval_restored = restore_pending_approval(
                task_ref=task_ref,
                task_id=pending_add.task_id,
                task_hash=pending_add.task_hash,
                expected_lease_version=expected_lease_version,
            )
            if claimed_job:
                restore_pending_job(
                    job_id=claimed_job_id,
                    expected_version=claimed_job_version,
                    lease_owner=lease_owner,
                )
            if approval_restored is not True:
                return self._add_confirm_state_unavailable_text
            return execution.reply

        result = execution.result
        reply = execution.reply
        return self._confirm_finalization_state.finalize_confirmation(
            task_ref=task_ref,
            pending_add=pending_add,
            result=result,
            reply=reply,
            chat_id=chat_id,
            user_id=user_id,
            expected_lease_version=expected_lease_version,
            claimed_job=claimed_job,
            claimed_job_id=claimed_job_id,
            claimed_job_version=claimed_job_version,
            lease_owner=lease_owner,
            record_executed_lease_version=record_executed_lease_version,
            move_completed_approval_identity=move_completed_approval_identity,
            mark_completed_job=mark_completed_job,
            clear_pending_context=clear_pending_context,
        )

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.db.approval_repo import APPROVAL_STATUS_PENDING
from app.db.job_repo import JOB_STATE_PENDING_APPROVAL
from app.services.add_confirm_context_state import ConfirmExecutionContext
from app.services.add_pending_context import PendingAddContext

FindVersionStaleRejectionTextFunc = Callable[..., str | None]
GetInMemoryPendingFunc = Callable[..., PendingAddContext | None]
HandleExpiredPendingConfirmFunc = Callable[..., str | None]
LogPendingJobResultMissingFunc = Callable[..., None]
RebuildConfirmContextFunc = Callable[..., tuple[ConfirmExecutionContext | None, bool]]


@dataclass(frozen=True, slots=True)
class ConfirmAvailabilityResolution:
    confirm_context: ConfirmExecutionContext | None
    in_memory_pending: PendingAddContext | None


class AddConfirmAvailabilityState:
    def __init__(
        self,
        *,
        add_confirm_not_pending_text: str,
        add_confirm_state_unavailable_text: str,
    ) -> None:
        self._add_confirm_not_pending_text = add_confirm_not_pending_text
        self._add_confirm_state_unavailable_text = add_confirm_state_unavailable_text

    def resolve(
        self,
        *,
        task_ref: str,
        chat_id: int | None,
        job_repo_available: bool,
        rebuild_confirm_context: RebuildConfirmContextFunc,
        get_in_memory_pending: GetInMemoryPendingFunc,
        log_pending_job_result_missing: LogPendingJobResultMissingFunc,
        find_version_stale_rejection_text: FindVersionStaleRejectionTextFunc,
        handle_expired_pending_confirm: HandleExpiredPendingConfirmFunc,
    ) -> tuple[ConfirmAvailabilityResolution | None, str | None]:
        confirm_context, confirm_context_unavailable = rebuild_confirm_context(
            task_ref=task_ref,
            chat_id=chat_id,
        )
        if confirm_context is None:
            return self._resolve_missing_confirm_context(
                task_ref=task_ref,
                chat_id=chat_id,
                confirm_context_unavailable=confirm_context_unavailable,
                job_repo_available=job_repo_available,
                get_in_memory_pending=get_in_memory_pending,
                log_pending_job_result_missing=log_pending_job_result_missing,
            )

        if confirm_context.approval_lookup_failed:
            return None, self._add_confirm_state_unavailable_text
        if confirm_context.job.state != JOB_STATE_PENDING_APPROVAL:
            return None, self._resolve_not_pending_rejection_text(
                task_id=confirm_context.pending_add.task_id,
                task_hash=confirm_context.pending_add.task_hash,
                find_version_stale_rejection_text=find_version_stale_rejection_text,
            )
        if (
            confirm_context.approval_record is None
            or confirm_context.approval_record.status != APPROVAL_STATUS_PENDING
        ):
            return None, self._resolve_not_pending_rejection_text(
                task_id=confirm_context.pending_add.task_id,
                task_hash=confirm_context.pending_add.task_hash,
                find_version_stale_rejection_text=find_version_stale_rejection_text,
            )
        expired_text = handle_expired_pending_confirm(
            task_ref=task_ref,
            context=confirm_context,
            chat_id=chat_id,
        )
        if expired_text is not None:
            return None, expired_text
        return ConfirmAvailabilityResolution(confirm_context=confirm_context, in_memory_pending=None), None

    def _resolve_missing_confirm_context(
        self,
        *,
        task_ref: str,
        chat_id: int | None,
        confirm_context_unavailable: bool,
        job_repo_available: bool,
        get_in_memory_pending: GetInMemoryPendingFunc,
        log_pending_job_result_missing: LogPendingJobResultMissingFunc,
    ) -> tuple[ConfirmAvailabilityResolution | None, str | None]:
        if confirm_context_unavailable:
            return None, self._add_confirm_state_unavailable_text
        in_memory_pending = get_in_memory_pending(chat_id=chat_id, task_ref=task_ref)
        if in_memory_pending is None:
            return None, self._add_confirm_not_pending_text
        if job_repo_available and chat_id is not None and chat_id > 0:
            log_pending_job_result_missing(
                chat_id=chat_id,
                task_ref=task_ref,
                task_id=in_memory_pending.task_id,
                task_hash=in_memory_pending.task_hash,
                stage="confirm",
            )
            return None, self._add_confirm_state_unavailable_text
        return ConfirmAvailabilityResolution(confirm_context=None, in_memory_pending=in_memory_pending), None

    def _resolve_not_pending_rejection_text(
        self,
        *,
        task_id: str,
        task_hash: str,
        find_version_stale_rejection_text: FindVersionStaleRejectionTextFunc,
    ) -> str:
        stale_text = find_version_stale_rejection_text(task_id=task_id, task_hash=task_hash)
        return stale_text or self._add_confirm_not_pending_text

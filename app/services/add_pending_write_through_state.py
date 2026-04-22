from __future__ import annotations

from collections.abc import Callable

from app.services.add_pending_context import PendingAddContext
from app.services.add_pending_persistence import render_add_pending_reply

CancelPendingApprovalFunc = Callable[..., bool]
ClearPendingContextFunc = Callable[..., None]
LogTraceFunc = Callable[..., None]
RecordEventFunc = Callable[..., None]
RecordPendingApprovalFunc = Callable[..., int]
RecordPendingContextFunc = Callable[..., None]
RecordPendingJobFunc = Callable[..., bool]


class AddPendingWriteThroughState:
    def __init__(
        self,
        *,
        add_pending_state_unavailable_text: str,
        add_approval_pending_text_template: str,
        supported_delivery_channels: frozenset[str],
    ) -> None:
        self._add_pending_state_unavailable_text = add_pending_state_unavailable_text
        self._add_approval_pending_text_template = add_approval_pending_text_template
        self._supported_delivery_channels = supported_delivery_channels

    def persist_pending_add(
        self,
        *,
        chat_id: int,
        user_id: int | None,
        pending_add: PendingAddContext,
        channel: str | None,
        record_pending_approval: RecordPendingApprovalFunc,
        record_pending_context: RecordPendingContextFunc,
        record_pending_job: RecordPendingJobFunc,
        clear_pending_context: ClearPendingContextFunc,
        cancel_pending_approval: CancelPendingApprovalFunc,
        record_event: RecordEventFunc,
        log_trace: LogTraceFunc,
    ) -> str:
        expected_lease_version = record_pending_approval(
            task_ref=pending_add.task_ref,
            task_id=pending_add.task_id,
            task_hash=pending_add.task_hash,
        )
        if expected_lease_version <= 0:
            return self._add_pending_state_unavailable_text
        record_pending_context(chat_id=chat_id, pending_add=pending_add)
        if not record_pending_job(chat_id=chat_id, user_id=user_id, pending_add=pending_add):
            clear_pending_context(chat_id=chat_id, task_ref=pending_add.task_ref)
            cancel_pending_approval(
                task_ref=pending_add.task_ref,
                task_id=pending_add.task_id,
                task_hash=pending_add.task_hash,
                expected_lease_version=expected_lease_version,
            )
            return self._add_pending_state_unavailable_text
        record_event(
            task_ref=pending_add.task_ref,
            task_id=pending_add.task_id,
            task_hash=pending_add.task_hash,
            event_type="downloader.approval_pending",
            message=pending_add.title,
        )
        log_trace(
            event="approval_pending",
            result="created",
            stage="pending",
            chat_id=chat_id,
            user_id=user_id,
            task_ref=pending_add.task_ref,
            task_id=pending_add.task_id,
            task_hash=pending_add.task_hash,
            detail=pending_add.title,
        )
        if channel in self._supported_delivery_channels:
            return render_add_pending_reply(pending_add=pending_add, channel=channel)
        return self._add_approval_pending_text_template.format(title=pending_add.title, task_ref=pending_add.task_ref)

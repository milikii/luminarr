from __future__ import annotations

import sqlite3
from collections.abc import Callable

from app.clients.transmission import TransmissionImportSource
from app.db.approval_repo import ApprovalPersistenceError, ApprovalRepo
from app.operational_logging import format_operational_log_message

LogTraceFunc = Callable[..., None]
RecordImportEventFunc = Callable[..., None]
RecordPendingApprovalFunc = Callable[..., int]
RecordPendingJobFunc = Callable[..., bool]


class ImportPendingWriteThroughState:
    def __init__(
        self,
        *,
        approval_repo: ApprovalRepo | None,
        import_pending_state_unavailable_text: str,
        import_approval_pending_text_template: str,
    ) -> None:
        self._approval_repo = approval_repo
        self._import_pending_state_unavailable_text = import_pending_state_unavailable_text
        self._import_approval_pending_text_template = import_approval_pending_text_template

    def persist_pending_import(
        self,
        *,
        task_ref: str,
        import_source: TransmissionImportSource,
        chat_id: int | None,
        user_id: int | None,
        record_pending_approval: RecordPendingApprovalFunc,
        record_pending_job: RecordPendingJobFunc,
        record_event: RecordImportEventFunc,
        log_trace: LogTraceFunc,
    ) -> str:
        expected_lease_version = record_pending_approval(
            task_ref=task_ref,
            task_id=import_source.task_id,
            task_hash=import_source.task_hash,
        )
        if expected_lease_version <= 0:
            return self._import_pending_state_unavailable_text
        if not record_pending_job(
            chat_id=chat_id,
            user_id=user_id,
            task_ref=task_ref,
            task_id=import_source.task_id,
            task_hash=import_source.task_hash,
            payload_json="",
        ):
            self._cancel_pending_approval(
                task_ref=task_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                expected_lease_version=expected_lease_version,
            )
            return self._import_pending_state_unavailable_text
        record_event(
            task_ref=task_ref,
            task_id=import_source.task_id,
            task_hash=import_source.task_hash,
            event_type="import.approval_pending",
            message=task_ref,
        )
        log_trace(
            event="approval_pending",
            result="created",
            stage="pending",
            chat_id=chat_id,
            user_id=user_id,
            task_ref=task_ref,
            task_id=import_source.task_id,
            task_hash=import_source.task_hash,
            detail=import_source.name,
        )
        return self._import_approval_pending_text_template.format(
            name=import_source.name,
            task_id=import_source.task_id,
            task_hash=import_source.task_hash,
            task_ref=task_ref,
        )

    def _cancel_pending_approval(
        self,
        *,
        task_ref: str,
        task_id: str,
        task_hash: str,
        expected_lease_version: int,
    ) -> None:
        if self._approval_repo is None:
            return
        try:
            self._approval_repo.cancel_import(
                task_id=task_id,
                task_hash=task_hash,
                task_ref=task_ref,
                expected_lease_version=expected_lease_version,
            )
        except (ApprovalPersistenceError, sqlite3.Error) as error:
            print(
                format_operational_log_message(
                    title="导入取消审批更新失败",
                    detail=f"task_ref={task_ref} task_id={task_id} task_hash={task_hash} lease_version={expected_lease_version} 错误={error}",
                    fix_hint="检查 SQLite/approval_record 表更新是否正常；当前导入待确认创建会直接失败返回，但审批真相可能仍残留。",
                ),
                flush=True,
            )

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass

from app.db.approval_repo import ApprovalRecord, ApprovalRepo
from app.db.job_repo import JobRecord, JobRepo


@dataclass(frozen=True, slots=True)
class ConfirmExecutionContext:
    job: JobRecord
    approval_record: ApprovalRecord | None
    approval_lookup_failed: bool = False

    @property
    def lookup_task_ref(self) -> str:
        if self.job.task_hash:
            return self.job.task_hash
        if self.job.task_id:
            return self.job.task_id
        return self.job.task_ref


@dataclass(frozen=True, slots=True)
class ConfirmContextLookupResult:
    context: ConfirmExecutionContext | None
    lookup_failed: bool = False
    job_error_kind: str = ""
    job_error_detail: str = ""
    approval_error_detail: str = ""


@dataclass(frozen=True, slots=True)
class RawBtTaskLookupResult:
    is_raw_bt: bool | None
    error_kind: str = ""
    detail: str = ""


class ImportContextLookup:
    def __init__(
        self,
        *,
        job_repo: JobRepo | None,
        approval_repo: ApprovalRepo | None,
        is_job_row_corrupted_error: Callable[[Exception], bool],
    ) -> None:
        self._job_repo = job_repo
        self._approval_repo = approval_repo
        self._is_job_row_corrupted_error = is_job_row_corrupted_error

    def rebuild_confirm_context(
        self,
        *,
        task_ref: str,
        chat_id: int | None,
    ) -> ConfirmContextLookupResult:
        if self._job_repo is None or chat_id is None or chat_id <= 0:
            return ConfirmContextLookupResult(context=None)
        try:
            job = self._job_repo.get_import_job_for_chat_ref(chat_id=chat_id, task_ref=task_ref)
        except Exception as error:
            error_kind = "row_corrupted" if self._is_job_row_corrupted_error(error) else "lookup_failed"
            return ConfirmContextLookupResult(
                context=None,
                lookup_failed=True,
                job_error_kind=error_kind,
                job_error_detail=str(error),
            )
        if job is None:
            return ConfirmContextLookupResult(context=None)

        approval_record: ApprovalRecord | None = None
        approval_lookup_failed = False
        approval_error_detail = ""
        if self._approval_repo is not None:
            try:
                approval_record = self._approval_repo.get_import_approval(
                    task_id=job.task_id,
                    task_hash=job.task_hash,
                )
            except Exception as error:
                approval_lookup_failed = True
                approval_error_detail = str(error)
        return ConfirmContextLookupResult(
            context=ConfirmExecutionContext(
                job=job,
                approval_record=approval_record,
                approval_lookup_failed=approval_lookup_failed,
            ),
            approval_error_detail=approval_error_detail,
        )

    def lookup_raw_bt_task(
        self,
        *,
        chat_id: int | None,
        task_ref: str,
    ) -> RawBtTaskLookupResult:
        if self._job_repo is None or chat_id is None or chat_id <= 0:
            return RawBtTaskLookupResult(is_raw_bt=False)
        try:
            downloader_job = self._job_repo.get_downloader_job_for_chat_ref(chat_id=chat_id, task_ref=task_ref)
        except Exception as error:
            error_kind = "row_corrupted" if self._is_job_row_corrupted_error(error) else "lookup_failed"
            return RawBtTaskLookupResult(is_raw_bt=None, error_kind=error_kind, detail=str(error))
        if downloader_job is None:
            return RawBtTaskLookupResult(is_raw_bt=None, error_kind="result_missing")

        cleaned_payload = downloader_job.payload_json.strip()
        if not cleaned_payload:
            return RawBtTaskLookupResult(is_raw_bt=None, error_kind="payload_corrupted", detail="payload_json empty")
        try:
            payload = json.loads(cleaned_payload)
        except json.JSONDecodeError:
            return RawBtTaskLookupResult(is_raw_bt=None, error_kind="payload_corrupted", detail="payload_json invalid json")
        if not isinstance(payload, dict):
            return RawBtTaskLookupResult(is_raw_bt=None, error_kind="payload_corrupted", detail="payload_json not object")
        return RawBtTaskLookupResult(is_raw_bt=payload.get("auto_import_enabled") is False)

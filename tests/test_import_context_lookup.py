from __future__ import annotations

import sqlite3

import pytest

from app.db.approval_repo import ApprovalPersistenceError
from app.db.job_repo import JobPersistenceError, JobRecord
from app.services.import_context_lookup import ImportContextLookup


def _job_record(*, payload_json: str = "{}") -> JobRecord:
    return JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="import_to_library",
        state="pending_approval",
        task_ref="87",
        task_id="task-87",
        task_hash="hash-87",
        payload_json=payload_json,
        version=1,
        lease_owner="",
        lease_until="",
        created_at="2026-04-27T00:00:00Z",
        updated_at="2026-04-27T00:00:00Z",
    )


def test_rebuild_confirm_context_reports_job_lookup_failure() -> None:
    class FailingJobRepo:
        def get_import_job_for_chat_ref(self, *, chat_id: int, task_ref: str):
            raise JobPersistenceError("job down")

    lookup = ImportContextLookup(
        job_repo=FailingJobRepo(),  # type: ignore[arg-type]
        approval_repo=None,
        is_job_row_corrupted_error=lambda error: False,
    )

    result = lookup.rebuild_confirm_context(task_ref="87", chat_id=1001)

    assert result.context is None
    assert result.lookup_failed is True
    assert result.job_error_kind == "lookup_failed"
    assert result.job_error_detail == "job down"


def test_rebuild_confirm_context_reports_approval_lookup_failure() -> None:
    class JobRepo:
        def get_import_job_for_chat_ref(self, *, chat_id: int, task_ref: str):
            return _job_record()

    class FailingApprovalRepo:
        def get_import_approval(self, *, task_id: str, task_hash: str):
            raise ApprovalPersistenceError("approval down")

    lookup = ImportContextLookup(
        job_repo=JobRepo(),  # type: ignore[arg-type]
        approval_repo=FailingApprovalRepo(),  # type: ignore[arg-type]
        is_job_row_corrupted_error=lambda error: False,
    )

    result = lookup.rebuild_confirm_context(task_ref="87", chat_id=1001)

    assert result.context is not None
    assert result.context.approval_record is None
    assert result.context.approval_lookup_failed is True
    assert result.approval_error_detail == "approval down"


def test_lookup_raw_bt_task_reports_sqlite_failure() -> None:
    class FailingJobRepo:
        def get_downloader_job_for_chat_ref(self, *, chat_id: int, task_ref: str):
            raise sqlite3.OperationalError("database locked")

    lookup = ImportContextLookup(
        job_repo=FailingJobRepo(),  # type: ignore[arg-type]
        approval_repo=None,
        is_job_row_corrupted_error=lambda error: False,
    )

    result = lookup.lookup_raw_bt_task(chat_id=1001, task_ref="1")

    assert result.is_raw_bt is None
    assert result.error_kind == "lookup_failed"
    assert result.detail == "database locked"


def test_rebuild_confirm_context_does_not_swallow_programming_errors() -> None:
    class BrokenJobRepo:
        def get_import_job_for_chat_ref(self, *, chat_id: int, task_ref: str):
            raise ValueError("bad fake")

    lookup = ImportContextLookup(
        job_repo=BrokenJobRepo(),  # type: ignore[arg-type]
        approval_repo=None,
        is_job_row_corrupted_error=lambda error: False,
    )

    with pytest.raises(ValueError, match="bad fake"):
        lookup.rebuild_confirm_context(task_ref="87", chat_id=1001)

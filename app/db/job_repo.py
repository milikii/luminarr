from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.db.job_repo_support import (
    fetch_job_row_by_chat_task_ref,
    fetch_job_row_by_identity,
    fetch_latest_pending_job_row,
    normalize_downloader_completed_job_identity,
    normalize_job_chat_task_query_identity,
    normalize_job_lease_identity,
    normalize_job_pending_cancel_identity,
    normalize_job_pending_query_identity,
    normalize_job_pending_upsert_identity,
    normalize_job_workflow,
    resolve_job_record_from_row,
    upsert_pending_job_row,
    update_downloader_job_completed,
    update_job_cancel_pending,
    update_job_lease_claim,
    update_job_state_transition,
)
from app.db.sqlite import SqliteDatabase

JOB_STATE_CANCELLED = "cancelled"
JOB_STATE_COMPLETED = "completed"
JOB_STATE_PENDING_APPROVAL = "pending_approval"
LEASE_SECONDS = 30
WORKFLOW_ADD_TO_DOWNLOADER = "add_to_downloader"
WORKFLOW_IMPORT_TO_LIBRARY = "import_to_library"


@dataclass(frozen=True, slots=True)
class JobRecord:
    job_id: str
    chat_id: int
    user_id: int
    workflow_type: str
    state: str
    task_ref: str
    task_id: str
    task_hash: str
    payload_json: str
    version: int
    lease_owner: str
    lease_until: str
    created_at: str
    updated_at: str


class JobPersistenceError(RuntimeError):
    pass


class JobRepo:
    def __init__(self, database: SqliteDatabase) -> None:
        self._database = database

    def upsert_import_job_pending(
        self,
        *,
        chat_id: int | None,
        user_id: int | None,
        task_ref: str,
        task_id: str,
        task_hash: str,
        payload_json: str = "",
    ) -> JobRecord | None:
        return self._upsert_job_pending(
            workflow_type=WORKFLOW_IMPORT_TO_LIBRARY,
            chat_id=chat_id,
            user_id=user_id,
            task_ref=task_ref,
            task_id=task_id,
            task_hash=task_hash,
            payload_json=payload_json,
        )

    def upsert_downloader_job_pending(
        self,
        *,
        chat_id: int | None,
        user_id: int | None,
        task_ref: str,
        task_id: str,
        task_hash: str,
        payload_json: str,
    ) -> JobRecord | None:
        return self._upsert_job_pending(
            workflow_type=WORKFLOW_ADD_TO_DOWNLOADER,
            chat_id=chat_id,
            user_id=user_id,
            task_ref=task_ref,
            task_id=task_id,
            task_hash=task_hash,
            payload_json=payload_json,
        )

    def get_import_job_for_chat_ref(self, *, chat_id: int, task_ref: str) -> JobRecord | None:
        return self._get_job_for_chat_ref(
            workflow_type=WORKFLOW_IMPORT_TO_LIBRARY,
            chat_id=chat_id,
            task_ref=task_ref,
        )

    def get_downloader_job_for_chat_ref(self, *, chat_id: int, task_ref: str) -> JobRecord | None:
        return self._get_job_for_chat_ref(
            workflow_type=WORKFLOW_ADD_TO_DOWNLOADER,
            chat_id=chat_id,
            task_ref=task_ref,
        )

    def get_pending_job_for_chat_ref(self, *, chat_id: int, task_ref: str) -> JobRecord | None:
        identity = normalize_job_chat_task_query_identity(
            chat_id=chat_id,
            task_ref=task_ref,
            context="query",
            error_cls=JobPersistenceError,
        )
        with self._database.connect() as connection:
            row = fetch_job_row_by_chat_task_ref(
                connection=connection,
                chat_id=identity.chat_id,
                task_ref=identity.task_ref,
                state=JOB_STATE_PENDING_APPROVAL,
            )
        return resolve_job_record_from_row(
            row=row,
            to_job_record=_to_job_record,
        )

    def get_job_for_chat_ref(self, *, chat_id: int, task_ref: str) -> JobRecord | None:
        identity = normalize_job_chat_task_query_identity(
            chat_id=chat_id,
            task_ref=task_ref,
            context="query",
            error_cls=JobPersistenceError,
        )
        with self._database.connect() as connection:
            row = fetch_job_row_by_chat_task_ref(
                connection=connection,
                chat_id=identity.chat_id,
                task_ref=identity.task_ref,
            )
        return resolve_job_record_from_row(
            row=row,
            to_job_record=_to_job_record,
        )

    def get_latest_pending_import_job(self, *, chat_id: int) -> JobRecord | None:
        return self._get_latest_pending_job_for_workflow(
            workflow_type=WORKFLOW_IMPORT_TO_LIBRARY,
            chat_id=chat_id,
        )

    def get_latest_pending_downloader_job(self, *, chat_id: int) -> JobRecord | None:
        return self._get_latest_pending_job_for_workflow(
            workflow_type=WORKFLOW_ADD_TO_DOWNLOADER,
            chat_id=chat_id,
        )

    def get_latest_pending_job(self, *, chat_id: int) -> JobRecord | None:
        identity = normalize_job_pending_query_identity(
            chat_id=chat_id,
            context="pending query",
            error_cls=JobPersistenceError,
        )
        with self._database.connect() as connection:
            row = fetch_latest_pending_job_row(
                connection=connection,
                chat_id=identity.chat_id,
                pending_state=JOB_STATE_PENDING_APPROVAL,
            )
        return resolve_job_record_from_row(
            row=row,
            to_job_record=_to_job_record,
        )

    def claim_lease(
        self,
        *,
        job_id: str,
        expected_version: int,
        lease_owner: str,
        workflow_type: str,
    ) -> bool:
        identity = normalize_job_lease_identity(
            job_id=job_id,
            expected_version=expected_version,
            lease_owner=lease_owner,
            workflow_type=workflow_type,
            context="lease",
            error_cls=JobPersistenceError,
        )

        current_time = _utcnow()
        lease_until = _format_utc(current_time + timedelta(seconds=LEASE_SECONDS))
        current_time_text = _format_utc(current_time)
        with self._database.connect() as connection:
            rowcount = update_job_lease_claim(
                connection=connection,
                job_id=identity.job_id,
                expected_version=identity.expected_version,
                lease_owner=identity.lease_owner,
                workflow_type=identity.workflow_type,
                pending_state=JOB_STATE_PENDING_APPROVAL,
                current_time_text=current_time_text,
                lease_until=lease_until,
            )
            connection.commit()
        if rowcount == 1:
            return True
        self._require_job_by_identity(
            job_id=identity.job_id,
            workflow_type=identity.workflow_type,
            missing_error="job missing during lease claim",
        )
        return False

    def release_lease_to_pending(
        self,
        *,
        job_id: str,
        expected_version: int,
        lease_owner: str,
        workflow_type: str,
    ) -> bool:
        return self._set_job_state(
            job_id=job_id,
            expected_version=expected_version,
            lease_owner=lease_owner,
            workflow_type=workflow_type,
            next_state=JOB_STATE_PENDING_APPROVAL,
            bump_version=False,
        )

    def mark_completed(
        self,
        *,
        job_id: str,
        expected_version: int,
        lease_owner: str,
        workflow_type: str,
    ) -> bool:
        return self._set_job_state(
            job_id=job_id,
            expected_version=expected_version,
            lease_owner=lease_owner,
            workflow_type=workflow_type,
            next_state=JOB_STATE_COMPLETED,
            bump_version=True,
        )

    def mark_downloader_completed(
        self,
        *,
        job_id: str,
        expected_version: int,
        lease_owner: str,
        task_id: str,
        task_hash: str,
        payload_json: str,
    ) -> bool:
        if not job_id.strip() or not lease_owner.strip():
            raise JobPersistenceError("downloader completed job identity missing")
        if expected_version <= 0:
            raise JobPersistenceError("downloader completed job expected version missing")
        if not task_id.strip() or not task_hash.strip():
            raise JobPersistenceError("downloader completed job identity missing")
        identity = normalize_downloader_completed_job_identity(
            job_id=job_id,
            expected_version=expected_version,
            lease_owner=lease_owner,
            task_id=task_id,
            task_hash=task_hash,
            workflow_type=WORKFLOW_ADD_TO_DOWNLOADER,
            error_cls=JobPersistenceError,
        )

        with self._database.connect() as connection:
            rowcount = update_downloader_job_completed(
                connection=connection,
                job_id=identity.job_id,
                expected_version=identity.expected_version,
                lease_owner=identity.lease_owner,
                task_id=identity.task_id,
                task_hash=identity.task_hash,
                payload_json=payload_json,
                completed_state=JOB_STATE_COMPLETED,
                workflow_type=identity.workflow_type,
            )
            connection.commit()
        return rowcount == 1

    def cancel_pending_job(self, *, job_id: str, expected_version: int, workflow_type: str) -> bool:
        identity = normalize_job_pending_cancel_identity(
            job_id=job_id,
            expected_version=expected_version,
            workflow_type=workflow_type,
            error_cls=JobPersistenceError,
        )

        current_time_text = _format_utc(_utcnow())
        with self._database.connect() as connection:
            rowcount = update_job_cancel_pending(
                connection=connection,
                job_id=identity.job_id,
                expected_version=identity.expected_version,
                workflow_type=identity.workflow_type,
                cancelled_state=JOB_STATE_CANCELLED,
                pending_state=JOB_STATE_PENDING_APPROVAL,
                current_time_text=current_time_text,
            )
            connection.commit()
        if rowcount == 1:
            return True
        self._require_job_by_identity(
            job_id=identity.job_id,
            workflow_type=identity.workflow_type,
            missing_error="job missing during cancel",
        )
        return False

    def _upsert_job_pending(
        self,
        *,
        workflow_type: str,
        chat_id: int | None,
        user_id: int | None,
        task_ref: str,
        task_id: str,
        task_hash: str,
        payload_json: str,
    ) -> JobRecord | None:
        identity = normalize_job_pending_upsert_identity(
            workflow_type=workflow_type,
            chat_id=chat_id,
            user_id=user_id,
            task_ref=task_ref,
            task_id=task_id,
            task_hash=task_hash,
            error_cls=JobPersistenceError,
        )

        job_id = _build_job_id(identity.workflow_type, identity.task_hash)
        with self._database.connect() as connection:
            upsert_pending_job_row(
                connection=connection,
                job_id=job_id,
                chat_id=identity.chat_id,
                user_id=identity.user_id,
                workflow_type=identity.workflow_type,
                pending_state=JOB_STATE_PENDING_APPROVAL,
                task_ref=identity.task_ref,
                task_id=identity.task_id,
                task_hash=identity.task_hash,
                payload_json=payload_json,
            )
            connection.commit()
        job = self._require_job_by_identity(
            job_id=job_id,
            workflow_type=identity.workflow_type,
            missing_error="job missing after pending upsert",
        )
        return job

    def _get_job_for_chat_ref(
        self,
        *,
        workflow_type: str,
        chat_id: int,
        task_ref: str,
    ) -> JobRecord | None:
        identity = normalize_job_chat_task_query_identity(
            chat_id=chat_id,
            task_ref=task_ref,
            context="query",
            error_cls=JobPersistenceError,
        )
        workflow = normalize_job_workflow(
            workflow_type=workflow_type,
            context="query",
            error_cls=JobPersistenceError,
        )
        with self._database.connect() as connection:
            row = fetch_job_row_by_chat_task_ref(
                connection=connection,
                chat_id=identity.chat_id,
                task_ref=identity.task_ref,
                workflow_type=workflow.workflow_type,
            )
        return resolve_job_record_from_row(
            row=row,
            to_job_record=_to_job_record,
        )

    def _get_latest_pending_job_for_workflow(
        self,
        *,
        workflow_type: str,
        chat_id: int,
    ) -> JobRecord | None:
        identity = normalize_job_pending_query_identity(
            chat_id=chat_id,
            workflow_type=workflow_type,
            context="pending query",
            error_cls=JobPersistenceError,
        )
        with self._database.connect() as connection:
            row = fetch_latest_pending_job_row(
                connection=connection,
                chat_id=identity.chat_id,
                workflow_type=identity.workflow_type,
                pending_state=JOB_STATE_PENDING_APPROVAL,
            )
        return resolve_job_record_from_row(
            row=row,
            to_job_record=_to_job_record,
        )

    def _set_job_state(
        self,
        *,
        job_id: str,
        expected_version: int,
        lease_owner: str,
        workflow_type: str,
        next_state: str,
        bump_version: bool,
    ) -> bool:
        lease = normalize_job_lease_identity(
            job_id=job_id,
            expected_version=expected_version,
            lease_owner=lease_owner,
            workflow_type=workflow_type,
            context="state transition",
            error_cls=JobPersistenceError,
        )
        cleaned_state = next_state.strip()
        if not cleaned_state:
            raise JobPersistenceError("job state transition identity missing")

        with self._database.connect() as connection:
            rowcount = update_job_state_transition(
                connection=connection,
                job_id=lease.job_id,
                expected_version=lease.expected_version,
                workflow_type=lease.workflow_type,
                lease_owner=lease.lease_owner,
                next_state=cleaned_state,
                bump_version=bump_version,
            )
            connection.commit()
        if rowcount == 1:
            return True
        self._require_job_by_identity(
            job_id=lease.job_id,
            workflow_type=lease.workflow_type,
            missing_error="job missing during state transition",
        )
        return False

    def _get_job_by_identity(self, *, job_id: str, workflow_type: str) -> JobRecord | None:
        cleaned_job_id = job_id.strip()
        workflow = normalize_job_workflow(
            workflow_type=workflow_type,
            context="internal query",
            error_cls=JobPersistenceError,
        )
        if not cleaned_job_id:
            raise JobPersistenceError("job identity missing for internal query")
        with self._database.connect() as connection:
            row = fetch_job_row_by_identity(
                connection=connection,
                job_id=cleaned_job_id,
                workflow_type=workflow.workflow_type,
            )
        return resolve_job_record_from_row(
            row=row,
            to_job_record=_to_job_record,
        )

    def _require_job_by_identity(
        self,
        *,
        job_id: str,
        workflow_type: str,
        missing_error: str,
    ) -> JobRecord:
        job = self._get_job_by_identity(
            job_id=job_id,
            workflow_type=workflow_type,
        )
        if job is None:
            raise JobPersistenceError(missing_error)
        return job


def _build_job_id(workflow_type: str, task_hash: str) -> str:
    return f"{workflow_type}:{task_hash}"


def _to_job_record(row: Mapping[str, object]) -> JobRecord:
    job_id = str(row["job_id"]).strip()
    workflow_type = str(row["workflow_type"]).strip()
    state = str(row["state"]).strip()
    task_id = str(row["task_id"]).strip()
    task_hash = str(row["task_hash"]).strip()
    version = int(row["version"])
    chat_id = int(row["chat_id"])
    user_id = int(row["user_id"])

    if not job_id or not workflow_type or not state or not task_id or not task_hash:
        raise JobPersistenceError("job row identity corrupted after read")
    if chat_id <= 0:
        raise JobPersistenceError("job row chat identity corrupted after read")
    if user_id < 0:
        raise JobPersistenceError("job row user identity corrupted after read")
    if version <= 0:
        raise JobPersistenceError("job row version corrupted after read")

    return JobRecord(
        job_id=job_id,
        chat_id=chat_id,
        user_id=user_id,
        workflow_type=workflow_type,
        state=state,
        task_ref=str(row["task_ref"]),
        task_id=task_id,
        task_hash=task_hash,
        payload_json=str(row["payload_json"]),
        version=version,
        lease_owner=str(row["lease_owner"]),
        lease_until=str(row["lease_until"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _format_utc(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

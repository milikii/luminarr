from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.db.sqlite import SqliteDatabase

JOB_STATE_CANCELLED = "cancelled"
JOB_STATE_COMPLETED = "completed"
JOB_STATE_PENDING_APPROVAL = "pending_approval"
LEASE_SECONDS = 30
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
    version: int
    lease_owner: str
    lease_until: str
    created_at: str
    updated_at: str


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
    ) -> JobRecord | None:
        cleaned_task_id = task_id.strip()
        cleaned_task_hash = task_hash.strip()
        if not cleaned_task_id or not cleaned_task_hash:
            return None

        job_id = _build_import_job_id(cleaned_task_hash)
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO jobs (
                    job_id,
                    chat_id,
                    user_id,
                    workflow_type,
                    state,
                    task_ref,
                    task_id,
                    task_hash,
                    version,
                    lease_owner,
                    lease_until,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, '', '', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(job_id)
                DO UPDATE SET
                    chat_id = excluded.chat_id,
                    user_id = excluded.user_id,
                    workflow_type = excluded.workflow_type,
                    state = excluded.state,
                    task_ref = excluded.task_ref,
                    task_id = excluded.task_id,
                    task_hash = excluded.task_hash,
                    version = jobs.version + 1,
                    lease_owner = '',
                    lease_until = '',
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    job_id,
                    int(chat_id or 0),
                    int(user_id or 0),
                    WORKFLOW_IMPORT_TO_LIBRARY,
                    JOB_STATE_PENDING_APPROVAL,
                    task_ref.strip(),
                    cleaned_task_id,
                    cleaned_task_hash,
                ),
            )
            row = connection.execute(
                """
                SELECT
                    job_id,
                    chat_id,
                    user_id,
                    workflow_type,
                    state,
                    task_ref,
                    task_id,
                    task_hash,
                    version,
                    lease_owner,
                    lease_until,
                    created_at,
                    updated_at
                FROM jobs
                WHERE job_id = ?
                LIMIT 1
                """,
                (job_id,),
            ).fetchone()
            connection.commit()
        if row is None:
            return None
        return _to_job_record(row)

    def get_import_job_for_chat_ref(self, *, chat_id: int, task_ref: str) -> JobRecord | None:
        cleaned_task_ref = task_ref.strip()
        if chat_id <= 0 or not cleaned_task_ref:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    job_id,
                    chat_id,
                    user_id,
                    workflow_type,
                    state,
                    task_ref,
                    task_id,
                    task_hash,
                    version,
                    lease_owner,
                    lease_until,
                    created_at,
                    updated_at
                FROM jobs
                WHERE workflow_type = ?
                  AND chat_id = ?
                  AND (task_ref = ? OR task_id = ? OR task_hash = ?)
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (
                    WORKFLOW_IMPORT_TO_LIBRARY,
                    chat_id,
                    cleaned_task_ref,
                    cleaned_task_ref,
                    cleaned_task_ref,
                ),
            ).fetchone()
        if row is None:
            return None
        return _to_job_record(row)

    def get_latest_pending_import_job(self, *, chat_id: int) -> JobRecord | None:
        if chat_id <= 0:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    job_id,
                    chat_id,
                    user_id,
                    workflow_type,
                    state,
                    task_ref,
                    task_id,
                    task_hash,
                    version,
                    lease_owner,
                    lease_until,
                    created_at,
                    updated_at
                FROM jobs
                WHERE workflow_type = ? AND chat_id = ? AND state = ?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (WORKFLOW_IMPORT_TO_LIBRARY, chat_id, JOB_STATE_PENDING_APPROVAL),
            ).fetchone()
        if row is None:
            return None
        return _to_job_record(row)

    def claim_lease(self, *, job_id: str, expected_version: int, lease_owner: str) -> bool:
        cleaned_job_id = job_id.strip()
        cleaned_owner = lease_owner.strip()
        if not cleaned_job_id or not cleaned_owner or expected_version <= 0:
            return False

        current_time = _utcnow()
        lease_until = _format_utc(current_time + timedelta(seconds=LEASE_SECONDS))
        current_time_text = _format_utc(current_time)
        with self._database.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE jobs
                SET
                    lease_owner = ?,
                    lease_until = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE job_id = ?
                  AND version = ?
                  AND workflow_type = ?
                  AND state = ?
                  AND (lease_until = '' OR lease_until <= ?)
                """,
                (
                    cleaned_owner,
                    lease_until,
                    cleaned_job_id,
                    expected_version,
                    WORKFLOW_IMPORT_TO_LIBRARY,
                    JOB_STATE_PENDING_APPROVAL,
                    current_time_text,
                ),
            )
            connection.commit()
        return cursor.rowcount == 1

    def release_lease_to_pending(
        self,
        *,
        job_id: str,
        expected_version: int,
        lease_owner: str,
    ) -> bool:
        return self._set_job_state(
            job_id=job_id,
            expected_version=expected_version,
            lease_owner=lease_owner,
            next_state=JOB_STATE_PENDING_APPROVAL,
            bump_version=False,
        )

    def mark_completed(
        self,
        *,
        job_id: str,
        expected_version: int,
        lease_owner: str,
    ) -> bool:
        return self._set_job_state(
            job_id=job_id,
            expected_version=expected_version,
            lease_owner=lease_owner,
            next_state=JOB_STATE_COMPLETED,
            bump_version=True,
        )

    def cancel_pending_job(self, *, job_id: str, expected_version: int) -> bool:
        cleaned_job_id = job_id.strip()
        if not cleaned_job_id or expected_version <= 0:
            return False

        current_time_text = _format_utc(_utcnow())
        with self._database.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE jobs
                SET
                    state = ?,
                    version = version + 1,
                    lease_owner = '',
                    lease_until = '',
                    updated_at = CURRENT_TIMESTAMP
                WHERE job_id = ?
                  AND version = ?
                  AND workflow_type = ?
                  AND state = ?
                  AND (lease_until = '' OR lease_until <= ?)
                """,
                (
                    JOB_STATE_CANCELLED,
                    cleaned_job_id,
                    expected_version,
                    WORKFLOW_IMPORT_TO_LIBRARY,
                    JOB_STATE_PENDING_APPROVAL,
                    current_time_text,
                ),
            )
            connection.commit()
        return cursor.rowcount == 1

    def _set_job_state(
        self,
        *,
        job_id: str,
        expected_version: int,
        lease_owner: str,
        next_state: str,
        bump_version: bool,
    ) -> bool:
        cleaned_job_id = job_id.strip()
        cleaned_owner = lease_owner.strip()
        cleaned_state = next_state.strip()
        if not cleaned_job_id or not cleaned_owner or not cleaned_state or expected_version <= 0:
            return False

        version_sql = "version + 1" if bump_version else "version"
        with self._database.connect() as connection:
            cursor = connection.execute(
                f"""
                UPDATE jobs
                SET
                    state = ?,
                    version = {version_sql},
                    lease_owner = '',
                    lease_until = '',
                    updated_at = CURRENT_TIMESTAMP
                WHERE job_id = ?
                  AND version = ?
                  AND workflow_type = ?
                  AND lease_owner = ?
                """,
                (
                    cleaned_state,
                    cleaned_job_id,
                    expected_version,
                    WORKFLOW_IMPORT_TO_LIBRARY,
                    cleaned_owner,
                ),
            )
            connection.commit()
        return cursor.rowcount == 1


def _build_import_job_id(task_hash: str) -> str:
    return f"{WORKFLOW_IMPORT_TO_LIBRARY}:{task_hash}"


def _to_job_record(row: Mapping[str, object]) -> JobRecord:
    return JobRecord(
        job_id=str(row["job_id"]),
        chat_id=int(row["chat_id"]),
        user_id=int(row["user_id"]),
        workflow_type=str(row["workflow_type"]),
        state=str(row["state"]),
        task_ref=str(row["task_ref"]),
        task_id=str(row["task_id"]),
        task_hash=str(row["task_hash"]),
        version=int(row["version"]),
        lease_owner=str(row["lease_owner"]),
        lease_until=str(row["lease_until"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _format_utc(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

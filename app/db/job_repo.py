from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.db.job_repo_support import (
    normalize_job_chat_identity,
    normalize_job_lease_identity,
    normalize_job_pending_upsert_identity,
    normalize_job_task_ref,
    normalize_job_workflow,
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
        chat = normalize_job_chat_identity(chat_id=chat_id, context="query", error_cls=JobPersistenceError)
        task = normalize_job_task_ref(task_ref=task_ref, context="query", error_cls=JobPersistenceError)
        return self._select_one(
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
                payload_json,
                version,
                lease_owner,
                lease_until,
                created_at,
                updated_at
            FROM jobs
            WHERE chat_id = ?
              AND state = ?
              AND (task_ref = ? OR task_id = ? OR task_hash = ?)
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (
                chat.chat_id,
                JOB_STATE_PENDING_APPROVAL,
                task.task_ref,
                task.task_ref,
                task.task_ref,
            ),
        )

    def get_job_for_chat_ref(self, *, chat_id: int, task_ref: str) -> JobRecord | None:
        chat = normalize_job_chat_identity(chat_id=chat_id, context="query", error_cls=JobPersistenceError)
        task = normalize_job_task_ref(task_ref=task_ref, context="query", error_cls=JobPersistenceError)
        return self._select_one(
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
                payload_json,
                version,
                lease_owner,
                lease_until,
                created_at,
                updated_at
            FROM jobs
            WHERE chat_id = ?
              AND (task_ref = ? OR task_id = ? OR task_hash = ?)
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (
                chat.chat_id,
                task.task_ref,
                task.task_ref,
                task.task_ref,
            ),
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
        chat = normalize_job_chat_identity(
            chat_id=chat_id,
            context="pending query",
            error_cls=JobPersistenceError,
        )
        return self._select_one(
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
                payload_json,
                version,
                lease_owner,
                lease_until,
                created_at,
                updated_at
            FROM jobs
            WHERE chat_id = ? AND state = ?
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (chat.chat_id, JOB_STATE_PENDING_APPROVAL),
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
                    identity.lease_owner,
                    lease_until,
                    identity.job_id,
                    identity.expected_version,
                    identity.workflow_type,
                    JOB_STATE_PENDING_APPROVAL,
                    current_time_text,
                ),
            )
            connection.commit()
        if cursor.rowcount == 1:
            return True
        if self._get_job_by_identity(job_id=identity.job_id, workflow_type=identity.workflow_type) is None:
            raise JobPersistenceError("job missing during lease claim")
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
        cleaned_job_id = job_id.strip()
        cleaned_owner = lease_owner.strip()
        cleaned_task_id = task_id.strip()
        cleaned_task_hash = task_hash.strip()
        if not cleaned_job_id or not cleaned_owner or not cleaned_task_id or not cleaned_task_hash:
            raise JobPersistenceError("downloader completed job identity missing")
        if expected_version <= 0:
            raise JobPersistenceError("downloader completed job expected version missing")

        with self._database.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE jobs
                SET
                    state = ?,
                    task_id = ?,
                    task_hash = ?,
                    payload_json = ?,
                    version = version + 1,
                    lease_owner = '',
                    lease_until = '',
                    updated_at = CURRENT_TIMESTAMP
                WHERE job_id = ?
                  AND version = ?
                  AND workflow_type = ?
                  AND lease_owner = ?
                """,
                (
                    JOB_STATE_COMPLETED,
                    cleaned_task_id,
                    cleaned_task_hash,
                    payload_json.strip(),
                    cleaned_job_id,
                    expected_version,
                    WORKFLOW_ADD_TO_DOWNLOADER,
                    cleaned_owner,
                ),
            )
            connection.commit()
        return cursor.rowcount == 1

    def cancel_pending_job(self, *, job_id: str, expected_version: int, workflow_type: str) -> bool:
        cleaned_job_id = job_id.strip()
        cleaned_workflow = workflow_type.strip()
        if not cleaned_job_id or not cleaned_workflow:
            raise JobPersistenceError("job cancel identity missing")
        if expected_version <= 0:
            raise JobPersistenceError("job cancel expected version missing")

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
                    cleaned_workflow,
                    JOB_STATE_PENDING_APPROVAL,
                    current_time_text,
                ),
            )
            connection.commit()
        if cursor.rowcount == 1:
            return True
        if self._get_job_by_identity(job_id=cleaned_job_id, workflow_type=cleaned_workflow) is None:
            raise JobPersistenceError("job missing during cancel")
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
                    payload_json,
                    version,
                    lease_owner,
                    lease_until,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, '', '', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(job_id)
                DO UPDATE SET
                    chat_id = excluded.chat_id,
                    user_id = excluded.user_id,
                    workflow_type = excluded.workflow_type,
                    state = excluded.state,
                    task_ref = excluded.task_ref,
                    task_id = excluded.task_id,
                    task_hash = excluded.task_hash,
                    payload_json = excluded.payload_json,
                    version = jobs.version + 1,
                    lease_owner = '',
                    lease_until = '',
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    job_id,
                    identity.chat_id,
                    identity.user_id,
                    identity.workflow_type,
                    JOB_STATE_PENDING_APPROVAL,
                    identity.task_ref,
                    identity.task_id,
                    identity.task_hash,
                    payload_json.strip(),
                ),
            )
            connection.commit()
        job = self._select_one(
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
                payload_json,
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
        )
        if job is None:
            raise JobPersistenceError("job missing after pending upsert")
        return job

    def _get_job_for_chat_ref(
        self,
        *,
        workflow_type: str,
        chat_id: int,
        task_ref: str,
    ) -> JobRecord | None:
        chat = normalize_job_chat_identity(chat_id=chat_id, context="query", error_cls=JobPersistenceError)
        task = normalize_job_task_ref(task_ref=task_ref, context="query", error_cls=JobPersistenceError)
        workflow = normalize_job_workflow(
            workflow_type=workflow_type,
            context="query",
            error_cls=JobPersistenceError,
        )
        return self._select_one(
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
                payload_json,
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
                workflow.workflow_type,
                chat.chat_id,
                task.task_ref,
                task.task_ref,
                task.task_ref,
            ),
        )

    def _get_latest_pending_job_for_workflow(
        self,
        *,
        workflow_type: str,
        chat_id: int,
    ) -> JobRecord | None:
        chat = normalize_job_chat_identity(
            chat_id=chat_id,
            context="pending query",
            error_cls=JobPersistenceError,
        )
        workflow = normalize_job_workflow(
            workflow_type=workflow_type,
            context="pending query",
            error_cls=JobPersistenceError,
        )
        return self._select_one(
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
                payload_json,
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
            (workflow.workflow_type, chat.chat_id, JOB_STATE_PENDING_APPROVAL),
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
                    lease.job_id,
                    lease.expected_version,
                    lease.workflow_type,
                    lease.lease_owner,
                ),
            )
            connection.commit()
        if cursor.rowcount == 1:
            return True
        if self._get_job_by_identity(job_id=lease.job_id, workflow_type=lease.workflow_type) is None:
            raise JobPersistenceError("job missing during state transition")
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
        return self._select_one(
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
                payload_json,
                version,
                lease_owner,
                lease_until,
                created_at,
                updated_at
            FROM jobs
            WHERE job_id = ? AND workflow_type = ?
            LIMIT 1
            """,
            (cleaned_job_id, workflow.workflow_type),
        )

    def _select_one(self, query: str, params: tuple[object, ...]) -> JobRecord | None:
        with self._database.connect() as connection:
            row = connection.execute(query, params).fetchone()
        if row is None:
            return None
        return _to_job_record(row)


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

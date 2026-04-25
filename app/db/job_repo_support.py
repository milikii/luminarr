from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class JobTaskIdentity:
    task_ref: str


@dataclass(frozen=True, slots=True)
class JobChatIdentity:
    chat_id: int


@dataclass(frozen=True, slots=True)
class JobWorkflowIdentity:
    workflow_type: str


@dataclass(frozen=True, slots=True)
class JobTaskKey:
    task_id: str
    task_hash: str


@dataclass(frozen=True, slots=True)
class JobPendingUpsertIdentity:
    workflow_type: str
    chat_id: int
    user_id: int
    task_ref: str
    task_id: str
    task_hash: str


@dataclass(frozen=True, slots=True)
class JobLeaseIdentity:
    job_id: str
    workflow_type: str
    lease_owner: str
    expected_version: int


@dataclass(frozen=True, slots=True)
class DownloaderCompletedJobIdentity(JobLeaseIdentity):
    task_id: str
    task_hash: str


@dataclass(frozen=True, slots=True)
class JobPendingCancelIdentity:
    job_id: str
    workflow_type: str
    expected_version: int


@dataclass(frozen=True, slots=True)
class JobChatTaskQueryIdentity:
    chat_id: int
    task_ref: str


@dataclass(frozen=True, slots=True)
class JobPendingQueryIdentity:
    chat_id: int
    workflow_type: str


def normalize_job_chat_identity(*, chat_id: int, context: str, error_cls: type[Exception]) -> JobChatIdentity:
    if chat_id <= 0:
        raise error_cls(f"job chat identity missing for {context}")
    return JobChatIdentity(chat_id=chat_id)


def normalize_job_task_ref(*, task_ref: str, context: str, error_cls: type[Exception]) -> JobTaskIdentity:
    cleaned_task_ref = task_ref.strip()
    if not cleaned_task_ref:
        raise error_cls(f"job task ref missing for {context}")
    return JobTaskIdentity(task_ref=cleaned_task_ref)


def normalize_job_workflow(*, workflow_type: str, context: str, error_cls: type[Exception]) -> JobWorkflowIdentity:
    cleaned_workflow = workflow_type.strip()
    if not cleaned_workflow:
        raise error_cls(f"job workflow missing for {context}")
    return JobWorkflowIdentity(workflow_type=cleaned_workflow)


def normalize_job_task_key(*, task_id: str, task_hash: str, context: str, error_cls: type[Exception]) -> JobTaskKey:
    cleaned_task_id = task_id.strip()
    cleaned_task_hash = task_hash.strip()
    if not cleaned_task_id or not cleaned_task_hash:
        raise error_cls(f"job task identity missing for {context}")
    return JobTaskKey(task_id=cleaned_task_id, task_hash=cleaned_task_hash)


def normalize_job_pending_upsert_identity(
    *,
    workflow_type: str,
    chat_id: int | None,
    user_id: int | None,
    task_ref: str,
    task_id: str,
    task_hash: str,
    error_cls: type[Exception],
) -> JobPendingUpsertIdentity:
    workflow = normalize_job_workflow(
        workflow_type=workflow_type,
        context="pending upsert",
        error_cls=error_cls,
    )
    if chat_id is None or chat_id <= 0:
        raise error_cls("job chat identity missing for pending upsert")
    if user_id is not None and user_id <= 0:
        raise error_cls("job user identity invalid for pending upsert")
    task_key = normalize_job_task_key(
        task_id=task_id,
        task_hash=task_hash,
        context="pending upsert",
        error_cls=error_cls,
    )
    return JobPendingUpsertIdentity(
        workflow_type=workflow.workflow_type,
        chat_id=int(chat_id),
        user_id=int(user_id or 0),
        task_ref=task_ref.strip(),
        task_id=task_key.task_id,
        task_hash=task_key.task_hash,
    )


def fetch_job_row_by_chat_task_ref(
    *,
    connection: object,
    chat_id: int,
    task_ref: str,
    state: str | None = None,
    workflow_type: str = "",
) -> Mapping[str, object] | None:
    state_clause = "AND state = ?" if state else ""
    parameters: list[object] = []
    if workflow_type:
        parameters.append(workflow_type)
    parameters.append(chat_id)
    if state:
        parameters.append(state)
    parameters.extend([task_ref, task_ref, task_ref])
    return connection.execute(
        f"""
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
        WHERE {('workflow_type = ? AND ' if workflow_type else '')}chat_id = ?
          {state_clause}
          AND (task_ref = ? OR task_id = ? OR task_hash = ?)
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        tuple(parameters),
    ).fetchone()


def fetch_latest_pending_job_row(
    *,
    connection: object,
    chat_id: int,
    workflow_type: str = "",
    pending_state: str,
) -> Mapping[str, object] | None:
    workflow_clause = "workflow_type = ? AND " if workflow_type else ""
    parameters: list[object] = []
    if workflow_type:
        parameters.append(workflow_type)
    parameters.extend([chat_id, pending_state])
    return connection.execute(
        f"""
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
        WHERE {workflow_clause}chat_id = ? AND state = ?
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        tuple(parameters),
    ).fetchone()


def fetch_job_row_by_identity(
    *,
    connection: object,
    job_id: str,
    workflow_type: str,
) -> Mapping[str, object] | None:
    return connection.execute(
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
        (job_id, workflow_type),
    ).fetchone()


def resolve_job_record_from_row(
    *,
    row: Mapping[str, object] | None,
    to_job_record: callable,
) -> object | None:
    if row is None:
        return None
    return to_job_record(row)


def normalize_job_lease_identity(
    *,
    job_id: str,
    expected_version: int,
    lease_owner: str,
    workflow_type: str,
    context: str,
    error_cls: type[Exception],
) -> JobLeaseIdentity:
    cleaned_job_id = job_id.strip()
    cleaned_owner = lease_owner.strip()
    workflow = normalize_job_workflow(
        workflow_type=workflow_type,
        context=context,
        error_cls=error_cls,
    )
    if not cleaned_job_id or not cleaned_owner:
        raise error_cls(f"job {context} identity missing")
    if expected_version <= 0:
        raise error_cls(f"job {context} expected version missing")
    return JobLeaseIdentity(
        job_id=cleaned_job_id,
        workflow_type=workflow.workflow_type,
        lease_owner=cleaned_owner,
        expected_version=expected_version,
    )


def normalize_downloader_completed_job_identity(
    *,
    job_id: str,
    expected_version: int,
    lease_owner: str,
    task_id: str,
    task_hash: str,
    workflow_type: str,
    error_cls: type[Exception],
) -> DownloaderCompletedJobIdentity:
    lease = normalize_job_lease_identity(
        job_id=job_id,
        expected_version=expected_version,
        lease_owner=lease_owner,
        workflow_type=workflow_type,
        context="downloader completed",
        error_cls=error_cls,
    )
    task_key = normalize_job_task_key(
        task_id=task_id,
        task_hash=task_hash,
        context="downloader completed",
        error_cls=error_cls,
    )
    return DownloaderCompletedJobIdentity(
        job_id=lease.job_id,
        workflow_type=lease.workflow_type,
        lease_owner=lease.lease_owner,
        expected_version=lease.expected_version,
        task_id=task_key.task_id,
        task_hash=task_key.task_hash,
    )


def normalize_job_pending_cancel_identity(
    *,
    job_id: str,
    expected_version: int,
    workflow_type: str,
    error_cls: type[Exception],
) -> JobPendingCancelIdentity:
    cleaned_job_id = job_id.strip()
    workflow = normalize_job_workflow(
        workflow_type=workflow_type,
        context="cancel",
        error_cls=error_cls,
    )
    if not cleaned_job_id:
        raise error_cls("job cancel identity missing")
    if expected_version <= 0:
        raise error_cls("job cancel expected version missing")
    return JobPendingCancelIdentity(
        job_id=cleaned_job_id,
        workflow_type=workflow.workflow_type,
        expected_version=expected_version,
    )


def normalize_job_chat_task_query_identity(
    *,
    chat_id: int,
    task_ref: str,
    context: str,
    error_cls: type[Exception],
) -> JobChatTaskQueryIdentity:
    chat = normalize_job_chat_identity(
        chat_id=chat_id,
        context=context,
        error_cls=error_cls,
    )
    task = normalize_job_task_ref(
        task_ref=task_ref,
        context=context,
        error_cls=error_cls,
    )
    return JobChatTaskQueryIdentity(chat_id=chat.chat_id, task_ref=task.task_ref)


def normalize_job_pending_query_identity(
    *,
    chat_id: int,
    workflow_type: str,
    context: str,
    error_cls: type[Exception],
) -> JobPendingQueryIdentity:
    chat = normalize_job_chat_identity(
        chat_id=chat_id,
        context=context,
        error_cls=error_cls,
    )
    workflow = normalize_job_workflow(
        workflow_type=workflow_type,
        context=context,
        error_cls=error_cls,
    )
    return JobPendingQueryIdentity(
        chat_id=chat.chat_id,
        workflow_type=workflow.workflow_type,
    )


def update_job_lease_claim(
    *,
    connection: object,
    job_id: str,
    expected_version: int,
    lease_owner: str,
    workflow_type: str,
    pending_state: str,
    current_time_text: str,
    lease_until: str,
) -> int:
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
            lease_owner,
            lease_until,
            job_id,
            expected_version,
            workflow_type,
            pending_state,
            current_time_text,
        ),
    )
    return cursor.rowcount


def update_job_state_transition(
    *,
    connection: object,
    job_id: str,
    expected_version: int,
    workflow_type: str,
    lease_owner: str,
    next_state: str,
    bump_version: bool,
) -> int:
    version_sql = "version + 1" if bump_version else "version"
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
            next_state,
            job_id,
            expected_version,
            workflow_type,
            lease_owner,
        ),
    )
    return cursor.rowcount


def update_downloader_job_completed(
    *,
    connection: object,
    job_id: str,
    expected_version: int,
    lease_owner: str,
    task_id: str,
    task_hash: str,
    payload_json: str,
    completed_state: str,
    workflow_type: str,
) -> int:
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
            completed_state,
            task_id,
            task_hash,
            payload_json.strip(),
            job_id,
            expected_version,
            workflow_type,
            lease_owner,
        ),
    )
    return cursor.rowcount


def update_job_cancel_pending(
    *,
    connection: object,
    job_id: str,
    expected_version: int,
    workflow_type: str,
    cancelled_state: str,
    pending_state: str,
    current_time_text: str,
) -> int:
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
            cancelled_state,
            job_id,
            expected_version,
            workflow_type,
            pending_state,
            current_time_text,
        ),
    )
    return cursor.rowcount


def upsert_pending_job_row(
    *,
    connection: object,
    job_id: str,
    chat_id: int,
    user_id: int,
    workflow_type: str,
    pending_state: str,
    task_ref: str,
    task_id: str,
    task_hash: str,
    payload_json: str,
) -> None:
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
            chat_id,
            user_id,
            workflow_type,
            pending_state,
            task_ref,
            task_id,
            task_hash,
            payload_json.strip(),
        ),
    )

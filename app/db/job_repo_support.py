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

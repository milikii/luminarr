from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping


@dataclass(frozen=True, slots=True)
class ApprovalIdentity:
    task_id: str
    task_hash: str


@dataclass(frozen=True, slots=True)
class ApprovalTransitionIdentity(ApprovalIdentity):
    expected_lease_version: int


@dataclass(frozen=True, slots=True)
class ApprovalMoveIdentity:
    current_task_id: str
    current_task_hash: str
    new_task_id: str
    new_task_hash: str


@dataclass(frozen=True, slots=True)
class ApprovalExecutedIdentity(ApprovalIdentity):
    executed_lease_version: int


def normalize_approval_identity(
    *,
    task_id: str,
    task_hash: str,
    context: str,
    error_cls: type[Exception],
) -> ApprovalIdentity:
    cleaned_task_id = task_id.strip()
    cleaned_task_hash = task_hash.strip()
    if not cleaned_task_id or not cleaned_task_hash:
        raise error_cls(f"approval task identity missing for {context}")
    return ApprovalIdentity(task_id=cleaned_task_id, task_hash=cleaned_task_hash)


def normalize_transition_identity(
    *,
    task_id: str,
    task_hash: str,
    expected_lease_version: int,
    context: str,
    error_cls: type[Exception],
) -> ApprovalTransitionIdentity:
    identity = normalize_approval_identity(
        task_id=task_id,
        task_hash=task_hash,
        context=context,
        error_cls=error_cls,
    )
    if expected_lease_version <= 0:
        raise error_cls(f"approval expected lease version missing for {context}")
    return ApprovalTransitionIdentity(
        task_id=identity.task_id,
        task_hash=identity.task_hash,
        expected_lease_version=expected_lease_version,
    )


def normalize_executed_identity(
    *,
    task_id: str,
    task_hash: str,
    executed_lease_version: int,
    error_cls: type[Exception],
) -> ApprovalExecutedIdentity:
    identity = normalize_approval_identity(
        task_id=task_id,
        task_hash=task_hash,
        context="executed version update",
        error_cls=error_cls,
    )
    if executed_lease_version <= 0:
        raise error_cls("approval executed lease version missing")
    return ApprovalExecutedIdentity(
        task_id=identity.task_id,
        task_hash=identity.task_hash,
        executed_lease_version=executed_lease_version,
    )


def fetch_exact_approval_row(
    *,
    connection: object,
    action_type: str,
    task_id: str,
    task_hash: str,
) -> Mapping[str, object] | None:
    return connection.execute(
        """
        SELECT
            action_type,
            task_id,
            task_hash,
            status,
            lease_version,
            executed_version,
            expires_at,
            last_task_ref,
            created_at,
            updated_at
        FROM approval_record
        WHERE action_type = ? AND task_id = ? AND task_hash = ?
        LIMIT 1
        """,
        (action_type, task_id, task_hash),
    ).fetchone()


def fetch_latest_approval_row_for_task_id(
    *,
    connection: object,
    action_type: str,
    task_id: str,
) -> Mapping[str, object] | None:
    return connection.execute(
        """
        SELECT
            action_type,
            task_id,
            task_hash,
            status,
            lease_version,
            executed_version,
            expires_at,
            last_task_ref,
            created_at,
            updated_at
        FROM approval_record
        WHERE action_type = ? AND task_id = ?
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (action_type, task_id),
    ).fetchone()


def fetch_approval_lease_version_row(
    *,
    connection: object,
    action_type: str,
    task_id: str,
    task_hash: str,
) -> Mapping[str, object] | None:
    return connection.execute(
        """
        SELECT lease_version
        FROM approval_record
        WHERE action_type = ? AND task_id = ? AND task_hash = ?
        LIMIT 1
        """,
        (action_type, task_id, task_hash),
    ).fetchone()


def upsert_approval_row(
    *,
    connection: object,
    action_type: str,
    task_id: str,
    task_hash: str,
    status: str,
    lease_version: int,
    executed_version: int,
    task_ref: str,
) -> None:
    connection.execute(
        """
        INSERT INTO approval_record (
            action_type,
            task_id,
            task_hash,
            status,
            lease_version,
            executed_version,
            last_task_ref,
            created_at,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(action_type, task_id, task_hash)
        DO UPDATE SET
            status = excluded.status,
            lease_version = CASE
                WHEN approval_record.lease_version > 0 THEN approval_record.lease_version
                ELSE excluded.lease_version
            END,
            executed_version = CASE
                WHEN approval_record.executed_version > 0 THEN approval_record.executed_version
                ELSE excluded.executed_version
            END,
            last_task_ref = excluded.last_task_ref,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            action_type,
            task_id,
            task_hash,
            status,
            lease_version,
            executed_version,
            task_ref.strip(),
        ),
    )


def request_approval_row(
    *,
    connection: object,
    action_type: str,
    task_id: str,
    task_hash: str,
    pending_status: str,
    expires_at: str,
    task_ref: str,
) -> None:
    connection.execute(
        """
        INSERT INTO approval_record (
            action_type,
            task_id,
            task_hash,
            status,
            lease_version,
            executed_version,
            expires_at,
            last_task_ref,
            created_at,
            updated_at
        ) VALUES (?, ?, ?, ?, 1, 0, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(action_type, task_id, task_hash)
        DO UPDATE SET
            status = excluded.status,
            lease_version = approval_record.lease_version + 1,
            expires_at = excluded.expires_at,
            last_task_ref = excluded.last_task_ref,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            action_type,
            task_id,
            task_hash,
            pending_status,
            expires_at,
            task_ref.strip(),
        ),
    )


def update_approval_status(
    *,
    connection: object,
    action_type: str,
    task_id: str,
    task_hash: str,
    task_ref: str,
    next_status: str,
    expected_lease_version: int,
    require_pending_status: bool,
) -> int:
    where_status_clause = "AND status = ?" if require_pending_status else ""
    parameters: list[object] = [
        next_status,
        task_ref.strip(),
        action_type,
        task_id,
        task_hash,
    ]
    if require_pending_status:
        parameters.append("pending")
    parameters.extend([expected_lease_version, expected_lease_version])
    cursor = connection.execute(
        f"""
        UPDATE approval_record
        SET
            status = ?,
            last_task_ref = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE action_type = ?
          AND task_id = ?
          AND task_hash = ?
          {where_status_clause}
          AND lease_version = ?
          AND executed_version < ?
        """,
        tuple(parameters),
    )
    return cursor.rowcount


def normalize_move_identity(
    *,
    current_task_id: str,
    current_task_hash: str,
    new_task_id: str,
    new_task_hash: str,
    error_cls: type[Exception],
) -> ApprovalMoveIdentity:
    current_identity = normalize_approval_identity(
        task_id=current_task_id,
        task_hash=current_task_hash,
        context="identity move",
        error_cls=error_cls,
    )
    new_identity = normalize_approval_identity(
        task_id=new_task_id,
        task_hash=new_task_hash,
        context="identity move",
        error_cls=error_cls,
    )
    return ApprovalMoveIdentity(
        current_task_id=current_identity.task_id,
        current_task_hash=current_identity.task_hash,
        new_task_id=new_identity.task_id,
        new_task_hash=new_identity.task_hash,
    )


def update_approval_executed_version(
    *,
    connection: object,
    action_type: str,
    task_id: str,
    task_hash: str,
    executed_lease_version: int,
) -> int:
    cursor = connection.execute(
        """
        UPDATE approval_record
        SET
            executed_version = CASE
                WHEN executed_version < ? THEN ?
                ELSE executed_version
            END,
            updated_at = CURRENT_TIMESTAMP
        WHERE action_type = ? AND task_id = ? AND task_hash = ?
        """,
        (
            executed_lease_version,
            executed_lease_version,
            action_type,
            task_id,
            task_hash,
        ),
    )
    return cursor.rowcount


def move_approval_identity_row(
    *,
    connection: object,
    action_type: str,
    current_task_id: str,
    current_task_hash: str,
    new_task_id: str,
    new_task_hash: str,
) -> int:
    cursor = connection.execute(
        """
        UPDATE approval_record
        SET
            task_id = ?,
            task_hash = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE action_type = ? AND task_id = ? AND task_hash = ?
        """,
        (
            new_task_id,
            new_task_hash,
            action_type,
            current_task_id,
            current_task_hash,
        ),
    )
    return cursor.rowcount


def resolve_approval_record_from_row(
    *,
    row: Mapping[str, object] | None,
    to_approval_record: callable,
) -> object | None:
    if row is None:
        return None
    return to_approval_record(row)


def resolve_requested_lease_version_from_row(
    *,
    row: Mapping[str, object] | None,
    error_cls: type[Exception],
) -> int | None:
    if row is None:
        return None
    lease_version = int(row["lease_version"])
    if lease_version <= 0:
        raise error_cls("approval lease version corrupted after read")
    return lease_version

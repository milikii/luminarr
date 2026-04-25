from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.db.approval_repo_support import (
    fetch_approval_lease_version_row,
    fetch_exact_approval_row,
    fetch_latest_approval_row_for_task_id,
    move_approval_identity_row,
    normalize_approval_identity,
    normalize_move_identity,
    normalize_transition_identity,
    update_approval_executed_version,
    update_approval_status,
)
from app.db.sqlite import SqliteDatabase

ACTION_ADD_TO_DOWNLOADER = "add_to_downloader"
ACTION_IMPORT_TO_LIBRARY = "import_to_library"
APPROVAL_STATUS_CANCELLED = "cancelled"
APPROVAL_STATUS_PENDING = "pending"
APPROVAL_STATUS_APPROVED = "approved"
VALID_APPROVAL_STATUSES = frozenset(
    {
        APPROVAL_STATUS_CANCELLED,
        APPROVAL_STATUS_PENDING,
        APPROVAL_STATUS_APPROVED,
    }
)
DEFAULT_PENDING_TIMEOUT_SECONDS = 15 * 60


@dataclass(frozen=True, slots=True)
class ApprovalRecord:
    action_type: str
    task_id: str
    task_hash: str
    status: str
    lease_version: int
    executed_version: int
    expires_at: str
    last_task_ref: str
    created_at: str
    updated_at: str


class ApprovalPersistenceError(RuntimeError):
    pass


class ApprovalRepo:
    def __init__(self, database: SqliteDatabase) -> None:
        self._database = database

    def upsert_import_approval(
        self,
        *,
        task_id: str,
        task_hash: str,
        task_ref: str,
        status: str = APPROVAL_STATUS_APPROVED,
    ) -> None:
        self._upsert_approval(
            action_type=ACTION_IMPORT_TO_LIBRARY,
            task_id=task_id,
            task_hash=task_hash,
            task_ref=task_ref,
            status=status,
        )

    def request_import_approval(
        self,
        *,
        task_id: str,
        task_hash: str,
        task_ref: str,
        timeout_seconds: int = DEFAULT_PENDING_TIMEOUT_SECONDS,
    ) -> int:
        return self._request_approval(
            action_type=ACTION_IMPORT_TO_LIBRARY,
            task_id=task_id,
            task_hash=task_hash,
            task_ref=task_ref,
            timeout_seconds=timeout_seconds,
        )

    def approve_import(
        self,
        *,
        task_id: str,
        task_hash: str,
        task_ref: str,
        expected_lease_version: int,
    ) -> bool:
        return self._approve(
            action_type=ACTION_IMPORT_TO_LIBRARY,
            task_id=task_id,
            task_hash=task_hash,
            task_ref=task_ref,
            expected_lease_version=expected_lease_version,
        )

    def restore_import_pending(
        self,
        *,
        task_id: str,
        task_hash: str,
        task_ref: str,
        expected_lease_version: int,
    ) -> bool:
        return self._restore_pending(
            action_type=ACTION_IMPORT_TO_LIBRARY,
            task_id=task_id,
            task_hash=task_hash,
            task_ref=task_ref,
            expected_lease_version=expected_lease_version,
        )

    def cancel_import(
        self,
        *,
        task_id: str,
        task_hash: str,
        task_ref: str,
        expected_lease_version: int,
    ) -> bool:
        return self._cancel(
            action_type=ACTION_IMPORT_TO_LIBRARY,
            task_id=task_id,
            task_hash=task_hash,
            task_ref=task_ref,
            expected_lease_version=expected_lease_version,
        )

    def mark_import_executed(self, *, task_id: str, task_hash: str, executed_lease_version: int) -> None:
        self._mark_executed(
            action_type=ACTION_IMPORT_TO_LIBRARY,
            task_id=task_id,
            task_hash=task_hash,
            executed_lease_version=executed_lease_version,
        )

    def get_import_approval(self, *, task_id: str, task_hash: str) -> ApprovalRecord | None:
        return self._get_approval(
            action_type=ACTION_IMPORT_TO_LIBRARY,
            task_id=task_id,
            task_hash=task_hash,
        )

    def is_import_pending_expired(
        self,
        *,
        task_id: str,
        task_hash: str,
        expected_lease_version: int,
    ) -> bool:
        return self._is_pending_expired(
            action_type=ACTION_IMPORT_TO_LIBRARY,
            task_id=task_id,
            task_hash=task_hash,
            expected_lease_version=expected_lease_version,
        )

    def request_downloader_approval(
        self,
        *,
        task_id: str,
        task_hash: str,
        task_ref: str,
        timeout_seconds: int = DEFAULT_PENDING_TIMEOUT_SECONDS,
    ) -> int:
        return self._request_approval(
            action_type=ACTION_ADD_TO_DOWNLOADER,
            task_id=task_id,
            task_hash=task_hash,
            task_ref=task_ref,
            timeout_seconds=timeout_seconds,
        )

    def approve_downloader(
        self,
        *,
        task_id: str,
        task_hash: str,
        task_ref: str,
        expected_lease_version: int,
    ) -> bool:
        return self._approve(
            action_type=ACTION_ADD_TO_DOWNLOADER,
            task_id=task_id,
            task_hash=task_hash,
            task_ref=task_ref,
            expected_lease_version=expected_lease_version,
        )

    def restore_downloader_pending(
        self,
        *,
        task_id: str,
        task_hash: str,
        task_ref: str,
        expected_lease_version: int,
    ) -> bool:
        return self._restore_pending(
            action_type=ACTION_ADD_TO_DOWNLOADER,
            task_id=task_id,
            task_hash=task_hash,
            task_ref=task_ref,
            expected_lease_version=expected_lease_version,
        )

    def cancel_downloader(
        self,
        *,
        task_id: str,
        task_hash: str,
        task_ref: str,
        expected_lease_version: int,
    ) -> bool:
        return self._cancel(
            action_type=ACTION_ADD_TO_DOWNLOADER,
            task_id=task_id,
            task_hash=task_hash,
            task_ref=task_ref,
            expected_lease_version=expected_lease_version,
        )

    def mark_downloader_executed(
        self,
        *,
        task_id: str,
        task_hash: str,
        executed_lease_version: int,
    ) -> None:
        self._mark_executed(
            action_type=ACTION_ADD_TO_DOWNLOADER,
            task_id=task_id,
            task_hash=task_hash,
            executed_lease_version=executed_lease_version,
        )

    def move_downloader_approval_identity(
        self,
        *,
        current_task_id: str,
        current_task_hash: str,
        new_task_id: str,
        new_task_hash: str,
    ) -> None:
        self._move_approval_identity(
            action_type=ACTION_ADD_TO_DOWNLOADER,
            current_task_id=current_task_id,
            current_task_hash=current_task_hash,
            new_task_id=new_task_id,
            new_task_hash=new_task_hash,
        )

    def get_downloader_approval(self, *, task_id: str, task_hash: str) -> ApprovalRecord | None:
        return self._get_approval(
            action_type=ACTION_ADD_TO_DOWNLOADER,
            task_id=task_id,
            task_hash=task_hash,
        )

    def is_downloader_pending_expired(
        self,
        *,
        task_id: str,
        task_hash: str,
        expected_lease_version: int,
    ) -> bool:
        return self._is_pending_expired(
            action_type=ACTION_ADD_TO_DOWNLOADER,
            task_id=task_id,
            task_hash=task_hash,
            expected_lease_version=expected_lease_version,
        )

    def _upsert_approval(
        self,
        *,
        action_type: str,
        task_id: str,
        task_hash: str,
        task_ref: str,
        status: str,
    ) -> None:
        identity = normalize_approval_identity(
            task_id=task_id,
            task_hash=task_hash,
            context="upsert",
            error_cls=ApprovalPersistenceError,
        )
        cleaned_status = _normalize_approval_status(status, context="upsert")

        initial_lease_version = 1 if cleaned_status == APPROVAL_STATUS_APPROVED else 0
        initial_executed_version = 1 if cleaned_status == APPROVAL_STATUS_APPROVED else 0
        with self._database.connect() as connection:
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
                    identity.task_id,
                    identity.task_hash,
                    cleaned_status,
                    initial_lease_version,
                    initial_executed_version,
                    task_ref.strip(),
                ),
            )
            connection.commit()
        approval_record = self._get_exact_approval_record(
            action_type=action_type,
            task_id=identity.task_id,
            task_hash=identity.task_hash,
        )
        if approval_record is None:
            raise ApprovalPersistenceError("approval_record missing after upsert")

    def _request_approval(
        self,
        *,
        action_type: str,
        task_id: str,
        task_hash: str,
        task_ref: str,
        timeout_seconds: int,
    ) -> int:
        identity = normalize_approval_identity(
            task_id=task_id,
            task_hash=task_hash,
            context="pending request",
            error_cls=ApprovalPersistenceError,
        )
        expires_at = _format_utc(_utcnow() + timedelta(seconds=max(0, timeout_seconds)))

        with self._database.connect() as connection:
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
                    identity.task_id,
                    identity.task_hash,
                    APPROVAL_STATUS_PENDING,
                    expires_at,
                    task_ref.strip(),
                ),
            )
            connection.commit()
        lease_version = self._get_requested_lease_version(
            action_type=action_type,
            task_id=identity.task_id,
            task_hash=identity.task_hash,
        )
        if lease_version is None:
            raise ApprovalPersistenceError("approval_record missing after pending request")
        return lease_version

    def _approve(
        self,
        *,
        action_type: str,
        task_id: str,
        task_hash: str,
        task_ref: str,
        expected_lease_version: int,
    ) -> bool:
        identity = normalize_transition_identity(
            task_id=task_id,
            task_hash=task_hash,
            expected_lease_version=expected_lease_version,
            context="state transition",
            error_cls=ApprovalPersistenceError,
        )

        with self._database.connect() as connection:
            rowcount = update_approval_status(
                connection=connection,
                action_type=action_type,
                task_id=identity.task_id,
                task_hash=identity.task_hash,
                task_ref=task_ref,
                next_status=APPROVAL_STATUS_APPROVED,
                expected_lease_version=identity.expected_lease_version,
                require_pending_status=True,
            )
            connection.commit()
        if rowcount == 1:
            return True
        approval_record = self._get_exact_approval_record(
            action_type=action_type,
            task_id=identity.task_id,
            task_hash=identity.task_hash,
        )
        if approval_record is None:
            raise ApprovalPersistenceError("approval_record missing during approve")
        return False

    def _restore_pending(
        self,
        *,
        action_type: str,
        task_id: str,
        task_hash: str,
        task_ref: str,
        expected_lease_version: int,
    ) -> bool:
        identity = normalize_transition_identity(
            task_id=task_id,
            task_hash=task_hash,
            expected_lease_version=expected_lease_version,
            context="state transition",
            error_cls=ApprovalPersistenceError,
        )

        with self._database.connect() as connection:
            rowcount = update_approval_status(
                connection=connection,
                action_type=action_type,
                task_id=identity.task_id,
                task_hash=identity.task_hash,
                task_ref=task_ref,
                next_status=APPROVAL_STATUS_PENDING,
                expected_lease_version=identity.expected_lease_version,
                require_pending_status=False,
            )
            connection.commit()
        if rowcount == 1:
            return True
        approval_record = self._get_exact_approval_record(
            action_type=action_type,
            task_id=identity.task_id,
            task_hash=identity.task_hash,
        )
        if approval_record is None:
            raise ApprovalPersistenceError("approval_record missing during restore")
        return False

    def _cancel(
        self,
        *,
        action_type: str,
        task_id: str,
        task_hash: str,
        task_ref: str,
        expected_lease_version: int,
    ) -> bool:
        identity = normalize_transition_identity(
            task_id=task_id,
            task_hash=task_hash,
            expected_lease_version=expected_lease_version,
            context="state transition",
            error_cls=ApprovalPersistenceError,
        )

        with self._database.connect() as connection:
            rowcount = update_approval_status(
                connection=connection,
                action_type=action_type,
                task_id=identity.task_id,
                task_hash=identity.task_hash,
                task_ref=task_ref,
                next_status=APPROVAL_STATUS_CANCELLED,
                expected_lease_version=identity.expected_lease_version,
                require_pending_status=True,
            )
            connection.commit()
        if rowcount == 1:
            return True
        approval_record = self._get_exact_approval_record(
            action_type=action_type,
            task_id=identity.task_id,
            task_hash=identity.task_hash,
        )
        if approval_record is None:
            raise ApprovalPersistenceError("approval_record missing during cancel")
        return False

    def _mark_executed(
        self,
        *,
        action_type: str,
        task_id: str,
        task_hash: str,
        executed_lease_version: int,
    ) -> None:
        identity = normalize_approval_identity(
            task_id=task_id,
            task_hash=task_hash,
            context="executed version update",
            error_cls=ApprovalPersistenceError,
        )
        if executed_lease_version <= 0:
            raise ApprovalPersistenceError("approval executed lease version missing")

        with self._database.connect() as connection:
            rowcount = update_approval_executed_version(
                connection=connection,
                action_type=action_type,
                task_id=identity.task_id,
                task_hash=identity.task_hash,
                executed_lease_version=executed_lease_version,
            )
            connection.commit()
        if rowcount != 1:
            raise ApprovalPersistenceError("approval_record missing during executed version update")

    def _move_approval_identity(
        self,
        *,
        action_type: str,
        current_task_id: str,
        current_task_hash: str,
        new_task_id: str,
        new_task_hash: str,
    ) -> None:
        identity = normalize_move_identity(
            current_task_id=current_task_id,
            current_task_hash=current_task_hash,
            new_task_id=new_task_id,
            new_task_hash=new_task_hash,
            error_cls=ApprovalPersistenceError,
        )
        if (
            identity.current_task_id == identity.new_task_id
            and identity.current_task_hash == identity.new_task_hash
        ):
            approval_record = self._get_exact_approval_record(
                action_type=action_type,
                task_id=identity.current_task_id,
                task_hash=identity.current_task_hash,
            )
            if approval_record is None:
                raise ApprovalPersistenceError("approval_record missing during identity move")
            return

        with self._database.connect() as connection:
            rowcount = move_approval_identity_row(
                connection=connection,
                action_type=action_type,
                current_task_id=identity.current_task_id,
                current_task_hash=identity.current_task_hash,
                new_task_id=identity.new_task_id,
                new_task_hash=identity.new_task_hash,
            )
            connection.commit()
        if rowcount == 1:
            return

        target_record = self._get_exact_approval_record(
            action_type=action_type,
            task_id=identity.new_task_id,
            task_hash=identity.new_task_hash,
        )
        if target_record is not None:
            return
        raise ApprovalPersistenceError("approval_record missing during identity move")

    def _get_approval(
        self,
        *,
        action_type: str,
        task_id: str,
        task_hash: str,
    ) -> ApprovalRecord | None:
        identity = normalize_approval_identity(
            task_id=task_id,
            task_hash=task_hash,
            context="query",
            error_cls=ApprovalPersistenceError,
        )
        with self._database.connect() as connection:
            row = fetch_exact_approval_row(
                connection=connection,
                action_type=action_type,
                task_id=identity.task_id,
                task_hash=identity.task_hash,
            )
            if row is None:
                fallback_row = fetch_latest_approval_row_for_task_id(
                    connection=connection,
                    action_type=action_type,
                    task_id=identity.task_id,
                )
                if fallback_row is not None:
                    raise ApprovalPersistenceError("approval task hash mismatch for query")
        if row is None:
            return None
        return _to_approval_record(row)

    def _get_exact_approval_record(
        self,
        *,
        action_type: str,
        task_id: str,
        task_hash: str,
    ) -> ApprovalRecord | None:
        identity = normalize_approval_identity(
            task_id=task_id,
            task_hash=task_hash,
            context="exact query",
            error_cls=ApprovalPersistenceError,
        )
        with self._database.connect() as connection:
            row = fetch_exact_approval_row(
                connection=connection,
                action_type=action_type,
                task_id=identity.task_id,
                task_hash=identity.task_hash,
            )
        if row is None:
            return None
        return _to_approval_record(row)

    def _is_pending_expired(
        self,
        *,
        action_type: str,
        task_id: str,
        task_hash: str,
        expected_lease_version: int,
    ) -> bool:
        identity = normalize_transition_identity(
            task_id=task_id,
            task_hash=task_hash,
            expected_lease_version=expected_lease_version,
            context="pending expiry check",
            error_cls=ApprovalPersistenceError,
        )
        approval_record = self._get_exact_approval_record(
            action_type=action_type,
            task_id=identity.task_id,
            task_hash=identity.task_hash,
        )
        if approval_record is None:
            raise ApprovalPersistenceError("approval_record missing during pending expiry check")
        if approval_record.status != APPROVAL_STATUS_PENDING:
            return False
        if approval_record.lease_version != identity.expected_lease_version:
            return False
        expires_at = _parse_pending_expires_at(approval_record.expires_at)
        return expires_at <= _utcnow()

    def _get_requested_lease_version(
        self,
        *,
        action_type: str,
        task_id: str,
        task_hash: str,
    ) -> int | None:
        identity = normalize_approval_identity(
            task_id=task_id,
            task_hash=task_hash,
            context="requested lease query",
            error_cls=ApprovalPersistenceError,
        )
        with self._database.connect() as connection:
            row = fetch_approval_lease_version_row(
                connection=connection,
                action_type=action_type,
                task_id=identity.task_id,
                task_hash=identity.task_hash,
            )
        if row is None:
            return None
        lease_version = int(row["lease_version"])
        if lease_version <= 0:
            raise ApprovalPersistenceError("approval lease version corrupted after read")
        return lease_version


def _to_approval_record(row: Mapping[str, object]) -> ApprovalRecord:
    action_type = str(row["action_type"]).strip()
    task_id = str(row["task_id"]).strip()
    task_hash = str(row["task_hash"]).strip()
    status = _normalize_approval_status(row["status"], context="read")
    lease_version = int(row["lease_version"])
    executed_version = int(row["executed_version"])

    if not action_type or not task_id or not task_hash:
        raise ApprovalPersistenceError("approval row identity corrupted after read")
    if lease_version <= 0:
        raise ApprovalPersistenceError("approval row lease version corrupted after read")
    if executed_version < 0:
        raise ApprovalPersistenceError("approval row executed version corrupted after read")

    return ApprovalRecord(
        action_type=action_type,
        task_id=task_id,
        task_hash=task_hash,
        status=status,
        lease_version=lease_version,
        executed_version=executed_version,
        expires_at=str(row["expires_at"]),
        last_task_ref=str(row["last_task_ref"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _format_utc(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _normalize_approval_status(raw_status: object, *, context: str) -> str:
    status = str(raw_status).strip()
    if not status:
        if context == "upsert":
            raise ApprovalPersistenceError("approval status missing for upsert")
        raise ApprovalPersistenceError("approval row identity corrupted after read")
    if status not in VALID_APPROVAL_STATUSES:
        if context == "upsert":
            raise ApprovalPersistenceError("approval status invalid for upsert")
        raise ApprovalPersistenceError("approval row status corrupted after read")
    return status


def _parse_pending_expires_at(raw_expires_at: object) -> datetime:
    expires_at = str(raw_expires_at).strip()
    if not expires_at:
        raise ApprovalPersistenceError("approval expires_at missing for pending expiry check")
    try:
        parsed = datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S")
    except ValueError as error:
        raise ApprovalPersistenceError("approval expires_at invalid for pending expiry check") from error
    return parsed.replace(tzinfo=UTC)

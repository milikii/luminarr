from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.db.sqlite import SqliteDatabase

ACTION_ADD_TO_DOWNLOADER = "add_to_downloader"
ACTION_IMPORT_TO_LIBRARY = "import_to_library"
APPROVAL_STATUS_CANCELLED = "cancelled"
APPROVAL_STATUS_PENDING = "pending"
APPROVAL_STATUS_APPROVED = "approved"
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
        cleaned_task_id = task_id.strip()
        cleaned_task_hash = task_hash.strip()
        if not cleaned_task_id or not cleaned_task_hash:
            return
        cleaned_status = status.strip()
        if not cleaned_status:
            return

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
                    cleaned_task_id,
                    cleaned_task_hash,
                    cleaned_status,
                    initial_lease_version,
                    initial_executed_version,
                    task_ref.strip(),
                ),
            )
            connection.commit()

    def _request_approval(
        self,
        *,
        action_type: str,
        task_id: str,
        task_hash: str,
        task_ref: str,
        timeout_seconds: int,
    ) -> int:
        cleaned_task_id = task_id.strip()
        cleaned_task_hash = task_hash.strip()
        if not cleaned_task_id or not cleaned_task_hash:
            return 0
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
                    cleaned_task_id,
                    cleaned_task_hash,
                    APPROVAL_STATUS_PENDING,
                    expires_at,
                    task_ref.strip(),
                ),
            )
            connection.commit()
        lease_version = self._get_requested_lease_version(
            action_type=action_type,
            task_id=cleaned_task_id,
            task_hash=cleaned_task_hash,
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
        cleaned_task_id = task_id.strip()
        cleaned_task_hash = task_hash.strip()
        if not cleaned_task_id or not cleaned_task_hash or expected_lease_version <= 0:
            return False

        with self._database.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE approval_record
                SET
                    status = ?,
                    last_task_ref = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE action_type = ?
                  AND task_id = ?
                  AND task_hash = ?
                  AND status = ?
                  AND lease_version = ?
                  AND executed_version < ?
                """,
                (
                    APPROVAL_STATUS_APPROVED,
                    task_ref.strip(),
                    action_type,
                    cleaned_task_id,
                    cleaned_task_hash,
                    APPROVAL_STATUS_PENDING,
                    expected_lease_version,
                    expected_lease_version,
                ),
            )
            connection.commit()
        return cursor.rowcount == 1

    def _restore_pending(
        self,
        *,
        action_type: str,
        task_id: str,
        task_hash: str,
        task_ref: str,
        expected_lease_version: int,
    ) -> bool:
        cleaned_task_id = task_id.strip()
        cleaned_task_hash = task_hash.strip()
        if not cleaned_task_id or not cleaned_task_hash or expected_lease_version <= 0:
            return False

        with self._database.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE approval_record
                SET
                    status = ?,
                    last_task_ref = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE action_type = ?
                  AND task_id = ?
                  AND task_hash = ?
                  AND lease_version = ?
                  AND executed_version < ?
                """,
                (
                    APPROVAL_STATUS_PENDING,
                    task_ref.strip(),
                    action_type,
                    cleaned_task_id,
                    cleaned_task_hash,
                    expected_lease_version,
                    expected_lease_version,
                ),
            )
            connection.commit()
        return cursor.rowcount == 1

    def _cancel(
        self,
        *,
        action_type: str,
        task_id: str,
        task_hash: str,
        task_ref: str,
        expected_lease_version: int,
    ) -> bool:
        cleaned_task_id = task_id.strip()
        cleaned_task_hash = task_hash.strip()
        if not cleaned_task_id or not cleaned_task_hash or expected_lease_version <= 0:
            return False

        with self._database.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE approval_record
                SET
                    status = ?,
                    last_task_ref = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE action_type = ?
                  AND task_id = ?
                  AND task_hash = ?
                  AND status = ?
                  AND lease_version = ?
                  AND executed_version < ?
                """,
                (
                    APPROVAL_STATUS_CANCELLED,
                    task_ref.strip(),
                    action_type,
                    cleaned_task_id,
                    cleaned_task_hash,
                    APPROVAL_STATUS_PENDING,
                    expected_lease_version,
                    expected_lease_version,
                ),
            )
            connection.commit()
        return cursor.rowcount == 1

    def _mark_executed(
        self,
        *,
        action_type: str,
        task_id: str,
        task_hash: str,
        executed_lease_version: int,
    ) -> None:
        cleaned_task_id = task_id.strip()
        cleaned_task_hash = task_hash.strip()
        if not cleaned_task_id or not cleaned_task_hash or executed_lease_version <= 0:
            return

        with self._database.connect() as connection:
            connection.execute(
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
                    cleaned_task_id,
                    cleaned_task_hash,
                ),
            )
            connection.commit()

    def _get_approval(
        self,
        *,
        action_type: str,
        task_id: str,
        task_hash: str,
    ) -> ApprovalRecord | None:
        cleaned_task_id = task_id.strip()
        cleaned_task_hash = task_hash.strip()
        if not cleaned_task_id or not cleaned_task_hash:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
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
                (action_type, cleaned_task_id, cleaned_task_hash),
            ).fetchone()
            if row is None:
                row = connection.execute(
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
                    (action_type, cleaned_task_id),
                ).fetchone()
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
        cleaned_task_id = task_id.strip()
        cleaned_task_hash = task_hash.strip()
        if not cleaned_task_id or not cleaned_task_hash or expected_lease_version <= 0:
            return False
        with self._database.connect() as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM approval_record
                WHERE action_type = ?
                  AND task_id = ?
                  AND task_hash = ?
                  AND status = ?
                  AND lease_version = ?
                  AND expires_at != ''
                  AND expires_at <= CURRENT_TIMESTAMP
                LIMIT 1
                """,
                (
                    action_type,
                    cleaned_task_id,
                    cleaned_task_hash,
                    APPROVAL_STATUS_PENDING,
                    expected_lease_version,
                ),
            ).fetchone()
        return row is not None

    def _get_requested_lease_version(
        self,
        *,
        action_type: str,
        task_id: str,
        task_hash: str,
    ) -> int | None:
        with self._database.connect() as connection:
            row = connection.execute(
                """
                SELECT lease_version
                FROM approval_record
                WHERE action_type = ? AND task_id = ? AND task_hash = ?
                LIMIT 1
                """,
                (action_type, task_id, task_hash),
            ).fetchone()
        if row is None:
            return None
        return int(row["lease_version"])


def _to_approval_record(row: Mapping[str, object]) -> ApprovalRecord:
    return ApprovalRecord(
        action_type=str(row["action_type"]),
        task_id=str(row["task_id"]),
        task_hash=str(row["task_hash"]),
        status=str(row["status"]),
        lease_version=int(row["lease_version"]),
        executed_version=int(row["executed_version"]),
        expires_at=str(row["expires_at"]),
        last_task_ref=str(row["last_task_ref"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _format_utc(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")

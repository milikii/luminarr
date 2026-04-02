from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from app.db.sqlite import SqliteDatabase

ACTION_IMPORT_TO_LIBRARY = "import_to_library"
APPROVAL_STATUS_PENDING = "pending"
APPROVAL_STATUS_APPROVED = "approved"


@dataclass(frozen=True, slots=True)
class ApprovalRecord:
    action_type: str
    task_id: str
    task_hash: str
    status: str
    lease_version: int
    executed_version: int
    last_task_ref: str
    created_at: str
    updated_at: str


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
                    ACTION_IMPORT_TO_LIBRARY,
                    cleaned_task_id,
                    cleaned_task_hash,
                    cleaned_status,
                    initial_lease_version,
                    initial_executed_version,
                    task_ref.strip(),
                ),
            )
            connection.commit()

    def request_import_approval(self, *, task_id: str, task_hash: str, task_ref: str) -> int:
        cleaned_task_id = task_id.strip()
        cleaned_task_hash = task_hash.strip()
        if not cleaned_task_id or not cleaned_task_hash:
            return 0

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
                ) VALUES (?, ?, ?, ?, 1, 0, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(action_type, task_id, task_hash)
                DO UPDATE SET
                    status = excluded.status,
                    lease_version = approval_record.lease_version + 1,
                    last_task_ref = excluded.last_task_ref,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    ACTION_IMPORT_TO_LIBRARY,
                    cleaned_task_id,
                    cleaned_task_hash,
                    APPROVAL_STATUS_PENDING,
                    task_ref.strip(),
                ),
            )
            row = connection.execute(
                """
                SELECT lease_version
                FROM approval_record
                WHERE action_type = ? AND task_id = ? AND task_hash = ?
                LIMIT 1
                """,
                (ACTION_IMPORT_TO_LIBRARY, cleaned_task_id, cleaned_task_hash),
            ).fetchone()
            connection.commit()
        if row is None:
            return 0
        return int(row["lease_version"])

    def approve_import(
        self,
        *,
        task_id: str,
        task_hash: str,
        task_ref: str,
        expected_lease_version: int,
    ) -> bool:
        cleaned_task_id = task_id.strip()
        cleaned_task_hash = task_hash.strip()
        if not cleaned_task_id or not cleaned_task_hash:
            return False
        if expected_lease_version <= 0:
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
                    ACTION_IMPORT_TO_LIBRARY,
                    cleaned_task_id,
                    cleaned_task_hash,
                    APPROVAL_STATUS_PENDING,
                    expected_lease_version,
                    expected_lease_version,
                ),
            )
            connection.commit()
        return cursor.rowcount == 1

    def restore_import_pending(
        self,
        *,
        task_id: str,
        task_hash: str,
        task_ref: str,
        expected_lease_version: int,
    ) -> bool:
        cleaned_task_id = task_id.strip()
        cleaned_task_hash = task_hash.strip()
        if not cleaned_task_id or not cleaned_task_hash:
            return False
        if expected_lease_version <= 0:
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
                    ACTION_IMPORT_TO_LIBRARY,
                    cleaned_task_id,
                    cleaned_task_hash,
                    expected_lease_version,
                    expected_lease_version,
                ),
            )
            connection.commit()
        return cursor.rowcount == 1

    def mark_import_executed(self, *, task_id: str, task_hash: str, executed_lease_version: int) -> None:
        cleaned_task_id = task_id.strip()
        cleaned_task_hash = task_hash.strip()
        if not cleaned_task_id or not cleaned_task_hash:
            return
        if executed_lease_version <= 0:
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
                    ACTION_IMPORT_TO_LIBRARY,
                    cleaned_task_id,
                    cleaned_task_hash,
                ),
            )
            connection.commit()

    def get_import_approval(self, *, task_id: str, task_hash: str) -> ApprovalRecord | None:
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
                    last_task_ref,
                    created_at,
                    updated_at
                FROM approval_record
                WHERE action_type = ? AND task_id = ? AND task_hash = ?
                LIMIT 1
                """,
                (ACTION_IMPORT_TO_LIBRARY, cleaned_task_id, cleaned_task_hash),
            ).fetchone()
        if row is None:
            return None
        return _to_approval_record(row)


def _to_approval_record(row: Mapping[str, object]) -> ApprovalRecord:
    return ApprovalRecord(
        action_type=str(row["action_type"]),
        task_id=str(row["task_id"]),
        task_hash=str(row["task_hash"]),
        status=str(row["status"]),
        lease_version=int(row["lease_version"]),
        executed_version=int(row["executed_version"]),
        last_task_ref=str(row["last_task_ref"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from app.db.sqlite import SqliteDatabase

ACTION_IMPORT_TO_LIBRARY = "import_to_library"
APPROVAL_STATUS_APPROVED = "approved"


@dataclass(frozen=True, slots=True)
class ApprovalRecord:
    action_type: str
    task_id: str
    task_hash: str
    status: str
    last_task_ref: str
    created_at: str
    updated_at: str


class ApprovalRepo:
    def __init__(self, database: SqliteDatabase) -> None:
        self._database = database

    def upsert_import_approval(self, *, task_id: str, task_hash: str, task_ref: str) -> None:
        cleaned_task_id = task_id.strip()
        cleaned_task_hash = task_hash.strip()
        if not cleaned_task_id or not cleaned_task_hash:
            return
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO approval_record (
                    action_type,
                    task_id,
                    task_hash,
                    status,
                    last_task_ref,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(action_type, task_id, task_hash)
                DO UPDATE SET
                    status = excluded.status,
                    last_task_ref = excluded.last_task_ref,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    ACTION_IMPORT_TO_LIBRARY,
                    cleaned_task_id,
                    cleaned_task_hash,
                    APPROVAL_STATUS_APPROVED,
                    task_ref.strip(),
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
        last_task_ref=str(row["last_task_ref"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from app.db.sqlite import SqliteDatabase


@dataclass(frozen=True, slots=True)
class JobEvent:
    id: int
    task_ref: str
    task_id: str
    task_hash: str
    event_type: str
    message: str
    created_at: str


class JobEventRepo:
    def __init__(self, database: SqliteDatabase) -> None:
        self._database = database

    def append_event(
        self,
        *,
        task_ref: str,
        event_type: str,
        task_id: str = "",
        task_hash: str = "",
        message: str = "",
    ) -> None:
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO job_event (
                    task_ref,
                    task_id,
                    task_hash,
                    event_type,
                    message
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (task_ref, task_id, task_hash, event_type, message),
            )
            connection.commit()

    def list_events_for_task_ref(self, task_ref: str) -> list[JobEvent]:
        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, task_ref, task_id, task_hash, event_type, message, created_at
                FROM job_event
                WHERE task_ref = ?
                ORDER BY id ASC
                """,
                (task_ref,),
            ).fetchall()
        return [_to_job_event(row) for row in rows]


def _to_job_event(row: Mapping[str, object]) -> JobEvent:
    return JobEvent(
        id=int(row["id"]),
        task_ref=str(row["task_ref"]),
        task_id=str(row["task_id"]),
        task_hash=str(row["task_hash"]),
        event_type=str(row["event_type"]),
        message=str(row["message"]),
        created_at=str(row["created_at"]),
    )

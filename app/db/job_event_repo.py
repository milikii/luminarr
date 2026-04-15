from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace

from app.db.sqlite import SqliteDatabase


@dataclass(frozen=True, slots=True)
class JobEvent:
    id: int
    task_ref: str
    task_id: str
    task_hash: str
    event_type: str
    message: str
    source_path: str
    target_path: str
    created_at: str


class JobEventPersistenceError(RuntimeError):
    pass


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
        source_path: str = "",
        target_path: str = "",
    ) -> None:
        cleaned_task_ref = task_ref.strip()
        cleaned_event_type = event_type.strip()
        if not cleaned_task_ref:
            raise JobEventPersistenceError("job_event task_ref missing")
        if not cleaned_event_type:
            raise JobEventPersistenceError("job_event event_type missing")
        with self._database.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO job_event (
                    task_ref,
                    task_id,
                    task_hash,
                    event_type,
                    message,
                    source_path,
                    target_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (cleaned_task_ref, task_id, task_hash, cleaned_event_type, message, source_path, target_path),
            )
            connection.commit()
            event_id = int(cursor.lastrowid)
        if self._get_event_by_id(event_id) is None:
            raise JobEventPersistenceError("job_event missing after append")

    def list_events_for_task_ref(self, task_ref: str) -> list[JobEvent]:
        cleaned_task_ref = task_ref.strip()
        if not cleaned_task_ref:
            raise JobEventPersistenceError("job_event task_ref missing for query")
        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, task_ref, task_id, task_hash, event_type, message, source_path, target_path, created_at
                FROM job_event
                WHERE task_ref = ?
                ORDER BY id ASC
                """,
                (cleaned_task_ref,),
            ).fetchall()
        return [_to_job_event(row) for row in rows]

    def list_events_for_task_identity(self, *, task_id: str, task_hash: str) -> list[JobEvent]:
        cleaned_task_id = task_id.strip()
        cleaned_task_hash = task_hash.strip()
        if not cleaned_task_id and not cleaned_task_hash:
            raise JobEventPersistenceError("job_event task identity missing for query")

        statement = """
            SELECT id, task_ref, task_id, task_hash, event_type, message, source_path, target_path, created_at
            FROM job_event
            WHERE {condition}
            ORDER BY id ASC
        """
        params: tuple[str, ...]
        condition: str
        if cleaned_task_id and cleaned_task_hash:
            condition = "(task_id = ? OR task_hash = ?)"
            params = (cleaned_task_id, cleaned_task_hash)
        elif cleaned_task_id:
            condition = "task_id = ?"
            params = (cleaned_task_id,)
        else:
            condition = "task_hash = ?"
            params = (cleaned_task_hash,)

        with self._database.connect() as connection:
            rows = connection.execute(statement.format(condition=condition), params).fetchall()
        return [_to_job_event(row) for row in rows]

    def find_latest_import_correlation(
        self,
        *,
        task_ref: str = "",
        task_id: str = "",
        task_hash: str = "",
    ) -> JobEvent | None:
        cleaned_task_ref = task_ref.strip()
        cleaned_task_id = task_id.strip()
        cleaned_task_hash = task_hash.strip()

        events: list[JobEvent] = []
        if cleaned_task_id or cleaned_task_hash:
            events = self.list_events_for_task_identity(task_id=cleaned_task_id, task_hash=cleaned_task_hash)
        if not events and cleaned_task_ref:
            events = self.list_events_for_task_ref(cleaned_task_ref)

        for event in reversed(events):
            if event.event_type != "import.succeeded":
                continue
            target_path = event.target_path.strip() or event.message.strip()
            if not target_path:
                continue
            if target_path == event.target_path:
                return event
            return replace(event, target_path=target_path)
        return None

    def _get_event_by_id(self, event_id: int) -> JobEvent | None:
        if event_id <= 0:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                SELECT id, task_ref, task_id, task_hash, event_type, message, source_path, target_path, created_at
                FROM job_event
                WHERE id = ?
                LIMIT 1
                """,
                (event_id,),
            ).fetchone()
        if row is None:
            return None
        return _to_job_event(row)


def _to_job_event(row: Mapping[str, object]) -> JobEvent:
    return JobEvent(
        id=int(row["id"]),
        task_ref=str(row["task_ref"]),
        task_id=str(row["task_id"]),
        task_hash=str(row["task_hash"]),
        event_type=str(row["event_type"]),
        message=str(row["message"]),
        source_path=str(row["source_path"]),
        target_path=str(row["target_path"]),
        created_at=str(row["created_at"]),
    )

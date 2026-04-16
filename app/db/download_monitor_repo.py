from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from app.clients.transmission import TransmissionTaskStatus
from app.db.sqlite import SqliteDatabase


@dataclass(frozen=True, slots=True)
class DownloadMonitorRecord:
    task_id: str
    task_hash: str
    name: str
    chat_id: int
    user_id: int
    status_code: int
    percent_done: float
    is_complete: bool
    completion_observed_at: str
    last_observed_at: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class DownloadMonitorUpdate:
    record: DownloadMonitorRecord
    newly_completed: bool


class DownloadMonitorPersistenceError(RuntimeError):
    pass


class DownloadMonitorRepo:
    def __init__(self, database: SqliteDatabase) -> None:
        self._database = database

    def register_download(
        self,
        *,
        task_id: str,
        task_hash: str,
        name: str,
        chat_id: int | None = None,
        user_id: int | None = None,
    ) -> None:
        cleaned_task_id = task_id.strip()
        cleaned_task_hash = task_hash.strip()
        if not cleaned_task_id or not cleaned_task_hash:
            raise DownloadMonitorPersistenceError("download monitor task identity missing")
        if chat_id is not None and chat_id <= 0:
            raise DownloadMonitorPersistenceError("download monitor chat identity missing")
        if user_id is not None and user_id <= 0:
            raise DownloadMonitorPersistenceError("download monitor user identity missing")

        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO download_monitor (
                    task_id,
                    task_hash,
                    name,
                    chat_id,
                    user_id,
                    status_code,
                    percent_done,
                    is_complete,
                    completion_observed_at,
                    last_observed_at,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, 0, 0, 0, '', '', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(task_id, task_hash)
                DO UPDATE SET
                    name = excluded.name,
                    chat_id = CASE
                        WHEN excluded.chat_id > 0 THEN excluded.chat_id
                        ELSE download_monitor.chat_id
                    END,
                    user_id = CASE
                        WHEN excluded.user_id > 0 THEN excluded.user_id
                        ELSE download_monitor.user_id
                    END,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    cleaned_task_id,
                    cleaned_task_hash,
                    name.strip(),
                    int(chat_id or 0),
                    int(user_id or 0),
                ),
            )
            connection.commit()

    def record_status(self, task_status: TransmissionTaskStatus) -> DownloadMonitorUpdate:
        cleaned_task_id = task_status.task_id.strip()
        cleaned_task_hash = task_status.task_hash.strip()
        if not cleaned_task_id or not cleaned_task_hash:
            raise DownloadMonitorPersistenceError("download monitor task identity missing")

        completed = _is_download_completed(task_status)
        with self._database.connect() as connection:
            existing_row = connection.execute(
                """
                SELECT
                    task_id,
                    task_hash,
                    name,
                    chat_id,
                    user_id,
                    status_code,
                    percent_done,
                    is_complete,
                    completion_observed_at,
                    last_observed_at,
                    created_at,
                    updated_at
                FROM download_monitor
                WHERE task_id = ? AND task_hash = ?
                LIMIT 1
                """,
                (cleaned_task_id, cleaned_task_hash),
            ).fetchone()

            previous_completion = ""
            if existing_row is not None:
                previous_completion = str(existing_row["completion_observed_at"])

            connection.execute(
                """
                INSERT INTO download_monitor (
                    task_id,
                    task_hash,
                    name,
                    chat_id,
                    user_id,
                    status_code,
                    percent_done,
                    is_complete,
                    completion_observed_at,
                    last_observed_at,
                    created_at,
                    updated_at
                ) VALUES (
                    ?, ?, ?, 0, 0, ?, ?, ?, CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE '' END, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                ON CONFLICT(task_id, task_hash)
                DO UPDATE SET
                    name = excluded.name,
                    status_code = excluded.status_code,
                    percent_done = excluded.percent_done,
                    is_complete = CASE
                        WHEN download_monitor.is_complete = 1 THEN 1
                        ELSE excluded.is_complete
                    END,
                    completion_observed_at = CASE
                        WHEN download_monitor.completion_observed_at != '' THEN download_monitor.completion_observed_at
                        WHEN excluded.is_complete = 1 THEN CURRENT_TIMESTAMP
                        ELSE ''
                    END,
                    last_observed_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    cleaned_task_id,
                    cleaned_task_hash,
                    task_status.name.strip(),
                    int(task_status.status_code),
                    float(task_status.percent_done),
                    1 if completed else 0,
                    completed,
                ),
            )
            connection.commit()

        record = self._get_record_by_identity(task_id=cleaned_task_id, task_hash=cleaned_task_hash)
        if record is None:
            raise DownloadMonitorPersistenceError("download monitor state missing after status upsert")
        newly_completed = completed and not previous_completion and bool(record.completion_observed_at)
        return DownloadMonitorUpdate(record=record, newly_completed=newly_completed)

    def get_record(self, *, task_id: str, task_hash: str) -> DownloadMonitorRecord | None:
        cleaned_task_id = task_id.strip()
        cleaned_task_hash = task_hash.strip()
        if not cleaned_task_id or not cleaned_task_hash:
            raise DownloadMonitorPersistenceError("download monitor task identity missing for query")
        return self._get_record_by_identity(task_id=cleaned_task_id, task_hash=cleaned_task_hash)

    def list_pending_completion(self, *, limit: int = 100) -> list[DownloadMonitorRecord]:
        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    task_id,
                    task_hash,
                    name,
                    chat_id,
                    user_id,
                    status_code,
                    percent_done,
                    is_complete,
                    completion_observed_at,
                    last_observed_at,
                    created_at,
                    updated_at
                FROM download_monitor
                WHERE is_complete = 0
                ORDER BY created_at ASC, updated_at ASC
                LIMIT ?
                """,
                (max(1, limit),),
            ).fetchall()
        return [_to_download_monitor_record(row) for row in rows]

    def list_completed_for_auto_import(self, *, limit: int = 20) -> list[DownloadMonitorRecord]:
        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    task_id,
                    task_hash,
                    name,
                    chat_id,
                    user_id,
                    status_code,
                    percent_done,
                    is_complete,
                    completion_observed_at,
                    last_observed_at,
                    created_at,
                    updated_at
                FROM download_monitor
                WHERE is_complete = 1
                ORDER BY completion_observed_at ASC, updated_at ASC
                LIMIT ?
                """,
                (max(1, limit),),
            ).fetchall()
        return [_to_download_monitor_record(row) for row in rows]

    def _get_record_by_identity(self, *, task_id: str, task_hash: str) -> DownloadMonitorRecord | None:
        with self._database.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    task_id,
                    task_hash,
                    name,
                    chat_id,
                    user_id,
                    status_code,
                    percent_done,
                    is_complete,
                    completion_observed_at,
                    last_observed_at,
                    created_at,
                    updated_at
                FROM download_monitor
                WHERE task_id = ? AND task_hash = ?
                LIMIT 1
                """,
                (task_id, task_hash),
            ).fetchone()
        if row is None:
            return None
        return _to_download_monitor_record(row)


def _is_download_completed(task_status: TransmissionTaskStatus) -> bool:
    if task_status.percent_done >= 1.0:
        return True
    return task_status.status_code in {5, 6}


def _to_download_monitor_record(row: Mapping[str, object]) -> DownloadMonitorRecord:
    task_id = str(row["task_id"]).strip()
    task_hash = str(row["task_hash"]).strip()
    status_code = int(row["status_code"])
    percent_done = float(row["percent_done"])

    if not task_id or not task_hash:
        raise DownloadMonitorPersistenceError("download monitor row identity corrupted after read")
    if status_code < 0:
        raise DownloadMonitorPersistenceError("download monitor status corrupted after read")
    if percent_done < 0:
        raise DownloadMonitorPersistenceError("download monitor progress corrupted after read")

    return DownloadMonitorRecord(
        task_id=task_id,
        task_hash=task_hash,
        name=str(row["name"]),
        chat_id=int(row["chat_id"]),
        user_id=int(row["user_id"]),
        status_code=status_code,
        percent_done=percent_done,
        is_complete=bool(int(row["is_complete"])),
        completion_observed_at=str(row["completion_observed_at"]),
        last_observed_at=str(row["last_observed_at"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )

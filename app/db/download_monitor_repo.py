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


class DownloadMonitorRepo:
    def __init__(self, database: SqliteDatabase) -> None:
        self._database = database

    def register_download(self, *, task_id: str, task_hash: str, name: str) -> None:
        cleaned_task_id = task_id.strip()
        cleaned_task_hash = task_hash.strip()
        if not cleaned_task_id or not cleaned_task_hash:
            return

        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO download_monitor (
                    task_id,
                    task_hash,
                    name,
                    status_code,
                    percent_done,
                    is_complete,
                    completion_observed_at,
                    last_observed_at,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, 0, 0, 0, '', '', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(task_id, task_hash)
                DO UPDATE SET
                    name = excluded.name,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (cleaned_task_id, cleaned_task_hash, name.strip()),
            )
            connection.commit()

    def record_status(self, task_status: TransmissionTaskStatus) -> DownloadMonitorUpdate:
        cleaned_task_id = task_status.task_id.strip()
        cleaned_task_hash = task_status.task_hash.strip()
        if not cleaned_task_id or not cleaned_task_hash:
            raise ValueError("task id/hash is required")

        completed = _is_download_completed(task_status)
        with self._database.connect() as connection:
            existing_row = connection.execute(
                """
                SELECT
                    task_id,
                    task_hash,
                    name,
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
                    status_code,
                    percent_done,
                    is_complete,
                    completion_observed_at,
                    last_observed_at,
                    created_at,
                    updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE '' END, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
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
            row = connection.execute(
                """
                SELECT
                    task_id,
                    task_hash,
                    name,
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
            connection.commit()

        if row is None:
            raise RuntimeError("failed to persist download monitor state")

        record = _to_download_monitor_record(row)
        newly_completed = completed and not previous_completion and bool(record.completion_observed_at)
        return DownloadMonitorUpdate(record=record, newly_completed=newly_completed)

    def get_record(self, *, task_id: str, task_hash: str) -> DownloadMonitorRecord | None:
        cleaned_task_id = task_id.strip()
        cleaned_task_hash = task_hash.strip()
        if not cleaned_task_id or not cleaned_task_hash:
            return None

        with self._database.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    task_id,
                    task_hash,
                    name,
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
        if row is None:
            return None
        return _to_download_monitor_record(row)

    def list_pending_completion(self) -> list[DownloadMonitorRecord]:
        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    task_id,
                    task_hash,
                    name,
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
                """
            ).fetchall()
        return [_to_download_monitor_record(row) for row in rows]


def _is_download_completed(task_status: TransmissionTaskStatus) -> bool:
    if task_status.percent_done >= 1.0:
        return True
    return task_status.status_code in {5, 6}


def _to_download_monitor_record(row: Mapping[str, object]) -> DownloadMonitorRecord:
    return DownloadMonitorRecord(
        task_id=str(row["task_id"]),
        task_hash=str(row["task_hash"]),
        name=str(row["name"]),
        status_code=int(row["status_code"]),
        percent_done=float(row["percent_done"]),
        is_complete=bool(int(row["is_complete"])),
        completion_observed_at=str(row["completion_observed_at"]),
        last_observed_at=str(row["last_observed_at"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )

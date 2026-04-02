from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS candidate_mapping (
        chat_id INTEGER NOT NULL,
        selection_index INTEGER NOT NULL,
        candidate_json TEXT NOT NULL,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (chat_id, selection_index)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS job_event (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_ref TEXT NOT NULL,
        task_id TEXT NOT NULL DEFAULT '',
        task_hash TEXT NOT NULL DEFAULT '',
        event_type TEXT NOT NULL,
        message TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_job_event_task_ref ON job_event(task_ref)",
    "CREATE INDEX IF NOT EXISTS idx_job_event_task_id ON job_event(task_id)",
    "CREATE INDEX IF NOT EXISTS idx_job_event_task_hash ON job_event(task_hash)",
)


class SqliteDatabase:
    def __init__(self, db_path: str) -> None:
        self._db_path = Path(db_path).expanduser()

    @property
    def db_path(self) -> Path:
        return self._db_path

    def initialize(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            for statement in SCHEMA_STATEMENTS:
                connection.execute(statement)
            connection.commit()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

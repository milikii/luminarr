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
    CREATE TABLE IF NOT EXISTS approval_record (
        action_type TEXT NOT NULL,
        task_id TEXT NOT NULL DEFAULT '',
        task_hash TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL,
        lease_version INTEGER NOT NULL DEFAULT 0,
        executed_version INTEGER NOT NULL DEFAULT 0,
        expires_at TEXT NOT NULL DEFAULT '',
        last_task_ref TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (action_type, task_id, task_hash)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_approval_record_task_id ON approval_record(task_id)",
    "CREATE INDEX IF NOT EXISTS idx_approval_record_task_hash ON approval_record(task_hash)",
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
    """
    CREATE TABLE IF NOT EXISTS telegram_updates (
        update_key TEXT PRIMARY KEY,
        source_type TEXT NOT NULL,
        source_id TEXT NOT NULL,
        chat_id INTEGER NOT NULL DEFAULT 0,
        user_id INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS watchlist_item (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        year TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(chat_id, title, year)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_watchlist_item_chat_id ON watchlist_item(chat_id)",
    """
    CREATE TABLE IF NOT EXISTS jobs (
        job_id TEXT PRIMARY KEY,
        chat_id INTEGER NOT NULL DEFAULT 0,
        user_id INTEGER NOT NULL DEFAULT 0,
        workflow_type TEXT NOT NULL,
        state TEXT NOT NULL,
        task_ref TEXT NOT NULL DEFAULT '',
        task_id TEXT NOT NULL DEFAULT '',
        task_hash TEXT NOT NULL DEFAULT '',
        payload_json TEXT NOT NULL DEFAULT '',
        version INTEGER NOT NULL DEFAULT 1,
        lease_owner TEXT NOT NULL DEFAULT '',
        lease_until TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_jobs_chat_workflow ON jobs(chat_id, workflow_type)",
    "CREATE INDEX IF NOT EXISTS idx_jobs_task_ref ON jobs(task_ref)",
    "CREATE INDEX IF NOT EXISTS idx_jobs_task_identity ON jobs(task_id, task_hash)",
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
            _ensure_approval_record_columns(connection)
            _ensure_jobs_columns(connection)
            connection.commit()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()


def _ensure_approval_record_columns(connection: sqlite3.Connection) -> None:
    rows = connection.execute("PRAGMA table_info(approval_record)").fetchall()
    existing_columns = {str(row["name"]) for row in rows}
    if "lease_version" not in existing_columns:
        connection.execute(
            "ALTER TABLE approval_record ADD COLUMN lease_version INTEGER NOT NULL DEFAULT 0"
        )
    if "executed_version" not in existing_columns:
        connection.execute(
            "ALTER TABLE approval_record ADD COLUMN executed_version INTEGER NOT NULL DEFAULT 0"
        )
    if "expires_at" not in existing_columns:
        connection.execute("ALTER TABLE approval_record ADD COLUMN expires_at TEXT NOT NULL DEFAULT ''")


def _ensure_jobs_columns(connection: sqlite3.Connection) -> None:
    rows = connection.execute("PRAGMA table_info(jobs)").fetchall()
    existing_columns = {str(row["name"]) for row in rows}
    if "payload_json" not in existing_columns:
        connection.execute("ALTER TABLE jobs ADD COLUMN payload_json TEXT NOT NULL DEFAULT ''")

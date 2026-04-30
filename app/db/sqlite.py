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
        source_path TEXT NOT NULL DEFAULT '',
        target_path TEXT NOT NULL DEFAULT '',
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
        media_kind TEXT NOT NULL DEFAULT 'movie',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(chat_id, title, year, media_kind)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_watchlist_item_chat_id ON watchlist_item(chat_id)",
    """
    CREATE TABLE IF NOT EXISTS clarification_state (
        chat_id INTEGER PRIMARY KEY,
        query TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS bt_pending_state (
        chat_id INTEGER PRIMARY KEY,
        stage TEXT NOT NULL DEFAULT '',
        payload_json TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS bt_subscription_item (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        year TEXT NOT NULL DEFAULT '',
        media_kind TEXT NOT NULL DEFAULT 'movie',
        last_seen_source TEXT NOT NULL DEFAULT '',
        last_seen_title TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(chat_id, title, year, media_kind)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_bt_subscription_item_chat_id ON bt_subscription_item(chat_id)",
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
    """
    CREATE TABLE IF NOT EXISTS download_monitor (
        task_id TEXT NOT NULL,
        task_hash TEXT NOT NULL,
        name TEXT NOT NULL DEFAULT '',
        chat_id INTEGER NOT NULL DEFAULT 0,
        user_id INTEGER NOT NULL DEFAULT 0,
        status_code INTEGER NOT NULL DEFAULT 0,
        percent_done REAL NOT NULL DEFAULT 0,
        is_complete INTEGER NOT NULL DEFAULT 0,
        completion_observed_at TEXT NOT NULL DEFAULT '',
        last_observed_at TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (task_id, task_hash)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_download_monitor_complete ON download_monitor(is_complete, updated_at)",
    """
    CREATE TABLE IF NOT EXISTS adult_content_registry (
        normalized_content_id TEXT PRIMARY KEY,
        content_id_kind TEXT NOT NULL,
        archive_category TEXT NOT NULL,
        display_title TEXT NOT NULL DEFAULT '',
        latest_source_site TEXT NOT NULL DEFAULT '',
        current_status TEXT NOT NULL DEFAULT '',
        current_task_ref TEXT NOT NULL DEFAULT '',
        current_task_id TEXT NOT NULL DEFAULT '',
        current_task_hash TEXT NOT NULL DEFAULT '',
        current_downloader_name TEXT NOT NULL DEFAULT '',
        archive_path TEXT NOT NULL DEFAULT '',
        archive_present INTEGER NOT NULL DEFAULT 0,
        last_status_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_adult_content_registry_task_identity ON adult_content_registry(current_task_id, current_task_hash)",
    "CREATE INDEX IF NOT EXISTS idx_adult_content_registry_status ON adult_content_registry(current_status, updated_at)",
    """
    CREATE TABLE IF NOT EXISTS adult_duplicate_memory_snapshot (
        normalized_content_id TEXT PRIMARY KEY,
        display_title TEXT NOT NULL DEFAULT '',
        snapshot_status TEXT NOT NULL DEFAULT '',
        evidence_summary_json TEXT NOT NULL DEFAULT '',
        last_verified_at TEXT NOT NULL DEFAULT '',
        last_scan_failed_at TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_adult_duplicate_memory_snapshot_status ON adult_duplicate_memory_snapshot(snapshot_status, updated_at)",
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
            _ensure_download_monitor_columns(connection)
            _ensure_watchlist_item_columns(connection)
            _ensure_job_event_columns(connection)
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


def _ensure_download_monitor_columns(connection: sqlite3.Connection) -> None:
    rows = connection.execute("PRAGMA table_info(download_monitor)").fetchall()
    existing_columns = {str(row["name"]) for row in rows}
    if "chat_id" not in existing_columns:
        connection.execute("ALTER TABLE download_monitor ADD COLUMN chat_id INTEGER NOT NULL DEFAULT 0")
    if "user_id" not in existing_columns:
        connection.execute("ALTER TABLE download_monitor ADD COLUMN user_id INTEGER NOT NULL DEFAULT 0")


def _ensure_watchlist_item_columns(connection: sqlite3.Connection) -> None:
    rows = connection.execute("PRAGMA table_info(watchlist_item)").fetchall()
    existing_columns = {str(row["name"]) for row in rows}
    if "media_kind" in existing_columns:
        return

    connection.execute(
        """
        CREATE TABLE watchlist_item_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            year TEXT NOT NULL DEFAULT '',
            media_kind TEXT NOT NULL DEFAULT 'movie',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(chat_id, title, year, media_kind)
        )
        """
    )
    connection.execute(
        """
        INSERT INTO watchlist_item_new (
            id,
            chat_id,
            title,
            year,
            media_kind,
            created_at,
            updated_at
        )
        SELECT
            id,
            chat_id,
            title,
            year,
            'movie',
            created_at,
            updated_at
        FROM watchlist_item
        """
    )
    connection.execute("DROP TABLE watchlist_item")
    connection.execute("ALTER TABLE watchlist_item_new RENAME TO watchlist_item")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_watchlist_item_chat_id ON watchlist_item(chat_id)")


def _ensure_job_event_columns(connection: sqlite3.Connection) -> None:
    rows = connection.execute("PRAGMA table_info(job_event)").fetchall()
    existing_columns = {str(row["name"]) for row in rows}
    if "source_path" not in existing_columns:
        connection.execute("ALTER TABLE job_event ADD COLUMN source_path TEXT NOT NULL DEFAULT ''")
    if "target_path" not in existing_columns:
        connection.execute("ALTER TABLE job_event ADD COLUMN target_path TEXT NOT NULL DEFAULT ''")

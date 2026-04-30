from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from app.db.sqlite import SqliteDatabase


class AdultDuplicateMemorySnapshotPersistenceError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AdultDuplicateMemorySnapshotRecord:
    normalized_content_id: str
    display_title: str
    snapshot_status: str
    evidence_summary_json: str
    last_verified_at: str
    last_scan_failed_at: str
    created_at: str
    updated_at: str


class AdultDuplicateMemorySnapshotRepo:
    def __init__(self, database: SqliteDatabase) -> None:
        self._database = database

    def get_snapshot(self, normalized_content_id: str) -> AdultDuplicateMemorySnapshotRecord | None:
        cleaned_content_id = normalized_content_id.strip().lower()
        if not cleaned_content_id:
            raise AdultDuplicateMemorySnapshotPersistenceError(
                "adult_duplicate_memory_snapshot content id missing for query"
            )
        with self._database.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    normalized_content_id,
                    display_title,
                    snapshot_status,
                    evidence_summary_json,
                    last_verified_at,
                    last_scan_failed_at,
                    created_at,
                    updated_at
                FROM adult_duplicate_memory_snapshot
                WHERE normalized_content_id = ?
                LIMIT 1
                """,
                (cleaned_content_id,),
            ).fetchone()
        if row is None:
            return None
        return _to_snapshot_record(row)

    def upsert_snapshot(
        self,
        *,
        normalized_content_id: str,
        display_title: str,
        snapshot_status: str,
        evidence_summary_json: str,
        last_verified_at: str,
        last_scan_failed_at: str,
    ) -> AdultDuplicateMemorySnapshotRecord:
        cleaned_content_id = normalized_content_id.strip().lower()
        if not cleaned_content_id:
            raise AdultDuplicateMemorySnapshotPersistenceError("adult_duplicate_memory_snapshot content id missing")
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO adult_duplicate_memory_snapshot (
                    normalized_content_id,
                    display_title,
                    snapshot_status,
                    evidence_summary_json,
                    last_verified_at,
                    last_scan_failed_at,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(normalized_content_id)
                DO UPDATE SET
                    display_title = excluded.display_title,
                    snapshot_status = excluded.snapshot_status,
                    evidence_summary_json = excluded.evidence_summary_json,
                    last_verified_at = excluded.last_verified_at,
                    last_scan_failed_at = excluded.last_scan_failed_at,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    cleaned_content_id,
                    display_title.strip(),
                    snapshot_status.strip(),
                    evidence_summary_json.strip(),
                    last_verified_at.strip(),
                    last_scan_failed_at.strip(),
                ),
            )
            connection.commit()
        record = self.get_snapshot(cleaned_content_id)
        if record is None:
            raise AdultDuplicateMemorySnapshotPersistenceError(
                "adult_duplicate_memory_snapshot missing after upsert"
            )
        return record


def _to_snapshot_record(row: Mapping[str, object]) -> AdultDuplicateMemorySnapshotRecord:
    normalized_content_id = str(row["normalized_content_id"]).strip().lower()
    snapshot_status = str(row["snapshot_status"]).strip()
    if not normalized_content_id or not snapshot_status:
        raise AdultDuplicateMemorySnapshotPersistenceError(
            "adult_duplicate_memory_snapshot row identity corrupted after read"
        )
    return AdultDuplicateMemorySnapshotRecord(
        normalized_content_id=normalized_content_id,
        display_title=str(row["display_title"]),
        snapshot_status=snapshot_status,
        evidence_summary_json=str(row["evidence_summary_json"]),
        last_verified_at=str(row["last_verified_at"]),
        last_scan_failed_at=str(row["last_scan_failed_at"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )

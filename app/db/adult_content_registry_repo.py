from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.db.sqlite import SqliteDatabase

ADULT_CONTENT_STATUS_PENDING = "pending"
ADULT_CONTENT_STATUS_DOWNLOADING = "downloading"
ADULT_CONTENT_STATUS_ARCHIVED_PRESENT = "archived_present"
ADULT_CONTENT_STATUS_ARCHIVED_DELETED = "archived_deleted"
ADULT_CONTENT_STATUSES = {
    ADULT_CONTENT_STATUS_PENDING,
    ADULT_CONTENT_STATUS_DOWNLOADING,
    ADULT_CONTENT_STATUS_ARCHIVED_PRESENT,
    ADULT_CONTENT_STATUS_ARCHIVED_DELETED,
}


@dataclass(frozen=True, slots=True)
class AdultContentRegistryRecord:
    normalized_content_id: str
    content_id_kind: str
    archive_category: str
    display_title: str
    latest_source_site: str
    current_status: str
    current_task_ref: str
    current_task_id: str
    current_task_hash: str
    current_downloader_name: str
    archive_path: str
    archive_present: bool
    last_status_at: str
    created_at: str
    updated_at: str


class AdultContentRegistryPersistenceError(RuntimeError):
    pass


class AdultContentRegistryRepo:
    def __init__(self, database: SqliteDatabase) -> None:
        self._database = database

    def get_by_content_id(self, *, normalized_content_id: str) -> AdultContentRegistryRecord | None:
        cleaned_id = normalized_content_id.strip().lower()
        if not cleaned_id:
            raise AdultContentRegistryPersistenceError("adult_content_registry content id missing for query")
        with self._database.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    normalized_content_id,
                    content_id_kind,
                    archive_category,
                    display_title,
                    latest_source_site,
                    current_status,
                    current_task_ref,
                    current_task_id,
                    current_task_hash,
                    current_downloader_name,
                    archive_path,
                    archive_present,
                    last_status_at,
                    created_at,
                    updated_at
                FROM adult_content_registry
                WHERE normalized_content_id = ?
                LIMIT 1
                """,
                (cleaned_id,),
            ).fetchone()
        if row is None:
            return None
        return _to_registry_record(row)

    def get_by_task_identity(self, *, task_id: str, task_hash: str) -> AdultContentRegistryRecord | None:
        cleaned_task_id = task_id.strip()
        cleaned_task_hash = task_hash.strip()
        if not cleaned_task_id and not cleaned_task_hash:
            raise AdultContentRegistryPersistenceError("adult_content_registry task identity missing for query")
        condition = "current_task_id = ?" if cleaned_task_id else "current_task_hash = ?"
        params: tuple[str, ...] = (cleaned_task_id,) if cleaned_task_id else (cleaned_task_hash,)
        if cleaned_task_id and cleaned_task_hash:
            condition = "(current_task_id = ? OR current_task_hash = ?)"
            params = (cleaned_task_id, cleaned_task_hash)
        with self._database.connect() as connection:
            row = connection.execute(
                f"""
                SELECT
                    normalized_content_id,
                    content_id_kind,
                    archive_category,
                    display_title,
                    latest_source_site,
                    current_status,
                    current_task_ref,
                    current_task_id,
                    current_task_hash,
                    current_downloader_name,
                    archive_path,
                    archive_present,
                    last_status_at,
                    created_at,
                    updated_at
                FROM adult_content_registry
                WHERE {condition}
                LIMIT 1
                """,
                params,
            ).fetchone()
        if row is None:
            return None
        return _to_registry_record(row)

    def upsert_pending(
        self,
        *,
        normalized_content_id: str,
        content_id_kind: str,
        archive_category: str,
        display_title: str,
        latest_source_site: str,
        task_ref: str,
        task_id: str,
        task_hash: str,
        downloader_name: str,
    ) -> None:
        self._upsert_status(
            normalized_content_id=normalized_content_id,
            content_id_kind=content_id_kind,
            archive_category=archive_category,
            display_title=display_title,
            latest_source_site=latest_source_site,
            current_status=ADULT_CONTENT_STATUS_PENDING,
            task_ref=task_ref,
            task_id=task_id,
            task_hash=task_hash,
            downloader_name=downloader_name,
            archive_path="",
            archive_present=False,
        )

    def mark_downloading(
        self,
        *,
        normalized_content_id: str,
        content_id_kind: str,
        archive_category: str,
        display_title: str,
        latest_source_site: str,
        task_ref: str,
        task_id: str,
        task_hash: str,
        downloader_name: str,
    ) -> None:
        self._upsert_status(
            normalized_content_id=normalized_content_id,
            content_id_kind=content_id_kind,
            archive_category=archive_category,
            display_title=display_title,
            latest_source_site=latest_source_site,
            current_status=ADULT_CONTENT_STATUS_DOWNLOADING,
            task_ref=task_ref,
            task_id=task_id,
            task_hash=task_hash,
            downloader_name=downloader_name,
            archive_path="",
            archive_present=False,
        )

    def mark_archived_present(
        self,
        *,
        normalized_content_id: str,
        archive_path: str,
        task_id: str,
        task_hash: str,
    ) -> None:
        self._transition_archive_status(
            normalized_content_id=normalized_content_id,
            current_status=ADULT_CONTENT_STATUS_ARCHIVED_PRESENT,
            archive_path=archive_path,
            archive_present=True,
            task_id=task_id,
            task_hash=task_hash,
        )

    def mark_archived_deleted(
        self,
        *,
        normalized_content_id: str,
        archive_path: str,
        task_id: str,
        task_hash: str,
    ) -> None:
        self._transition_archive_status(
            normalized_content_id=normalized_content_id,
            current_status=ADULT_CONTENT_STATUS_ARCHIVED_DELETED,
            archive_path=archive_path,
            archive_present=False,
            task_id=task_id,
            task_hash=task_hash,
        )

    def _upsert_status(
        self,
        *,
        normalized_content_id: str,
        content_id_kind: str,
        archive_category: str,
        display_title: str,
        latest_source_site: str,
        current_status: str,
        task_ref: str,
        task_id: str,
        task_hash: str,
        downloader_name: str,
        archive_path: str,
        archive_present: bool,
    ) -> None:
        cleaned_content_id = normalized_content_id.strip().lower()
        cleaned_kind = content_id_kind.strip().lower()
        cleaned_category = archive_category.strip().lower()
        cleaned_status = current_status.strip().lower()
        if not cleaned_content_id:
            raise AdultContentRegistryPersistenceError("adult_content_registry content id missing")
        if not cleaned_kind:
            raise AdultContentRegistryPersistenceError("adult_content_registry content kind missing")
        if not cleaned_category:
            raise AdultContentRegistryPersistenceError("adult_content_registry archive category missing")
        if cleaned_status not in ADULT_CONTENT_STATUSES:
            raise AdultContentRegistryPersistenceError("adult_content_registry status invalid")
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO adult_content_registry (
                    normalized_content_id,
                    content_id_kind,
                    archive_category,
                    display_title,
                    latest_source_site,
                    current_status,
                    current_task_ref,
                    current_task_id,
                    current_task_hash,
                    current_downloader_name,
                    archive_path,
                    archive_present,
                    last_status_at,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(normalized_content_id)
                DO UPDATE SET
                    content_id_kind = excluded.content_id_kind,
                    archive_category = excluded.archive_category,
                    display_title = CASE
                        WHEN excluded.display_title != '' THEN excluded.display_title
                        ELSE adult_content_registry.display_title
                    END,
                    latest_source_site = CASE
                        WHEN excluded.latest_source_site != '' THEN excluded.latest_source_site
                        ELSE adult_content_registry.latest_source_site
                    END,
                    current_status = excluded.current_status,
                    current_task_ref = excluded.current_task_ref,
                    current_task_id = excluded.current_task_id,
                    current_task_hash = excluded.current_task_hash,
                    current_downloader_name = excluded.current_downloader_name,
                    archive_path = CASE
                        WHEN excluded.archive_path != '' THEN excluded.archive_path
                        ELSE adult_content_registry.archive_path
                    END,
                    archive_present = excluded.archive_present,
                    last_status_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    cleaned_content_id,
                    cleaned_kind,
                    cleaned_category,
                    display_title.strip(),
                    latest_source_site.strip(),
                    cleaned_status,
                    task_ref.strip(),
                    task_id.strip(),
                    task_hash.strip(),
                    downloader_name.strip(),
                    archive_path.strip(),
                    1 if archive_present else 0,
                ),
            )
            connection.commit()
        if self.get_by_content_id(normalized_content_id=cleaned_content_id) is None:
            raise AdultContentRegistryPersistenceError("adult_content_registry missing after upsert")

    def _transition_archive_status(
        self,
        *,
        normalized_content_id: str,
        current_status: str,
        archive_path: str,
        archive_present: bool,
        task_id: str,
        task_hash: str,
    ) -> None:
        cleaned_content_id = normalized_content_id.strip().lower()
        if not cleaned_content_id:
            raise AdultContentRegistryPersistenceError("adult_content_registry content id missing for transition")
        with self._database.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE adult_content_registry
                SET
                    current_status = ?,
                    archive_path = ?,
                    archive_present = ?,
                    current_task_id = ?,
                    current_task_hash = ?,
                    last_status_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE normalized_content_id = ?
                """,
                (
                    current_status,
                    archive_path.strip(),
                    1 if archive_present else 0,
                    task_id.strip(),
                    task_hash.strip(),
                    cleaned_content_id,
                ),
            )
            connection.commit()
        if cursor.rowcount <= 0:
            raise AdultContentRegistryPersistenceError("adult_content_registry row missing during transition")


def _to_registry_record(row: Any) -> AdultContentRegistryRecord:
    normalized_content_id = str(row["normalized_content_id"]).strip().lower()
    content_id_kind = str(row["content_id_kind"]).strip().lower()
    archive_category = str(row["archive_category"]).strip().lower()
    current_status = str(row["current_status"]).strip().lower()
    if not normalized_content_id or not content_id_kind or not archive_category:
        raise AdultContentRegistryPersistenceError("adult_content_registry row identity corrupted after read")
    if current_status not in ADULT_CONTENT_STATUSES:
        raise AdultContentRegistryPersistenceError("adult_content_registry row status corrupted after read")
    return AdultContentRegistryRecord(
        normalized_content_id=normalized_content_id,
        content_id_kind=content_id_kind,
        archive_category=archive_category,
        display_title=str(row["display_title"]).strip(),
        latest_source_site=str(row["latest_source_site"]).strip(),
        current_status=current_status,
        current_task_ref=str(row["current_task_ref"]).strip(),
        current_task_id=str(row["current_task_id"]).strip(),
        current_task_hash=str(row["current_task_hash"]).strip(),
        current_downloader_name=str(row["current_downloader_name"]).strip(),
        archive_path=str(row["archive_path"]).strip(),
        archive_present=bool(int(row["archive_present"])),
        last_status_at=str(row["last_status_at"]).strip(),
        created_at=str(row["created_at"]).strip(),
        updated_at=str(row["updated_at"]).strip(),
    )

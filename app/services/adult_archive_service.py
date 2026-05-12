from __future__ import annotations

import shutil
import sqlite3
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from app.clients.transmission import TransmissionImportSource
from app.config import AdultArchiveDestination
from app.db.adult_content_registry_repo import (
    ADULT_CONTENT_STATUS_ARCHIVED_DELETED,
    ADULT_CONTENT_STATUS_ARCHIVED_PRESENT,
    ADULT_CONTENT_STATUS_DOWNLOADING,
    ADULT_CONTENT_STATUS_PENDING,
    AdultContentRegistryPersistenceError,
    AdultContentRegistryRecord,
    AdultContentRegistryRepo,
)
from app.db.download_monitor_repo import DownloadMonitorRecord
from app.db.job_event_repo import JobEventPersistenceError, JobEventRepo
from app.services.import_transfer_execution import _copy_import, _hardlink_import

GetImportSourceFunc = Callable[..., Awaitable[TransmissionImportSource | None]]
RemoveTorrentFunc = Callable[..., Awaitable[None]]

_SQLITE_UTC_FORMAT = "%Y-%m-%d %H:%M:%S"


class AdultArchiveStateUnavailableError(RuntimeError):
    pass


class AdultArchiveOperationError(RuntimeError):
    pass


class AdultArchiveService:
    def __init__(
        self,
        *,
        get_import_source_func: GetImportSourceFunc,
        remove_torrent_func: RemoveTorrentFunc,
        registry_repo: AdultContentRegistryRepo,
        job_event_repo: JobEventRepo,
        archive_destinations: tuple[AdultArchiveDestination, ...],
        retention_hours: int,
    ) -> None:
        self._get_import_source_func = get_import_source_func
        self._remove_torrent_func = remove_torrent_func
        self._registry_repo = registry_repo
        self._job_event_repo = job_event_repo
        self._archive_destinations = {item.category: item for item in archive_destinations}
        self._retention_hours = max(0, retention_hours)

    async def run_for_record(
        self,
        *,
        candidate: DownloadMonitorRecord,
        registry_record: AdultContentRegistryRecord,
    ) -> str | None:
        if registry_record.current_status in {
            ADULT_CONTENT_STATUS_PENDING,
            ADULT_CONTENT_STATUS_DOWNLOADING,
        }:
            return await self._archive_completed_download(candidate=candidate, registry_record=registry_record)
        if registry_record.current_status == ADULT_CONTENT_STATUS_ARCHIVED_PRESENT:
            if not self._retention_elapsed(candidate):
                return None
            return await self._cleanup_retained_download(candidate=candidate, registry_record=registry_record)
        if registry_record.current_status == ADULT_CONTENT_STATUS_ARCHIVED_DELETED:
            return None
        return None

    async def _archive_completed_download(
        self,
        *,
        candidate: DownloadMonitorRecord,
        registry_record: AdultContentRegistryRecord,
    ) -> str | None:
        import_source = await self._get_import_source(candidate=candidate)
        if import_source is None:
            return None
        source_path = Path(import_source.download_dir) / import_source.name
        if not source_path.exists():
            raise AdultArchiveStateUnavailableError(
                f"adult archive source missing for {candidate.task_id}/{candidate.task_hash}: {source_path}"
            )
        destination = self._archive_destinations.get(registry_record.archive_category)
        if destination is None:
            raise AdultArchiveStateUnavailableError(
                f"adult archive destination missing for category={registry_record.archive_category}"
            )
        target_root = Path(destination.target_dir).expanduser()
        try:
            target_root.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise AdultArchiveStateUnavailableError(
                f"adult archive target root create failed for {target_root}: {error}"
            ) from error
        target_path = target_root / source_path.name
        if not target_path.exists():
            try:
                _hardlink_import(
                    source_path,
                    target_path,
                    import_source_type_unsupported_text="成人资源源路径不是文件或目录，无法归档。",
                )
            except OSError:
                try:
                    _copy_import(
                        source_path,
                        target_path,
                        import_source_type_unsupported_text="成人资源源路径不是文件或目录，无法归档。",
                    )
                except OSError as error:
                    raise AdultArchiveOperationError(
                        f"adult archive transfer failed for {candidate.task_id}/{candidate.task_hash}: {error}"
                    ) from error

        try:
            self._job_event_repo.append_event(
                task_ref=candidate.task_hash,
                task_id=candidate.task_id,
                task_hash=candidate.task_hash,
                event_type="adult_archive.succeeded",
                message=str(target_path),
                source_path=str(source_path),
                target_path=str(target_path),
            )
            self._registry_repo.mark_archived_present(
                normalized_content_id=registry_record.normalized_content_id,
                archive_path=str(target_path),
                task_id=candidate.task_id,
                task_hash=candidate.task_hash,
            )
        except (AdultContentRegistryPersistenceError, JobEventPersistenceError, sqlite3.Error) as error:
            raise AdultArchiveStateUnavailableError(
                f"adult archive state persist failed for {candidate.task_id}/{candidate.task_hash}: {error}"
            ) from error
        return (
            f"成人资源归档成功：{registry_record.display_title or import_source.name}\n"
            f"任务 Hash: {candidate.task_hash}\n"
            f"归档路径: {target_path}"
        )

    async def _cleanup_retained_download(
        self,
        *,
        candidate: DownloadMonitorRecord,
        registry_record: AdultContentRegistryRecord,
    ) -> str | None:
        import_source = await self._get_import_source(candidate=candidate)
        if import_source is None:
            raise AdultArchiveStateUnavailableError(
                f"adult archive cleanup import source missing for {candidate.task_id}/{candidate.task_hash}"
            )
        source_path = Path(import_source.download_dir) / import_source.name
        try:
            await self._remove_torrent_func(candidate.task_hash, candidate.chat_id, True)
        except (httpx.HTTPError, OSError, ValueError) as error:
            raise AdultArchiveOperationError(
                f"adult archive cleanup downloader removal failed for {candidate.task_id}/{candidate.task_hash}: {error}"
            ) from error
        try:
            if source_path.exists():
                if source_path.is_dir():
                    shutil.rmtree(source_path)
                elif source_path.is_file():
                    source_path.unlink()
                else:
                    raise OSError("成人资源源路径不是文件或目录，无法清理。")
        except OSError as error:
            raise AdultArchiveOperationError(
                f"adult archive cleanup source removal failed for {candidate.task_id}/{candidate.task_hash}: {error}"
            ) from error
        try:
            self._job_event_repo.append_event(
                task_ref=candidate.task_hash,
                task_id=candidate.task_id,
                task_hash=candidate.task_hash,
                event_type="adult_archive.retention_cleanup_succeeded",
                message=registry_record.archive_path,
                source_path=str(source_path),
                target_path=registry_record.archive_path,
            )
            self._registry_repo.mark_archived_deleted(
                normalized_content_id=registry_record.normalized_content_id,
                archive_path=registry_record.archive_path,
                task_id=candidate.task_id,
                task_hash=candidate.task_hash,
            )
        except (AdultContentRegistryPersistenceError, JobEventPersistenceError, sqlite3.Error) as error:
            raise AdultArchiveStateUnavailableError(
                f"adult archive cleanup state persist failed for {candidate.task_id}/{candidate.task_hash}: {error}"
            ) from error
        return (
            f"成人资源保留期清理完成：{registry_record.display_title or import_source.name}\n"
            f"任务 Hash: {candidate.task_hash}\n"
            f"归档保留: {registry_record.archive_path or '-'}"
        )

    async def _get_import_source(self, *, candidate: DownloadMonitorRecord) -> TransmissionImportSource | None:
        import inspect
        try:
            params = inspect.signature(self._get_import_source_func).parameters
        except (ValueError, TypeError):
            return await self._get_import_source_func(candidate.task_hash, candidate.chat_id)
        if len(params) >= 3:
            return await self._get_import_source_func(candidate.task_hash, candidate.chat_id, None)
        return await self._get_import_source_func(candidate.task_hash, candidate.chat_id)

    def _retention_elapsed(self, candidate: DownloadMonitorRecord) -> bool:
        if self._retention_hours <= 0:
            return True
        completion_observed_at = candidate.completion_observed_at.strip()
        if not completion_observed_at:
            raise AdultArchiveStateUnavailableError(
                f"adult archive retention completion time missing for {candidate.task_id}/{candidate.task_hash}"
            )
        try:
            observed_at = datetime.strptime(completion_observed_at, _SQLITE_UTC_FORMAT).replace(tzinfo=UTC)
        except ValueError as error:
            raise AdultArchiveStateUnavailableError(
                f"adult archive retention completion time invalid for {candidate.task_id}/{candidate.task_hash}: {completion_observed_at}"
            ) from error
        return datetime.now(UTC) >= observed_at + timedelta(hours=self._retention_hours)

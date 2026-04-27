from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.clients.transmission import TransmissionImportSource
from app.config import AdultArchiveDestination
from app.db.adult_content_registry_repo import AdultContentRegistryPersistenceError, AdultContentRegistryRepo
from app.db.download_monitor_repo import DownloadMonitorRecord
from app.db.job_event_repo import JobEventRepo
from app.db.sqlite import SqliteDatabase
from app.services.adult_archive_service import AdultArchiveService, AdultArchiveStateUnavailableError


def test_adult_archive_service_hardlinks_completed_download_and_cleans_after_retention(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "adult.sqlite3"))
    database.initialize()
    registry_repo = AdultContentRegistryRepo(database)
    event_repo = JobEventRepo(database)

    source_dir = tmp_path / "downloads"
    source_dir.mkdir()
    source_file = source_dir / "SSIS-123.mp4"
    source_file.write_bytes(b"adult-video")
    archive_dir = tmp_path / "archive" / "censored"

    registry_repo.mark_downloading(
        normalized_content_id="censored:ssis-123",
        content_id_kind="censored",
        archive_category="censored",
        display_title="SSIS-123",
        latest_source_site="tokyotosho",
        task_ref="bt-ssis123",
        task_id="123",
        task_hash="hash-123",
        downloader_name="bt-main",
    )

    remove_calls: list[tuple[str, int | None, bool]] = []

    async def fake_get_import_source(task_ref: str, chat_id: int | None = None, user_id: int | None = None):
        _ = user_id
        assert task_ref == "hash-123"
        assert chat_id == 1001
        return TransmissionImportSource(
            task_id="123",
            task_hash="hash-123",
            name="SSIS-123.mp4",
            download_dir=str(source_dir),
            is_finished=True,
            percent_done=1.0,
        )

    async def fake_remove_torrent(task_ref: str, chat_id: int | None = None, delete_local_data: bool = True) -> None:
        remove_calls.append((task_ref, chat_id, delete_local_data))

    service = AdultArchiveService(
        get_import_source_func=fake_get_import_source,
        remove_torrent_func=fake_remove_torrent,
        registry_repo=registry_repo,
        job_event_repo=event_repo,
        archive_destinations=(
            AdultArchiveDestination(category="censored", label="有码", target_dir=str(archive_dir)),
        ),
        retention_hours=96,
    )

    completion_record = DownloadMonitorRecord(
        task_id="123",
        task_hash="hash-123",
        name="SSIS-123.mp4",
        chat_id=1001,
        user_id=2001,
        status_code=6,
        percent_done=1.0,
        is_complete=True,
        completion_observed_at="2026-04-26 00:00:00",
        last_observed_at="2026-04-26 00:00:00",
        created_at="2026-04-26 00:00:00",
        updated_at="2026-04-26 00:00:00",
    )

    archive_reply = asyncio.run(
        service.run_for_record(
            candidate=completion_record,
            registry_record=registry_repo.get_by_content_id(normalized_content_id="censored:ssis-123"),
        )
    )

    target_file = archive_dir / "SSIS-123.mp4"
    assert archive_reply is not None
    assert target_file.exists()
    assert source_file.exists()
    archived_record = registry_repo.get_by_content_id(normalized_content_id="censored:ssis-123")
    assert archived_record is not None
    assert archived_record.current_status == "archived_present"
    assert archived_record.archive_path == str(target_file)

    retained_record = DownloadMonitorRecord(
        task_id="123",
        task_hash="hash-123",
        name="SSIS-123.mp4",
        chat_id=1001,
        user_id=2001,
        status_code=6,
        percent_done=1.0,
        is_complete=True,
        completion_observed_at="2000-01-01 00:00:00",
        last_observed_at="2000-01-01 00:00:00",
        created_at="2000-01-01 00:00:00",
        updated_at="2000-01-01 00:00:00",
    )

    cleanup_reply = asyncio.run(
        service.run_for_record(
            candidate=retained_record,
            registry_record=registry_repo.get_by_content_id(normalized_content_id="censored:ssis-123"),
        )
    )

    assert cleanup_reply is not None
    assert remove_calls == [("hash-123", 1001, True)]
    assert source_file.exists() is False
    assert target_file.exists() is True
    cleaned_record = registry_repo.get_by_content_id(normalized_content_id="censored:ssis-123")
    assert cleaned_record is not None
    assert cleaned_record.current_status == "archived_deleted"
    events = event_repo.list_events_for_task_identity(task_id="123", task_hash="hash-123")
    assert [event.event_type for event in events] == [
        "adult_archive.succeeded",
        "adult_archive.retention_cleanup_succeeded",
    ]


def test_adult_archive_service_supports_two_arg_get_import_source(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "adult.sqlite3"))
    database.initialize()
    registry_repo = AdultContentRegistryRepo(database)
    event_repo = JobEventRepo(database)

    source_dir = tmp_path / "downloads"
    source_dir.mkdir()
    source_file = source_dir / "SSIS-123.mp4"
    source_file.write_bytes(b"adult-video")
    archive_dir = tmp_path / "archive" / "censored"

    registry_repo.mark_downloading(
        normalized_content_id="censored:ssis-123",
        content_id_kind="censored",
        archive_category="censored",
        display_title="SSIS-123",
        latest_source_site="tokyotosho",
        task_ref="bt-ssis123",
        task_id="123",
        task_hash="hash-123",
        downloader_name="bt-main",
    )

    async def fake_get_import_source(task_ref: str, chat_id: int | None = None):
        _ = chat_id
        assert task_ref == "hash-123"
        return TransmissionImportSource(
            task_id="123",
            task_hash="hash-123",
            name="SSIS-123.mp4",
            download_dir=str(source_dir),
            is_finished=True,
            percent_done=1.0,
        )

    async def fake_remove_torrent(task_ref: str, chat_id: int | None = None, delete_local_data: bool = True) -> None:
        _ = (task_ref, chat_id, delete_local_data)

    service = AdultArchiveService(
        get_import_source_func=fake_get_import_source,
        remove_torrent_func=fake_remove_torrent,
        registry_repo=registry_repo,
        job_event_repo=event_repo,
        archive_destinations=(
            AdultArchiveDestination(category="censored", label="有码", target_dir=str(archive_dir)),
        ),
        retention_hours=96,
    )

    completion_record = DownloadMonitorRecord(
        task_id="123",
        task_hash="hash-123",
        name="SSIS-123.mp4",
        chat_id=1001,
        user_id=2001,
        status_code=6,
        percent_done=1.0,
        is_complete=True,
        completion_observed_at="2026-04-26 00:00:00",
        last_observed_at="2026-04-26 00:00:00",
        created_at="2026-04-26 00:00:00",
        updated_at="2026-04-26 00:00:00",
    )

    archive_reply = asyncio.run(
        service.run_for_record(
            candidate=completion_record,
            registry_record=registry_repo.get_by_content_id(normalized_content_id="censored:ssis-123"),
        )
    )

    assert archive_reply is not None
    assert (archive_dir / "SSIS-123.mp4").exists()


def test_adult_archive_service_raises_state_unavailable_when_archive_registry_persist_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = SqliteDatabase(str(tmp_path / "adult.sqlite3"))
    database.initialize()
    registry_repo = AdultContentRegistryRepo(database)
    event_repo = JobEventRepo(database)
    source_dir = tmp_path / "downloads"
    source_dir.mkdir()
    source_file = source_dir / "SSIS-123.mp4"
    source_file.write_bytes(b"adult-video")
    archive_dir = tmp_path / "archive" / "censored"
    registry_repo.mark_downloading(
        normalized_content_id="censored:ssis-123",
        content_id_kind="censored",
        archive_category="censored",
        display_title="SSIS-123",
        latest_source_site="tokyotosho",
        task_ref="bt-ssis123",
        task_id="123",
        task_hash="hash-123",
        downloader_name="bt-main",
    )

    async def fake_get_import_source(task_ref: str, chat_id: int | None = None):
        _ = (task_ref, chat_id)
        return TransmissionImportSource(
            task_id="123",
            task_hash="hash-123",
            name="SSIS-123.mp4",
            download_dir=str(source_dir),
            is_finished=True,
            percent_done=1.0,
        )

    async def fake_remove_torrent(task_ref: str, chat_id: int | None = None, delete_local_data: bool = True) -> None:
        _ = (task_ref, chat_id, delete_local_data)

    def _raise_persist_error(**_: object) -> None:
        raise AdultContentRegistryPersistenceError("registry down")

    monkeypatch.setattr(registry_repo, "mark_archived_present", _raise_persist_error)
    service = AdultArchiveService(
        get_import_source_func=fake_get_import_source,
        remove_torrent_func=fake_remove_torrent,
        registry_repo=registry_repo,
        job_event_repo=event_repo,
        archive_destinations=(
            AdultArchiveDestination(category="censored", label="有码", target_dir=str(archive_dir)),
        ),
        retention_hours=96,
    )
    completion_record = DownloadMonitorRecord(
        task_id="123",
        task_hash="hash-123",
        name="SSIS-123.mp4",
        chat_id=1001,
        user_id=2001,
        status_code=6,
        percent_done=1.0,
        is_complete=True,
        completion_observed_at="2026-04-26 00:00:00",
        last_observed_at="2026-04-26 00:00:00",
        created_at="2026-04-26 00:00:00",
        updated_at="2026-04-26 00:00:00",
    )

    with pytest.raises(AdultArchiveStateUnavailableError, match="adult archive state persist failed"):
        asyncio.run(
            service.run_for_record(
                candidate=completion_record,
                registry_record=registry_repo.get_by_content_id(normalized_content_id="censored:ssis-123"),
            )
        )

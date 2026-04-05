from __future__ import annotations

from pathlib import Path

from app.db.job_event_repo import JobEventRepo
from app.db.sqlite import SqliteDatabase
from app.services.cleanup_downloaded_source import (
    CLEANUP_CORRELATION_MISSING_TEXT,
    CLEANUP_GUARD_REJECTED_TEXT,
    CLEANUP_QUERY_USAGE_TEXT,
    CLEANUP_TARGET_MISSING_TEXT,
    CleanupDownloadedSourceService,
    parse_cleanup_query,
)


def test_parse_cleanup_query_supports_prefixes() -> None:
    assert parse_cleanup_query("cleanup 87") == "87"
    assert parse_cleanup_query("CLEANUP hash-87") == "hash-87"
    assert parse_cleanup_query("清理 abc123") == "abc123"
    assert parse_cleanup_query("cleanup") == ""


def test_parse_cleanup_query_rejects_non_cleanup_text() -> None:
    assert parse_cleanup_query("import 87") is None
    assert parse_cleanup_query("dune") is None


def test_cleanup_by_task_ref_usage_when_empty(tmp_path: Path) -> None:
    service = CleanupDownloadedSourceService(JobEventRepo(_make_database(tmp_path)))
    assert service.cleanup_by_task_ref("  ") == CLEANUP_QUERY_USAGE_TEXT


def test_cleanup_by_task_ref_removes_source_file_and_keeps_target(tmp_path: Path) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    target_dir = tmp_path / "library"
    target_dir.mkdir(parents=True)
    target_file = target_dir / "Dune (2021).mkv"
    target_file.hardlink_to(source_file)

    database = _make_database(tmp_path)
    event_repo = JobEventRepo(database)
    event_repo.append_event(
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message=str(target_file),
        source_path=str(source_file),
        target_path=str(target_file),
    )
    service = CleanupDownloadedSourceService(event_repo)

    reply = service.cleanup_by_task_ref("87")

    assert "已清理下载源资产" in reply
    assert str(source_file) in reply
    assert not source_file.exists()
    assert target_file.exists()
    assert target_file.read_bytes() == b"demo"
    events = event_repo.list_events_for_task_identity(task_id="87", task_hash="hash-87")
    assert events[-1].event_type == "cleanup.succeeded"


def test_cleanup_by_task_ref_rejects_missing_structured_source_path(tmp_path: Path) -> None:
    target_dir = tmp_path / "library"
    target_dir.mkdir(parents=True)
    target_file = target_dir / "Dune (2021).mkv"
    target_file.write_bytes(b"demo")

    event_repo = JobEventRepo(_make_database(tmp_path))
    event_repo.append_event(
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message=str(target_file),
        target_path=str(target_file),
    )
    service = CleanupDownloadedSourceService(event_repo)

    reply = service.cleanup_by_task_ref("87")

    assert reply == CLEANUP_CORRELATION_MISSING_TEXT


def test_cleanup_by_task_ref_rejects_when_target_missing(tmp_path: Path) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    target_file = tmp_path / "library" / "Dune (2021).mkv"
    event_repo = JobEventRepo(_make_database(tmp_path))
    event_repo.append_event(
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message=str(target_file),
        source_path=str(source_file),
        target_path=str(target_file),
    )
    service = CleanupDownloadedSourceService(event_repo)

    reply = service.cleanup_by_task_ref("87")

    assert reply == CLEANUP_TARGET_MISSING_TEXT.format(target_path=str(target_file))
    assert source_file.exists()


def test_cleanup_by_task_ref_rejects_overlapping_source_and_target(tmp_path: Path) -> None:
    source_dir = tmp_path / "downloads" / "Dune.Part.Two.2024"
    source_dir.mkdir(parents=True)
    target_file = source_dir / "movie.mkv"
    target_file.write_bytes(b"demo")

    event_repo = JobEventRepo(_make_database(tmp_path))
    event_repo.append_event(
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.succeeded",
        message=str(target_file),
        source_path=str(source_dir),
        target_path=str(target_file),
    )
    service = CleanupDownloadedSourceService(event_repo)

    reply = service.cleanup_by_task_ref("87")

    assert reply == CLEANUP_GUARD_REJECTED_TEXT.format(
        source_path=str(source_dir),
        target_path=str(target_file),
    )
    assert source_dir.exists()


def _make_database(tmp_path: Path) -> SqliteDatabase:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    return database

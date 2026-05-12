from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.db.job_event_repo import JobEventPersistenceError, JobEventRepo
from app.db.sqlite import SqliteDatabase
from app.services.import_to_library import ImportToLibraryService
from app.services.media_identity import MEDIA_IDENTITY_EVENT_TYPE, media_identity_to_json


def _build_service(tmp_path: Path, *, job_event_repo: object | None = None) -> ImportToLibraryService:
    return ImportToLibraryService(
        get_import_source_func=AsyncMock(),
        library_target_dir=str(tmp_path / "library"),
        job_event_repo=job_event_repo,
    )


def test_import_confirmed_media_identity_resolver_reads_latest_media_identity(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    event_repo = JobEventRepo(database)
    event_repo.append_event(
        task_ref="1",
        task_id="task-1",
        task_hash="hash-1",
        event_type=MEDIA_IDENTITY_EVENT_TYPE,
        message=media_identity_to_json(
            {
                "title": "Dune",
                "original_title": "沙丘",
                "year": "2021",
                "tmdb_id": "12345",
            }
        ),
    )

    service = _build_service(tmp_path, job_event_repo=event_repo)

    media_identity = service._resolve_confirmed_media_identity(task_id="task-1", task_hash="hash-1")

    assert media_identity is not None
    assert media_identity["tmdb_id"] == "12345"
    assert service._resolve_confirmed_media_tmdb_id("task-1", "hash-1") == "12345"


def test_import_confirmed_media_identity_resolver_returns_none_without_events(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    event_repo = JobEventRepo(database)

    service = _build_service(tmp_path, job_event_repo=event_repo)

    assert service._resolve_confirmed_media_identity(task_id="task-1", task_hash="hash-1") is None
    assert service._resolve_confirmed_media_tmdb_id("task-1", "hash-1") == ""


def test_import_confirmed_media_identity_resolver_logs_persistence_failure(capsys) -> None:
    class FailingJobEventRepo:
        def list_events_for_task_identity(self, *, task_id: str, task_hash: str):
            raise JobEventPersistenceError("job_event down")

    service = ImportToLibraryService(  # type: ignore[arg-type]
        get_import_source_func=AsyncMock(),
        library_target_dir="library",
        job_event_repo=FailingJobEventRepo(),
    )

    assert service._resolve_confirmed_media_identity(task_id="task-1", task_hash="hash-1") is None
    output = capsys.readouterr().out
    assert "[导入媒体身份查询失败]" in output
    assert "job_event down" in output


def test_import_confirmed_media_identity_resolver_does_not_swallow_programming_errors() -> None:
    class BrokenJobEventRepo:
        def list_events_for_task_identity(self, *, task_id: str, task_hash: str):
            raise ValueError("bad fake")

    service = ImportToLibraryService(  # type: ignore[arg-type]
        get_import_source_func=AsyncMock(),
        library_target_dir="library",
        job_event_repo=BrokenJobEventRepo(),
    )

    with pytest.raises(ValueError, match="bad fake"):
        service._resolve_confirmed_media_identity(task_id="task-1", task_hash="hash-1")

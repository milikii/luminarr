from __future__ import annotations

from pathlib import Path

from app.db.job_event_repo import JobEventRepo
from app.db.sqlite import SqliteDatabase
from app.services.import_confirmed_media_identity import ImportConfirmedMediaIdentityResolver
from app.services.media_identity import MEDIA_IDENTITY_EVENT_TYPE, media_identity_to_json


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

    resolver = ImportConfirmedMediaIdentityResolver(job_event_repo=event_repo)

    media_identity = resolver.resolve(task_id="task-1", task_hash="hash-1")

    assert media_identity is not None
    assert media_identity["tmdb_id"] == "12345"
    assert resolver.resolve_tmdb_id("task-1", "hash-1") == "12345"


def test_import_confirmed_media_identity_resolver_returns_none_without_events(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    event_repo = JobEventRepo(database)

    resolver = ImportConfirmedMediaIdentityResolver(job_event_repo=event_repo)

    assert resolver.resolve(task_id="task-1", task_hash="hash-1") is None
    assert resolver.resolve_tmdb_id("task-1", "hash-1") == ""

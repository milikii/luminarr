from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock

from app.clients.transmission import TransmissionTask
from app.db.job_event_repo import JobEventRepo, JobEventPersistenceError
from app.db.sqlite import SqliteDatabase
from app.db.download_monitor_repo import DownloadMonitorPersistenceError
from app.services.add_execution_follow_up import AddExecutionFollowUpService
from app.services.add_pending_context import PendingAddContext
from app.services.media_identity import MEDIA_IDENTITY_EVENT_TYPE


def test_record_event_logs_persistence_failure(capsys) -> None:
    service = AddExecutionFollowUpService(
        add_torrent_func=AsyncMock(),
        job_event_repo=type(
            "JobEventRepo",
            (),
            {"append_event": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down"))},
        )(),
        download_monitor_repo=None,
        log_trace_func=lambda **kwargs: None,
        add_failed_text="下载投递失败，请稍后重试。",
        download_monitor_register_result_missing_reason="download monitor state missing after register",
    )

    service.record_event(
        task_ref="1",
        task_id="selection:1",
        task_hash="abc123",
        event_type="downloader.approval_pending",
        message="Dune: Part Two",
    )

    output = capsys.readouterr().out
    assert "[下载事件落盘失败]" in output
    assert "event_type=downloader.approval_pending" in output


def test_record_event_logs_missing_appended_event_result(capsys) -> None:
    service = AddExecutionFollowUpService(
        add_torrent_func=AsyncMock(),
        job_event_repo=type(
            "JobEventRepo",
            (),
            {"append_event": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("job_event missing after append"))},
        )(),
        download_monitor_repo=None,
        log_trace_func=lambda **kwargs: None,
        add_failed_text="下载投递失败，请稍后重试。",
        download_monitor_register_result_missing_reason="download monitor state missing after register",
    )

    service.record_event(
        task_ref="1",
        task_id="selection:1",
        task_hash="abc123",
        event_type="downloader.approval_pending",
        message="Dune: Part Two",
    )

    output = capsys.readouterr().out
    assert "[下载事件结果缺失]" in output
    assert "downloader event missing after append" in output
    assert "event_type=downloader.approval_pending" in output


def test_record_event_logs_row_corrupted_appended_event(capsys) -> None:
    service = AddExecutionFollowUpService(
        add_torrent_func=AsyncMock(),
        job_event_repo=type(
            "JobEventRepo",
            (),
            {
                "append_event": lambda self, **kwargs: (_ for _ in ()).throw(
                    JobEventPersistenceError("job_event row identity corrupted after read")
                )
            },
        )(),
        download_monitor_repo=None,
        log_trace_func=lambda **kwargs: None,
        add_failed_text="下载投递失败，请稍后重试。",
        download_monitor_register_result_missing_reason="download monitor state missing after register",
    )

    service.record_event(
        task_ref="1",
        task_id="selection:1",
        task_hash="abc123",
        event_type="downloader.approval_pending",
        message="Dune: Part Two",
    )

    output = capsys.readouterr().out
    assert "[下载事件记录损坏]" in output
    assert "job_event row identity corrupted after read" in output
    assert "event_type=downloader.approval_pending" in output


def test_register_download_monitor_logs_persistence_failure(capsys) -> None:
    service = AddExecutionFollowUpService(
        add_torrent_func=AsyncMock(),
        job_event_repo=None,
        download_monitor_repo=type(
            "DownloadMonitorRepo",
            (),
            {"register_download": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down"))},
        )(),
        log_trace_func=lambda **kwargs: None,
        add_failed_text="下载投递失败，请稍后重试。",
        download_monitor_register_result_missing_reason="download monitor state missing after register",
    )

    service.register_download_monitor(
        task_id="42",
        task_hash="abc123",
        title="Dune: Part Two",
        chat_id=1001,
        user_id=2001,
    )

    output = capsys.readouterr().out
    assert "[下载监控登记失败]" in output
    assert "task_id=42" in output


def test_register_download_monitor_logs_missing_registered_result(capsys) -> None:
    service = AddExecutionFollowUpService(
        add_torrent_func=AsyncMock(),
        job_event_repo=None,
        download_monitor_repo=type(
            "DownloadMonitorRepo",
            (),
            {
                "register_download": lambda self, **kwargs: (_ for _ in ()).throw(
                    RuntimeError("download monitor state missing after register")
                )
            },
        )(),
        log_trace_func=lambda **kwargs: None,
        add_failed_text="下载投递失败，请稍后重试。",
        download_monitor_register_result_missing_reason="download monitor state missing after register",
    )

    service.register_download_monitor(
        task_id="42",
        task_hash="abc123",
        title="Dune: Part Two",
        chat_id=1001,
        user_id=2001,
    )

    output = capsys.readouterr().out
    assert "[下载监控登记结果缺失]" in output
    assert "download monitor state missing after register" in output
    assert "task_id=42" in output


def test_register_download_monitor_logs_row_corrupted_result(capsys) -> None:
    service = AddExecutionFollowUpService(
        add_torrent_func=AsyncMock(),
        job_event_repo=None,
        download_monitor_repo=type(
            "DownloadMonitorRepo",
            (),
            {
                "register_download": lambda self, **kwargs: (_ for _ in ()).throw(
                    DownloadMonitorPersistenceError("download monitor row identity corrupted after read")
                )
            },
        )(),
        log_trace_func=lambda **kwargs: None,
        add_failed_text="下载投递失败，请稍后重试。",
        download_monitor_register_result_missing_reason="download monitor state missing after register",
    )

    service.register_download_monitor(
        task_id="42",
        task_hash="abc123",
        title="Dune: Part Two",
        chat_id=1001,
        user_id=2001,
    )

    output = capsys.readouterr().out
    assert "[下载监控登记记录损坏]" in output
    assert "download monitor row identity corrupted after read" in output
    assert "task_id=42" in output


def test_dispatch_records_confirmed_media_identity_event(tmp_path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    event_repo = JobEventRepo(database)
    service = AddExecutionFollowUpService(
        add_torrent_func=AsyncMock(return_value=TransmissionTask(task_id="42", task_hash="hash-42")),
        job_event_repo=event_repo,
        download_monitor_repo=None,
        log_trace_func=lambda **kwargs: None,
        add_failed_text="下载投递失败，请稍后重试。",
        download_monitor_register_result_missing_reason="download monitor state missing after register",
    )

    pending_add = PendingAddContext(
        task_ref="1",
        task_id="selection:1",
        task_hash="candidate:abc123",
        title="Interstellar",
        source="https://example.com/interstellar.torrent",
        media_identity={
            "media_type": "movie",
            "tmdb_id": "157336",
            "title": "Interstellar",
            "original_title": "Interstellar",
            "year": "2014",
            "source": "search_confirmed",
        },
    )

    outcome = asyncio.run(
        service.dispatch(
            task_ref="1",
            pending_add=pending_add,
            chat_id=1001,
            user_id=2001,
        )
    )

    assert outcome.result is not None
    events = event_repo.list_events_for_task_identity(task_id="42", task_hash="hash-42")
    assert [event.event_type for event in events] == ["downloader.succeeded", MEDIA_IDENTITY_EVENT_TYPE]
    assert json.loads(events[1].message) == pending_add.media_identity


def test_dispatch_registers_download_monitor_for_adult_candidate_even_without_auto_import() -> None:
    calls: list[tuple[str, str, str, int | None, int | None]] = []

    service = AddExecutionFollowUpService(
        add_torrent_func=AsyncMock(return_value=TransmissionTask(task_id="42", task_hash="hash-42")),
        job_event_repo=None,
        download_monitor_repo=type(
            "DownloadMonitorRepo",
            (),
            {
                "register_download": lambda self, **kwargs: calls.append(
                    (
                        kwargs["task_id"],
                        kwargs["task_hash"],
                        kwargs["name"],
                        kwargs["chat_id"],
                        kwargs["user_id"],
                    )
                )
            },
        )(),
        log_trace_func=lambda **kwargs: None,
        add_failed_text="下载投递失败，请稍后重试。",
        download_monitor_register_result_missing_reason="download monitor state missing after register",
    )

    pending_add = PendingAddContext(
        task_ref="1",
        task_id="selection:1",
        task_hash="candidate:abc123",
        title="SSIS-123",
        source="magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12",
        adult_content_id="censored:ssis-123",
        adult_archive_category="censored",
        adult_display_id="SSIS-123",
        auto_import_enabled=False,
    )

    outcome = asyncio.run(
        service.dispatch(
            task_ref="1",
            pending_add=pending_add,
            chat_id=1001,
            user_id=2001,
        )
    )

    assert outcome.result is not None
    assert calls == [("42", "hash-42", "SSIS-123", 1001, 2001)]

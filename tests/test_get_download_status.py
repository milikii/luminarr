from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.clients.transmission import TransmissionTaskStatus
from app.db.download_monitor_repo import DownloadMonitorPersistenceError, DownloadMonitorRepo
from app.db.job_event_repo import JobEventPersistenceError, JobEventRepo
from app.db.sqlite import SqliteDatabase
from app.services.get_download_status import (
    STATUS_AUTO_IMPORT_STATE_UNAVAILABLE_TEXT,
    STATUS_NOT_FOUND_TEXT,
    STATUS_QUERY_FAILED_TEXT,
    STATUS_QUERY_USAGE_TEXT,
    GetDownloadStatusService,
    parse_status_query,
)
from app.services.post_download_auto_import import (
    AUTO_IMPORT_SKIPPED_BY_RULE_EVENT,
    AutoImportStateUnavailableError,
    AutoImportRunResult,
    PostDownloadAutoImportService,
)


def test_parse_status_query_supports_status_prefix() -> None:
    assert parse_status_query("status 87") == "87"
    assert parse_status_query("STATUS abc123") == "abc123"
    assert parse_status_query("状态 b305bf") == "b305bf"
    assert parse_status_query("status") == ""


def test_parse_status_query_rejects_non_status_text() -> None:
    assert parse_status_query("dune") is None
    assert parse_status_query("1") is None


def test_get_status_text_success() -> None:
    get_status = AsyncMock(
        return_value=TransmissionTaskStatus(
            task_id="87",
            task_hash="b305bf",
            name="Dune 1984",
            status_code=4,
            percent_done=0.56,
            rate_download=1048576,
            eta_seconds=121,
        )
    )
    service = GetDownloadStatusService(get_status)

    text = _run(service.get_status_text("87"))
    assert "任务 ID: 87" in text
    assert "任务 Hash: b305bf" in text
    assert "状态: 下载中" in text
    assert "进度: 56.0%" in text
    assert "下载速度: 1.0 MB/s" in text
    assert "预计剩余: 02:01" in text


def test_get_status_text_not_found() -> None:
    service = GetDownloadStatusService(AsyncMock(return_value=None))
    text = _run(service.get_status_text("missing"))
    assert text == STATUS_NOT_FOUND_TEXT


def test_get_status_text_handles_query_error() -> None:
    service = GetDownloadStatusService(AsyncMock(side_effect=RuntimeError("boom")))
    text = _run(service.get_status_text("87"))
    assert text == STATUS_QUERY_FAILED_TEXT


def test_get_status_text_logs_query_error(capsys) -> None:
    service = GetDownloadStatusService(AsyncMock(side_effect=RuntimeError("boom")))

    text = _run(service.get_status_text("87", chat_id=1001))

    assert text == STATUS_QUERY_FAILED_TEXT
    output = capsys.readouterr().out
    assert "[下载状态查询失败]" in output
    assert "task_ref=87" in output


def test_get_status_text_handles_empty_ref() -> None:
    service = GetDownloadStatusService(AsyncMock())
    text = _run(service.get_status_text("   "))
    assert text == STATUS_QUERY_USAGE_TEXT


def test_get_status_text_updates_download_monitor_truth_and_completion_event(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    monitor_repo = DownloadMonitorRepo(database)
    event_repo = JobEventRepo(database)

    service = GetDownloadStatusService(
        AsyncMock(
            side_effect=[
                TransmissionTaskStatus(
                    task_id="87",
                    task_hash="hash-87",
                    name="Dune 1984",
                    status_code=4,
                    percent_done=0.5,
                    rate_download=1024,
                    eta_seconds=30,
                ),
                TransmissionTaskStatus(
                    task_id="87",
                    task_hash="hash-87",
                    name="Dune 1984",
                    status_code=6,
                    percent_done=1.0,
                    rate_download=0,
                    eta_seconds=-1,
                ),
            ]
        ),
        download_monitor_repo=monitor_repo,
        job_event_repo=event_repo,
    )

    first_text = _run(service.get_status_text("87"))
    assert "状态: 下载中" in first_text
    first_record = monitor_repo.get_record(task_id="87", task_hash="hash-87")
    assert first_record is not None
    assert first_record.is_complete is False
    assert len(monitor_repo.list_pending_completion()) == 1
    assert event_repo.list_events_for_task_identity(task_id="87", task_hash="hash-87") == []

    second_text = _run(service.get_status_text("87"))
    assert "状态: 做种中" in second_text
    second_record = monitor_repo.get_record(task_id="87", task_hash="hash-87")
    assert second_record is not None
    assert second_record.is_complete is True
    assert second_record.completion_observed_at
    assert monitor_repo.list_pending_completion() == []
    events = event_repo.list_events_for_task_identity(task_id="87", task_hash="hash-87")
    assert [event.event_type for event in events] == ["downloader.completed_observed"]


def test_get_status_text_logs_download_monitor_persistence_failure(capsys) -> None:
    monitor_repo = type(
        "BoomRepo",
        (),
        {
            "record_status": lambda self, task_status: (_ for _ in ()).throw(
                DownloadMonitorPersistenceError("download monitor task identity missing")
            )
        },
    )()
    service = GetDownloadStatusService(
        AsyncMock(
            return_value=TransmissionTaskStatus(
                task_id="87",
                task_hash="hash-87",
                name="Dune 1984",
                status_code=4,
                percent_done=0.5,
                rate_download=1024,
                eta_seconds=30,
            )
        ),
        download_monitor_repo=monitor_repo,
    )

    text = _run(service.get_status_text("87"))

    assert "状态: 下载中" in text
    assert "注意：下载状态观察落盘失败" in text
    output = capsys.readouterr().out
    assert "[下载状态观察落盘失败]" in output
    assert "download monitor task identity missing" in output


def test_get_status_text_warns_when_download_monitor_returns_missing_update(capsys) -> None:
    monitor_repo = type(
        "MissingUpdateRepo",
        (),
        {"record_status": lambda self, task_status: None},
    )()
    service = GetDownloadStatusService(
        AsyncMock(
            return_value=TransmissionTaskStatus(
                task_id="87",
                task_hash="hash-87",
                name="Dune 1984",
                status_code=4,
                percent_done=0.5,
                rate_download=1024,
                eta_seconds=30,
            )
        ),
        download_monitor_repo=monitor_repo,
    )

    text = _run(service.get_status_text("87"))

    assert "状态: 下载中" in text
    assert "注意：下载状态观察落盘失败" in text
    output = capsys.readouterr().out
    assert "[下载状态观察结果缺失]" in output
    assert "download monitor status result missing" in output
    assert "[处理建议]" in output


def test_get_status_text_warns_when_download_monitor_status_upsert_result_is_missing(capsys) -> None:
    monitor_repo = type(
        "MissingUpsertResultRepo",
        (),
        {
            "record_status": lambda self, task_status: (_ for _ in ()).throw(
                DownloadMonitorPersistenceError("download monitor state missing after status upsert")
            )
        },
    )()
    service = GetDownloadStatusService(
        AsyncMock(
            return_value=TransmissionTaskStatus(
                task_id="87",
                task_hash="hash-87",
                name="Dune 1984",
                status_code=4,
                percent_done=0.5,
                rate_download=1024,
                eta_seconds=30,
            )
        ),
        download_monitor_repo=monitor_repo,
    )

    text = _run(service.get_status_text("87"))

    assert "状态: 下载中" in text
    assert "注意：下载状态观察落盘失败" in text
    output = capsys.readouterr().out
    assert "[下载状态观察结果缺失]" in output
    assert "download monitor state missing after status upsert" in output
    assert "[处理建议]" in output


def test_get_status_text_warns_when_download_monitor_returns_missing_record(capsys) -> None:
    monitor_repo = type(
        "MissingRecordRepo",
        (),
        {
            "record_status": lambda self, task_status: type(
                "Update",
                (),
                {
                    "newly_completed": False,
                    "record": None,
                },
            )()
        },
    )()
    service = GetDownloadStatusService(
        AsyncMock(
            return_value=TransmissionTaskStatus(
                task_id="87",
                task_hash="hash-87",
                name="Dune 1984",
                status_code=4,
                percent_done=0.5,
                rate_download=1024,
                eta_seconds=30,
            )
        ),
        download_monitor_repo=monitor_repo,
        post_download_auto_import_service=type("AutoImport", (), {"run_for_record": AsyncMock()})(),
    )

    text = _run(service.get_status_text("87"))

    assert "状态: 下载中" in text
    assert "注意：下载状态观察落盘失败" in text
    output = capsys.readouterr().out
    assert "[下载状态观察结果缺失]" in output
    assert "download monitor observed record missing" in output
    assert "[处理建议]" in output


def test_get_status_text_warns_when_download_monitor_returns_missing_completion_flag(capsys) -> None:
    monitor_repo = type(
        "MissingCompletionRepo",
        (),
        {
            "record_status": lambda self, task_status: type(
                "Update",
                (),
                {
                    "record": type(
                        "Record",
                        (),
                        {
                            "task_id": "87",
                            "task_hash": "hash-87",
                            "name": "Dune 1984",
                            "chat_id": 1001,
                            "user_id": 2001,
                        },
                    )(),
                },
            )()
        },
    )()
    service = GetDownloadStatusService(
        AsyncMock(
            return_value=TransmissionTaskStatus(
                task_id="87",
                task_hash="hash-87",
                name="Dune 1984",
                status_code=4,
                percent_done=0.5,
                rate_download=1024,
                eta_seconds=30,
            )
        ),
        download_monitor_repo=monitor_repo,
    )

    text = _run(service.get_status_text("87"))

    assert "状态: 下载中" in text
    assert "注意：下载状态观察落盘失败" in text
    output = capsys.readouterr().out
    assert "[下载状态观察完成标记缺失]" in output
    assert "download monitor completion flag missing" in output
    assert "[处理建议]" in output


def test_get_status_text_warns_when_completion_event_write_fails(capsys) -> None:
    monitor_repo = type(
        "MonitorRepo",
        (),
        {
            "record_status": lambda self, task_status: type(
                "Update",
                (),
                {
                    "newly_completed": True,
                    "record": type(
                        "Record",
                        (),
                        {
                            "task_id": "87",
                            "task_hash": "hash-87",
                            "name": "Dune 1984",
                            "chat_id": 1001,
                            "user_id": 2001,
                        },
                    )(),
                },
            )()
        },
    )()
    event_repo = type(
        "BoomEventRepo",
        (),
        {"append_event": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down"))},
    )()
    service = GetDownloadStatusService(
        AsyncMock(
            return_value=TransmissionTaskStatus(
                task_id="87",
                task_hash="hash-87",
                name="Dune 1984",
                status_code=6,
                percent_done=1.0,
                rate_download=0,
                eta_seconds=-1,
            )
        ),
        download_monitor_repo=monitor_repo,
        job_event_repo=event_repo,
    )

    text = _run(service.get_status_text("87"))

    assert "状态: 做种中" in text
    assert "注意：下载完成观察事件落盘失败" in text
    output = capsys.readouterr().out
    assert "[下载完成观察事件落盘失败]" in output
    assert "event_type=downloader.completed_observed" in output
    assert "db down" in output


def test_get_status_text_warns_when_completion_event_result_is_missing(capsys) -> None:
    monitor_repo = type(
        "MonitorRepo",
        (),
        {
            "record_status": lambda self, task_status: type(
                "Update",
                (),
                {
                    "newly_completed": True,
                    "record": type(
                        "Record",
                        (),
                        {
                            "task_id": "87",
                            "task_hash": "hash-87",
                            "name": "Dune 1984",
                            "chat_id": 1001,
                            "user_id": 2001,
                        },
                    )(),
                },
            )()
        },
    )()
    event_repo = type(
        "MissingEventRepo",
        (),
        {
            "append_event": lambda self, **kwargs: (_ for _ in ()).throw(
                RuntimeError("job_event missing after append")
            )
        },
    )()
    service = GetDownloadStatusService(
        AsyncMock(
            return_value=TransmissionTaskStatus(
                task_id="87",
                task_hash="hash-87",
                name="Dune 1984",
                status_code=6,
                percent_done=1.0,
                rate_download=0,
                eta_seconds=-1,
            )
        ),
        download_monitor_repo=monitor_repo,
        job_event_repo=event_repo,
    )

    text = _run(service.get_status_text("87"))

    assert "状态: 做种中" in text
    assert "注意：下载完成观察事件落盘失败" in text
    output = capsys.readouterr().out
    assert "[下载完成观察事件结果缺失]" in output
    assert "event_type=downloader.completed_observed" in output
    assert "job_event missing after append" in output


def test_get_download_status_service_exposes_download_monitor_repo(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    monitor_repo = DownloadMonitorRepo(database)
    service = GetDownloadStatusService(AsyncMock(), download_monitor_repo=monitor_repo)
    assert service.download_monitor_repo is monitor_repo


def test_get_status_text_progresses_completed_download_to_auto_import_pending(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    monitor_repo = DownloadMonitorRepo(database)
    monitor_repo.register_download(
        task_id="87",
        task_hash="hash-87",
        name="Dune 1984",
        chat_id=1001,
        user_id=2001,
    )
    event_repo = JobEventRepo(database)
    auto_import = AsyncMock(return_value="导入待确认：Dune 1984\n请发送 confirm hash-87 执行导入。")
    auto_import_service = PostDownloadAutoImportService(
        download_monitor_repo=monitor_repo,
        job_event_repo=event_repo,
        auto_import_func=auto_import,
    )
    service = GetDownloadStatusService(
        AsyncMock(
            return_value=TransmissionTaskStatus(
                task_id="87",
                task_hash="hash-87",
                name="Dune 1984",
                status_code=6,
                percent_done=1.0,
                rate_download=0,
                eta_seconds=-1,
            )
        ),
        download_monitor_repo=monitor_repo,
        job_event_repo=event_repo,
        post_download_auto_import_service=auto_import_service,
    )

    text = _run(service.get_status_text("87"))

    assert "状态: 做种中" in text
    assert "导入待确认：Dune 1984" in text
    auto_import.assert_awaited_once_with("hash-87", 1001, 2001)


def test_get_status_text_does_not_repeat_auto_import_when_import_activity_exists(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    monitor_repo = DownloadMonitorRepo(database)
    monitor_repo.register_download(
        task_id="87",
        task_hash="hash-87",
        name="Dune 1984",
        chat_id=1001,
        user_id=2001,
    )
    monitor_repo.record_status(
        TransmissionTaskStatus(
            task_id="87",
            task_hash="hash-87",
            name="Dune 1984",
            status_code=6,
            percent_done=1.0,
            rate_download=0,
            eta_seconds=-1,
        )
    )
    event_repo = JobEventRepo(database)
    event_repo.append_event(
        task_ref="hash-87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.approval_pending",
        message="already pending",
    )
    auto_import = AsyncMock(return_value="不应走到这里")
    auto_import_service = PostDownloadAutoImportService(
        download_monitor_repo=monitor_repo,
        job_event_repo=event_repo,
        auto_import_func=auto_import,
    )
    service = GetDownloadStatusService(
        AsyncMock(
            return_value=TransmissionTaskStatus(
                task_id="87",
                task_hash="hash-87",
                name="Dune 1984",
                status_code=6,
                percent_done=1.0,
                rate_download=0,
                eta_seconds=-1,
            )
        ),
        download_monitor_repo=monitor_repo,
        job_event_repo=event_repo,
        post_download_auto_import_service=auto_import_service,
    )

    text = _run(service.get_status_text("87"))

    assert "状态: 做种中" in text
    assert "导入待确认" not in text
    auto_import.assert_not_awaited()


def test_get_status_text_stops_auto_import_when_terminal_lookup_fails(
    tmp_path: Path,
    capsys,
) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    monitor_repo = DownloadMonitorRepo(database)
    monitor_repo.register_download(
        task_id="87",
        task_hash="hash-87",
        name="Dune 1984",
        chat_id=1001,
        user_id=2001,
    )
    event_repo = type(
        "BoomEventRepo",
        (),
        {"list_events_for_task_identity": lambda self, *, task_id, task_hash: (_ for _ in ()).throw(RuntimeError("db down"))},
    )()
    auto_import = AsyncMock(return_value="不应走到这里")
    auto_import_service = PostDownloadAutoImportService(
        download_monitor_repo=monitor_repo,
        job_event_repo=event_repo,
        auto_import_func=auto_import,
    )
    service = GetDownloadStatusService(
        AsyncMock(
            return_value=TransmissionTaskStatus(
                task_id="87",
                task_hash="hash-87",
                name="Dune 1984",
                status_code=6,
                percent_done=1.0,
                rate_download=0,
                eta_seconds=-1,
            )
        ),
        download_monitor_repo=monitor_repo,
        job_event_repo=None,
        post_download_auto_import_service=auto_import_service,
    )

    text = _run(service.get_status_text("87"))

    assert "状态: 做种中" in text
    assert "导入待确认" not in text
    assert STATUS_AUTO_IMPORT_STATE_UNAVAILABLE_TEXT in text
    auto_import.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[自动导入终态查询失败]" in output
    assert "[下载状态自动导入状态读取失败]" in output
    assert "task_id=87" in output
    assert "db down" in output


def test_post_download_auto_import_run_once_skips_record_when_terminal_lookup_fails(capsys) -> None:
    candidate = type(
        "Record",
        (),
        {
            "task_id": "87",
            "task_hash": "hash-87",
            "name": "Dune 2024 1080p WEB-DL",
            "chat_id": 1001,
            "user_id": 2001,
            "status_code": 6,
            "percent_done": 1.0,
            "is_complete": True,
            "completion_observed_at": "2026-04-15T00:00:00+00:00",
            "last_observed_at": "2026-04-15T00:00:00+00:00",
            "created_at": "2026-04-15T00:00:00+00:00",
            "updated_at": "2026-04-15T00:00:00+00:00",
        },
    )()
    monitor_repo = type("MonitorRepo", (), {"list_completed_for_auto_import": lambda self, *, limit: [candidate]})()
    event_repo = type(
        "BoomEventRepo",
        (),
        {"list_events_for_task_identity": lambda self, *, task_id, task_hash: (_ for _ in ()).throw(RuntimeError("db down"))},
    )()
    auto_import = AsyncMock(return_value="不应走到这里")
    auto_import_service = PostDownloadAutoImportService(
        download_monitor_repo=monitor_repo,
        job_event_repo=event_repo,
        auto_import_func=auto_import,
    )

    result = asyncio.run(auto_import_service.run_once(limit=5))

    assert result == AutoImportRunResult(scanned=1, progressed=0, replies=(), state_unavailable=True)
    auto_import.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[自动导入终态查询失败]" in output
    assert "task_id=87" in output
    assert "db down" in output


def test_post_download_auto_import_run_once_surfaces_terminal_row_corruption(capsys) -> None:
    candidate = type(
        "Record",
        (),
        {
            "task_id": "87",
            "task_hash": "hash-87",
            "name": "Dune 2024 1080p WEB-DL",
            "chat_id": 1001,
            "user_id": 2001,
            "status_code": 6,
            "percent_done": 1.0,
            "is_complete": True,
            "completion_observed_at": "2026-04-15T00:00:00+00:00",
            "last_observed_at": "2026-04-15T00:00:00+00:00",
            "created_at": "2026-04-15T00:00:00+00:00",
            "updated_at": "2026-04-15T00:00:00+00:00",
        },
    )()
    monitor_repo = type("MonitorRepo", (), {"list_completed_for_auto_import": lambda self, *, limit: [candidate]})()
    event_repo = type(
        "CorruptedEventRepo",
        (),
        {
            "list_events_for_task_identity": lambda self, *, task_id, task_hash: (_ for _ in ()).throw(
                JobEventPersistenceError("job_event row identity corrupted after read")
            )
        },
    )()
    auto_import = AsyncMock(return_value="不应走到这里")
    auto_import_service = PostDownloadAutoImportService(
        download_monitor_repo=monitor_repo,
        job_event_repo=event_repo,
        auto_import_func=auto_import,
    )

    result = asyncio.run(auto_import_service.run_once(limit=5))

    assert result == AutoImportRunResult(scanned=1, progressed=0, replies=(), state_unavailable=True)
    auto_import.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[自动导入终态记录损坏]" in output
    assert "job_event row identity corrupted after read" in output
    assert "[处理建议]" in output


def test_post_download_auto_import_run_once_skips_record_when_terminal_lookup_returns_none(capsys) -> None:
    candidate = type(
        "Record",
        (),
        {
            "task_id": "87",
            "task_hash": "hash-87",
            "name": "Dune 2024 1080p WEB-DL",
            "chat_id": 1001,
            "user_id": 2001,
            "status_code": 6,
            "percent_done": 1.0,
            "is_complete": True,
            "completion_observed_at": "2026-04-15T00:00:00+00:00",
            "last_observed_at": "2026-04-15T00:00:00+00:00",
            "created_at": "2026-04-15T00:00:00+00:00",
            "updated_at": "2026-04-15T00:00:00+00:00",
        },
    )()
    monitor_repo = type("MonitorRepo", (), {"list_completed_for_auto_import": lambda self, *, limit: [candidate]})()
    event_repo = type(
        "MissingEventRepo",
        (),
        {"list_events_for_task_identity": lambda self, *, task_id, task_hash: None},
    )()
    auto_import = AsyncMock(return_value="不应走到这里")
    auto_import_service = PostDownloadAutoImportService(
        download_monitor_repo=monitor_repo,
        job_event_repo=event_repo,
        auto_import_func=auto_import,
    )

    result = asyncio.run(auto_import_service.run_once(limit=5))

    assert result == AutoImportRunResult(scanned=1, progressed=0, replies=(), state_unavailable=True)
    auto_import.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[自动导入终态结果缺失]" in output
    assert "task_id=87" in output
    assert "auto import terminal lookup result missing" in output
    assert "[处理建议]" in output


def test_get_status_text_skips_low_quality_resource_auto_import_and_records_event(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    monitor_repo = DownloadMonitorRepo(database)
    monitor_repo.register_download(
        task_id="87",
        task_hash="hash-87",
        name="Dune 2024 CAM",
        chat_id=1001,
        user_id=2001,
    )
    event_repo = JobEventRepo(database)
    auto_import = AsyncMock(return_value="不应走到这里")
    auto_import_service = PostDownloadAutoImportService(
        download_monitor_repo=monitor_repo,
        job_event_repo=event_repo,
        auto_import_func=auto_import,
    )
    service = GetDownloadStatusService(
        AsyncMock(
            return_value=TransmissionTaskStatus(
                task_id="87",
                task_hash="hash-87",
                name="Dune 2024 CAM",
                status_code=6,
                percent_done=1.0,
                rate_download=0,
                eta_seconds=-1,
            )
        ),
        download_monitor_repo=monitor_repo,
        job_event_repo=event_repo,
        post_download_auto_import_service=auto_import_service,
    )

    text = _run(service.get_status_text("87"))

    assert "状态: 做种中" in text
    assert "资源自动规则已跳过自动导入：Dune 2024 CAM" in text
    assert "命中低质量来源标记 CAM" in text
    assert "import hash-87" in text
    auto_import.assert_not_awaited()
    events = event_repo.list_events_for_task_identity(task_id="87", task_hash="hash-87")
    assert [event.event_type for event in events] == [
        "downloader.completed_observed",
        AUTO_IMPORT_SKIPPED_BY_RULE_EVENT,
    ]


def test_get_status_text_does_not_repeat_rule_skip_when_skip_event_exists(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    monitor_repo = DownloadMonitorRepo(database)
    monitor_repo.register_download(
        task_id="87",
        task_hash="hash-87",
        name="Dune 2024 CAM",
        chat_id=1001,
        user_id=2001,
    )
    monitor_repo.record_status(
        TransmissionTaskStatus(
            task_id="87",
            task_hash="hash-87",
            name="Dune 2024 CAM",
            status_code=6,
            percent_done=1.0,
            rate_download=0,
            eta_seconds=-1,
        )
    )
    event_repo = JobEventRepo(database)
    event_repo.append_event(
        task_ref="hash-87",
        task_id="87",
        task_hash="hash-87",
        event_type=AUTO_IMPORT_SKIPPED_BY_RULE_EVENT,
        message="CAM",
    )
    auto_import = AsyncMock(return_value="不应走到这里")
    auto_import_service = PostDownloadAutoImportService(
        download_monitor_repo=monitor_repo,
        job_event_repo=event_repo,
        auto_import_func=auto_import,
    )
    service = GetDownloadStatusService(
        AsyncMock(
            return_value=TransmissionTaskStatus(
                task_id="87",
                task_hash="hash-87",
                name="Dune 2024 CAM",
                status_code=6,
                percent_done=1.0,
                rate_download=0,
                eta_seconds=-1,
            )
        ),
        download_monitor_repo=monitor_repo,
        job_event_repo=event_repo,
        post_download_auto_import_service=auto_import_service,
    )

    text = _run(service.get_status_text("87"))

    assert "状态: 做种中" in text
    assert "资源自动规则已跳过自动导入" not in text
    auto_import.assert_not_awaited()


def test_get_status_text_returns_state_unavailable_when_skip_event_write_fails(
    tmp_path: Path, capsys
) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    monitor_repo = DownloadMonitorRepo(database)
    monitor_repo.register_download(
        task_id="87",
        task_hash="hash-87",
        name="Dune 2024 CAM",
        chat_id=1001,
        user_id=2001,
    )
    event_repo = JobEventRepo(database)
    auto_import = AsyncMock(return_value="不应走到这里")
    auto_import_service = PostDownloadAutoImportService(
        download_monitor_repo=monitor_repo,
        job_event_repo=type(
            "BoomSkipEventRepo",
            (),
            {
                "list_events_for_task_identity": lambda self, *, task_id, task_hash: [],
                "append_event": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down")),
            },
        )(),
        auto_import_func=auto_import,
    )
    service = GetDownloadStatusService(
        AsyncMock(
            return_value=TransmissionTaskStatus(
                task_id="87",
                task_hash="hash-87",
                name="Dune 2024 CAM",
                status_code=6,
                percent_done=1.0,
                rate_download=0,
                eta_seconds=-1,
            )
        ),
        download_monitor_repo=monitor_repo,
        job_event_repo=event_repo,
        post_download_auto_import_service=auto_import_service,
    )

    text = _run(service.get_status_text("87"))

    assert "状态: 做种中" in text
    assert STATUS_AUTO_IMPORT_STATE_UNAVAILABLE_TEXT in text
    assert "资源自动规则已跳过自动导入" not in text
    auto_import.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[自动导入跳过事件落盘失败]" in output
    assert "[下载状态自动导入状态读取失败]" in output


def test_get_status_text_returns_state_unavailable_when_skip_event_result_is_missing(
    tmp_path: Path, capsys
) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    monitor_repo = DownloadMonitorRepo(database)
    monitor_repo.register_download(
        task_id="87",
        task_hash="hash-87",
        name="Dune 2024 CAM",
        chat_id=1001,
        user_id=2001,
    )
    event_repo = JobEventRepo(database)
    auto_import = AsyncMock(return_value="不应走到这里")
    auto_import_service = PostDownloadAutoImportService(
        download_monitor_repo=monitor_repo,
        job_event_repo=type(
            "MissingSkipEventRepo",
            (),
            {
                "list_events_for_task_identity": lambda self, *, task_id, task_hash: [],
                "append_event": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("job_event missing after append")),
            },
        )(),
        auto_import_func=auto_import,
    )
    service = GetDownloadStatusService(
        AsyncMock(
            return_value=TransmissionTaskStatus(
                task_id="87",
                task_hash="hash-87",
                name="Dune 2024 CAM",
                status_code=6,
                percent_done=1.0,
                rate_download=0,
                eta_seconds=-1,
            )
        ),
        download_monitor_repo=monitor_repo,
        job_event_repo=event_repo,
        post_download_auto_import_service=auto_import_service,
    )

    text = _run(service.get_status_text("87"))

    assert "状态: 做种中" in text
    assert STATUS_AUTO_IMPORT_STATE_UNAVAILABLE_TEXT in text
    assert "资源自动规则已跳过自动导入" not in text
    auto_import.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[自动导入跳过事件结果缺失]" in output
    assert "auto import skip event missing after append" in output
    assert "[下载状态自动导入状态读取失败]" in output


def test_post_download_auto_import_run_once_counts_only_real_progress(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    monitor_repo = DownloadMonitorRepo(database)
    monitor_repo.register_download(
        task_id="87",
        task_hash="hash-87",
        name="Dune 2024 1080p WEB-DL",
        chat_id=1001,
        user_id=2001,
    )
    monitor_repo.register_download(
        task_id="88",
        task_hash="hash-88",
        name="Dune 2024 CAM",
        chat_id=1001,
        user_id=2001,
    )
    monitor_repo.record_status(
        TransmissionTaskStatus(
            task_id="87",
            task_hash="hash-87",
            name="Dune 2024 1080p WEB-DL",
            status_code=6,
            percent_done=1.0,
            rate_download=0,
            eta_seconds=-1,
        )
    )
    monitor_repo.record_status(
        TransmissionTaskStatus(
            task_id="88",
            task_hash="hash-88",
            name="Dune 2024 CAM",
            status_code=6,
            percent_done=1.0,
            rate_download=0,
            eta_seconds=-1,
        )
    )
    auto_import = AsyncMock(return_value="导入待确认：Dune 2024 1080p WEB-DL")
    auto_import_service = PostDownloadAutoImportService(
        download_monitor_repo=monitor_repo,
        job_event_repo=JobEventRepo(database),
        auto_import_func=auto_import,
    )

    result = asyncio.run(auto_import_service.run_once())

    assert result.scanned == 2
    assert result.progressed == 1
    assert len(result.replies) == 2
    auto_import.assert_awaited_once_with("hash-87", 1001, 2001)


def test_post_download_auto_import_run_once_marks_state_unavailable_when_skip_event_write_fails(
    tmp_path: Path, capsys
) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    monitor_repo = DownloadMonitorRepo(database)
    monitor_repo.register_download(
        task_id="87",
        task_hash="hash-87",
        name="Dune 2024 CAM",
        chat_id=1001,
        user_id=2001,
    )
    monitor_repo.record_status(
        TransmissionTaskStatus(
            task_id="87",
            task_hash="hash-87",
            name="Dune 2024 CAM",
            status_code=6,
            percent_done=1.0,
            rate_download=0,
            eta_seconds=-1,
        )
    )
    auto_import = AsyncMock(return_value="不应走到这里")
    auto_import_service = PostDownloadAutoImportService(
        download_monitor_repo=monitor_repo,
        job_event_repo=type(
            "BoomSkipEventRepo",
            (),
            {
                "list_events_for_task_identity": lambda self, *, task_id, task_hash: [],
                "append_event": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down")),
            },
        )(),
        auto_import_func=auto_import,
    )

    result = asyncio.run(auto_import_service.run_once(limit=5))

    assert result == AutoImportRunResult(scanned=1, progressed=0, replies=(), state_unavailable=True)
    auto_import.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[自动导入跳过事件落盘失败]" in output
    assert "task_id=87" in output
    assert "db down" in output


def test_post_download_auto_import_run_once_marks_state_unavailable_when_skip_event_result_is_missing(
    tmp_path: Path, capsys
) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    monitor_repo = DownloadMonitorRepo(database)
    monitor_repo.register_download(
        task_id="87",
        task_hash="hash-87",
        name="Dune 2024 CAM",
        chat_id=1001,
        user_id=2001,
    )
    monitor_repo.record_status(
        TransmissionTaskStatus(
            task_id="87",
            task_hash="hash-87",
            name="Dune 2024 CAM",
            status_code=6,
            percent_done=1.0,
            rate_download=0,
            eta_seconds=-1,
        )
    )
    auto_import = AsyncMock(return_value="不应走到这里")
    auto_import_service = PostDownloadAutoImportService(
        download_monitor_repo=monitor_repo,
        job_event_repo=type(
            "MissingSkipEventRepo",
            (),
            {
                "list_events_for_task_identity": lambda self, *, task_id, task_hash: [],
                "append_event": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("job_event missing after append")),
            },
        )(),
        auto_import_func=auto_import,
    )

    result = asyncio.run(auto_import_service.run_once(limit=5))

    assert result == AutoImportRunResult(scanned=1, progressed=0, replies=(), state_unavailable=True)
    auto_import.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[自动导入跳过事件结果缺失]" in output
    assert "task_id=87" in output
    assert "auto import skip event missing after append" in output


def test_post_download_auto_import_run_for_record_logs_invalid_chat_identity(capsys) -> None:
    auto_import_service = PostDownloadAutoImportService(
        download_monitor_repo=None,
        job_event_repo=type("EventRepo", (), {"list_events_for_task_identity": lambda self, **kwargs: []})(),
        auto_import_func=AsyncMock(return_value="AUTO IMPORT"),
    )
    record = type(
        "Record",
        (),
        {
            "task_id": "87",
            "task_hash": "hash-87",
            "name": "Dune 2024 1080p WEB-DL",
            "chat_id": 0,
            "user_id": 2001,
            "status_code": 6,
            "percent_done": 1.0,
            "is_complete": True,
            "completion_observed_at": "2026-04-15T00:00:00+00:00",
            "last_observed_at": "2026-04-15T00:00:00+00:00",
            "created_at": "2026-04-15T00:00:00+00:00",
            "updated_at": "2026-04-15T00:00:00+00:00",
        },
    )()

    with pytest.raises(AutoImportStateUnavailableError):
        asyncio.run(auto_import_service.run_for_record(record))
    output = capsys.readouterr().out
    assert "[自动导入聊天身份无效]" in output
    assert "chat_id=0" in output


def test_post_download_auto_import_run_for_record_raises_when_skip_event_write_fails(capsys) -> None:
    auto_import = AsyncMock(return_value="不应走到这里")
    auto_import_service = PostDownloadAutoImportService(
        download_monitor_repo=None,
        job_event_repo=type(
            "BoomSkipEventRepo",
            (),
            {
                "list_events_for_task_identity": lambda self, **kwargs: [],
                "append_event": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down")),
            },
        )(),
        auto_import_func=auto_import,
    )
    record = type(
        "Record",
        (),
        {
            "task_id": "87",
            "task_hash": "hash-87",
            "name": "Dune 2024 CAM",
            "chat_id": 1001,
            "user_id": 2001,
            "status_code": 6,
            "percent_done": 1.0,
            "is_complete": True,
            "completion_observed_at": "2026-04-15T00:00:00+00:00",
            "last_observed_at": "2026-04-15T00:00:00+00:00",
            "created_at": "2026-04-15T00:00:00+00:00",
            "updated_at": "2026-04-15T00:00:00+00:00",
        },
    )()

    with pytest.raises(AutoImportStateUnavailableError):
        asyncio.run(auto_import_service.run_for_record(record))

    auto_import.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[自动导入跳过事件落盘失败]" in output
    assert "task_id=87" in output
    assert "db down" in output


def test_post_download_auto_import_run_for_record_raises_when_skip_event_result_is_missing(capsys) -> None:
    auto_import = AsyncMock(return_value="不应走到这里")
    auto_import_service = PostDownloadAutoImportService(
        download_monitor_repo=None,
        job_event_repo=type(
            "MissingSkipEventRepo",
            (),
            {
                "list_events_for_task_identity": lambda self, **kwargs: [],
                "append_event": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("job_event missing after append")),
            },
        )(),
        auto_import_func=auto_import,
    )
    record = type(
        "Record",
        (),
        {
            "task_id": "87",
            "task_hash": "hash-87",
            "name": "Dune 2024 CAM",
            "chat_id": 1001,
            "user_id": 2001,
            "status_code": 6,
            "percent_done": 1.0,
            "is_complete": True,
            "completion_observed_at": "2026-04-15T00:00:00+00:00",
            "last_observed_at": "2026-04-15T00:00:00+00:00",
            "created_at": "2026-04-15T00:00:00+00:00",
            "updated_at": "2026-04-15T00:00:00+00:00",
        },
    )()

    with pytest.raises(AutoImportStateUnavailableError):
        asyncio.run(auto_import_service.run_for_record(record))

    auto_import.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[自动导入跳过事件结果缺失]" in output
    assert "task_id=87" in output
    assert "auto import skip event missing after append" in output


def test_post_download_auto_import_run_once_surfaces_completed_list_corruption(tmp_path: Path, capsys) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO download_monitor (
                task_id,
                task_hash,
                name,
                chat_id,
                user_id,
                status_code,
                percent_done,
                is_complete,
                completion_observed_at,
                last_observed_at,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                "87",
                "hash-87",
                "Dune 2024 1080p WEB-DL",
                0,
                2001,
                6,
                1.0,
                1,
            ),
        )
        connection.commit()

    auto_import_service = PostDownloadAutoImportService(
        download_monitor_repo=DownloadMonitorRepo(database),
        job_event_repo=type("EventRepo", (), {"list_events_for_task_identity": lambda self, **kwargs: []})(),
        auto_import_func=AsyncMock(return_value="AUTO IMPORT"),
    )

    result = asyncio.run(auto_import_service.run_once(limit=5))

    assert result == AutoImportRunResult(scanned=0, progressed=0, replies=(), state_unavailable=True)
    output = capsys.readouterr().out
    assert "[自动导入候选记录损坏]" in output
    assert "limit=5" in output
    assert "download monitor completed row chat identity corrupted after read" in output
    assert "[处理建议]" in output


def test_post_download_auto_import_run_once_logs_completed_list_failure(capsys) -> None:
    monitor_repo = type(
        "BoomRepo",
        (),
        {"list_completed_for_auto_import": lambda self, *, limit: (_ for _ in ()).throw(RuntimeError("db down"))},
    )()
    auto_import_service = PostDownloadAutoImportService(
        download_monitor_repo=monitor_repo,
        job_event_repo=type("EventRepo", (), {})(),
        auto_import_func=AsyncMock(),
    )

    result = asyncio.run(auto_import_service.run_once(limit=5))

    assert result == AutoImportRunResult(scanned=0, progressed=0, replies=(), state_unavailable=True)
    output = capsys.readouterr().out
    assert "[自动导入候选读取失败]" in output
    assert "limit=5" in output
    assert "db down" in output
    assert "[处理建议]" in output


def test_post_download_auto_import_run_once_logs_completed_list_missing_result(capsys) -> None:
    monitor_repo = type(
        "MissingRepo",
        (),
        {"list_completed_for_auto_import": lambda self, *, limit: None},
    )()
    auto_import_service = PostDownloadAutoImportService(
        download_monitor_repo=monitor_repo,
        job_event_repo=type("EventRepo", (), {})(),
        auto_import_func=AsyncMock(),
    )

    result = asyncio.run(auto_import_service.run_once(limit=5))

    assert result == AutoImportRunResult(scanned=0, progressed=0, replies=(), state_unavailable=True)
    output = capsys.readouterr().out
    assert "[自动导入候选结果缺失]" in output
    assert "limit=5" in output
    assert "auto import completed list result missing" in output
    assert "[处理建议]" in output


def _run(coroutine: Awaitable[str]) -> str:
    return asyncio.run(coroutine)

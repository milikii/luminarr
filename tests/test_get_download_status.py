from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from pathlib import Path
from unittest.mock import AsyncMock

from app.clients.transmission import TransmissionTaskStatus
from app.db.download_monitor_repo import DownloadMonitorRepo
from app.db.job_event_repo import JobEventRepo
from app.db.sqlite import SqliteDatabase
from app.services.get_download_status import (
    STATUS_NOT_FOUND_TEXT,
    STATUS_QUERY_FAILED_TEXT,
    STATUS_QUERY_USAGE_TEXT,
    GetDownloadStatusService,
    parse_status_query,
)
from app.services.post_download_auto_import import (
    AUTO_IMPORT_SKIPPED_BY_RULE_EVENT,
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


def _run(coroutine: Awaitable[str]) -> str:
    return asyncio.run(coroutine)

from __future__ import annotations

from unittest.mock import AsyncMock

from app.db.download_monitor_repo import DownloadMonitorPersistenceError
from app.db.job_event_repo import JobEventPersistenceError
from app.services.add_execution_follow_up import AddExecutionFollowUpService


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

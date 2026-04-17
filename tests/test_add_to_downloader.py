from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.clients.transmission import TransmissionTask
from app.db.approval_repo import APPROVAL_STATUS_CANCELLED, ApprovalRepo
from app.db.candidate_repo import CandidateMappingRepo
from app.db.download_monitor_repo import DownloadMonitorRepo
from app.db.job_repo import JOB_STATE_CANCELLED, JobRecord, JobRepo
from app.db.sqlite import SqliteDatabase
from app.services.add_to_downloader import (
    ADD_APPROVAL_PENDING_TEXT,
    ADD_CANCEL_STATE_UNAVAILABLE_TEXT,
    ADD_CONFIRM_EXPIRED_TEXT,
    ADD_CONFIRM_NOT_PENDING_TEXT,
    ADD_CONFIRM_STATE_UNAVAILABLE_TEXT,
    ADD_FAILED_TEXT,
    ADD_FINALIZATION_WARNING_TEXT,
    ADD_PENDING_STATE_UNAVAILABLE_TEXT,
    CANDIDATE_SOURCE_MISSING_TEXT,
    ConfirmExecutionContext,
    SELECT_LOOKUP_FAILED_TEXT,
    SELECT_NOT_FOUND_TEXT,
    SELECT_OUT_OF_RANGE_TEXT,
    SELECT_USAGE_TEXT,
    AddToDownloaderService,
    PendingAddContext,
)
from app.services.search_media import SearchMediaService
from app.trace_logging import parse_trace_log_line


async def _fake_search_with_download_url(query: str) -> list[dict[str, object]]:
    assert query == "dune"
    return [
        {
            "title": "Dune: Part Two",
            "downloadUrl": "https://example.com/dune.torrent",
        }
    ]


async def _fake_search_without_source(query: str) -> list[dict[str, object]]:
    assert query == "dune"
    return [{"title": "Dune: Part Two"}]


def test_add_by_selection_returns_pending_approval() -> None:
    search_service = SearchMediaService(_fake_search_with_download_url)
    _run(search_service.search_and_format("dune", chat_id=1001))

    add_torrent = AsyncMock(return_value=TransmissionTask(task_id="42", task_hash="abc123"))
    service = AddToDownloaderService(search_service=search_service, add_torrent_func=add_torrent)

    reply = _run(service.add_by_selection(1001, "1"))

    assert reply == ADD_APPROVAL_PENDING_TEXT.format(title="Dune: Part Two", task_ref="1")
    add_torrent.assert_not_awaited()


def test_confirm_add_by_task_ref_dispatches_download() -> None:
    search_service = SearchMediaService(_fake_search_with_download_url)
    _run(search_service.search_and_format("dune", chat_id=1001))

    add_torrent = AsyncMock(return_value=TransmissionTask(task_id="42", task_hash="abc123"))
    service = AddToDownloaderService(search_service=search_service, add_torrent_func=add_torrent)

    pending_reply = _run(service.add_by_selection(1001, "1"))
    confirm_reply = _run(service.confirm_add_by_task_ref("1", chat_id=1001))

    assert pending_reply == ADD_APPROVAL_PENDING_TEXT.format(title="Dune: Part Two", task_ref="1")
    assert "任务 ID: 42" in confirm_reply
    assert "任务 Hash: abc123" in confirm_reply
    add_torrent.assert_awaited_once_with("https://example.com/dune.torrent")


def test_add_workflow_writes_trace_log_when_configured(tmp_path: Path) -> None:
    search_service = SearchMediaService(_fake_search_with_download_url)
    _run(search_service.search_and_format("dune", chat_id=1001))

    add_torrent = AsyncMock(return_value=TransmissionTask(task_id="42", task_hash="abc123"))
    log_path = tmp_path / "trace.log"
    service = AddToDownloaderService(
        search_service=search_service,
        add_torrent_func=add_torrent,
        trace_log_path=log_path,
    )

    _run(service.add_by_selection(1001, "1", user_id=2001))
    _run(service.confirm_add_by_task_ref("1", chat_id=1001, user_id=2001))

    lines = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    parsed_entries = [parse_trace_log_line(line) for line in lines]

    assert [entry.event if entry is not None else None for entry in parsed_entries] == [
        "approval_pending",
        "confirm_dispatch",
        "confirm_finalize",
    ]
    assert parsed_entries[0] is not None
    assert parsed_entries[0].workflow == "add_to_downloader"
    assert parsed_entries[0].result == "created"
    assert parsed_entries[1] is not None
    assert parsed_entries[1].task_id == "42"
    assert parsed_entries[1].result == "succeeded"


def test_confirm_add_by_task_ref_without_pending_request_returns_not_pending() -> None:
    service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search_with_download_url),
        add_torrent_func=AsyncMock(),
    )

    reply = _run(service.confirm_add_by_task_ref("1", chat_id=1001))

    assert reply == ADD_CONFIRM_NOT_PENDING_TEXT


def test_has_pending_add_logs_job_lookup_failure(capsys) -> None:
    job_repo = type("BoomJobRepo", (), {"get_downloader_job_for_chat_ref": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down"))})()
    service = AddToDownloaderService(search_service=SearchMediaService(_fake_search_with_download_url), add_torrent_func=AsyncMock(), job_repo=job_repo)
    assert service.has_pending_add(1001, "1") is None
    assert "[下载待确认查询失败]" in capsys.readouterr().out


def test_has_pending_add_uses_in_memory_pending_when_job_lookup_fails(capsys) -> None:
    job_repo = type("BoomJobRepo", (), {"get_downloader_job_for_chat_ref": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down"))})()
    service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search_with_download_url),
        add_torrent_func=AsyncMock(),
        job_repo=job_repo,
    )
    pending_add = PendingAddContext(
        task_ref="1",
        task_id="selection:1",
        task_hash="abc123",
        title="Dune: Part Two",
        source="https://example.com/dune.torrent",
    )

    service._record_pending_context(chat_id=1001, pending_add=pending_add)

    assert service.has_pending_add(1001, "1") is True
    assert "[下载待确认查询失败]" in capsys.readouterr().out


def test_cancel_pending_add_logs_job_lookup_failure(capsys) -> None:
    job_repo = type("BoomJobRepo", (), {"get_latest_pending_downloader_job": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down"))})()
    service = AddToDownloaderService(search_service=SearchMediaService(_fake_search_with_download_url), add_torrent_func=AsyncMock(), job_repo=job_repo)
    assert service.cancel_pending_add(1001) == ADD_CANCEL_STATE_UNAVAILABLE_TEXT
    assert "[下载取消查询失败]" in capsys.readouterr().out


def test_cancel_pending_add_logs_payload_corruption(capsys) -> None:
    pending_job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="add_to_downloader",
        state="pending_approval",
        task_ref="1",
        task_id="selection:1",
        task_hash="abc123",
        payload_json="{}",
        version=3,
        lease_owner="",
        lease_until="",
        created_at="2026-04-15 00:00:00",
        updated_at="2026-04-15 00:00:00",
    )
    job_repo = type("JobRepo", (), {"get_latest_pending_downloader_job": lambda self, **kwargs: pending_job})()
    service = AddToDownloaderService(search_service=SearchMediaService(_fake_search_with_download_url), add_torrent_func=AsyncMock(), job_repo=job_repo)

    assert service.cancel_pending_add(1001) == ADD_CANCEL_STATE_UNAVAILABLE_TEXT

    output = capsys.readouterr().out
    assert "[下载取消载荷损坏]" in output
    assert "job_id=job-1" in output
    assert "missing required fields: task_ref,task_id,task_hash,title,source" in output


def test_rebuild_confirm_context_logs_job_lookup_failure(capsys) -> None:
    job_repo = type("BoomJobRepo", (), {"get_downloader_job_for_chat_ref": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down"))})()
    service = AddToDownloaderService(search_service=SearchMediaService(_fake_search_with_download_url), add_torrent_func=AsyncMock(), job_repo=job_repo)
    context, lookup_failed = service._rebuild_confirm_context(task_ref="1", chat_id=1001)
    assert context is None
    assert lookup_failed is True
    assert "[下载确认上下文查询失败]" in capsys.readouterr().out


def test_rebuild_confirm_context_logs_approval_lookup_failure(capsys) -> None:
    job = type("Job", (), {"payload_json": "{\"task_ref\":\"1\",\"task_id\":\"selection:1\",\"task_hash\":\"abc123\",\"title\":\"Dune: Part Two\",\"source\":\"https://example.com/dune.torrent\"}", "task_id": "selection:1", "task_hash": "abc123"})()
    job_repo = type("JobRepo", (), {"get_downloader_job_for_chat_ref": lambda self, **kwargs: job})()
    approval_repo = type("ApprovalRepo", (), {"get_downloader_approval": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down"))})()
    service = AddToDownloaderService(search_service=SearchMediaService(_fake_search_with_download_url), add_torrent_func=AsyncMock(), job_repo=job_repo, approval_repo=approval_repo)
    context, lookup_failed = service._rebuild_confirm_context(task_ref="1", chat_id=1001)
    assert context is not None
    assert lookup_failed is False
    assert context.approval_record is None
    assert context.approval_lookup_failed is True
    output = capsys.readouterr().out
    assert "[下载确认审批查询失败]" in output
    assert "当前 confirm 会直接返回状态读取失败" in output


def test_rebuild_confirm_context_logs_payload_corruption(capsys) -> None:
    job = type("Job", (), {"payload_json": "{}", "task_id": "selection:1", "task_hash": "abc123"})()
    job_repo = type("JobRepo", (), {"get_downloader_job_for_chat_ref": lambda self, **kwargs: job})()
    service = AddToDownloaderService(search_service=SearchMediaService(_fake_search_with_download_url), add_torrent_func=AsyncMock(), job_repo=job_repo)

    context, lookup_failed = service._rebuild_confirm_context(task_ref="1", chat_id=1001)
    assert context is None
    assert lookup_failed is True

    output = capsys.readouterr().out
    assert "[下载确认上下文载荷损坏]" in output
    assert "task_hash=abc123" in output
    assert "missing required fields: task_ref,task_id,task_hash,title,source" in output


def test_confirm_add_by_task_ref_returns_state_unavailable_on_context_lookup_failure(capsys) -> None:
    job_repo = type("BoomJobRepo", (), {"get_downloader_job_for_chat_ref": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down"))})()
    add_torrent = AsyncMock(return_value=TransmissionTask(task_id="42", task_hash="abc123"))
    service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search_with_download_url),
        add_torrent_func=add_torrent,
        job_repo=job_repo,
    )

    text = _run(service.confirm_add_by_task_ref("1", chat_id=1001))

    assert text == ADD_CONFIRM_STATE_UNAVAILABLE_TEXT
    add_torrent.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[下载确认上下文查询失败]" in output
    assert "chat_id=1001" in output
    assert "task_ref=1" in output


def test_confirm_add_by_task_ref_returns_state_unavailable_on_context_payload_corruption(capsys) -> None:
    job = type("Job", (), {"payload_json": "{}", "task_id": "selection:1", "task_hash": "abc123"})()
    job_repo = type("JobRepo", (), {"get_downloader_job_for_chat_ref": lambda self, **kwargs: job})()
    add_torrent = AsyncMock(return_value=TransmissionTask(task_id="42", task_hash="abc123"))
    service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search_with_download_url),
        add_torrent_func=add_torrent,
        job_repo=job_repo,
    )

    text = _run(service.confirm_add_by_task_ref("1", chat_id=1001))

    assert text == ADD_CONFIRM_STATE_UNAVAILABLE_TEXT
    add_torrent.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[下载确认上下文载荷损坏]" in output
    assert "task_hash=abc123" in output


def test_confirm_add_by_task_ref_uses_in_memory_pending_when_context_lookup_fails(capsys) -> None:
    job_repo = type("BoomJobRepo", (), {"get_downloader_job_for_chat_ref": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down"))})()
    add_torrent = AsyncMock(return_value=TransmissionTask(task_id="42", task_hash="abc123"))
    service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search_with_download_url),
        add_torrent_func=add_torrent,
        job_repo=job_repo,
    )
    pending_add = PendingAddContext(
        task_ref="1",
        task_id="selection:1",
        task_hash="selection-hash",
        title="Dune: Part Two",
        source="https://example.com/dune.torrent",
    )
    service._record_pending_approval(
        task_ref=pending_add.task_ref,
        task_id=pending_add.task_id,
        task_hash=pending_add.task_hash,
    )
    service._record_pending_context(chat_id=1001, pending_add=pending_add)

    text = _run(service.confirm_add_by_task_ref("1", chat_id=1001))

    assert text == ADD_CONFIRM_STATE_UNAVAILABLE_TEXT
    add_torrent.assert_not_awaited()
    assert "[下载确认上下文查询失败]" in capsys.readouterr().out


def test_confirm_add_by_task_ref_uses_in_memory_pending_without_job_repo() -> None:
    add_torrent = AsyncMock(return_value=TransmissionTask(task_id="42", task_hash="abc123"))
    service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search_with_download_url),
        add_torrent_func=add_torrent,
    )
    pending_add = PendingAddContext(
        task_ref="1",
        task_id="selection:1",
        task_hash="selection-hash",
        title="Dune: Part Two",
        source="https://example.com/dune.torrent",
    )
    service._record_pending_approval(
        task_ref=pending_add.task_ref,
        task_id=pending_add.task_id,
        task_hash=pending_add.task_hash,
    )
    service._record_pending_context(chat_id=1001, pending_add=pending_add)

    text = _run(service.confirm_add_by_task_ref("1", chat_id=1001))

    assert "任务 ID: 42" in text
    assert "任务 Hash: abc123" in text
    add_torrent.assert_awaited_once_with("https://example.com/dune.torrent")


def test_record_pending_approval_logs_persistence_failure(capsys) -> None:
    approval_repo = type("ApprovalRepo", (), {"request_downloader_approval": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down"))})()
    service = AddToDownloaderService(search_service=SearchMediaService(_fake_search_with_download_url), add_torrent_func=AsyncMock(), approval_repo=approval_repo)
    assert service._record_pending_approval(task_ref="1", task_id="selection:1", task_hash="abc123") == 0
    output = capsys.readouterr().out
    assert "[下载待确认审批落盘失败]" in output
    assert "当前请求会直接返回待确认状态写入失败" in output


def test_record_pending_approval_logs_missing_pending_result(capsys) -> None:
    approval_repo = type(
        "ApprovalRepo",
        (),
        {"request_downloader_approval": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("approval_record missing after pending request"))},
    )()
    service = AddToDownloaderService(search_service=SearchMediaService(_fake_search_with_download_url), add_torrent_func=AsyncMock(), approval_repo=approval_repo)
    assert service._record_pending_approval(task_ref="1", task_id="selection:1", task_hash="abc123") == 0
    output = capsys.readouterr().out
    assert "[下载待确认审批结果缺失]" in output
    assert "approval_record missing after pending request" in output
    assert "当前请求会直接返回待确认状态写入失败" in output


def test_record_pending_job_logs_persistence_failure(capsys) -> None:
    job_repo = type("JobRepo", (), {"upsert_downloader_job_pending": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down"))})()
    service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search_with_download_url),
        add_torrent_func=AsyncMock(),
        job_repo=job_repo,
    )

    pending_add = PendingAddContext(
        task_ref="1",
        task_id="selection:1",
        task_hash="abc123",
        title="Dune",
        source="https://example.com/dune.torrent",
    )
    assert service._record_pending_job(chat_id=1001, user_id=2001, pending_add=pending_add) is False
    output = capsys.readouterr().out
    assert "[下载待确认任务落盘失败]" in output
    assert "task_ref=1" in output
    assert "当前请求会直接返回待确认状态写入失败" in output


def test_record_pending_job_logs_missing_pending_job_result(capsys) -> None:
    job_repo = type(
        "JobRepo",
        (),
        {"upsert_downloader_job_pending": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("job missing after pending upsert"))},
    )()
    service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search_with_download_url),
        add_torrent_func=AsyncMock(),
        job_repo=job_repo,
    )

    pending_add = PendingAddContext(
        task_ref="1",
        task_id="selection:1",
        task_hash="abc123",
        title="Dune",
        source="https://example.com/dune.torrent",
    )
    assert service._record_pending_job(chat_id=1001, user_id=2001, pending_add=pending_add) is False
    output = capsys.readouterr().out
    assert "[下载待确认任务结果缺失]" in output
    assert "task_ref=1" in output
    assert "downloader pending job missing after upsert" in output


def test_record_downloader_approval_logs_persistence_failure(capsys) -> None:
    approval_repo = type("ApprovalRepo", (), {"approve_downloader": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down"))})()
    service = AddToDownloaderService(search_service=SearchMediaService(_fake_search_with_download_url), add_torrent_func=AsyncMock(), approval_repo=approval_repo)
    service._pending_add_identities.add(("selection:1", "abc123"))
    service._pending_add_lease_versions[("selection:1", "abc123")] = 1
    assert service._record_downloader_approval(task_ref="1", task_id="selection:1", task_hash="abc123", expected_lease_version=1) is None
    assert "[下载确认审批更新失败]" in capsys.readouterr().out


def test_record_downloader_approval_logs_missing_result(capsys) -> None:
    approval_repo = type(
        "ApprovalRepo",
        (),
        {"approve_downloader": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("approval_record missing during approve"))},
    )()
    service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search_with_download_url),
        add_torrent_func=AsyncMock(),
        approval_repo=approval_repo,
    )
    service._pending_add_identities.add(("selection:1", "abc123"))
    service._pending_add_lease_versions[("selection:1", "abc123")] = 1

    assert service._record_downloader_approval(
        task_ref="1",
        task_id="selection:1",
        task_hash="abc123",
        expected_lease_version=1,
    ) is None

    output = capsys.readouterr().out
    assert "[下载确认审批结果缺失]" in output
    assert "approval_record missing during approve" in output
    assert "[处理建议]" in output


def test_record_downloader_approval_logs_rejected_current_state(capsys) -> None:
    approval_repo = type("ApprovalRepo", (), {"approve_downloader": lambda self, **kwargs: False})()
    service = AddToDownloaderService(search_service=SearchMediaService(_fake_search_with_download_url), add_torrent_func=AsyncMock(), approval_repo=approval_repo)
    service._pending_add_identities.add(("selection:1", "abc123"))
    service._pending_add_lease_versions[("selection:1", "abc123")] = 1
    assert service._record_downloader_approval(task_ref="1", task_id="selection:1", task_hash="abc123", expected_lease_version=1) is False
    output = capsys.readouterr().out
    assert "[下载确认审批更新失败]" in output
    assert "approval_record approve rejected current state" in output


def test_cancel_pending_approval_logs_persistence_failure(capsys) -> None:
    approval_repo = type("ApprovalRepo", (), {"cancel_downloader": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down"))})()
    service = AddToDownloaderService(search_service=SearchMediaService(_fake_search_with_download_url), add_torrent_func=AsyncMock(), approval_repo=approval_repo)
    assert service._cancel_pending_approval(task_ref="1", task_id="selection:1", task_hash="abc123", expected_lease_version=1) is False
    assert "[下载取消审批更新失败]" in capsys.readouterr().out


def test_cancel_pending_approval_logs_missing_result(capsys) -> None:
    approval_repo = type(
        "ApprovalRepo",
        (),
        {"cancel_downloader": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("approval_record missing during cancel"))},
    )()
    service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search_with_download_url),
        add_torrent_func=AsyncMock(),
        approval_repo=approval_repo,
    )

    assert service._cancel_pending_approval(
        task_ref="1",
        task_id="selection:1",
        task_hash="abc123",
        expected_lease_version=1,
    ) is False

    output = capsys.readouterr().out
    assert "[下载取消审批结果缺失]" in output
    assert "approval_record missing during cancel" in output
    assert "[处理建议]" in output


def test_record_executed_lease_version_logs_persistence_failure(capsys) -> None:
    approval_repo = type("ApprovalRepo", (), {"mark_downloader_executed": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down"))})()
    service = AddToDownloaderService(search_service=SearchMediaService(_fake_search_with_download_url), add_torrent_func=AsyncMock(), approval_repo=approval_repo)
    assert (
        service._record_executed_lease_version(
            task_ref="1",
            task_id="selection:1",
            task_hash="abc123",
            executed_lease_version=2,
        )
        is None
    )
    assert service._pending_add_lease_versions[("selection:1", "abc123")] == 2
    assert "[下载执行版号回写失败]" in capsys.readouterr().out


def test_record_executed_lease_version_logs_missing_result(capsys) -> None:
    approval_repo = type(
        "ApprovalRepo",
        (),
        {
            "mark_downloader_executed": lambda self, **kwargs: (_ for _ in ()).throw(
                RuntimeError("approval_record missing during executed version update")
            )
        },
    )()
    service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search_with_download_url),
        add_torrent_func=AsyncMock(),
        approval_repo=approval_repo,
    )
    assert (
        service._record_executed_lease_version(
            task_ref="1",
            task_id="selection:1",
            task_hash="abc123",
            executed_lease_version=2,
        )
        is None
    )
    assert service._pending_add_lease_versions[("selection:1", "abc123")] == 2
    output = capsys.readouterr().out
    assert "[下载执行版号结果缺失]" in output
    assert "approval_record 更新后该审批行是否仍存在" in output


def test_record_event_logs_persistence_failure(capsys) -> None:
    job_event_repo = type("JobEventRepo", (), {"append_event": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down"))})()
    service = AddToDownloaderService(search_service=SearchMediaService(_fake_search_with_download_url), add_torrent_func=AsyncMock(), job_event_repo=job_event_repo)
    service._record_event(
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
    job_event_repo = type(
        "JobEventRepo",
        (),
        {"append_event": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("job_event missing after append"))},
    )()
    service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search_with_download_url),
        add_torrent_func=AsyncMock(),
        job_event_repo=job_event_repo,
    )
    service._record_event(
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


def test_register_download_monitor_logs_persistence_failure(capsys) -> None:
    download_monitor_repo = type("DownloadMonitorRepo", (), {"register_download": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down"))})()
    service = AddToDownloaderService(search_service=SearchMediaService(_fake_search_with_download_url), add_torrent_func=AsyncMock(), download_monitor_repo=download_monitor_repo)
    service._register_download_monitor(
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
    download_monitor_repo = type(
        "DownloadMonitorRepo",
        (),
        {"register_download": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("download monitor state missing after register"))},
    )()
    service = AddToDownloaderService(search_service=SearchMediaService(_fake_search_with_download_url), add_torrent_func=AsyncMock(), download_monitor_repo=download_monitor_repo)
    service._register_download_monitor(
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


def test_record_pending_job_logs_persistence_failure(capsys) -> None:
    job_repo = type("JobRepo", (), {"upsert_downloader_job_pending": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down"))})()
    service = AddToDownloaderService(search_service=SearchMediaService(_fake_search_with_download_url), add_torrent_func=AsyncMock(), job_repo=job_repo)
    assert service._record_pending_job(
        chat_id=1001,
        user_id=2001,
        pending_add=PendingAddContext(
            task_ref="1",
            task_id="selection:1",
            task_hash="abc123",
            title="Dune: Part Two",
            source="https://example.com/dune.torrent",
        ),
    ) is False
    output = capsys.readouterr().out
    assert "[下载待确认任务落盘失败]" in output
    assert "task_ref=1" in output


def test_add_by_selection_returns_state_unavailable_when_pending_approval_persist_fails() -> None:
    search_service = SearchMediaService(_fake_search_with_download_url)
    _run(search_service.search_and_format("dune", chat_id=1001))
    approval_repo = type("ApprovalRepo", (), {"request_downloader_approval": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down"))})()
    service = AddToDownloaderService(
        search_service=search_service,
        add_torrent_func=AsyncMock(),
        approval_repo=approval_repo,
    )

    reply = _run(service.add_by_selection(1001, "1"))

    assert reply == ADD_PENDING_STATE_UNAVAILABLE_TEXT


def test_add_by_selection_returns_state_unavailable_when_pending_job_persist_fails() -> None:
    search_service = SearchMediaService(_fake_search_with_download_url)
    _run(search_service.search_and_format("dune", chat_id=1001))
    approval_repo = type(
        "ApprovalRepo",
        (),
        {
            "request_downloader_approval": lambda self, **kwargs: 2,
            "cancel_downloader": lambda self, **kwargs: True,
        },
    )()
    job_repo = type("JobRepo", (), {"upsert_downloader_job_pending": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down"))})()
    service = AddToDownloaderService(
        search_service=search_service,
        add_torrent_func=AsyncMock(),
        approval_repo=approval_repo,
        job_repo=job_repo,
    )

    reply = _run(service.add_by_selection(1001, "1"))

    assert reply == ADD_PENDING_STATE_UNAVAILABLE_TEXT


def test_add_candidate_source_returns_state_unavailable_when_pending_job_persist_fails() -> None:
    approval_repo = type(
        "ApprovalRepo",
        (),
        {
            "request_downloader_approval": lambda self, **kwargs: 2,
            "cancel_downloader": lambda self, **kwargs: True,
        },
    )()
    job_repo = type("JobRepo", (), {"upsert_downloader_job_pending": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down"))})()
    service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search_with_download_url),
        add_torrent_func=AsyncMock(),
        approval_repo=approval_repo,
        job_repo=job_repo,
    )

    reply = _run(
        service.add_candidate_source(
            chat_id=1001,
            source="magnet:?xt=urn:btih:abc",
            title="Dune: Part Two",
        )
    )

    assert reply == ADD_PENDING_STATE_UNAVAILABLE_TEXT


def test_claim_pending_job_logs_persistence_failure(capsys) -> None:
    job_repo = type("JobRepo", (), {"claim_lease": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down"))})()
    service = AddToDownloaderService(search_service=SearchMediaService(_fake_search_with_download_url), add_torrent_func=AsyncMock(), job_repo=job_repo)
    job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="add_to_downloader",
        state="pending_approval",
        task_ref="1",
        task_id="selection:1",
        task_hash="abc123",
        payload_json="{}",
        version=3,
        lease_owner="",
        lease_until="",
        created_at="2026-04-15 00:00:00",
        updated_at="2026-04-15 00:00:00",
    )
    assert service._claim_pending_job(job=job, lease_owner="downloader_confirm:1") is None
    output = capsys.readouterr().out
    assert "[下载确认任务抢占失败]" in output
    assert "job_id=job-1" in output
    assert "当前 confirm 会直接返回状态读取失败" in output


def test_claim_pending_job_logs_missing_result(capsys) -> None:
    job_repo = type(
        "JobRepo",
        (),
        {
            "claim_lease": lambda self, **kwargs: (
                _ for _ in ()
            ).throw(RuntimeError("job missing during lease claim"))
        },
    )()
    service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search_with_download_url),
        add_torrent_func=AsyncMock(),
        job_repo=job_repo,
    )
    job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="add_to_downloader",
        state="pending_approval",
        task_ref="1",
        task_id="selection:1",
        task_hash="abc123",
        payload_json="{}",
        version=3,
        lease_owner="",
        lease_until="",
        created_at="2026-04-15 00:00:00",
        updated_at="2026-04-15 00:00:00",
    )
    assert service._claim_pending_job(job=job, lease_owner="downloader_confirm:1") is None
    output = capsys.readouterr().out
    assert "[下载确认任务抢占结果缺失]" in output
    assert "job missing during lease claim" in output
    assert "job_id=job-1" in output


def test_claim_pending_job_logs_rejected_current_state(capsys) -> None:
    job_repo = type("JobRepo", (), {"claim_lease": lambda self, **kwargs: False})()
    service = AddToDownloaderService(search_service=SearchMediaService(_fake_search_with_download_url), add_torrent_func=AsyncMock(), job_repo=job_repo)
    job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="add_to_downloader",
        state="pending_approval",
        task_ref="1",
        task_id="selection:1",
        task_hash="abc123",
        payload_json="{}",
        version=3,
        lease_owner="",
        lease_until="",
        created_at="2026-04-15 00:00:00",
        updated_at="2026-04-15 00:00:00",
    )
    assert service._claim_pending_job(job=job, lease_owner="downloader_confirm:1") is False
    output = capsys.readouterr().out
    assert "[下载确认任务抢占失败]" in output
    assert "jobs.claim_lease rejected current state" in output
    assert "job_id=job-1" in output


def test_confirm_add_by_task_ref_returns_state_unavailable_when_claim_lease_raises(capsys) -> None:
    job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="add_to_downloader",
        state="pending_approval",
        task_ref="1",
        task_id="selection:1",
        task_hash="abc123",
        payload_json="{\"task_ref\":\"1\",\"task_id\":\"selection:1\",\"task_hash\":\"abc123\",\"title\":\"Dune: Part Two\",\"source\":\"https://example.com/dune.torrent\"}",
        version=3,
        lease_owner="",
        lease_until="",
        created_at="2026-04-15 00:00:00",
        updated_at="2026-04-15 00:00:00",
    )
    approval_record = type("ApprovalRecord", (), {"status": "pending", "lease_version": 2, "executed_version": 0})()
    job_repo = type(
        "JobRepo",
        (),
        {
            "get_downloader_job_for_chat_ref": lambda self, **kwargs: job,
            "claim_lease": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down")),
        },
    )()
    approval_repo = type(
        "ApprovalRepo",
        (),
        {
            "get_downloader_approval": lambda self, **kwargs: approval_record,
            "is_downloader_pending_expired": lambda self, **kwargs: False,
        },
    )()
    add_torrent = AsyncMock()
    service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search_with_download_url),
        add_torrent_func=add_torrent,
        job_repo=job_repo,
        approval_repo=approval_repo,
    )

    reply = _run(service.confirm_add_by_task_ref("1", chat_id=1001))

    assert reply == ADD_CONFIRM_STATE_UNAVAILABLE_TEXT
    add_torrent.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[下载确认任务抢占失败]" in output
    assert "job_id=job-1" in output
    assert "db down" in output


def test_confirm_add_by_task_ref_returns_state_unavailable_when_claim_lease_result_is_missing(capsys) -> None:
    job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="add_to_downloader",
        state="pending_approval",
        task_ref="1",
        task_id="selection:1",
        task_hash="abc123",
        payload_json="{\"task_ref\":\"1\",\"task_id\":\"selection:1\",\"task_hash\":\"abc123\",\"title\":\"Dune: Part Two\",\"source\":\"https://example.com/dune.torrent\"}",
        version=3,
        lease_owner="",
        lease_until="",
        created_at="2026-04-15 00:00:00",
        updated_at="2026-04-15 00:00:00",
    )
    approval_record = type("ApprovalRecord", (), {"status": "pending", "lease_version": 2, "executed_version": 0})()
    job_repo = type(
        "JobRepo",
        (),
        {
            "get_downloader_job_for_chat_ref": lambda self, **kwargs: job,
            "claim_lease": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("job missing during lease claim")),
        },
    )()
    approval_repo = type(
        "ApprovalRepo",
        (),
        {
            "get_downloader_approval": lambda self, **kwargs: approval_record,
            "is_downloader_pending_expired": lambda self, **kwargs: False,
        },
    )()
    add_torrent = AsyncMock()
    service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search_with_download_url),
        add_torrent_func=add_torrent,
        job_repo=job_repo,
        approval_repo=approval_repo,
    )

    reply = _run(service.confirm_add_by_task_ref("1", chat_id=1001))

    assert reply == ADD_CONFIRM_STATE_UNAVAILABLE_TEXT
    add_torrent.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[下载确认任务抢占结果缺失]" in output
    assert "job_id=job-1" in output
    assert "job missing during lease claim" in output


def test_confirm_add_by_task_ref_returns_not_pending_when_claim_lease_is_rejected(capsys) -> None:
    job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="add_to_downloader",
        state="pending_approval",
        task_ref="1",
        task_id="selection:1",
        task_hash="abc123",
        payload_json="{\"task_ref\":\"1\",\"task_id\":\"selection:1\",\"task_hash\":\"abc123\",\"title\":\"Dune: Part Two\",\"source\":\"https://example.com/dune.torrent\"}",
        version=3,
        lease_owner="",
        lease_until="",
        created_at="2026-04-15 00:00:00",
        updated_at="2026-04-15 00:00:00",
    )
    approval_record = type("ApprovalRecord", (), {"status": "pending", "lease_version": 2, "executed_version": 0})()
    job_repo = type(
        "JobRepo",
        (),
        {
            "get_downloader_job_for_chat_ref": lambda self, **kwargs: job,
            "claim_lease": lambda self, **kwargs: False,
        },
    )()
    approval_repo = type(
        "ApprovalRepo",
        (),
        {
            "get_downloader_approval": lambda self, **kwargs: approval_record,
            "is_downloader_pending_expired": lambda self, **kwargs: False,
        },
    )()
    add_torrent = AsyncMock()
    service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search_with_download_url),
        add_torrent_func=add_torrent,
        job_repo=job_repo,
        approval_repo=approval_repo,
    )

    reply = _run(service.confirm_add_by_task_ref("1", chat_id=1001))

    assert reply == ADD_CONFIRM_NOT_PENDING_TEXT
    add_torrent.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[下载确认任务抢占失败]" in output
    assert "jobs.claim_lease rejected current state" in output
    assert "job_id=job-1" in output


def test_restore_pending_job_logs_persistence_failure(capsys) -> None:
    job_repo = type("JobRepo", (), {"release_lease_to_pending": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down"))})()
    service = AddToDownloaderService(search_service=SearchMediaService(_fake_search_with_download_url), add_torrent_func=AsyncMock(), job_repo=job_repo)
    service._restore_pending_job(job_id="job-1", expected_version=3, lease_owner="downloader_confirm:1")
    output = capsys.readouterr().out
    assert "[下载确认任务回退失败]" in output
    assert "job_id=job-1" in output


def test_restore_pending_job_logs_missing_result(capsys) -> None:
    job_repo = type(
        "JobRepo",
        (),
        {
            "release_lease_to_pending": lambda self, **kwargs: (_ for _ in ()).throw(
                RuntimeError("job missing during state transition")
            )
        },
    )()
    service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search_with_download_url),
        add_torrent_func=AsyncMock(),
        job_repo=job_repo,
    )
    service._restore_pending_job(job_id="job-1", expected_version=3, lease_owner="downloader_confirm:1")
    output = capsys.readouterr().out
    assert "[下载确认任务回退结果缺失]" in output
    assert "lease 回退后是否还能回读到待确认状态" in output
    assert "job_id=job-1" in output


def test_restore_pending_job_logs_rejected_current_state(capsys) -> None:
    job_repo = type("JobRepo", (), {"release_lease_to_pending": lambda self, **kwargs: False})()
    service = AddToDownloaderService(search_service=SearchMediaService(_fake_search_with_download_url), add_torrent_func=AsyncMock(), job_repo=job_repo)
    service._restore_pending_job(job_id="job-1", expected_version=3, lease_owner="downloader_confirm:1")
    output = capsys.readouterr().out
    assert "[下载确认任务回退失败]" in output
    assert "jobs.release_lease_to_pending rejected current state" in output
    assert "job_id=job-1" in output


def test_mark_completed_job_logs_persistence_failure(capsys) -> None:
    job_repo = type("JobRepo", (), {"mark_downloader_completed": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down"))})()
    service = AddToDownloaderService(search_service=SearchMediaService(_fake_search_with_download_url), add_torrent_func=AsyncMock(), job_repo=job_repo)
    assert (
        service._mark_completed_job(
            job_id="job-1",
            expected_version=3,
            lease_owner="downloader_confirm:1",
            completed_add=PendingAddContext(
                task_ref="1",
                task_id="selection:1",
                task_hash="abc123",
                title="Dune: Part Two",
                source="https://example.com/dune.torrent",
            ),
        )
        is None
    )
    output = capsys.readouterr().out
    assert "[下载确认任务完结失败]" in output
    assert "job_id=job-1" in output


def test_mark_completed_job_logs_rejected_current_state(capsys) -> None:
    job_repo = type("JobRepo", (), {"mark_downloader_completed": lambda self, **kwargs: False})()
    service = AddToDownloaderService(search_service=SearchMediaService(_fake_search_with_download_url), add_torrent_func=AsyncMock(), job_repo=job_repo)
    assert (
        service._mark_completed_job(
            job_id="job-1",
            expected_version=3,
            lease_owner="downloader_confirm:1",
            completed_add=PendingAddContext(
                task_ref="1",
                task_id="selection:1",
                task_hash="abc123",
                title="Dune: Part Two",
                source="https://example.com/dune.torrent",
            ),
        )
        is False
    )
    output = capsys.readouterr().out
    assert "[下载确认任务完结失败]" in output
    assert "jobs.mark_downloader_completed rejected current state" in output
    assert "job_id=job-1" in output


def test_restore_pending_approval_logs_persistence_failure(capsys) -> None:
    approval_repo = type("ApprovalRepo", (), {"restore_downloader_pending": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down"))})()
    service = AddToDownloaderService(search_service=SearchMediaService(_fake_search_with_download_url), add_torrent_func=AsyncMock(), approval_repo=approval_repo)
    assert (
        service._restore_pending_approval(
            task_ref="1",
            task_id="selection:1",
            task_hash="abc123",
            expected_lease_version=2,
        )
        is None
    )
    output = capsys.readouterr().out
    assert "[下载审批回退失败]" in output
    assert "lease_version=2" in output


def test_restore_pending_approval_logs_missing_result(capsys) -> None:
    approval_repo = type("ApprovalRepo", (), {"restore_downloader_pending": lambda self, **kwargs: None})()
    service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search_with_download_url),
        add_torrent_func=AsyncMock(),
        approval_repo=approval_repo,
    )
    assert (
        service._restore_pending_approval(
            task_ref="1",
            task_id="selection:1",
            task_hash="abc123",
            expected_lease_version=2,
        )
        is None
    )
    output = capsys.readouterr().out
    assert "[下载审批回退结果缺失]" in output
    assert "downloader restore pending approval result missing" in output
    assert "lease_version=2" in output


def test_restore_pending_approval_logs_missing_row_result(capsys) -> None:
    approval_repo = type(
        "ApprovalRepo",
        (),
        {"restore_downloader_pending": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("approval_record missing during restore"))},
    )()
    service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search_with_download_url),
        add_torrent_func=AsyncMock(),
        approval_repo=approval_repo,
    )
    assert (
        service._restore_pending_approval(
            task_ref="1",
            task_id="selection:1",
            task_hash="abc123",
            expected_lease_version=2,
        )
        is None
    )
    output = capsys.readouterr().out
    assert "[下载审批回退结果缺失]" in output
    assert "approval_record missing during restore" in output
    assert "lease_version=2" in output


def test_restore_pending_approval_logs_rejected_current_state(capsys) -> None:
    approval_repo = type("ApprovalRepo", (), {"restore_downloader_pending": lambda self, **kwargs: False})()
    service = AddToDownloaderService(search_service=SearchMediaService(_fake_search_with_download_url), add_torrent_func=AsyncMock(), approval_repo=approval_repo)
    assert (
        service._restore_pending_approval(
            task_ref="1",
            task_id="selection:1",
            task_hash="abc123",
            expected_lease_version=2,
        )
        is False
    )
    output = capsys.readouterr().out
    assert "[下载审批回退失败]" in output
    assert "approval_record restore rejected current state" in output
    assert "lease_version=2" in output


def test_resolve_pending_lease_version_logs_approval_lookup_failure(capsys) -> None:
    approval_repo = type("ApprovalRepo", (), {"get_downloader_approval": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down"))})()
    service = AddToDownloaderService(search_service=SearchMediaService(_fake_search_with_download_url), add_torrent_func=AsyncMock(), approval_repo=approval_repo)
    service._pending_add_identities.add(("selection:1", "abc123"))
    service._pending_add_lease_versions[("selection:1", "abc123")] = 3
    assert service._resolve_pending_lease_version(task_id="selection:1", task_hash="abc123") == 3
    output = capsys.readouterr().out
    assert "[下载待确认版号查询失败]" in output
    assert "task_id=selection:1" in output
    assert "当前调用会按状态读取失败处理" in output


def test_resolve_pending_lease_version_logs_missing_approval_row_with_in_memory_pending(capsys) -> None:
    approval_repo = type("ApprovalRepo", (), {"get_downloader_approval": lambda self, **kwargs: None})()
    service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search_with_download_url),
        add_torrent_func=AsyncMock(),
        approval_repo=approval_repo,
    )
    service._pending_add_identities.add(("selection:1", "abc123"))
    service._pending_add_lease_versions[("selection:1", "abc123")] = 3

    assert (
        service._resolve_pending_lease_version(
            task_id="selection:1",
            task_hash="abc123",
            allow_in_memory_fallback_on_error=False,
        )
        == -1
    )

    output = capsys.readouterr().out
    assert "[下载待确认版号查询失败]" in output
    assert "approval_record missing while in-memory pending exists" in output
    assert "task_id=selection:1" in output


def test_find_version_stale_rejection_text_logs_approval_lookup_failure(capsys) -> None:
    approval_repo = type("ApprovalRepo", (), {"get_downloader_approval": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down"))})()
    service = AddToDownloaderService(search_service=SearchMediaService(_fake_search_with_download_url), add_torrent_func=AsyncMock(), approval_repo=approval_repo)
    assert service._find_version_stale_rejection_text(task_id="selection:1", task_hash="abc123") == ADD_CONFIRM_STATE_UNAVAILABLE_TEXT
    output = capsys.readouterr().out
    assert "[下载确认执行版号查询失败]" in output
    assert "task_hash=abc123" in output


def test_find_version_stale_rejection_text_logs_missing_approval_row(capsys) -> None:
    approval_repo = type("ApprovalRepo", (), {"get_downloader_approval": lambda self, **kwargs: None})()
    service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search_with_download_url),
        add_torrent_func=AsyncMock(),
        approval_repo=approval_repo,
    )

    assert service._find_version_stale_rejection_text(task_id="selection:1", task_hash="abc123") == ADD_CONFIRM_STATE_UNAVAILABLE_TEXT

    output = capsys.readouterr().out
    assert "[下载确认执行版号查询失败]" in output
    assert "approval_record missing during stale check" in output
    assert "task_id=selection:1" in output


def test_is_pending_approval_expired_logs_approval_lookup_failure(capsys) -> None:
    approval_repo = type("ApprovalRepo", (), {"is_downloader_pending_expired": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down"))})()
    service = AddToDownloaderService(search_service=SearchMediaService(_fake_search_with_download_url), add_torrent_func=AsyncMock(), approval_repo=approval_repo)
    assert service._is_pending_approval_expired(task_id="selection:1", task_hash="abc123", expected_lease_version=2) is None
    output = capsys.readouterr().out
    assert "[下载确认过期判断失败]" in output
    assert "lease_version=2" in output


def test_is_pending_approval_expired_logs_missing_approval_result(capsys) -> None:
    approval_repo = type(
        "ApprovalRepo",
        (),
        {
            "is_downloader_pending_expired": lambda self, **kwargs: (
                _ for _ in ()
            ).throw(RuntimeError("approval_record missing during pending expiry check"))
        },
    )()
    service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search_with_download_url),
        add_torrent_func=AsyncMock(),
        approval_repo=approval_repo,
    )

    assert service._is_pending_approval_expired(task_id="selection:1", task_hash="abc123", expected_lease_version=2) is None

    output = capsys.readouterr().out
    assert "[下载确认过期结果缺失]" in output
    assert "approval_record missing during pending expiry check" in output
    assert "lease_version=2" in output


def test_confirm_add_by_task_ref_returns_state_unavailable_when_approval_lookup_fails(capsys) -> None:
    job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="add_to_downloader",
        state="pending_approval",
        task_ref="1",
        task_id="selection:1",
        task_hash="abc123",
        payload_json="{\"task_ref\":\"1\",\"task_id\":\"selection:1\",\"task_hash\":\"abc123\",\"title\":\"Dune: Part Two\",\"source\":\"https://example.com/dune.torrent\"}",
        version=3,
        lease_owner="",
        lease_until="",
        created_at="2026-04-15 00:00:00",
        updated_at="2026-04-15 00:00:00",
    )
    job_repo = type("JobRepo", (), {"get_downloader_job_for_chat_ref": lambda self, **kwargs: job})()
    approval_repo = type("ApprovalRepo", (), {"get_downloader_approval": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down"))})()
    add_torrent = AsyncMock()
    service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search_with_download_url),
        add_torrent_func=add_torrent,
        job_repo=job_repo,
        approval_repo=approval_repo,
    )

    reply = _run(service.confirm_add_by_task_ref("1", chat_id=1001))

    assert reply == ADD_CONFIRM_STATE_UNAVAILABLE_TEXT
    add_torrent.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[下载确认审批查询失败]" in output
    assert "当前 confirm 会直接返回状态读取失败" in output


def test_confirm_add_by_task_ref_returns_state_unavailable_when_approval_row_missing(capsys) -> None:
    job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="add_to_downloader",
        state="pending_approval",
        task_ref="1",
        task_id="selection:1",
        task_hash="abc123",
        payload_json="{\"task_ref\":\"1\",\"task_id\":\"selection:1\",\"task_hash\":\"abc123\",\"title\":\"Dune: Part Two\",\"source\":\"https://example.com/dune.torrent\"}",
        version=3,
        lease_owner="",
        lease_until="",
        created_at="2026-04-15 00:00:00",
        updated_at="2026-04-15 00:00:00",
    )
    job_repo = type("JobRepo", (), {"get_downloader_job_for_chat_ref": lambda self, **kwargs: job})()
    approval_repo = type("ApprovalRepo", (), {"get_downloader_approval": lambda self, **kwargs: None})()
    add_torrent = AsyncMock()
    service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search_with_download_url),
        add_torrent_func=add_torrent,
        job_repo=job_repo,
        approval_repo=approval_repo,
    )

    reply = _run(service.confirm_add_by_task_ref("1", chat_id=1001))

    assert reply == ADD_CONFIRM_STATE_UNAVAILABLE_TEXT
    add_torrent.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[下载确认执行版号查询失败]" in output
    assert "approval_record missing during stale check" in output


def test_confirm_add_by_task_ref_returns_state_unavailable_when_expiry_lookup_fails(capsys) -> None:
    job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="add_to_downloader",
        state="pending_approval",
        task_ref="1",
        task_id="selection:1",
        task_hash="abc123",
        payload_json="{\"task_ref\":\"1\",\"task_id\":\"selection:1\",\"task_hash\":\"abc123\",\"title\":\"Dune: Part Two\",\"source\":\"https://example.com/dune.torrent\"}",
        version=3,
        lease_owner="",
        lease_until="",
        created_at="2026-04-15 00:00:00",
        updated_at="2026-04-15 00:00:00",
    )
    approval_record = type("ApprovalRecord", (), {"status": "pending", "lease_version": 2, "executed_version": 0})()
    job_repo = type("JobRepo", (), {"get_downloader_job_for_chat_ref": lambda self, **kwargs: job})()
    approval_repo = type(
        "ApprovalRepo",
        (),
        {
            "get_downloader_approval": lambda self, **kwargs: approval_record,
            "is_downloader_pending_expired": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down")),
        },
    )()
    add_torrent = AsyncMock()
    service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search_with_download_url),
        add_torrent_func=add_torrent,
        job_repo=job_repo,
        approval_repo=approval_repo,
    )

    reply = _run(service.confirm_add_by_task_ref("1", chat_id=1001))

    assert reply == ADD_CONFIRM_STATE_UNAVAILABLE_TEXT
    add_torrent.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[下载确认过期判断失败]" in output
    assert "lease_version=2" in output


def test_confirm_add_by_task_ref_returns_state_unavailable_when_approval_update_fails(capsys) -> None:
    job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="add_to_downloader",
        state="pending_approval",
        task_ref="1",
        task_id="selection:1",
        task_hash="abc123",
        payload_json="{\"task_ref\":\"1\",\"task_id\":\"selection:1\",\"task_hash\":\"abc123\",\"title\":\"Dune: Part Two\",\"source\":\"https://example.com/dune.torrent\"}",
        version=3,
        lease_owner="",
        lease_until="",
        created_at="2026-04-15 00:00:00",
        updated_at="2026-04-15 00:00:00",
    )
    approval_record = type("ApprovalRecord", (), {"status": "pending", "lease_version": 2, "executed_version": 0})()
    job_repo = type(
        "JobRepo",
        (),
        {
            "get_downloader_job_for_chat_ref": lambda self, **kwargs: job,
            "claim_lease": lambda self, **kwargs: True,
            "release_lease_to_pending": lambda self, **kwargs: True,
        },
    )()
    approval_repo = type(
        "ApprovalRepo",
        (),
        {
            "get_downloader_approval": lambda self, **kwargs: approval_record,
            "is_downloader_pending_expired": lambda self, **kwargs: False,
            "approve_downloader": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down")),
        },
    )()
    add_torrent = AsyncMock(return_value=TransmissionTask(task_id="42", task_hash="hash-42"))
    service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search_with_download_url),
        add_torrent_func=add_torrent,
        job_repo=job_repo,
        approval_repo=approval_repo,
    )

    reply = _run(service.confirm_add_by_task_ref("1", chat_id=1001))

    assert reply == ADD_CONFIRM_STATE_UNAVAILABLE_TEXT
    add_torrent.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[下载确认审批更新失败]" in output
    assert "lease_version=2" in output


def test_confirm_add_by_task_ref_returns_state_unavailable_when_pending_lease_lookup_fails_after_stale_check(
    capsys,
) -> None:
    approval_records = iter(
        (
            type("ApprovalRecord", (), {"lease_version": 0, "executed_version": 0})(),
            RuntimeError("db down"),
        )
    )

    def _get_downloader_approval(**_: object):
        next_value = next(approval_records)
        if isinstance(next_value, Exception):
            raise next_value
        return next_value

    approval_repo = type(
        "ApprovalRepo",
        (),
        {
            "get_downloader_approval": lambda self, **kwargs: _get_downloader_approval(**kwargs),
            "approve_downloader": lambda self, **kwargs: (_ for _ in ()).throw(AssertionError("approve_downloader should not be called")),
        },
    )()
    service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search_with_download_url),
        add_torrent_func=AsyncMock(),
        approval_repo=approval_repo,
    )
    pending_add = PendingAddContext(
        task_ref="1",
        task_id="selection:1",
        task_hash="abc123",
        title="Dune: Part Two",
        source="https://example.com/dune.torrent",
    )
    service._record_pending_context(chat_id=1001, pending_add=pending_add)
    service._pending_add_identities.add((pending_add.task_id, pending_add.task_hash))
    service._pending_add_lease_versions[(pending_add.task_id, pending_add.task_hash)] = 2

    reply = _run(service.confirm_add_by_task_ref("1", chat_id=1001))

    assert reply == ADD_CONFIRM_STATE_UNAVAILABLE_TEXT
    output = capsys.readouterr().out
    assert "[下载待确认版号查询失败]" in output
    assert "task_id=selection:1" in output
    assert "db down" in output


def test_cancel_pending_add_logs_job_cancel_failure(capsys) -> None:
    pending_job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="add_to_downloader",
        state="pending_approval",
        task_ref="1",
        task_id="selection:1",
        task_hash="abc123",
        payload_json="{\"task_ref\":\"1\",\"task_id\":\"selection:1\",\"task_hash\":\"abc123\",\"title\":\"Dune: Part Two\",\"source\":\"https://example.com/dune.torrent\"}",
        version=3,
        lease_owner="",
        lease_until="",
        created_at="2026-04-15 00:00:00",
        updated_at="2026-04-15 00:00:00",
    )
    job_repo = type(
        "JobRepo",
        (),
        {
            "get_latest_pending_downloader_job": lambda self, chat_id: pending_job,
            "cancel_pending_job": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down")),
        },
    )()
    approval_repo = type("ApprovalRepo", (), {"cancel_downloader": lambda self, **kwargs: True})()
    service = AddToDownloaderService(search_service=SearchMediaService(_fake_search_with_download_url), add_torrent_func=AsyncMock(), job_repo=job_repo, approval_repo=approval_repo)
    service._resolve_pending_lease_version = lambda **kwargs: 2
    assert service.cancel_pending_add(1001) == ADD_CANCEL_STATE_UNAVAILABLE_TEXT
    output = capsys.readouterr().out
    assert "[下载取消任务更新失败]" in output
    assert "job_id=job-1" in output


def test_cancel_pending_add_logs_missing_job_cancel_result(capsys) -> None:
    pending_job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="add_to_downloader",
        state="pending_approval",
        task_ref="1",
        task_id="selection:1",
        task_hash="abc123",
        payload_json="{\"task_ref\":\"1\",\"task_id\":\"selection:1\",\"task_hash\":\"abc123\",\"title\":\"Dune: Part Two\",\"source\":\"https://example.com/dune.torrent\"}",
        version=3,
        lease_owner="",
        lease_until="",
        created_at="2026-04-15 00:00:00",
        updated_at="2026-04-15 00:00:00",
    )
    job_repo = type(
        "JobRepo",
        (),
        {
            "get_latest_pending_downloader_job": lambda self, chat_id: pending_job,
            "cancel_pending_job": lambda self, **kwargs: None,
        },
    )()
    approval_repo = type("ApprovalRepo", (), {"cancel_downloader": lambda self, **kwargs: True})()
    service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search_with_download_url),
        add_torrent_func=AsyncMock(),
        job_repo=job_repo,
        approval_repo=approval_repo,
    )
    service._resolve_pending_lease_version = lambda **kwargs: 2

    assert service.cancel_pending_add(1001) == ADD_CANCEL_STATE_UNAVAILABLE_TEXT

    output = capsys.readouterr().out
    assert "[下载取消任务结果缺失]" in output
    assert "job_id=job-1" in output
    assert "downloader cancel pending job result missing" in output


def test_handle_expired_pending_confirm_logs_job_cancel_failure(capsys) -> None:
    job_repo = type("JobRepo", (), {"cancel_pending_job": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down"))})()
    service = AddToDownloaderService(search_service=SearchMediaService(_fake_search_with_download_url), add_torrent_func=AsyncMock(), job_repo=job_repo)
    service._is_pending_approval_expired = lambda **kwargs: True
    context = ConfirmExecutionContext(
        job=JobRecord(
            job_id="job-1",
            chat_id=1001,
            user_id=2001,
            workflow_type="add_to_downloader",
            state="pending_approval",
            task_ref="1",
            task_id="selection:1",
            task_hash="abc123",
            payload_json="{}",
            version=3,
            lease_owner="",
            lease_until="",
            created_at="2026-04-15 00:00:00",
            updated_at="2026-04-15 00:00:00",
        ),
        approval_record=type("ApprovalRecord", (), {"lease_version": 2})(),
        pending_add=PendingAddContext(
            task_ref="1",
            task_id="selection:1",
            task_hash="abc123",
            title="Dune: Part Two",
            source="https://example.com/dune.torrent",
        ),
    )
    assert service._handle_expired_pending_confirm(task_ref="1", context=context, chat_id=1001) == ADD_CONFIRM_STATE_UNAVAILABLE_TEXT
    output = capsys.readouterr().out
    assert "[下载确认超时任务取消失败]" in output
    assert "job_id=job-1" in output
    assert "当前 confirm 会直接返回状态读取失败" in output


def test_handle_expired_pending_confirm_logs_missing_job_during_cancel(capsys) -> None:
    job_repo = type(
        "JobRepo",
        (),
        {
            "cancel_pending_job": lambda self, **kwargs: (_ for _ in ()).throw(
                RuntimeError("job missing during cancel")
            )
        },
    )()
    service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search_with_download_url),
        add_torrent_func=AsyncMock(),
        job_repo=job_repo,
    )
    service._is_pending_approval_expired = lambda **kwargs: True
    context = ConfirmExecutionContext(
        job=JobRecord(
            job_id="job-1",
            chat_id=1001,
            user_id=2001,
            workflow_type="add_to_downloader",
            state="pending_approval",
            task_ref="1",
            task_id="selection:1",
            task_hash="abc123",
            payload_json="{}",
            version=3,
            lease_owner="",
            lease_until="",
            created_at="2026-04-15 00:00:00",
            updated_at="2026-04-15 00:00:00",
        ),
        approval_record=type("ApprovalRecord", (), {"lease_version": 2})(),
        pending_add=PendingAddContext(
            task_ref="1",
            task_id="selection:1",
            task_hash="abc123",
            title="Dune: Part Two",
            source="https://example.com/dune.torrent",
        ),
    )

    assert service._handle_expired_pending_confirm(task_ref="1", context=context, chat_id=1001) == ADD_CONFIRM_STATE_UNAVAILABLE_TEXT

    output = capsys.readouterr().out
    assert "[下载确认超时任务结果缺失]" in output
    assert "job_id=job-1" in output
    assert "job missing during cancel" in output
    assert "当前 confirm 会直接返回状态读取失败" in output


def test_handle_expired_pending_confirm_logs_job_cancel_state_rejection(capsys) -> None:
    job_repo = type("JobRepo", (), {"cancel_pending_job": lambda self, **kwargs: False})()
    service = AddToDownloaderService(search_service=SearchMediaService(_fake_search_with_download_url), add_torrent_func=AsyncMock(), job_repo=job_repo)
    service._is_pending_approval_expired = lambda **kwargs: True
    context = ConfirmExecutionContext(
        job=JobRecord(
            job_id="job-1",
            chat_id=1001,
            user_id=2001,
            workflow_type="add_to_downloader",
            state="pending_approval",
            task_ref="1",
            task_id="selection:1",
            task_hash="abc123",
            payload_json="{}",
            version=3,
            lease_owner="",
            lease_until="",
            created_at="2026-04-15 00:00:00",
            updated_at="2026-04-15 00:00:00",
        ),
        approval_record=type("ApprovalRecord", (), {"lease_version": 2})(),
        pending_add=PendingAddContext(
            task_ref="1",
            task_id="selection:1",
            task_hash="abc123",
            title="Dune: Part Two",
            source="https://example.com/dune.torrent",
        ),
    )
    assert service._handle_expired_pending_confirm(task_ref="1", context=context, chat_id=1001) == ADD_CONFIRM_STATE_UNAVAILABLE_TEXT
    output = capsys.readouterr().out
    assert "[下载确认超时任务取消失败]" in output
    assert "当前 confirm 会直接返回状态读取失败" in output
    assert "jobs.cancel_pending_job rejected current state" in output


def test_handle_expired_pending_confirm_returns_state_unavailable_when_approval_cancel_fails(capsys) -> None:
    approval_repo = type("ApprovalRepo", (), {"cancel_downloader": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down"))})()
    service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search_with_download_url),
        add_torrent_func=AsyncMock(),
        approval_repo=approval_repo,
    )
    service._is_pending_approval_expired = lambda **kwargs: True
    context = ConfirmExecutionContext(
        job=JobRecord(
            job_id="job-1",
            chat_id=1001,
            user_id=2001,
            workflow_type="add_to_downloader",
            state="pending_approval",
            task_ref="1",
            task_id="selection:1",
            task_hash="abc123",
            payload_json="{}",
            version=3,
            lease_owner="",
            lease_until="",
            created_at="2026-04-15 00:00:00",
            updated_at="2026-04-15 00:00:00",
        ),
        approval_record=type("ApprovalRecord", (), {"lease_version": 2})(),
        pending_add=PendingAddContext(
            task_ref="1",
            task_id="selection:1",
            task_hash="abc123",
            title="Dune: Part Two",
            source="https://example.com/dune.torrent",
        ),
    )

    assert service._handle_expired_pending_confirm(task_ref="1", context=context, chat_id=1001) == ADD_CONFIRM_STATE_UNAVAILABLE_TEXT

    output = capsys.readouterr().out
    assert "[下载取消审批更新失败]" in output
    assert "lease_version=2" in output


def test_cancel_pending_add_logs_job_cancel_state_rejection(capsys) -> None:
    pending_job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="add_to_downloader",
        state="pending_approval",
        task_ref="1",
        task_id="selection:1",
        task_hash="abc123",
        payload_json='{"task_ref":"1","task_id":"selection:1","task_hash":"abc123","title":"Dune: Part Two","source":"https://example.com/dune.torrent","downloader_name":"tr-main","download_dir":"/data/downloads/tr"}',
        version=3,
        lease_owner="",
        lease_until="",
        created_at="2026-04-15 00:00:00",
        updated_at="2026-04-15 00:00:00",
    )
    job_repo = type(
        "JobRepo",
        (),
        {
            "get_latest_pending_downloader_job": lambda self, chat_id: pending_job,
            "cancel_pending_job": lambda self, **kwargs: False,
        },
    )()
    approval_repo = type("ApprovalRepo", (), {"cancel_downloader": lambda self, **kwargs: True})()
    service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search_with_download_url),
        add_torrent_func=AsyncMock(),
        job_repo=job_repo,
        approval_repo=approval_repo,
    )
    service._resolve_pending_lease_version = lambda **kwargs: 2

    assert service.cancel_pending_add(1001) == ADD_CANCEL_STATE_UNAVAILABLE_TEXT

    output = capsys.readouterr().out
    assert "[下载取消任务更新失败]" in output
    assert "jobs.cancel_pending_job rejected current state" in output


def test_cancel_pending_add_returns_state_unavailable_when_approval_cancel_rejected(capsys) -> None:
    pending_job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="add_to_downloader",
        state="pending_approval",
        task_ref="1",
        task_id="selection:1",
        task_hash="abc123",
        payload_json="{\"task_ref\":\"1\",\"task_id\":\"selection:1\",\"task_hash\":\"abc123\",\"title\":\"Dune: Part Two\",\"source\":\"https://example.com/dune.torrent\"}",
        version=3,
        lease_owner="",
        lease_until="",
        created_at="2026-04-15 00:00:00",
        updated_at="2026-04-15 00:00:00",
    )
    job_repo = type("JobRepo", (), {"get_latest_pending_downloader_job": lambda self, chat_id: pending_job})()
    approval_repo = type("ApprovalRepo", (), {"cancel_downloader": lambda self, **kwargs: False})()
    service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search_with_download_url),
        add_torrent_func=AsyncMock(),
        job_repo=job_repo,
        approval_repo=approval_repo,
    )
    service._resolve_pending_lease_version = lambda **kwargs: 2

    assert service.cancel_pending_add(1001) == ADD_CANCEL_STATE_UNAVAILABLE_TEXT

    output = capsys.readouterr().out
    assert "[下载取消审批更新失败]" in output
    assert "approval_record missing or lease_version mismatch" in output


def test_cancel_pending_add_returns_state_unavailable_when_pending_lease_missing(capsys) -> None:
    pending_job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="add_to_downloader",
        state="pending_approval",
        task_ref="1",
        task_id="selection:1",
        task_hash="abc123",
        payload_json="{\"task_ref\":\"1\",\"task_id\":\"selection:1\",\"task_hash\":\"abc123\",\"title\":\"Dune: Part Two\",\"source\":\"https://example.com/dune.torrent\"}",
        version=3,
        lease_owner="",
        lease_until="",
        created_at="2026-04-15 00:00:00",
        updated_at="2026-04-15 00:00:00",
    )
    job_repo = type("JobRepo", (), {"get_latest_pending_downloader_job": lambda self, chat_id: pending_job})()
    service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search_with_download_url),
        add_torrent_func=AsyncMock(),
        job_repo=job_repo,
    )
    service._resolve_pending_lease_version = lambda **kwargs: 0

    assert service.cancel_pending_add(1001) == ADD_CANCEL_STATE_UNAVAILABLE_TEXT

    output = capsys.readouterr().out
    assert "[下载取消状态读取失败]" in output
    assert "downloader approval pending lease missing" in output


def test_cancel_pending_add_returns_state_unavailable_when_pending_lease_lookup_fails_with_in_memory_pending(
    capsys,
) -> None:
    approval_repo = type(
        "ApprovalRepo",
        (),
        {
            "get_downloader_approval": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down")),
            "cancel_downloader": lambda self, **kwargs: (_ for _ in ()).throw(AssertionError("cancel_downloader should not be called")),
        },
    )()
    job_repo = type(
        "JobRepo",
        (),
        {
            "get_latest_pending_downloader_job": lambda self, chat_id: None,
            "cancel_pending_job": lambda self, **kwargs: (_ for _ in ()).throw(AssertionError("cancel_pending_job should not be called")),
        },
    )()
    service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search_with_download_url),
        add_torrent_func=AsyncMock(),
        approval_repo=approval_repo,
        job_repo=job_repo,
    )
    pending_add = PendingAddContext(
        task_ref="1",
        task_id="selection:1",
        task_hash="abc123",
        title="Dune: Part Two",
        source="https://example.com/dune.torrent",
    )
    service._record_pending_context(chat_id=1001, pending_add=pending_add)
    service._pending_add_identities.add((pending_add.task_id, pending_add.task_hash))
    service._pending_add_lease_versions[(pending_add.task_id, pending_add.task_hash)] = 2

    assert service.cancel_pending_add(1001) == ADD_CANCEL_STATE_UNAVAILABLE_TEXT

    output = capsys.readouterr().out
    assert "[下载待确认版号查询失败]" in output
    assert "[下载取消状态读取失败]" in output
    assert "downloader approval pending lease lookup failed" in output


def test_cancel_pending_add_returns_state_unavailable_when_pending_approval_row_missing_with_in_memory_pending(
    capsys,
) -> None:
    approval_repo = type(
        "ApprovalRepo",
        (),
        {
            "get_downloader_approval": lambda self, **kwargs: None,
            "cancel_downloader": lambda self, **kwargs: (_ for _ in ()).throw(AssertionError("cancel_downloader should not be called")),
        },
    )()
    job_repo = type(
        "JobRepo",
        (),
        {
            "get_latest_pending_downloader_job": lambda self, chat_id: None,
            "cancel_pending_job": lambda self, **kwargs: (_ for _ in ()).throw(AssertionError("cancel_pending_job should not be called")),
        },
    )()
    service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search_with_download_url),
        add_torrent_func=AsyncMock(),
        approval_repo=approval_repo,
        job_repo=job_repo,
    )
    pending_add = PendingAddContext(
        task_ref="1",
        task_id="selection:1",
        task_hash="abc123",
        title="Dune: Part Two",
        source="https://example.com/dune.torrent",
    )
    service._record_pending_context(chat_id=1001, pending_add=pending_add)
    service._pending_add_identities.add((pending_add.task_id, pending_add.task_hash))
    service._pending_add_lease_versions[(pending_add.task_id, pending_add.task_hash)] = 2

    assert service.cancel_pending_add(1001) == ADD_CANCEL_STATE_UNAVAILABLE_TEXT

    output = capsys.readouterr().out
    assert "[下载待确认版号查询失败]" in output
    assert "approval_record missing while in-memory pending exists" in output
    assert "[下载取消状态读取失败]" in output
    assert "downloader approval pending lease lookup failed" in output


def test_add_by_selection_without_cached_candidates() -> None:
    search_service = SearchMediaService(_fake_search_with_download_url)
    add_torrent = AsyncMock()
    service = AddToDownloaderService(search_service=search_service, add_torrent_func=add_torrent)

    reply = _run(service.add_by_selection(1001, "1"))
    assert reply == SELECT_NOT_FOUND_TEXT
    add_torrent.assert_not_called()


def test_add_by_selection_out_of_range() -> None:
    search_service = SearchMediaService(_fake_search_with_download_url)
    _run(search_service.search_and_format("dune", chat_id=1001))
    add_torrent = AsyncMock()
    service = AddToDownloaderService(search_service=search_service, add_torrent_func=add_torrent)

    reply = _run(service.add_by_selection(1001, "2"))
    assert reply == SELECT_OUT_OF_RANGE_TEXT
    add_torrent.assert_not_called()


def test_add_by_selection_returns_lookup_failed_when_candidate_lookup_fails() -> None:
    failing_repo = type(
        "BoomRepo",
        (),
        {"get_candidate": lambda self, chat_id, index: (_ for _ in ()).throw(RuntimeError("db down"))},
    )()
    add_torrent = AsyncMock()
    service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search_with_download_url, candidate_repo=failing_repo),
        add_torrent_func=add_torrent,
    )

    reply = _run(service.add_by_selection(1001, "1"))

    assert reply == SELECT_LOOKUP_FAILED_TEXT
    add_torrent.assert_not_called()


def test_add_by_selection_returns_lookup_failed_when_range_probe_fails() -> None:
    class PartialRepo:
        def get_candidate(self, chat_id: int, index: int):
            _ = chat_id
            if index == 2:
                return None
            raise RuntimeError("db down")

    add_torrent = AsyncMock()
    service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search_with_download_url, candidate_repo=PartialRepo()),
        add_torrent_func=add_torrent,
    )

    reply = _run(service.add_by_selection(1001, "2"))

    assert reply == SELECT_LOOKUP_FAILED_TEXT
    add_torrent.assert_not_called()


def test_add_by_selection_invalid_index() -> None:
    search_service = SearchMediaService(_fake_search_with_download_url)
    add_torrent = AsyncMock()
    service = AddToDownloaderService(search_service=search_service, add_torrent_func=add_torrent)

    reply = _run(service.add_by_selection(1001, "x"))
    assert reply == SELECT_USAGE_TEXT
    add_torrent.assert_not_called()


def test_add_by_selection_missing_source() -> None:
    search_service = SearchMediaService(_fake_search_without_source)
    _run(search_service.search_and_format("dune", chat_id=1001))
    add_torrent = AsyncMock()
    service = AddToDownloaderService(search_service=search_service, add_torrent_func=add_torrent)

    reply = _run(service.add_by_selection(1001, "1"))
    assert reply == CANDIDATE_SOURCE_MISSING_TEXT
    add_torrent.assert_not_called()


def test_confirm_add_by_task_ref_returns_failed_when_downloader_errors() -> None:
    search_service = SearchMediaService(_fake_search_with_download_url)
    _run(search_service.search_and_format("dune", chat_id=1001))
    add_torrent = AsyncMock(side_effect=RuntimeError("boom"))
    service = AddToDownloaderService(search_service=search_service, add_torrent_func=add_torrent)

    _run(service.add_by_selection(1001, "1"))
    reply = _run(service.confirm_add_by_task_ref("1", chat_id=1001))

    assert reply == ADD_FAILED_TEXT


def test_confirm_add_by_task_ref_appends_warning_when_executed_version_write_fails(
    capsys: pytest.CaptureFixture[str],
) -> None:
    job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="add_to_downloader",
        state="pending_approval",
        task_ref="1",
        task_id="selection:1",
        task_hash="abc123",
        payload_json="{\"task_ref\":\"1\",\"task_id\":\"selection:1\",\"task_hash\":\"abc123\",\"title\":\"Dune: Part Two\",\"source\":\"https://example.com/dune.torrent\"}",
        version=3,
        lease_owner="",
        lease_until="",
        created_at="2026-04-15 00:00:00",
        updated_at="2026-04-15 00:00:00",
    )
    approval_record = type("ApprovalRecord", (), {"status": "pending", "lease_version": 2, "executed_version": 0})()
    job_repo = type(
        "JobRepo",
        (),
        {
            "get_downloader_job_for_chat_ref": lambda self, **kwargs: job,
            "claim_lease": lambda self, **kwargs: True,
            "mark_downloader_completed": lambda self, **kwargs: True,
        },
    )()
    approval_repo = type(
        "ApprovalRepo",
        (),
        {
            "get_downloader_approval": lambda self, **kwargs: approval_record,
            "is_downloader_pending_expired": lambda self, **kwargs: False,
            "approve_downloader": lambda self, **kwargs: True,
            "mark_downloader_executed": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down")),
        },
    )()
    add_torrent = AsyncMock(return_value=TransmissionTask(task_id="42", task_hash="hash-42"))
    service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search_with_download_url),
        add_torrent_func=add_torrent,
        job_repo=job_repo,
        approval_repo=approval_repo,
    )

    reply = _run(service.confirm_add_by_task_ref("1", chat_id=1001))

    assert "已添加下载：Dune: Part Two" in reply
    assert ADD_FINALIZATION_WARNING_TEXT in reply
    output = capsys.readouterr().out
    assert "[下载执行版号回写失败]" in output
    assert "db down" in output


def test_confirm_add_by_task_ref_appends_warning_when_job_completion_write_fails(
    capsys: pytest.CaptureFixture[str],
) -> None:
    job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="add_to_downloader",
        state="pending_approval",
        task_ref="1",
        task_id="selection:1",
        task_hash="abc123",
        payload_json="{\"task_ref\":\"1\",\"task_id\":\"selection:1\",\"task_hash\":\"abc123\",\"title\":\"Dune: Part Two\",\"source\":\"https://example.com/dune.torrent\"}",
        version=3,
        lease_owner="",
        lease_until="",
        created_at="2026-04-15 00:00:00",
        updated_at="2026-04-15 00:00:00",
    )
    approval_record = type("ApprovalRecord", (), {"status": "pending", "lease_version": 2, "executed_version": 0})()
    job_repo = type(
        "JobRepo",
        (),
        {
            "get_downloader_job_for_chat_ref": lambda self, **kwargs: job,
            "claim_lease": lambda self, **kwargs: True,
            "mark_downloader_completed": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down")),
        },
    )()
    approval_repo = type(
        "ApprovalRepo",
        (),
        {
            "get_downloader_approval": lambda self, **kwargs: approval_record,
            "is_downloader_pending_expired": lambda self, **kwargs: False,
            "approve_downloader": lambda self, **kwargs: True,
            "mark_downloader_executed": lambda self, **kwargs: None,
        },
    )()
    add_torrent = AsyncMock(return_value=TransmissionTask(task_id="42", task_hash="hash-42"))
    service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search_with_download_url),
        add_torrent_func=add_torrent,
        job_repo=job_repo,
        approval_repo=approval_repo,
    )

    reply = _run(service.confirm_add_by_task_ref("1", chat_id=1001))

    assert "已添加下载：Dune: Part Two" in reply
    assert ADD_FINALIZATION_WARNING_TEXT in reply
    output = capsys.readouterr().out
    assert "[下载确认任务完结失败]" in output
    assert "db down" in output


@pytest.mark.parametrize(
    ("restore_mode", "expected_label", "expected_error"),
    [
        ("raise", "[下载审批回退失败]", "db down"),
        ("missing", "[下载审批回退结果缺失]", "downloader restore pending approval result missing"),
        ("missing_row", "[下载审批回退结果缺失]", "approval_record missing during restore"),
        ("reject", "[下载审批回退失败]", "approval_record restore rejected current state"),
    ],
)
def test_confirm_add_by_task_ref_returns_state_unavailable_when_dispatch_failure_cannot_restore_pending_approval(
    restore_mode: str,
    expected_label: str,
    expected_error: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class BrokenRestoreApprovalRepo:
        def request_downloader_approval(self, **_: object) -> int:
            return 1

        def get_downloader_approval(self, **_: object):
            return type(
                "ApprovalRecord",
                (),
                {"status": "pending", "lease_version": 1, "executed_version": 0},
            )()

        def approve_downloader(self, **_: object) -> bool:
            return True

        def restore_downloader_pending(self, **_: object) -> bool:
            if restore_mode == "raise":
                raise RuntimeError("db down")
            if restore_mode == "missing":
                return None
            if restore_mode == "missing_row":
                raise RuntimeError("approval_record missing during restore")
            return False

    search_service = SearchMediaService(_fake_search_with_download_url)
    _run(search_service.search_and_format("dune", chat_id=1001))
    add_torrent = AsyncMock(side_effect=RuntimeError("boom"))
    service = AddToDownloaderService(
        search_service=search_service,
        add_torrent_func=add_torrent,
        approval_repo=BrokenRestoreApprovalRepo(),
    )

    _run(service.add_by_selection(1001, "1"))
    reply = _run(service.confirm_add_by_task_ref("1", chat_id=1001))

    assert reply == ADD_CONFIRM_STATE_UNAVAILABLE_TEXT
    add_torrent.assert_awaited_once()
    output = capsys.readouterr().out
    assert expected_label in output
    assert expected_error in output


def test_confirm_add_by_task_ref_rejects_expired_pending(tmp_path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    search_service = SearchMediaService(
        _fake_search_with_download_url,
        candidate_repo=CandidateMappingRepo(database),
    )
    _run(search_service.search_and_format("dune", chat_id=1001))
    add_torrent = AsyncMock(return_value=TransmissionTask(task_id="42", task_hash="abc123"))
    service = AddToDownloaderService(
        search_service=search_service,
        add_torrent_func=add_torrent,
        approval_repo=ApprovalRepo(database),
        job_repo=JobRepo(database),
    )

    pending_reply = _run(service.add_by_selection(1001, "1", user_id=2001))
    assert pending_reply == ADD_APPROVAL_PENDING_TEXT.format(title="Dune: Part Two", task_ref="1")

    with database.connect() as connection:
        connection.execute(
            """
            UPDATE approval_record
            SET expires_at = '2000-01-01 00:00:00'
            WHERE action_type = 'add_to_downloader' AND task_id = 'selection:1'
            """
        )
        connection.commit()

    confirm_reply = _run(service.confirm_add_by_task_ref("1", chat_id=1001, user_id=2001))
    assert confirm_reply == ADD_CONFIRM_EXPIRED_TEXT
    add_torrent.assert_not_awaited()

    job = JobRepo(database).get_downloader_job_for_chat_ref(chat_id=1001, task_ref="1")
    assert job is not None
    assert job.state == JOB_STATE_CANCELLED

    record = ApprovalRepo(database).get_downloader_approval(
        task_id=job.task_id,
        task_hash=job.task_hash,
    )
    assert record is not None
    assert record.status == APPROVAL_STATUS_CANCELLED


def test_confirm_add_by_task_ref_registers_download_monitor_truth(tmp_path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    search_service = SearchMediaService(
        _fake_search_with_download_url,
        candidate_repo=CandidateMappingRepo(database),
    )
    _run(search_service.search_and_format("dune", chat_id=1001))

    add_torrent = AsyncMock(return_value=TransmissionTask(task_id="42", task_hash="abc123"))
    monitor_repo = DownloadMonitorRepo(database)
    service = AddToDownloaderService(
        search_service=search_service,
        add_torrent_func=add_torrent,
        download_monitor_repo=monitor_repo,
    )

    _run(service.add_by_selection(1001, "1"))
    confirm_reply = _run(service.confirm_add_by_task_ref("1", chat_id=1001, user_id=2001))

    assert "任务 ID: 42" in confirm_reply
    record = monitor_repo.get_record(task_id="42", task_hash="abc123")
    assert record is not None
    assert record.name == "Dune: Part Two"
    assert record.chat_id == 1001
    assert record.user_id == 2001
    assert record.is_complete is False
    pending_records = monitor_repo.list_pending_completion()
    assert len(pending_records) == 1
    assert pending_records[0].task_hash == "abc123"


def _run(coroutine: Awaitable[str]) -> str:
    return asyncio.run(coroutine)

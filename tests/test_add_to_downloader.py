from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from unittest.mock import AsyncMock

from app.clients.transmission import TransmissionTask
from app.db.approval_repo import APPROVAL_STATUS_CANCELLED, ApprovalRepo
from app.db.candidate_repo import CandidateMappingRepo
from app.db.download_monitor_repo import DownloadMonitorRepo
from app.db.job_repo import JOB_STATE_CANCELLED, JobRepo
from app.db.sqlite import SqliteDatabase
from app.services.add_to_downloader import (
    ADD_APPROVAL_PENDING_TEXT,
    ADD_CONFIRM_EXPIRED_TEXT,
    ADD_CONFIRM_NOT_PENDING_TEXT,
    ADD_FAILED_TEXT,
    CANDIDATE_SOURCE_MISSING_TEXT,
    SELECT_NOT_FOUND_TEXT,
    SELECT_OUT_OF_RANGE_TEXT,
    SELECT_USAGE_TEXT,
    AddToDownloaderService,
)
from app.services.search_media import SearchMediaService


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
    assert service.has_pending_add(1001, "1") is False
    assert "[下载待确认查询失败]" in capsys.readouterr().out


def test_cancel_pending_add_logs_job_lookup_failure(capsys) -> None:
    job_repo = type("BoomJobRepo", (), {"get_latest_pending_downloader_job": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down"))})()
    service = AddToDownloaderService(search_service=SearchMediaService(_fake_search_with_download_url), add_torrent_func=AsyncMock(), job_repo=job_repo)
    assert service.cancel_pending_add(1001) is None
    assert "[下载取消查询失败]" in capsys.readouterr().out


def test_rebuild_confirm_context_logs_job_lookup_failure(capsys) -> None:
    job_repo = type("BoomJobRepo", (), {"get_downloader_job_for_chat_ref": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down"))})()
    service = AddToDownloaderService(search_service=SearchMediaService(_fake_search_with_download_url), add_torrent_func=AsyncMock(), job_repo=job_repo)
    assert service._rebuild_confirm_context(task_ref="1", chat_id=1001) is None
    assert "[下载确认上下文查询失败]" in capsys.readouterr().out


def test_rebuild_confirm_context_logs_approval_lookup_failure(capsys) -> None:
    job = type("Job", (), {"payload_json": "{\"task_ref\":\"1\",\"task_id\":\"selection:1\",\"task_hash\":\"abc123\",\"title\":\"Dune: Part Two\",\"source\":\"https://example.com/dune.torrent\"}", "task_id": "selection:1", "task_hash": "abc123"})()
    job_repo = type("JobRepo", (), {"get_downloader_job_for_chat_ref": lambda self, **kwargs: job})()
    approval_repo = type("ApprovalRepo", (), {"get_downloader_approval": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down"))})()
    service = AddToDownloaderService(search_service=SearchMediaService(_fake_search_with_download_url), add_torrent_func=AsyncMock(), job_repo=job_repo, approval_repo=approval_repo)
    assert service._rebuild_confirm_context(task_ref="1", chat_id=1001).approval_record is None
    assert "[下载确认审批查询失败]" in capsys.readouterr().out


def test_record_pending_approval_logs_persistence_failure(capsys) -> None:
    approval_repo = type("ApprovalRepo", (), {"request_downloader_approval": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down"))})()
    service = AddToDownloaderService(search_service=SearchMediaService(_fake_search_with_download_url), add_torrent_func=AsyncMock(), approval_repo=approval_repo)
    assert service._record_pending_approval(task_ref="1", task_id="selection:1", task_hash="abc123") == 1
    assert "[下载待确认审批落盘失败]" in capsys.readouterr().out


def test_record_downloader_approval_logs_persistence_failure(capsys) -> None:
    approval_repo = type("ApprovalRepo", (), {"approve_downloader": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down"))})()
    service = AddToDownloaderService(search_service=SearchMediaService(_fake_search_with_download_url), add_torrent_func=AsyncMock(), approval_repo=approval_repo)
    service._pending_add_identities.add(("selection:1", "abc123"))
    service._pending_add_lease_versions[("selection:1", "abc123")] = 1
    assert service._record_downloader_approval(task_ref="1", task_id="selection:1", task_hash="abc123", expected_lease_version=1) is True
    assert "[下载确认审批更新失败]" in capsys.readouterr().out


def test_cancel_pending_approval_logs_persistence_failure(capsys) -> None:
    approval_repo = type("ApprovalRepo", (), {"cancel_downloader": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("db down"))})()
    service = AddToDownloaderService(search_service=SearchMediaService(_fake_search_with_download_url), add_torrent_func=AsyncMock(), approval_repo=approval_repo)
    assert service._cancel_pending_approval(task_ref="1", task_id="selection:1", task_hash="abc123", expected_lease_version=1) is False
    assert "[下载取消审批更新失败]" in capsys.readouterr().out


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

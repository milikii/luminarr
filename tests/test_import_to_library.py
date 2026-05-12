from __future__ import annotations

import asyncio
import errno
import json
import sqlite3
from collections.abc import Awaitable
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

import app.services.import_prepare_state as import_prepare_module
import app.services.import_to_library as import_module
from app.clients.transmission import TransmissionImportSource
from app.db.approval_repo import (
    APPROVAL_STATUS_APPROVED,
    APPROVAL_STATUS_CANCELLED,
    APPROVAL_STATUS_PENDING,
    ApprovalPersistenceError,
    ApprovalRepo,
)
from app.db.job_event_repo import JobEventPersistenceError, JobEventRepo
from app.db.job_repo import (
    JOB_STATE_CANCELLED,
    JOB_STATE_PENDING_APPROVAL,
    WORKFLOW_IMPORT_TO_LIBRARY,
    JobPersistenceError,
    JobRecord,
    JobRepo,
)
from app.db.sqlite import SqliteDatabase
from app.downloader_route_lookup import DownloaderRouteLookupError
from app.services.import_to_library import (
    CONFIRM_QUERY_USAGE_TEXT,
    IMPORT_CANCEL_STATE_UNAVAILABLE_TEXT,
    IMPORT_CONFIRM_EXPIRED_TEXT,
    IMPORT_CONFIRM_NOT_PENDING_TEXT,
    IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT,
    IMPORT_COPY_APPROVAL_PENDING_TEXT,
    IMPORT_COPY_FAILED_TEXT,
    IMPORT_FINALIZATION_WARNING_TEXT,
    IMPORT_HARDLINK_FAILED_TEXT,
    IMPORT_NOT_COMPLETED_TEXT,
    IMPORT_NOT_FOUND_TEXT,
    IMPORT_PENDING_STATE_UNAVAILABLE_TEXT,
    IMPORT_QUERY_FAILED_TEXT,
    IMPORT_REFRESH_FAILED_TEXT,
    IMPORT_SOURCE_MISSING_TEXT,
    ConfirmExecutionContext,
    ImportToLibraryService,
    PreparedImport,
    parse_confirm_query,
    parse_import_query,
)
from app.services.media_identity import MEDIA_IDENTITY_EVENT_TYPE, media_identity_to_json
from app.services.metadata_scraper import MetadataScrapeInput, MetadataScrapeResult
from app.services.subtitle_translator import SubtitleTranslateInput, SubtitleTranslateResult
from app.trace_logging import parse_trace_log_line


def test_parse_import_query_supports_import_prefix() -> None:
    assert parse_import_query("import 87") == "87"
    assert parse_import_query("IMPORT abc123") == "abc123"
    assert parse_import_query("导入 b305bf") == "b305bf"
    assert parse_import_query("import") == ""


def test_parse_import_query_rejects_non_import_text() -> None:
    assert parse_import_query("status 87") is None
    assert parse_import_query("dune") is None


def test_parse_confirm_query_supports_confirm_prefix() -> None:
    assert parse_confirm_query("confirm 87") == "87"
    assert parse_confirm_query("CONFIRM abc123") == "abc123"
    assert parse_confirm_query("确认 b305bf") == "b305bf"
    assert parse_confirm_query("confirm") == ""


def test_parse_confirm_query_rejects_non_confirm_text() -> None:
    assert parse_confirm_query("import 87") is None
    assert parse_confirm_query("dune") is None


def test_import_by_task_ref_returns_pending_for_file(tmp_path: Path) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    target_dir = tmp_path / "library"
    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    service = ImportToLibraryService(AsyncMock(return_value=import_source), str(target_dir))

    text = _run(service.import_by_task_ref("87"))
    assert "导入待确认" in text
    assert "请发送 confirm 87" in text
    assert text.startswith("导入待确认：")
    assert not (target_dir / source_file.name).exists()


def test_confirm_import_by_task_ref_executes_after_pending(tmp_path: Path) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    target_dir = tmp_path / "library"
    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    service = ImportToLibraryService(AsyncMock(return_value=import_source), str(target_dir))

    pending_text = _run(service.import_by_task_ref("87"))
    assert "导入待确认" in pending_text

    text = _run(service.confirm_import_by_task_ref("87"))
    assert "导入成功" in text


def test_import_by_task_ref_with_auto_confirm_executes_without_pending_reply(tmp_path: Path) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    target_dir = tmp_path / "library"
    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    service = ImportToLibraryService(
        AsyncMock(return_value=import_source),
        str(target_dir),
        refresh_media_server_func=AsyncMock(return_value="媒体库刷新成功。"),
    )

    text = _run(service.import_by_task_ref_with_auto_confirm("87"))

    assert "导入成功" in text
    assert "导入待确认" not in text
    assert "后处理总结" in text
    assert "目标路径:" in text


def test_confirm_import_by_task_ref_hardlinks_matching_external_subtitles(tmp_path: Path) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")
    source_en_subtitle = download_dir / "Dune.2021.en.srt"
    source_en_subtitle.write_text("1\n00:00:01,000 --> 00:00:03,000\nhello dune\n", encoding="utf-8")
    source_zh_subtitle = download_dir / "Dune.2021.zh.ass"
    source_zh_subtitle.write_text("[Script Info]\nTitle: demo\n", encoding="utf-8")

    target_dir = tmp_path / "library"
    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    service = ImportToLibraryService(AsyncMock(return_value=import_source), str(target_dir))

    _run(service.import_by_task_ref("87"))
    text = _run(service.confirm_import_by_task_ref("87"))

    assert "导入成功" in text
    target_file = target_dir / "Dune (2021).mkv"
    target_en_subtitle = target_dir / "Dune (2021).en.srt"
    target_zh_subtitle = target_dir / "Dune (2021).zh.ass"
    assert target_file.exists()
    assert target_en_subtitle.exists()
    assert target_zh_subtitle.exists()
    assert source_file.stat().st_ino == target_file.stat().st_ino
    assert source_en_subtitle.stat().st_ino == target_en_subtitle.stat().st_ino
    assert source_zh_subtitle.stat().st_ino == target_zh_subtitle.stat().st_ino


def test_import_workflow_writes_trace_log_when_configured(tmp_path: Path) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    target_dir = tmp_path / "library"
    log_path = tmp_path / "trace.log"
    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    service = ImportToLibraryService(
        AsyncMock(return_value=import_source),
        str(target_dir),
        trace_log_path=log_path,
    )

    _run(service.import_by_task_ref("87", chat_id=1001, user_id=2001))
    _run(service.confirm_import_by_task_ref("87", chat_id=1001, user_id=2001))

    lines = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    parsed_entries = [parse_trace_log_line(line) for line in lines]

    assert [entry.event if entry is not None else None for entry in parsed_entries] == [
        "approval_pending",
        "confirm_execute",
        "confirm_finalize",
    ]
    assert parsed_entries[0] is not None
    assert parsed_entries[0].workflow == "import_to_library"
    assert parsed_entries[0].task_hash == "hash-87"
    assert parsed_entries[1] is not None
    assert parsed_entries[1].result == "imported"


def test_confirm_import_records_structured_asset_correlation(tmp_path: Path) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    target_dir = tmp_path / "library"
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    event_repo = JobEventRepo(database)
    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    service = ImportToLibraryService(
        get_import_source_func=AsyncMock(return_value=import_source),
        library_target_dir=str(target_dir),
        job_event_repo=event_repo,
    )

    _run(service.import_by_task_ref("87"))
    text = _run(service.confirm_import_by_task_ref("87"))

    assert "导入成功" in text
    correlation = event_repo.find_latest_import_correlation(task_ref="87")
    assert correlation is not None
    assert correlation.source_path == str(source_file)
    assert correlation.target_path == str(target_dir / "Dune (2021).mkv")


def test_confirm_import_by_task_ref_requires_pending(tmp_path: Path) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    service = ImportToLibraryService(AsyncMock(return_value=import_source), str(tmp_path / "library"))

    text = _run(service.confirm_import_by_task_ref("87"))
    assert text == IMPORT_CONFIRM_NOT_PENDING_TEXT


def test_confirm_import_by_task_ref_usage_when_empty() -> None:
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies")
    text = _run(service.confirm_import_by_task_ref("  "))
    assert text == CONFIRM_QUERY_USAGE_TEXT


def test_rebuild_confirm_context_logs_job_lookup_failure(capsys) -> None:
    job_repo = type(
        "JobRepo",
        (),
        {"get_import_job_for_chat_ref": lambda self, **kwargs: (_ for _ in ()).throw(JobPersistenceError("db down"))},
    )()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", job_repo=job_repo)
    context, lookup_failed = service._rebuild_confirm_context(task_ref="87", chat_id=1001)
    assert context is None
    assert lookup_failed is True
    assert "[导入确认上下文查询失败]" in capsys.readouterr().out


def test_rebuild_confirm_context_logs_approval_lookup_failure(capsys) -> None:
    job = type(
        "Job",
        (),
        {
            "job_id": "job-1",
            "task_ref": "87",
            "task_id": "87",
            "task_hash": "hash-87",
            "version": 3,
            "state": "pending_approval",
        },
    )()
    job_repo = type("JobRepo", (), {"get_import_job_for_chat_ref": lambda self, **kwargs: job})()
    approval_repo = type(
        "ApprovalRepo",
        (),
        {"get_import_approval": lambda self, **kwargs: (_ for _ in ()).throw(ApprovalPersistenceError("db down"))},
    )()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", job_repo=job_repo, approval_repo=approval_repo)
    context, lookup_failed = service._rebuild_confirm_context(task_ref="87", chat_id=1001)
    assert context is not None
    assert lookup_failed is False
    assert context.approval_record is None
    assert context.approval_lookup_failed is True
    output = capsys.readouterr().out
    assert "[导入确认审批查询失败]" in output
    assert "当前 confirm 会直接返回状态读取失败" in output


def test_confirm_import_by_task_ref_returns_state_unavailable_on_context_lookup_failure(
    capsys: pytest.CaptureFixture[str],
) -> None:
    job_repo = type("JobRepo", (), {"get_import_job_for_chat_ref": lambda self, **kwargs: (_ for _ in ()).throw(sqlite3.OperationalError("db down"))})()
    get_import_source = AsyncMock(return_value=None)
    service = ImportToLibraryService(get_import_source, "/data/library/movies", job_repo=job_repo)

    text = _run(service.confirm_import_by_task_ref("87", chat_id=1001))

    assert text == IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT
    get_import_source.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[导入确认上下文查询失败]" in output
    assert "chat_id=1001" in output
    assert "task_ref=87" in output


def test_confirm_import_by_task_ref_returns_state_unavailable_on_context_row_corruption(
    capsys: pytest.CaptureFixture[str],
) -> None:
    job_repo = type(
        "JobRepo",
        (),
        {
            "get_import_job_for_chat_ref": lambda self, **kwargs: (_ for _ in ()).throw(
                JobPersistenceError("job row identity corrupted after read")
            )
        },
    )()
    get_import_source = AsyncMock(return_value=None)
    service = ImportToLibraryService(get_import_source, "/data/library/movies", job_repo=job_repo)

    text = _run(service.confirm_import_by_task_ref("87", chat_id=1001))

    assert text == IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT
    get_import_source.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[导入确认上下文记录损坏]" in output
    assert "chat_id=1001" in output
    assert "task_ref=87" in output
    assert "job row identity corrupted after read" in output
    assert "[处理建议]" in output


@pytest.mark.parametrize(
    ("payload_json", "expected_summary"),
    [
        ("", "payload_json empty"),
        ("{", "payload_json invalid json"),
        ("[]", "payload_json not object"),
    ],
)
def test_is_raw_bt_task_logs_payload_corruption(
    payload_json: str,
    expected_summary: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    job = type("Job", (), {"payload_json": payload_json})()
    job_repo = type("JobRepo", (), {"get_downloader_job_for_chat_ref": lambda self, **kwargs: job})()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", job_repo=job_repo)

    assert service._is_raw_bt_task(chat_id=1001, task_ref="87") is None

    output = capsys.readouterr().out
    assert "[导入 raw_bt 判定载荷损坏]" in output
    assert "chat_id=1001" in output
    assert "task_ref=87" in output
    assert expected_summary in output
    assert "[处理建议]" in output


def test_import_by_task_ref_returns_query_failed_when_raw_bt_lookup_fails(capsys: pytest.CaptureFixture[str]) -> None:
    job_repo = type(
        "JobRepo",
        (),
        {"get_downloader_job_for_chat_ref": lambda self, **kwargs: (_ for _ in ()).throw(JobPersistenceError("db down"))},
    )()
    get_import_source = AsyncMock()
    service = ImportToLibraryService(get_import_source, "/data/library/movies", job_repo=job_repo)

    text = _run(service.import_by_task_ref("87", chat_id=1001))

    assert text == IMPORT_QUERY_FAILED_TEXT
    get_import_source.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[导入 raw_bt 判定查询失败]" in output
    assert "task_ref=87" in output
    assert "当前请求会直接返回查询失败" in output


def test_is_raw_bt_task_treats_missing_job_as_not_raw_bt(capsys: pytest.CaptureFixture[str]) -> None:
    job_repo = type("JobRepo", (), {"get_downloader_job_for_chat_ref": lambda self, **kwargs: None})()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", job_repo=job_repo)

    assert service._is_raw_bt_task(chat_id=1001, task_ref="87") is False
    assert capsys.readouterr().out == ""


def test_is_raw_bt_task_logs_row_corruption(capsys: pytest.CaptureFixture[str]) -> None:
    job_repo = type(
        "JobRepo",
        (),
        {
            "get_downloader_job_for_chat_ref": lambda self, **kwargs: (_ for _ in ()).throw(
                JobPersistenceError("job row identity corrupted after read")
            )
        },
    )()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", job_repo=job_repo)

    assert service._is_raw_bt_task(chat_id=1001, task_ref="87") is None

    output = capsys.readouterr().out
    assert "[导入 raw_bt 判定记录损坏]" in output
    assert "chat_id=1001" in output
    assert "task_ref=87" in output
    assert "job row identity corrupted after read" in output
    assert "[处理建议]" in output


def test_import_by_task_ref_allows_pending_when_raw_bt_job_result_is_missing(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()

    class MissingDownloaderJobRepo(JobRepo):
        def get_downloader_job_for_chat_ref(self, *, chat_id: int, task_ref: str):
            _ = chat_id, task_ref
            return None

    job_repo = MissingDownloaderJobRepo(database)
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")
    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    get_import_source = AsyncMock(return_value=import_source)
    service = ImportToLibraryService(get_import_source, str(tmp_path / "library"), job_repo=job_repo)

    text = _run(service.import_by_task_ref("87", chat_id=1001))

    assert "导入待确认" in text
    get_import_source.assert_awaited_once_with("87", 1001)


def test_import_by_task_ref_returns_query_failed_when_raw_bt_payload_is_corrupted(
    capsys: pytest.CaptureFixture[str],
) -> None:
    job = type("Job", (), {"payload_json": "{"})()
    job_repo = type("JobRepo", (), {"get_downloader_job_for_chat_ref": lambda self, **kwargs: job})()
    get_import_source = AsyncMock()
    service = ImportToLibraryService(get_import_source, "/data/library/movies", job_repo=job_repo)

    text = _run(service.import_by_task_ref("87", chat_id=1001))

    assert text == IMPORT_QUERY_FAILED_TEXT
    get_import_source.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[导入 raw_bt 判定载荷损坏]" in output
    assert "payload_json invalid json" in output
    assert "当前请求会直接返回查询失败" in output


def test_claim_pending_job_logs_persistence_failure(capsys) -> None:
    job_repo = type("JobRepo", (), {"claim_lease": lambda self, **kwargs: (_ for _ in ()).throw(sqlite3.OperationalError("db down"))})()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", job_repo=job_repo)
    job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="import_to_library",
        state="pending_approval",
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        payload_json="{}",
        version=3,
        lease_owner="",
        lease_until="",
        created_at="2026-04-15 00:00:00",
        updated_at="2026-04-15 00:00:00",
    )
    assert service._claim_pending_job(job=job, lease_owner="import_confirm:87") is None
    output = capsys.readouterr().out
    assert "[导入确认任务抢占失败]" in output
    assert "job_id=job-1" in output
    assert "当前 confirm 会直接返回状态读取失败" in output


def test_claim_pending_job_logs_missing_result(capsys) -> None:
    job_repo = type(
        "JobRepo",
        (),
        {
            "claim_lease": lambda self, **kwargs: (
                _ for _ in ()
            ).throw(JobPersistenceError("job missing during lease claim"))
        },
    )()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", job_repo=job_repo)
    job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="import_to_library",
        state="pending_approval",
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        payload_json="{}",
        version=3,
        lease_owner="",
        lease_until="",
        created_at="2026-04-15 00:00:00",
        updated_at="2026-04-15 00:00:00",
    )
    assert service._claim_pending_job(job=job, lease_owner="import_confirm:87") is None
    output = capsys.readouterr().out
    assert "[导入确认任务抢占结果缺失]" in output
    assert "job missing during lease claim" in output
    assert "job_id=job-1" in output


def test_claim_pending_job_logs_rejected_current_state(capsys) -> None:
    job_repo = type("JobRepo", (), {"claim_lease": lambda self, **kwargs: False})()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", job_repo=job_repo)
    job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="import_to_library",
        state="pending_approval",
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        payload_json="{}",
        version=3,
        lease_owner="",
        lease_until="",
        created_at="2026-04-15 00:00:00",
        updated_at="2026-04-15 00:00:00",
    )
    assert service._claim_pending_job(job=job, lease_owner="import_confirm:87") is False
    output = capsys.readouterr().out
    assert "[导入确认任务抢占失败]" in output
    assert "jobs.claim_lease rejected current state" in output
    assert "job_id=job-1" in output


def test_confirm_import_by_task_ref_returns_state_unavailable_when_claim_lease_fails(
    capsys: pytest.CaptureFixture[str],
) -> None:
    job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="import_to_library",
        state="pending_approval",
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        payload_json="{}",
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
            "get_import_job_for_chat_ref": lambda self, **kwargs: job,
            "claim_lease": lambda self, **kwargs: (_ for _ in ()).throw(sqlite3.OperationalError("db down")),
        },
    )()
    approval_repo = type(
        "ApprovalRepo",
        (),
        {
            "get_import_approval": lambda self, **kwargs: approval_record,
            "is_import_pending_expired": lambda self, **kwargs: False,
        },
    )()
    get_import_source = AsyncMock(return_value=None)
    service = ImportToLibraryService(
        get_import_source,
        "/data/library/movies",
        job_repo=job_repo,
        approval_repo=approval_repo,
    )

    text = _run(service.confirm_import_by_task_ref("87", chat_id=1001))

    assert text == IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT
    get_import_source.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[导入确认任务抢占失败]" in output
    assert "job_id=job-1" in output
    assert "db down" in output


def test_confirm_import_by_task_ref_returns_state_unavailable_when_claim_lease_result_is_missing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="import_to_library",
        state="pending_approval",
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        payload_json="{}",
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
            "get_import_job_for_chat_ref": lambda self, **kwargs: job,
            "claim_lease": lambda self, **kwargs: (_ for _ in ()).throw(JobPersistenceError("job missing during lease claim")),
        },
    )()
    approval_repo = type(
        "ApprovalRepo",
        (),
        {
            "get_import_approval": lambda self, **kwargs: approval_record,
            "is_import_pending_expired": lambda self, **kwargs: False,
        },
    )()
    get_import_source = AsyncMock(return_value=None)
    service = ImportToLibraryService(
        get_import_source,
        "/data/library/movies",
        job_repo=job_repo,
        approval_repo=approval_repo,
    )

    text = _run(service.confirm_import_by_task_ref("87", chat_id=1001))

    assert text == IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT
    get_import_source.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[导入确认任务抢占结果缺失]" in output
    assert "job_id=job-1" in output
    assert "job missing during lease claim" in output


def test_confirm_import_by_task_ref_returns_not_pending_when_claim_lease_is_rejected(
    capsys: pytest.CaptureFixture[str],
) -> None:
    job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="import_to_library",
        state="pending_approval",
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        payload_json="{}",
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
            "get_import_job_for_chat_ref": lambda self, **kwargs: job,
            "claim_lease": lambda self, **kwargs: False,
        },
    )()
    approval_repo = type(
        "ApprovalRepo",
        (),
        {
            "get_import_approval": lambda self, **kwargs: approval_record,
            "is_import_pending_expired": lambda self, **kwargs: False,
        },
    )()
    get_import_source = AsyncMock(return_value=None)
    service = ImportToLibraryService(
        get_import_source,
        "/data/library/movies",
        job_repo=job_repo,
        approval_repo=approval_repo,
    )

    text = _run(service.confirm_import_by_task_ref("87", chat_id=1001))

    assert text == IMPORT_CONFIRM_NOT_PENDING_TEXT
    get_import_source.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[导入确认任务抢占失败]" in output
    assert "jobs.claim_lease rejected current state" in output
    assert "job_id=job-1" in output


def test_restore_pending_job_logs_persistence_failure(capsys) -> None:
    job_repo = type("JobRepo", (), {"release_lease_to_pending": lambda self, **kwargs: (_ for _ in ()).throw(sqlite3.OperationalError("db down"))})()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", job_repo=job_repo)
    service._restore_pending_job(job_id="job-1", expected_version=3, lease_owner="import_confirm:87")
    output = capsys.readouterr().out
    assert "[导入确认任务回退失败]" in output
    assert "job_id=job-1" in output


def test_restore_pending_job_logs_missing_result(capsys) -> None:
    job_repo = type(
        "JobRepo",
        (),
        {
            "release_lease_to_pending": lambda self, **kwargs: (_ for _ in ()).throw(
                JobPersistenceError("job missing during state transition")
            )
        },
    )()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", job_repo=job_repo)
    service._restore_pending_job(job_id="job-1", expected_version=3, lease_owner="import_confirm:87")
    output = capsys.readouterr().out
    assert "[导入确认任务回退结果缺失]" in output
    assert "lease 回退后是否还能回读到待确认状态" in output
    assert "job_id=job-1" in output


def test_restore_pending_job_logs_rejected_current_state(capsys) -> None:
    job_repo = type("JobRepo", (), {"release_lease_to_pending": lambda self, **kwargs: False})()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", job_repo=job_repo)
    service._restore_pending_job(job_id="job-1", expected_version=3, lease_owner="import_confirm:87")
    output = capsys.readouterr().out
    assert "[导入确认任务回退失败]" in output
    assert "jobs.release_lease_to_pending rejected current state" in output
    assert "job_id=job-1" in output


def test_mark_completed_job_logs_persistence_failure(capsys) -> None:
    job_repo = type("JobRepo", (), {"mark_completed": lambda self, **kwargs: (_ for _ in ()).throw(sqlite3.OperationalError("db down"))})()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", job_repo=job_repo)
    assert service._mark_completed_job(job_id="job-1", expected_version=3, lease_owner="import_confirm:87") is None
    output = capsys.readouterr().out
    assert "[导入确认任务完结失败]" in output
    assert "job_id=job-1" in output


def test_mark_completed_job_logs_missing_result(capsys) -> None:
    job_repo = type("JobRepo", (), {"mark_completed": lambda self, **kwargs: None})()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", job_repo=job_repo)
    assert service._mark_completed_job(job_id="job-1", expected_version=3, lease_owner="import_confirm:87") is None
    output = capsys.readouterr().out
    assert "[导入确认任务完结结果缺失]" in output
    assert "import completed job result missing" in output
    assert "job_id=job-1" in output


def test_mark_completed_job_logs_rejected_current_state(capsys) -> None:
    job_repo = type("JobRepo", (), {"mark_completed": lambda self, **kwargs: False})()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", job_repo=job_repo)
    assert service._mark_completed_job(job_id="job-1", expected_version=3, lease_owner="import_confirm:87") is False
    output = capsys.readouterr().out
    assert "[导入确认任务完结失败]" in output
    assert "jobs.mark_completed rejected current state" in output
    assert "job_id=job-1" in output


def test_record_pending_approval_logs_persistence_failure(capsys) -> None:
    approval_repo = type(
        "ApprovalRepo",
        (),
        {"request_import_approval": lambda self, **kwargs: (_ for _ in ()).throw(sqlite3.OperationalError("db down"))},
    )()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", approval_repo=approval_repo)
    assert service._record_pending_approval(task_ref="87", task_id="87", task_hash="hash-87") == 0
    output = capsys.readouterr().out
    assert "[导入待确认审批落盘失败]" in output
    assert "当前请求会直接返回待确认状态写入失败" in output


def test_record_pending_approval_logs_missing_pending_result(capsys) -> None:
    approval_repo = type(
        "ApprovalRepo",
        (),
        {
            "request_import_approval": lambda self, **kwargs: (
                _ for _ in ()
            ).throw(ApprovalPersistenceError("approval_record missing after pending request"))
        },
    )()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", approval_repo=approval_repo)
    assert service._record_pending_approval(task_ref="87", task_id="87", task_hash="hash-87") == 0
    output = capsys.readouterr().out
    assert "[导入待确认审批结果缺失]" in output
    assert "approval_record 写入后回读是否仍能拿到当前待确认导入审批的 lease_version" in output


def test_record_pending_approval_logs_missing_pending_result_when_repo_returns_zero(capsys) -> None:
    approval_repo = type("ApprovalRepo", (), {"request_import_approval": lambda self, **kwargs: 0})()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", approval_repo=approval_repo)
    assert service._record_pending_approval(task_ref="87", task_id="87", task_hash="hash-87") == 0
    output = capsys.readouterr().out
    assert "[导入待确认审批结果缺失]" in output
    assert "import pending approval result missing" in output
    assert "当前请求会直接返回待确认状态写入失败" in output


def test_record_pending_approval_logs_row_corruption(capsys) -> None:
    approval_repo = type(
        "ApprovalRepo",
        (),
        {
            "request_import_approval": lambda self, **kwargs: (
                _ for _ in ()
            ).throw(ApprovalPersistenceError("approval row lease version corrupted after read"))
        },
    )()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", approval_repo=approval_repo)
    assert service._record_pending_approval(task_ref="87", task_id="87", task_hash="hash-87") == 0
    output = capsys.readouterr().out
    assert "[导入待确认审批记录损坏]" in output
    assert "approval row lease version corrupted after read" in output
    assert "approval_record.lease_version" in output


def test_record_pending_approval_clears_in_memory_copy_fallback_pending() -> None:
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies")
    service._record_copy_fallback_pending(task_id="87", task_hash="hash-87")

    assert service._resolve_execution_mode(task_id="87", task_hash="hash-87", confirm_context=None) == "copy"

    lease_version = service._record_pending_approval(task_ref="87", task_id="87", task_hash="hash-87")

    assert lease_version == 1
    assert service._resolve_execution_mode(task_id="87", task_hash="hash-87", confirm_context=None) == "hardlink"


def test_record_import_approval_logs_persistence_failure(capsys) -> None:
    approval_repo = type(
        "ApprovalRepo",
        (),
        {"approve_import": lambda self, **kwargs: (_ for _ in ()).throw(sqlite3.OperationalError("db down"))},
    )()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", approval_repo=approval_repo)
    service._pending_import_identities.add(("87", "hash-87"))
    service._pending_import_lease_versions[("87", "hash-87")] = 2
    assert service._record_import_approval(task_ref="87", task_id="87", task_hash="hash-87", expected_lease_version=2) is None
    assert "[导入确认审批更新失败]" in capsys.readouterr().out


def test_record_import_approval_logs_missing_result(capsys) -> None:
    approval_repo = type(
        "ApprovalRepo",
        (),
        {
            "approve_import": lambda self, **kwargs: (
                _ for _ in ()
            ).throw(ApprovalPersistenceError("approval_record missing during approve"))
        },
    )()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", approval_repo=approval_repo)
    service._pending_import_identities.add(("87", "hash-87"))
    service._pending_import_lease_versions[("87", "hash-87")] = 2

    assert service._record_import_approval(
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        expected_lease_version=2,
    ) is None

    output = capsys.readouterr().out
    assert "[导入确认审批结果缺失]" in output
    assert "approval_record missing during approve" in output
    assert "[处理建议]" in output


def test_record_import_approval_logs_missing_result_when_repo_returns_none(capsys) -> None:
    approval_repo = type("ApprovalRepo", (), {"approve_import": lambda self, **kwargs: None})()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", approval_repo=approval_repo)
    service._pending_import_identities.add(("87", "hash-87"))
    service._pending_import_lease_versions[("87", "hash-87")] = 2

    assert service._record_import_approval(
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        expected_lease_version=2,
    ) is None

    output = capsys.readouterr().out
    assert "[导入确认审批结果缺失]" in output
    assert "import approval result missing" in output
    assert "[处理建议]" in output


def test_record_import_approval_logs_rejected_current_state(capsys) -> None:
    approval_repo = type("ApprovalRepo", (), {"approve_import": lambda self, **kwargs: False})()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", approval_repo=approval_repo)
    service._pending_import_identities.add(("87", "hash-87"))
    service._pending_import_lease_versions[("87", "hash-87")] = 2
    assert service._record_import_approval(task_ref="87", task_id="87", task_hash="hash-87", expected_lease_version=2) is False
    output = capsys.readouterr().out
    assert "[导入确认审批更新失败]" in output
    assert "approval_record approve rejected current state" in output


def test_cancel_pending_import_logs_missing_approval_result(capsys) -> None:
    pending_job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type=WORKFLOW_IMPORT_TO_LIBRARY,
        state=JOB_STATE_PENDING_APPROVAL,
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        payload_json="{}",
        version=3,
        lease_owner="",
        lease_until="",
        created_at="2026-04-15 00:00:00",
        updated_at="2026-04-15 00:00:00",
    )
    job_repo = type("JobRepo", (), {"get_latest_pending_import_job": lambda self, chat_id: pending_job})()
    approval_repo = type(
        "ApprovalRepo",
        (),
        {"cancel_import": lambda self, **kwargs: (_ for _ in ()).throw(ApprovalPersistenceError("approval_record missing during cancel"))},
    )()
    service = ImportToLibraryService(
        AsyncMock(return_value=None),
        "/data/library/movies",
        job_repo=job_repo,
        approval_repo=approval_repo,
    )
    service._resolve_pending_lease_version = lambda **kwargs: 2

    assert service.cancel_pending_import(1001) == IMPORT_CANCEL_STATE_UNAVAILABLE_TEXT

    output = capsys.readouterr().out
    assert "[导入取消审批结果缺失]" in output
    assert "approval_record missing during cancel" in output
    assert "[处理建议]" in output


def test_cancel_pending_import_logs_missing_approval_result_when_repo_returns_none(capsys) -> None:
    pending_job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type=WORKFLOW_IMPORT_TO_LIBRARY,
        state=JOB_STATE_PENDING_APPROVAL,
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        payload_json="{}",
        version=3,
        lease_owner="",
        lease_until="",
        created_at="2026-04-15 00:00:00",
        updated_at="2026-04-15 00:00:00",
    )
    job_repo = type("JobRepo", (), {"get_latest_pending_import_job": lambda self, chat_id: pending_job})()
    approval_repo = type("ApprovalRepo", (), {"cancel_import": lambda self, **kwargs: None})()
    service = ImportToLibraryService(
        AsyncMock(return_value=None),
        "/data/library/movies",
        job_repo=job_repo,
        approval_repo=approval_repo,
    )
    service._resolve_pending_lease_version = lambda **kwargs: 2

    assert service.cancel_pending_import(1001) == IMPORT_CANCEL_STATE_UNAVAILABLE_TEXT

    output = capsys.readouterr().out
    assert "[导入取消审批结果缺失]" in output
    assert "import cancel approval result missing" in output
    assert "[处理建议]" in output


def test_record_executed_lease_version_logs_persistence_failure(capsys) -> None:
    approval_repo = type(
        "ApprovalRepo",
        (),
        {"mark_import_executed": lambda self, **kwargs: (_ for _ in ()).throw(sqlite3.OperationalError("db down"))},
    )()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", approval_repo=approval_repo)
    assert (
        service._record_executed_lease_version(
            task_ref="87",
            task_id="87",
            task_hash="hash-87",
            executed_lease_version=3,
        )
        is None
    )
    assert service._pending_import_lease_versions[("87", "hash-87")] == 3
    assert "[导入执行版号回写失败]" in capsys.readouterr().out


def test_record_executed_lease_version_logs_missing_result(capsys) -> None:
    approval_repo = type(
        "ApprovalRepo",
        (),
        {
            "mark_import_executed": lambda self, **kwargs: (_ for _ in ()).throw(
                ApprovalPersistenceError("approval_record missing during executed version update")
            )
        },
    )()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", approval_repo=approval_repo)
    assert (
        service._record_executed_lease_version(
            task_ref="87",
            task_id="87",
            task_hash="hash-87",
            executed_lease_version=3,
        )
        is None
    )
    assert service._pending_import_lease_versions[("87", "hash-87")] == 3
    output = capsys.readouterr().out
    assert "[导入执行版号结果缺失]" in output
    assert "approval_record 更新后该审批行是否仍存在" in output


def test_record_executed_lease_version_logs_row_corruption(capsys) -> None:
    approval_repo = type(
        "ApprovalRepo",
        (),
        {
            "mark_import_executed": lambda self, **kwargs: (
                _ for _ in ()
            ).throw(ApprovalPersistenceError("approval row executed version corrupted after read"))
        },
    )()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", approval_repo=approval_repo)
    assert (
        service._record_executed_lease_version(
            task_ref="87",
            task_id="87",
            task_hash="hash-87",
            executed_lease_version=3,
        )
        is None
    )
    output = capsys.readouterr().out
    assert "[导入执行版号记录损坏]" in output
    assert "approval row executed version corrupted after read" in output
    assert "lease_version / executed_version" in output


def test_record_pending_job_logs_persistence_failure(capsys) -> None:
    job_repo = type("JobRepo", (), {"upsert_import_job_pending": lambda self, **kwargs: (_ for _ in ()).throw(sqlite3.OperationalError("db down"))})()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", job_repo=job_repo)
    assert service._record_pending_job(chat_id=1001, user_id=2001, task_ref="87", task_id="87", task_hash="hash-87", payload_json="{}") is False
    output = capsys.readouterr().out
    assert "[导入待确认任务落盘失败]" in output
    assert "task_ref=87" in output
    assert "当前请求会直接返回待确认状态写入失败" in output


def test_record_pending_job_logs_missing_pending_job_result(capsys) -> None:
    job_repo = type(
        "JobRepo",
        (),
        {"upsert_import_job_pending": lambda self, **kwargs: (_ for _ in ()).throw(JobPersistenceError("job missing after pending upsert"))},
    )()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", job_repo=job_repo)
    assert (
        service._record_pending_job(
            chat_id=1001,
            user_id=2001,
            task_ref="87",
            task_id="87",
            task_hash="hash-87",
            payload_json="{}",
        )
        is False
    )
    output = capsys.readouterr().out
    assert "[导入待确认任务结果缺失]" in output
    assert "task_ref=87" in output
    assert "job missing after pending upsert" in output


def test_record_pending_job_logs_missing_pending_job_result_when_repo_returns_none(capsys) -> None:
    job_repo = type("JobRepo", (), {"upsert_import_job_pending": lambda self, **kwargs: None})()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", job_repo=job_repo)
    assert service._record_pending_job(chat_id=1001, user_id=2001, task_ref="87", task_id="87", task_hash="hash-87", payload_json="{}") is False
    output = capsys.readouterr().out
    assert "[导入待确认任务结果缺失]" in output
    assert "import pending job result missing" in output
    assert "当前请求会直接返回待确认状态写入失败" in output


def test_record_pending_job_logs_row_corruption(capsys) -> None:
    job_repo = type(
        "JobRepo",
        (),
        {
            "upsert_import_job_pending": lambda self, **kwargs: (
                _ for _ in ()
            ).throw(JobPersistenceError("job row version corrupted after read"))
        },
    )()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", job_repo=job_repo)
    assert service._record_pending_job(chat_id=1001, user_id=2001, task_ref="87", task_id="87", task_hash="hash-87", payload_json="{}") is False
    output = capsys.readouterr().out
    assert "[导入待确认任务记录损坏]" in output
    assert "job row version corrupted after read" in output
    assert "job_id / chat_id / user_id / version" in output


def test_confirm_import_by_task_ref_returns_state_unavailable_when_approval_update_fails(
    tmp_path: Path,
    capsys,
) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")
    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="import_to_library",
        state="pending_approval",
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        payload_json="{}",
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
            "get_import_job_for_chat_ref": lambda self, **kwargs: job,
            "claim_lease": lambda self, **kwargs: True,
            "release_lease_to_pending": lambda self, **kwargs: True,
        },
    )()
    approval_repo = type(
        "ApprovalRepo",
        (),
        {
            "get_import_approval": lambda self, **kwargs: approval_record,
            "is_import_pending_expired": lambda self, **kwargs: False,
            "approve_import": lambda self, **kwargs: (_ for _ in ()).throw(sqlite3.OperationalError("db down")),
        },
    )()
    get_import_source = AsyncMock(return_value=import_source)
    service = ImportToLibraryService(
        get_import_source,
        "/data/library/movies",
        job_repo=job_repo,
        approval_repo=approval_repo,
    )

    text = _run(service.confirm_import_by_task_ref("87", chat_id=1001))

    assert text == IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT
    get_import_source.assert_awaited_once()
    output = capsys.readouterr().out
    assert "[导入确认审批更新失败]" in output
    assert "lease_version=2" in output


def test_confirm_import_by_task_ref_returns_state_unavailable_when_approval_result_is_missing(
    tmp_path: Path,
    capsys,
) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")
    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="import_to_library",
        state="pending_approval",
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        payload_json="{}",
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
            "get_import_job_for_chat_ref": lambda self, **kwargs: job,
            "claim_lease": lambda self, **kwargs: True,
            "release_lease_to_pending": lambda self, **kwargs: True,
        },
    )()
    approval_repo = type(
        "ApprovalRepo",
        (),
        {
            "get_import_approval": lambda self, **kwargs: approval_record,
            "is_import_pending_expired": lambda self, **kwargs: False,
            "approve_import": lambda self, **kwargs: None,
        },
    )()
    get_import_source = AsyncMock(return_value=import_source)
    service = ImportToLibraryService(
        get_import_source,
        "/data/library/movies",
        job_repo=job_repo,
        approval_repo=approval_repo,
    )

    text = _run(service.confirm_import_by_task_ref("87", chat_id=1001))

    assert text == IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT
    get_import_source.assert_awaited_once()
    output = capsys.readouterr().out
    assert "[导入确认审批结果缺失]" in output
    assert "import approval result missing" in output
    assert "lease_version=2" in output


def test_confirm_import_by_task_ref_returns_state_unavailable_when_pending_lease_lookup_fails_without_confirm_context(
    tmp_path: Path,
    capsys,
) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")
    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    approval_records = iter(
        (
            type("ApprovalRecord", (), {"lease_version": 0, "executed_version": 0})(),
            sqlite3.OperationalError("db down"),
        )
    )

    def _get_import_approval(**_: object):
        next_value = next(approval_records)
        if isinstance(next_value, Exception):
            raise next_value
        return next_value

    approval_repo = type(
        "ApprovalRepo",
        (),
        {
            "get_import_approval": lambda self, **kwargs: _get_import_approval(**kwargs),
            "approve_import": lambda self, **kwargs: (_ for _ in ()).throw(AssertionError("approve_import should not be called")),
        },
    )()
    service = ImportToLibraryService(
        AsyncMock(return_value=import_source),
        str(tmp_path / "library"),
        approval_repo=approval_repo,
    )
    service._pending_import_identities.add((import_source.task_id, import_source.task_hash))
    service._pending_import_lease_versions[(import_source.task_id, import_source.task_hash)] = 2

    text = _run(service.confirm_import_by_task_ref("87"))

    assert text == IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT
    output = capsys.readouterr().out
    assert "[导入待确认版号查询失败]" in output
    assert "task_id=87" in output
    assert "db down" in output


def test_import_by_task_ref_returns_state_unavailable_when_pending_approval_persist_fails(tmp_path: Path) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")
    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    approval_repo = type(
        "ApprovalRepo",
        (),
        {"request_import_approval": lambda self, **kwargs: (_ for _ in ()).throw(sqlite3.OperationalError("db down"))},
    )()
    service = ImportToLibraryService(
        AsyncMock(return_value=import_source),
        str(tmp_path / "library"),
        approval_repo=approval_repo,
    )

    text = _run(service.import_by_task_ref("87"))

    assert text == IMPORT_PENDING_STATE_UNAVAILABLE_TEXT


def test_import_by_task_ref_returns_state_unavailable_when_pending_approval_result_is_missing(tmp_path: Path) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")
    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    approval_repo = type("ApprovalRepo", (), {"request_import_approval": lambda self, **kwargs: 0})()
    service = ImportToLibraryService(
        AsyncMock(return_value=import_source),
        str(tmp_path / "library"),
        approval_repo=approval_repo,
    )

    text = _run(service.import_by_task_ref("87"))

    assert text == IMPORT_PENDING_STATE_UNAVAILABLE_TEXT


def test_import_by_task_ref_returns_state_unavailable_when_pending_job_persist_fails(tmp_path: Path) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")
    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    approval_repo = type(
        "ApprovalRepo",
        (),
        {
            "request_import_approval": lambda self, **kwargs: 2,
            "cancel_import": lambda self, **kwargs: True,
        },
    )()
    job_repo = type("JobRepo", (), {"upsert_import_job_pending": lambda self, **kwargs: (_ for _ in ()).throw(sqlite3.OperationalError("db down"))})()
    service = ImportToLibraryService(
        AsyncMock(return_value=import_source),
        str(tmp_path / "library"),
        approval_repo=approval_repo,
        job_repo=job_repo,
    )

    text = _run(service.import_by_task_ref("87"))

    assert text == IMPORT_PENDING_STATE_UNAVAILABLE_TEXT


def test_import_by_task_ref_returns_state_unavailable_when_pending_job_result_is_missing(tmp_path: Path) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")
    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    approval_repo = type(
        "ApprovalRepo",
        (),
        {
            "request_import_approval": lambda self, **kwargs: 2,
            "cancel_import": lambda self, **kwargs: True,
        },
    )()
    job_repo = type("JobRepo", (), {"upsert_import_job_pending": lambda self, **kwargs: None})()
    service = ImportToLibraryService(
        AsyncMock(return_value=import_source),
        str(tmp_path / "library"),
        approval_repo=approval_repo,
        job_repo=job_repo,
    )

    text = _run(service.import_by_task_ref("87"))

    assert text == IMPORT_PENDING_STATE_UNAVAILABLE_TEXT


def test_record_event_logs_persistence_failure(capsys) -> None:
    event_repo = type(
        "EventRepo",
        (),
        {"append_event": lambda self, **kwargs: (_ for _ in ()).throw(sqlite3.OperationalError("db down"))},
    )()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", job_event_repo=event_repo)

    service._record_event(
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.approval_pending",
        message="87",
        source_path="/downloads/Dune.2021.mkv",
        target_path="/library/Dune (2021).mkv",
    )

    output = capsys.readouterr().out
    assert "[导入事件落盘失败]" in output
    assert "event_type=import.approval_pending" in output
    assert "task_ref=87" in output


def test_record_event_logs_missing_appended_event_result(capsys) -> None:
    event_repo = type(
        "EventRepo",
        (),
        {
            "append_event": lambda self, **kwargs: (_ for _ in ()).throw(
                JobEventPersistenceError("job_event missing after append")
            )
        },
    )()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", job_event_repo=event_repo)

    service._record_event(
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.approval_pending",
        message="87",
        source_path="/downloads/Dune.2021.mkv",
        target_path="/library/Dune (2021).mkv",
    )

    output = capsys.readouterr().out
    assert "[导入事件结果缺失]" in output
    assert "event_type=import.approval_pending" in output
    assert "import event missing after append" in output


def test_record_event_logs_row_corrupted_appended_event(capsys) -> None:
    event_repo = type(
        "EventRepo",
        (),
        {
            "append_event": lambda self, **kwargs: (_ for _ in ()).throw(
                JobEventPersistenceError("job_event row identity corrupted after read")
            )
        },
    )()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", job_event_repo=event_repo)

    service._record_event(
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        event_type="import.approval_pending",
        message="87",
        source_path="/downloads/Dune.2021.mkv",
        target_path="/library/Dune (2021).mkv",
    )

    output = capsys.readouterr().out
    assert "[导入事件记录损坏]" in output
    assert "event_type=import.approval_pending" in output
    assert "job_event row identity corrupted after read" in output


def test_restore_pending_approval_logs_persistence_failure(capsys) -> None:
    approval_repo = type(
        "ApprovalRepo",
        (),
        {"restore_import_pending": lambda self, **kwargs: (_ for _ in ()).throw(sqlite3.OperationalError("db down"))},
    )()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", approval_repo=approval_repo)
    assert (
        service._restore_pending_approval(
            task_ref="87",
            task_id="87",
            task_hash="hash-87",
            expected_lease_version=2,
        )
        is None
    )
    output = capsys.readouterr().out
    assert "[导入审批回退失败]" in output
    assert "lease_version=2" in output


def test_restore_pending_approval_logs_missing_result(capsys) -> None:
    approval_repo = type("ApprovalRepo", (), {"restore_import_pending": lambda self, **kwargs: None})()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", approval_repo=approval_repo)
    assert (
        service._restore_pending_approval(
            task_ref="87",
            task_id="87",
            task_hash="hash-87",
            expected_lease_version=2,
        )
        is None
    )
    output = capsys.readouterr().out
    assert "[导入审批回退结果缺失]" in output
    assert "import restore pending approval result missing" in output
    assert "lease_version=2" in output


def test_restore_pending_approval_logs_missing_row_result(capsys) -> None:
    approval_repo = type(
        "ApprovalRepo",
        (),
        {
            "restore_import_pending": lambda self, **kwargs: (
                _ for _ in ()
            ).throw(ApprovalPersistenceError("approval_record missing during restore"))
        },
    )()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", approval_repo=approval_repo)
    assert (
        service._restore_pending_approval(
            task_ref="87",
            task_id="87",
            task_hash="hash-87",
            expected_lease_version=2,
        )
        is None
    )
    output = capsys.readouterr().out
    assert "[导入审批回退结果缺失]" in output
    assert "approval_record missing during restore" in output
    assert "lease_version=2" in output


def test_restore_pending_approval_logs_rejected_current_state(capsys) -> None:
    approval_repo = type("ApprovalRepo", (), {"restore_import_pending": lambda self, **kwargs: False})()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", approval_repo=approval_repo)
    assert (
        service._restore_pending_approval(
            task_ref="87",
            task_id="87",
            task_hash="hash-87",
            expected_lease_version=2,
        )
        is False
    )
    output = capsys.readouterr().out
    assert "[导入审批回退失败]" in output
    assert "approval_record restore rejected current state" in output
    assert "lease_version=2" in output


@pytest.mark.parametrize(
    ("execution_result", "expected_reply"),
    [
        (
            import_module.ImportExecutionResult(
                reply=IMPORT_COPY_FAILED_TEXT,
                imported=False,
            ),
            IMPORT_COPY_FAILED_TEXT,
        ),
        (
            import_module.ImportExecutionResult(
                reply=IMPORT_COPY_APPROVAL_PENDING_TEXT,
                imported=False,
                pending_copy_approval=True,
            ),
            IMPORT_COPY_APPROVAL_PENDING_TEXT,
        ),
    ],
    ids=("import_failed", "copy_fallback_pending"),
)
def test_confirm_import_by_task_ref_returns_state_unavailable_when_execution_cannot_restore_pending_approval(
    tmp_path: Path,
    execution_result: import_module.ImportExecutionResult,
    expected_reply: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class BrokenRestoreApprovalRepo:
        def request_import_approval(self, **_: object) -> int:
            return 1

        def get_import_approval(self, **_: object):
            return type(
                "ApprovalRecord",
                (),
                {"status": APPROVAL_STATUS_PENDING, "lease_version": 1, "executed_version": 0},
            )()

        def approve_import(self, **_: object) -> bool:
            return True

        def restore_import_pending(self, **_: object) -> bool:
            raise sqlite3.OperationalError("db down")

    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")
    target_dir = tmp_path / "library"
    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    service = ImportToLibraryService(
        AsyncMock(return_value=import_source),
        str(target_dir),
        approval_repo=BrokenRestoreApprovalRepo(),
    )

    async def _fake_execute_import(*_: object, **__: object) -> import_module.ImportExecutionResult:
        return execution_result

    service._execute_import = _fake_execute_import  # type: ignore[method-assign]

    _run(service.import_by_task_ref("87"))
    text = _run(service.confirm_import_by_task_ref("87"))

    assert text == IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT
    assert expected_reply not in text
    output = capsys.readouterr().out
    assert "[导入审批回退失败]" in output
    assert "db down" in output


@pytest.mark.parametrize(
    ("restore_mode", "execution_result", "expected_reply", "expected_error"),
    [
        (
            "missing",
            import_module.ImportExecutionResult(
                reply=IMPORT_COPY_FAILED_TEXT,
                imported=False,
            ),
            IMPORT_COPY_FAILED_TEXT,
            "import restore pending approval result missing",
        ),
        (
            "missing_row",
            import_module.ImportExecutionResult(
                reply=IMPORT_COPY_FAILED_TEXT,
                imported=False,
            ),
            IMPORT_COPY_FAILED_TEXT,
            "approval_record missing during restore",
        ),
        (
            "missing",
            import_module.ImportExecutionResult(
                reply=IMPORT_COPY_APPROVAL_PENDING_TEXT,
                imported=False,
                pending_copy_approval=True,
            ),
            IMPORT_COPY_APPROVAL_PENDING_TEXT,
            "import restore pending approval result missing",
        ),
    ],
    ids=("missing_import_failed", "missing_row_import_failed", "missing_copy_fallback_pending"),
)
def test_confirm_import_by_task_ref_returns_state_unavailable_when_execution_restore_pending_approval_result_is_missing(
    tmp_path: Path,
    restore_mode: str,
    execution_result: import_module.ImportExecutionResult,
    expected_reply: str,
    expected_error: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class MissingRestoreApprovalRepo:
        def request_import_approval(self, **_: object) -> int:
            return 1

        def get_import_approval(self, **_: object):
            return type(
                "ApprovalRecord",
                (),
                {"status": APPROVAL_STATUS_PENDING, "lease_version": 1, "executed_version": 0},
            )()

        def approve_import(self, **_: object) -> bool:
            return True

        def restore_import_pending(self, **_: object):
            if restore_mode == "missing_row":
                raise ApprovalPersistenceError("approval_record missing during restore")
            return None

    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")
    target_dir = tmp_path / "library"
    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    service = ImportToLibraryService(
        AsyncMock(return_value=import_source),
        str(target_dir),
        approval_repo=MissingRestoreApprovalRepo(),
    )

    async def _fake_execute_import(*_: object, **__: object) -> import_module.ImportExecutionResult:
        return execution_result

    service._execute_import = _fake_execute_import  # type: ignore[method-assign]

    _run(service.import_by_task_ref("87"))
    text = _run(service.confirm_import_by_task_ref("87"))

    assert text == IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT
    assert expected_reply not in text
    output = capsys.readouterr().out
    assert "[导入审批回退结果缺失]" in output
    assert expected_error in output


def test_resolve_pending_lease_version_logs_approval_lookup_failure(capsys) -> None:
    approval_repo = type(
        "ApprovalRepo",
        (),
        {"get_import_approval": lambda self, **kwargs: (_ for _ in ()).throw(sqlite3.OperationalError("db down"))},
    )()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", approval_repo=approval_repo)
    service._pending_import_identities.add(("87", "hash-87"))
    service._pending_import_lease_versions[("87", "hash-87")] = 3
    assert service._resolve_pending_lease_version(task_id="87", task_hash="hash-87") == 3
    output = capsys.readouterr().out
    assert "[导入待确认版号查询失败]" in output
    assert "task_hash=hash-87" in output
    assert "当前调用会按状态读取失败处理" in output


def test_resolve_pending_lease_version_logs_missing_approval_row_with_in_memory_pending(capsys) -> None:
    approval_repo = type("ApprovalRepo", (), {"get_import_approval": lambda self, **kwargs: None})()
    service = ImportToLibraryService(
        AsyncMock(return_value=None),
        "/data/library/movies",
        approval_repo=approval_repo,
    )
    service._pending_import_identities.add(("87", "hash-87"))
    service._pending_import_lease_versions[("87", "hash-87")] = 3

    assert (
        service._resolve_pending_lease_version(
            task_id="87",
            task_hash="hash-87",
            allow_in_memory_fallback_on_error=False,
        )
        == -1
    )

    output = capsys.readouterr().out
    assert "[导入待确认版号查询失败]" in output
    assert "approval_record missing while in-memory pending exists" in output
    assert "task_hash=hash-87" in output


def test_find_version_stale_rejection_text_logs_approval_lookup_failure(capsys) -> None:
    approval_repo = type(
        "ApprovalRepo",
        (),
        {"get_import_approval": lambda self, **kwargs: (_ for _ in ()).throw(sqlite3.OperationalError("db down"))},
    )()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", approval_repo=approval_repo)
    assert service._find_version_stale_rejection_text(task_id="87", task_hash="hash-87") == IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT
    output = capsys.readouterr().out
    assert "[导入确认执行版号查询失败]" in output
    assert "task_id=87" in output


def test_find_version_stale_rejection_text_logs_missing_approval_row(capsys) -> None:
    approval_repo = type("ApprovalRepo", (), {"get_import_approval": lambda self, **kwargs: None})()
    service = ImportToLibraryService(
        AsyncMock(return_value=None),
        "/data/library/movies",
        approval_repo=approval_repo,
    )

    assert service._find_version_stale_rejection_text(task_id="87", task_hash="hash-87") == IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT

    output = capsys.readouterr().out
    assert "[导入确认执行版号查询失败]" in output
    assert "approval_record missing during stale check" in output
    assert "task_hash=hash-87" in output


def test_find_version_stale_rejection_text_logs_row_corruption(capsys) -> None:
    approval_repo = type(
        "ApprovalRepo",
        (),
        {
            "get_import_approval": lambda self, **kwargs: (
                _ for _ in ()
            ).throw(ApprovalPersistenceError("approval row executed version corrupted after read"))
        },
    )()
    service = ImportToLibraryService(
        AsyncMock(return_value=None),
        "/data/library/movies",
        approval_repo=approval_repo,
    )

    assert service._find_version_stale_rejection_text(task_id="87", task_hash="hash-87") == IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT

    output = capsys.readouterr().out
    assert "[导入确认执行版号记录损坏]" in output
    assert "approval row executed version corrupted after read" in output
    assert "status / lease_version / executed_version" in output


def test_find_latest_import_target_path_logs_event_lookup_failure(capsys) -> None:
    event_repo = type(
        "EventRepo",
        (),
        {
            "find_latest_import_correlation": lambda self, **kwargs: (
                _ for _ in ()
            ).throw(sqlite3.OperationalError("db down"))
        },
    )()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", job_event_repo=event_repo)

    result = service._find_latest_import_target_path(task_id="87", task_hash="hash-87")

    assert result.target_path is None
    assert result.lookup_failed is True
    output = capsys.readouterr().out
    assert "[导入目标路径查询失败]" in output
    assert "task_hash=hash-87" in output


def test_find_latest_import_target_path_logs_missing_event_lookup_result(capsys) -> None:
    event_repo = type(
        "EventRepo",
        (),
        {
            "find_latest_import_correlation": lambda self, **kwargs: (
                _ for _ in ()
            ).throw(JobEventPersistenceError("job_event list result missing during correlation lookup"))
        },
    )()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", job_event_repo=event_repo)

    result = service._find_latest_import_target_path(task_id="87", task_hash="hash-87")

    assert result.target_path is None
    assert result.lookup_failed is True
    output = capsys.readouterr().out
    assert "[导入目标路径结果缺失]" in output
    assert "job_event list result missing during correlation lookup" in output
    assert "task_hash=hash-87" in output


def test_find_latest_import_target_path_logs_corrupted_event_lookup_result(capsys) -> None:
    event_repo = type(
        "EventRepo",
        (),
        {
            "find_latest_import_correlation": lambda self, **kwargs: (
                _ for _ in ()
            ).throw(JobEventPersistenceError("job_event row identity corrupted after read"))
        },
    )()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", job_event_repo=event_repo)

    result = service._find_latest_import_target_path(task_id="87", task_hash="hash-87")

    assert result.target_path is None
    assert result.lookup_failed is True
    output = capsys.readouterr().out
    assert "[导入目标路径记录损坏]" in output
    assert "job_event row identity corrupted after read" in output
    assert "task_hash=hash-87" in output


def test_find_latest_import_target_path_logs_missing_structured_target(capsys) -> None:
    event_repo = type(
        "EventRepo",
        (),
        {
            "find_latest_import_correlation": lambda self, **kwargs: type(
                "Correlation",
                (),
                {
                    "target_path": "",
                    "message": "",
                },
            )()
        },
    )()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", job_event_repo=event_repo)

    result = service._find_latest_import_target_path(task_id="87", task_hash="hash-87")

    assert result.target_path is None
    assert result.lookup_failed is False
    output = capsys.readouterr().out
    assert "[导入目标路径缺失]" in output
    assert "import correlation target path missing" in output
    assert "task_hash=hash-87" in output


def test_find_version_stale_rejection_text_returns_state_unavailable_when_event_lookup_fails(capsys) -> None:
    approval_record = type("ApprovalRecord", (), {"lease_version": 2, "executed_version": 2})()
    approval_repo = type("ApprovalRepo", (), {"get_import_approval": lambda self, **kwargs: approval_record})()
    event_repo = type(
        "EventRepo",
        (),
        {
            "find_latest_import_correlation": lambda self, **kwargs: (
                _ for _ in ()
            ).throw(sqlite3.OperationalError("db down")),
            "append_event": lambda self, **kwargs: None,
        },
    )()
    service = ImportToLibraryService(
        AsyncMock(return_value=None),
        "/data/library/movies",
        approval_repo=approval_repo,
        job_event_repo=event_repo,
    )

    assert service._find_version_stale_rejection_text(task_id="87", task_hash="hash-87") == IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT

    output = capsys.readouterr().out
    assert "[导入目标路径查询失败]" in output
    assert "task_id=87" in output


def test_find_version_stale_rejection_text_returns_state_unavailable_when_event_lookup_row_corrupted(capsys) -> None:
    approval_record = type("ApprovalRecord", (), {"lease_version": 2, "executed_version": 2})()
    approval_repo = type("ApprovalRepo", (), {"get_import_approval": lambda self, **kwargs: approval_record})()
    event_repo = type(
        "EventRepo",
        (),
        {
            "find_latest_import_correlation": lambda self, **kwargs: (
                _ for _ in ()
            ).throw(JobEventPersistenceError("job_event row identity corrupted after read")),
            "append_event": lambda self, **kwargs: None,
        },
    )()
    service = ImportToLibraryService(
        AsyncMock(return_value=None),
        "/data/library/movies",
        approval_repo=approval_repo,
        job_event_repo=event_repo,
    )

    assert service._find_version_stale_rejection_text(task_id="87", task_hash="hash-87") == IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT

    output = capsys.readouterr().out
    assert "[导入目标路径记录损坏]" in output
    assert "task_id=87" in output
    assert "job_event row identity corrupted after read" in output


def test_find_version_stale_rejection_text_logs_missing_structured_target(capsys) -> None:
    approval_record = type("ApprovalRecord", (), {"lease_version": 2, "executed_version": 2})()
    approval_repo = type("ApprovalRepo", (), {"get_import_approval": lambda self, **kwargs: approval_record})()
    event_repo = type(
        "EventRepo",
        (),
        {
            "find_latest_import_correlation": lambda self, **kwargs: type(
                "Correlation",
                (),
                {
                    "target_path": "",
                    "message": "",
                },
            )(),
            "append_event": lambda self, **kwargs: None,
        },
    )()
    service = ImportToLibraryService(
        AsyncMock(return_value=None),
        "/data/library/movies",
        approval_repo=approval_repo,
        job_event_repo=event_repo,
    )

    assert service._find_version_stale_rejection_text(task_id="87", task_hash="hash-87") == IMPORT_CONFIRM_NOT_PENDING_TEXT

    output = capsys.readouterr().out
    assert "[导入目标路径缺失]" in output
    assert "task_id=87" in output


def test_confirm_import_by_task_ref_returns_state_unavailable_when_stale_target_lookup_fails(capsys) -> None:
    job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="import_to_library",
        state="completed",
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        payload_json="{}",
        version=3,
        lease_owner="",
        lease_until="",
        created_at="2026-04-15 00:00:00",
        updated_at="2026-04-15 00:00:00",
    )
    approval_record = type("ApprovalRecord", (), {"lease_version": 2, "executed_version": 2})()
    job_repo = type("JobRepo", (), {"get_import_job_for_chat_ref": lambda self, **kwargs: job})()
    approval_repo = type("ApprovalRepo", (), {"get_import_approval": lambda self, **kwargs: approval_record})()
    event_repo = type(
        "EventRepo",
        (),
        {
            "find_latest_import_correlation": lambda self, **kwargs: (
                _ for _ in ()
            ).throw(sqlite3.OperationalError("db down")),
            "append_event": lambda self, **kwargs: None,
        },
    )()
    get_import_source = AsyncMock(return_value=None)
    service = ImportToLibraryService(
        get_import_source,
        "/data/library/movies",
        job_repo=job_repo,
        approval_repo=approval_repo,
        job_event_repo=event_repo,
    )

    text = _run(service.confirm_import_by_task_ref("87", chat_id=1001))

    assert text == IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT
    get_import_source.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[导入目标路径查询失败]" in output
    assert "task_hash=hash-87" in output


def test_prepare_import_logs_target_dir_create_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")
    target_dir = tmp_path / "library"
    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    service = ImportToLibraryService(AsyncMock(return_value=import_source), str(target_dir))
    original_mkdir = Path.mkdir

    def _crash_mkdir(self: Path, parents: bool = False, exist_ok: bool = False) -> None:
        if self == target_dir:
            raise OSError("permission denied")
        original_mkdir(self, parents=parents, exist_ok=exist_ok)

    monkeypatch.setattr(Path, "mkdir", _crash_mkdir)

    prepared, message = _run(service._prepare_import("87"))

    assert prepared is None
    assert message == "创建目标目录失败：" + str(target_dir)
    output = capsys.readouterr().out
    assert "[导入目标目录创建失败]" in output
    assert "task_id=87" in output
    assert "permission denied" in output
    assert "[处理建议]" in output


def test_prepare_import_logs_query_failure(capsys: pytest.CaptureFixture[str]) -> None:
    service = ImportToLibraryService(
        AsyncMock(side_effect=DownloaderRouteLookupError("route unavailable")),
        "/data/library/movies",
    )

    prepared, message = _run(service._prepare_import("87", chat_id=1001))

    assert prepared is None
    assert message == IMPORT_QUERY_FAILED_TEXT
    output = capsys.readouterr().out
    assert "[导入源查询失败]" in output
    assert "task_ref=87" in output
    assert "route unavailable" in output
    assert "[处理建议]" in output


def test_prepare_import_propagates_unexpected_query_failure() -> None:
    service = ImportToLibraryService(
        AsyncMock(side_effect=RuntimeError("programming error")),
        "/data/library/movies",
    )

    with pytest.raises(RuntimeError, match="programming error"):
        _run(service._prepare_import("87", chat_id=1001))


def test_prepare_import_logs_source_missing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name="Dune.2021.mkv",
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    service = ImportToLibraryService(AsyncMock(return_value=import_source), str(tmp_path / "library"))

    prepared, message = _run(service._prepare_import("87"))

    assert prepared is None
    assert message == IMPORT_SOURCE_MISSING_TEXT
    output = capsys.readouterr().out
    assert "[导入源文件缺失]" in output
    assert "task_id=87" in output
    assert "Dune.2021.mkv" in output
    assert "[处理建议]" in output


def test_prepare_import_logs_target_exists(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")
    target_dir = tmp_path / "library"
    target_dir.mkdir(parents=True)
    target_path = target_dir / "Dune (2021).mkv"
    target_path.write_bytes(b"existing")

    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    service = ImportToLibraryService(AsyncMock(return_value=import_source), str(target_dir))

    prepared, message = _run(service._prepare_import("87"))

    assert prepared is None
    assert message == f"目标已存在，已拒绝覆盖：{target_path}"
    output = capsys.readouterr().out
    assert "[导入目标已存在]" in output
    assert "task_id=87" in output
    assert str(target_path) in output
    assert "[处理建议]" in output


def test_is_pending_approval_expired_logs_approval_lookup_failure(capsys) -> None:
    approval_repo = type(
        "ApprovalRepo",
        (),
        {
            "is_import_pending_expired": lambda self, **kwargs: (
                _ for _ in ()
            ).throw(sqlite3.OperationalError("db down"))
        },
    )()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", approval_repo=approval_repo)
    assert service._is_pending_approval_expired(task_id="87", task_hash="hash-87", expected_lease_version=2) is None
    output = capsys.readouterr().out
    assert "[导入确认过期判断失败]" in output
    assert "lease_version=2" in output


def test_is_pending_approval_expired_logs_missing_approval_result(capsys) -> None:
    approval_repo = type(
        "ApprovalRepo",
        (),
        {
            "is_import_pending_expired": lambda self, **kwargs: (
                _ for _ in ()
            ).throw(ApprovalPersistenceError("approval_record missing during pending expiry check"))
        },
    )()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", approval_repo=approval_repo)

    assert service._is_pending_approval_expired(task_id="87", task_hash="hash-87", expected_lease_version=2) is None

    output = capsys.readouterr().out
    assert "[导入确认过期结果缺失]" in output
    assert "approval_record missing during pending expiry check" in output
    assert "lease_version=2" in output


def test_is_pending_approval_expired_logs_row_corruption(capsys) -> None:
    approval_repo = type(
        "ApprovalRepo",
        (),
        {
            "is_import_pending_expired": lambda self, **kwargs: (
                _ for _ in ()
            ).throw(ApprovalPersistenceError("approval row status corrupted after read"))
        },
    )()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", approval_repo=approval_repo)

    assert service._is_pending_approval_expired(task_id="87", task_hash="hash-87", expected_lease_version=2) is None

    output = capsys.readouterr().out
    assert "[导入确认过期审批记录损坏]" in output
    assert "approval row status corrupted after read" in output
    assert "status / lease_version / executed_version" in output


def test_confirm_import_by_task_ref_returns_state_unavailable_when_approval_lookup_fails(capsys) -> None:
    job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="import_to_library",
        state="pending_approval",
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        payload_json="{}",
        version=3,
        lease_owner="",
        lease_until="",
        created_at="2026-04-15 00:00:00",
        updated_at="2026-04-15 00:00:00",
    )
    job_repo = type("JobRepo", (), {"get_import_job_for_chat_ref": lambda self, **kwargs: job})()
    approval_repo = type("ApprovalRepo", (), {"get_import_approval": lambda self, **kwargs: (_ for _ in ()).throw(sqlite3.OperationalError("db down"))})()
    get_import_source = AsyncMock(return_value=None)
    service = ImportToLibraryService(
        get_import_source,
        "/data/library/movies",
        job_repo=job_repo,
        approval_repo=approval_repo,
    )

    text = _run(service.confirm_import_by_task_ref("87", chat_id=1001))

    assert text == IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT
    get_import_source.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[导入确认审批查询失败]" in output
    assert "当前 confirm 会直接返回状态读取失败" in output


def test_confirm_import_by_task_ref_returns_state_unavailable_when_approval_row_missing(capsys) -> None:
    job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="import_to_library",
        state="pending_approval",
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        payload_json="{}",
        version=3,
        lease_owner="",
        lease_until="",
        created_at="2026-04-15 00:00:00",
        updated_at="2026-04-15 00:00:00",
    )
    job_repo = type("JobRepo", (), {"get_import_job_for_chat_ref": lambda self, **kwargs: job})()
    approval_repo = type("ApprovalRepo", (), {"get_import_approval": lambda self, **kwargs: None})()
    get_import_source = AsyncMock(return_value=None)
    service = ImportToLibraryService(
        get_import_source,
        "/data/library/movies",
        job_repo=job_repo,
        approval_repo=approval_repo,
    )

    text = _run(service.confirm_import_by_task_ref("87", chat_id=1001))

    assert text == IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT
    get_import_source.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[导入确认执行版号查询失败]" in output
    assert "approval_record missing during stale check" in output


def test_confirm_import_by_task_ref_returns_state_unavailable_when_expiry_lookup_fails(capsys) -> None:
    job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="import_to_library",
        state="pending_approval",
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        payload_json="{}",
        version=3,
        lease_owner="",
        lease_until="",
        created_at="2026-04-15 00:00:00",
        updated_at="2026-04-15 00:00:00",
    )
    approval_record = type("ApprovalRecord", (), {"status": "pending", "lease_version": 2})()
    job_repo = type("JobRepo", (), {"get_import_job_for_chat_ref": lambda self, **kwargs: job})()
    approval_repo = type(
        "ApprovalRepo",
        (),
        {
            "get_import_approval": lambda self, **kwargs: approval_record,
            "is_import_pending_expired": lambda self, **kwargs: (
                _ for _ in ()
            ).throw(sqlite3.OperationalError("db down")),
        },
    )()
    get_import_source = AsyncMock(return_value=None)
    service = ImportToLibraryService(
        get_import_source,
        "/data/library/movies",
        job_repo=job_repo,
        approval_repo=approval_repo,
    )

    text = _run(service.confirm_import_by_task_ref("87", chat_id=1001))

    assert text == IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT
    get_import_source.assert_not_awaited()
    output = capsys.readouterr().out
    assert "[导入确认过期判断失败]" in output
    assert "lease_version=2" in output


def test_cancel_pending_import_logs_job_cancel_failure(capsys) -> None:
    pending_job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="import_to_library",
        state="pending_approval",
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        payload_json="{}",
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
            "get_latest_pending_import_job": lambda self, chat_id: pending_job,
            "cancel_pending_job": lambda self, **kwargs: (_ for _ in ()).throw(sqlite3.OperationalError("db down")),
        },
    )()
    approval_repo = type("ApprovalRepo", (), {"cancel_import": lambda self, **kwargs: True})()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", job_repo=job_repo, approval_repo=approval_repo)
    service._resolve_pending_lease_version = lambda **kwargs: 2
    assert service.cancel_pending_import(1001) == IMPORT_CANCEL_STATE_UNAVAILABLE_TEXT
    output = capsys.readouterr().out
    assert "[导入取消任务更新失败]" in output
    assert "job_id=job-1" in output


def test_cancel_pending_import_logs_job_lookup_failure(capsys) -> None:
    job_repo = type(
        "JobRepo",
        (),
        {"get_latest_pending_import_job": lambda self, chat_id: (_ for _ in ()).throw(sqlite3.OperationalError("db down"))},
    )()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", job_repo=job_repo)

    assert service.cancel_pending_import(1001) == IMPORT_CANCEL_STATE_UNAVAILABLE_TEXT

    output = capsys.readouterr().out
    assert "[导入取消查询失败]" in output
    assert "chat_id=1001" in output
    assert "db down" in output
    assert "[处理建议]" in output


def test_cancel_pending_import_logs_missing_job_cancel_result(capsys) -> None:
    pending_job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="import_to_library",
        state="pending_approval",
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        payload_json="{}",
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
            "get_latest_pending_import_job": lambda self, chat_id: pending_job,
            "cancel_pending_job": lambda self, **kwargs: None,
        },
    )()
    approval_repo = type("ApprovalRepo", (), {"cancel_import": lambda self, **kwargs: True})()
    service = ImportToLibraryService(
        AsyncMock(return_value=None),
        "/data/library/movies",
        job_repo=job_repo,
        approval_repo=approval_repo,
    )
    service._resolve_pending_lease_version = lambda **kwargs: 2

    assert service.cancel_pending_import(1001) == IMPORT_CANCEL_STATE_UNAVAILABLE_TEXT

    output = capsys.readouterr().out
    assert "[导入取消任务结果缺失]" in output
    assert "job_id=job-1" in output
    assert "import cancel pending job result missing" in output


def test_handle_expired_pending_confirm_logs_approval_cancel_failure(capsys) -> None:
    approval_repo = type("ApprovalRepo", (), {"cancel_import": lambda self, **kwargs: (_ for _ in ()).throw(sqlite3.OperationalError("db down"))})()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", approval_repo=approval_repo)
    service._is_pending_approval_expired = lambda **kwargs: True
    context = ConfirmExecutionContext(
        job=JobRecord(
            job_id="job-1",
            chat_id=1001,
            user_id=2001,
            workflow_type="import_to_library",
            state="pending_approval",
            task_ref="87",
            task_id="87",
            task_hash="hash-87",
            payload_json="{}",
            version=3,
            lease_owner="",
            lease_until="",
            created_at="2026-04-15 00:00:00",
            updated_at="2026-04-15 00:00:00",
        ),
        approval_record=type("ApprovalRecord", (), {"lease_version": 2})(),
    )
    assert service._handle_expired_pending_confirm(task_ref="87", context=context) == IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT
    output = capsys.readouterr().out
    assert "[导入确认超时审批取消失败]" in output
    assert "lease_version=2" in output
    assert "当前 confirm 会直接返回状态读取失败" in output


def test_handle_expired_pending_confirm_logs_job_cancel_failure(capsys) -> None:
    job_repo = type("JobRepo", (), {"cancel_pending_job": lambda self, **kwargs: (_ for _ in ()).throw(sqlite3.OperationalError("db down"))})()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", job_repo=job_repo)
    service._is_pending_approval_expired = lambda **kwargs: True
    context = ConfirmExecutionContext(
        job=JobRecord(
            job_id="job-1",
            chat_id=1001,
            user_id=2001,
            workflow_type="import_to_library",
            state="pending_approval",
            task_ref="87",
            task_id="87",
            task_hash="hash-87",
            payload_json="{}",
            version=3,
            lease_owner="",
            lease_until="",
            created_at="2026-04-15 00:00:00",
            updated_at="2026-04-15 00:00:00",
        ),
        approval_record=type("ApprovalRecord", (), {"lease_version": 2})(),
    )
    assert service._handle_expired_pending_confirm(task_ref="87", context=context) == IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT
    output = capsys.readouterr().out
    assert "[导入确认超时任务取消失败]" in output
    assert "job_id=job-1" in output
    assert "当前 confirm 会直接返回状态读取失败" in output


def test_handle_expired_pending_confirm_logs_missing_job_during_cancel(capsys) -> None:
    job_repo = type(
        "JobRepo",
        (),
        {
            "cancel_pending_job": lambda self, **kwargs: (_ for _ in ()).throw(
                JobPersistenceError("job missing during cancel")
            )
        },
    )()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", job_repo=job_repo)
    service._is_pending_approval_expired = lambda **kwargs: True
    context = ConfirmExecutionContext(
        job=JobRecord(
            job_id="job-1",
            chat_id=1001,
            user_id=2001,
            workflow_type="import_to_library",
            state="pending_approval",
            task_ref="87",
            task_id="87",
            task_hash="hash-87",
            payload_json="{}",
            version=3,
            lease_owner="",
            lease_until="",
            created_at="2026-04-15 00:00:00",
            updated_at="2026-04-15 00:00:00",
        ),
        approval_record=type("ApprovalRecord", (), {"lease_version": 2})(),
    )

    assert service._handle_expired_pending_confirm(task_ref="87", context=context) == IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT

    output = capsys.readouterr().out
    assert "[导入确认超时任务结果缺失]" in output
    assert "job_id=job-1" in output
    assert "job missing during cancel" in output
    assert "当前 confirm 会直接返回状态读取失败" in output


def test_handle_expired_pending_confirm_logs_job_cancel_state_rejection(capsys) -> None:
    job_repo = type("JobRepo", (), {"cancel_pending_job": lambda self, **kwargs: False})()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", job_repo=job_repo)
    service._is_pending_approval_expired = lambda **kwargs: True
    context = ConfirmExecutionContext(
        job=JobRecord(
            job_id="job-1",
            chat_id=1001,
            user_id=2001,
            workflow_type="import_to_library",
            state="pending_approval",
            task_ref="87",
            task_id="87",
            task_hash="hash-87",
            payload_json="{}",
            version=3,
            lease_owner="",
            lease_until="",
            created_at="2026-04-15 00:00:00",
            updated_at="2026-04-15 00:00:00",
        ),
        approval_record=type("ApprovalRecord", (), {"lease_version": 2})(),
    )
    assert service._handle_expired_pending_confirm(task_ref="87", context=context) == IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT
    output = capsys.readouterr().out
    assert "[导入确认超时任务取消失败]" in output
    assert "当前 confirm 会直接返回状态读取失败" in output
    assert "jobs.cancel_pending_job rejected current state" in output


def test_cancel_pending_import_logs_job_cancel_state_rejection(capsys) -> None:
    pending_job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="import_to_library",
        state="pending_approval",
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        payload_json="{}",
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
            "get_latest_pending_import_job": lambda self, chat_id: pending_job,
            "cancel_pending_job": lambda self, **kwargs: False,
        },
    )()
    approval_repo = type("ApprovalRepo", (), {"cancel_import": lambda self, **kwargs: True})()
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies", job_repo=job_repo, approval_repo=approval_repo)
    service._resolve_pending_lease_version = lambda **kwargs: 2

    assert service.cancel_pending_import(1001) == IMPORT_CANCEL_STATE_UNAVAILABLE_TEXT

    output = capsys.readouterr().out
    assert "[导入取消任务更新失败]" in output
    assert "jobs.cancel_pending_job rejected current state" in output


def test_cancel_pending_import_returns_state_unavailable_when_approval_cancel_rejected(capsys) -> None:
    pending_job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="import_to_library",
        state="pending_approval",
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        payload_json="{}",
        version=3,
        lease_owner="",
        lease_until="",
        created_at="2026-04-15 00:00:00",
        updated_at="2026-04-15 00:00:00",
    )
    job_repo = type("JobRepo", (), {"get_latest_pending_import_job": lambda self, chat_id: pending_job})()
    approval_repo = type("ApprovalRepo", (), {"cancel_import": lambda self, **kwargs: False})()
    service = ImportToLibraryService(
        AsyncMock(return_value=None),
        "/data/library/movies",
        job_repo=job_repo,
        approval_repo=approval_repo,
    )
    service._resolve_pending_lease_version = lambda **kwargs: 2

    assert service.cancel_pending_import(1001) == IMPORT_CANCEL_STATE_UNAVAILABLE_TEXT

    output = capsys.readouterr().out
    assert "[导入取消审批更新失败]" in output
    assert "approval_record missing or lease_version mismatch" in output


def test_cancel_pending_import_returns_state_unavailable_when_approval_cancel_result_is_missing(capsys) -> None:
    pending_job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type=WORKFLOW_IMPORT_TO_LIBRARY,
        state=JOB_STATE_PENDING_APPROVAL,
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        payload_json="{}",
        version=3,
        lease_owner="",
        lease_until="",
        created_at="2026-04-15 00:00:00",
        updated_at="2026-04-15 00:00:00",
    )
    job_repo = type("JobRepo", (), {"get_latest_pending_import_job": lambda self, chat_id: pending_job})()
    approval_repo = type("ApprovalRepo", (), {"cancel_import": lambda self, **kwargs: None})()
    service = ImportToLibraryService(
        AsyncMock(return_value=None),
        "/data/library/movies",
        job_repo=job_repo,
        approval_repo=approval_repo,
    )
    service._resolve_pending_lease_version = lambda **kwargs: 2

    assert service.cancel_pending_import(1001) == IMPORT_CANCEL_STATE_UNAVAILABLE_TEXT

    output = capsys.readouterr().out
    assert "[导入取消审批结果缺失]" in output
    assert "import cancel approval result missing" in output
    assert "lease_version=2" in output


def test_cancel_pending_import_returns_state_unavailable_when_pending_lease_missing(capsys) -> None:
    pending_job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="import_to_library",
        state="pending_approval",
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        payload_json="{}",
        version=3,
        lease_owner="",
        lease_until="",
        created_at="2026-04-15 00:00:00",
        updated_at="2026-04-15 00:00:00",
    )
    job_repo = type("JobRepo", (), {"get_latest_pending_import_job": lambda self, chat_id: pending_job})()
    service = ImportToLibraryService(
        AsyncMock(return_value=None),
        "/data/library/movies",
        job_repo=job_repo,
    )
    service._resolve_pending_lease_version = lambda **kwargs: 0

    assert service.cancel_pending_import(1001) == IMPORT_CANCEL_STATE_UNAVAILABLE_TEXT

    output = capsys.readouterr().out
    assert "[导入取消状态读取失败]" in output
    assert "import approval pending lease missing" in output


def test_cancel_pending_import_returns_state_unavailable_when_pending_lease_lookup_fails(
    capsys,
) -> None:
    pending_job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="import_to_library",
        state="pending_approval",
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        payload_json="{}",
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
            "get_latest_pending_import_job": lambda self, chat_id: pending_job,
            "cancel_pending_job": lambda self, **kwargs: (_ for _ in ()).throw(AssertionError("cancel_pending_job should not be called")),
        },
    )()
    approval_repo = type(
        "ApprovalRepo",
        (),
        {
            "get_import_approval": lambda self, **kwargs: (_ for _ in ()).throw(sqlite3.OperationalError("db down")),
            "cancel_import": lambda self, **kwargs: (_ for _ in ()).throw(AssertionError("cancel_import should not be called")),
        },
    )()
    service = ImportToLibraryService(
        AsyncMock(return_value=None),
        "/data/library/movies",
        approval_repo=approval_repo,
        job_repo=job_repo,
    )
    service._pending_import_identities.add((pending_job.task_id, pending_job.task_hash))
    service._pending_import_lease_versions[(pending_job.task_id, pending_job.task_hash)] = 2

    assert service.cancel_pending_import(1001) == IMPORT_CANCEL_STATE_UNAVAILABLE_TEXT

    output = capsys.readouterr().out
    assert "[导入待确认版号查询失败]" in output
    assert "[导入取消状态读取失败]" in output
    assert "import approval pending lease lookup failed" in output


def test_cancel_pending_import_returns_state_unavailable_when_pending_approval_row_missing_with_in_memory_pending(
    capsys,
) -> None:
    pending_job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="import_to_library",
        state="pending_approval",
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        payload_json="{}",
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
            "get_latest_pending_import_job": lambda self, chat_id: pending_job,
            "cancel_pending_job": lambda self, **kwargs: (_ for _ in ()).throw(AssertionError("cancel_pending_job should not be called")),
        },
    )()
    approval_repo = type(
        "ApprovalRepo",
        (),
        {
            "get_import_approval": lambda self, **kwargs: None,
            "cancel_import": lambda self, **kwargs: (_ for _ in ()).throw(AssertionError("cancel_import should not be called")),
        },
    )()
    service = ImportToLibraryService(
        AsyncMock(return_value=None),
        "/data/library/movies",
        approval_repo=approval_repo,
        job_repo=job_repo,
    )
    service._pending_import_identities.add((pending_job.task_id, pending_job.task_hash))
    service._pending_import_lease_versions[(pending_job.task_id, pending_job.task_hash)] = 2

    assert service.cancel_pending_import(1001) == IMPORT_CANCEL_STATE_UNAVAILABLE_TEXT

    output = capsys.readouterr().out
    assert "[导入待确认版号查询失败]" in output
    assert "approval_record missing while in-memory pending exists" in output
    assert "[导入取消状态读取失败]" in output
    assert "import approval pending lease lookup failed" in output


@pytest.mark.parametrize(
    ("payload_json", "expected_summary"),
    [
        ("{", "payload_json invalid json"),
        ("[]", "payload_json not object"),
    ],
)
def test_resolve_execution_mode_logs_copy_fallback_payload_corruption(
    payload_json: str,
    expected_summary: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies")
    context = ConfirmExecutionContext(
        job=JobRecord(
            job_id="job-1",
            chat_id=1001,
            user_id=2001,
            workflow_type="import_to_library",
            state="pending_approval",
            task_ref="87",
            task_id="87",
            task_hash="hash-87",
            payload_json=payload_json,
            version=3,
            lease_owner="",
            lease_until="",
            created_at="2026-04-15 00:00:00",
            updated_at="2026-04-15 00:00:00",
        ),
        approval_record=None,
    )

    assert (
        service._resolve_execution_mode(
            task_id="87",
            task_hash="hash-87",
            confirm_context=context,
        )
        is None
    )

    output = capsys.readouterr().out
    assert "[导入执行模式载荷损坏]" in output
    assert "task_id=87" in output
    assert "task_hash=hash-87" in output
    assert expected_summary in output
    assert "[处理建议]" in output


def test_resolve_execution_mode_uses_in_memory_copy_fallback_when_payload_corrupted(
    capsys: pytest.CaptureFixture[str],
) -> None:
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies")
    service._record_copy_fallback_pending(task_id="87", task_hash="hash-87")
    context = ConfirmExecutionContext(
        job=JobRecord(
            job_id="job-1",
            chat_id=1001,
            user_id=2001,
            workflow_type="import_to_library",
            state="pending_approval",
            task_ref="87",
            task_id="87",
            task_hash="hash-87",
            payload_json="{",
            version=3,
            lease_owner="",
            lease_until="",
            created_at="2026-04-15 00:00:00",
            updated_at="2026-04-15 00:00:00",
        ),
        approval_record=None,
    )

    assert (
        service._resolve_execution_mode(
            task_id="87",
            task_hash="hash-87",
            confirm_context=context,
        )
        == import_module.IMPORT_EXECUTION_MODE_COPY
    )
    assert "[导入执行模式载荷损坏]" in capsys.readouterr().out


def test_confirm_import_by_task_ref_returns_state_unavailable_on_copy_fallback_payload_corruption(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="import_to_library",
        state="pending_approval",
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        payload_json="{",
        version=3,
        lease_owner="",
        lease_until="",
        created_at="2026-04-15 00:00:00",
        updated_at="2026-04-15 00:00:00",
    )
    approval_record = type(
        "ApprovalRecord",
        (),
        {"status": APPROVAL_STATUS_PENDING, "lease_version": 2, "executed_version": 0},
    )()
    service = ImportToLibraryService(
        AsyncMock(return_value=import_source),
        str(tmp_path / "library"),
        job_repo=type(
            "JobRepo",
            (),
            {
                "get_import_job_for_chat_ref": lambda self, **kwargs: job,
                "claim_lease": lambda self, **kwargs: True,
                "release_lease_to_pending": lambda self, **kwargs: True,
            },
        )(),
        approval_repo=type(
            "ApprovalRepo",
            (),
            {
                "get_import_approval": lambda self, **kwargs: approval_record,
                "is_import_pending_expired": lambda self, **kwargs: False,
            },
        )(),
    )

    text = _run(service.confirm_import_by_task_ref("87", chat_id=1001))

    assert text == IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT
    output = capsys.readouterr().out
    assert "[导入执行模式载荷损坏]" in output
    assert "task_id=87" in output


def test_confirm_import_by_task_ref_appends_warning_when_executed_version_write_fails(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")
    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="import_to_library",
        state="pending_approval",
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        payload_json="{}",
        version=3,
        lease_owner="",
        lease_until="",
        created_at="2026-04-15 00:00:00",
        updated_at="2026-04-15 00:00:00",
    )
    approval_record = type(
        "ApprovalRecord",
        (),
        {"status": APPROVAL_STATUS_PENDING, "lease_version": 2, "executed_version": 0},
    )()
    service = ImportToLibraryService(
        AsyncMock(return_value=import_source),
        str(tmp_path / "library"),
        job_repo=type(
            "JobRepo",
            (),
            {
                "get_import_job_for_chat_ref": lambda self, **kwargs: job,
                "claim_lease": lambda self, **kwargs: True,
                "mark_completed": lambda self, **kwargs: True,
            },
        )(),
        approval_repo=type(
            "ApprovalRepo",
            (),
            {
                    "get_import_approval": lambda self, **kwargs: approval_record,
                    "is_import_pending_expired": lambda self, **kwargs: False,
                    "approve_import": lambda self, **kwargs: True,
                    "mark_import_executed": lambda self, **kwargs: (
                        _ for _ in ()
                    ).throw(sqlite3.OperationalError("db down")),
                },
            )(),
        )

    async def _fake_execute_import(*_: object, **__: object) -> import_module.ImportExecutionResult:
        return import_module.ImportExecutionResult(reply="导入成功：Dune.2021.mkv", imported=True)

    service._execute_import = _fake_execute_import  # type: ignore[method-assign]

    text = _run(service.confirm_import_by_task_ref("87", chat_id=1001))

    assert "导入成功：Dune.2021.mkv" in text
    assert IMPORT_FINALIZATION_WARNING_TEXT in text
    output = capsys.readouterr().out
    assert "[导入执行版号回写失败]" in output
    assert "db down" in output


def test_confirm_import_by_task_ref_appends_warning_when_job_completion_write_fails(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")
    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="import_to_library",
        state="pending_approval",
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        payload_json="{}",
        version=3,
        lease_owner="",
        lease_until="",
        created_at="2026-04-15 00:00:00",
        updated_at="2026-04-15 00:00:00",
    )
    approval_record = type(
        "ApprovalRecord",
        (),
        {"status": APPROVAL_STATUS_PENDING, "lease_version": 2, "executed_version": 0},
    )()
    service = ImportToLibraryService(
        AsyncMock(return_value=import_source),
        str(tmp_path / "library"),
        job_repo=type(
            "JobRepo",
            (),
            {
                "get_import_job_for_chat_ref": lambda self, **kwargs: job,
                "claim_lease": lambda self, **kwargs: True,
                "mark_completed": lambda self, **kwargs: (_ for _ in ()).throw(sqlite3.OperationalError("db down")),
            },
        )(),
        approval_repo=type(
            "ApprovalRepo",
            (),
            {
                "get_import_approval": lambda self, **kwargs: approval_record,
                "is_import_pending_expired": lambda self, **kwargs: False,
                "approve_import": lambda self, **kwargs: True,
                "mark_import_executed": lambda self, **kwargs: None,
            },
        )(),
    )

    async def _fake_execute_import(*_: object, **__: object) -> import_module.ImportExecutionResult:
        return import_module.ImportExecutionResult(reply="导入成功：Dune.2021.mkv", imported=True)

    service._execute_import = _fake_execute_import  # type: ignore[method-assign]

    text = _run(service.confirm_import_by_task_ref("87", chat_id=1001))

    assert "导入成功：Dune.2021.mkv" in text
    assert IMPORT_FINALIZATION_WARNING_TEXT in text
    output = capsys.readouterr().out
    assert "[导入确认任务完结失败]" in output
    assert "db down" in output


def test_confirm_import_by_task_ref_appends_warning_when_job_completion_result_is_missing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")
    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    job = JobRecord(
        job_id="job-1",
        chat_id=1001,
        user_id=2001,
        workflow_type="import_to_library",
        state="pending_approval",
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        payload_json="{}",
        version=3,
        lease_owner="",
        lease_until="",
        created_at="2026-04-15 00:00:00",
        updated_at="2026-04-15 00:00:00",
    )
    approval_record = type(
        "ApprovalRecord",
        (),
        {"status": APPROVAL_STATUS_PENDING, "lease_version": 2, "executed_version": 0},
    )()
    service = ImportToLibraryService(
        AsyncMock(return_value=import_source),
        str(tmp_path / "library"),
        job_repo=type(
            "JobRepo",
            (),
            {
                "get_import_job_for_chat_ref": lambda self, **kwargs: job,
                "claim_lease": lambda self, **kwargs: True,
                "mark_completed": lambda self, **kwargs: None,
            },
        )(),
        approval_repo=type(
            "ApprovalRepo",
            (),
            {
                "get_import_approval": lambda self, **kwargs: approval_record,
                "is_import_pending_expired": lambda self, **kwargs: False,
                "approve_import": lambda self, **kwargs: True,
                "mark_import_executed": lambda self, **kwargs: None,
            },
        )(),
    )

    async def _fake_execute_import(*_: object, **__: object) -> import_module.ImportExecutionResult:
        return import_module.ImportExecutionResult(reply="导入成功：Dune.2021.mkv", imported=True)

    service._execute_import = _fake_execute_import  # type: ignore[method-assign]

    text = _run(service.confirm_import_by_task_ref("87", chat_id=1001))

    assert "导入成功：Dune.2021.mkv" in text
    assert IMPORT_FINALIZATION_WARNING_TEXT in text
    output = capsys.readouterr().out
    assert "[导入确认任务完结结果缺失]" in output
    assert "import completed job result missing" in output


def test_confirm_import_by_task_ref_success_with_refresh_success(tmp_path: Path) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    target_dir = tmp_path / "library"
    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    refresh = AsyncMock(return_value="媒体库刷新成功。")
    service = ImportToLibraryService(
        AsyncMock(return_value=import_source),
        str(target_dir),
        refresh_media_server_func=refresh,
    )

    _run(service.import_by_task_ref("87"))
    text = _run(service.confirm_import_by_task_ref("87"))

    assert "导入成功" in text
    assert "媒体库刷新成功。" in text
    assert "后处理总结" in text
    refresh.assert_awaited_once()


def test_confirm_import_by_task_ref_success_with_refresh_failure_text(tmp_path: Path) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    target_dir = tmp_path / "library"
    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    refresh = AsyncMock(return_value="媒体库刷新失败：connection timeout")
    service = ImportToLibraryService(
        AsyncMock(return_value=import_source),
        str(target_dir),
        refresh_media_server_func=refresh,
    )

    _run(service.import_by_task_ref("87"))
    text = _run(service.confirm_import_by_task_ref("87"))

    assert "导入成功" in text
    assert "媒体库刷新失败：connection timeout" in text
    assert "后处理总结" in text
    refresh.assert_awaited_once()


def test_confirm_import_by_task_ref_success_with_refresh_exception(tmp_path: Path) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    target_dir = tmp_path / "library"
    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    refresh = AsyncMock(side_effect=RuntimeError("boom"))
    service = ImportToLibraryService(
        AsyncMock(return_value=import_source),
        str(target_dir),
        refresh_media_server_func=refresh,
    )

    _run(service.import_by_task_ref("87"))
    text = _run(service.confirm_import_by_task_ref("87"))

    assert "导入成功" in text
    assert IMPORT_REFRESH_FAILED_TEXT in text
    assert "后处理总结" in text
    refresh.assert_awaited_once()


def test_confirm_import_by_task_ref_re_raises_non_runtime_refresh_error(tmp_path: Path) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    target_dir = tmp_path / "library"
    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    refresh = AsyncMock(side_effect=ValueError("bad refresh stub"))
    service = ImportToLibraryService(
        AsyncMock(return_value=import_source),
        str(target_dir),
        refresh_media_server_func=refresh,
    )

    _run(service.import_by_task_ref("87"))
    with pytest.raises(ValueError, match="bad refresh stub"):
        _run(service.confirm_import_by_task_ref("87"))


def test_import_by_task_ref_not_found() -> None:
    service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies")
    text = _run(service.import_by_task_ref("missing"))
    assert text == IMPORT_NOT_FOUND_TEXT


def test_import_by_task_ref_not_completed(tmp_path: Path) -> None:
    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name="Dune.2021.mkv",
        download_dir=str(tmp_path / "downloads"),
        is_finished=False,
        percent_done=0.42,
    )
    service = ImportToLibraryService(AsyncMock(return_value=import_source), str(tmp_path / "library"))
    text = _run(service.import_by_task_ref("87"))
    assert text == IMPORT_NOT_COMPLETED_TEXT.format(progress=42.0)


def test_confirm_import_by_task_ref_not_completed_does_not_refresh(tmp_path: Path) -> None:
    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name="Dune.2021.mkv",
        download_dir=str(tmp_path / "downloads"),
        is_finished=False,
        percent_done=0.42,
    )
    refresh = AsyncMock(return_value="媒体库刷新成功。")
    service = ImportToLibraryService(
        AsyncMock(return_value=import_source),
        str(tmp_path / "library"),
        refresh_media_server_func=refresh,
    )

    text = _run(service.confirm_import_by_task_ref("87"))
    assert text == IMPORT_NOT_COMPLETED_TEXT.format(progress=42.0)
    refresh.assert_not_called()


def test_import_by_task_ref_source_missing(tmp_path: Path) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name="missing.mkv",
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    service = ImportToLibraryService(AsyncMock(return_value=import_source), str(tmp_path / "library"))
    text = _run(service.import_by_task_ref("87"))
    assert text == IMPORT_SOURCE_MISSING_TEXT


def test_confirm_import_by_task_ref_cross_filesystem_error(tmp_path: Path, monkeypatch) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    service = ImportToLibraryService(AsyncMock(return_value=import_source), str(tmp_path / "library"))

    def _raise_exdev(src: str | Path, dst: str | Path) -> None:
        raise OSError(errno.EXDEV, "Invalid cross-device link")

    _run(service.import_by_task_ref("87"))
    monkeypatch.setattr(import_module.import_transfer_execution.os, "link", _raise_exdev)
    text = _run(service.confirm_import_by_task_ref("87"))
    assert text == IMPORT_COPY_APPROVAL_PENDING_TEXT.format(task_ref="87")


def test_import_by_task_ref_with_auto_confirm_keeps_copy_fallback_confirmation(tmp_path: Path, monkeypatch) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    service = ImportToLibraryService(AsyncMock(return_value=import_source), str(tmp_path / "library"))

    def _raise_exdev(src: str | Path, dst: str | Path) -> None:
        raise OSError(errno.EXDEV, "Invalid cross-device link")

    monkeypatch.setattr(import_module.import_transfer_execution.os, "link", _raise_exdev)
    text = _run(service.import_by_task_ref_with_auto_confirm("87"))

    assert text == IMPORT_COPY_APPROVAL_PENDING_TEXT.format(task_ref="87")


def test_confirm_failure_restores_pending_without_advancing_lease(tmp_path: Path, monkeypatch) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    approval_repo = ApprovalRepo(database)

    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    service = ImportToLibraryService(
        get_import_source_func=AsyncMock(return_value=import_source),
        library_target_dir=str(tmp_path / "library"),
        approval_repo=approval_repo,
    )

    _run(service.import_by_task_ref("87"))
    def _raise_exdev(src: str | Path, dst: str | Path) -> None:
        raise OSError(errno.EXDEV, "Invalid cross-device link")

    monkeypatch.setattr(import_module.import_transfer_execution.os, "link", _raise_exdev)
    first_confirm = _run(service.confirm_import_by_task_ref("87"))
    assert first_confirm == IMPORT_COPY_APPROVAL_PENDING_TEXT.format(task_ref="87")

    failed_record = approval_repo.get_import_approval(task_id="87", task_hash="hash-87")
    assert failed_record is not None
    assert failed_record.status == APPROVAL_STATUS_PENDING
    assert failed_record.lease_version == 1
    assert failed_record.executed_version == 0

    def _unexpected_hardlink(src: str | Path, dst: str | Path) -> None:
        raise AssertionError("copy confirm should not call os.link again")

    monkeypatch.setattr(import_module.import_transfer_execution.os, "link", _unexpected_hardlink)
    second_confirm = _run(service.confirm_import_by_task_ref("87"))
    assert "导入成功" in second_confirm
    assert "导入方式: 复制" in second_confirm
    target_file = tmp_path / "library" / "Dune (2021).mkv"
    assert target_file.exists()
    assert source_file.stat().st_ino != target_file.stat().st_ino

    succeeded_record = approval_repo.get_import_approval(task_id="87", task_hash="hash-87")
    assert succeeded_record is not None
    assert succeeded_record.status == APPROVAL_STATUS_APPROVED
    assert succeeded_record.lease_version == 1
    assert succeeded_record.executed_version == 1


def test_confirm_import_logs_hardlink_failure(tmp_path: Path, monkeypatch, capsys) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    service = ImportToLibraryService(
        get_import_source_func=AsyncMock(return_value=import_source),
        library_target_dir=str(tmp_path / "library"),
    )

    _run(service.import_by_task_ref("87"))

    def _raise_hardlink_failure(src: str | Path, dst: str | Path) -> None:
        raise OSError(errno.EPERM, "permission denied")

    monkeypatch.setattr(import_module.import_transfer_execution.os, "link", _raise_hardlink_failure)

    text = _run(service.confirm_import_by_task_ref("87"))

    assert text == IMPORT_HARDLINK_FAILED_TEXT.format(reason="[Errno 1] permission denied")
    output = capsys.readouterr().out
    assert "[导入硬链接失败]" in output
    assert "task_id=87" in output
    assert "permission denied" in output
    assert "[处理建议]" in output


def test_confirm_import_copy_fallback_copies_matching_external_subtitles(tmp_path: Path, monkeypatch) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")
    source_subtitle = download_dir / "Dune.2021.en.srt"
    source_subtitle.write_text("1\n00:00:01,000 --> 00:00:03,000\nhello dune\n", encoding="utf-8")

    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    approval_repo = ApprovalRepo(database)
    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    service = ImportToLibraryService(
        get_import_source_func=AsyncMock(return_value=import_source),
        library_target_dir=str(tmp_path / "library"),
        approval_repo=approval_repo,
    )

    _run(service.import_by_task_ref("87"))

    def _raise_exdev(src: str | Path, dst: str | Path) -> None:
        raise OSError(errno.EXDEV, "Invalid cross-device link")

    monkeypatch.setattr(import_module.import_transfer_execution.os, "link", _raise_exdev)
    first_confirm = _run(service.confirm_import_by_task_ref("87"))
    assert first_confirm == IMPORT_COPY_APPROVAL_PENDING_TEXT.format(task_ref="87")

    def _unexpected_hardlink(src: str | Path, dst: str | Path) -> None:
        raise AssertionError("copy confirm should not call os.link again")

    monkeypatch.setattr(import_module.import_transfer_execution.os, "link", _unexpected_hardlink)
    second_confirm = _run(service.confirm_import_by_task_ref("87"))

    assert "导入成功" in second_confirm
    assert "导入方式: 复制" in second_confirm
    target_file = tmp_path / "library" / "Dune (2021).mkv"
    target_subtitle = tmp_path / "library" / "Dune (2021).en.srt"
    assert target_file.exists()
    assert target_subtitle.exists()
    assert source_file.stat().st_ino != target_file.stat().st_ino
    assert source_subtitle.stat().st_ino != target_subtitle.stat().st_ino


def test_confirm_import_copy_fallback_preserves_directoryized_movie_sidecars(tmp_path: Path, monkeypatch) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Akron.2015.1080p.AMZN.WEB-DL.DDP2.0.H.264-NZMA.mkv"
    source_file.write_bytes(b"demo")
    source_subtitle = download_dir / "Akron.2015.1080p.AMZN.WEB-DL.DDP2.0.H.264-NZMA.zh.srt"
    source_subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\nhello\n", encoding="utf-8")

    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    approval_repo = ApprovalRepo(database)
    event_repo = JobEventRepo(database)
    event_repo.append_event(
        task_ref="1",
        task_id="20",
        task_hash="hash-20",
        event_type=MEDIA_IDENTITY_EVENT_TYPE,
        message=media_identity_to_json(
            {
                "media_type": "movie",
                "tmdb_id": "361018",
                "title": "爱的进行时",
                "original_title": "Akron",
                "year": "2015",
                "source": "search_confirmed",
            }
        ),
    )

    import_source = TransmissionImportSource(
        task_id="20",
        task_hash="hash-20",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    service = ImportToLibraryService(
        get_import_source_func=AsyncMock(return_value=import_source),
        library_target_dir=str(tmp_path / "library"),
        approval_repo=approval_repo,
        job_event_repo=event_repo,
    )

    _run(service.import_by_task_ref("20"))

    def _raise_exdev(src: str | Path, dst: str | Path) -> None:
        raise OSError(errno.EXDEV, "Invalid cross-device link")

    monkeypatch.setattr(import_module.import_transfer_execution.os, "link", _raise_exdev)
    first_confirm = _run(service.confirm_import_by_task_ref("20"))
    assert first_confirm == IMPORT_COPY_APPROVAL_PENDING_TEXT.format(task_ref="20")

    def _unexpected_hardlink(src: str | Path, dst: str | Path) -> None:
        raise AssertionError("copy confirm should not call os.link again")

    monkeypatch.setattr(import_module.import_transfer_execution.os, "link", _unexpected_hardlink)
    second_confirm = _run(service.confirm_import_by_task_ref("20"))

    target_directory = tmp_path / "library" / "爱的进行时 (2015)"
    target_file = target_directory / "爱的进行时 (2015).mkv"
    target_subtitle = target_directory / "爱的进行时 (2015).zh.srt"
    assert "导入成功" in second_confirm
    assert "导入方式: 复制" in second_confirm
    assert target_directory.is_dir()
    assert target_file.exists()
    assert target_subtitle.exists()
    assert source_file.stat().st_ino != target_file.stat().st_ino
    assert source_subtitle.stat().st_ino != target_subtitle.stat().st_ino


def test_execute_import_logs_copy_failure(tmp_path: Path, monkeypatch, capsys) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")
    target_path = tmp_path / "library" / "Dune (2021).mkv"

    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    prepared = PreparedImport(
        import_source=import_source,
        source_path=source_file,
        target_path=target_path,
    )
    service = ImportToLibraryService(
        get_import_source_func=AsyncMock(return_value=import_source),
        library_target_dir=str(tmp_path / "library"),
    )

    def _raise_copy_failure(src: str | Path, dst: str | Path) -> None:
        raise OSError(errno.ENOSPC, "no space left on device")

    monkeypatch.setattr(import_module.import_transfer_execution.shutil, "copy2", _raise_copy_failure)

    result = _run(
        service._execute_import(
            "87",
            prepared,
            execution_mode=import_module.IMPORT_EXECUTION_MODE_COPY,
        )
    )

    assert result.reply == IMPORT_COPY_FAILED_TEXT.format(reason="[Errno 28] no space left on device")
    assert result.imported is False
    output = capsys.readouterr().out
    assert "[导入复制失败]" in output
    assert "task_id=87" in output
    assert "no space left on device" in output
    assert "[处理建议]" in output


def test_execute_import_logs_partial_target_cleanup_failure(tmp_path: Path, monkeypatch, capsys) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")
    target_path = tmp_path / "library" / "Dune (2021).mkv"

    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    prepared = PreparedImport(
        import_source=import_source,
        source_path=source_file,
        target_path=target_path,
    )
    service = ImportToLibraryService(
        get_import_source_func=AsyncMock(return_value=import_source),
        library_target_dir=str(tmp_path / "library"),
    )

    def _raise_copy_failure_with_partial_target(src: str | Path, dst: str | Path) -> None:
        dst_path = Path(dst)
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        dst_path.write_bytes(b"partial")
        raise OSError(errno.ENOSPC, "no space left on device")

    original_unlink = type(target_path).unlink

    def _raise_cleanup_failure(self: Path, *args, **kwargs) -> None:
        if self == target_path:
            raise OSError(errno.EBUSY, "device or resource busy")
        return original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(import_module.import_transfer_execution.shutil, "copy2", _raise_copy_failure_with_partial_target)
    monkeypatch.setattr(type(target_path), "unlink", _raise_cleanup_failure)

    result = _run(
        service._execute_import(
            "87",
            prepared,
            execution_mode=import_module.IMPORT_EXECUTION_MODE_COPY,
        )
    )

    assert result.reply == IMPORT_COPY_FAILED_TEXT.format(reason="[Errno 28] no space left on device")
    assert result.imported is False
    output = capsys.readouterr().out
    assert "[导入残留清理失败]" in output
    assert str(target_path) in output
    assert "device or resource busy" in output
    assert "[处理建议]" in output


def test_confirm_import_logs_target_exists_during_execute(tmp_path: Path, monkeypatch, capsys) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")
    target_path = tmp_path / "library" / "Dune (2021).mkv"

    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    service = ImportToLibraryService(
        get_import_source_func=AsyncMock(return_value=import_source),
        library_target_dir=str(tmp_path / "library"),
    )

    _run(service.import_by_task_ref("87"))

    def _raise_target_exists(src: str | Path, dst: str | Path) -> None:
        raise FileExistsError(str(dst))

    monkeypatch.setattr(import_module.import_transfer_execution.os, "link", _raise_target_exists)

    text = _run(service.confirm_import_by_task_ref("87"))

    assert text == f"目标已存在，已拒绝覆盖：{target_path}"
    output = capsys.readouterr().out
    assert "[导入目标已存在]" in output
    assert "task_id=87" in output
    assert str(target_path) in output
    assert "[处理建议]" in output


def test_confirm_import_by_task_ref_rejects_expired_pending(tmp_path: Path) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")

    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    approval_repo = ApprovalRepo(database)
    job_repo = JobRepo(database)

    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    service = ImportToLibraryService(
        get_import_source_func=AsyncMock(return_value=import_source),
        library_target_dir=str(tmp_path / "library"),
        approval_repo=approval_repo,
        job_repo=job_repo,
    )
    job_repo.upsert_downloader_job_pending(
        chat_id=1001,
        user_id=2001,
        task_ref="87",
        task_id="87",
        task_hash="hash-87",
        payload_json=json.dumps({"auto_import_enabled": True}),
    )

    pending_text = _run(service.import_by_task_ref("87", chat_id=1001, user_id=2001))
    assert "导入待确认" in pending_text

    with database.connect() as connection:
        connection.execute(
            """
            UPDATE approval_record
            SET expires_at = '2000-01-01 00:00:00'
            WHERE action_type = 'import_to_library' AND task_id = '87' AND task_hash = 'hash-87'
            """
        )
        connection.commit()

    confirm_text = _run(service.confirm_import_by_task_ref("87", chat_id=1001, user_id=2001))
    assert confirm_text == IMPORT_CONFIRM_EXPIRED_TEXT

    record = approval_repo.get_import_approval(task_id="87", task_hash="hash-87")
    assert record is not None
    assert record.status == APPROVAL_STATUS_CANCELLED

    job = job_repo.get_import_job_for_chat_ref(chat_id=1001, task_ref="87")
    assert job is not None
    assert job.state == JOB_STATE_CANCELLED


def test_import_by_task_ref_persists_pending_approval(tmp_path: Path) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")
    target_dir = tmp_path / "library"

    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    approval_repo = ApprovalRepo(database)
    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    service = ImportToLibraryService(
        AsyncMock(return_value=import_source),
        str(target_dir),
        approval_repo=approval_repo,
    )

    text = _run(service.import_by_task_ref("87"))
    assert "导入待确认" in text

    record = approval_repo.get_import_approval(task_id="87", task_hash="hash-87")
    assert record is not None
    assert record.status == APPROVAL_STATUS_PENDING
    assert record.last_task_ref == "87"


def test_confirm_import_by_task_ref_promotes_pending_to_approved(tmp_path: Path) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.2021.mkv"
    source_file.write_bytes(b"demo")
    target_dir = tmp_path / "library"

    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    approval_repo = ApprovalRepo(database)
    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    service = ImportToLibraryService(
        AsyncMock(return_value=import_source),
        str(target_dir),
        approval_repo=approval_repo,
    )

    _run(service.import_by_task_ref("87"))
    text = _run(service.confirm_import_by_task_ref("87"))
    assert "导入成功" in text

    record = approval_repo.get_import_approval(task_id="87", task_hash="hash-87")
    assert record is not None
    assert record.status == APPROVAL_STATUS_APPROVED


def test_confirm_import_prefers_downloader_title_for_normalized_name(tmp_path: Path) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Dune.Part.Two.2024.1080p.WEB-DL.mkv"
    source_file.write_bytes(b"demo")
    target_dir = tmp_path / "library"

    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    event_repo = JobEventRepo(database)
    event_repo.append_event(
        task_ref="1",
        task_id="87",
        task_hash="hash-87",
        event_type="downloader.succeeded",
        message="Dune: Part Two 2024",
    )

    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    service = ImportToLibraryService(
        get_import_source_func=AsyncMock(return_value=import_source),
        library_target_dir=str(target_dir),
        job_event_repo=event_repo,
    )

    _run(service.import_by_task_ref("87"))
    text = _run(service.confirm_import_by_task_ref("87"))

    target_file = target_dir / "Dune Part Two (2024).mkv"
    assert target_file.exists()
    assert str(target_file) in text


def test_resolve_normalized_naming_truth_logs_missing_result(capsys: pytest.CaptureFixture[str]) -> None:
    event_repo = type("EventRepo", (), {"list_events_for_task_identity": lambda self, **kwargs: None})()
    service = ImportToLibraryService(
        get_import_source_func=AsyncMock(return_value=None),
        library_target_dir="/data/library/movies",
        job_event_repo=event_repo,
    )

    result = service._resolve_normalized_naming_truth(
        task_id="87",
        task_hash="hash-87",
        fallback_name="Dune.Part.Two.2024.1080p.WEB-DL.mkv",
    )

    assert result == "Dune.Part.Two.2024.1080p.WEB-DL.mkv"
    output = capsys.readouterr().out
    assert "[导入命名真相结果缺失]" in output
    assert "import naming truth result missing" in output
    assert "task_id=87" in output
    assert "task_hash=hash-87" in output
    assert "[处理建议]" in output


def test_resolve_normalized_naming_truth_logs_query_failure(capsys: pytest.CaptureFixture[str]) -> None:
    event_repo = type(
        "EventRepo",
        (),
        {"list_events_for_task_identity": lambda self, **kwargs: (_ for _ in ()).throw(sqlite3.OperationalError("db down"))},
    )()
    service = ImportToLibraryService(
        get_import_source_func=AsyncMock(return_value=None),
        library_target_dir="/data/library/movies",
        job_event_repo=event_repo,
    )

    result = service._resolve_normalized_naming_truth(
        task_id="87",
        task_hash="hash-87",
        fallback_name="Dune.Part.Two.2024.1080p.WEB-DL.mkv",
    )

    assert result == "Dune.Part.Two.2024.1080p.WEB-DL.mkv"
    output = capsys.readouterr().out
    assert "[导入命名真相查询失败]" in output
    assert "db down" in output
    assert "task_id=87" in output
    assert "task_hash=hash-87" in output
    assert "[处理建议]" in output


def test_resolve_normalized_naming_truth_logs_row_corruption(capsys: pytest.CaptureFixture[str]) -> None:
    event_repo = type(
        "EventRepo",
        (),
        {
            "list_events_for_task_identity": lambda self, **kwargs: (_ for _ in ()).throw(
                JobEventPersistenceError("job_event row identity corrupted after read")
            )
        },
    )()
    service = ImportToLibraryService(
        get_import_source_func=AsyncMock(return_value=None),
        library_target_dir="/data/library/movies",
        job_event_repo=event_repo,
    )

    result = service._resolve_normalized_naming_truth(
        task_id="87",
        task_hash="hash-87",
        fallback_name="Dune.Part.Two.2024.1080p.WEB-DL.mkv",
    )

    assert result == "Dune.Part.Two.2024.1080p.WEB-DL.mkv"
    output = capsys.readouterr().out
    assert "[导入命名真相记录损坏]" in output
    assert "job_event row identity corrupted after read" in output
    assert "task_id=87" in output
    assert "task_hash=hash-87" in output
    assert "[处理建议]" in output


def test_build_normalized_target_name_uses_parser_for_episode_file(tmp_path: Path) -> None:
    source_path = tmp_path / "Frieren.S01E01.1080p.WEB-DL.mkv"
    source_path.write_bytes(b"demo")

    result = import_prepare_module.build_normalized_target_name(
        source_path=source_path,
        naming_truth="Frieren.S01E01.1080p.WEB-DL.mkv",
    )

    assert result == "Frieren S01E01.mkv"


def test_extract_title_year_for_scrape_uses_parser_for_episode_file(tmp_path: Path) -> None:
    target_path = tmp_path / "Frieren.S01E01.1080p.WEB-DL.mkv"
    target_path.write_bytes(b"demo")

    title, year = import_prepare_module.extract_title_year_for_scrape(target_path)

    assert title == "Frieren"
    assert year == ""


def test_extract_title_year_for_scrape_uses_parser_for_bracket_episode_directory(tmp_path: Path) -> None:
    target_path = tmp_path / "[SweetSub][Frieren][01][WebRip][1080p][CHS]"
    target_path.mkdir(parents=True)

    title, year = import_prepare_module.extract_title_year_for_scrape(target_path)

    assert title == "Frieren"
    assert year == ""


def test_resolve_metadata_title_year_falls_back_to_target_path_name(tmp_path: Path) -> None:
    target_path = tmp_path / "Interstellar.2014.1080p.WEB-DL.mkv"
    target_path.write_bytes(b"demo")
    service = ImportToLibraryService(
        get_import_source_func=AsyncMock(return_value=None),
        library_target_dir="/data/library/movies",
    )

    title, year = service._resolve_metadata_title_year(
        task_id="87",
        task_hash="hash-87",
        target_path=target_path,
    )

    assert title == "Interstellar"
    assert year == "2014"


def test_resolve_metadata_title_year_prefers_downloader_naming_truth(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    event_repo = JobEventRepo(database)
    event_repo.append_event(
        task_ref="1",
        task_id="87",
        task_hash="hash-87",
        event_type="downloader.succeeded",
        message="Mission: Impossible - Fallout 2018 1080p",
    )
    target_path = tmp_path / "raw.mkv"
    target_path.write_bytes(b"demo")
    service = ImportToLibraryService(
        get_import_source_func=AsyncMock(return_value=None),
        library_target_dir="/data/library/movies",
        job_event_repo=event_repo,
    )

    title, year = service._resolve_metadata_title_year(
        task_id="87",
        task_hash="hash-87",
        target_path=target_path,
    )

    assert title == "Mission: Impossible - Fallout"
    assert year == "2018"


def test_resolve_metadata_title_year_prefers_confirmed_media_identity(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    event_repo = JobEventRepo(database)
    event_repo.append_event(
        task_ref="1",
        task_id="87",
        task_hash="hash-87",
        event_type="downloader.succeeded",
        message="Wrong Guess 2018 1080p",
    )
    event_repo.append_event(
        task_ref="1",
        task_id="87",
        task_hash="hash-87",
        event_type=MEDIA_IDENTITY_EVENT_TYPE,
        message=media_identity_to_json(
            {
                "media_type": "movie",
                "tmdb_id": "157336",
                "title": "Interstellar",
                "original_title": "星际穿越",
                "year": "2014",
                "source": "search_confirmed",
            }
        ),
    )
    target_path = tmp_path / "raw.mkv"
    target_path.write_bytes(b"demo")
    service = ImportToLibraryService(
        get_import_source_func=AsyncMock(return_value=None),
        library_target_dir="/data/library/movies",
        job_event_repo=event_repo,
    )

    title, year = service._resolve_metadata_title_year(
        task_id="87",
        task_hash="hash-87",
        target_path=target_path,
    )

    assert title == "Interstellar"
    assert year == "2014"


def test_confirm_import_prefers_confirmed_media_identity_for_movie_target_name(tmp_path: Path) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Akron.2015.1080p.AMZN.WEB-DL.DDP2.0.H.264-NZMA.mkv"
    source_file.write_bytes(b"demo")
    source_subtitle = download_dir / "Akron.2015.1080p.AMZN.WEB-DL.DDP2.0.H.264-NZMA.zh.srt"
    source_subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\nhello\n", encoding="utf-8")
    target_dir = tmp_path / "library"

    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    event_repo = JobEventRepo(database)
    event_repo.append_event(
        task_ref="1",
        task_id="20",
        task_hash="hash-20",
        event_type="downloader.succeeded",
        message="Akron.2015.1080p.AMZN.WEB-DL.DDP2.0.H.264-NZMA",
    )
    event_repo.append_event(
        task_ref="1",
        task_id="20",
        task_hash="hash-20",
        event_type=MEDIA_IDENTITY_EVENT_TYPE,
        message=media_identity_to_json(
            {
                "media_type": "movie",
                "tmdb_id": "361018",
                "title": "爱的进行时",
                "original_title": "Akron",
                "year": "2015",
                "source": "search_confirmed",
            }
        ),
    )

    import_source = TransmissionImportSource(
        task_id="20",
        task_hash="hash-20",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    service = ImportToLibraryService(
        get_import_source_func=AsyncMock(return_value=import_source),
        library_target_dir=str(target_dir),
        job_event_repo=event_repo,
    )

    _run(service.import_by_task_ref("20"))
    text = _run(service.confirm_import_by_task_ref("20"))

    target_directory = target_dir / "爱的进行时 (2015)"
    target_file = target_directory / "爱的进行时 (2015).mkv"
    target_subtitle = target_directory / "爱的进行时 (2015).zh.srt"
    assert target_directory.is_dir()
    assert target_file.exists()
    assert target_subtitle.exists()
    assert str(target_file) in text
    assert source_file.stat().st_ino == target_file.stat().st_ino
    assert source_subtitle.stat().st_ino == target_subtitle.stat().st_ino


def test_confirm_import_renames_directory_with_normalized_movie_name(tmp_path: Path) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_dir = download_dir / "Dune.Part.Two.2024.1080p.WEB-DL"
    source_dir.mkdir(parents=True)
    (source_dir / "movie.mkv").write_bytes(b"demo")
    target_dir = tmp_path / "library"

    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_dir.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    service = ImportToLibraryService(
        get_import_source_func=AsyncMock(return_value=import_source),
        library_target_dir=str(target_dir),
    )

    _run(service.import_by_task_ref("87"))
    text = _run(service.confirm_import_by_task_ref("87"))

    target_path = target_dir / "Dune Part Two (2024)"
    assert target_path.is_dir()
    assert (target_path / "movie.mkv").exists()
    assert str(target_path) in text


def test_confirm_import_triggers_metadata_scrape_success_event(tmp_path: Path) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Interstellar.2014.mkv"
    source_file.write_bytes(b"demo")
    target_dir = tmp_path / "library"

    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    event_repo = JobEventRepo(database)

    seen_inputs: list[MetadataScrapeInput] = []

    async def fake_scrape(scrape_input: MetadataScrapeInput) -> MetadataScrapeResult:
        seen_inputs.append(scrape_input)
        return MetadataScrapeResult(success=True, message="metadata 刮削成功：/tmp/demo.metadata.json")

    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    service = ImportToLibraryService(
        get_import_source_func=AsyncMock(return_value=import_source),
        library_target_dir=str(target_dir),
        scrape_metadata_func=fake_scrape,
        job_event_repo=event_repo,
    )

    _run(service.import_by_task_ref("87"))
    text = _run(service.confirm_import_by_task_ref("87"))
    assert "导入成功" in text
    assert "metadata：成功；metadata 刮削成功：/tmp/demo.metadata.json" in text
    assert len(seen_inputs) == 1
    assert seen_inputs[0].title == "Interstellar"
    assert seen_inputs[0].year == "2014"

    events = event_repo.list_events_for_task_identity(task_id="87", task_hash="hash-87")
    assert any(event.event_type == "metadata.succeeded" for event in events)


def test_confirm_import_metadata_scrape_prefers_downloader_title_truth(tmp_path: Path) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "raw.mkv"
    source_file.write_bytes(b"demo")
    target_dir = tmp_path / "library"

    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    event_repo = JobEventRepo(database)
    event_repo.append_event(
        task_ref="1",
        task_id="87",
        task_hash="hash-87",
        event_type="downloader.succeeded",
        message="Mission: Impossible - Fallout 2018 1080p",
    )

    seen_inputs: list[MetadataScrapeInput] = []

    async def fake_scrape(scrape_input: MetadataScrapeInput) -> MetadataScrapeResult:
        seen_inputs.append(scrape_input)
        return MetadataScrapeResult(success=True, message="metadata 刮削成功：/tmp/demo.metadata.json")

    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    service = ImportToLibraryService(
        get_import_source_func=AsyncMock(return_value=import_source),
        library_target_dir=str(target_dir),
        scrape_metadata_func=fake_scrape,
        job_event_repo=event_repo,
    )

    _run(service.import_by_task_ref("87"))
    text = _run(service.confirm_import_by_task_ref("87"))
    assert "导入成功" in text
    assert "字幕：跳过" in text
    assert len(seen_inputs) == 1
    assert seen_inputs[0].title == "Mission: Impossible - Fallout"
    assert seen_inputs[0].year == "2018"


def test_confirm_import_metadata_scrape_passes_confirmed_tmdb_id(tmp_path: Path) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "raw.mkv"
    source_file.write_bytes(b"demo")
    target_dir = tmp_path / "library"

    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    event_repo = JobEventRepo(database)
    event_repo.append_event(
        task_ref="1",
        task_id="87",
        task_hash="hash-87",
        event_type=MEDIA_IDENTITY_EVENT_TYPE,
        message=media_identity_to_json(
            {
                "media_type": "movie",
                "tmdb_id": "157336",
                "title": "Interstellar",
                "original_title": "星际穿越",
                "year": "2014",
                "source": "search_confirmed",
            }
        ),
    )

    seen_inputs: list[MetadataScrapeInput] = []

    async def fake_scrape(scrape_input: MetadataScrapeInput) -> MetadataScrapeResult:
        seen_inputs.append(scrape_input)
        return MetadataScrapeResult(success=True, message="metadata 刮削成功：/tmp/demo.metadata.json")

    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    service = ImportToLibraryService(
        get_import_source_func=AsyncMock(return_value=import_source),
        library_target_dir=str(target_dir),
        scrape_metadata_func=fake_scrape,
        job_event_repo=event_repo,
    )

    _run(service.import_by_task_ref("87"))
    text = _run(service.confirm_import_by_task_ref("87"))
    assert "导入成功" in text
    assert "字幕：跳过" in text
    assert len(seen_inputs) == 1
    assert seen_inputs[0].tmdb_id == "157336"
    assert seen_inputs[0].title == "Interstellar"
    assert seen_inputs[0].year == "2014"


def test_confirm_import_metadata_scrape_exception_does_not_break_import(tmp_path: Path) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Interstellar.2014.mkv"
    source_file.write_bytes(b"demo")
    target_dir = tmp_path / "library"

    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    event_repo = JobEventRepo(database)

    async def failing_scrape(_: MetadataScrapeInput) -> MetadataScrapeResult:
        raise RuntimeError("fanart timeout")

    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    service = ImportToLibraryService(
        get_import_source_func=AsyncMock(return_value=import_source),
        library_target_dir=str(target_dir),
        scrape_metadata_func=failing_scrape,
        job_event_repo=event_repo,
    )

    _run(service.import_by_task_ref("87"))
    text = _run(service.confirm_import_by_task_ref("87"))
    assert "导入成功" in text

    events = event_repo.list_events_for_task_identity(task_id="87", task_hash="hash-87")
    assert any(event.event_type == "metadata.failed" for event in events)


def test_confirm_import_metadata_scrape_re_raises_non_runtime_error(tmp_path: Path) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Interstellar.2014.mkv"
    source_file.write_bytes(b"demo")
    target_dir = tmp_path / "library"

    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    event_repo = JobEventRepo(database)

    async def failing_scrape(_: MetadataScrapeInput) -> MetadataScrapeResult:
        raise ValueError("bad scrape stub")

    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    service = ImportToLibraryService(
        get_import_source_func=AsyncMock(return_value=import_source),
        library_target_dir=str(target_dir),
        scrape_metadata_func=failing_scrape,
        job_event_repo=event_repo,
    )

    _run(service.import_by_task_ref("87"))
    with pytest.raises(ValueError, match="bad scrape stub"):
        _run(service.confirm_import_by_task_ref("87"))


def test_confirm_import_triggers_subtitle_translate_success_event(tmp_path: Path) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Interstellar.2014.mkv"
    source_file.write_bytes(b"demo")
    target_dir = tmp_path / "library"

    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    event_repo = JobEventRepo(database)

    seen_inputs: list[SubtitleTranslateInput] = []

    def fake_translate(translate_input: SubtitleTranslateInput) -> SubtitleTranslateResult:
        seen_inputs.append(translate_input)
        return SubtitleTranslateResult(success=True, message="字幕翻译成功：已生成 1 个字幕文件。", translated_count=1)

    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    service = ImportToLibraryService(
        get_import_source_func=AsyncMock(return_value=import_source),
        library_target_dir=str(target_dir),
        translate_subtitle_func=fake_translate,
        job_event_repo=event_repo,
    )

    _run(service.import_by_task_ref("87"))
    text = _run(service.confirm_import_by_task_ref("87"))
    assert "导入成功" in text
    assert len(seen_inputs) == 1
    assert seen_inputs[0].task_id == "87"
    assert seen_inputs[0].task_hash == "hash-87"

    events = event_repo.list_events_for_task_identity(task_id="87", task_hash="hash-87")
    assert any(event.event_type == "subtitle.succeeded" for event in events)


def test_confirm_import_reports_chinese_subtitle_skip_as_chinese_ready(tmp_path: Path) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Interstellar.2014.mkv"
    source_file.write_bytes(b"demo")
    target_dir = tmp_path / "library"

    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    event_repo = JobEventRepo(database)

    def fake_translate(_: SubtitleTranslateInput) -> SubtitleTranslateResult:
        return SubtitleTranslateResult(
            success=False,
            skipped=True,
            message="字幕翻译已跳过：已检测到中文字幕外挂字幕。",
            translated_count=0,
        )

    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    service = ImportToLibraryService(
        get_import_source_func=AsyncMock(return_value=import_source),
        library_target_dir=str(target_dir),
        translate_subtitle_func=fake_translate,
        job_event_repo=event_repo,
    )

    _run(service.import_by_task_ref("87"))
    text = _run(service.confirm_import_by_task_ref("87"))

    assert "字幕：✅ 已有中文字幕；字幕翻译已跳过：已检测到中文字幕外挂字幕。" in text
    events = event_repo.list_events_for_task_identity(task_id="87", task_hash="hash-87")
    assert any(event.event_type == "subtitle.skipped" for event in events)


def test_confirm_import_subtitle_translate_exception_does_not_break_import(tmp_path: Path) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Interstellar.2014.mkv"
    source_file.write_bytes(b"demo")
    target_dir = tmp_path / "library"

    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    event_repo = JobEventRepo(database)

    def failing_translate(_: SubtitleTranslateInput) -> SubtitleTranslateResult:
        raise RuntimeError("subtitle service timeout")

    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    service = ImportToLibraryService(
        get_import_source_func=AsyncMock(return_value=import_source),
        library_target_dir=str(target_dir),
        translate_subtitle_func=failing_translate,
        job_event_repo=event_repo,
    )

    _run(service.import_by_task_ref("87"))
    text = _run(service.confirm_import_by_task_ref("87"))
    assert "导入成功" in text

    events = event_repo.list_events_for_task_identity(task_id="87", task_hash="hash-87")
    assert any(event.event_type == "subtitle.failed" for event in events)


def test_confirm_import_subtitle_translate_re_raises_non_runtime_error(tmp_path: Path) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True)
    source_file = download_dir / "Interstellar.2014.mkv"
    source_file.write_bytes(b"demo")
    target_dir = tmp_path / "library"

    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    event_repo = JobEventRepo(database)

    def failing_translate(_: SubtitleTranslateInput) -> SubtitleTranslateResult:
        raise ValueError("bad translate stub")

    import_source = TransmissionImportSource(
        task_id="87",
        task_hash="hash-87",
        name=source_file.name,
        download_dir=str(download_dir),
        is_finished=True,
        percent_done=1.0,
    )
    service = ImportToLibraryService(
        get_import_source_func=AsyncMock(return_value=import_source),
        library_target_dir=str(target_dir),
        translate_subtitle_func=failing_translate,
        job_event_repo=event_repo,
    )

    _run(service.import_by_task_ref("87"))
    with pytest.raises(ValueError, match="bad translate stub"):
        _run(service.confirm_import_by_task_ref("87"))


def _run(coroutine: Awaitable[str]) -> str:
    return asyncio.run(coroutine)

from __future__ import annotations

import asyncio
import errno
import os
from collections.abc import Awaitable
from pathlib import Path
from unittest.mock import AsyncMock

import app.services.import_to_library as import_module
from app.clients.transmission import TransmissionImportSource
from app.db.approval_repo import (
    APPROVAL_STATUS_APPROVED,
    APPROVAL_STATUS_CANCELLED,
    APPROVAL_STATUS_PENDING,
    ApprovalRepo,
)
from app.db.job_event_repo import JobEventRepo
from app.db.job_repo import JOB_STATE_CANCELLED, JobRepo
from app.db.sqlite import SqliteDatabase
from app.services.import_to_library import (
    CONFIRM_QUERY_USAGE_TEXT,
    IMPORT_COPY_APPROVAL_PENDING_TEXT,
    IMPORT_CONFIRM_EXPIRED_TEXT,
    IMPORT_CONFIRM_NOT_PENDING_TEXT,
    IMPORT_NOT_COMPLETED_TEXT,
    IMPORT_NOT_FOUND_TEXT,
    IMPORT_REFRESH_FAILED_TEXT,
    IMPORT_SOURCE_MISSING_TEXT,
    ImportToLibraryService,
    parse_confirm_query,
    parse_import_query,
)
from app.services.metadata_scraper import MetadataScrapeInput, MetadataScrapeResult
from app.services.subtitle_translator import SubtitleTranslateInput, SubtitleTranslateResult


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
    target_file = target_dir / "Dune (2021).mkv"
    assert "导入成功" in text
    assert str(target_file) in text
    assert target_file.exists()
    assert source_file.stat().st_ino == target_file.stat().st_ino


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
    refresh.assert_awaited_once()


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
    monkeypatch.setattr(import_module.os, "link", _raise_exdev)
    text = _run(service.confirm_import_by_task_ref("87"))
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

    monkeypatch.setattr(import_module.os, "link", _raise_exdev)
    first_confirm = _run(service.confirm_import_by_task_ref("87"))
    assert first_confirm == IMPORT_COPY_APPROVAL_PENDING_TEXT.format(task_ref="87")

    failed_record = approval_repo.get_import_approval(task_id="87", task_hash="hash-87")
    assert failed_record is not None
    assert failed_record.status == APPROVAL_STATUS_PENDING
    assert failed_record.lease_version == 1
    assert failed_record.executed_version == 0

    def _unexpected_hardlink(src: str | Path, dst: str | Path) -> None:
        raise AssertionError("copy confirm should not call os.link again")

    monkeypatch.setattr(import_module.os, "link", _unexpected_hardlink)
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
    assert len(seen_inputs) == 1
    assert seen_inputs[0].title == "Mission: Impossible - Fallout"
    assert seen_inputs[0].year == "2018"


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


def _run(coroutine: Awaitable[str]) -> str:
    return asyncio.run(coroutine)

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
    target_file = target_dir / source_file.name
    assert "导入成功" in text
    assert str(target_file) in text
    assert target_file.exists()
    assert source_file.stat().st_ino == target_file.stat().st_ino


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
    target_file = tmp_path / "library" / source_file.name
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


def _run(coroutine: Awaitable[str]) -> str:
    return asyncio.run(coroutine)

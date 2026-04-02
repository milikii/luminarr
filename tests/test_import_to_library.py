from __future__ import annotations

import asyncio
import errno
from collections.abc import Awaitable
from pathlib import Path
from unittest.mock import AsyncMock

import app.services.import_to_library as import_module
from app.clients.transmission import TransmissionImportSource
from app.services.import_to_library import (
    IMPORT_HARDLINK_CROSS_FILESYSTEM_TEXT,
    IMPORT_NOT_COMPLETED_TEXT,
    IMPORT_NOT_FOUND_TEXT,
    IMPORT_SOURCE_MISSING_TEXT,
    ImportToLibraryService,
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


def test_import_by_task_ref_success_for_file(tmp_path: Path) -> None:
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
    target_file = target_dir / source_file.name
    assert "导入成功" in text
    assert str(target_file) in text
    assert target_file.exists()
    assert source_file.stat().st_ino == target_file.stat().st_ino


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


def test_import_by_task_ref_cross_filesystem_error(tmp_path: Path, monkeypatch) -> None:
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

    monkeypatch.setattr(import_module.os, "link", _raise_exdev)
    text = _run(service.import_by_task_ref("87"))
    assert text == IMPORT_HARDLINK_CROSS_FILESYSTEM_TEXT


def _run(coroutine: Awaitable[str]) -> str:
    return asyncio.run(coroutine)

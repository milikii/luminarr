from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

import httpx

from app.clients.javlibrary_helper import JavLibraryReadOnlyMatch
from app.db.adult_content_registry_repo import AdultContentRegistryPersistenceError, AdultContentRegistryRepo
from app.db.sqlite import SqliteDatabase
from app.services.bt_read_only_display import BtReadOnlyDisplayService


def test_prepare_raw_candidates_adds_adult_metadata_and_history(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "adult.sqlite3"))
    database.initialize()
    registry_repo = AdultContentRegistryRepo(database)
    registry_repo.upsert_pending(
        normalized_content_id="censored:ssis-123",
        content_id_kind="censored",
        archive_category="censored",
        display_title="SSIS-123",
        latest_source_site="tokyotosho",
        task_ref="1",
        task_id="selection:1",
        task_hash="candidate:hash",
        downloader_name="bt",
    )

    service = BtReadOnlyDisplayService(adult_content_registry_repo=registry_repo)
    results = service.prepare_raw_candidates(
        [
            {
                "title": "SSIS-123 sample release",
                "sourceProvider": "tokyotosho",
                "indexerName": "tokyotosho",
            }
        ],
        query="SSIS-123",
    )

    assert results[0]["adult_content_id"] == "censored:ssis-123"
    assert results[0]["adult_display_id"] == "SSIS-123"
    assert "历史: 该番号已有待确认下载记录。" in results[0]["adult_history_text"]


def test_build_display_candidates_attaches_helper_fields_and_history(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "adult-helper.sqlite3"))
    database.initialize()
    registry_repo = AdultContentRegistryRepo(database)
    registry_repo.upsert_pending(
        normalized_content_id="censored:ssis-123",
        content_id_kind="censored",
        archive_category="censored",
        display_title="SSIS-123",
        latest_source_site="tokyotosho",
        task_ref="1",
        task_id="selection:1",
        task_hash="candidate:hash",
        downloader_name="bt",
    )

    async def fake_lookup(_: str) -> JavLibraryReadOnlyMatch | None:
        return JavLibraryReadOnlyMatch(
            normalized_content_id="censored:ssis-123",
            display_id="SSIS-123",
            archive_category="censored",
            title="SSIS-123 Secret Mission Nurse",
            detail_url="https://www.javlibrary.com/tw/?v=javli0001",
        )

    service = BtReadOnlyDisplayService(
        adult_content_registry_repo=registry_repo,
        adult_read_only_lookup_func=fake_lookup,
    )
    results = asyncio.run(
            service.build_display_candidates(
                [
                    {
                        "title": "Secret Mission Nurse leaked cut",
                        "indexerName": "tokyotosho",
                        "sourceProvider": "tokyotosho",
                    }
                ],
            lookup_query="SSIS-123",
            limit=5,
        )
    )

    assert results[0]["read_only_adult_display_id"] == "SSIS-123"
    assert results[0]["read_only_adult_detail_url"] == "https://www.javlibrary.com/tw/?v=javli0001"
    assert "历史: 该番号已有待确认下载记录。" in results[0]["adult_history_text"]


def test_lookup_helper_match_logs_http_failure(capsys) -> None:
    async def failing_lookup(_: str) -> JavLibraryReadOnlyMatch | None:
        raise httpx.ConnectError("timeout", request=httpx.Request("GET", "https://example.com"))

    service = BtReadOnlyDisplayService(adult_read_only_lookup_func=failing_lookup)

    result = asyncio.run(service.lookup_helper_match("SSIS-123"))

    assert result is None
    output = capsys.readouterr().out
    assert "[JavLibrary 只读补全失败]" in output
    assert "timeout" in output


def test_prepare_raw_candidates_logs_adult_history_persistence_failure(capsys) -> None:
    class FailingRegistryRepo:
        def get_by_content_id(self, *, normalized_content_id: str):
            raise AdultContentRegistryPersistenceError("registry down")

    service = BtReadOnlyDisplayService(adult_content_registry_repo=FailingRegistryRepo())  # type: ignore[arg-type]
    results = service.prepare_raw_candidates(
        [
            {
                "title": "SSIS-123 sample release",
                "sourceProvider": "tokyotosho",
                "indexerName": "tokyotosho",
            }
        ],
        query="SSIS-123",
    )

    assert results[0]["adult_content_id"] == "censored:ssis-123"
    assert "adult_history_text" not in results[0]
    output = capsys.readouterr().out
    assert "[成人资源历史查询失败]" in output
    assert "registry down" in output


def test_prepare_raw_candidates_logs_adult_history_sqlite_failure(capsys) -> None:
    class FailingRegistryRepo:
        def get_by_content_id(self, *, normalized_content_id: str):
            raise sqlite3.OperationalError("database locked")

    service = BtReadOnlyDisplayService(adult_content_registry_repo=FailingRegistryRepo())  # type: ignore[arg-type]
    results = service.prepare_raw_candidates(
        [
            {
                "title": "SSIS-123 sample release",
                "sourceProvider": "tokyotosho",
                "indexerName": "tokyotosho",
            }
        ],
        query="SSIS-123",
    )

    assert results[0]["adult_content_id"] == "censored:ssis-123"
    assert "adult_history_text" not in results[0]
    output = capsys.readouterr().out
    assert "[成人资源历史查询失败]" in output
    assert "database locked" in output

from __future__ import annotations

from pathlib import Path

from app.db.adult_content_registry_repo import AdultContentRegistryRepo
from app.db.adult_duplicate_memory_snapshot_repo import AdultDuplicateMemorySnapshotRepo
from app.db.sqlite import SqliteDatabase
from app.maintenance.adult_duplicate_memory_tools import main


def _seed_duplicate_snapshot(database: SqliteDatabase, *, normalized_content_id: str) -> None:
    repo = AdultDuplicateMemorySnapshotRepo(database)
    repo.upsert_snapshot(
        normalized_content_id=normalized_content_id,
        display_title="SSIS-123",
        snapshot_status="fresh",
        evidence_summary_json=(
            '{"evidence":[{"kind":"local_path","summary":"local_path:/archive/SSIS-123.mp4","raw_value":"/archive/SSIS-123.mp4"}],'
            '"registry_status":"archived_present","warning_text":"检测到该番号已有本地或历史命中；如需继续，请显式确认继续下载。"}'
        ),
        last_verified_at="CURRENT",
        last_scan_failed_at="",
    )


def test_adult_duplicate_memory_tools_inspect_prints_local_registry_and_event_hits(
    tmp_path: Path,
    capsys,
) -> None:
    db_path = tmp_path / "adult-duplicate.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()
    _seed_duplicate_snapshot(database, normalized_content_id="censored:ssis-123")

    exit_code = main(["inspect", "--db", str(db_path), "--content-id", "censored:ssis-123"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "censored:ssis-123" in output
    assert "local_path" in output
    assert "archived_present" in output


def test_adult_duplicate_memory_tools_backfill_rebuilds_snapshot(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "adult-duplicate.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()
    adult_dir = tmp_path / "adult"
    adult_dir.mkdir()
    (adult_dir / "SSIS-123 archived.mp4").write_text("video", encoding="utf-8")

    registry_repo = AdultContentRegistryRepo(database)
    registry_repo.upsert_pending(
        normalized_content_id="censored:ssis-123",
        content_id_kind="censored",
        archive_category="censored",
        display_title="SSIS-123",
        latest_source_site="tokyotosho",
        task_ref="bt-1",
        task_id="123",
        task_hash="hash-123",
        downloader_name="bt",
    )
    registry_repo.mark_archived_present(
        normalized_content_id="censored:ssis-123",
        archive_path="/archive/adult/SSIS-123.mp4",
        task_id="123",
        task_hash="hash-123",
    )

    exit_code = main(["backfill", "--db", str(db_path), "--scan-dir", str(adult_dir)])

    assert exit_code == 0
    assert "backfilled=1" in capsys.readouterr().out

    snapshot_repo = AdultDuplicateMemorySnapshotRepo(SqliteDatabase(str(db_path)))
    row = snapshot_repo.get_snapshot("censored:ssis-123")
    assert row is not None
    assert row.snapshot_status == "fresh"
    assert "local_path" in row.evidence_summary_json
    assert "archived_present" in row.evidence_summary_json

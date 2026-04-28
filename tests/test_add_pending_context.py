from __future__ import annotations

from pathlib import Path

from app.db.adult_content_registry_repo import AdultContentRegistryRepo
from app.db.sqlite import SqliteDatabase
from app.services.add_pending_context import AddPendingContextBuilder
from app.services.search_media import SearchMediaService


async def _fake_search(_: str) -> list[dict[str, object]]:
    return []


def test_build_from_source_keeps_exact_adult_id_after_noise_normalization() -> None:
    builder = AddPendingContextBuilder(SearchMediaService(_fake_search))

    result = builder.build_from_source(
        source="magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12",
        title="【中文字幕】 一本道 042123_001 1080p 无码流出",
    )

    assert result.error_text == ""
    assert result.pending_add is not None
    assert result.pending_add.adult_content_id == "1pon:042123-001"
    assert result.pending_add.adult_archive_category == "uncensored"
    assert result.pending_add.adult_display_id == "1PON-042123-001"


def test_build_from_source_does_not_promote_keyword_only_fallback_guess_into_pending_truth() -> None:
    builder = AddPendingContextBuilder(SearchMediaService(_fake_search))

    result = builder.build_from_source(
        source="magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12",
        title="麻豆 中文字幕 无码流出 合集",
    )

    assert result.error_text == ""
    assert result.pending_add is not None
    assert result.pending_add.adult_content_id == ""
    assert result.pending_add.adult_archive_category == ""
    assert result.pending_add.adult_display_id == ""


def test_build_from_source_loads_adult_history_from_registry(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "adult-history.sqlite3"))
    database.initialize()
    registry_repo = AdultContentRegistryRepo(database)
    registry_repo.upsert_pending(
        normalized_content_id="censored:ssis-123",
        content_id_kind="censored",
        archive_category="censored",
        display_title="SSIS-123",
        latest_source_site="tokyotosho",
        task_ref="old-1",
        task_id="task-1",
        task_hash="hash-1",
        downloader_name="bt",
    )
    registry_repo.mark_archived_present(
        normalized_content_id="censored:ssis-123",
        archive_path="/archive/adult/SSIS-123",
        task_id="task-1",
        task_hash="hash-1",
    )

    builder = AddPendingContextBuilder(
        SearchMediaService(_fake_search),
        adult_content_registry_repo=registry_repo,
    )

    result = builder.build_from_source(
        source="magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12",
        title="SSIS-123",
    )

    assert result.pending_add is not None
    assert result.pending_add.adult_history_text.startswith("历史: 该番号已归档保留：")

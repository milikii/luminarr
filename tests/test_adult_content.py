from __future__ import annotations

from pathlib import Path

from app.db.adult_content_registry_repo import (
    ADULT_CONTENT_STATUS_ARCHIVED_PRESENT,
    ADULT_CONTENT_STATUS_ARCHIVED_DELETED,
    ADULT_CONTENT_STATUS_DOWNLOADING,
    ADULT_CONTENT_STATUS_PENDING,
    AdultContentRegistryRepo,
)
from app.db.sqlite import SqliteDatabase
from app.services.adult_bt_selector import build_adult_history_text, order_adult_bt_candidates
from app.services.adult_content import (
    build_fallback_content_id,
    extract_adult_content_match,
    extract_exact_adult_content_match,
    guess_adult_archive_category,
    is_fallback_adult_content_match,
)


def test_extract_adult_content_match_supports_fc2_censored_and_uncensored_patterns() -> None:
    fc2_match = extract_adult_content_match("FC2-PPV-4321981 awesome title")
    assert fc2_match is not None
    assert fc2_match.normalized_content_id == "fc2:4321981"
    assert fc2_match.archive_category == "fc2"
    assert fc2_match.display_id == "FC2-4321981"

    censored_match = extract_adult_content_match("[JAV] SSIS-123 sample release")
    assert censored_match is not None
    assert censored_match.normalized_content_id == "censored:ssis-123"
    assert censored_match.archive_category == "censored"
    assert censored_match.display_id == "SSIS-123"

    uncensored_match = extract_adult_content_match("Carib-042123-001 title text")
    assert uncensored_match is not None
    assert uncensored_match.normalized_content_id == "carib:042123-001"
    assert uncensored_match.archive_category == "uncensored"


def test_extract_adult_content_match_normalizes_full_width_and_variant_separators() -> None:
    censored_match = extract_adult_content_match("【ＪＡＶ】 ＳＳＩＳ－１２３ sample release")
    assert censored_match is not None
    assert censored_match.normalized_content_id == "censored:ssis-123"
    assert censored_match.display_id == "SSIS-123"

    fc2_match = extract_adult_content_match("ＦＣ２—ＰＰＶ—４３２１９８１")
    assert fc2_match is not None
    assert fc2_match.normalized_content_id == "fc2:4321981"
    assert fc2_match.display_id == "FC2-4321981"

    uncensored_match = extract_adult_content_match("Ｃａｒｉｂ－０４２１２３＿００１")
    assert uncensored_match is not None
    assert uncensored_match.normalized_content_id == "carib:042123-001"
    assert uncensored_match.display_id == "CARIB-042123-001"


def test_extract_adult_content_match_canonicalizes_uncensored_prefix_aliases() -> None:
    alias_samples = (
        ("Caribbeancom-042123-001", "carib:042123-001", "CARIB-042123-001"),
        ("1Pondo-042123-001", "1pon:042123-001", "1PON-042123-001"),
        ("10Musume-042123-001", "10mu:042123-001", "10MU-042123-001"),
        ("PacoPacomama-042123-001", "paco:042123-001", "PACO-042123-001"),
    )

    for text, expected_id, expected_display in alias_samples:
        match = extract_adult_content_match(text)
        assert match is not None
        assert match.normalized_content_id == expected_id
        assert match.display_id == expected_display


def test_extract_exact_adult_content_match_strips_noise_and_normalizes_localized_aliases() -> None:
    uncensored_match = extract_exact_adult_content_match("【中文字幕】 一本道 042123_001 1080p 无码流出")
    assert uncensored_match is not None
    assert uncensored_match.normalized_content_id == "1pon:042123-001"
    assert uncensored_match.display_id == "1PON-042123-001"

    tokyohot_match = extract_exact_adult_content_match("東京熱 n1234 HDR 4K sample")
    assert tokyohot_match is not None
    assert tokyohot_match.normalized_content_id == "tokyohot:n1234"
    assert tokyohot_match.display_id == "TOKYOHOT-N1234"


def test_extract_exact_adult_content_match_rejects_keyword_only_fallback_guess() -> None:
    exact_match = extract_exact_adult_content_match("麻豆 中文字幕 无码流出 合集")
    assert exact_match is None

    fallback_match = extract_adult_content_match("麻豆 中文字幕 无码流出 合集")
    assert fallback_match is not None
    assert fallback_match.archive_category == "chinese_original"
    assert is_fallback_adult_content_match(fallback_match) is True


def test_guess_adult_archive_category_prefers_chinese_original_and_western_keywords() -> None:
    assert guess_adult_archive_category("麻豆 国产原创") == "chinese_original"
    assert guess_adult_archive_category("Brazzers western title") == "western"
    assert guess_adult_archive_category("unknown title", source_site="javbus") == "censored"
    assert guess_adult_archive_category("unknown title") == "other_adult"


def test_build_fallback_content_id_is_stable() -> None:
    assert build_fallback_content_id("Some Random Adult Title", category="other_adult") == "other_adult:somerandomadulttitle"


def test_order_adult_bt_candidates_prefers_exact_id_match_then_site_priority() -> None:
    ordered = order_adult_bt_candidates(
        [
            {
                "title": "ABP-123 low seed",
                "adult_content_id": "censored:abp-123",
                "sourceProvider": "prowlarr",
                "seeders": 50,
            },
            {
                "title": "ABP-123 tokyotosho",
                "adult_content_id": "censored:abp-123",
                "sourceProvider": "tokyotosho",
                "seeders": 10,
            },
            {
                "title": "ABP-999 higher seed",
                "adult_content_id": "censored:abp-999",
                "sourceProvider": "sukebei",
                "seeders": 999,
            },
        ],
        query="ABP-123",
    )

    assert ordered[0]["title"] == "ABP-123 tokyotosho"
    assert ordered[1]["title"] == "ABP-123 low seed"


def test_order_adult_bt_candidates_applies_source_priority_aliases() -> None:
    ordered = order_adult_bt_candidates(
        [
            {
                "title": "ABP-123 prowlarr high seed",
                "adult_content_id": "censored:abp-123",
                "sourceProvider": "prowlarr",
                "seeders": 999,
            },
            {
                "title": "ABP-123 offkab lower seed",
                "adult_content_id": "censored:abp-123",
                "sourceProvider": "offkab",
                "seeders": 10,
            },
        ],
        query="ABP-123",
    )

    assert ordered[0]["title"] == "ABP-123 offkab lower seed"


def test_build_adult_history_text_formats_known_states() -> None:
    assert build_adult_history_text(status=ADULT_CONTENT_STATUS_PENDING, archive_path="") == "历史: 该番号已有待确认下载记录。"
    assert build_adult_history_text(status=ADULT_CONTENT_STATUS_DOWNLOADING, archive_path="") == "历史: 该番号已有下载任务在运行。"
    assert (
        build_adult_history_text(
            status=ADULT_CONTENT_STATUS_ARCHIVED_PRESENT,
            archive_path="/data/adult/fc2/FC2-1234",
        )
        == "历史: 该番号已归档保留：/data/adult/fc2/FC2-1234"
    )
    assert (
        build_adult_history_text(
            status=ADULT_CONTENT_STATUS_ARCHIVED_DELETED,
            archive_path="/data/adult/fc2/FC2-1234",
        )
        == "历史: 该番号曾归档，当前源资源已清理：/data/adult/fc2/FC2-1234"
    )


def test_adult_content_registry_repo_persists_status_transitions(tmp_path: Path) -> None:
    database = SqliteDatabase(str(tmp_path / "adult.sqlite3"))
    database.initialize()
    repo = AdultContentRegistryRepo(database)

    repo.upsert_pending(
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
    pending = repo.get_by_content_id(normalized_content_id="censored:ssis-123")
    assert pending is not None
    assert pending.current_status == ADULT_CONTENT_STATUS_PENDING

    repo.mark_downloading(
        normalized_content_id="censored:ssis-123",
        content_id_kind="censored",
        archive_category="censored",
        display_title="SSIS-123",
        latest_source_site="tokyotosho",
        task_ref="1",
        task_id="123",
        task_hash="hash-123",
        downloader_name="bt",
    )
    downloading = repo.get_by_task_identity(task_id="123", task_hash="hash-123")
    assert downloading is not None
    assert downloading.current_status == ADULT_CONTENT_STATUS_DOWNLOADING

    repo.mark_archived_present(
        normalized_content_id="censored:ssis-123",
        archive_path="/data/adult/censored/SSIS-123",
        task_id="123",
        task_hash="hash-123",
    )
    archived = repo.get_by_content_id(normalized_content_id="censored:ssis-123")
    assert archived is not None
    assert archived.current_status == ADULT_CONTENT_STATUS_ARCHIVED_PRESENT
    assert archived.archive_present is True

    repo.mark_archived_deleted(
        normalized_content_id="censored:ssis-123",
        archive_path="/data/adult/censored/SSIS-123",
        task_id="123",
        task_hash="hash-123",
    )
    deleted = repo.get_by_content_id(normalized_content_id="censored:ssis-123")
    assert deleted is not None
    assert deleted.current_status == ADULT_CONTENT_STATUS_ARCHIVED_DELETED
    assert deleted.archive_present is False

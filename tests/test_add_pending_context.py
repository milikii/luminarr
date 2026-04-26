from __future__ import annotations

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

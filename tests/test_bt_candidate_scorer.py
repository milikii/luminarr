from __future__ import annotations

from app.services.bt_candidate_scorer import BTCandidate, BTScoringContext, filter_candidates, pick_best


def test_filter_candidates_drops_invalid_source() -> None:
    scored = filter_candidates((_make_candidate(magnet_or_torrent_url="ftp://example.com/bad.torrent"),), _movie_context())

    assert scored[0].drop_reason == "invalid_source"
    assert scored[0].score == 0.0


def test_filter_candidates_drops_query_mismatch() -> None:
    scored = filter_candidates((_make_candidate(title="Interstellar 2014 1080p"),), _movie_context(query="Dune 2021"))

    assert scored[0].drop_reason == "title_mismatch"


def test_filter_candidates_allows_chinese_title_with_year_token_match() -> None:
    scored = filter_candidates((_make_candidate(title="葬送的芙莉莲 2023 1080p"),), _anime_context(query="葬送的芙莉莲 2023"))

    assert scored[0].drop_reason is None


def test_filter_candidates_drops_seen_info_hash() -> None:
    source = "magnet:?xt=urn:btih:ABCDEF1234567890ABCDEF1234567890ABCDEF12&dn=frieren"
    scored = filter_candidates(
        (_make_candidate(title="Frieren S01E01 1080p", magnet_or_torrent_url=source, media_kind="anime"),),
        BTScoringContext(query="Frieren", media_kind="anime", seen_info_hashes=("abcdef1234567890abcdef1234567890abcdef12",)),
    )

    assert scored[0].drop_reason == "duplicate_info_hash"


def test_filter_candidates_deduplicates_repeated_info_hash_inside_batch() -> None:
    source = "magnet:?xt=urn:btih:ABCDEF1234567890ABCDEF1234567890ABCDEF12&dn=frieren"
    scored = filter_candidates(
        (
            _make_candidate(title="Frieren S01E01 1080p", magnet_or_torrent_url=source),
            _make_candidate(title="Frieren S01E01 720p", magnet_or_torrent_url=source),
        ),
        _anime_context(query="Frieren"),
    )

    assert scored[0].drop_reason is None
    assert scored[1].drop_reason == "duplicate_info_hash"


def test_filter_candidates_drops_low_quality_title() -> None:
    scored = filter_candidates((_make_candidate(title="Dune 2021 CAM"),), _movie_context())

    assert scored[0].drop_reason == "low_quality_title"


def test_filter_candidates_drops_multi_item_release_in_single_item_mode() -> None:
    scored = filter_candidates(
        (_make_candidate(title="Frieren S01 Complete 1080p"),),
        BTScoringContext(query="Frieren", media_kind="raw_bt", single_item_mode=True),
    )

    assert scored[0].drop_reason == "multi_item_release"


def test_pick_best_prefers_higher_weighted_candidate() -> None:
    best = pick_best(
        (
            _make_candidate(title="Dune 2021 720p WEBRip x264", resolution="720p", source_type="WEBRip", codec="x264", seeders=20),
            _make_candidate(
                title="Dune 2021 1080p WEB-DL x265",
                resolution="1080p",
                source_type="WEB-DL",
                codec="x265",
                seeders=20,
                size_bytes=8 * 1024**3,
                release_group="CHD",
            ),
        ),
        _movie_context(),
    )

    assert best is not None
    assert best.candidate.title == "Dune 2021 1080p WEB-DL x265"


def test_filter_candidates_exposes_expected_score_breakdown() -> None:
    scored = filter_candidates(
        (
            _make_candidate(
                title="Dune 2021 1080p WEB-DL x265",
                resolution="1080p",
                source_type="WEB-DL",
                codec="x265",
                seeders=55,
                size_bytes=8 * 1024**3,
                release_group="CHD",
            ),
        ),
        _movie_context(),
    )

    first = scored[0]
    assert first.drop_reason is None
    assert first.score_breakdown == {
        "resolution": 0.8,
        "source_type": 0.7,
        "seeders": 1.0,
        "size_fit": 1.0,
        "codec": 0.9,
        "release_group": 1.0,
    }
    assert first.score == 9.05


def test_filter_candidates_prefers_movie_size_range() -> None:
    scored = filter_candidates(
        (
            _make_candidate(title="Dune 2021 1080p", size_bytes=8 * 1024**3),
            _make_candidate(title="Dune 2021 1080p small", size_bytes=1 * 1024**3),
        ),
        _movie_context(),
    )

    assert scored[0].candidate.size_bytes == 8 * 1024**3
    assert scored[0].score_breakdown["size_fit"] == 1.0
    assert scored[1].score_breakdown["size_fit"] == 0.2


def test_filter_candidates_prefers_episode_size_range_for_anime() -> None:
    scored = filter_candidates(
        (
            _make_candidate(title="Frieren S01E01 1080p", media_kind="anime", size_bytes=2 * 1024**3),
            _make_candidate(title="Frieren S01E01 1080p oversized", media_kind="anime", size_bytes=8 * 1024**3),
        ),
        _anime_context(query="Frieren"),
    )

    assert scored[0].candidate.size_bytes == 2 * 1024**3
    assert scored[0].score_breakdown["size_fit"] == 1.0
    assert scored[1].score_breakdown["size_fit"] == 0.625


def test_filter_candidates_uses_seeder_thresholds() -> None:
    scored = filter_candidates(
        (
            _make_candidate(title="Dune 2021 1080p many", seeders=70),
            _make_candidate(title="Dune 2021 1080p medium", seeders=25),
            _make_candidate(title="Dune 2021 1080p few", seeders=6),
            _make_candidate(title="Dune 2021 1080p rare", seeders=1),
            _make_candidate(title="Dune 2021 1080p none", seeders=0),
        ),
        _movie_context(),
    )

    assert [item.score_breakdown["seeders"] for item in scored] == [1.0, 0.8, 0.5, 0.2, 0.0]


def test_filter_candidates_applies_release_group_bonus() -> None:
    scored = filter_candidates(
        (
            _make_candidate(title="Dune 2021 1080p CHD", release_group="CHD"),
            _make_candidate(title="Dune 2021 1080p Other", release_group="OtherGroup"),
            _make_candidate(title="Dune 2021 1080p Missing", release_group=None),
        ),
        _movie_context(),
    )

    assert [item.score_breakdown["release_group"] for item in scored] == [1.0, 0.2, 0.0]


def test_filter_candidates_keeps_dropped_candidates_after_valid_results() -> None:
    scored = filter_candidates(
        (
            _make_candidate(title="Dune 2021 1080p"),
            _make_candidate(title="Dune 2021 CAM"),
        ),
        _movie_context(),
    )

    assert scored[0].drop_reason is None
    assert scored[1].drop_reason == "low_quality_title"


def test_pick_best_returns_none_when_all_candidates_are_dropped() -> None:
    best = pick_best((_make_candidate(title="Dune 2021 CAM"),), _movie_context())

    assert best is None


def _make_candidate(
    *,
    title: str = "Dune 2021 1080p",
    magnet_or_torrent_url: str = "https://example.com/dune.torrent",
    size_bytes: int | None = 8 * 1024**3,
    seeders: int | None = 20,
    leechers: int | None = None,
    resolution: str | None = "1080p",
    codec: str | None = "x264",
    source_type: str | None = "WEB-DL",
    audio: tuple[str, ...] = (),
    release_group: str | None = None,
    age_days: int | None = None,
    media_kind: str = "movie",
) -> BTCandidate:
    return BTCandidate(
        source_site="nyaa",
        title=title,
        magnet_or_torrent_url=magnet_or_torrent_url,
        size_bytes=size_bytes,
        seeders=seeders,
        leechers=leechers,
        resolution=resolution,
        codec=codec,
        source_type=source_type,
        audio=audio,
        release_group=release_group,
        age_days=age_days,
        media_kind=media_kind,
    )


def _movie_context(*, query: str = "Dune 2021") -> BTScoringContext:
    return BTScoringContext(query=query, media_kind="movie")


def _anime_context(*, query: str = "Frieren") -> BTScoringContext:
    return BTScoringContext(query=query, media_kind="anime")

from __future__ import annotations

from pathlib import Path

from app.services.bt_candidate_scorer import BTCandidate, BTScoringContext, BTScoringRules, filter_candidates, pick_best
from app.services.bt_candidate_scorer import DEFAULT_BT_SCORING_RULES, load_bt_scoring_rules


def test_filter_candidates_drops_invalid_source() -> None:
    scored = filter_candidates((_make_candidate(magnet_or_torrent_url="ftp://example.com/bad.torrent"),), _movie_context())

    assert scored[0].drop_reason == "invalid_source"
    assert scored[0].score == 0.0


def test_filter_candidates_drops_query_mismatch() -> None:
    scored = filter_candidates((_make_candidate(title="Interstellar 2014 1080p"),), _movie_context(query="Dune 2021"))

    assert scored[0].drop_reason == "title_mismatch"


def test_filter_candidates_drops_series_episode_release_for_movie_query() -> None:
    scored = filter_candidates(
        (_make_candidate(title="Zhou Chu Chu San Hai Zhi Su Ming 2024 S01 1080p WEB-DL"),),
        _movie_context(query="周处除三害 2024"),
    )

    assert scored[0].drop_reason == "title_mismatch"


def test_filter_candidates_drops_movie_extra_release_for_movie_query() -> None:
    scored = filter_candidates(
        (_make_candidate(title="Dune: Part Two 2024 Extras 1080p BluRay Remux AVC DD2.0-OPTIMUM"),),
        _movie_context(query="Dune Part 2 2024"),
    )

    assert scored[0].drop_reason == "title_mismatch"


def test_filter_candidates_keeps_sequel_alias_match_for_movie_query() -> None:
    scored = filter_candidates(
        (_make_candidate(title="Dune: Part Two 2024 1080p WEB-DL"),),
        _movie_context(query="Dune Part 2 2024"),
    )

    assert scored[0].drop_reason is None
    assert scored[0].score_breakdown["title_relevance"] == 0.9


def test_filter_candidates_prefers_sequel_alias_candidate_over_neighbor_title() -> None:
    scored = filter_candidates(
        (
            _make_candidate(title="Dune: Part One 2024 2160p BluRay", resolution="2160p", source_type="BluRay"),
            _make_candidate(title="Dune: Part Two 2024 1080p WEB-DL", resolution="1080p", source_type="WEB-DL"),
        ),
        _movie_context(query="Dune Part 2 2024"),
    )

    assert scored[0].candidate.title == "Dune: Part Two 2024 1080p WEB-DL"
    assert scored[0].score_breakdown["title_relevance"] == 0.9
    assert scored[1].drop_reason == "title_mismatch"


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
        "title_relevance": 1.0,
        "source_site": 0.2,
        "resolution": 0.8,
        "source_type": 0.7,
        "seeders": 1.0,
        "size_fit": 1.0,
        "codec": 0.9,
        "release_group": 1.0,
    }
    assert first.score == 16.025


def test_filter_candidates_prefers_exact_movie_title_over_neighbor_title() -> None:
    scored = filter_candidates(
        (
            _make_candidate(title="Dune: Part One 2021 2160p BluRay", resolution="2160p", source_type="BluRay", size_bytes=90 * 1024**3),
            _make_candidate(title="Dune 2021 1080p WEB-DL", resolution="1080p", source_type="WEB-DL", size_bytes=10 * 1024**3),
        ),
        _movie_context(query="Dune 2021"),
    )

    assert scored[0].candidate.title == "Dune 2021 1080p WEB-DL"
    assert scored[0].score_breakdown["title_relevance"] > scored[1].score_breakdown["title_relevance"]


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


def test_filter_candidates_prefers_better_source_type_over_more_seeders() -> None:
    scored = filter_candidates(
        (
            _make_candidate(
                title="Dune 2021 1080p BluRay",
                source_type="BluRay",
                resolution="1080p",
                seeders=8,
            ),
            _make_candidate(
                title="Dune 2021 1080p WEBRip",
                source_type="WEBRip",
                resolution="1080p",
                seeders=70,
            ),
        ),
        _movie_context(),
    )

    assert scored[0].candidate.title == "Dune 2021 1080p BluRay"
    assert scored[0].score_breakdown["source_type"] > scored[1].score_breakdown["source_type"]
    assert scored[0].score > scored[1].score


def test_filter_candidates_applies_source_site_preference() -> None:
    scored = filter_candidates(
        (
            _make_candidate(title="Dune 2021 1080p WEB-DL", source_type="WEB-DL", source_site="PTP"),
            _make_candidate(title="Dune 2021 1080p WEB-DL", source_type="WEB-DL", source_site="OtherSite"),
        ),
        _movie_context(),
    )

    assert scored[0].candidate.source_site == "PTP"
    assert scored[0].score_breakdown["source_site"] == 1.0
    assert scored[1].score_breakdown["source_site"] == 0.2


def test_filter_candidates_applies_source_site_preference_for_alias_name() -> None:
    scored = filter_candidates(
        (
            _make_candidate(title="Dune 2021 1080p WEB-DL", source_type="WEB-DL", source_site="BeyondHD"),
            _make_candidate(title="Dune 2021 1080p WEB-DL", source_type="WEB-DL", source_site="OtherSite"),
        ),
        _movie_context(),
        rules=BTScoringRules(
            weights=dict(DEFAULT_BT_SCORING_RULES.weights),
            resolution_scores=dict(DEFAULT_BT_SCORING_RULES.resolution_scores),
            source_type_scores=dict(DEFAULT_BT_SCORING_RULES.source_type_scores),
            codec_scores=dict(DEFAULT_BT_SCORING_RULES.codec_scores),
            source_site_preferred=("BHD",),
            release_group_preferred=DEFAULT_BT_SCORING_RULES.release_group_preferred,
        ),
    )

    assert scored[0].candidate.source_site == "BeyondHD"
    assert scored[0].score_breakdown["source_site"] == 1.0
    assert scored[1].score_breakdown["source_site"] == 0.2


def test_filter_candidates_uses_seeders_as_tiebreak_inside_same_quality_bucket() -> None:
    scored = filter_candidates(
        (
            _make_candidate(
                title="Dune 2021 1080p WEB-DL x265 low-seeders",
                source_type="WEB-DL",
                resolution="1080p",
                codec="x265",
                seeders=6,
            ),
            _make_candidate(
                title="Dune 2021 1080p WEB-DL x265 high-seeders",
                source_type="WEB-DL",
                resolution="1080p",
                codec="x265",
                seeders=80,
            ),
        ),
        _movie_context(),
    )

    assert scored[0].candidate.title == "Dune 2021 1080p WEB-DL x265 high-seeders"
    assert scored[0].score_breakdown["seeders"] > scored[1].score_breakdown["seeders"]


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


def test_load_bt_scoring_rules_reads_repo_defaults() -> None:
    rules = load_bt_scoring_rules()

    assert rules == DEFAULT_BT_SCORING_RULES


def test_load_bt_scoring_rules_warns_and_falls_back_when_file_missing(tmp_path: Path, capsys) -> None:
    rules = load_bt_scoring_rules(tmp_path / "missing.yml")

    assert rules == DEFAULT_BT_SCORING_RULES
    captured = capsys.readouterr()
    assert "[BT 评分规则文件回退]" in captured.out
    assert "[处理建议]" in captured.out
    assert "规则文件缺失" in captured.out


def test_load_bt_scoring_rules_warns_and_keeps_defaults_for_invalid_field(tmp_path: Path, capsys) -> None:
    path = tmp_path / "broken.yml"
    path.write_text(
        "weights:\n"
        "  seeders: fast\n"
        "release_group_preferred:\n"
        "  - CHD\n",
        encoding="utf-8",
    )

    rules = load_bt_scoring_rules(path)

    assert rules.weights["seeders"] == DEFAULT_BT_SCORING_RULES.weights["seeders"]
    assert rules.source_site_preferred == DEFAULT_BT_SCORING_RULES.source_site_preferred
    assert rules.release_group_preferred == ("CHD",)
    captured = capsys.readouterr()
    assert "[BT 评分规则文件回退]" in captured.out
    assert "weights.seeders 不是数字" in captured.out


def test_load_bt_scoring_rules_allows_env_override_for_source_site_priority(tmp_path: Path) -> None:
    path = tmp_path / "rules.yml"
    path.write_text(
        "source_site_preferred:\n"
        "  - PTerClub\n"
        "  - PassThePopcorn\n",
        encoding="utf-8",
    )

    rules = load_bt_scoring_rules(path, environ={"BT_SOURCE_SITE_PREFERRED": "PTP,BTN,BHD,PTerClub"})

    assert rules.source_site_preferred == ("PTP", "BTN", "BHD", "PTerClub")


def test_pick_best_can_use_loaded_custom_rules(tmp_path: Path) -> None:
    path = tmp_path / "custom.yml"
    path.write_text(
        "weights:\n"
        "  resolution: 1.0\n"
        "  source_site: 1.25\n"
        "  source_type: 1.0\n"
        "  seeders: 8.0\n"
        "  size_fit: 1.0\n"
        "  codec: 1.0\n"
        "  release_group: 0.0\n"
        "source_site_preferred:\n"
        "  - PTP\n"
        "release_group_preferred:\n"
        "  - CHD\n",
        encoding="utf-8",
    )
    custom_rules = load_bt_scoring_rules(path)

    best = pick_best(
        (
            _make_candidate(title="Dune 2021 1080p WEB-DL", seeders=3),
            _make_candidate(title="Dune 2021 720p WEBRip", resolution="720p", source_type="WEBRip", seeders=60),
        ),
        _movie_context(),
        rules=custom_rules,
    )

    assert best is not None
    assert best.candidate.title == "Dune 2021 720p WEBRip"


def _make_candidate(
    *,
    title: str = "Dune 2021 1080p",
    magnet_or_torrent_url: str = "https://example.com/dune.torrent",
    source_site: str = "nyaa",
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
        source_site=source_site,
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

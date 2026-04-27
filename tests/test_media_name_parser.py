from __future__ import annotations

from pathlib import Path

import pytest

import app.services.media_name_parser as parser_module
from app.services.media_name_parser import load_naming_rules, parse_media_name


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "",
            {
                "title": "",
                "alt_titles": (),
                "year": None,
                "season": None,
                "episode": None,
                "episode_end": None,
                "quality_tags": (),
                "source_group": None,
                "container": None,
                "media_kind": "unknown",
                "confidence_range": (0.0, 0.0),
            },
        ),
        (
            "Dune (2021)",
            {
                "title": "Dune",
                "alt_titles": (),
                "year": 2021,
                "season": None,
                "episode": None,
                "episode_end": None,
                "quality_tags": (),
                "source_group": None,
                "container": None,
                "media_kind": "movie",
                "confidence_range": (0.7, 0.9),
            },
        ),
        (
            "鬼灭之刃 S01E01",
            {
                "title": "鬼灭之刃",
                "alt_titles": ("Demon Slayer", "Kimetsu no Yaiba"),
                "year": None,
                "season": 1,
                "episode": 1,
                "episode_end": None,
                "quality_tags": (),
                "source_group": None,
                "container": None,
                "media_kind": "series",
                "confidence_range": (0.75, 0.9),
            },
        ),
        (
            "进击的巨人 第2季",
            {
                "title": "进击的巨人",
                "alt_titles": ("Attack on Titan", "Shingeki no Kyojin", "進撃の巨人"),
                "year": None,
                "season": 2,
                "episode": None,
                "episode_end": None,
                "quality_tags": (),
                "source_group": None,
                "container": None,
                "media_kind": "series",
                "confidence_range": (0.75, 0.9),
            },
        ),
        (
            "名侦探柯南 1096",
            {
                "title": "名侦探柯南",
                "alt_titles": (),
                "year": None,
                "season": None,
                "episode": 1096,
                "episode_end": None,
                "quality_tags": (),
                "source_group": None,
                "container": None,
                "media_kind": "anime",
                "confidence_range": (0.4, 0.7),
            },
        ),
        (
            "[SweetSub][Frieren][01][WebRip][1080p][AVC AAC][CHS][MP4]",
            {
                "title": "Frieren",
                "alt_titles": ("葬送的芙莉莲", "Sousou no Frieren"),
                "year": None,
                "season": None,
                "episode": 1,
                "episode_end": None,
                "quality_tags": ("1080p", "WEBRip"),
                "source_group": "SweetSub",
                "container": "mp4",
                "media_kind": "anime",
                "confidence_range": (0.3, 0.7),
            },
        ),
        (
            "鬼灭之刃.Demon.Slayer.S01E01.1080p.WEB-DL.x264-GROUP",
            {
                "title": "鬼灭之刃",
                "alt_titles": ("Demon Slayer", "Kimetsu no Yaiba"),
                "year": None,
                "season": 1,
                "episode": 1,
                "episode_end": None,
                "quality_tags": ("1080p", "WEB-DL", "x264"),
                "source_group": "GROUP",
                "container": None,
                "media_kind": "anime",
                "confidence_range": (0.7, 0.9),
            },
        ),
        (
            "Frieren.S01E01-03.2160p.BluRay.10bit.mkv",
            {
                "title": "Frieren",
                "alt_titles": ("葬送的芙莉莲", "Sousou no Frieren"),
                "year": None,
                "season": 1,
                "episode": 1,
                "episode_end": 3,
                "quality_tags": ("2160p", "BluRay", "10bit"),
                "source_group": None,
                "container": "mkv",
                "media_kind": "series",
                "confidence_range": (0.7, 0.9),
            },
        ),
        (
            "Attack on Titan EP 07 1080p",
            {
                "title": "Attack on Titan",
                "alt_titles": ("进击的巨人", "Shingeki no Kyojin", "進撃の巨人"),
                "year": None,
                "season": None,
                "episode": 7,
                "episode_end": None,
                "quality_tags": ("1080p",),
                "source_group": None,
                "container": None,
                "media_kind": "series",
                "confidence_range": (0.7, 0.9),
            },
        ),
        (
            "【葬送的芙莉莲】.ass",
            {
                "title": "葬送的芙莉莲",
                "alt_titles": ("Frieren", "Sousou no Frieren"),
                "year": None,
                "season": None,
                "episode": None,
                "episode_end": None,
                "quality_tags": (),
                "source_group": None,
                "container": "ass",
                "media_kind": "unknown",
                "confidence_range": (0.5, 0.7),
            },
        ),
    ],
)
def test_parse_media_name_typical_inputs(raw: str, expected: dict[str, object]) -> None:
    parsed = parse_media_name(raw)

    assert parsed.title == expected["title"]
    assert parsed.alt_titles == expected["alt_titles"]
    assert parsed.year == expected["year"]
    assert parsed.season == expected["season"]
    assert parsed.episode == expected["episode"]
    assert parsed.episode_end == expected["episode_end"]
    assert parsed.quality_tags == expected["quality_tags"]
    assert parsed.source_group == expected["source_group"]
    assert parsed.container == expected["container"]
    assert parsed.media_kind == expected["media_kind"]
    min_confidence, max_confidence = expected["confidence_range"]
    assert min_confidence <= parsed.parser_confidence <= max_confidence


def test_parse_media_name_uses_repo_rules_for_primary_title_aliases() -> None:
    parsed = parse_media_name("进击的巨人 第2季 繁中")

    assert parsed.title == "进击的巨人"
    assert "Attack on Titan" in parsed.alt_titles
    assert "Shingeki no Kyojin" in parsed.alt_titles
    assert "繁中" not in parsed.title


def test_parse_media_name_uses_repo_rules_for_alias_title() -> None:
    parsed = parse_media_name("Attack on Titan EP 07")

    assert parsed.title == "Attack on Titan"
    assert "进击的巨人" in parsed.alt_titles
    assert "Shingeki no Kyojin" in parsed.alt_titles


def test_parse_media_name_uses_repo_rules_to_strip_noise_tags() -> None:
    parsed = parse_media_name("鬼灭之刃 国配 1080p")

    assert parsed.title == "鬼灭之刃"
    assert parsed.quality_tags == ("1080p",)
    assert "Demon Slayer" in parsed.alt_titles


def test_parse_media_name_uses_custom_quality_whitelist(tmp_path: Path) -> None:
    rules_path = tmp_path / "naming_rules.yml"
    rules_path.write_text(
        "\n".join(
            [
                "strip_tags:",
                "  - 国配",
                "alt_titles:",
                '  - primary: "葬送的芙莉莲"',
                '    aliases: ["Frieren"]',
                "quality_whitelist:",
                "  - Remux",
                "  - 1080p",
            ]
        ),
        encoding="utf-8",
    )

    parsed = parse_media_name("Frieren Remux 国配", naming_rules=load_naming_rules(rules_path))

    assert parsed.title == "Frieren"
    assert parsed.quality_tags == ("Remux",)
    assert "葬送的芙莉莲" in parsed.alt_titles


def test_load_naming_rules_falls_back_to_builtin_defaults_for_missing_file(tmp_path: Path) -> None:
    parsed = parse_media_name("Dune CHS 1080p", naming_rules=load_naming_rules(tmp_path / "missing.yml"))

    assert parsed.title == "Dune"
    assert parsed.quality_tags == ("1080p",)


def test_load_naming_rules_falls_back_for_malformed_inline_list(tmp_path: Path) -> None:
    rules_path = tmp_path / "naming_rules.yml"
    rules_path.write_text("quality_whitelist: [1080p\n", encoding="utf-8")

    parsed = parse_media_name("Dune 1080p", naming_rules=load_naming_rules(rules_path))

    assert parsed.title == "Dune"
    assert parsed.quality_tags == ("1080p",)


def test_load_naming_rules_propagates_unexpected_parser_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rules_path = tmp_path / "naming_rules.yml"
    rules_path.write_text("strip_tags: []\n", encoding="utf-8")

    def _raise_unexpected(_: str) -> parser_module.NamingRules:
        raise RuntimeError("programming error")

    monkeypatch.setattr(parser_module, "_parse_naming_rules_yaml", _raise_unexpected)

    with pytest.raises(RuntimeError, match="programming error"):
        load_naming_rules(rules_path)

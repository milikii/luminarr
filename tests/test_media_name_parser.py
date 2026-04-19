from __future__ import annotations

import pytest

from app.services.media_name_parser import parse_media_name


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
                "alt_titles": (),
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
                "alt_titles": (),
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
                "alt_titles": (),
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
                "alt_titles": ("Demon Slayer",),
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
                "alt_titles": (),
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
                "alt_titles": (),
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
                "alt_titles": (),
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

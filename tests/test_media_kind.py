from __future__ import annotations

from app.services.media_kind import media_kind_label, parse_media_kind_prefix


def test_parse_media_kind_prefix_uses_default_when_prefix_is_missing() -> None:
    assert parse_media_kind_prefix("dune 2021", default_media_kind="movie") == ("movie", "dune 2021")
    assert parse_media_kind_prefix("dune 2021", default_media_kind="") == ("", "dune 2021")


def test_parse_media_kind_prefix_extracts_known_aliases() -> None:
    assert parse_media_kind_prefix("series 三体 2023", default_media_kind="movie") == ("series", "三体 2023")
    assert parse_media_kind_prefix("动漫 葬送的芙莉莲 2023", default_media_kind="movie") == ("anime", "葬送的芙莉莲 2023")


def test_media_kind_label_falls_back_to_movie_label() -> None:
    assert media_kind_label("series") == "剧集"
    assert media_kind_label("unknown") == "电影"

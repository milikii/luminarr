from __future__ import annotations

from collections.abc import Awaitable

from app.clients.tmdb import TmdbMovie
from app.services.search_media import (
    EMPTY_QUERY_TEXT,
    NO_RESULT_TEXT_TEMPLATE,
    SearchMediaService,
    parse_movie_query,
)


async def _fake_search_with_results(query: str) -> list[dict[str, object]]:
    assert query == "dune"
    return [
        {
            "title": "Dune: Part Two",
            "year": 2024,
            "quality": "2160p",
            "size": 8 * 1024 * 1024 * 1024,
            "indexer": {"name": "IndexerA"},
        },
        {
            "title": "Dune (2021)",
            "year": 2021,
            "resolution": "1080p",
            "size": 2 * 1024 * 1024 * 1024,
            "indexerName": "IndexerB",
        },
    ]


async def _fake_search_empty(query: str) -> list[dict[str, object]]:
    assert query == "unknown"
    return []


def test_search_and_format_with_results() -> None:
    service = SearchMediaService(_fake_search_with_results)
    text = _run(service.search_and_format("dune"))
    assert "搜索结果：dune" in text
    assert "1. Dune: Part Two (2024)" in text
    assert "画质: 2160p | 大小: 8.0 GB | 站点: IndexerA" in text
    assert "2. Dune (2021) (2021)" in text
    assert "画质: 1080p | 大小: 2.0 GB | 站点: IndexerB" in text


def test_search_and_format_empty_query() -> None:
    service = SearchMediaService(_fake_search_with_results)
    text = _run(service.search_and_format("   "))
    assert text == EMPTY_QUERY_TEXT


def test_search_and_format_no_result() -> None:
    service = SearchMediaService(_fake_search_empty)
    text = _run(service.search_and_format("unknown"))
    assert text == NO_RESULT_TEXT_TEMPLATE.format(query="unknown")


async def _fake_search_quality_from_title(query: str) -> list[dict[str, object]]:
    assert query == "dune"
    return [
        {
            "title": "Dune 1984 1080p AMZN WEB-DL DDP 5.1 H.264-vase",
            "size": 10 * 1024 * 1024 * 1024,
            "indexerName": "BeyondHD",
        }
    ]


def test_search_and_format_guesses_quality_from_title() -> None:
    service = SearchMediaService(_fake_search_quality_from_title)
    text = _run(service.search_and_format("dune"))
    assert "画质: 1080p WEB-DL" in text


async def _fake_search_tmdb_hit(query: str) -> list[dict[str, object]]:
    assert query == "Interstellar 2014"
    return [
        {
            "title": "Interstellar 2014 1080p BluRay",
            "year": 2014,
            "size": 2 * 1024 * 1024 * 1024,
            "indexerName": "IndexerA",
        }
    ]


async def _fake_lookup_tmdb_movie(title: str, year: str) -> TmdbMovie | None:
    assert title == "星际穿越"
    assert year == "2014"
    return TmdbMovie(title="Interstellar", original_title="Interstellar", year="2014")


def test_search_and_format_uses_tmdb_first_when_available() -> None:
    service = SearchMediaService(
        _fake_search_tmdb_hit,
        lookup_movie_func=_fake_lookup_tmdb_movie,
    )
    text = _run(service.search_and_format("星际穿越 (2014)"))
    assert "搜索结果：星际穿越 (2014)" in text
    assert "Interstellar 2014 1080p BluRay" in text


def test_search_and_format_fallbacks_to_normalized_query_when_tmdb_empty() -> None:
    seen_query: dict[str, str] = {}

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_query["value"] = query
        return []

    async def fake_tmdb_lookup(title: str, year: str) -> TmdbMovie | None:
        assert title == "Dune"
        assert year == "2021"
        return None

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("Dune (2021)"))
    assert seen_query["value"] == "Dune 2021"
    assert text == NO_RESULT_TEXT_TEMPLATE.format(query="Dune (2021)")


def test_search_and_format_fallbacks_to_normalized_query_when_tmdb_failed() -> None:
    seen_query: dict[str, str] = {}

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_query["value"] = query
        return []

    async def fake_tmdb_lookup(_: str, __: str) -> TmdbMovie | None:
        raise RuntimeError("tmdb unavailable")

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("Dune 2021"))
    assert seen_query["value"] == "Dune 2021"
    assert text == NO_RESULT_TEXT_TEMPLATE.format(query="Dune 2021")


def test_parse_movie_query_parentheses_year() -> None:
    parsed = parse_movie_query("Dune (2021)")
    assert parsed.title == "Dune"
    assert parsed.year == "2021"


def test_parse_movie_query_suffix_year() -> None:
    parsed = parse_movie_query("Dune 2021")
    assert parsed.title == "Dune"
    assert parsed.year == "2021"


def test_parse_movie_query_keeps_title_when_no_year() -> None:
    parsed = parse_movie_query("  Dune   Part   Two  ")
    assert parsed.title == "Dune Part Two"
    assert parsed.year == ""


def _run(coroutine: Awaitable[str]) -> str:
    import asyncio

    return asyncio.run(coroutine)

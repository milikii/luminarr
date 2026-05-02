from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import Any

import httpx
import pytest

from app.clients.tmdb import TmdbClient


class _FakeResponse:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def json(self) -> Any:
        return self._payload


def test_search_movie_returns_none_on_empty_title() -> None:
    client = TmdbClient(api_key="tmdb-key")
    result = _run(client.search_movie("   "))
    assert result is None


def test_get_movie_by_id_returns_none_on_empty_tmdb_id() -> None:
    client = TmdbClient(api_key="tmdb-key")
    result = _run(client.get_movie_by_id("   "))
    assert result is None


def test_get_movie_by_id_returns_valid_result() -> None:
    client = TmdbClient(api_key="tmdb-key", base_url="https://tmdb.example")
    captured: dict[str, Any] = {}

    async def fake_get(path: str, params: dict[str, str]) -> _FakeResponse:
        captured["path"] = path
        captured["params"] = params
        return _FakeResponse(
            {
                "id": 157336,
                "title": "星际穿越",
                "original_title": "Interstellar",
                "release_date": "2014-11-05",
                "poster_path": "/interstellar.jpg",
                "overview": "A journey across space and time.",
            }
        )

    client._get = fake_get  # type: ignore[method-assign]
    result = _run(client.get_movie_by_id("157336"))

    assert captured["path"] == "/3/movie/157336"
    assert captured["params"] == {"api_key": "tmdb-key", "language": "zh-CN"}
    assert result is not None
    assert result.title == "星际穿越"
    assert result.original_title == "Interstellar"
    assert result.year == "2014"
    assert result.tmdb_id == "157336"
    assert result.poster_path == "/interstellar.jpg"
    assert result.overview == "A journey across space and time."


def test_get_tv_by_id_returns_valid_result() -> None:
    client = TmdbClient(api_key="tmdb-key", base_url="https://tmdb.example")
    captured: dict[str, Any] = {}

    async def fake_get(path: str, params: dict[str, str]) -> _FakeResponse:
        captured["path"] = path
        captured["params"] = params
        return _FakeResponse(
            {
                "id": 1001,
                "name": "三体",
                "original_name": "Three-Body",
                "first_air_date": "2023-01-15",
                "poster_path": "/three-body.jpg",
                "overview": "Humanity makes first contact.",
            }
        )

    client._get = fake_get  # type: ignore[method-assign]
    result = _run(client.get_tv_by_id("1001"))

    assert captured["path"] == "/3/tv/1001"
    assert captured["params"] == {"api_key": "tmdb-key", "language": "zh-CN"}
    assert result is not None
    assert result.title == "三体"
    assert result.original_title == "Three-Body"
    assert result.year == "2023"
    assert result.tmdb_id == "1001"
    assert result.media_type == "tv"
    assert result.poster_path == "/three-body.jpg"
    assert result.overview == "Humanity makes first contact."


def test_get_movie_credits_returns_localized_people() -> None:
    client = TmdbClient(api_key="tmdb-key", base_url="https://tmdb.example")
    captured: dict[str, Any] = {}

    async def fake_get(path: str, params: dict[str, str]) -> _FakeResponse:
        captured["path"] = path
        captured["params"] = params
        return _FakeResponse(
            {
                "cast": [
                    {
                        "id": 100,
                        "name": "马修·麦康纳",
                        "original_name": "Matthew McConaughey",
                        "character": "库珀",
                        "order": 0,
                    }
                ],
                "crew": [
                    {
                        "id": 200,
                        "name": "克里斯托弗·诺兰",
                        "original_name": "Christopher Nolan",
                        "job": "Director",
                        "department": "Directing",
                    }
                ],
            }
        )

    client._get = fake_get  # type: ignore[method-assign]
    result = _run(client.get_movie_credits("157336", language="zh-CN"))

    assert captured["path"] == "/3/movie/157336/credits"
    assert captured["params"] == {"api_key": "tmdb-key", "language": "zh-CN"}
    assert result[0].person_id == "100"
    assert result[0].name == "马修·麦康纳"
    assert result[0].original_name == "Matthew McConaughey"
    assert result[0].character == "库珀"
    assert result[1].name == "克里斯托弗·诺兰"
    assert result[1].job == "Director"


def test_get_tv_credits_returns_empty_on_empty_tmdb_id() -> None:
    client = TmdbClient(api_key="tmdb-key")
    result = _run(client.get_tv_credits("   "))
    assert result == ()


def test_search_movie_returns_first_valid_result() -> None:
    client = TmdbClient(api_key="tmdb-key", base_url="https://tmdb.example")
    captured: dict[str, Any] = {}

    async def fake_get(path: str, params: dict[str, str]) -> _FakeResponse:
        captured["path"] = path
        captured["params"] = params
        return _FakeResponse(
            {
                "results": [
                    {"title": "", "original_title": "", "release_date": "2024-01-01"},
                    {
                        "id": 157336,
                        "title": "Interstellar",
                        "original_title": "Interstellar",
                        "release_date": "2014-11-05",
                    },
                ]
            }
        )

    client._get = fake_get  # type: ignore[method-assign]
    result = _run(client.search_movie("星际穿越", "2014"))

    assert captured["path"] == "/3/search/movie"
    assert captured["params"]["api_key"] == "tmdb-key"
    assert captured["params"]["query"] == "星际穿越"
    assert captured["params"]["year"] == "2014"
    assert captured["params"]["include_adult"] == "false"
    assert result is not None
    assert result.title == "Interstellar"
    assert result.original_title == "Interstellar"
    assert result.year == "2014"
    assert result.tmdb_id == "157336"


def test_search_movie_prefers_exact_title_match_over_partial_prefix() -> None:
    client = TmdbClient(api_key="tmdb-key")

    async def fake_get(_: str, params: dict[str, str]) -> _FakeResponse:
        assert params["query"] == "沙丘"
        assert params["year"] == "2021"
        return _FakeResponse(
            {
                "results": [
                    {
                        "id": 1,
                        "title": "沙丘虫暴",
                        "original_title": "Devil in Dune",
                        "release_date": "2021-07-30",
                    },
                    {
                        "id": 2,
                        "title": "沙丘",
                        "original_title": "Dune",
                        "release_date": "2021-09-15",
                    },
                ]
            }
        )

    client._get = fake_get  # type: ignore[method-assign]
    result = _run(client.search_movie("沙丘", "2021"))

    assert result is not None
    assert result.title == "沙丘"
    assert result.original_title == "Dune"
    assert result.tmdb_id == "2"


def test_search_movie_prefers_sequel_alias_match_over_base_title() -> None:
    client = TmdbClient(api_key="tmdb-key")

    async def fake_get(_: str, params: dict[str, str]) -> _FakeResponse:
        assert params["query"] == "Dune II"
        assert params["year"] == "2024"
        return _FakeResponse(
            {
                "results": [
                    {
                        "id": 1,
                        "title": "Dune",
                        "original_title": "Dune",
                        "release_date": "2024-01-01",
                    },
                    {
                        "id": 2,
                        "title": "Dune Part Two",
                        "original_title": "Dune: Part Two",
                        "release_date": "2024-03-01",
                    },
                ]
            }
        )

    client._get = fake_get  # type: ignore[method-assign]
    result = _run(client.search_movie("Dune II", "2024"))

    assert result is not None
    assert result.title == "Dune Part Two"
    assert result.tmdb_id == "2"


def test_search_movie_prefers_chapter_alias_match_over_base_title() -> None:
    client = TmdbClient(api_key="tmdb-key")

    async def fake_get(_: str, params: dict[str, str]) -> _FakeResponse:
        assert params["query"] == "John Wick IV"
        assert params["year"] == "2023"
        return _FakeResponse(
            {
                "results": [
                    {
                        "id": 1,
                        "title": "John Wick",
                        "original_title": "John Wick",
                        "release_date": "2023-01-01",
                    },
                    {
                        "id": 2,
                        "title": "John Wick: Chapter 4",
                        "original_title": "John Wick: Chapter 4",
                        "release_date": "2023-03-24",
                    },
                ]
            }
        )

    client._get = fake_get  # type: ignore[method-assign]
    result = _run(client.search_movie("John Wick IV", "2023"))

    assert result is not None
    assert result.title == "John Wick: Chapter 4"
    assert result.tmdb_id == "2"


def test_search_movie_prefers_chapter_word_alias_match_over_base_title() -> None:
    client = TmdbClient(api_key="tmdb-key")

    async def fake_get(_: str, params: dict[str, str]) -> _FakeResponse:
        assert params["query"] == "John Wick Chapter Four"
        assert params["year"] == "2023"
        return _FakeResponse(
            {
                "results": [
                    {
                        "id": 1,
                        "title": "John Wick",
                        "original_title": "John Wick",
                        "release_date": "2023-01-01",
                    },
                    {
                        "id": 2,
                        "title": "John Wick: Chapter 4",
                        "original_title": "John Wick: Chapter 4",
                        "release_date": "2023-03-24",
                    },
                ]
            }
        )

    client._get = fake_get  # type: ignore[method-assign]
    result = _run(client.search_movie("John Wick Chapter Four", "2023"))

    assert result is not None
    assert result.title == "John Wick: Chapter 4"
    assert result.tmdb_id == "2"


def test_search_movie_prefers_trailing_word_number_alias_match_over_base_title() -> None:
    client = TmdbClient(api_key="tmdb-key")

    async def fake_get(_: str, params: dict[str, str]) -> _FakeResponse:
        assert params["query"] == "Fast Ten"
        assert params["year"] == "2023"
        return _FakeResponse(
            {
                "results": [
                    {
                        "id": 1,
                        "title": "Fast Five",
                        "original_title": "Fast Five",
                        "release_date": "2023-01-01",
                    },
                    {
                        "id": 2,
                        "title": "Fast X",
                        "original_title": "Fast X",
                        "release_date": "2023-05-19",
                    },
                ]
            }
        )

    client._get = fake_get  # type: ignore[method-assign]
    result = _run(client.search_movie("Fast Ten", "2023"))

    assert result is not None
    assert result.title == "Fast X"
    assert result.tmdb_id == "2"


def test_search_media_candidates_prefers_exact_tmdb_identity_for_strong_japanese_title() -> None:
    client = TmdbClient(api_key="tmdb-key")

    async def fake_get(path: str, params: dict[str, str]) -> _FakeResponse:
        assert params["query"] == "你的名字"
        if path == "/3/search/movie":
            return _FakeResponse(
                {
                    "results": [
                        {
                            "id": 12,
                            "title": "你的名字 特别收藏版",
                            "original_title": "君の名は。4K Collection",
                            "release_date": "2017-01-01",
                        },
                        {
                            "id": 11,
                            "title": "你的名字。",
                            "original_title": "君の名は。",
                            "release_date": "2016-08-26",
                            "poster_path": "/your-name.jpg",
                            "overview": "Two teenagers share a supernatural connection.",
                        },
                    ]
                }
            )
        assert path == "/3/search/tv"
        return _FakeResponse(
            {
                "results": [
                    {
                        "id": 21,
                        "name": "你的名字：特辑",
                        "original_name": "君の名は。 特別編",
                        "first_air_date": "2018-01-01",
                    }
                ]
            }
        )

    client._get = fake_get  # type: ignore[method-assign]

    results = _run(client.search_media_candidates("你的名字", limit=5))

    assert [item.tmdb_id for item in results] == ["11"]
    assert results[0].title == "你的名字。"
    assert results[0].poster_path == "/your-name.jpg"
    assert results[0].overview == "Two teenagers share a supernatural connection."


def test_search_media_candidates_keeps_broad_candidates_for_short_generic_cjk_query() -> None:
    client = TmdbClient(api_key="tmdb-key")

    async def fake_get(path: str, params: dict[str, str]) -> _FakeResponse:
        assert params["query"] == "传奇"
        if path == "/3/search/movie":
            return _FakeResponse(
                {
                    "results": [
                        {
                            "id": 100,
                            "title": "传奇",
                            "original_title": "Legend",
                            "release_date": "2015-11-20",
                            "poster_path": "/legend-2015.jpg",
                            "popularity": 42.0,
                            "vote_count": 1800,
                        },
                        {
                            "id": 104,
                            "title": "传奇联盟",
                            "original_title": "Legend League",
                            "release_date": "2016-01-01",
                            "popularity": 5.0,
                            "vote_count": 12,
                        },
                        {
                            "id": 105,
                            "title": "传奇少年",
                            "original_title": "Legend Boy",
                            "release_date": "2017-01-01",
                            "popularity": 4.0,
                            "vote_count": 8,
                        },
                        {
                            "id": 106,
                            "title": "传奇风云",
                            "original_title": "Legend Storm",
                            "release_date": "2018-01-01",
                            "popularity": 3.0,
                            "vote_count": 6,
                        },
                        {
                            "id": 101,
                            "title": "黑道传奇",
                            "original_title": "Legend",
                            "release_date": "2015-09-09",
                            "popularity": 18.0,
                            "vote_count": 220,
                        },
                        {
                            "id": 102,
                            "title": "我是传奇",
                            "original_title": "I Am Legend",
                            "release_date": "2007-12-14",
                            "poster_path": "/i-am-legend.jpg",
                            "overview": "A lone survivor searches for a cure in a devastated world.",
                            "popularity": 68.0,
                            "vote_count": 9500,
                        },
                        {
                            "id": 103,
                            "title": "纳尼亚传奇：狮子、女巫和魔衣橱",
                            "original_title": "The Chronicles of Narnia: The Lion, the Witch and the Wardrobe",
                            "release_date": "2005-12-07",
                            "popularity": 55.0,
                            "vote_count": 8200,
                        },
                    ]
                }
            )
        if path == "/3/search/tv":
            return _FakeResponse(
                {
                    "results": [
                        {
                            "id": 201,
                            "name": "传奇办公室",
                            "original_name": "Le Bureau des Légendes",
                            "first_air_date": "2015-04-27",
                            "popularity": 24.0,
                            "vote_count": 340,
                        },
                        {
                            "id": 202,
                            "name": "传奇训练营",
                            "original_name": "Legend Camp",
                            "first_air_date": "2019-02-01",
                            "popularity": 2.0,
                            "vote_count": 4,
                        }
                    ]
                }
            )
        raise AssertionError(f"unexpected TMDB path: {path}")

    client._get = fake_get  # type: ignore[method-assign]

    results = _run(client.search_media_candidates("传奇", limit=5))

    assert len(results) == 5
    assert results[0].title == "传奇"
    assert any(item.title == "我是传奇" for item in results)
    assert any(item.title == "传奇办公室" for item in results)
    assert any(item.title == "纳尼亚传奇：狮子、女巫和魔衣橱" for item in results)
    assert all(item.title != "传奇训练营" for item in results)


def test_search_media_candidates_keeps_compact_family_for_short_strong_cjk_title_with_single_mainstream_contains() -> None:
    client = TmdbClient(api_key="tmdb-key")

    async def fake_get(path: str, params: dict[str, str]) -> _FakeResponse:
        assert params["query"] == "色戒"
        if path == "/3/search/movie":
            return _FakeResponse(
                {
                    "results": [
                        {
                            "id": 401,
                            "title": "色戒",
                            "original_title": "Lust, Caution",
                            "release_date": "2007-11-01",
                            "poster_path": "/lust-caution.jpg",
                            "overview": "An espionage drama set in occupied Shanghai.",
                            "popularity": 36.0,
                            "vote_count": 1600,
                        },
                        {
                            "id": 402,
                            "title": "色戒 导演剪辑版",
                            "original_title": "Lust, Caution Director's Cut",
                            "release_date": "2007-12-01",
                            "poster_path": "/lust-caution-director.jpg",
                            "overview": "A lower-priority cut of the same film.",
                            "popularity": 9.0,
                            "vote_count": 40,
                        },
                        {
                            "id": 403,
                            "title": "色戒 幕后纪事",
                            "original_title": "Lust, Caution Behind the Scenes",
                            "release_date": "2008-01-01",
                            "poster_path": "/lust-caution-behind.jpg",
                            "overview": "A featurette that should stay behind the main film.",
                            "popularity": 6.0,
                            "vote_count": 18,
                        },
                        {
                            "id": 404,
                            "title": "色戒 十五周年纪念版",
                            "original_title": "Lust, Caution 15th Anniversary Edition",
                            "release_date": "2022-01-01",
                            "poster_path": "/lust-caution-anniversary.jpg",
                            "overview": "A commemorative re-release that should stay out of the compact set.",
                            "popularity": 3.0,
                            "vote_count": 9,
                        },
                        {
                            "id": 405,
                            "title": "情陷色戒",
                            "original_title": "Temptation Around Lust, Caution",
                            "release_date": "2011-01-01",
                            "poster_path": "/temptation-around-lust-caution.jpg",
                            "overview": "A mainstream contains-style title that should not blow the query back open.",
                            "popularity": 51.0,
                            "vote_count": 6200,
                        },
                    ]
                }
            )
        if path == "/3/search/tv":
            return _FakeResponse({"results": []})
        raise AssertionError(f"unexpected TMDB path: {path}")

    client._get = fake_get  # type: ignore[method-assign]

    results = _run(client.search_media_candidates("色戒", limit=5))

    assert [item.tmdb_id for item in results] == ["401", "402", "403"]
    assert results[0].title == "色戒"
    assert all(item.title != "情陷色戒" for item in results)


@pytest.mark.parametrize("query", ["魔戒", "指环王", "Lord of the Rings"])
def test_search_media_candidates_prefers_lord_of_the_rings_franchise_for_explicit_alias_query(query: str) -> None:
    client = TmdbClient(api_key="tmdb-key")

    async def fake_get(path: str, params: dict[str, str]) -> _FakeResponse:
        assert params["query"] == query
        if path == "/3/search/movie":
            return _FakeResponse(
                {
                    "results": [
                        {
                            "id": 91,
                            "title": "魔戒迷踪",
                            "original_title": "Ringers: Lord of the Fans",
                            "release_date": "2005-01-21",
                        },
                        {
                            "id": 92,
                            "title": "指环王：护戒使者",
                            "original_title": "The Lord of the Rings: The Fellowship of the Ring",
                            "release_date": "2001-12-19",
                            "poster_path": "/lotr-fellowship.jpg",
                            "overview": "Frodo begins the journey to destroy the One Ring.",
                        },
                        {
                            "id": 93,
                            "title": "指环王：双塔奇兵",
                            "original_title": "The Lord of the Rings: The Two Towers",
                            "release_date": "2002-12-18",
                        },
                        {
                            "id": 95,
                            "title": "指环王：王者无敌",
                            "original_title": "The Lord of the Rings: The Return of the King",
                            "release_date": "2003-12-17",
                        },
                    ]
                }
            )
        assert path == "/3/search/tv"
        return _FakeResponse(
            {
                "results": [
                    {
                        "id": 94,
                        "name": "牙狼：魔戒之花",
                        "original_name": "GARO: Makai no Hana",
                        "first_air_date": "2014-04-04",
                    }
                ]
            }
        )

    client._get = fake_get  # type: ignore[method-assign]

    results = _run(client.search_media_candidates(query, limit=5))

    assert [item.tmdb_id for item in results] == ["92", "93", "95"]
    assert results[0].title == "指环王：护戒使者"
    assert results[0].poster_path == "/lotr-fellowship.jpg"
    assert results[0].overview == "Frodo begins the journey to destroy the One Ring."
    assert all(item.tmdb_id not in {"91", "94"} for item in results)


def test_search_movie_prefers_base_title_when_query_has_final_cut_noise() -> None:
    client = TmdbClient(api_key="tmdb-key")

    async def fake_get(_: str, params: dict[str, str]) -> _FakeResponse:
        assert params["query"] == "Blade Runner Final Cut"
        assert params["year"] == "1982"
        return _FakeResponse(
            {
                "results": [
                    {
                        "id": 1,
                        "title": "Blade Runner 2049",
                        "original_title": "Blade Runner 2049",
                        "release_date": "1982-10-01",
                    },
                    {
                        "id": 2,
                        "title": "Blade Runner",
                        "original_title": "Blade Runner",
                        "release_date": "1982-06-25",
                    },
                ]
            }
        )

    client._get = fake_get  # type: ignore[method-assign]
    result = _run(client.search_movie("Blade Runner Final Cut", "1982"))

    assert result is not None
    assert result.title == "Blade Runner"
    assert result.tmdb_id == "2"


def test_search_movie_prefers_base_title_when_query_has_the_final_cut_noise() -> None:
    client = TmdbClient(api_key="tmdb-key")

    async def fake_get(_: str, params: dict[str, str]) -> _FakeResponse:
        assert params["query"] == "Blade Runner The Final Cut"
        assert params["year"] == "1982"
        return _FakeResponse(
            {
                "results": [
                    {
                        "id": 1,
                        "title": "Blade Runner 2049",
                        "original_title": "Blade Runner 2049",
                        "release_date": "1982-10-01",
                    },
                    {
                        "id": 2,
                        "title": "Blade Runner",
                        "original_title": "Blade Runner",
                        "release_date": "1982-06-25",
                    },
                ]
            }
        )

    client._get = fake_get  # type: ignore[method-assign]
    result = _run(client.search_movie("Blade Runner The Final Cut", "1982"))

    assert result is not None
    assert result.title == "Blade Runner"
    assert result.tmdb_id == "2"


def test_search_movie_prefers_chapter_alias_when_query_has_extended_noise() -> None:
    client = TmdbClient(api_key="tmdb-key")

    async def fake_get(_: str, params: dict[str, str]) -> _FakeResponse:
        assert params["query"] == "John Wick Chapter 4 Extended"
        assert params["year"] == "2023"
        return _FakeResponse(
            {
                "results": [
                    {
                        "id": 1,
                        "title": "John Wick",
                        "original_title": "John Wick",
                        "release_date": "2023-01-01",
                    },
                    {
                        "id": 2,
                        "title": "John Wick: Chapter 4",
                        "original_title": "John Wick: Chapter 4",
                        "release_date": "2023-03-24",
                    },
                ]
            }
        )

    client._get = fake_get  # type: ignore[method-assign]
    result = _run(client.search_movie("John Wick Chapter 4 Extended", "2023"))

    assert result is not None
    assert result.title == "John Wick: Chapter 4"
    assert result.tmdb_id == "2"


def test_search_movie_prefers_part_alias_when_query_has_imax_enhanced_noise() -> None:
    client = TmdbClient(api_key="tmdb-key")

    async def fake_get(_: str, params: dict[str, str]) -> _FakeResponse:
        assert params["query"] == "Dune Part 2 IMAX Enhanced"
        assert params["year"] == "2024"
        return _FakeResponse(
            {
                "results": [
                    {
                        "id": 1,
                        "title": "Dune",
                        "original_title": "Dune",
                        "release_date": "2024-01-01",
                    },
                    {
                        "id": 2,
                        "title": "Dune Part Two",
                        "original_title": "Dune: Part Two",
                        "release_date": "2024-03-01",
                    },
                ]
            }
        )

    client._get = fake_get  # type: ignore[method-assign]
    result = _run(client.search_movie("Dune Part 2 IMAX Enhanced", "2024"))

    assert result is not None
    assert result.title == "Dune Part Two"
    assert result.tmdb_id == "2"


def test_search_movie_prefers_base_title_when_query_has_remastered_noise() -> None:
    client = TmdbClient(api_key="tmdb-key")

    async def fake_get(_: str, params: dict[str, str]) -> _FakeResponse:
        assert params["query"] == "Alien Remastered"
        assert params["year"] == "1979"
        return _FakeResponse(
            {
                "results": [
                    {
                        "id": 1,
                        "title": "Aliens",
                        "original_title": "Aliens",
                        "release_date": "1979-07-01",
                    },
                    {
                        "id": 2,
                        "title": "Alien",
                        "original_title": "Alien",
                        "release_date": "1979-05-25",
                    },
                ]
            }
        )

    client._get = fake_get  # type: ignore[method-assign]
    result = _run(client.search_movie("Alien Remastered", "1979"))

    assert result is not None
    assert result.title == "Alien"
    assert result.tmdb_id == "2"


def test_search_movie_prefers_base_title_when_query_has_extended_cut_noise() -> None:
    client = TmdbClient(api_key="tmdb-key")

    async def fake_get(_: str, params: dict[str, str]) -> _FakeResponse:
        assert params["query"] == "Avatar Extended Cut"
        assert params["year"] == "2009"
        return _FakeResponse(
            {
                "results": [
                    {
                        "id": 1,
                        "title": "The Last Avatar",
                        "original_title": "The Last Avatar",
                        "release_date": "2009-08-01",
                    },
                    {
                        "id": 2,
                        "title": "Avatar",
                        "original_title": "Avatar",
                        "release_date": "2009-12-18",
                    },
                ]
            }
        )

    client._get = fake_get  # type: ignore[method-assign]
    result = _run(client.search_movie("Avatar Extended Cut", "2009"))

    assert result is not None
    assert result.title == "Avatar"
    assert result.tmdb_id == "2"


def test_search_movie_prefers_base_title_when_query_has_anniversary_edition_noise() -> None:
    client = TmdbClient(api_key="tmdb-key")

    async def fake_get(_: str, params: dict[str, str]) -> _FakeResponse:
        assert params["query"] == "Blade Runner Anniversary Edition"
        assert params["year"] == "1982"
        return _FakeResponse(
            {
                "results": [
                    {
                        "id": 1,
                        "title": "Blade Runner 2049",
                        "original_title": "Blade Runner 2049",
                        "release_date": "1982-10-01",
                    },
                    {
                        "id": 2,
                        "title": "Blade Runner",
                        "original_title": "Blade Runner",
                        "release_date": "1982-06-25",
                    },
                ]
            }
        )

    client._get = fake_get  # type: ignore[method-assign]
    result = _run(client.search_movie("Blade Runner Anniversary Edition", "1982"))

    assert result is not None
    assert result.title == "Blade Runner"
    assert result.tmdb_id == "2"


def test_search_movie_without_valid_result_returns_none() -> None:
    client = TmdbClient(api_key="tmdb-key")

    async def fake_get(_: str, params: dict[str, str]) -> _FakeResponse:
        _ = params
        return _FakeResponse({"results": [{"title": "", "original_title": "", "release_date": ""}]})

    client._get = fake_get  # type: ignore[method-assign]
    result = _run(client.search_movie("unknown"))
    assert result is None


def test_search_tv_candidates_returns_valid_results() -> None:
    client = TmdbClient(api_key="tmdb-key")
    captured: dict[str, Any] = {}

    async def fake_get(path: str, params: dict[str, str]) -> _FakeResponse:
        captured["path"] = path
        captured["params"] = params
        return _FakeResponse(
            {
                "results": [
                    {
                        "id": 1001,
                        "name": "Three-Body",
                        "original_name": "三体",
                        "first_air_date": "2023-01-15",
                        "poster_path": "/three-body.jpg",
                        "overview": "A science fiction series.",
                    },
                    {
                        "id": 1002,
                        "name": "Frieren: Beyond Journey's End",
                        "original_name": "葬送的芙莉莲",
                        "first_air_date": "2023-09-29",
                    },
                ]
            }
        )

    client._get = fake_get  # type: ignore[method-assign]
    result = _run(client.search_tv_candidates("三体", year="2023", limit=2))

    assert captured["path"] == "/3/search/tv"
    assert captured["params"]["query"] == "三体"
    assert captured["params"]["first_air_date_year"] == "2023"
    assert len(result) == 2
    assert result[0].title == "Three-Body"
    assert result[0].original_title == "三体"
    assert result[0].year == "2023"
    assert result[0].tmdb_id == "1001"
    assert result[0].media_type == "tv"
    assert result[0].poster_path == "/three-body.jpg"
    assert result[0].overview == "A science fiction series."


def test_search_media_candidates_keeps_mixed_media_candidates_when_query_is_broad() -> None:
    client = TmdbClient(api_key="tmdb-key")
    seen_paths: list[str] = []

    async def fake_get(path: str, params: dict[str, str]) -> _FakeResponse:
        seen_paths.append(path)
        assert params["query"] == "丧尸"
        if path == "/3/search/movie":
            return _FakeResponse(
                {
                    "results": [
                        {
                            "id": 222,
                            "title": "Zombie for Sale",
                            "original_title": "기묘한 가족",
                            "release_date": "2019-01-01",
                            "poster_path": "/zombie-for-sale.jpg",
                            "overview": "A family comedy about zombies.",
                        }
                    ]
                }
            )
        if path == "/3/search/tv":
            return _FakeResponse(
                {
                    "results": [
                        {
                            "id": 111,
                            "name": "Zombie Detective",
                            "original_name": "좀비탐정",
                            "first_air_date": "2020-01-01",
                            "poster_path": "/zombie-detective.jpg",
                            "overview": "A detective story with a zombie lead.",
                        }
                    ]
                }
            )
        raise AssertionError(f"unexpected TMDB path: {path}")

    client._get = fake_get  # type: ignore[method-assign]
    result = _run(client.search_media_candidates("丧尸", limit=3))

    assert seen_paths == ["/3/search/movie", "/3/search/tv"]
    assert {item.media_type for item in result} == {"tv", "movie"}
    assert any(item.title == "Zombie Detective" for item in result)
    assert any(item.title == "Zombie for Sale" for item in result)


def test_search_media_candidates_prefers_exact_movie_identity_for_strong_title() -> None:
    client = TmdbClient(api_key="tmdb-key")

    async def fake_get(path: str, params: dict[str, str]) -> _FakeResponse:
        assert params["query"] == "你的名字"
        if path == "/3/search/movie":
            return _FakeResponse(
                {
                    "results": [
                        {
                            "id": 372058,
                            "title": "你的名字。",
                            "original_title": "君の名は。",
                            "release_date": "2016-08-26",
                            "poster_path": "/your-name.jpg",
                            "overview": "Two teenagers share a mysterious connection.",
                        }
                    ]
                }
            )
        if path == "/3/search/tv":
            return _FakeResponse(
                {
                    "results": [
                        {
                            "id": 9001,
                            "name": "你的名字 特别篇",
                            "original_name": "Your Name Special",
                            "first_air_date": "2021-01-01",
                            "poster_path": "/your-name-special.jpg",
                            "overview": "A lower relevance expanded-title result.",
                        }
                    ]
                }
            )
        raise AssertionError(f"unexpected TMDB path: {path}")

    client._get = fake_get  # type: ignore[method-assign]
    result = _run(client.search_media_candidates("你的名字", limit=3))

    assert [item.media_type for item in result] == ["movie"]
    assert result[0].title == "你的名字。"
    assert result[0].tmdb_id == "372058"


def test_search_media_candidates_filters_out_low_relevance_expanded_titles_for_strong_query() -> None:
    client = TmdbClient(api_key="tmdb-key")

    async def fake_get(path: str, params: dict[str, str]) -> _FakeResponse:
        assert params["query"] == "你的名字"
        if path == "/3/search/movie":
            return _FakeResponse(
                {
                    "results": [
                        {
                            "id": 372058,
                            "title": "你的名字。",
                            "original_title": "君の名は。",
                            "release_date": "2016-08-26",
                        },
                        {
                            "id": 9002,
                            "title": "你的名字我的姓氏",
                            "original_title": "Your Name My Surname",
                            "release_date": "2020-01-01",
                        },
                    ]
                }
            )
        if path == "/3/search/tv":
            return _FakeResponse({"results": []})
        raise AssertionError(f"unexpected TMDB path: {path}")

    client._get = fake_get  # type: ignore[method-assign]
    result = _run(client.search_media_candidates("你的名字", limit=5))

    assert [item.tmdb_id for item in result] == ["372058"]


def test_tmdb_client_passes_proxy_to_httpx(monkeypatch) -> None:
    client_kwargs: list[dict[str, object]] = []

    class FakeAsyncClient:
        def __init__(self, **kwargs: object) -> None:
            client_kwargs.append(dict(kwargs))

        async def __aenter__(self) -> FakeAsyncClient:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, url: str, params: dict[str, str]) -> httpx.Response:
            return httpx.Response(
                200,
                json={"results": []},
                request=httpx.Request("GET", url, params=params),
            )

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient(**kwargs))

    client = TmdbClient(
        api_key="tmdb-key",
        base_url="https://tmdb.example",
        proxy_url="http://192.168.2.110:7890",
    )
    result = asyncio.run(client.search_movie_candidates("Dune", limit=1))

    assert result == []
    assert client_kwargs
    assert client_kwargs[0]["proxy"] == "http://192.168.2.110:7890"


def _run(coroutine: Awaitable[Any]) -> Any:
    import asyncio

    return asyncio.run(coroutine)

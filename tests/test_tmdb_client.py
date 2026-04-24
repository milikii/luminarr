from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import Any

import httpx

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

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

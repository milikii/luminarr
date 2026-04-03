from __future__ import annotations

from collections.abc import Awaitable
from typing import Any

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


def _run(coroutine: Awaitable[Any]) -> Any:
    import asyncio

    return asyncio.run(coroutine)

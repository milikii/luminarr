from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import Any

import httpx

from app.clients.fanart import FanartClient


class _FakeResponse:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def json(self) -> Any:
        return self._payload


def test_get_movie_images_returns_none_on_empty_tmdb_id() -> None:
    client = FanartClient(api_key="fanart-key")
    result = _run(client.get_movie_images("  "))
    assert result is None


def test_get_movie_images_returns_first_valid_urls() -> None:
    client = FanartClient(api_key="fanart-key", base_url="https://fanart.example")
    captured: dict[str, Any] = {}

    async def fake_get(path: str, params: dict[str, str]) -> _FakeResponse:
        captured["path"] = path
        captured["params"] = params
        return _FakeResponse(
            {
                "movieposter": [
                    {"url": ""},
                    {"url": "https://img.example/poster.jpg"},
                ],
                "moviebackground": [
                    {"url": "https://img.example/bg.jpg"},
                ],
            }
        )

    client._get = fake_get  # type: ignore[method-assign]
    result = _run(client.get_movie_images("157336"))

    assert captured["path"] == "/movies/157336"
    assert captured["params"]["api_key"] == "fanart-key"
    assert result is not None
    assert result.poster_url == "https://img.example/poster.jpg"
    assert result.backdrop_url == "https://img.example/bg.jpg"


def test_get_movie_images_keeps_extended_assets_separate_from_poster_and_backdrop() -> None:
    client = FanartClient(api_key="fanart-key", base_url="https://fanart.example")

    async def fake_get(_: str, params: dict[str, str]) -> _FakeResponse:
        _ = params
        return _FakeResponse(
            {
                "hdmovieclearart": [
                    {"url": "https://img.example/clearart.png"},
                ],
                "movielogo": [
                    {"url": "https://img.example/logo.png"},
                ],
                "moviethumb": [
                    {"url": "https://img.example/thumb.jpg"},
                ],
            }
        )

    client._get = fake_get  # type: ignore[method-assign]
    result = _run(client.get_movie_images("157336"))

    assert result is not None
    assert result.poster_url == ""
    assert result.backdrop_url == ""
    assert result.logo_url == "https://img.example/logo.png"
    assert result.clearart_url == "https://img.example/clearart.png"
    assert result.thumb_url == "https://img.example/thumb.jpg"


def test_get_movie_images_returns_none_without_urls() -> None:
    client = FanartClient(api_key="fanart-key")

    async def fake_get(_: str, params: dict[str, str]) -> _FakeResponse:
        _ = params
        return _FakeResponse({"movieposter": [{"url": " "}], "moviebackground": []})

    client._get = fake_get  # type: ignore[method-assign]
    result = _run(client.get_movie_images("157336"))
    assert result is None


def test_fanart_client_passes_proxy_to_httpx(monkeypatch) -> None:
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
                json={},
                request=httpx.Request("GET", url, params=params),
            )

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient(**kwargs))

    client = FanartClient(
        api_key="fanart-key",
        base_url="https://fanart.example",
        proxy_url="http://192.168.2.110:7890",
    )
    result = asyncio.run(client.get_movie_images("157336"))

    assert result is None
    assert client_kwargs
    assert client_kwargs[0]["proxy"] == "http://192.168.2.110:7890"


def _run(coroutine: Awaitable[Any]) -> Any:
    import asyncio

    return asyncio.run(coroutine)

from __future__ import annotations

import asyncio

import httpx
import pytest

from app.clients.jellyfin import JellyfinClient


def test_jellyfin_client_refresh_library_posts_refresh_request(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(self, url: str, *, headers: dict[str, str]) -> httpx.Response:
            captured["method"] = "POST"
            captured["url"] = url
            captured["token"] = headers.get("X-Emby-Token")
            return httpx.Response(status_code=204, request=httpx.Request("POST", url))

    monkeypatch.setattr("app.clients.jellyfin.httpx.AsyncClient", FakeAsyncClient)

    asyncio.run(JellyfinClient(base_url="http://jellyfin:8096", api_key="jelly-key").refresh_library())

    assert captured["method"] == "POST"
    assert captured["url"] == "http://jellyfin:8096/Library/Refresh"
    assert captured["token"] == "jelly-key"
    assert captured["timeout"] == 10.0


def test_jellyfin_client_refresh_library_raises_for_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            self._timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(self, url: str, *, headers: dict[str, str]) -> httpx.Response:
            _ = (headers, self._timeout)
            return httpx.Response(status_code=500, request=httpx.Request("POST", url))

    monkeypatch.setattr("app.clients.jellyfin.httpx.AsyncClient", FakeAsyncClient)

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(JellyfinClient(base_url="http://jellyfin:8096", api_key="jelly-key").refresh_library())

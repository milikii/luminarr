from __future__ import annotations

import asyncio

import httpx
import pytest

from app.clients.plex import PlexClient


def test_plex_client_refresh_library_gets_refresh_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

    class FakeAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            captured["timeout"] = timeout

        async def __aenter__(self) -> FakeAsyncClient:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, url: str, params: dict[str, str]) -> FakeResponse:
            captured["url"] = url
            captured["token"] = params.get("X-Plex-Token")
            return FakeResponse()

    monkeypatch.setattr("app.clients.plex.httpx.AsyncClient", FakeAsyncClient)

    asyncio.run(PlexClient(base_url="http://plex:32400", token="plex-token").refresh_library())

    assert captured["timeout"] == 10.0
    assert captured["url"] == "http://plex:32400/library/sections/all/refresh"
    assert captured["token"] == "plex-token"


def test_plex_client_refresh_library_raises_for_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            request = httpx.Request("GET", "http://plex:32400/library/sections/all/refresh")
            response = httpx.Response(status_code=500, request=request)
            raise httpx.HTTPStatusError("refresh failed", request=request, response=response)

    class FakeAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            assert timeout == 10.0

        async def __aenter__(self) -> FakeAsyncClient:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, url: str, params: dict[str, str]) -> FakeResponse:
            assert url == "http://plex:32400/library/sections/all/refresh"
            assert params == {"X-Plex-Token": "plex-token"}
            return FakeResponse()

    monkeypatch.setattr("app.clients.plex.httpx.AsyncClient", FakeAsyncClient)

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(PlexClient(base_url="http://plex:32400", token="plex-token").refresh_library())

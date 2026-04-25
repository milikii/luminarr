from __future__ import annotations

import asyncio
from collections.abc import Callable

import httpx

from app.clients.transmission import TransmissionClient


class FakeAsyncClient:
    def __init__(self, dispatcher: Callable[[str, str, dict[str, object] | None], httpx.Response], **_: object) -> None:
        self._dispatcher = dispatcher

    async def __aenter__(self) -> FakeAsyncClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(self, url: str, json: dict[str, object] | None = None, headers: dict[str, str] | None = None) -> httpx.Response:
        _ = headers
        return self._dispatcher("POST", url, json)


def _json_response(method: str, url: str, payload: object, status_code: int = 200) -> httpx.Response:
    return httpx.Response(status_code, json=payload, request=httpx.Request(method, url))


def test_remove_torrent_uses_torrent_remove_rpc(monkeypatch) -> None:
    requests: list[dict[str, object]] = []

    def dispatcher(method: str, url: str, payload: dict[str, object] | None) -> httpx.Response:
        requests.append(payload or {})
        assert method == "POST"
        assert url == "http://tr:9091/transmission/rpc"
        return _json_response(method, url, {"result": "success", "arguments": {}})

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient(dispatcher, **kwargs))

    client = TransmissionClient(base_url="http://tr:9091")
    asyncio.run(client.remove_torrent("hash-42", delete_local_data=True))

    assert requests == [
        {
            "method": "torrent-remove",
            "arguments": {
                "ids": ["hash-42"],
                "delete-local-data": True,
            },
        }
    ]

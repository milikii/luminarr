from __future__ import annotations

import asyncio
import base64
from collections.abc import Callable

import httpx
import pytest

from app.clients.qbittorrent import QbittorrentClient


class FakeAsyncClient:
    def __init__(self, dispatcher: Callable[[str, str, dict[str, object]], httpx.Response], **_: object) -> None:
        self._dispatcher = dispatcher

    async def __aenter__(self) -> FakeAsyncClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(self, url: str, data: dict[str, object] | None = None) -> httpx.Response:
        return self._dispatcher("POST", url, data or {})

    async def get(self, url: str, params: dict[str, object] | None = None) -> httpx.Response:
        return self._dispatcher("GET", url, params or {})


def _text_response(method: str, url: str, text: str, status_code: int = 200) -> httpx.Response:
    return httpx.Response(status_code, text=text, request=httpx.Request(method, url))


def _json_response(method: str, url: str, payload: object, status_code: int = 200) -> httpx.Response:
    return httpx.Response(status_code, json=payload, request=httpx.Request(method, url))


def test_add_torrent_resolves_magnet_hash_and_savepath(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str, dict[str, object]]] = []
    list_calls = 0

    def dispatcher(method: str, url: str, payload: dict[str, object]) -> httpx.Response:
        nonlocal list_calls
        calls.append((method, url, payload))
        if url.endswith("/auth/login"):
            return _text_response(method, url, "Ok.")
        if method == "GET" and url.endswith("/torrents/info"):
            list_calls += 1
            if list_calls == 1:
                return _json_response(method, url, [])
            return _json_response(
                method,
                url,
                [{"hash": "abcdef1234567890abcdef1234567890abcdef12", "added_on": 1}],
            )
        if method == "POST" and url.endswith("/torrents/add"):
            return _text_response(method, url, "Ok.")
        raise AssertionError(f"unexpected request: {method} {url} {payload}")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient(dispatcher, **kwargs))

    client = QbittorrentClient(base_url="http://qb:8080", username="user", password="pass")
    task = asyncio.run(
        client.add_torrent("magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12", "/data/downloads/qb")
    )

    assert task.task_id == "abcdef1234567890abcdef1234567890abcdef12"
    assert task.task_hash == "abcdef1234567890abcdef1234567890abcdef12"
    assert calls[2][2]["savepath"] == "/data/downloads/qb"


def test_add_torrent_resolves_base32_magnet_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    expected_hash = "abcdef1234567890abcdef1234567890abcdef12"
    magnet_hash = base64.b32encode(bytes.fromhex(expected_hash)).decode("ascii").rstrip("=")
    list_calls = 0

    def dispatcher(method: str, url: str, payload: dict[str, object]) -> httpx.Response:
        nonlocal list_calls
        if url.endswith("/auth/login"):
            return _text_response(method, url, "Ok.")
        if method == "GET" and url.endswith("/torrents/info"):
            list_calls += 1
            if list_calls == 1:
                return _json_response(method, url, [])
            return _json_response(method, url, [{"hash": expected_hash, "added_on": 1}])
        if method == "POST" and url.endswith("/torrents/add"):
            return _text_response(method, url, "Ok.")
        raise AssertionError(f"unexpected request: {method} {url} {payload}")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient(dispatcher, **kwargs))

    client = QbittorrentClient(base_url="http://qb:8080", username="user", password="pass")
    task = asyncio.run(client.add_torrent(f"magnet:?xt=urn:btih:{magnet_hash}", "/data/downloads/qb"))

    assert task.task_id == expected_hash
    assert task.task_hash == expected_hash


def test_add_torrent_resolves_new_hash_from_after_diff(monkeypatch: pytest.MonkeyPatch) -> None:
    list_calls = 0

    def dispatcher(method: str, url: str, payload: dict[str, object]) -> httpx.Response:
        nonlocal list_calls
        if url.endswith("/auth/login"):
            return _text_response(method, url, "Ok.")
        if method == "GET" and url.endswith("/torrents/info"):
            list_calls += 1
            if list_calls == 1:
                return _json_response(method, url, [{"hash": "oldhash", "added_on": 1}])
            return _json_response(
                method,
                url,
                [
                    {"hash": "newhash", "added_on": 2},
                    {"hash": "oldhash", "added_on": 1},
                ],
            )
        if method == "POST" and url.endswith("/torrents/add"):
            return _text_response(method, url, "Ok.")
        raise AssertionError(f"unexpected request: {method} {url} {payload}")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient(dispatcher, **kwargs))

    client = QbittorrentClient(base_url="http://qb:8080", username="user", password="pass")
    task = asyncio.run(client.add_torrent("https://example.com/dune.torrent", "/data/downloads/qb"))

    assert task.task_id == "newhash"
    assert task.task_hash == "newhash"


def test_get_torrent_status_maps_qb_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    def dispatcher(method: str, url: str, payload: dict[str, object]) -> httpx.Response:
        if url.endswith("/auth/login"):
            return _text_response(method, url, "Ok.")
        if method == "GET" and url.endswith("/torrents/info"):
            assert payload["hashes"] == "hash-42"
            return _json_response(
                method,
                url,
                [
                    {
                        "hash": "hash-42",
                        "name": "Dune 2021",
                        "state": "downloading",
                        "progress": 0.5,
                        "dlspeed": 2048,
                        "eta": 60,
                    }
                ],
            )
        raise AssertionError(f"unexpected request: {method} {url} {payload}")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient(dispatcher, **kwargs))

    client = QbittorrentClient(base_url="http://qb:8080", username="user", password="pass")
    status = asyncio.run(client.get_torrent_status("hash-42"))

    assert status is not None
    assert status.task_id == "hash-42"
    assert status.task_hash == "hash-42"
    assert status.name == "Dune 2021"
    assert status.status_code == 4
    assert status.percent_done == 0.5
    assert status.rate_download == 2048
    assert status.eta_seconds == 60


def test_get_torrent_import_source_maps_qb_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    def dispatcher(method: str, url: str, payload: dict[str, object]) -> httpx.Response:
        if url.endswith("/auth/login"):
            return _text_response(method, url, "Ok.")
        if method == "GET" and url.endswith("/torrents/info"):
            return _json_response(
                method,
                url,
                [
                    {
                        "hash": "hash-99",
                        "name": "Dune 2021",
                        "state": "uploading",
                        "progress": 1.0,
                        "save_path": "/data/downloads/qb",
                    }
                ],
            )
        raise AssertionError(f"unexpected request: {method} {url} {payload}")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient(dispatcher, **kwargs))

    client = QbittorrentClient(base_url="http://qb:8080", username="user", password="pass")
    source = asyncio.run(client.get_torrent_import_source("hash-99"))

    assert source is not None
    assert source.task_id == "hash-99"
    assert source.task_hash == "hash-99"
    assert source.name == "Dune 2021"
    assert source.download_dir == "/data/downloads/qb"
    assert source.is_finished is True
    assert source.percent_done == 1.0


def test_remove_torrent_calls_delete_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str, dict[str, object]]] = []

    def dispatcher(method: str, url: str, payload: dict[str, object]) -> httpx.Response:
        calls.append((method, url, payload))
        if url.endswith("/auth/login"):
            return _text_response(method, url, "Ok.")
        if method == "POST" and url.endswith("/torrents/delete"):
            return _text_response(method, url, "")
        raise AssertionError(f"unexpected request: {method} {url} {payload}")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient(dispatcher, **kwargs))

    client = QbittorrentClient(base_url="http://qb:8080", username="user", password="pass")
    asyncio.run(client.remove_torrent("hash-99", delete_local_data=True))

    assert calls[1] == (
        "POST",
        "http://qb:8080/api/v2/torrents/delete",
        {"hashes": "hash-99", "deleteFiles": "true"},
    )

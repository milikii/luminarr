from __future__ import annotations

import asyncio
import json
from collections.abc import Callable

import httpx
import pytest

from app.clients.feishu import FeishuClient, FeishuClientError


class FakeAsyncClient:
    def __init__(self, dispatcher: Callable[..., httpx.Response], **_: object) -> None:
        self._dispatcher = dispatcher

    async def __aenter__(self) -> FakeAsyncClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(
        self,
        url: str,
        *,
        params: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
        json: dict[str, object] | None = None,
    ) -> httpx.Response:
        return self._dispatcher(url, params or {}, headers or {}, json or {})


def _json_response(url: str, payload: object, status_code: int = 200) -> httpx.Response:
    return httpx.Response(status_code, json=payload, request=httpx.Request("POST", url))


def test_send_private_text_requests_token_then_message(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, dict[str, object], dict[str, str], dict[str, object]]] = []

    def dispatcher(
        url: str,
        params: dict[str, object],
        headers: dict[str, str],
        payload: dict[str, object],
    ) -> httpx.Response:
        calls.append((url, params, headers, payload))
        if url.endswith("/auth/v3/tenant_access_token/internal"):
            return _json_response(
                url,
                {
                    "code": 0,
                    "tenant_access_token": "tenant-token",
                    "expire": 7200,
                },
            )
        if url.endswith("/im/v1/messages"):
            return _json_response(
                url,
                {
                    "code": 0,
                    "msg": "success",
                    "data": {"message_id": "om_reply_1"},
                },
            )
        raise AssertionError(f"unexpected request: {url}")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient(dispatcher, **kwargs))

    client = FeishuClient(app_id="cli_a", app_secret="sec_b", base_url="https://open.feishu.test")
    message_id = asyncio.run(client.send_private_text(chat_id="oc_feishu_chat_1", text="搜索结果：dune"))

    assert message_id == "om_reply_1"
    assert calls[0][3] == {"app_id": "cli_a", "app_secret": "sec_b"}
    assert calls[1][1] == {"receive_id_type": "chat_id"}
    assert calls[1][2]["Authorization"] == "Bearer tenant-token"
    assert calls[1][3]["receive_id"] == "oc_feishu_chat_1"
    assert calls[1][3]["msg_type"] == "text"
    assert json.loads(str(calls[1][3]["content"])) == {"text": "搜索结果：dune"}


def test_send_private_text_raises_when_feishu_returns_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def dispatcher(
        url: str,
        params: dict[str, object],
        headers: dict[str, str],
        payload: dict[str, object],
    ) -> httpx.Response:
        if url.endswith("/auth/v3/tenant_access_token/internal"):
            return _json_response(
                url,
                {
                    "code": 0,
                    "tenant_access_token": "tenant-token",
                    "expire": 7200,
                },
            )
        if url.endswith("/im/v1/messages"):
            return _json_response(url, {"code": 9999, "msg": "permission denied"}, status_code=403)
        raise AssertionError(f"unexpected request: {url}")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient(dispatcher, **kwargs))

    client = FeishuClient(app_id="cli_a", app_secret="sec_b", base_url="https://open.feishu.test")
    with pytest.raises(FeishuClientError):
        asyncio.run(client.send_private_text(chat_id="oc_feishu_chat_1", text="搜索结果：dune"))

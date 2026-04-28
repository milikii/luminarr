from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest

from app.services.refresh_media_server import (
    REFRESH_FAILED_TEXT_TEMPLATE,
    REFRESH_FAILED_UNKNOWN_REASON,
    REFRESH_SUCCESS_TEXT,
    RefreshMediaServerService,
)


def test_refresh_text_success() -> None:
    refresh = AsyncMock(return_value=None)
    service = RefreshMediaServerService(refresh)

    text = asyncio.run(service.refresh_text())
    assert text == REFRESH_SUCCESS_TEXT
    refresh.assert_awaited_once()


def test_refresh_text_failure_with_reason(capsys) -> None:
    request = httpx.Request("POST", "http://127.0.0.1:8096/Library/Refresh")
    refresh = AsyncMock(side_effect=httpx.ConnectError("connection timeout", request=request))
    service = RefreshMediaServerService(
        refresh,
        provider_name="jellyfin",
        target_url="http://127.0.0.1:8096",
    )

    text = asyncio.run(service.refresh_text())
    assert text == REFRESH_FAILED_TEXT_TEMPLATE.format(reason="connection timeout")
    output = capsys.readouterr().out
    assert "[媒体库刷新失败]" in output
    assert "provider=jellyfin" in output
    assert "target=http://127.0.0.1:8096" in output
    assert "connection timeout" in output
    assert "[处理建议]" in output


def test_refresh_text_failure_with_unknown_reason(capsys) -> None:
    request = httpx.Request("GET", "http://127.0.0.1:32400/library/sections/all/refresh")
    refresh = AsyncMock(side_effect=httpx.ConnectError("", request=request))
    service = RefreshMediaServerService(
        refresh,
        provider_name="plex",
        target_url="http://127.0.0.1:32400",
    )

    text = asyncio.run(service.refresh_text())
    assert text == REFRESH_FAILED_TEXT_TEMPLATE.format(reason=REFRESH_FAILED_UNKNOWN_REASON)
    output = capsys.readouterr().out
    assert "[媒体库刷新失败]" in output
    assert "provider=plex" in output
    assert "target=http://127.0.0.1:32400" in output
    assert REFRESH_FAILED_UNKNOWN_REASON in output
    assert "[处理建议]" in output


def test_refresh_text_logs_request_url_for_httpx_error(capsys) -> None:
    request = httpx.Request("POST", "http://127.0.0.1:8096/Library/Refresh")
    refresh = AsyncMock(side_effect=httpx.ConnectError("connection refused", request=request))
    service = RefreshMediaServerService(
        refresh,
        provider_name="jellyfin",
        target_url="http://127.0.0.1:8096",
    )

    text = asyncio.run(service.refresh_text())
    assert text == REFRESH_FAILED_TEXT_TEMPLATE.format(reason="connection refused")
    output = capsys.readouterr().out
    assert "provider=jellyfin" in output
    assert "target=http://127.0.0.1:8096" in output
    assert "request_url=http://127.0.0.1:8096/Library/Refresh" in output


def test_refresh_text_re_raises_non_http_error() -> None:
    refresh = AsyncMock(side_effect=RuntimeError("unexpected callback bug"))
    service = RefreshMediaServerService(refresh)

    with pytest.raises(RuntimeError, match="unexpected callback bug"):
        asyncio.run(service.refresh_text())

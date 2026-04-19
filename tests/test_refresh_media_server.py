from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

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
    refresh = AsyncMock(side_effect=RuntimeError("connection timeout"))
    service = RefreshMediaServerService(refresh, provider_name="jellyfin")

    text = asyncio.run(service.refresh_text())
    assert text == REFRESH_FAILED_TEXT_TEMPLATE.format(reason="connection timeout")
    output = capsys.readouterr().out
    assert "[媒体库刷新失败]" in output
    assert "provider=jellyfin" in output
    assert "connection timeout" in output
    assert "[处理建议]" in output


def test_refresh_text_failure_with_unknown_reason(capsys) -> None:
    refresh = AsyncMock(side_effect=RuntimeError(""))
    service = RefreshMediaServerService(refresh, provider_name="plex")

    text = asyncio.run(service.refresh_text())
    assert text == REFRESH_FAILED_TEXT_TEMPLATE.format(reason=REFRESH_FAILED_UNKNOWN_REASON)
    output = capsys.readouterr().out
    assert "[媒体库刷新失败]" in output
    assert "provider=plex" in output
    assert REFRESH_FAILED_UNKNOWN_REASON in output
    assert "[处理建议]" in output

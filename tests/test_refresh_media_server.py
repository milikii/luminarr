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


def test_refresh_text_failure_with_reason() -> None:
    refresh = AsyncMock(side_effect=RuntimeError("connection timeout"))
    service = RefreshMediaServerService(refresh)

    text = asyncio.run(service.refresh_text())
    assert text == REFRESH_FAILED_TEXT_TEMPLATE.format(reason="connection timeout")


def test_refresh_text_failure_with_unknown_reason() -> None:
    refresh = AsyncMock(side_effect=RuntimeError(""))
    service = RefreshMediaServerService(refresh)

    text = asyncio.run(service.refresh_text())
    assert text == REFRESH_FAILED_TEXT_TEMPLATE.format(reason=REFRESH_FAILED_UNKNOWN_REASON)

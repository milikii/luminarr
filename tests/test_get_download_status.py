from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from unittest.mock import AsyncMock

from app.clients.transmission import TransmissionTaskStatus
from app.services.get_download_status import (
    STATUS_NOT_FOUND_TEXT,
    STATUS_QUERY_FAILED_TEXT,
    STATUS_QUERY_USAGE_TEXT,
    GetDownloadStatusService,
    parse_status_query,
)


def test_parse_status_query_supports_status_prefix() -> None:
    assert parse_status_query("status 87") == "87"
    assert parse_status_query("STATUS abc123") == "abc123"
    assert parse_status_query("状态 b305bf") == "b305bf"
    assert parse_status_query("status") == ""


def test_parse_status_query_rejects_non_status_text() -> None:
    assert parse_status_query("dune") is None
    assert parse_status_query("1") is None


def test_get_status_text_success() -> None:
    get_status = AsyncMock(
        return_value=TransmissionTaskStatus(
            task_id="87",
            task_hash="b305bf",
            name="Dune 1984",
            status_code=4,
            percent_done=0.56,
            rate_download=1048576,
            eta_seconds=121,
        )
    )
    service = GetDownloadStatusService(get_status)

    text = _run(service.get_status_text("87"))
    assert "任务 ID: 87" in text
    assert "任务 Hash: b305bf" in text
    assert "状态: 下载中" in text
    assert "进度: 56.0%" in text
    assert "下载速度: 1.0 MB/s" in text
    assert "预计剩余: 02:01" in text


def test_get_status_text_not_found() -> None:
    service = GetDownloadStatusService(AsyncMock(return_value=None))
    text = _run(service.get_status_text("missing"))
    assert text == STATUS_NOT_FOUND_TEXT


def test_get_status_text_handles_query_error() -> None:
    service = GetDownloadStatusService(AsyncMock(side_effect=RuntimeError("boom")))
    text = _run(service.get_status_text("87"))
    assert text == STATUS_QUERY_FAILED_TEXT


def test_get_status_text_handles_empty_ref() -> None:
    service = GetDownloadStatusService(AsyncMock())
    text = _run(service.get_status_text("   "))
    assert text == STATUS_QUERY_USAGE_TEXT


def _run(coroutine: Awaitable[str]) -> str:
    return asyncio.run(coroutine)

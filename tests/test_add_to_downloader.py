from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from unittest.mock import AsyncMock

from app.clients.transmission import TransmissionTask
from app.services.add_to_downloader import (
    ADD_APPROVAL_PENDING_TEXT,
    ADD_CONFIRM_NOT_PENDING_TEXT,
    ADD_FAILED_TEXT,
    CANDIDATE_SOURCE_MISSING_TEXT,
    SELECT_NOT_FOUND_TEXT,
    SELECT_OUT_OF_RANGE_TEXT,
    SELECT_USAGE_TEXT,
    AddToDownloaderService,
)
from app.services.search_media import SearchMediaService


async def _fake_search_with_download_url(query: str) -> list[dict[str, object]]:
    assert query == "dune"
    return [
        {
            "title": "Dune: Part Two",
            "downloadUrl": "https://example.com/dune.torrent",
        }
    ]


async def _fake_search_without_source(query: str) -> list[dict[str, object]]:
    assert query == "dune"
    return [{"title": "Dune: Part Two"}]


def test_add_by_selection_returns_pending_approval() -> None:
    search_service = SearchMediaService(_fake_search_with_download_url)
    _run(search_service.search_and_format("dune", chat_id=1001))

    add_torrent = AsyncMock(return_value=TransmissionTask(task_id="42", task_hash="abc123"))
    service = AddToDownloaderService(search_service=search_service, add_torrent_func=add_torrent)

    reply = _run(service.add_by_selection(1001, "1"))

    assert reply == ADD_APPROVAL_PENDING_TEXT.format(title="Dune: Part Two", task_ref="1")
    add_torrent.assert_not_awaited()


def test_confirm_add_by_task_ref_dispatches_download() -> None:
    search_service = SearchMediaService(_fake_search_with_download_url)
    _run(search_service.search_and_format("dune", chat_id=1001))

    add_torrent = AsyncMock(return_value=TransmissionTask(task_id="42", task_hash="abc123"))
    service = AddToDownloaderService(search_service=search_service, add_torrent_func=add_torrent)

    pending_reply = _run(service.add_by_selection(1001, "1"))
    confirm_reply = _run(service.confirm_add_by_task_ref("1", chat_id=1001))

    assert pending_reply == ADD_APPROVAL_PENDING_TEXT.format(title="Dune: Part Two", task_ref="1")
    assert "任务 ID: 42" in confirm_reply
    assert "任务 Hash: abc123" in confirm_reply
    add_torrent.assert_awaited_once_with("https://example.com/dune.torrent")


def test_confirm_add_by_task_ref_without_pending_request_returns_not_pending() -> None:
    service = AddToDownloaderService(
        search_service=SearchMediaService(_fake_search_with_download_url),
        add_torrent_func=AsyncMock(),
    )

    reply = _run(service.confirm_add_by_task_ref("1", chat_id=1001))

    assert reply == ADD_CONFIRM_NOT_PENDING_TEXT


def test_add_by_selection_without_cached_candidates() -> None:
    search_service = SearchMediaService(_fake_search_with_download_url)
    add_torrent = AsyncMock()
    service = AddToDownloaderService(search_service=search_service, add_torrent_func=add_torrent)

    reply = _run(service.add_by_selection(1001, "1"))
    assert reply == SELECT_NOT_FOUND_TEXT
    add_torrent.assert_not_called()


def test_add_by_selection_out_of_range() -> None:
    search_service = SearchMediaService(_fake_search_with_download_url)
    _run(search_service.search_and_format("dune", chat_id=1001))
    add_torrent = AsyncMock()
    service = AddToDownloaderService(search_service=search_service, add_torrent_func=add_torrent)

    reply = _run(service.add_by_selection(1001, "2"))
    assert reply == SELECT_OUT_OF_RANGE_TEXT
    add_torrent.assert_not_called()


def test_add_by_selection_invalid_index() -> None:
    search_service = SearchMediaService(_fake_search_with_download_url)
    add_torrent = AsyncMock()
    service = AddToDownloaderService(search_service=search_service, add_torrent_func=add_torrent)

    reply = _run(service.add_by_selection(1001, "x"))
    assert reply == SELECT_USAGE_TEXT
    add_torrent.assert_not_called()


def test_add_by_selection_missing_source() -> None:
    search_service = SearchMediaService(_fake_search_without_source)
    _run(search_service.search_and_format("dune", chat_id=1001))
    add_torrent = AsyncMock()
    service = AddToDownloaderService(search_service=search_service, add_torrent_func=add_torrent)

    reply = _run(service.add_by_selection(1001, "1"))
    assert reply == CANDIDATE_SOURCE_MISSING_TEXT
    add_torrent.assert_not_called()


def test_confirm_add_by_task_ref_returns_failed_when_downloader_errors() -> None:
    search_service = SearchMediaService(_fake_search_with_download_url)
    _run(search_service.search_and_format("dune", chat_id=1001))
    add_torrent = AsyncMock(side_effect=RuntimeError("boom"))
    service = AddToDownloaderService(search_service=search_service, add_torrent_func=add_torrent)

    _run(service.add_by_selection(1001, "1"))
    reply = _run(service.confirm_add_by_task_ref("1", chat_id=1001))

    assert reply == ADD_FAILED_TEXT


def _run(coroutine: Awaitable[str]) -> str:
    return asyncio.run(coroutine)

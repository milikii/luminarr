from __future__ import annotations

import asyncio

import pytest

from app.services.search_media_batch_preview_support import (
    UnsupportedBatchPreviewPageUrl,
    search_bt_batch_preview_candidates,
    search_raw_page_candidates,
)


async def _fake_raw_search(query: str):
    return [{"title": f"raw:{query}"}]


async def _fake_raw_page_search(page_url: str):
    return [{"title": f"page:{page_url}"}]


def _prepare_raw_candidates(raw_results, query):  # noqa: ANN001
    return tuple({**item, "query": query} for item in raw_results)


def test_search_bt_batch_preview_candidates_uses_raw_search_for_plain_query() -> None:
    results = asyncio.run(
        search_bt_batch_preview_candidates(
            "dune",
            raw_search_func=_fake_raw_search,
            raw_page_search_func=_fake_raw_page_search,
            prepare_raw_candidates=_prepare_raw_candidates,
        )
    )

    assert results == ({"title": "raw:dune", "query": "dune"},)


def test_search_raw_page_candidates_uses_page_fetch_and_preparation() -> None:
    results = asyncio.run(
        search_raw_page_candidates(
            "https://example.com/list",
            raw_page_search_func=_fake_raw_page_search,
            prepare_raw_candidates=_prepare_raw_candidates,
        )
    )

    assert results == ({"title": "page:https://example.com/list", "query": "https://example.com/list"},)


def test_search_bt_batch_preview_candidates_rejects_unsupported_page_url() -> None:
    with pytest.raises(UnsupportedBatchPreviewPageUrl):
        asyncio.run(
            search_bt_batch_preview_candidates(
                "https://example.com/list",
                raw_search_func=_fake_raw_search,
                raw_page_search_func=None,
                prepare_raw_candidates=_prepare_raw_candidates,
            )
        )

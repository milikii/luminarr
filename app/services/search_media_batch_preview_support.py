from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

from app.clients.web_source import (
    looks_like_http_url,
    looks_like_web_source_page_request,
    resolve_supported_web_source_page_request,
)

BatchPreviewSearchFunc = Callable[[str], Awaitable[Sequence[Mapping[str, Any]]]]
PrepareRawCandidatesFunc = Callable[[Sequence[Mapping[str, Any]], str], Sequence[Mapping[str, Any]]]


class UnsupportedBatchPreviewPageUrl(ValueError):
    pass


async def search_bt_batch_preview_candidates(
    query: str,
    *,
    raw_search_func: BatchPreviewSearchFunc,
    raw_page_search_func: BatchPreviewSearchFunc | None,
    prepare_raw_candidates: PrepareRawCandidatesFunc,
) -> Sequence[Mapping[str, Any]]:
    resolved_page_url = resolve_supported_web_source_page_request(query)
    if resolved_page_url is not None:
        if raw_page_search_func is None:
            raise UnsupportedBatchPreviewPageUrl(query)
        return await search_raw_page_candidates(
            resolved_page_url,
            raw_page_search_func=raw_page_search_func,
            prepare_raw_candidates=prepare_raw_candidates,
        )
    if looks_like_http_url(query) or looks_like_web_source_page_request(query):
        raise UnsupportedBatchPreviewPageUrl(query)
    raw_results = await raw_search_func(query)
    return tuple(prepare_raw_candidates(raw_results, query=query))


async def search_raw_page_candidates(
    page_url: str,
    *,
    raw_page_search_func: BatchPreviewSearchFunc | None,
    prepare_raw_candidates: PrepareRawCandidatesFunc,
) -> Sequence[Mapping[str, Any]]:
    cleaned_page_url = page_url.strip()
    if not cleaned_page_url:
        return ()
    if raw_page_search_func is None:
        raise UnsupportedBatchPreviewPageUrl(cleaned_page_url)
    try:
        raw_results = await raw_page_search_func(cleaned_page_url)
    except UnsupportedBatchPreviewPageUrl:
        raise
    except Exception as error:
        print(
            f"\033[31m[BT 页面预览失败]\033[0m 页面={cleaned_page_url} 错误={error}\n"
            "\033[33m[处理建议]\033[0m 检查页面 URL 是否仍在 allowlist 内、站点是否可达，以及 HTML 结构是否变化后重试。",
            flush=True,
        )
        raise
    return tuple(prepare_raw_candidates(raw_results, query=cleaned_page_url))

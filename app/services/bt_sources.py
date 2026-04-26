from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.clients.web_source import UnsupportedWebSourcePageError
from app.services.adult_content import extract_exact_adult_content_match
from app.services.media_name_parser import parse_media_name

BtSourceSearchFunc = Callable[[str], Awaitable[Sequence[Mapping[str, Any]]]]

_SOURCE_KEYS = ("source", "downloadUrl", "downloadurl", "magnetUrl", "magneturl", "guid", "link", "url")
_INFO_HASH_KEYS = ("infoHash", "infohash", "torrentHash", "torrenthash", "hash")
_MAGNET_INFO_HASH_PATTERN = re.compile(r"xt=urn:btih:([0-9a-z]{32,40})", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class BtSourceProvider:
    name: str
    search_func: BtSourceSearchFunc
    page_search_func: BtSourceSearchFunc | None = None


class BtSourceAdapter:
    def __init__(self, providers: Sequence[BtSourceProvider]) -> None:
        self._providers = tuple(
            BtSourceProvider(
                name=provider.name.strip(),
                search_func=provider.search_func,
                page_search_func=provider.page_search_func,
            )
            for provider in providers
            if provider.name.strip()
        )

    async def search(self, query: str) -> list[dict[str, Any]]:
        cleaned_query = query.strip()
        if not cleaned_query or not self._providers:
            return []

        merged_results: list[dict[str, Any]] = []
        seen_keys: set[str] = set()
        last_error: Exception | None = None
        for provider in self._providers:
            try:
                raw_results = await provider.search_func(cleaned_query)
            except Exception as error:
                last_error = error
                _log_bt_source_provider_error(provider_name=provider.name, query=cleaned_query, error=error)
                continue
            for index, candidate in enumerate(raw_results):
                normalized_candidate = normalize_bt_candidate(
                    candidate,
                    provider_name=provider.name,
                    provider_index=index,
                )
                if normalized_candidate is None:
                    continue
                dedupe_key = build_bt_candidate_dedupe_key(normalized_candidate)
                if dedupe_key in seen_keys:
                    continue
                seen_keys.add(dedupe_key)
                merged_results.append(normalized_candidate)
        if merged_results or last_error is None:
            return merged_results
        raise last_error

    async def search_page(self, page_url: str) -> list[dict[str, Any]]:
        cleaned_page_url = page_url.strip()
        if not cleaned_page_url or not self._providers:
            return []

        merged_results: list[dict[str, Any]] = []
        seen_keys: set[str] = set()
        last_error: Exception | None = None
        matched_provider = False
        for provider in self._providers:
            if provider.page_search_func is None:
                continue
            try:
                raw_results = await provider.page_search_func(cleaned_page_url)
            except UnsupportedWebSourcePageError:
                continue
            except Exception as error:
                matched_provider = True
                last_error = error
                _log_bt_source_provider_page_error(provider_name=provider.name, page_url=cleaned_page_url, error=error)
                continue
            matched_provider = True
            for index, candidate in enumerate(raw_results):
                normalized_candidate = normalize_bt_candidate(
                    candidate,
                    provider_name=provider.name,
                    provider_index=index,
                )
                if normalized_candidate is None:
                    continue
                dedupe_key = build_bt_candidate_dedupe_key(normalized_candidate)
                if dedupe_key in seen_keys:
                    continue
                seen_keys.add(dedupe_key)
                merged_results.append(normalized_candidate)
        if merged_results or (matched_provider and last_error is None):
            return merged_results
        if not matched_provider:
            raise UnsupportedWebSourcePageError(cleaned_page_url)
        raise last_error


def normalize_bt_candidate(
    candidate: Mapping[str, Any],
    *,
    provider_name: str,
    provider_index: int,
) -> dict[str, Any] | None:
    title = str(candidate.get("title", "")).strip()
    source = resolve_bt_source(candidate)
    if not title or not source:
        return None

    normalized_candidate = dict(candidate.items())
    normalized_candidate["title"] = title
    normalized_candidate["source"] = source
    normalized_candidate["seeders"] = _safe_int(candidate.get("seeders"))
    normalized_candidate["size"] = _safe_int(candidate.get("size"))
    normalized_candidate["sourceProvider"] = provider_name.strip() or "unknown"
    normalized_candidate["providerIndex"] = provider_index
    normalized_candidate["parsedMediaName"] = parse_media_name(title)
    adult_content_match = extract_exact_adult_content_match(title, source_site=provider_name)
    if adult_content_match is not None:
        normalized_candidate["adult_content_id"] = adult_content_match.normalized_content_id
        normalized_candidate["adult_archive_category"] = adult_content_match.archive_category
        normalized_candidate["adult_content_kind"] = adult_content_match.source_kind
        normalized_candidate["adult_display_id"] = adult_content_match.display_id

    indexer_name = _resolve_indexer_name(candidate, default=normalized_candidate["sourceProvider"])
    if indexer_name:
        normalized_candidate["indexerName"] = indexer_name

    info_hash = resolve_bt_info_hash(candidate, source=source)
    if info_hash:
        normalized_candidate["infoHash"] = info_hash

    if source.lower().startswith("magnet:?"):
        normalized_candidate.setdefault("magnetUrl", source)
    else:
        normalized_candidate.setdefault("downloadUrl", source)

    return normalized_candidate


def build_bt_candidate_dedupe_key(candidate: Mapping[str, Any]) -> str:
    info_hash = resolve_bt_info_hash(candidate)
    if info_hash:
        return f"info_hash:{info_hash}"
    source = resolve_bt_source(candidate)
    return f"source:{source.lower()}"


def resolve_bt_source(candidate: Mapping[str, Any]) -> str:
    for key in _SOURCE_KEYS:
        value = candidate.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def resolve_bt_info_hash(candidate: Mapping[str, Any], *, source: str = "") -> str:
    for key in _INFO_HASH_KEYS:
        value = candidate.get(key)
        if value is None:
            continue
        text = str(value).strip().lower()
        if text:
            return text

    resolved_source = source.strip() or resolve_bt_source(candidate)
    if not resolved_source:
        return ""
    matched = _MAGNET_INFO_HASH_PATTERN.search(resolved_source)
    if matched is None:
        return ""
    return str(matched.group(1) or "").strip().lower()


def _resolve_indexer_name(candidate: Mapping[str, Any], *, default: str) -> str:
    indexer_name = str(candidate.get("indexerName", "")).strip()
    if indexer_name:
        return indexer_name

    indexer = candidate.get("indexer")
    if isinstance(indexer, Mapping):
        nested_name = str(indexer.get("name", "")).strip()
        if nested_name:
            return nested_name
    elif indexer is not None:
        text = str(indexer).strip()
        if text:
            return text

    return default.strip()


def _safe_int(value: Any) -> int:
    try:
        resolved = int(value)
    except (TypeError, ValueError):
        return 0
    if resolved > 0:
        return resolved
    return 0


def _log_bt_source_provider_error(*, provider_name: str, query: str, error: Exception) -> None:
    print(
        f"\033[31m[BT 来源搜索失败]\033[0m 来源={provider_name} 查询={query} 原因={error}\n"
        "\033[33m[处理建议]\033[0m 检查对应来源配置、站点可达性和网络连通性后重试。"
    )


def _log_bt_source_provider_page_error(*, provider_name: str, page_url: str, error: Exception) -> None:
    print(
        f"\033[31m[BT 页面预览失败]\033[0m 来源={provider_name} 页面={page_url} 原因={error}\n"
        "\033[33m[处理建议]\033[0m 检查页面 URL 是否仍在 allowlist 内、站点是否可达，以及 HTML 结构是否变化后重试。"
    )

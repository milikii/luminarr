from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

SearchFunc = Callable[[str], Awaitable[Sequence[Mapping[str, Any]]]]

EMPTY_QUERY_TEXT = "请输入要搜索的内容。"
NO_RESULT_TEXT_TEMPLATE = "未找到候选结果：{query}"


@dataclass(frozen=True, slots=True)
class Candidate:
    title: str
    year: str
    quality: str
    size: str
    indexer: str


class SearchMediaService:
    def __init__(self, search_func: SearchFunc, limit: int = 5) -> None:
        self._search_func = search_func
        self._limit = max(1, limit)
        self._recent_candidates_by_chat: dict[int, list[dict[str, Any]]] = {}

    async def search_and_format(self, query: str, chat_id: int | None = None) -> str:
        cleaned_query = query.strip()
        if not cleaned_query:
            return EMPTY_QUERY_TEXT

        raw_results = await self._search_func(cleaned_query)
        selected_raw_results = [_to_candidate_dict(item) for item in raw_results[: self._limit]]
        if chat_id is not None:
            self._recent_candidates_by_chat[chat_id] = selected_raw_results

        candidates = [normalize_candidate(item) for item in selected_raw_results]
        return format_candidates(cleaned_query, candidates)

    def get_cached_candidate(self, chat_id: int, index: int) -> Mapping[str, Any] | None:
        if index < 1:
            return None
        candidates = self._recent_candidates_by_chat.get(chat_id)
        if not candidates:
            return None
        resolved_index = index - 1
        if resolved_index >= len(candidates):
            return None
        return candidates[resolved_index]


def normalize_candidate(item: Mapping[str, Any]) -> Candidate:
    title = _safe_text(item.get("title"), default="(no title)")
    year = _safe_year(item.get("year"))
    quality = _safe_text(item.get("quality"), default="-")
    if quality == "-" and "resolution" in item:
        quality = _safe_text(item.get("resolution"), default="-")
    if quality == "-":
        quality = _guess_quality_from_title(title)
    size = _format_size(item.get("size"))
    indexer = _safe_indexer(item.get("indexer"), item.get("indexerName"))
    return Candidate(title=title, year=year, quality=quality, size=size, indexer=indexer)


def format_candidates(query: str, candidates: Sequence[Candidate]) -> str:
    if not candidates:
        return NO_RESULT_TEXT_TEMPLATE.format(query=query)

    lines = [f"搜索结果：{query}"]
    for i, item in enumerate(candidates, start=1):
        lines.append(f"{i}. {item.title} ({item.year})")
        lines.append(f"   画质: {item.quality} | 大小: {item.size} | 站点: {item.indexer}")
    return "\n".join(lines)


def _safe_text(value: Any, default: str) -> str:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    return text


def _safe_year(value: Any) -> str:
    if value is None:
        return "-"
    text = str(value).strip()
    if not text:
        return "-"
    return text


def _safe_indexer(indexer_value: Any, indexer_name_value: Any) -> str:
    if isinstance(indexer_value, Mapping):
        mapped_name = _safe_text(indexer_value.get("name"), default="-")
        if mapped_name != "-":
            return mapped_name

    name = _safe_text(indexer_name_value, default="-")
    if name != "-":
        return name
    return _safe_text(indexer_value, default="-")


def _format_size(size_value: Any) -> str:
    if size_value is None:
        return "-"

    try:
        bytes_value = int(size_value)
    except (TypeError, ValueError):
        return "-"

    if bytes_value <= 0:
        return "-"

    units = ("B", "KB", "MB", "GB", "TB")
    size = float(bytes_value)
    unit_index = 0
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    return f"{size:.1f} {units[unit_index]}"


def _guess_quality_from_title(title: str) -> str:
    resolution_match = re.search(r"\b(2160p|1080p|720p|480p|4k)\b", title, flags=re.IGNORECASE)
    source_match = re.search(
        r"\b(web[- ]dl|webrip|bluray|remux|hdtv|dvdrip|bdrip)\b",
        title,
        flags=re.IGNORECASE,
    )
    if not resolution_match and not source_match:
        return "-"

    resolution = "-"
    if resolution_match:
        raw_resolution = resolution_match.group(1)
        resolution = "4K" if raw_resolution.lower() == "4k" else raw_resolution.lower()

    if not source_match:
        return resolution

    source_raw = source_match.group(1).lower().replace(" ", "-")
    source_map = {
        "web-dl": "WEB-DL",
        "webrip": "WEBRip",
        "bluray": "BluRay",
        "remux": "Remux",
        "hdtv": "HDTV",
        "dvdrip": "DVDRip",
        "bdrip": "BDRip",
    }
    source = source_map.get(source_raw, source_raw.upper())
    if resolution == "-":
        return source
    return f"{resolution} {source}"


def _to_candidate_dict(item: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): value for key, value in item.items()}

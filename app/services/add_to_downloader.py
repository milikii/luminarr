from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from app.clients.transmission import TransmissionTask
from app.services.search_media import SearchMediaService

AddTorrentFunc = Callable[[str], Awaitable[TransmissionTask]]

SELECT_USAGE_TEXT = "请输入要选择的序号，例如：1"
SELECT_NOT_FOUND_TEXT = "没有可用的候选结果，请先发一条搜索请求。"
SELECT_OUT_OF_RANGE_TEXT = "序号超出范围，请按搜索结果里的序号重试。"
CANDIDATE_SOURCE_MISSING_TEXT = "该候选缺少可下载链接，请换一个序号。"
ADD_FAILED_TEXT = "下载投递失败，请稍后重试。"


@dataclass(frozen=True, slots=True)
class AddResult:
    task_id: str
    task_hash: str
    title: str


class AddToDownloaderService:
    def __init__(self, search_service: SearchMediaService, add_torrent_func: AddTorrentFunc) -> None:
        self._search_service = search_service
        self._add_torrent_func = add_torrent_func

    async def add_by_selection(self, chat_id: int, selection_text: str) -> str:
        index = _parse_selection_index(selection_text)
        if index is None:
            return SELECT_USAGE_TEXT

        candidate = self._search_service.get_cached_candidate(chat_id, index)
        if candidate is None:
            if self._search_service.get_cached_candidate(chat_id, 1) is None:
                return SELECT_NOT_FOUND_TEXT
            return SELECT_OUT_OF_RANGE_TEXT

        source = _resolve_source(candidate)
        if not source:
            return CANDIDATE_SOURCE_MISSING_TEXT

        try:
            task = await self._add_torrent_func(source)
        except Exception:
            return ADD_FAILED_TEXT

        title = str(candidate.get("title", "")).strip() or "(no title)"
        result = AddResult(task_id=task.task_id, task_hash=task.task_hash, title=title)
        return (
            f"已添加下载：{result.title}\n"
            f"任务 ID: {result.task_id}\n"
            f"任务 Hash: {result.task_hash}"
        )


def _parse_selection_index(text: str) -> int | None:
    cleaned = text.strip()
    if not cleaned.isdigit():
        return None
    value = int(cleaned)
    if value <= 0:
        return None
    return value


def _resolve_source(candidate: Mapping[str, Any]) -> str:
    for key in ("downloadUrl", "downloadurl", "magnetUrl", "magneturl", "guid"):
        value = candidate.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""

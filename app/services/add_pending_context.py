from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.services.media_identity import normalize_media_identity_payload
from app.services.bt_sources import resolve_bt_source
from app.services.search_media import SearchMediaService

SELECT_USAGE_TEXT = "请输入要选择的序号，例如：1"
SELECT_NOT_FOUND_TEXT = "没有可用的候选结果，请先发一条搜索请求。"
SELECT_OUT_OF_RANGE_TEXT = "序号超出范围，请按搜索结果里的序号重试。"
SELECT_LOOKUP_FAILED_TEXT = "搜索候选读取失败，请稍后重试。"
CANDIDATE_SOURCE_MISSING_TEXT = "该候选缺少可下载链接，请换一个序号。"


@dataclass(frozen=True, slots=True)
class PendingAddContext:
    task_ref: str
    task_id: str
    task_hash: str
    title: str
    source: str
    media_identity: dict[str, str] | None = None
    downloader_name: str = ""
    downloader_type: str = "transmission"
    download_dir: str = ""
    auto_import_enabled: bool = True


@dataclass(frozen=True, slots=True)
class PendingAddBuildResult:
    pending_add: PendingAddContext | None
    error_text: str = ""


class AddPendingContextBuilder:
    def __init__(self, search_service: SearchMediaService) -> None:
        self._search_service = search_service

    def build_from_selection(
        self,
        *,
        chat_id: int,
        selection_text: str,
        downloader_name: str = "",
        downloader_type: str = "transmission",
        download_dir: str = "",
        auto_import_enabled: bool = True,
    ) -> PendingAddBuildResult:
        index = _parse_selection_index(selection_text)
        if index is None:
            return PendingAddBuildResult(pending_add=None, error_text=SELECT_USAGE_TEXT)

        candidate_result = self._search_service.get_cached_candidate_load_result(chat_id, index)
        if candidate_result.load_failed:
            return PendingAddBuildResult(pending_add=None, error_text=SELECT_LOOKUP_FAILED_TEXT)
        candidate = candidate_result.candidate
        if candidate is None:
            first_candidate_result = self._search_service.get_cached_candidate_load_result(chat_id, 1)
            if first_candidate_result.load_failed:
                return PendingAddBuildResult(pending_add=None, error_text=SELECT_LOOKUP_FAILED_TEXT)
            if first_candidate_result.candidate is None:
                return PendingAddBuildResult(pending_add=None, error_text=SELECT_NOT_FOUND_TEXT)
            return PendingAddBuildResult(pending_add=None, error_text=SELECT_OUT_OF_RANGE_TEXT)

        source = _resolve_source(candidate)
        if not source:
            return PendingAddBuildResult(pending_add=None, error_text=CANDIDATE_SOURCE_MISSING_TEXT)

        title = str(candidate.get("title", "")).strip() or "(no title)"
        media_identity = normalize_media_identity_payload(candidate.get("media_identity"))
        return PendingAddBuildResult(
            pending_add=build_pending_add_context(
                task_ref=str(index),
                title=title,
                source=source,
                media_identity=media_identity,
                downloader_name=downloader_name,
                downloader_type=downloader_type,
                download_dir=download_dir,
                auto_import_enabled=auto_import_enabled,
            )
        )

    def build_from_source(
        self,
        *,
        source: str,
        title: str,
        downloader_name: str = "",
        downloader_type: str = "transmission",
        download_dir: str = "",
        auto_import_enabled: bool = True,
    ) -> PendingAddBuildResult:
        cleaned_source = source.strip()
        if not cleaned_source:
            return PendingAddBuildResult(pending_add=None, error_text=CANDIDATE_SOURCE_MISSING_TEXT)

        return PendingAddBuildResult(
            pending_add=build_pending_add_context(
                task_ref=build_bt_task_ref(cleaned_source),
                title=title.strip() or "(no title)",
                source=cleaned_source,
                downloader_name=downloader_name,
                downloader_type=downloader_type,
                download_dir=download_dir,
                auto_import_enabled=auto_import_enabled,
            )
        )


class AddPendingRuntimeState:
    def __init__(self) -> None:
        self._pending_add_contexts_by_chat_ref: dict[tuple[int, str], PendingAddContext] = {}
        self._latest_pending_task_ref_by_chat: dict[int, str] = {}

    def record(self, *, chat_id: int, pending_add: PendingAddContext) -> None:
        if chat_id <= 0:
            return
        key = (chat_id, pending_add.task_ref)
        self._pending_add_contexts_by_chat_ref[key] = pending_add
        self._latest_pending_task_ref_by_chat[chat_id] = pending_add.task_ref

    def get(self, *, chat_id: int | None, task_ref: str) -> PendingAddContext | None:
        if chat_id is None or chat_id <= 0:
            return None
        return self._pending_add_contexts_by_chat_ref.get((chat_id, task_ref))

    def get_latest_task_ref(self, chat_id: int) -> str:
        return self._latest_pending_task_ref_by_chat.get(chat_id, "")

    def clear(self, *, chat_id: int | None, task_ref: str) -> None:
        if chat_id is None or chat_id <= 0:
            return
        key = (chat_id, task_ref)
        self._pending_add_contexts_by_chat_ref.pop(key, None)
        if self._latest_pending_task_ref_by_chat.get(chat_id) == task_ref:
            self._latest_pending_task_ref_by_chat.pop(chat_id, None)

    def log_pending_job_result_missing(
        self,
        *,
        chat_id: int,
        task_ref: str,
        task_id: str,
        task_hash: str,
        stage: str,
    ) -> None:
        if stage == "confirm":
            suggestion = (
                "检查 SQLite/jobs 表里的待确认下载任务是否仍存在；当前 confirm 会直接返回状态读取失败，"
                "避免把进程内残留上下文误判成仍可确认下载。"
            )
        elif stage == "cancel":
            suggestion = (
                "检查 SQLite/jobs 表里的待确认下载任务是否仍存在；当前取消会直接返回状态读取失败，"
                "避免把进程内残留上下文误判成仍可取消下载。"
            )
        else:
            suggestion = (
                "检查 SQLite/jobs 表里的待确认下载任务是否仍存在；当前入口会直接返回服务未就绪，"
                "避免把进程内残留上下文误判成普通仍有待确认下载。"
            )
        print(
            f"\033[31m[下载待确认任务结果缺失]\033[0m chat_id={chat_id} task_ref={task_ref} "
            f"task_id={task_id} task_hash={task_hash} 错误=jobs pending row missing while in-memory pending exists\n"
            f"\033[33m[处理建议]\033[0m {suggestion}",
            flush=True,
        )


def build_pending_add_context(
    *,
    task_ref: str,
    title: str,
    source: str,
    media_identity: Mapping[str, Any] | None = None,
    downloader_name: str = "",
    downloader_type: str = "transmission",
    download_dir: str = "",
    auto_import_enabled: bool = True,
) -> PendingAddContext:
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    return PendingAddContext(
        task_ref=task_ref,
        task_id=f"selection:{task_ref}",
        task_hash=f"candidate:{digest}",
        title=title,
        source=source,
        media_identity=normalize_media_identity_payload(media_identity),
        downloader_name=downloader_name.strip(),
        downloader_type=downloader_type.strip() or "transmission",
        download_dir=download_dir.strip(),
        auto_import_enabled=bool(auto_import_enabled),
    )


def to_completed_pending_add_context(
    pending_add: PendingAddContext,
    *,
    actual_task_id: str,
    actual_task_hash: str,
) -> PendingAddContext:
    return PendingAddContext(
        task_ref=pending_add.task_ref,
        task_id=actual_task_id.strip(),
        task_hash=actual_task_hash.strip(),
        title=pending_add.title,
        source=pending_add.source,
        media_identity=pending_add.media_identity,
        downloader_name=pending_add.downloader_name,
        downloader_type=pending_add.downloader_type,
        download_dir=pending_add.download_dir,
        auto_import_enabled=pending_add.auto_import_enabled,
    )


def build_bt_task_ref(source: str) -> str:
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    return f"bt-{digest[:8]}"


def pending_add_to_json(pending_add: PendingAddContext) -> str:
    return json.dumps(
        {
            "task_ref": pending_add.task_ref,
            "task_id": pending_add.task_id,
            "task_hash": pending_add.task_hash,
            "title": pending_add.title,
            "source": pending_add.source,
            "media_identity": pending_add.media_identity or {},
            "downloader_name": pending_add.downloader_name,
            "downloader_type": pending_add.downloader_type,
            "download_dir": pending_add.download_dir,
            "auto_import_enabled": pending_add.auto_import_enabled,
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def pending_add_from_json(payload_json: str) -> tuple[PendingAddContext | None, str | None]:
    cleaned_payload = payload_json.strip()
    if not cleaned_payload:
        return None, "payload_json empty"
    try:
        payload = json.loads(cleaned_payload)
    except json.JSONDecodeError:
        return None, "payload_json invalid json"
    if not isinstance(payload, dict):
        return None, "payload_json not object"

    task_ref = str(payload.get("task_ref", "")).strip()
    task_id = str(payload.get("task_id", "")).strip()
    task_hash = str(payload.get("task_hash", "")).strip()
    title = str(payload.get("title", "")).strip()
    source = str(payload.get("source", "")).strip()
    media_identity = normalize_media_identity_payload(payload.get("media_identity"))
    downloader_name = str(payload.get("downloader_name", "")).strip()
    downloader_type = str(payload.get("downloader_type", "")).strip() or "transmission"
    download_dir = str(payload.get("download_dir", "")).strip()
    auto_import_enabled = payload.get("auto_import_enabled", True)
    if not task_ref or not task_id or not task_hash or not title or not source:
        missing_fields = [
            field_name
            for field_name, value in (
                ("task_ref", task_ref),
                ("task_id", task_id),
                ("task_hash", task_hash),
                ("title", title),
                ("source", source),
            )
            if not value
        ]
        return None, "missing required fields: " + ",".join(missing_fields)
    return (
        PendingAddContext(
            task_ref=task_ref,
            task_id=task_id,
            task_hash=task_hash,
            title=title,
            source=source,
            media_identity=media_identity,
            downloader_name=downloader_name,
            downloader_type=downloader_type,
            download_dir=download_dir,
            auto_import_enabled=bool(auto_import_enabled),
        ),
        None,
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
    return resolve_bt_source(candidate)

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from app.db.job_event_repo import JobEventPersistenceError, JobEventRepo
from app.services.media_identity import MEDIA_IDENTITY_EVENT_TYPE, media_identity_from_json

IMPORT_MEDIA_IDENTITY_RESULT_MISSING_REASON = "import media identity result missing"


@dataclass(frozen=True, slots=True)
class ImportConfirmedMediaIdentityResolver:
    job_event_repo: JobEventRepo | None

    def resolve(self, *, task_id: str, task_hash: str) -> dict[str, str] | None:
        if self.job_event_repo is None:
            return None
        try:
            events = self.job_event_repo.list_events_for_task_identity(task_id=task_id, task_hash=task_hash)
            if events is None:
                raise JobEventPersistenceError(IMPORT_MEDIA_IDENTITY_RESULT_MISSING_REASON)
        except (JobEventPersistenceError, sqlite3.Error) as error:
            if str(error) == IMPORT_MEDIA_IDENTITY_RESULT_MISSING_REASON:
                _log_import_media_identity_result_missing(task_id=task_id, task_hash=task_hash, reason=str(error))
            elif _is_import_media_identity_row_corrupted_error(error):
                _log_import_media_identity_row_corrupted(task_id=task_id, task_hash=task_hash, reason=str(error))
            else:
                _log_import_media_identity_query_failed(task_id=task_id, task_hash=task_hash, reason=str(error))
            return None
        for event in reversed(events):
            if event.event_type != MEDIA_IDENTITY_EVENT_TYPE:
                continue
            media_identity = media_identity_from_json(event.message)
            if media_identity is not None:
                return media_identity
        return None

    def resolve_tmdb_id(self, task_id: str, task_hash: str) -> str:
        confirmed_media_identity = self.resolve(task_id=task_id, task_hash=task_hash)
        if confirmed_media_identity is None:
            return ""
        return confirmed_media_identity.get("tmdb_id", "").strip()


def _log_import_media_identity_query_failed(*, task_id: str, task_hash: str, reason: str) -> None:
    print(
        f"\033[31m[导入媒体身份查询失败]\033[0m task_id={task_id} task_hash={task_hash} 错误={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 SQLite/job_event 表读取是否正常；"
        "当前 metadata 入参会退回命名真相或文件名解析，避免把查询失败混成普通“无媒体身份”。",
        flush=True,
    )


def _log_import_media_identity_result_missing(*, task_id: str, task_hash: str, reason: str) -> None:
    print(
        f"\033[31m[导入媒体身份结果缺失]\033[0m task_id={task_id} task_hash={task_hash} 错误={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 job_event 查询返回是否仍带有完整结果；"
        "当前 metadata 入参会退回命名真相或文件名解析，避免把缺失真相误判成“没有已确认媒体身份”。",
        flush=True,
    )


def _log_import_media_identity_row_corrupted(*, task_id: str, task_hash: str, reason: str) -> None:
    print(
        f"\033[31m[导入媒体身份记录损坏]\033[0m task_id={task_id} task_hash={task_hash} 错误={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 job_event 里的 task_ref / event_type / message 等媒体身份字段是否仍是完整记录；"
        "当前 metadata 入参会退回命名真相或文件名解析，避免把坏记录混成普通查询失败。",
        flush=True,
    )


def _is_import_media_identity_row_corrupted_error(error: Exception) -> bool:
    return isinstance(error, JobEventPersistenceError) and str(error).endswith("corrupted after read")

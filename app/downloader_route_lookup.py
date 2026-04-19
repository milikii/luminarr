from __future__ import annotations

import json

from app.db.job_repo import JobRepo


class DownloaderRouteLookupError(RuntimeError):
    pass


def _resolve_downloader_payload_value(payload_json: str, key: str) -> tuple[str, str | None]:
    cleaned_payload = payload_json.strip()
    if not cleaned_payload:
        return "", "payload_json empty"
    try:
        payload = json.loads(cleaned_payload)
    except json.JSONDecodeError:
        return "", "payload_json invalid json"
    if not isinstance(payload, dict):
        return "", "payload_json not object"
    return str(payload.get(key, "")).strip(), None


def _log_downloader_route_lookup_failure(*, task_ref: str, chat_id: int | None, reason: str) -> None:
    print(
        f"\033[31m[下载器路由未命中]\033[0m task_ref={task_ref} chat_id={chat_id if chat_id is not None else '-'} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查当前任务是否已写入 downloader job、payload 里是否保留了 downloader_name，"
        "并确认状态/导入查询使用的是同一私聊会话。",
        flush=True,
    )


def _log_downloader_route_lookup_error(*, task_ref: str, chat_id: int | None, error: Exception) -> None:
    print(
        f"\033[31m[下载器路由查询失败]\033[0m task_ref={task_ref} chat_id={chat_id if chat_id is not None else '-'} 错误={error}\n"
        "\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表读取是否正常，并确认当前任务引用仍能命中 downloader job 真相。",
        flush=True,
    )


def _log_downloader_route_payload_corruption(
    *,
    task_ref: str,
    chat_id: int | None,
    reason: str,
) -> None:
    print(
        f"\033[31m[下载器路由载荷损坏]\033[0m task_ref={task_ref} chat_id={chat_id if chat_id is not None else '-'} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 jobs.payload_json 是否仍保留合法 JSON，且包含 downloader_name。",
        flush=True,
    )


def _resolve_downloader_name_for_task(
    *,
    task_ref: str,
    chat_id: int | None,
    job_repo: JobRepo,
) -> str | None:
    if chat_id is None or chat_id <= 0:
        _log_downloader_route_lookup_failure(task_ref=task_ref, chat_id=chat_id, reason="chat_id missing")
        return None
    try:
        downloader_job = job_repo.get_downloader_job_for_chat_ref(chat_id=chat_id, task_ref=task_ref)
    except Exception as error:
        _log_downloader_route_lookup_error(task_ref=task_ref, chat_id=chat_id, error=error)
        return None
    if downloader_job is None:
        _log_downloader_route_lookup_failure(task_ref=task_ref, chat_id=chat_id, reason="downloader job missing")
        return None
    downloader_name, payload_error = _resolve_downloader_payload_value(
        downloader_job.payload_json,
        "downloader_name",
    )
    if payload_error is not None:
        _log_downloader_route_payload_corruption(
            task_ref=task_ref,
            chat_id=chat_id,
            reason=payload_error,
        )
        return None
    if downloader_name:
        return downloader_name
    _log_downloader_route_lookup_failure(task_ref=task_ref, chat_id=chat_id, reason="downloader_name missing")
    return None

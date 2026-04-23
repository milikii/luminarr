from __future__ import annotations

import re
from collections.abc import Awaitable, Callable

from app.clients.transmission import TransmissionTaskStatus
from app.db.download_monitor_repo import DownloadMonitorRepo
from app.db.job_event_repo import JobEventRepo
from app.services.post_download_auto_import import PostDownloadAutoImportService
from app.services.status_delivery import (
    SUPPORTED_DELIVERY_CHANNELS,
    format_task_status,
    render_status_reply,
)
from app.services.status_follow_up import (
    STATUS_AUTO_IMPORT_STATE_UNAVAILABLE_TEXT as _STATUS_AUTO_IMPORT_STATE_UNAVAILABLE_TEXT,
    StatusFollowUpRecorder,
)

GetStatusFunc = Callable[..., Awaitable[TransmissionTaskStatus | None]]

STATUS_QUERY_USAGE_TEXT = "状态查询格式：status <任务ID或Hash>"
STATUS_NOT_FOUND_TEXT = "未找到对应下载任务，请检查任务 ID/Hash。"
STATUS_QUERY_FAILED_TEXT = "查询下载状态失败，请稍后重试。"
STATUS_AUTO_IMPORT_STATE_UNAVAILABLE_TEXT = _STATUS_AUTO_IMPORT_STATE_UNAVAILABLE_TEXT
class GetDownloadStatusService:
    def __init__(
        self,
        get_status_func: GetStatusFunc,
        download_monitor_repo: DownloadMonitorRepo | None = None,
        job_event_repo: JobEventRepo | None = None,
        post_download_auto_import_service: PostDownloadAutoImportService | None = None,
    ) -> None:
        self._get_status_func = get_status_func
        self._download_monitor_repo = download_monitor_repo
        self._job_event_repo = job_event_repo
        self._post_download_auto_import_service = post_download_auto_import_service
        self._status_follow_up_recorder = StatusFollowUpRecorder(
            download_monitor_repo=download_monitor_repo,
            job_event_repo=job_event_repo,
            post_download_auto_import_service=post_download_auto_import_service,
        )

    @property
    def download_monitor_repo(self) -> DownloadMonitorRepo | None:
        return self._download_monitor_repo

    async def get_status_text(
        self,
        task_ref: str,
        *,
        chat_id: int | None = None,
        channel: str | None = None,
    ) -> str:
        cleaned_ref = task_ref.strip()
        if not cleaned_ref:
            return STATUS_QUERY_USAGE_TEXT

        try:
            if chat_id is not None:
                task_status = await self._get_status_func(cleaned_ref, chat_id)
            else:
                task_status = await self._get_status_func(cleaned_ref)
        except Exception as error:
            print(
                f"\033[31m[下载状态查询失败]\033[0m task_ref={cleaned_ref} chat_id={chat_id or '-'} 错误={error}\n\033[33m[处理建议]\033[0m 检查下载器 RPC、下载器路由和网络连通性；当前请求会返回查询失败文本，但这次状态读取没有拿到真实结果。",
                flush=True,
            )
            return STATUS_QUERY_FAILED_TEXT
        if task_status is None:
            return STATUS_NOT_FOUND_TEXT
        auto_import_text = await self._record_status_observation(task_ref=cleaned_ref, task_status=task_status)
        if channel in SUPPORTED_DELIVERY_CHANNELS:
            return render_status_reply(
                task_ref=cleaned_ref,
                task_status=task_status,
                auto_import_text=auto_import_text,
                channel=channel,
            )
        status_text = format_task_status(task_status)
        if not auto_import_text:
            return status_text
        return f"{status_text}\n\n{auto_import_text}"

    async def _record_status_observation(self, *, task_ref: str, task_status: TransmissionTaskStatus) -> str | None:
        return await self._status_follow_up_recorder.record(task_ref=task_ref, task_status=task_status)


def parse_status_query(text: str) -> str | None:
    cleaned_text = text.strip()
    matched = re.match(r"^(?:(?i:status)|状态)(?:\s+(.*))?$", cleaned_text)
    if not matched:
        return None
    return (matched.group(1) or "").strip()

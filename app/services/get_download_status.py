from __future__ import annotations

import re
from collections.abc import Awaitable, Callable

from app.clients.transmission import TransmissionTaskStatus
from app.db.download_monitor_repo import DownloadMonitorRepo
from app.db.job_event_repo import JobEventRepo
from app.services.post_download_auto_import import PostDownloadAutoImportService

GetStatusFunc = Callable[..., Awaitable[TransmissionTaskStatus | None]]

STATUS_QUERY_USAGE_TEXT = "状态查询格式：status <任务ID或Hash>"
STATUS_NOT_FOUND_TEXT = "未找到对应下载任务，请检查任务 ID/Hash。"
STATUS_QUERY_FAILED_TEXT = "查询下载状态失败，请稍后重试。"
STATUS_OBSERVATION_WARNING_TEXT = "注意：下载状态观察落盘失败，自动导入跟进可能未推进，请稍后重试。"
STATUS_AUTO_IMPORT_WARNING_TEXT = "注意：自动导入跟进失败，本次状态查询未附带后续处理结果，请稍后重试。"

_STATUS_CODE_LABELS = {
    0: "已停止",
    1: "校验等待",
    2: "校验中",
    3: "下载等待",
    4: "下载中",
    5: "做种等待",
    6: "做种中",
}


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

    @property
    def download_monitor_repo(self) -> DownloadMonitorRepo | None:
        return self._download_monitor_repo

    async def get_status_text(self, task_ref: str, *, chat_id: int | None = None) -> str:
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
        status_text = format_task_status(task_status)
        if not auto_import_text:
            return status_text
        return f"{status_text}\n\n{auto_import_text}"

    async def _record_status_observation(self, *, task_ref: str, task_status: TransmissionTaskStatus) -> str | None:
        if self._download_monitor_repo is None:
            return None
        try:
            update = self._download_monitor_repo.record_status(task_status)
        except Exception as error:
            print(
                f"\033[31m[下载状态观察落盘失败]\033[0m task_ref={task_ref} task_id={task_status.task_id} task_hash={task_status.task_hash} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/download_monitor 表写入是否正常；当前请求仍会返回下载状态文本，但下载完成观察和后续自动导入可能不会推进。",
                flush=True,
            )
            return STATUS_OBSERVATION_WARNING_TEXT
        if update.newly_completed and self._job_event_repo is not None:
            try:
                self._job_event_repo.append_event(
                    task_ref=task_ref,
                    task_id=task_status.task_id,
                    task_hash=task_status.task_hash,
                    event_type="downloader.completed_observed",
                    message=task_status.name,
                )
            except Exception as error:
                print(
                    f"\033[31m[下载完成观察事件落盘失败]\033[0m task_ref={task_ref} task_id={task_status.task_id} task_hash={task_status.task_hash} event_type=downloader.completed_observed 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/job_event 表写入是否正常；当前请求仍会返回下载状态文本，但这次完成观察事件可能没有落盘。",
                    flush=True,
                )
        if self._post_download_auto_import_service is None:
            return None
        try:
            return await self._post_download_auto_import_service.run_for_record(update.record)
        except Exception as error:
            print(
                f"\033[31m[下载状态自动导入跟进失败]\033[0m task_ref={task_ref} task_id={task_status.task_id} task_hash={task_status.task_hash} 错误={error}\n\033[33m[处理建议]\033[0m 检查自动导入后半段依赖、SQLite 和导入审批链路；当前请求仍会返回下载状态文本，但不会附带这次自动导入 follow-up。",
                flush=True,
            )
            return STATUS_AUTO_IMPORT_WARNING_TEXT


def parse_status_query(text: str) -> str | None:
    cleaned_text = text.strip()
    matched = re.match(r"^(?:(?i:status)|状态)(?:\s+(.*))?$", cleaned_text)
    if not matched:
        return None
    return (matched.group(1) or "").strip()


def format_task_status(task_status: TransmissionTaskStatus) -> str:
    status_label = _STATUS_CODE_LABELS.get(task_status.status_code, f"未知({task_status.status_code})")
    progress_percent = _clamp_progress(task_status.percent_done)
    return "\n".join(
        [
            "下载状态：",
            f"任务 ID: {task_status.task_id}",
            f"任务 Hash: {task_status.task_hash}",
            f"名称: {task_status.name}",
            f"状态: {status_label}",
            f"进度: {progress_percent:.1f}%",
            f"下载速度: {_format_speed(task_status.rate_download)}",
            f"预计剩余: {_format_eta(task_status.eta_seconds)}",
        ]
    )


def _clamp_progress(raw_progress: float) -> float:
    progress = raw_progress * 100
    if progress < 0:
        return 0.0
    if progress > 100:
        return 100.0
    return progress


def _format_speed(raw_speed: int) -> str:
    if raw_speed <= 0:
        return "0 B/s"

    units = ("B/s", "KB/s", "MB/s", "GB/s")
    speed = float(raw_speed)
    unit_index = 0
    while speed >= 1024 and unit_index < len(units) - 1:
        speed /= 1024
        unit_index += 1

    if unit_index == 0:
        return f"{int(speed)} {units[unit_index]}"
    return f"{speed:.1f} {units[unit_index]}"


def _format_eta(eta_seconds: int) -> str:
    if eta_seconds < 0:
        return "-"
    hours, remainder = divmod(eta_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"

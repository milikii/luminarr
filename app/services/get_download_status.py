from __future__ import annotations

import re
from collections.abc import Awaitable, Callable

from app.clients.transmission import TransmissionTaskStatus

GetStatusFunc = Callable[[str], Awaitable[TransmissionTaskStatus | None]]

STATUS_QUERY_USAGE_TEXT = "状态查询格式：status <任务ID或Hash>"
STATUS_NOT_FOUND_TEXT = "未找到对应下载任务，请检查任务 ID/Hash。"
STATUS_QUERY_FAILED_TEXT = "查询下载状态失败，请稍后重试。"

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
    def __init__(self, get_status_func: GetStatusFunc) -> None:
        self._get_status_func = get_status_func

    async def get_status_text(self, task_ref: str) -> str:
        cleaned_ref = task_ref.strip()
        if not cleaned_ref:
            return STATUS_QUERY_USAGE_TEXT

        try:
            task_status = await self._get_status_func(cleaned_ref)
        except Exception:
            return STATUS_QUERY_FAILED_TEXT
        if task_status is None:
            return STATUS_NOT_FOUND_TEXT
        return format_task_status(task_status)


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

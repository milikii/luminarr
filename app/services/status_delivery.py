from __future__ import annotations

from app.clients.transmission import TransmissionTaskStatus
from app.runtime.delivery import DeliveryAction, DeliveryHeader, DeliveryItem, DeliverySection, render_delivery_item

STATUS_CODE_LABELS = {
    0: "已停止",
    1: "校验等待",
    2: "校验中",
    3: "下载等待",
    4: "下载中",
    5: "做种等待",
    6: "做种中",
}
SUPPORTED_DELIVERY_CHANNELS = frozenset({"telegram", "feishu", "personal_wechat", "wecom"})


def format_task_status(task_status: TransmissionTaskStatus) -> str:
    status_label = STATUS_CODE_LABELS.get(task_status.status_code, f"未知({task_status.status_code})")
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


def render_status_reply(
    *,
    task_ref: str,
    task_status: TransmissionTaskStatus,
    auto_import_text: str | None,
    channel: str,
) -> str:
    return render_delivery_item(
        build_status_delivery_item(
            task_ref=task_ref,
            task_status=task_status,
            auto_import_text=auto_import_text,
        ),
        channel=channel,
    )


def build_status_delivery_item(
    *,
    task_ref: str,
    task_status: TransmissionTaskStatus,
    auto_import_text: str | None,
) -> DeliveryItem:
    sections: list[DeliverySection] = [
        DeliverySection(
            label="当前进度",
            lines=(
                f"任务：{task_status.name}",
                f"任务 ID：{task_status.task_id}",
                f"任务 Hash：{task_status.task_hash}",
                f"状态：{STATUS_CODE_LABELS.get(task_status.status_code, f'未知({task_status.status_code})')}",
                f"进度：{_clamp_progress(task_status.percent_done):.1f}%",
                f"下载速度：{_format_speed(task_status.rate_download)}",
                f"预计剩余：{_format_eta(task_status.eta_seconds)}",
            ),
        )
    ]
    if auto_import_text:
        follow_up_lines = tuple(line.strip() for line in auto_import_text.splitlines() if line.strip())
        if follow_up_lines:
            sections.append(DeliverySection(label="后续处理", lines=follow_up_lines))
    status = "success" if _clamp_progress(task_status.percent_done) >= 100 else "pending"
    return DeliveryItem(
        header=DeliveryHeader(kind="status", title="下载状态", subtitle=f"查询对象：{task_ref}"),
        sections=tuple(sections),
        actions=(
            DeliveryAction(label="刷新状态", hint=f"发送 status {task_ref}", kind="secondary"),
        ),
        status=status,
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

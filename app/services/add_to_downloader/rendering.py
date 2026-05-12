from __future__ import annotations

from app.db.approval_repo import DEFAULT_PENDING_TIMEOUT_SECONDS
from app.runtime.delivery import DeliveryAction, DeliveryHeader, DeliveryItem, DeliverySection, render_delivery_item
from app.services.add_pending_context import PendingAddContext


def render_add_pending_reply(*, pending_add: PendingAddContext, channel: str) -> str:
    return render_delivery_item(build_add_pending_delivery_item(pending_add), channel=channel)


def render_duplicate_warning_reply(
    *,
    pending_add: PendingAddContext,
    warning_text: str,
    evidence_lines: tuple[str, ...],
    channel: str,
) -> str:
    return render_delivery_item(
        build_duplicate_warning_delivery_item(
            pending_add=pending_add,
            warning_text=warning_text,
            evidence_lines=evidence_lines,
        ),
        channel=channel,
    )


def build_add_pending_delivery_item(pending_add: PendingAddContext) -> DeliveryItem:
    expire_minutes = max(1, DEFAULT_PENDING_TIMEOUT_SECONDS // 60)
    task_lines = [
        f"片名：{pending_add.title}",
        f"选择序号：{pending_add.task_ref}",
    ]
    if pending_add.adult_display_id:
        task_lines.append(f"番号：{pending_add.adult_display_id}")
    if pending_add.adult_archive_category:
        task_lines.append(f"分类：{pending_add.adult_archive_category}")
    if pending_add.adult_history_text:
        task_lines.append(pending_add.adult_history_text)
    return DeliveryItem(
        header=DeliveryHeader(kind="approval", title="待确认：下载"),
        sections=(
            DeliverySection(
                label="任务信息",
                lines=tuple(task_lines),
            ),
        ),
        actions=(
            DeliveryAction(label="确认下载", hint=f"发送 confirm {pending_add.task_ref}", kind="primary"),
            DeliveryAction(label="取消下载", hint=f"发送 cancel {pending_add.task_ref}", kind="secondary"),
        ),
        footer=f"过期时间：{expire_minutes} 分钟后",
        status="pending",
    )


def build_duplicate_warning_delivery_item(
    *,
    pending_add: PendingAddContext,
    warning_text: str,
    evidence_lines: tuple[str, ...],
) -> DeliveryItem:
    summary_lines = [f"片名：{pending_add.title}"]
    if pending_add.adult_display_id:
        summary_lines.append(f"番号：{pending_add.adult_display_id}")
    if pending_add.adult_archive_category:
        summary_lines.append(f"分类：{pending_add.adult_archive_category}")

    sections = [
        DeliverySection(label="提醒", lines=(warning_text,)),
        DeliverySection(label="任务信息", lines=tuple(summary_lines)),
    ]
    if evidence_lines:
        sections.append(DeliverySection(label="命中证据", lines=evidence_lines))

    continue_query = f"继续下载 {pending_add.adult_display_id or pending_add.title}".strip()
    return DeliveryItem(
        header=DeliveryHeader(kind="warning", title="重复命中：下载前确认"),
        sections=tuple(sections),
        actions=(
            DeliveryAction(label="继续下载", hint=f"发送 {continue_query}", kind="primary"),
            DeliveryAction(label="取消", hint="发送 cancel", kind="secondary"),
        ),
        status="warning",
    )



from __future__ import annotations

from app.db.approval_repo import DEFAULT_PENDING_TIMEOUT_SECONDS
from app.db.job_repo import JobRepo
from app.runtime.delivery import DeliveryAction, DeliveryHeader, DeliveryItem, DeliverySection, render_delivery_item
from app.services.add_pending_context import PendingAddContext, pending_add_to_json


class AddPendingPersistenceState:
    def __init__(
        self,
        *,
        job_repo: JobRepo | None,
        downloader_pending_job_result_missing_reason: str,
        downloader_pending_job_none_reason: str,
        job_row_corrupted_reasons: frozenset[str],
    ) -> None:
        self._job_repo = job_repo
        self._downloader_pending_job_result_missing_reason = downloader_pending_job_result_missing_reason
        self._downloader_pending_job_none_reason = downloader_pending_job_none_reason
        self._job_row_corrupted_reasons = job_row_corrupted_reasons

    def record_pending_job(
        self,
        *,
        chat_id: int,
        user_id: int | None,
        pending_add: PendingAddContext,
    ) -> bool:
        if self._job_repo is None:
            return True
        try:
            pending_job = self._job_repo.upsert_downloader_job_pending(
                chat_id=chat_id,
                user_id=user_id,
                task_ref=pending_add.task_ref,
                task_id=pending_add.task_id,
                task_hash=pending_add.task_hash,
                payload_json=pending_add_to_json(pending_add),
            )
            if pending_job is None:
                raise RuntimeError(self._downloader_pending_job_none_reason)
        except Exception as error:
            if str(error) in {
                self._downloader_pending_job_result_missing_reason,
                self._downloader_pending_job_none_reason,
            }:
                print(
                    f"\033[31m[下载待确认任务结果缺失]\033[0m chat_id={chat_id} user_id={user_id} task_ref={pending_add.task_ref} task_id={pending_add.task_id} task_hash={pending_add.task_hash} 错误={error}\n\033[33m[处理建议]\033[0m 检查 jobs 写入后回读是否仍能拿到刚创建的待确认任务；当前请求会直接返回待确认状态写入失败，避免把缺失真相误报成可确认下载。",
                    flush=True,
                )
            elif str(error) in self._job_row_corrupted_reasons:
                print(
                    f"\033[31m[下载待确认任务记录损坏]\033[0m chat_id={chat_id} user_id={user_id} task_ref={pending_add.task_ref} task_id={pending_add.task_id} task_hash={pending_add.task_hash} 错误={error}\n\033[33m[处理建议]\033[0m 检查 jobs 新写入待确认任务里的 job_id / chat_id / user_id / version 等字段是否仍是完整真相；当前请求会直接返回待确认状态写入失败，避免把坏任务记录误报成可确认下载。",
                    flush=True,
                )
            else:
                print(
                    f"\033[31m[下载待确认任务落盘失败]\033[0m chat_id={chat_id} user_id={user_id} task_ref={pending_add.task_ref} task_id={pending_add.task_id} task_hash={pending_add.task_hash} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表写入是否正常；当前请求会直接返回待确认状态写入失败，避免把待确认任务真相缺口误报成可确认下载。",
                    flush=True,
                )
            return False
        return True


def render_add_pending_reply(*, pending_add: PendingAddContext, channel: str) -> str:
    return render_delivery_item(build_add_pending_delivery_item(pending_add), channel=channel)


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

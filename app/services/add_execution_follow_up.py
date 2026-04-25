from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.clients.transmission import TransmissionTask
from app.db.adult_content_registry_repo import AdultContentRegistryRepo
from app.db.download_monitor_repo import DownloadMonitorPersistenceError, DownloadMonitorRepo
from app.db.job_event_repo import JobEventPersistenceError, JobEventRepo
from app.services.media_identity import MEDIA_IDENTITY_EVENT_TYPE, media_identity_to_json
from app.services.add_pending_context import PendingAddContext

AddTorrentFunc = Callable[..., Awaitable[TransmissionTask]]
LogTraceFunc = Callable[..., None]


@dataclass(frozen=True, slots=True)
class AddResult:
    task_id: str
    task_hash: str
    title: str


@dataclass(frozen=True, slots=True)
class AddExecutionOutcome:
    reply: str
    result: AddResult | None = None


class AddExecutionFollowUpService:
    def __init__(
        self,
        *,
        add_torrent_func: AddTorrentFunc,
        job_event_repo: JobEventRepo | None,
        download_monitor_repo: DownloadMonitorRepo | None,
        log_trace_func: LogTraceFunc,
        add_failed_text: str,
        download_monitor_register_result_missing_reason: str,
        adult_content_registry_repo: AdultContentRegistryRepo | None = None,
    ) -> None:
        self._add_torrent_func = add_torrent_func
        self._job_event_repo = job_event_repo
        self._download_monitor_repo = download_monitor_repo
        self._adult_content_registry_repo = adult_content_registry_repo
        self._log_trace = log_trace_func
        self._add_failed_text = add_failed_text
        self._download_monitor_register_result_missing_reason = download_monitor_register_result_missing_reason

    async def dispatch(
        self,
        *,
        task_ref: str,
        pending_add: PendingAddContext,
        chat_id: int | None,
        user_id: int | None,
    ) -> AddExecutionOutcome:
        try:
            task = await self._invoke_add_torrent(pending_add)
        except Exception as error:
            self._log_dispatch_error(pending_add=pending_add, error=error)
            self.record_event(
                task_ref=task_ref,
                task_id=pending_add.task_id,
                task_hash=pending_add.task_hash,
                event_type="downloader.dispatch_failed",
                message=self._add_failed_text,
            )
            self._log_trace(
                event="confirm_dispatch",
                result="failed",
                stage="dispatch",
                chat_id=chat_id,
                user_id=user_id,
                task_ref=task_ref,
                task_id=pending_add.task_id,
                task_hash=pending_add.task_hash,
                detail=str(error),
            )
            return AddExecutionOutcome(reply=self._add_failed_text)

        result = AddResult(task_id=task.task_id, task_hash=task.task_hash, title=pending_add.title)
        reply = (
            f"已添加下载：{result.title}\n"
            f"任务 ID: {result.task_id}\n"
            f"任务 Hash: {result.task_hash}"
        )
        self.record_event(
            task_ref=task_ref,
            task_id=result.task_id,
            task_hash=result.task_hash,
            event_type="downloader.succeeded",
            message=result.title,
        )
        self.record_media_identity_event(
            task_ref=task_ref,
            task_id=result.task_id,
            task_hash=result.task_hash,
            pending_add=pending_add,
        )
        self.record_adult_content_downloading(
            task_ref=task_ref,
            task_id=result.task_id,
            task_hash=result.task_hash,
            pending_add=pending_add,
        )
        self._log_trace(
            event="confirm_dispatch",
            result="succeeded",
            stage="dispatch",
            chat_id=chat_id,
            user_id=user_id,
            task_ref=task_ref,
            task_id=result.task_id,
            task_hash=result.task_hash,
            detail=result.title,
        )
        if pending_add.auto_import_enabled or bool(pending_add.adult_content_id):
            self.register_download_monitor(
                task_id=result.task_id,
                task_hash=result.task_hash,
                title=result.title,
                chat_id=chat_id,
                user_id=user_id,
            )
        return AddExecutionOutcome(reply=reply, result=result)

    def record_event(
        self,
        *,
        task_ref: str,
        event_type: str,
        message: str,
        task_id: str = "",
        task_hash: str = "",
    ) -> None:
        if self._job_event_repo is None:
            return
        try:
            self._job_event_repo.append_event(
                task_ref=task_ref,
                task_id=task_id,
                task_hash=task_hash,
                event_type=event_type,
                message=message,
            )
        except Exception as error:
            if str(error) == "job_event missing after append":
                print(
                    f"\033[31m[下载事件结果缺失]\033[0m task_ref={task_ref} task_id={task_id} task_hash={task_hash} event_type={event_type} 错误=downloader event missing after append\n"
                    "\033[33m[处理建议]\033[0m 检查 job_event 写入后是否还能立即回读到该条下载事件；"
                    "当前流程会继续执行，但这条下载事件真相可能没有落稳。",
                    flush=True,
                )
            elif _is_downloader_event_row_corrupted_error(error):
                print(
                    f"\033[31m[下载事件记录损坏]\033[0m task_ref={task_ref} task_id={task_id} task_hash={task_hash} event_type={event_type} 错误={error}\n"
                    "\033[33m[处理建议]\033[0m 检查 job_event 读回事件里的 task_ref / event_type 等真相字段是否仍然完整；"
                    "当前流程会继续执行，但不会把这条坏事件当成已稳定落盘。",
                    flush=True,
                )
            else:
                print(
                    f"\033[31m[下载事件落盘失败]\033[0m task_ref={task_ref} task_id={task_id} task_hash={task_hash} event_type={event_type} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/job_event 表写入是否正常；当前流程会继续执行，但这条下载事件可能没有落盘。",
                    flush=True,
                )

    def record_media_identity_event(
        self,
        *,
        task_ref: str,
        task_id: str,
        task_hash: str,
        pending_add: PendingAddContext,
    ) -> None:
        if pending_add.media_identity is None:
            return
        payload_json = media_identity_to_json(pending_add.media_identity)
        if not payload_json:
            return
        self.record_event(
            task_ref=task_ref,
            task_id=task_id,
            task_hash=task_hash,
            event_type=MEDIA_IDENTITY_EVENT_TYPE,
            message=payload_json,
        )

    def register_download_monitor(
        self,
        *,
        task_id: str,
        task_hash: str,
        title: str,
        chat_id: int | None,
        user_id: int | None,
    ) -> None:
        if self._download_monitor_repo is None:
            return
        try:
            self._download_monitor_repo.register_download(
                task_id=task_id,
                task_hash=task_hash,
                name=title,
                chat_id=chat_id,
                user_id=user_id,
            )
        except Exception as error:
            if str(error) == self._download_monitor_register_result_missing_reason:
                print(
                    f"\033[31m[下载监控登记结果缺失]\033[0m task_id={task_id} task_hash={task_hash} 标题={title} chat_id={chat_id} user_id={user_id} 错误={error}\n"
                    "\033[33m[处理建议]\033[0m 检查 download_monitor 写入后回读是否仍能拿到刚登记的任务状态；"
                    "当前下载已投递，但后续状态跟踪和自动导入真相还没有确认落稳。",
                    flush=True,
                )
            elif _is_download_monitor_register_row_corrupted_error(error):
                print(
                    f"\033[31m[下载监控登记记录损坏]\033[0m task_id={task_id} task_hash={task_hash} 标题={title} chat_id={chat_id} user_id={user_id} 错误={error}\n"
                    "\033[33m[处理建议]\033[0m 检查 download_monitor 读回记录里的 task_id / task_hash / chat_id / user_id 等真相字段是否仍然完整；"
                    "当前下载已投递，但后续状态跟踪和自动导入不会把这条坏记录当成已稳定登记。",
                    flush=True,
                )
            else:
                print(
                    f"\033[31m[下载监控登记失败]\033[0m task_id={task_id} task_hash={task_hash} 标题={title} chat_id={chat_id} user_id={user_id} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/download_monitor 表写入是否正常；当前下载已投递，但后续状态跟踪和自动导入可能不会推进。",
                    flush=True,
                )

    def record_adult_content_downloading(
        self,
        *,
        task_ref: str,
        task_id: str,
        task_hash: str,
        pending_add: PendingAddContext,
    ) -> None:
        if self._adult_content_registry_repo is None:
            return
        if not pending_add.adult_content_id:
            return
        try:
            self._adult_content_registry_repo.mark_downloading(
                normalized_content_id=pending_add.adult_content_id,
                content_id_kind=pending_add.adult_content_kind or pending_add.adult_archive_category or "adult",
                archive_category=pending_add.adult_archive_category or "other_adult",
                display_title=pending_add.adult_display_id or pending_add.title,
                latest_source_site=pending_add.source_site,
                task_ref=task_ref,
                task_id=task_id,
                task_hash=task_hash,
                downloader_name=pending_add.downloader_name,
            )
        except Exception as error:
            print(
                f"\033[31m[成人资源下载状态登记失败]\033[0m content_id={pending_add.adult_content_id} task_ref={task_ref} "
                f"task_id={task_id} task_hash={task_hash} 错误={error}\n"
                "\033[33m[处理建议]\033[0m 检查 adult_content_registry 表写入是否正常；当前下载已投递，但成人历史状态可能不会及时更新。",
                flush=True,
            )

    async def _invoke_add_torrent(self, pending_add: PendingAddContext) -> TransmissionTask:
        accepted_parameters = inspect.signature(self._add_torrent_func).parameters
        if pending_add.downloader_name.strip() and "downloader_name" in accepted_parameters:
            return await self._add_torrent_func(
                pending_add.source,
                downloader_name=pending_add.downloader_name,
                download_dir=pending_add.download_dir,
            )
        if pending_add.download_dir.strip() and "download_dir" in accepted_parameters:
            return await self._add_torrent_func(
                pending_add.source,
                download_dir=pending_add.download_dir,
            )
        return await self._add_torrent_func(pending_add.source)

    def _log_dispatch_error(self, *, pending_add: PendingAddContext, error: Exception) -> None:
        print(
            "\033[31m[下载投递失败]\033[0m "
            f"标题={pending_add.title} 下载器={pending_add.downloader_name or 'legacy-transmission'} "
            f"类型={pending_add.downloader_type or 'transmission'} 目标目录={pending_add.download_dir or '-'} "
            f"原因={error}\n"
            "\033[33m[处理建议]\033[0m 检查下载器地址、认证信息、目标目录和磁力链接后重试。"
        )


def _is_download_monitor_register_row_corrupted_error(error: Exception) -> bool:
    return isinstance(error, DownloadMonitorPersistenceError) and str(error).endswith("corrupted after read")


def _is_downloader_event_row_corrupted_error(error: Exception) -> bool:
    return isinstance(error, JobEventPersistenceError) and str(error).endswith("corrupted after read")

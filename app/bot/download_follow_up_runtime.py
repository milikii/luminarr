from __future__ import annotations

import asyncio
from collections.abc import MutableMapping
from typing import Protocol

from app.db.download_monitor_repo import DownloadMonitorPersistenceError, DownloadMonitorRepo
from app.services.get_download_status import GetDownloadStatusService
from app.services.post_download_auto_import import PostDownloadAutoImportService


class _SchedulerApplication(Protocol):
    bot_data: MutableMapping[str, object]

    def create_task(self, coroutine, *, name: str): ...


async def post_download_auto_import_scheduler_loop(
    *,
    service: PostDownloadAutoImportService,
    stop_event: asyncio.Event,
    interval_seconds: float,
) -> None:
    while not stop_event.is_set():
        try:
            result = await service.run_once()
            if result.state_unavailable:
                _log_post_download_auto_import_scheduler_state_unavailable(scanned=result.scanned)
        except Exception as error:
            _log_post_download_auto_import_scheduler_error(error=error)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            continue


async def poll_pending_download_completion_once(
    *,
    download_monitor_repo: DownloadMonitorRepo,
    status_service: GetDownloadStatusService,
) -> None:
    try:
        pending_records = download_monitor_repo.list_pending_completion()
        if pending_records is None:
            raise RuntimeError("download completion pending list result missing")
    except Exception as error:
        _log_download_completion_pending_list_error(error=error)
        return
    for record in pending_records:
        await status_service.get_status_text(record.task_hash, chat_id=record.chat_id)


async def download_completion_polling_loop(
    *,
    download_monitor_repo: DownloadMonitorRepo,
    status_service: GetDownloadStatusService,
    stop_event: asyncio.Event,
    interval_seconds: float,
) -> None:
    while not stop_event.is_set():
        try:
            await poll_pending_download_completion_once(
                download_monitor_repo=download_monitor_repo,
                status_service=status_service,
            )
        except Exception as error:
            _log_download_completion_polling_loop_error(error=error)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            continue


def start_download_follow_up_scheduler(
    *,
    application: _SchedulerApplication,
    post_download_auto_import_service_key: str,
    post_download_auto_import_stop_event_key: str,
    post_download_auto_import_task_key: str,
    get_download_status_service_key: str,
    download_completion_polling_stop_event_key: str,
    download_completion_polling_task_key: str,
    interval_seconds: float,
) -> None:
    service = application.bot_data.get(post_download_auto_import_service_key)
    existing_task = application.bot_data.get(post_download_auto_import_task_key)
    if isinstance(service, PostDownloadAutoImportService) and not (
        isinstance(existing_task, asyncio.Task) and not existing_task.done()
    ):
        stop_event = asyncio.Event()
        application.bot_data[post_download_auto_import_stop_event_key] = stop_event
        application.bot_data[post_download_auto_import_task_key] = application.create_task(
            post_download_auto_import_scheduler_loop(
                service=service,
                stop_event=stop_event,
                interval_seconds=interval_seconds,
            ),
            name="post_download_auto_import_scheduler",
        )

    status_service = application.bot_data.get(get_download_status_service_key)
    download_monitor_repo = getattr(status_service, "download_monitor_repo", None)
    existing_task = application.bot_data.get(download_completion_polling_task_key)
    if isinstance(existing_task, asyncio.Task) and not existing_task.done():
        return
    if not isinstance(status_service, GetDownloadStatusService):
        _log_download_completion_polling_config_error(reason="未注入有效的 get_download_status_service。")
        return
    if not isinstance(download_monitor_repo, DownloadMonitorRepo):
        _log_download_completion_polling_config_error(reason="get_download_status_service 未暴露有效的 download_monitor_repo。")
        return

    stop_event = asyncio.Event()
    application.bot_data[download_completion_polling_stop_event_key] = stop_event
    application.bot_data[download_completion_polling_task_key] = application.create_task(
        download_completion_polling_loop(
            download_monitor_repo=download_monitor_repo,
            status_service=status_service,
            stop_event=stop_event,
            interval_seconds=interval_seconds,
        ),
        name="download_completion_polling_scheduler",
    )


async def stop_download_follow_up_scheduler(
    *,
    application: _SchedulerApplication,
    post_download_auto_import_stop_event_key: str,
    post_download_auto_import_task_key: str,
    download_completion_polling_stop_event_key: str,
    download_completion_polling_task_key: str,
) -> None:
    stop_event = application.bot_data.pop(post_download_auto_import_stop_event_key, None)
    task = application.bot_data.pop(post_download_auto_import_task_key, None)
    if isinstance(stop_event, asyncio.Event):
        stop_event.set()
    if isinstance(task, asyncio.Task):
        await task

    stop_event = application.bot_data.pop(download_completion_polling_stop_event_key, None)
    task = application.bot_data.pop(download_completion_polling_task_key, None)
    if isinstance(stop_event, asyncio.Event):
        stop_event.set()
    if isinstance(task, asyncio.Task):
        try:
            await task
        except Exception as error:
            _log_download_completion_polling_stop_error(error=error)
            raise


def _log_post_download_auto_import_scheduler_error(*, error: Exception) -> None:
    print(
        f"\033[31m[下载完成后台轮询失败]\033[0m 原因={error}\n"
        "\033[33m[处理建议]\033[0m 检查 download_monitor、SQLite 和导入审批链路后等待下一轮自动轮询。"
    )


def _log_post_download_auto_import_scheduler_state_unavailable(*, scanned: int) -> None:
    print(
        f"\033[31m[下载完成后台轮询状态读取失败]\033[0m scanned={scanned}\n"
        "\033[33m[处理建议]\033[0m 检查 download_monitor、job_event 和导入审批链路的持久化状态；当前这轮自动导入已跳过异常记录，下一轮仍会继续尝试。",
    )


def _log_download_completion_polling_loop_error(*, error: Exception) -> None:
    print(
        f"\033[31m[下载完成状态轮询失败]\033[0m 原因={error}\n"
        "\033[33m[处理建议]\033[0m 检查下载器状态查询、download_monitor 和 SQLite 后等待下一轮自动轮询。"
    )


def _log_download_completion_pending_list_error(*, error: Exception) -> None:
    if str(error) == "download completion pending list result missing":
        print(
            f"\033[31m[下载完成待轮询列表结果缺失]\033[0m 原因={error}\n"
            "\033[33m[处理建议]\033[0m 检查 download_monitor 待轮询列表查询返回是否仍带有完整结果；当前这轮不会继续逐条查状态，避免把缺失真相误判成“当前没有待轮询任务”。"
        )
        return
    if _is_download_completion_pending_list_row_corrupted_error(error):
        print(
            f"\033[31m[下载完成待轮询列表记录损坏]\033[0m 原因={error}\n"
            "\033[33m[处理建议]\033[0m 检查 download_monitor 待轮询记录里的 task_id / task_hash / chat_id 等真相字段；当前这轮不会继续逐条查状态，避免把坏记录混成普通读库失败。"
        )
        return
    print(
        f"\033[31m[下载完成待轮询列表读取失败]\033[0m 原因={error}\n"
        "\033[33m[处理建议]\033[0m 检查 download_monitor 表读取和 SQLite 连通性；当前这轮不会继续逐条查状态，但下一轮轮询仍会继续尝试。"
    )


def _is_download_completion_pending_list_row_corrupted_error(error: Exception) -> bool:
    return isinstance(error, DownloadMonitorPersistenceError) and str(error).endswith("corrupted after read")


def _log_download_completion_polling_config_error(*, reason: str) -> None:
    print(
        f"\033[31m[下载完成状态轮询未启动]\033[0m 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查应用启动阶段是否已注入 get_download_status_service，并确认它携带有效的 download_monitor_repo。"
    )


def _log_download_completion_polling_stop_error(*, error: Exception) -> None:
    print(
        f"\033[31m[下载完成状态轮询停止失败]\033[0m 原因={error}\n"
        "\033[33m[处理建议]\033[0m 检查下载完成轮询 task 的退出路径、SQLite 连接状态，以及 stop_event 触发后的清理逻辑。"
    )

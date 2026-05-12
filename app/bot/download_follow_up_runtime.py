from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime

from app.bot.shared_private_chat_sender import log_shared_private_chat_send_error
from app.bot.sidecar_host_runtime import SidecarHost
from app.db.download_monitor_repo import DownloadMonitorPersistenceError, DownloadMonitorRepo
from app.operational_logging import emit_operational_log
from app.services.get_download_status import GetDownloadStatusService
from app.services.post_download_auto_import import PostDownloadAutoImportService


class DownloadCompletionPendingListError(RuntimeError):
    pass


async def post_download_auto_import_scheduler_loop(
    *,
    service: PostDownloadAutoImportService,
    send_text_func,
    stop_event: asyncio.Event,
    interval_seconds: float,
) -> None:
    while not stop_event.is_set():
        try:
            result = await service.run_once()
            for notification in result.notifications:
                try:
                    await send_text_func(chat_id=notification.chat_id, text=notification.text)
                except Exception as error:
                    log_shared_private_chat_send_error(chat_id=notification.chat_id, error=error)
            if result.state_unavailable:
                _log_post_download_auto_import_scheduler_state_unavailable(scanned=result.scanned)
        except Exception as error:
            _log_post_download_auto_import_scheduler_error(error=error)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except TimeoutError:
            continue


async def poll_pending_download_completion_once(
    *,
    download_monitor_repo: DownloadMonitorRepo,
    status_service: GetDownloadStatusService,
    send_text_func=None,
    telegram_edit_message_func=None,
    min_telegram_progress_edit_interval_seconds: float = 300.0,
) -> None:
    try:
        pending_records = download_monitor_repo.list_pending_completion()
        if pending_records is None:
            raise DownloadCompletionPendingListError("download completion pending list result missing")
        completed_records = _list_completed_telegram_progress_records(download_monitor_repo=download_monitor_repo)
    except (DownloadMonitorPersistenceError, sqlite3.Error, DownloadCompletionPendingListError) as error:
        _log_download_completion_pending_list_error(error=error)
        return
    records = list(pending_records)
    seen = {
        identity
        for record in records
        if (identity := _resolve_record_identity(record)) is not None
    }
    for record in completed_records:
        identity = _resolve_record_identity(record)
        if identity is None:
            records.append(record)
            continue
        if identity in seen:
            continue
        seen.add(identity)
        records.append(record)
    for record in records:
        if _can_edit_telegram_progress(record=record, telegram_edit_message_func=telegram_edit_message_func):
            text = await status_service.get_status_text(
                record.task_hash,
                chat_id=record.chat_id,
                channel="telegram_live_progress",
            )
            if not _is_telegram_live_progress_card_text(text):
                continue
            refreshed_record = download_monitor_repo.get_record(task_id=record.task_id, task_hash=record.task_hash)
            if refreshed_record is None:
                continue
            if not _should_edit_telegram_progress(
                record=refreshed_record,
                text=text,
                min_interval_seconds=min_telegram_progress_edit_interval_seconds,
            ):
                continue
            await _edit_telegram_progress_message(
                download_monitor_repo=download_monitor_repo,
                record=refreshed_record,
                text=text,
                telegram_edit_message_func=telegram_edit_message_func,
            )
            await _send_telegram_completion_summary_if_needed(
                status_service=status_service,
                record=refreshed_record,
                send_text_func=send_text_func,
            )
            continue
        await status_service.get_status_text(record.task_hash, chat_id=record.chat_id)


def _list_completed_telegram_progress_records(
    *,
    download_monitor_repo: DownloadMonitorRepo,
    limit: int = 100,
) -> list:
    list_completed_for_auto_import = getattr(download_monitor_repo, "list_completed_for_auto_import", None)
    if not callable(list_completed_for_auto_import):
        return []
    completed_records = list_completed_for_auto_import(limit=limit)
    if completed_records is None:
        raise DownloadCompletionPendingListError("download completion completed list result missing")
    return [
        record
        for record in completed_records
        if record.chat_id > 0
        and record.telegram_message_id > 0
        and not record.telegram_progress_last_text.startswith("🎉 <b>任务完成</b>")
    ]


def _resolve_record_identity(record) -> tuple[str, str] | None:
    task_id = str(getattr(record, "task_id", "") or "").strip()
    task_hash = str(getattr(record, "task_hash", "") or "").strip()
    if not task_id or not task_hash:
        return None
    return (task_id, task_hash)


async def download_completion_polling_loop(
    *,
    download_monitor_repo: DownloadMonitorRepo,
    status_service: GetDownloadStatusService,
    stop_event: asyncio.Event,
    interval_seconds: float,
    send_text_func=None,
    telegram_edit_message_func=None,
    min_telegram_progress_edit_interval_seconds: float | None = None,
) -> None:
    while not stop_event.is_set():
        try:
            await poll_pending_download_completion_once(
                download_monitor_repo=download_monitor_repo,
                status_service=status_service,
                send_text_func=send_text_func,
                telegram_edit_message_func=telegram_edit_message_func,
                min_telegram_progress_edit_interval_seconds=(
                    interval_seconds
                    if min_telegram_progress_edit_interval_seconds is None
                    else min_telegram_progress_edit_interval_seconds
                ),
            )
        except Exception as error:
            _log_download_completion_polling_loop_error(error=error)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except TimeoutError:
            continue


def start_download_follow_up_scheduler(
    *,
    application: SidecarHost,
    send_text_func_key: str,
    telegram_edit_message_func_key: str = "",
    post_download_auto_import_service_key: str,
    post_download_auto_import_stop_event_key: str,
    post_download_auto_import_task_key: str,
    get_download_status_service_key: str,
    download_completion_polling_stop_event_key: str,
    download_completion_polling_task_key: str,
    interval_seconds: float,
    download_completion_interval_seconds: float | None = None,
    download_completion_polling_interval_seconds: float | None = None,
    min_telegram_progress_edit_interval_seconds: float | None = None,
) -> None:
    service = application.bot_data.get(post_download_auto_import_service_key)
    send_text_func = application.bot_data.get(send_text_func_key)
    existing_task = application.bot_data.get(post_download_auto_import_task_key)
    if isinstance(service, PostDownloadAutoImportService) and not (
        isinstance(existing_task, asyncio.Task) and not existing_task.done()
    ) and callable(send_text_func):
        stop_event = asyncio.Event()
        application.bot_data[post_download_auto_import_stop_event_key] = stop_event
        application.bot_data[post_download_auto_import_task_key] = application.create_task(
            post_download_auto_import_scheduler_loop(
                service=service,
                send_text_func=send_text_func,
                stop_event=stop_event,
                interval_seconds=interval_seconds,
            ),
            name="post_download_auto_import_scheduler",
        )
    elif isinstance(service, PostDownloadAutoImportService) and not (
        isinstance(existing_task, asyncio.Task) and not existing_task.done()
    ):
        _log_post_download_auto_import_send_capability_missing()

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
    telegram_edit_message_func = application.bot_data.get(telegram_edit_message_func_key) if telegram_edit_message_func_key else None
    resolved_download_completion_interval_seconds = (
        download_completion_polling_interval_seconds
        if download_completion_polling_interval_seconds is not None
        else (
            download_completion_interval_seconds
            if download_completion_interval_seconds is not None
            else interval_seconds
        )
    )
    resolved_min_telegram_progress_edit_interval_seconds = (
        min_telegram_progress_edit_interval_seconds
        if min_telegram_progress_edit_interval_seconds is not None
        else resolved_download_completion_interval_seconds
    )
    application.bot_data[download_completion_polling_task_key] = application.create_task(
        download_completion_polling_loop(
            download_monitor_repo=download_monitor_repo,
            status_service=status_service,
            stop_event=stop_event,
            interval_seconds=resolved_download_completion_interval_seconds,
            send_text_func=send_text_func,
            telegram_edit_message_func=telegram_edit_message_func,
            min_telegram_progress_edit_interval_seconds=resolved_min_telegram_progress_edit_interval_seconds,
        ),
        name="download_completion_polling_scheduler",
    )


async def stop_download_follow_up_scheduler(
    *,
    application: SidecarHost,
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
        try:
            await task
        except Exception as error:
            _log_post_download_auto_import_scheduler_stop_error(error=error)
            raise

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
    emit_operational_log(
        title="下载完成后台轮询失败",
        detail=f"原因={error}",
        fix_hint="检查 download_monitor、SQLite 和导入审批链路后等待下一轮自动轮询。",
    )


def _log_post_download_auto_import_scheduler_state_unavailable(*, scanned: int) -> None:
    emit_operational_log(
        title="下载完成后台轮询状态读取失败",
        detail=f"scanned={scanned}",
        fix_hint="检查 download_monitor、job_event 和导入审批链路的持久化状态；当前这轮自动导入已跳过异常记录，下一轮仍会继续尝试。",
    )


def _log_post_download_auto_import_scheduler_stop_error(*, error: Exception) -> None:
    emit_operational_log(
        title="下载完成后台轮询停止失败",
        detail=f"原因={error}",
        fix_hint="检查 post-download auto-import 后台 task 的异常日志；当前停机将继续上抛该错误，避免静默吞掉未完成的导入后处理。",
    )


def _log_post_download_auto_import_send_capability_missing() -> None:
    emit_operational_log(
        title="下载完成后台轮询未启动主动通知",
        detail="原因=宿主未注入可用的 shared private-chat send_text 回调。",
        fix_hint="检查当前宿主是否已注入跨渠道主动发送能力；内部自动导入仍会推进，但用户不会收到后台总结通知。",
    )


def _log_download_completion_polling_loop_error(*, error: Exception) -> None:
    emit_operational_log(
        title="下载完成状态轮询失败",
        detail=f"原因={error}",
        fix_hint="检查下载器状态查询、download_monitor 和 SQLite 后等待下一轮自动轮询。",
    )


def _log_download_completion_pending_list_error(*, error: Exception) -> None:
    if str(error) == "download completion pending list result missing":
        emit_operational_log(
            title="下载完成待轮询列表结果缺失",
            detail=f"原因={error}",
            fix_hint="检查 download_monitor 待轮询列表查询返回是否仍带有完整结果；当前这轮不会继续逐条查状态，避免把缺失真相误判成“当前没有待轮询任务”。",
        )
        return
    if _is_download_completion_pending_list_row_corrupted_error(error):
        emit_operational_log(
            title="下载完成待轮询列表记录损坏",
            detail=f"原因={error}",
            fix_hint="检查 download_monitor 待轮询记录里的 task_id / task_hash / chat_id 等真相字段；当前这轮不会继续逐条查状态，避免把坏记录混成普通读库失败。",
        )
        return
    emit_operational_log(
        title="下载完成待轮询列表读取失败",
        detail=f"原因={error}",
        fix_hint="检查 download_monitor 表读取和 SQLite 连通性；当前这轮不会继续逐条查状态，但下一轮轮询仍会继续尝试。",
    )


def _is_download_completion_pending_list_row_corrupted_error(error: Exception) -> bool:
    return isinstance(error, DownloadMonitorPersistenceError) and str(error).endswith("corrupted after read")


def _log_download_completion_polling_config_error(*, reason: str) -> None:
    emit_operational_log(
        title="下载完成状态轮询未启动",
        detail=f"原因={reason}",
        fix_hint="检查应用启动阶段是否已注入 get_download_status_service，并确认它携带有效的 download_monitor_repo。",
    )


def _log_download_completion_polling_stop_error(*, error: Exception) -> None:
    emit_operational_log(
        title="下载完成状态轮询停止失败",
        detail=f"原因={error}",
        fix_hint="检查下载完成轮询 task 的退出路径、SQLite 连接状态，以及 stop_event 触发后的清理逻辑。",
    )


def _can_edit_telegram_progress(*, record, telegram_edit_message_func) -> bool:
    return callable(telegram_edit_message_func) and record.chat_id > 0 and record.telegram_message_id > 0


def _is_telegram_live_progress_card_text(text: str) -> bool:
    stripped_text = text.strip()
    if not stripped_text:
        return False
    first_line = stripped_text.splitlines()[0]
    return first_line in {
        "⏳ <b>任务下载中</b>",
        "✅ <b>下载完成</b>",
        "🎉 <b>任务完成</b>",
    }


def _should_edit_telegram_progress(
    *,
    record,
    text: str,
    min_interval_seconds: float,
) -> bool:
    if record.telegram_message_id <= 0 or record.chat_id <= 0:
        return False
    if record.telegram_progress_last_text == text:
        return False
    if record.is_complete:
        return True
    last_synced_at = _parse_sqlite_timestamp(record.telegram_progress_last_synced_at)
    if last_synced_at is None:
        return True
    return (datetime.utcnow() - last_synced_at).total_seconds() >= max(0.0, min_interval_seconds)


async def _edit_telegram_progress_message(
    *,
    download_monitor_repo: DownloadMonitorRepo,
    record,
    text: str,
    telegram_edit_message_func,
) -> None:
    try:
        await telegram_edit_message_func(
            chat_id=record.chat_id,
            message_id=record.telegram_message_id,
            text=text,
            parse_mode="HTML",
        )
    except Exception as error:
        _log_telegram_progress_edit_error(record=record, error=error)
        return
    try:
        download_monitor_repo.record_telegram_progress_sync(
            task_id=record.task_id,
            task_hash=record.task_hash,
            text=text,
        )
    except (DownloadMonitorPersistenceError, sqlite3.Error) as error:
        _log_telegram_progress_sync_error(record=record, error=error)


async def _send_telegram_completion_summary_if_needed(
    *,
    status_service: GetDownloadStatusService,
    record,
    send_text_func,
) -> None:
    if not callable(send_text_func) or record.chat_id <= 0:
        return
    summary_text = status_service.build_pending_telegram_summary(
        task_id=record.task_id,
        task_hash=record.task_hash,
        title=record.name,
    )
    if not summary_text:
        return
    try:
        await send_text_func(chat_id=record.chat_id, text=summary_text, parse_mode="HTML")
    except Exception as error:
        log_shared_private_chat_send_error(chat_id=record.chat_id, error=error)
        return
    status_service.mark_telegram_summary_sent(task_id=record.task_id, task_hash=record.task_hash)


def _parse_sqlite_timestamp(value: str) -> datetime | None:
    cleaned_value = value.strip()
    if not cleaned_value:
        return None
    try:
        return datetime.strptime(cleaned_value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _log_telegram_progress_edit_error(*, record, error: Exception) -> None:
    emit_operational_log(
        title="Telegram 下载进度消息编辑失败",
        detail=f"task_id={record.task_id} task_hash={record.task_hash} chat_id={record.chat_id} message_id={record.telegram_message_id} 原因={error}",
        fix_hint="检查 Telegram message_id/chat_id 是否仍有效、Bot 是否具备编辑消息权限，以及当前下载进度卡片内容是否满足 Telegram 文本限制。",
    )


def _log_telegram_progress_sync_error(*, record, error: Exception) -> None:
    emit_operational_log(
        title="Telegram 下载进度同步真相落盘失败",
        detail=f"task_id={record.task_id} task_hash={record.task_hash} chat_id={record.chat_id} message_id={record.telegram_message_id} 原因={error}",
        fix_hint="检查 SQLite/download_monitor 表写入是否正常；当前 Telegram 消息可能已经被编辑，但本地下次轮询无法可靠去重。",
    )

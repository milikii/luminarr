from __future__ import annotations

import html
import re
import sqlite3
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx

from app.clients.qbittorrent import QbittorrentError
from app.clients.transmission import TransmissionError, TransmissionTaskStatus
from app.db.download_monitor_repo import DownloadMonitorPersistenceError, DownloadMonitorRepo
from app.db.job_event_repo import JobEvent, JobEventPersistenceError, JobEventRepo
from app.downloader_route_lookup import DownloaderRouteLookupError
from app.operational_logging import emit_operational_log
from app.runtime.delivery import DeliveryAction, DeliveryHeader, DeliveryItem, DeliverySection, render_delivery_item
from app.services.post_download_auto_import import (
    POST_PROCESSING_SUMMARY_EVENT,
    AutoImportStateUnavailableError,
    PostDownloadAutoImportService,
)

GetStatusFunc = Callable[..., Awaitable[TransmissionTaskStatus | None]]

STATUS_QUERY_USAGE_TEXT = "状态查询格式：status <任务ID或Hash>"
STATUS_NOT_FOUND_TEXT = "未找到对应下载任务，请检查任务 ID/Hash。"
STATUS_QUERY_FAILED_TEXT = "查询下载状态失败，请稍后重试。"
STATUS_OBSERVATION_WARNING_TEXT = "注意：下载状态观察落盘失败，自动导入跟进可能未推进，请稍后重试。"
STATUS_COMPLETION_EVENT_WARNING_TEXT = "注意：下载完成观察事件落盘失败，后续恢复可能缺少这次完成记录，请稍后重试。"
STATUS_AUTO_IMPORT_STATE_UNAVAILABLE_TEXT = "注意：自动导入状态读取失败，本次状态查询未附带后续处理结果，请稍后重试。"
STATUS_AUTO_IMPORT_WARNING_TEXT = "注意：自动导入跟进失败，本次状态查询未附带后续处理结果，请稍后重试。"
DOWNLOAD_MONITOR_STATUS_RESULT_MISSING_REASON = "download monitor status result missing"
DOWNLOAD_MONITOR_OBSERVED_RECORD_MISSING_REASON = "download monitor observed record missing"
DOWNLOAD_MONITOR_STATUS_UPSERT_RESULT_MISSING_REASON = "download monitor state missing after status upsert"
DOWNLOAD_MONITOR_COMPLETION_FLAG_MISSING_REASON = "download monitor completion flag missing"
DOWNLOAD_COMPLETION_EVENT_RESULT_MISSING_REASON = "job_event missing after append"
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
TELEGRAM_LIVE_PROGRESS_CHANNEL = "telegram_live_progress"
TELEGRAM_LIVE_PROGRESS_BAR_WIDTH = 10
TELEGRAM_LIVE_PROGRESS_DIVIDER = "━━━━━━━━━━━━"
TELEGRAM_SUMMARY_SENT_EVENT = "telegram.summary_sent"
_TERMINAL_STAGE_STATUSES = frozenset({"✅ 已完成", "❌ 失败", "跳过", "✅ 已有中文字幕"})


@dataclass(frozen=True, slots=True)
class TelegramPostProcessingSnapshot:
    overall_state: str
    status_text: str
    import_status: str
    metadata_status: str
    subtitle_status: str
    refresh_status: str
    library_path: str = ""


class StatusFollowUpStateError(RuntimeError):
    pass


class StatusFollowUpRecorder:
    def __init__(
        self,
        *,
        download_monitor_repo: DownloadMonitorRepo | None,
        job_event_repo: JobEventRepo | None,
        post_download_auto_import_service: PostDownloadAutoImportService | None,
    ) -> None:
        self._download_monitor_repo = download_monitor_repo
        self._job_event_repo = job_event_repo
        self._post_download_auto_import_service = post_download_auto_import_service

    async def record(self, *, task_ref: str, task_status: TransmissionTaskStatus) -> str | None:
        if self._download_monitor_repo is None:
            return None
        try:
            update = self._download_monitor_repo.record_status(task_status)
            if update is None:
                raise StatusFollowUpStateError(DOWNLOAD_MONITOR_STATUS_RESULT_MISSING_REASON)
            if getattr(update, "record", None) is None:
                raise StatusFollowUpStateError(DOWNLOAD_MONITOR_OBSERVED_RECORD_MISSING_REASON)
            newly_completed = getattr(update, "newly_completed", None)
            if not isinstance(newly_completed, bool):
                raise StatusFollowUpStateError(DOWNLOAD_MONITOR_COMPLETION_FLAG_MISSING_REASON)
        except (DownloadMonitorPersistenceError, sqlite3.Error, StatusFollowUpStateError) as error:
            if str(error) in {
                DOWNLOAD_MONITOR_STATUS_RESULT_MISSING_REASON,
                DOWNLOAD_MONITOR_OBSERVED_RECORD_MISSING_REASON,
                DOWNLOAD_MONITOR_STATUS_UPSERT_RESULT_MISSING_REASON,
            }:
                _log_download_monitor_observation_result_missing(
                    task_ref=task_ref,
                    task_status=task_status,
                    reason=str(error),
                )
            elif _is_download_monitor_observation_row_corrupted_error(error):
                _log_download_monitor_observation_row_corrupted(
                    task_ref=task_ref,
                    task_status=task_status,
                    reason=str(error),
                )
            elif str(error) == DOWNLOAD_MONITOR_COMPLETION_FLAG_MISSING_REASON:
                _log_download_monitor_completion_flag_missing(
                    task_ref=task_ref,
                    task_status=task_status,
                    reason=str(error),
                )
            else:
                _log_download_monitor_observation_failed(task_ref=task_ref, task_status=task_status, reason=str(error))
            return STATUS_OBSERVATION_WARNING_TEXT
        follow_up_parts: list[str] = []
        if newly_completed and self._job_event_repo is not None:
            try:
                self._job_event_repo.append_event(
                    task_ref=task_ref,
                    task_id=task_status.task_id,
                    task_hash=task_status.task_hash,
                    event_type="downloader.completed_observed",
                    message=task_status.name,
                )
            except (JobEventPersistenceError, sqlite3.Error) as error:
                if str(error) == DOWNLOAD_COMPLETION_EVENT_RESULT_MISSING_REASON:
                    _log_download_completion_event_result_missing(
                        task_ref=task_ref,
                        task_status=task_status,
                        reason=str(error),
                    )
                elif _is_completion_event_row_corrupted_error(error):
                    _log_download_completion_event_row_corrupted(
                        task_ref=task_ref,
                        task_status=task_status,
                        reason=str(error),
                    )
                else:
                    _log_download_completion_event_append_failed(
                        task_ref=task_ref,
                        task_status=task_status,
                        reason=str(error),
                    )
                follow_up_parts.append(STATUS_COMPLETION_EVENT_WARNING_TEXT)
        if self._post_download_auto_import_service is None:
            if not follow_up_parts:
                return None
            return "\n\n".join(follow_up_parts)
        try:
            auto_import_text = await self._post_download_auto_import_service.run_for_record(update.record)
        except AutoImportStateUnavailableError as error:
            _log_status_auto_import_state_unavailable(
                task_ref=task_ref,
                task_status=task_status,
                reason=str(error),
            )
            auto_import_text = STATUS_AUTO_IMPORT_STATE_UNAVAILABLE_TEXT
        except RuntimeError as error:
            _log_status_auto_import_follow_up_failed(
                task_ref=task_ref,
                task_status=task_status,
                reason=str(error),
            )
            auto_import_text = STATUS_AUTO_IMPORT_WARNING_TEXT
        if auto_import_text:
            follow_up_parts.append(auto_import_text)
        if not follow_up_parts:
            return None
        return "\n\n".join(follow_up_parts)


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

    def build_pending_telegram_summary(self, *, task_id: str, task_hash: str, title: str) -> str | None:
        events = _safe_list_job_events(
            job_event_repo=self._job_event_repo,
            task_id=task_id,
            task_hash=task_hash,
        )
        if events is None:
            return None
        if any(event.event_type == TELEGRAM_SUMMARY_SENT_EVENT for event in events):
            return None
        snapshot = _resolve_telegram_post_processing_snapshot(
            task_status=None,
            auto_import_text="",
            events=events,
        )
        if snapshot.overall_state != "finished" or not snapshot.library_path:
            return None
        success_summary = all(
            status == "✅ 已完成"
            for status in (
                snapshot.import_status,
                snapshot.metadata_status,
                snapshot.subtitle_status,
                snapshot.refresh_status,
            )
        )
        completion_line = "✅ 全部后处理已完成" if success_summary else "ℹ️ 后处理已结束"
        resolved_title = title.strip() or _extract_summary_title_from_events(events) or "-"
        return (
            "🏁 <b>入库完成</b>\n"
            f"<b>{html.escape(resolved_title)}</b>\n\n"
            f"{completion_line}\n\n"
            "📁 <b>入库路径：</b>\n"
            f"<code>{html.escape(snapshot.library_path)}</code>"
        )

    def mark_telegram_summary_sent(self, *, task_id: str, task_hash: str) -> None:
        if self._job_event_repo is None:
            return
        try:
            self._job_event_repo.append_event(
                task_ref=task_hash,
                task_id=task_id,
                task_hash=task_hash,
                event_type=TELEGRAM_SUMMARY_SENT_EVENT,
                message="telegram summary sent",
            )
        except (JobEventPersistenceError, sqlite3.Error) as error:
            emit_operational_log(
                title="Telegram 总结消息落盘失败",
                detail=f"task_id={task_id} task_hash={task_hash} 错误={error}",
                fix_hint="检查 SQLite/job_event 表写入是否正常；当前总结消息可能已发出，但去重真相未稳定落盘。",
            )

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
        except (DownloaderRouteLookupError, QbittorrentError, TransmissionError, httpx.HTTPError) as error:
            emit_operational_log(
                title="下载状态查询失败",
                detail=f"task_ref={cleaned_ref} chat_id={chat_id or '-'} 错误={error}",
                fix_hint="检查下载器 RPC、下载器路由和网络连通性；当前请求会返回查询失败文本，但这次状态读取没有拿到真实结果。",
            )
            return STATUS_QUERY_FAILED_TEXT
        if task_status is None:
            return STATUS_NOT_FOUND_TEXT
        auto_import_text = await self._record_status_observation(task_ref=cleaned_ref, task_status=task_status)
        events = _safe_list_job_events(
            job_event_repo=self._job_event_repo,
            task_id=task_status.task_id,
            task_hash=task_status.task_hash,
        )
        if channel == TELEGRAM_LIVE_PROGRESS_CHANNEL:
            return render_telegram_live_progress_reply(
                task_ref=cleaned_ref,
                task_status=task_status,
                auto_import_text=auto_import_text,
                events=events or (),
            )
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


def render_telegram_live_progress_reply(
    *,
    task_ref: str,
    task_status: TransmissionTaskStatus,
    auto_import_text: str | None,
    events: tuple[JobEvent, ...] | list[JobEvent],
) -> str:
    snapshot = _resolve_telegram_post_processing_snapshot(
        task_status=task_status,
        auto_import_text=auto_import_text or "",
        events=tuple(events),
    )
    raw_progress_percent = _clamp_progress(task_status.percent_done)
    progress_percent = 100 if snapshot.overall_state in {"processing", "finished"} else int(round(raw_progress_percent))
    if snapshot.overall_state == "finished":
        lines = ["🎉 <b>任务完成</b>"]
    elif snapshot.overall_state == "processing":
        lines = ["✅ <b>下载完成</b>"]
    else:
        lines = ["⏳ <b>任务下载中</b>"]
    lines.extend(
        [
            f"<i>{html.escape(task_status.name.strip() or '-')}</i>",
            TELEGRAM_LIVE_PROGRESS_DIVIDER,
            f"<b>状态：</b> {html.escape(snapshot.status_text)}",
            f"<b>下载进度：</b> {progress_percent}%",
            f"<code>{_format_progress_bar(float(progress_percent), width=TELEGRAM_LIVE_PROGRESS_BAR_WIDTH, filled_char='█', empty_char='░')}</code>",
            "",
        ]
    )
    if snapshot.overall_state == "pending":
        lines.extend(
            [
                f"⚡ <b>速度：</b> {_format_speed(task_status.rate_download)}  |  <b>剩余：</b> {_format_live_eta(task_status.eta_seconds, completed=False)}",
                TELEGRAM_LIVE_PROGRESS_DIVIDER,
            ]
        )
    else:
        lines.append(TELEGRAM_LIVE_PROGRESS_DIVIDER)
    lines.extend(
        [
            "<b>后处理</b>",
            f"- 导入：{snapshot.import_status}",
            f"- 刮削：{snapshot.metadata_status}",
            f"- 字幕：{snapshot.subtitle_status}",
            f"- 刷新：{snapshot.refresh_status}",
            TELEGRAM_LIVE_PROGRESS_DIVIDER,
            f"🆔 <b>任务 ID：</b> <code>{html.escape(task_status.task_id)}</code>",
            f"🔑 <b>Hash：</b> <code>{html.escape(task_status.task_hash)}</code>",
        ]
    )
    if snapshot.overall_state == "pending":
        lines.extend(("", "⏱️ <b>消息每 5 秒自动刷新一次</b>"))
    return "\n".join(lines)


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
        actions=(DeliveryAction(label="刷新状态", hint=f"发送 status {task_ref}", kind="secondary"),),
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


def _format_progress_bar(
    progress_percent: float,
    *,
    width: int = 12,
    filled_char: str = "#",
    empty_char: str = "-",
) -> str:
    if width <= 0:
        return "[]"
    if progress_percent >= 100:
        filled = width
    elif progress_percent <= 0:
        filled = 0
    else:
        filled = round(progress_percent / 100 * width)
        filled = max(1, min(width - 1, filled))
    return f"[{filled_char * filled}{empty_char * (width - filled)}]"


def _format_live_eta(eta_seconds: int, *, completed: bool) -> str:
    if completed:
        return "已完成"
    if eta_seconds < 0:
        return "--"
    hours, remainder = divmod(eta_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{hours:02d}h {minutes:02d}m"
    return f"{minutes:02d}m {seconds:02d}s"


def _format_eta(eta_seconds: int) -> str:
    if eta_seconds < 0:
        return "-"
    hours, remainder = divmod(eta_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def _safe_list_job_events(
    *,
    job_event_repo: JobEventRepo | None,
    task_id: str,
    task_hash: str,
) -> list[JobEvent] | None:
    if job_event_repo is None:
        return []
    list_events = getattr(job_event_repo, "list_events_for_task_identity", None)
    if not callable(list_events):
        return []
    try:
        return list_events(task_id=task_id, task_hash=task_hash)
    except (JobEventPersistenceError, sqlite3.Error) as error:
        emit_operational_log(
            title="Telegram 后处理状态查询失败",
            detail=f"task_id={task_id} task_hash={task_hash} 错误={error}",
            fix_hint="检查 SQLite/job_event 表读取是否正常；当前状态卡片会回退成基础下载状态，不展示稳定的后处理分阶段真相。",
        )
        return None


def _resolve_telegram_post_processing_snapshot(
    *,
    task_status: TransmissionTaskStatus | None,
    auto_import_text: str,
    events: tuple[JobEvent, ...],
) -> TelegramPostProcessingSnapshot:
    summary_text = _resolve_post_processing_summary_text(auto_import_text=auto_import_text, events=events)
    import_status = _resolve_import_stage_status(events=events, summary_text=summary_text)
    metadata_status = _resolve_stage_status(
        summary_text=summary_text,
        summary_label="metadata",
        success_event="metadata.succeeded",
        failure_event="metadata.failed",
        skipped_event="",
        events=events,
        prerequisite_status=import_status,
        later_event_prefixes=("subtitle.", "refresh."),
    )
    subtitle_status = _resolve_stage_status(
        summary_text=summary_text,
        summary_label="字幕",
        success_event="subtitle.succeeded",
        failure_event="subtitle.failed",
        skipped_event="subtitle.skipped",
        events=events,
        prerequisite_status=metadata_status if import_status in _TERMINAL_STAGE_STATUSES else import_status,
        later_event_prefixes=("refresh.",),
    )
    refresh_status = _resolve_stage_status(
        summary_text=summary_text,
        summary_label="刷新",
        success_event="refresh.succeeded",
        failure_event="refresh.failed",
        skipped_event="",
        events=events,
        prerequisite_status=subtitle_status if metadata_status in _TERMINAL_STAGE_STATUSES else metadata_status,
        later_event_prefixes=(),
    )
    library_path = _resolve_library_path(events=events, summary_text=summary_text)
    progress_percent = _clamp_progress(task_status.percent_done) if task_status is not None else 100.0
    completed = progress_percent >= 100
    if not completed:
        status_text = STATUS_CODE_LABELS.get(task_status.status_code, f"未知({task_status.status_code})") if task_status is not None else "下载中"
        return TelegramPostProcessingSnapshot(
            overall_state="pending",
            status_text=status_text,
            import_status="等待",
            metadata_status="等待",
            subtitle_status="等待",
            refresh_status="等待",
            library_path=library_path,
        )
    statuses = (import_status, metadata_status, subtitle_status, refresh_status)
    terminal = all(status in _TERMINAL_STAGE_STATUSES for status in statuses)
    if terminal:
        failed = any(status == "❌ 失败" for status in statuses)
        status_text = "处理结束" if failed else "全部完成"
        overall_state = "finished"
    else:
        status_text = "后处理中"
        overall_state = "processing"
    return TelegramPostProcessingSnapshot(
        overall_state=overall_state,
        status_text=status_text,
        import_status=import_status,
        metadata_status=metadata_status,
        subtitle_status=subtitle_status,
        refresh_status=refresh_status,
        library_path=library_path,
    )


def _resolve_post_processing_summary_text(*, auto_import_text: str, events: tuple[JobEvent, ...]) -> str:
    if "后处理总结" in auto_import_text:
        return auto_import_text
    for event in reversed(events):
        if event.event_type == POST_PROCESSING_SUMMARY_EVENT and event.message.strip():
            return event.message.strip()
    return ""


def _resolve_import_stage_status(*, events: tuple[JobEvent, ...], summary_text: str) -> str:
    if any(event.event_type == "import.succeeded" for event in events):
        return "✅ 已完成"
    if summary_text.startswith("导入成功："):
        return "✅ 已完成"
    if any(event.event_type.startswith("import.") for event in events):
        return "❌ 失败"
    return "等待"


def _resolve_stage_status(
    *,
    summary_text: str,
    summary_label: str,
    success_event: str,
    failure_event: str,
    skipped_event: str,
    events: tuple[JobEvent, ...],
    prerequisite_status: str,
    later_event_prefixes: tuple[str, ...],
) -> str:
    parsed_status = _extract_summary_stage_status(summary_text=summary_text, label=summary_label)
    if parsed_status:
        return parsed_status
    if any(event.event_type == success_event for event in events):
        return "✅ 已完成"
    if failure_event and any(event.event_type == failure_event for event in events):
        return "❌ 失败"
    if skipped_event and any(event.event_type == skipped_event for event in events):
        skipped_message = _resolve_latest_event_message(events=events, event_type=skipped_event)
        return _resolve_skipped_stage_status(skipped_message)
    if later_event_prefixes and any(
        any(event.event_type.startswith(prefix) for prefix in later_event_prefixes) for event in events
    ):
        return "跳过"
    if prerequisite_status in _TERMINAL_STAGE_STATUSES or prerequisite_status == "✅ 已完成":
        return "⏳ 进行中"
    return "等待"


def _extract_summary_stage_status(*, summary_text: str, label: str) -> str:
    prefix = f"- {label}："
    for raw_line in summary_text.splitlines():
        line = raw_line.strip()
        if not line.startswith(prefix):
            continue
        status_text = line.removeprefix(prefix).split("；", 1)[0].strip()
        if status_text == "成功":
            return "✅ 已完成"
        if status_text == "失败":
            return "❌ 失败"
        if status_text == "跳过":
            return "跳过"
        if status_text == "已有中文字幕":
            return "✅ 已有中文字幕"
        if status_text == "✅ 已有中文字幕":
            return "✅ 已有中文字幕"
    return ""


def _resolve_latest_event_message(*, events: tuple[JobEvent, ...], event_type: str) -> str:
    for event in reversed(events):
        if event.event_type == event_type:
            return event.message.strip()
    return ""


def _resolve_skipped_stage_status(message: str) -> str:
    if any(
        marker in message
        for marker in (
            "已检测到中文字幕外挂字幕",
            "视频内已检测到中文字幕轨",
            "目标中文字幕文件已存在",
        )
    ):
        return "✅ 已有中文字幕"
    return "跳过"


def _resolve_library_path(*, events: tuple[JobEvent, ...], summary_text: str) -> str:
    for event in reversed(events):
        if event.event_type == "import.succeeded":
            target_path = event.target_path.strip() or event.message.strip()
            if target_path:
                return target_path
    prefix = "目标路径:"
    for raw_line in summary_text.splitlines():
        line = raw_line.strip()
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip()
    return ""


def _extract_summary_title_from_events(events: tuple[JobEvent, ...]) -> str:
    for event in reversed(events):
        if event.event_type != POST_PROCESSING_SUMMARY_EVENT:
            continue
        first_line = event.message.strip().splitlines()[0] if event.message.strip() else ""
        prefix = "导入成功："
        if first_line.startswith(prefix):
            return first_line.removeprefix(prefix).strip()
    return ""


def _log_download_monitor_observation_failed(
    *,
    task_ref: str,
    task_status: TransmissionTaskStatus,
    reason: str,
) -> None:
    emit_operational_log(
        title="下载状态观察落盘失败",
        detail=_status_follow_up_detail(task_ref=task_ref, task_status=task_status, reason=reason),
        fix_hint="检查 SQLite/download_monitor 表写入是否正常；当前请求仍会返回下载状态文本，但下载完成观察和后续自动导入可能不会推进。",
    )


def _log_download_monitor_observation_result_missing(
    *,
    task_ref: str,
    task_status: TransmissionTaskStatus,
    reason: str,
) -> None:
    emit_operational_log(
        title="下载状态观察结果缺失",
        detail=_status_follow_up_detail(task_ref=task_ref, task_status=task_status, reason=reason),
        fix_hint="检查 download_monitor 返回是否仍带有完整 update 和 record；当前请求仍会返回下载状态文本，但这次完成观察和后续自动导入不会继续推进。",
    )


def _log_download_monitor_completion_flag_missing(
    *,
    task_ref: str,
    task_status: TransmissionTaskStatus,
    reason: str,
) -> None:
    emit_operational_log(
        title="下载状态观察完成标记缺失",
        detail=_status_follow_up_detail(task_ref=task_ref, task_status=task_status, reason=reason),
        fix_hint="检查 download_monitor 更新结果是否仍带有完整的 newly_completed 真相；当前请求仍会返回下载状态文本，但不会把这次完成观察继续推进到后续自动导入。",
    )


def _log_download_monitor_observation_row_corrupted(
    *,
    task_ref: str,
    task_status: TransmissionTaskStatus,
    reason: str,
) -> None:
    emit_operational_log(
        title="下载状态观察记录损坏",
        detail=_status_follow_up_detail(task_ref=task_ref, task_status=task_status, reason=reason),
        fix_hint="检查 download_monitor 读回记录里的 task_id / task_hash / status_code / percent_done 等真相字段是否仍然完整；当前请求仍会返回下载状态文本，但这次完成观察和后续自动导入不会继续推进。",
    )


def _log_download_completion_event_result_missing(
    *,
    task_ref: str,
    task_status: TransmissionTaskStatus,
    reason: str,
) -> None:
    emit_operational_log(
        title="下载完成观察事件结果缺失",
        detail=_status_follow_up_detail(
            task_ref=task_ref,
            task_status=task_status,
            reason=reason,
            event_type="downloader.completed_observed",
        ),
        fix_hint="检查 job_event 写入后回读是否仍能拿到刚追加的完成观察事件；当前请求仍会返回下载状态文本，但这次完成观察事件真相还没有确认落稳。",
    )


def _log_download_completion_event_row_corrupted(
    *,
    task_ref: str,
    task_status: TransmissionTaskStatus,
    reason: str,
) -> None:
    emit_operational_log(
        title="下载完成观察事件记录损坏",
        detail=_status_follow_up_detail(
            task_ref=task_ref,
            task_status=task_status,
            reason=reason,
            event_type="downloader.completed_observed",
        ),
        fix_hint="检查 job_event 完成观察记录里的 task_ref / event_type 等字段是否仍是完整真相；当前请求仍会返回下载状态文本，但这次完成观察事件不会当成已稳定落盘。",
    )


def _log_download_completion_event_append_failed(
    *,
    task_ref: str,
    task_status: TransmissionTaskStatus,
    reason: str,
) -> None:
    emit_operational_log(
        title="下载完成观察事件落盘失败",
        detail=_status_follow_up_detail(
            task_ref=task_ref,
            task_status=task_status,
            reason=reason,
            event_type="downloader.completed_observed",
        ),
        fix_hint="检查 SQLite/job_event 表写入是否正常；当前请求仍会返回下载状态文本，但这次完成观察事件可能没有落盘。",
    )


def _log_status_auto_import_state_unavailable(
    *,
    task_ref: str,
    task_status: TransmissionTaskStatus,
    reason: str,
) -> None:
    emit_operational_log(
        title="下载状态自动导入状态读取失败",
        detail=_status_follow_up_detail(task_ref=task_ref, task_status=task_status, reason=reason),
        fix_hint="检查 SQLite/download_monitor、job_event 和自动导入审批链路是否正常；当前请求仍会返回下载状态文本，但不会附带这次自动导入 follow-up。",
    )


def _log_status_auto_import_follow_up_failed(
    *,
    task_ref: str,
    task_status: TransmissionTaskStatus,
    reason: str,
) -> None:
    emit_operational_log(
        title="下载状态自动导入跟进失败",
        detail=_status_follow_up_detail(task_ref=task_ref, task_status=task_status, reason=reason),
        fix_hint="检查自动导入后半段依赖、SQLite 和导入审批链路；当前请求仍会返回下载状态文本，但不会附带这次自动导入 follow-up。",
    )


def _status_follow_up_detail(
    *,
    task_ref: str,
    task_status: TransmissionTaskStatus,
    reason: str,
    event_type: str = "",
) -> str:
    event_detail = f" event_type={event_type}" if event_type else ""
    return f"task_ref={task_ref} task_id={task_status.task_id} task_hash={task_status.task_hash}{event_detail} 错误={reason}"


def _is_download_monitor_observation_row_corrupted_error(error: Exception) -> bool:
    return isinstance(error, DownloadMonitorPersistenceError) and str(error).endswith("corrupted after read")


def _is_completion_event_row_corrupted_error(error: Exception) -> bool:
    return isinstance(error, JobEventPersistenceError) and str(error).endswith("corrupted after read")

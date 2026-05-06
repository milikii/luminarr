from __future__ import annotations

import re
import sqlite3
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from app.db.adult_content_registry_repo import (
    ADULT_CONTENT_STATUS_ARCHIVED_DELETED,
    ADULT_CONTENT_STATUS_ARCHIVED_PRESENT,
    AdultContentRegistryPersistenceError,
    AdultContentRegistryRepo,
)
from app.db.download_monitor_repo import DownloadMonitorPersistenceError, DownloadMonitorRecord, DownloadMonitorRepo
from app.db.job_event_repo import JobEventPersistenceError, JobEventRepo
from app.operational_logging import emit_operational_log
from app.services.adult_archive_service import (
    AdultArchiveOperationError,
    AdultArchiveService,
    AdultArchiveStateUnavailableError,
)

AutoImportFunc = Callable[[str, int | None, int | None], Awaitable[str]]
AutoImportRecordRunner = Callable[[DownloadMonitorRecord], Awaitable[str | None]]
AutoImportProgressPredicate = Callable[[DownloadMonitorRecord, str], bool]
AUTO_IMPORT_SKIPPED_BY_RULE_EVENT = "auto_import.skipped_by_rule"
AUTO_IMPORT_SKIP_EVENT_RESULT_MISSING_REASON = "auto import skip event missing after append"
AUTO_IMPORT_COMPLETED_LIST_RESULT_MISSING_REASON = "auto import completed list result missing"
AUTO_IMPORT_SKIPPED_TEXT = (
    "资源自动规则已跳过自动导入：{name}\n"
    "原因：命中低质量来源标记 {reason}。\n"
    "如仍需导入，请手动发送 import {task_ref}。"
)
_LOW_QUALITY_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bhdcam\b", flags=re.IGNORECASE), "HDCAM"),
    (re.compile(r"\bhdts\b", flags=re.IGNORECASE), "HDTS"),
    (re.compile(r"\bcam\b", flags=re.IGNORECASE), "CAM"),
    (re.compile(r"\b(?:ts|telesync)\b", flags=re.IGNORECASE), "TS"),
    (re.compile(r"\b(?:tc|telecine)\b", flags=re.IGNORECASE), "TC"),
    (re.compile(r"\b(?:scr|dvdscr)\b", flags=re.IGNORECASE), "SCR"),
    (re.compile(r"\bworkprint\b", flags=re.IGNORECASE), "WORKPRINT"),
)


@dataclass(frozen=True, slots=True)
class AutoImportNotification:
    chat_id: int
    text: str


@dataclass(frozen=True, slots=True)
class AutoImportRunResult:
    scanned: int
    progressed: int
    replies: tuple[str, ...]
    notifications: tuple[AutoImportNotification, ...] = ()
    state_unavailable: bool = False


@dataclass(frozen=True, slots=True)
class AutoImportBatchProgress:
    progressed: int
    replies: tuple[str, ...]
    notifications: tuple[AutoImportNotification, ...]
    state_unavailable: bool = False


class AutoImportStateUnavailableError(RuntimeError):
    pass


class AutoImportCompletedListUnavailableError(RuntimeError):
    pass


class PostDownloadAutoImportService:
    def __init__(
        self,
        download_monitor_repo: DownloadMonitorRepo,
        job_event_repo: JobEventRepo,
        auto_import_func: AutoImportFunc,
        adult_content_registry_repo: AdultContentRegistryRepo | None = None,
        adult_archive_service: AdultArchiveService | None = None,
    ) -> None:
        self._download_monitor_repo = download_monitor_repo
        self._job_event_repo = job_event_repo
        self._auto_import_func = auto_import_func
        self._adult_content_registry_repo = adult_content_registry_repo
        self._adult_archive_service = adult_archive_service

    async def run_once(self, *, limit: int = 20) -> AutoImportRunResult:
        try:
            candidates = load_completed_auto_import_candidates(
                download_monitor_repo=self._download_monitor_repo,
                limit=limit,
            )
        except AutoImportCompletedListUnavailableError:
            return AutoImportRunResult(scanned=0, progressed=0, replies=(), state_unavailable=True)
        progress = await run_auto_import_candidates(
            candidates=candidates,
            run_for_record=self.run_for_record,
            count_as_progress=_count_auto_import_progress,
            state_unavailable_error=AutoImportStateUnavailableError,
        )

        return AutoImportRunResult(
            scanned=len(candidates),
            progressed=progress.progressed,
            replies=progress.replies,
            notifications=progress.notifications,
            state_unavailable=progress.state_unavailable,
        )

    async def run_for_record(self, candidate: DownloadMonitorRecord) -> str | None:
        if not candidate.is_complete:
            return None
        if candidate.chat_id <= 0:
            emit_operational_log(
                title="自动导入聊天身份无效",
                detail=f"task_id={candidate.task_id} task_hash={candidate.task_hash} chat_id={candidate.chat_id} user_id={candidate.user_id}",
                fix_hint="检查 SQLite/download_monitor 表里的归属聊天身份是否完整；当前不会推进自动导入，避免把坏身份任务继续送入导入审批链。",
            )
            raise AutoImportStateUnavailableError(
                f"auto import chat identity invalid for {candidate.task_id}/{candidate.task_hash}"
            )
        adult_registry_record = self._get_adult_registry_record(candidate)
        if adult_registry_record is not None:
            return await self._run_adult_archive_follow_up(candidate=candidate, registry_record=adult_registry_record)
        has_terminal_activity = self._has_terminal_activity(candidate)
        if has_terminal_activity:
            return None
        blocked_reason = _match_low_quality_reason(candidate.name)
        if blocked_reason is not None:
            self._record_skip_event(candidate=candidate, reason=blocked_reason)
            return AUTO_IMPORT_SKIPPED_TEXT.format(
                name=candidate.name,
                reason=blocked_reason,
                task_ref=candidate.task_hash,
            )
        user_id = candidate.user_id if candidate.user_id > 0 else None
        return await self._auto_import_func(candidate.task_hash, candidate.chat_id, user_id)

    def _get_adult_registry_record(self, candidate: DownloadMonitorRecord):
        if self._adult_content_registry_repo is None:
            return None
        try:
            return self._adult_content_registry_repo.get_by_task_identity(
                task_id=candidate.task_id,
                task_hash=candidate.task_hash,
            )
        except (AdultContentRegistryPersistenceError, sqlite3.Error) as error:
            emit_operational_log(
                title="成人资源历史查询失败",
                detail=f"task_id={candidate.task_id} task_hash={candidate.task_hash} 错误={error}",
                fix_hint="检查 adult_content_registry 表读取是否正常；当前会按状态不可用停路，避免把历史真相缺口误判成普通非成人下载。",
            )
            raise AutoImportStateUnavailableError(
                f"adult registry lookup failed for {candidate.task_id}/{candidate.task_hash}"
            ) from error

    async def _run_adult_archive_follow_up(self, *, candidate: DownloadMonitorRecord, registry_record) -> str | None:
        if registry_record.current_status == ADULT_CONTENT_STATUS_ARCHIVED_DELETED:
            return None
        if self._adult_archive_service is None:
            raise AutoImportStateUnavailableError(
                f"adult archive service missing for {candidate.task_id}/{candidate.task_hash}"
            )
        try:
            return await self._adult_archive_service.run_for_record(
                candidate=candidate,
                registry_record=registry_record,
            )
        except AdultArchiveStateUnavailableError as error:
            emit_operational_log(
                title="成人资源归档状态不可用",
                detail=f"task_id={candidate.task_id} task_hash={candidate.task_hash} 错误={error}",
                fix_hint="检查 adult_content_registry、下载器导入源查询和归档目录配置；当前这条成人资源不会继续推进归档/清理。",
            )
            raise AutoImportStateUnavailableError(
                f"adult archive state unavailable for {candidate.task_id}/{candidate.task_hash}"
            ) from error
        except AdultArchiveOperationError as error:
            action = "保留期清理" if registry_record.current_status == ADULT_CONTENT_STATUS_ARCHIVED_PRESENT else "归档"
            emit_operational_log(
                title=f"成人资源{action}失败",
                detail=f"task_id={candidate.task_id} task_hash={candidate.task_hash} 错误={error}",
                fix_hint="检查下载器删除协议、源路径权限、归档目标目录和 adult_content_registry 状态后重试。",
            )
            return f"注意：成人资源{action}失败，本轮未更新后续状态，请稍后重试。"

    def _has_terminal_activity(self, candidate: DownloadMonitorRecord) -> bool:
        try:
            events = self._job_event_repo.list_events_for_task_identity(
                task_id=candidate.task_id,
                task_hash=candidate.task_hash,
            )
            if events is None:
                raise JobEventPersistenceError(
                    f"auto import terminal lookup result missing for {candidate.task_id}/{candidate.task_hash}"
                )
        except (JobEventPersistenceError, sqlite3.Error) as error:
            if str(error).startswith("auto import terminal lookup result missing for "):
                _log_auto_import_terminal_lookup_result_missing(
                    task_id=candidate.task_id,
                    task_hash=candidate.task_hash,
                    reason=str(error),
                )
            elif _is_auto_import_terminal_row_corrupted_error(error):
                _log_auto_import_terminal_lookup_row_corrupted(
                    task_id=candidate.task_id,
                    task_hash=candidate.task_hash,
                    reason=str(error),
                )
            else:
                _log_auto_import_terminal_lookup_failed(
                    task_id=candidate.task_id,
                    task_hash=candidate.task_hash,
                    reason=str(error),
                )
            raise AutoImportStateUnavailableError(
                f"auto import terminal lookup failed for {candidate.task_id}/{candidate.task_hash}"
            ) from error
        return any(
            event.event_type.startswith("import.") or event.event_type == AUTO_IMPORT_SKIPPED_BY_RULE_EVENT
            for event in events
        )

    def _record_skip_event(self, *, candidate: DownloadMonitorRecord, reason: str) -> None:
        try:
            self._job_event_repo.append_event(
                task_ref=candidate.task_hash,
                task_id=candidate.task_id,
                task_hash=candidate.task_hash,
                event_type=AUTO_IMPORT_SKIPPED_BY_RULE_EVENT,
                message=reason,
            )
        except (JobEventPersistenceError, sqlite3.Error) as error:
            if str(error) == "job_event missing after append":
                _log_auto_import_skip_event_result_missing(
                    task_id=candidate.task_id,
                    task_hash=candidate.task_hash,
                    reason=AUTO_IMPORT_SKIP_EVENT_RESULT_MISSING_REASON,
                )
            elif _is_auto_import_skip_event_row_corrupted_error(error):
                _log_auto_import_skip_event_row_corrupted(
                    task_id=candidate.task_id,
                    task_hash=candidate.task_hash,
                    reason=str(error),
                )
            else:
                _log_auto_import_skip_event_append_failed(
                    task_id=candidate.task_id,
                    task_hash=candidate.task_hash,
                    reason=str(error),
                )
            raise AutoImportStateUnavailableError(
                f"auto import skip event append failed for {candidate.task_id}/{candidate.task_hash}"
            ) from error


def _match_low_quality_reason(name: str) -> str | None:
    cleaned_name = name.strip()
    if not cleaned_name:
        return None
    for pattern, label in _LOW_QUALITY_PATTERNS:
        if pattern.search(cleaned_name):
            return label
    return None


def _count_auto_import_progress(candidate: DownloadMonitorRecord, _reply: str) -> bool:
    return _match_low_quality_reason(candidate.name) is None


def _is_auto_import_terminal_row_corrupted_error(error: Exception) -> bool:
    return isinstance(error, JobEventPersistenceError) and str(error).endswith("corrupted after read")


def load_completed_auto_import_candidates(
    *,
    download_monitor_repo: DownloadMonitorRepo,
    limit: int,
) -> tuple[DownloadMonitorRecord, ...]:
    try:
        candidates = download_monitor_repo.list_completed_for_auto_import(limit=limit)
        if candidates is None:
            raise DownloadMonitorPersistenceError(AUTO_IMPORT_COMPLETED_LIST_RESULT_MISSING_REASON)
    except (DownloadMonitorPersistenceError, sqlite3.Error) as error:
        if str(error) == AUTO_IMPORT_COMPLETED_LIST_RESULT_MISSING_REASON:
            emit_operational_log(
                title="自动导入候选结果缺失",
                detail=f"limit={limit} 错误={error}",
                fix_hint="检查 download_monitor 已完成列表查询返回是否仍带有完整结果；当前这轮自动导入会直接停路，避免把缺失真相误判成“当前没有可导入候选”。",
            )
        elif _is_auto_import_completed_row_corrupted_error(error):
            emit_operational_log(
                title="自动导入候选记录损坏",
                detail=f"limit={limit} 错误={error}",
                fix_hint="检查 download_monitor 已完成记录里的 chat_id / task_id / task_hash 等字段是否仍是完整真相；当前这轮自动导入会直接停路，避免把坏记录误判成普通读取失败后继续推进导入审批。",
            )
        else:
            emit_operational_log(
                title="自动导入候选读取失败",
                detail=f"limit={limit} 错误={error}",
                fix_hint="检查 SQLite/download_monitor 表读取是否正常；当前这轮自动导入会直接跳过，但已完成下载可能暂时不会进入导入审批。",
            )
        raise AutoImportCompletedListUnavailableError(str(error)) from error
    return tuple(candidates)


async def run_auto_import_candidates(
    *,
    candidates: Sequence[DownloadMonitorRecord],
    run_for_record: AutoImportRecordRunner,
    count_as_progress: AutoImportProgressPredicate,
    state_unavailable_error: type[BaseException],
) -> AutoImportBatchProgress:
    replies: list[str] = []
    notifications: list[AutoImportNotification] = []
    progressed = 0
    state_unavailable = False

    for candidate in candidates:
        try:
            reply = await run_for_record(candidate)
        except state_unavailable_error:
            state_unavailable = True
            continue
        if reply is None:
            continue
        replies.append(reply)
        if candidate.chat_id > 0:
            for text in _build_auto_import_notification_texts(reply):
                notifications.append(AutoImportNotification(chat_id=candidate.chat_id, text=text))
        if count_as_progress(candidate, reply):
            progressed += 1

    return AutoImportBatchProgress(
        progressed=progressed,
        replies=tuple(replies),
        notifications=tuple(notifications),
        state_unavailable=state_unavailable,
    )


def _is_auto_import_completed_row_corrupted_error(error: Exception) -> bool:
    return isinstance(error, DownloadMonitorPersistenceError) and str(error).endswith("corrupted after read")


def _is_auto_import_skip_event_row_corrupted_error(error: Exception) -> bool:
    return isinstance(error, JobEventPersistenceError) and str(error).endswith("corrupted after read")


def _build_auto_import_notification_texts(reply: str) -> tuple[str, ...]:
    stripped_reply = reply.strip()
    if not stripped_reply:
        return ()

    import_text, summary_text = _split_auto_import_summary(stripped_reply)
    if not import_text or not summary_text:
        return (stripped_reply,)

    subtitle_text = _extract_stage_notification_text(
        summary_text=summary_text,
        source_label="字幕",
        notification_label="字幕翻译",
    )
    refresh_text = _extract_stage_notification_text(
        summary_text=summary_text,
        source_label="刷新",
        notification_label="媒体库刷新",
    )
    if not subtitle_text or not refresh_text:
        return (stripped_reply,)
    return (import_text, subtitle_text, refresh_text, summary_text)


def _split_auto_import_summary(reply: str) -> tuple[str, str]:
    marker = "\n\n后处理总结\n"
    if marker not in reply:
        return reply, ""
    import_text, _, summary_tail = reply.partition(marker)
    cleaned_import_text = import_text.strip()
    cleaned_summary_tail = summary_tail.strip()
    if not cleaned_import_text or not cleaned_summary_tail:
        return reply, ""
    return cleaned_import_text, f"后处理总结\n{cleaned_summary_tail}"


def _extract_stage_notification_text(
    *,
    summary_text: str,
    source_label: str,
    notification_label: str,
) -> str:
    prefix = f"- {source_label}："
    for line in summary_text.splitlines():
        stripped_line = line.strip()
        if not stripped_line.startswith(prefix):
            continue
        suffix = stripped_line.removeprefix(prefix).strip()
        if not suffix:
            return notification_label
        return f"{notification_label}：{suffix}"
    return ""


def _log_auto_import_terminal_lookup_failed(*, task_id: str, task_hash: str, reason: str) -> None:
    emit_operational_log(
        title="自动导入终态查询失败",
        detail=_auto_import_event_detail(task_id=task_id, task_hash=task_hash, reason=reason),
        fix_hint="检查 SQLite/job_event 表读取是否正常；当前会停止这条任务的自动导入跟进，避免把读取异常误判成“还没有终态事件”。",
    )


def _log_auto_import_terminal_lookup_result_missing(*, task_id: str, task_hash: str, reason: str) -> None:
    emit_operational_log(
        title="自动导入终态结果缺失",
        detail=_auto_import_event_detail(task_id=task_id, task_hash=task_hash, reason=reason),
        fix_hint="检查 job_event 查询返回是否仍带有完整结果；当前会停止这条任务的自动导入跟进，避免把缺失真相误判成“还没有终态事件”。",
    )


def _log_auto_import_terminal_lookup_row_corrupted(*, task_id: str, task_hash: str, reason: str) -> None:
    emit_operational_log(
        title="自动导入终态记录损坏",
        detail=_auto_import_event_detail(task_id=task_id, task_hash=task_hash, reason=reason),
        fix_hint="检查 job_event 终态记录里的 task_ref / event_type 等字段是否仍是完整真相；当前会停止这条任务的自动导入跟进，避免把坏记录误判成普通查询失败。",
    )


def _log_auto_import_skip_event_append_failed(*, task_id: str, task_hash: str, reason: str) -> None:
    emit_operational_log(
        title="自动导入跳过事件落盘失败",
        detail=_auto_import_event_detail(
            task_id=task_id,
            task_hash=task_hash,
            reason=reason,
            event_type=AUTO_IMPORT_SKIPPED_BY_RULE_EVENT,
        ),
        fix_hint="检查 SQLite/job_event 表写入是否正常；当前会按状态不可用停路，避免把落盘异常误判成普通“已跳过自动导入”。",
    )


def _log_auto_import_skip_event_result_missing(*, task_id: str, task_hash: str, reason: str) -> None:
    emit_operational_log(
        title="自动导入跳过事件结果缺失",
        detail=_auto_import_event_detail(
            task_id=task_id,
            task_hash=task_hash,
            reason=reason,
            event_type=AUTO_IMPORT_SKIPPED_BY_RULE_EVENT,
        ),
        fix_hint="检查 job_event 写入后是否还能立即回读到该条跳过事件；当前会按状态不可用停路，避免把缺失真相误判成普通“已跳过自动导入”。",
    )


def _log_auto_import_skip_event_row_corrupted(*, task_id: str, task_hash: str, reason: str) -> None:
    emit_operational_log(
        title="自动导入跳过事件记录损坏",
        detail=_auto_import_event_detail(
            task_id=task_id,
            task_hash=task_hash,
            reason=reason,
            event_type=AUTO_IMPORT_SKIPPED_BY_RULE_EVENT,
        ),
        fix_hint="检查 job_event 新写入的跳过事件里 task_ref / event_type 等字段是否仍是完整真相；当前会按状态不可用停路，避免把坏记录误判成普通“已跳过自动导入”。",
    )


def _auto_import_event_detail(
    *,
    task_id: str,
    task_hash: str,
    reason: str,
    event_type: str = "",
) -> str:
    event_detail = f" event_type={event_type}" if event_type else ""
    return f"task_id={task_id} task_hash={task_hash}{event_detail} 错误={reason}"

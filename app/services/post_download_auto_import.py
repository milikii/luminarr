from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.db.download_monitor_repo import DownloadMonitorRecord, DownloadMonitorRepo
from app.db.job_event_repo import JobEventRepo

AutoImportFunc = Callable[[str, int | None, int | None], Awaitable[str]]
AUTO_IMPORT_SKIPPED_BY_RULE_EVENT = "auto_import.skipped_by_rule"
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
class AutoImportRunResult:
    scanned: int
    progressed: int
    replies: tuple[str, ...]


class AutoImportStateUnavailableError(RuntimeError):
    pass


class PostDownloadAutoImportService:
    def __init__(
        self,
        download_monitor_repo: DownloadMonitorRepo,
        job_event_repo: JobEventRepo,
        auto_import_func: AutoImportFunc,
    ) -> None:
        self._download_monitor_repo = download_monitor_repo
        self._job_event_repo = job_event_repo
        self._auto_import_func = auto_import_func

    async def run_once(self, *, limit: int = 20) -> AutoImportRunResult:
        try:
            candidates = self._download_monitor_repo.list_completed_for_auto_import(limit=limit)
        except Exception as error:
            print(
                f"\033[31m[自动导入候选读取失败]\033[0m limit={limit} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/download_monitor 表读取是否正常；当前这轮自动导入会直接跳过，但已完成下载可能暂时不会进入导入审批。",
                flush=True,
            )
            return AutoImportRunResult(scanned=0, progressed=0, replies=())
        replies: list[str] = []
        progressed = 0

        for candidate in candidates:
            blocked_reason = _match_low_quality_reason(candidate.name)
            try:
                reply = await self.run_for_record(candidate)
            except AutoImportStateUnavailableError:
                continue
            if reply is None:
                continue
            replies.append(reply)
            if blocked_reason is None:
                progressed += 1

        return AutoImportRunResult(
            scanned=len(candidates),
            progressed=progressed,
            replies=tuple(replies),
        )

    async def run_for_record(self, candidate: DownloadMonitorRecord) -> str | None:
        if not candidate.is_complete:
            return None
        if candidate.chat_id <= 0:
            print(
                f"\033[31m[自动导入聊天身份无效]\033[0m task_id={candidate.task_id} task_hash={candidate.task_hash} chat_id={candidate.chat_id} user_id={candidate.user_id}\n\033[33m[处理建议]\033[0m 检查 SQLite/download_monitor 表里的归属聊天身份是否完整；当前不会推进自动导入，避免把坏身份任务继续送入导入审批链。",
                flush=True,
            )
            raise AutoImportStateUnavailableError(
                f"auto import chat identity invalid for {candidate.task_id}/{candidate.task_hash}"
            )
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

    def _has_terminal_activity(self, candidate: DownloadMonitorRecord) -> bool:
        try:
            events = self._job_event_repo.list_events_for_task_identity(
                task_id=candidate.task_id,
                task_hash=candidate.task_hash,
            )
        except Exception as error:
            print(
                f"\033[31m[自动导入终态查询失败]\033[0m task_id={candidate.task_id} task_hash={candidate.task_hash} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/job_event 表读取是否正常；当前会停止这条任务的自动导入跟进，避免把读取异常误判成“还没有终态事件”。",
                flush=True,
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
        except Exception as error:
            print(
                f"\033[31m[自动导入跳过事件落盘失败]\033[0m task_id={candidate.task_id} task_hash={candidate.task_hash} event_type={AUTO_IMPORT_SKIPPED_BY_RULE_EVENT} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/job_event 表写入是否正常；当前请求仍会返回“已跳过自动导入”，但这次跳过原因可能没有落盘。",
                flush=True,
            )


def _match_low_quality_reason(name: str) -> str | None:
    cleaned_name = name.strip()
    if not cleaned_name:
        return None
    for pattern, label in _LOW_QUALITY_PATTERNS:
        if pattern.search(cleaned_name):
            return label
    return None

from __future__ import annotations

import re
import shutil
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.db.download_monitor_repo import DownloadMonitorPersistenceError, DownloadMonitorRepo
from app.db.job_event_repo import JobEventPersistenceError, JobEventRepo
from app.db.job_repo import JobRepo
from app.operational_logging import emit_operational_log
from app.services.cleanup_correlation_lookup import CleanupCorrelationLookup

CLEANUP_QUERY_USAGE_TEXT = (
    "cleanup 用法：\n"
    "cleanup <任务ID或Hash> / 清理 <任务ID或Hash>：实际清理下载源资产\n"
    "cleanup inspect <任务ID或Hash> / 清理检查 <任务ID或Hash>：只读预检，不删除任何文件"
)
CLEANUP_INSPECT_QUERY_USAGE_TEXT = (
    "cleanup inspect 用法：\n"
    "cleanup inspect <任务ID或Hash> / 清理检查 <任务ID或Hash>：只读预检，不删除任何文件\n"
    "cleanup <任务ID或Hash> / 清理 <任务ID或Hash>：实际清理下载源资产"
)
CLEANUP_CORRELATION_MISSING_TEXT = "未找到带 source_path/target_path 的已导入关联，当前任务暂不能执行 cleanup。"
CLEANUP_TARGET_MISSING_TEXT = "库内目标路径不存在，已拒绝清理下载源资产：{target_path}"
CLEANUP_SOURCE_MISSING_TEXT = "下载源资产已不存在，无需清理：{source_path}"
CLEANUP_SOURCE_TYPE_UNSUPPORTED_TEXT = "下载源不是文件或目录，无法清理。"
CLEANUP_GUARD_REJECTED_TEXT = "检测到 source/target 路径关系异常，已拒绝清理：{source_path} -> {target_path}"
CLEANUP_FAILED_TEXT = "清理下载源资产失败：{reason}"
CLEANUP_PT_SEED_WINDOW_BLOCKED_TEMPLATE = (
    "PT 最小保护窗口未满，已拒绝 cleanup：当前完成观察仅过去 {elapsed_hours:.1f} 小时，要求至少 {required_hours} 小时。"
)
CLEANUP_PT_SEED_WINDOW_STATE_UNAVAILABLE_TEXT = (
    "PT 最小保护窗口真相不可用，已拒绝 cleanup：缺少下载完成观察时间，请先刷新下载状态。"
)
CLEANUP_FOLLOW_UP_TEMPLATE = (
    "如需复核，可先执行只读预检：\n"
    "cleanup inspect {task_ref} / 清理检查 {task_ref}：只读预检，不删除任何文件\n"
    "cleanup {task_ref} / 清理 {task_ref}：实际清理下载源资产"
)
CLEANUP_SUCCESS_FOLLOW_UP_TEMPLATE = (
    "如需复核当前结果，可执行只读预检：\n"
    "cleanup inspect {task_ref} / 清理检查 {task_ref}：只读预检，不删除任何文件"
)
CLEANUP_INSPECT_READY_FOLLOW_UP_TEMPLATE = (
    "下一步：\n"
    "cleanup {task_ref} / 清理 {task_ref}：实际清理下载源资产"
)
CLEANUP_INSPECT_BLOCKED_FOLLOW_UP_TEMPLATE = (
    "下一步：\n"
    "当前先不要执行 cleanup；如需后续复核，可再次运行 cleanup inspect {task_ref} / 清理检查 {task_ref}"
)
CLEANUP_INSPECT_RESULT_TEMPLATE = (
    "清理预检结果：\n"
    "查询引用: {query_ref}\n"
    "任务 ID: {task_id}\n"
    "任务 Hash: {task_hash}\n"
    "关联: {correlation_status}\n"
    "源路径: {source_path}\n"
    "源路径状态: {source_status}\n"
    "目标路径: {target_path}\n"
    "目标路径状态: {target_status}\n"
    "当前 guardrail: {guardrail_status}\n"
    "结论: {conclusion}"
)
CLEANUP_SUCCEEDED_TEXT = (
    "已清理下载源资产。\n"
    "任务 ID: {task_id}\n"
    "任务 Hash: {task_hash}\n"
    "源路径: {source_path}\n"
    "保留目标: {target_path}"
)
CLEANUP_CORRELATION_MISSING_FIX_HINT = (
    "检查 import.succeeded 事件是否已写入 source_path/target_path，"
    "并先执行 cleanup inspect <任务ID或Hash> / 清理检查 <任务ID或Hash> 复核关联。"
)
CLEANUP_TARGET_MISSING_FIX_HINT = "检查库内目标路径是否已被移动或删除；目标不存在时不要执行 cleanup。"
CLEANUP_SOURCE_MISSING_FIX_HINT = "下载源资产已经不存在，当前无需 cleanup；如需复核可再次执行 cleanup inspect。"
CLEANUP_SOURCE_TYPE_UNSUPPORTED_FIX_HINT = (
    "检查 source_path 是否误指到管道、套接字、失效链接等非常规类型；"
    "修正导入关联后再重试 cleanup。"
)
CLEANUP_GUARD_REJECTED_FIX_HINT = (
    "检查 source_path 和 target_path 是否指向同一位置或互为父子目录，确认导入关联无误后再重试。"
)
CLEANUP_PT_SEED_WINDOW_BLOCKED_FIX_HINT = (
    "等待 PT 最小保护窗口到期后再执行 cleanup；如需刷新当前观察时间，先发送 status <任务ID或Hash>。"
)
CLEANUP_PT_SEED_WINDOW_STATE_UNAVAILABLE_FIX_HINT = (
    "先发送 status <任务ID或Hash> 刷新下载完成观察；若仍缺少 completion_observed_at，再检查 download_monitor 真相。"
)
CLEANUP_EVENT_RESULT_MISSING_REASON = "job_event missing after append"
_SQLITE_UTC_FORMAT = "%Y-%m-%d %H:%M:%S"


@dataclass(frozen=True, slots=True)
class CleanupInspection:
    query_ref: str
    task_ref: str
    task_id: str
    task_hash: str
    source_path: str
    target_path: str
    correlation_found: bool
    source_exists: bool | None
    target_exists: bool | None
    cleanup_allowed: bool
    conclusion: str


@dataclass(frozen=True, slots=True)
class CleanupBlockedOutcome:
    event_type: str
    message: str
    fix_hint: str
    source_path: str = ""
    target_path: str = ""


@dataclass(frozen=True, slots=True)
class CleanupDeleteExecutionResult:
    success: bool
    event_type: str
    message: str
    failure_reason: str = ""


@dataclass(frozen=True, slots=True)
class CleanupFlowResult:
    message: str


class CleanupDownloadedSourceService:
    def __init__(
        self,
        job_event_repo: JobEventRepo,
        job_repo: JobRepo | None = None,
        download_monitor_repo: DownloadMonitorRepo | None = None,
        pt_min_seed_hours: int = 0,
    ) -> None:
        self._job_event_repo = job_event_repo
        self._download_monitor_repo = download_monitor_repo
        self._pt_min_seed_hours = max(0, pt_min_seed_hours)
        self._correlation_lookup = CleanupCorrelationLookup(
            job_event_repo=job_event_repo,
            job_repo=job_repo,
        )

    def cleanup_by_task_ref(
        self,
        task_ref: str,
        *,
        chat_id: int | None = None,
    ) -> str:
        return run_cleanup_flow(
            task_ref=task_ref,
            chat_id=chat_id,
            query_usage_text=CLEANUP_QUERY_USAGE_TEXT,
            inspect_cleanup=lambda resolved_task_ref, resolved_chat_id: self._inspect_cleanup(
                task_ref=resolved_task_ref,
                chat_id=resolved_chat_id,
            ),
            preferred_cleanup_ref=preferred_cleanup_ref,
            resolve_blocked_outcome=lambda inspection, follow_up_ref: resolve_cleanup_blocked_outcome(
                inspection=inspection,
                follow_up_ref=follow_up_ref,
                correlation_missing_text=CLEANUP_CORRELATION_MISSING_TEXT,
                correlation_missing_fix_hint=CLEANUP_CORRELATION_MISSING_FIX_HINT,
                target_missing_fix_hint=CLEANUP_TARGET_MISSING_FIX_HINT,
                source_missing_fix_hint=CLEANUP_SOURCE_MISSING_FIX_HINT,
                pt_seed_window_state_unavailable_text=CLEANUP_PT_SEED_WINDOW_STATE_UNAVAILABLE_TEXT,
                pt_seed_window_blocked_fix_hint=CLEANUP_PT_SEED_WINDOW_BLOCKED_FIX_HINT,
                pt_seed_window_state_unavailable_fix_hint=CLEANUP_PT_SEED_WINDOW_STATE_UNAVAILABLE_FIX_HINT,
                source_type_unsupported_text=CLEANUP_SOURCE_TYPE_UNSUPPORTED_TEXT,
                source_type_unsupported_fix_hint=CLEANUP_SOURCE_TYPE_UNSUPPORTED_FIX_HINT,
                guard_rejected_fix_hint=CLEANUP_GUARD_REJECTED_FIX_HINT,
                follow_up_template=CLEANUP_FOLLOW_UP_TEMPLATE,
            ),
            record_event=lambda task_ref_for_event, inspection, event_type, message, source_path, target_path: self._record_event(
                task_ref=task_ref_for_event,
                task_id=inspection.task_id,
                task_hash=inspection.task_hash,
                event_type=event_type,
                message=message,
                source_path=source_path,
                target_path=target_path,
            ),
            log_blocked=lambda task_ref_for_event, inspection, event_type, fix_hint, source_path, target_path: print_cleanup_blocked_log(
                event_type=event_type,
                task_ref=task_ref_for_event,
                task_id=inspection.task_id,
                task_hash=inspection.task_hash,
                source_path=source_path,
                target_path=target_path,
                reason=inspection.conclusion,
                fix_hint=fix_hint,
            ),
            execute_delete=lambda source_path, target_path, inspection, follow_up_ref: execute_cleanup_delete(
                delete_source_asset=_delete_source_asset,
                source_path=source_path,
                target_path=target_path,
                task_id=inspection.task_id,
                task_hash=inspection.task_hash,
                follow_up_ref=follow_up_ref,
                cleanup_failed_text=CLEANUP_FAILED_TEXT,
                cleanup_succeeded_text=CLEANUP_SUCCEEDED_TEXT,
                follow_up_template=CLEANUP_FOLLOW_UP_TEMPLATE,
                success_follow_up_template=CLEANUP_SUCCESS_FOLLOW_UP_TEMPLATE,
            ),
            log_delete_failed=lambda task_ref_for_event, inspection, source_path, target_path, delete_result: print_cleanup_delete_failed_log(
                task_ref=task_ref_for_event,
                event_type=delete_result.event_type,
                task_id=inspection.task_id,
                task_hash=inspection.task_hash,
                source_path=str(source_path),
                target_path=str(target_path),
                failure_reason=delete_result.failure_reason,
            ),
        ).message

    def inspect_by_task_ref(
        self,
        task_ref: str,
        *,
        chat_id: int | None = None,
    ) -> str:
        cleaned_ref = task_ref.strip()
        if not cleaned_ref:
            return CLEANUP_INSPECT_QUERY_USAGE_TEXT
        inspection = self._inspect_cleanup(task_ref=cleaned_ref, chat_id=chat_id)
        return render_cleanup_inspect_message(
            inspection=inspection,
            inspect_result_template=CLEANUP_INSPECT_RESULT_TEMPLATE,
            inspect_ready_follow_up_template=CLEANUP_INSPECT_READY_FOLLOW_UP_TEMPLATE,
            inspect_blocked_follow_up_template=CLEANUP_INSPECT_BLOCKED_FOLLOW_UP_TEMPLATE,
        )

    def _inspect_cleanup(
        self,
        *,
        task_ref: str,
        chat_id: int | None,
    ) -> CleanupInspection:
        resolved_identity, correlation = self._correlation_lookup.find_import_correlation(
            task_ref=task_ref,
            chat_id=chat_id,
        )
        return build_cleanup_inspection(
            task_ref=task_ref,
            resolved_identity=resolved_identity,
            correlation=correlation,
            correlation_missing_text=CLEANUP_CORRELATION_MISSING_TEXT,
            target_missing_text=CLEANUP_TARGET_MISSING_TEXT,
            source_missing_text=CLEANUP_SOURCE_MISSING_TEXT,
            validate_cleanup_paths=lambda source_path, target_path: _validate_cleanup_paths(
                source_path=source_path,
                target_path=target_path,
            ),
            evaluate_pt_seed_window=lambda resolved_task_ref, task_id, task_hash: self._evaluate_pt_seed_window(
                task_ref=resolved_task_ref,
                task_id=task_id,
                task_hash=task_hash,
            ),
        )

    def _record_event(
        self,
        *,
        task_ref: str,
        event_type: str,
        message: str,
        task_id: str = "",
        task_hash: str = "",
        source_path: str = "",
        target_path: str = "",
    ) -> None:
        try:
            self._job_event_repo.append_event(
                task_ref=task_ref,
                task_id=task_id,
                task_hash=task_hash,
                event_type=event_type,
                message=message,
                source_path=source_path,
                target_path=target_path,
            )
        except (JobEventPersistenceError, sqlite3.Error) as error:
            if str(error) == CLEANUP_EVENT_RESULT_MISSING_REASON:
                print_cleanup_event_append_result_missing_log(
                    task_ref=task_ref,
                    event_type=event_type,
                    task_id=task_id,
                    task_hash=task_hash,
                    source_path=source_path,
                    target_path=target_path,
                    reason="cleanup event missing after append",
                )
                return
            if _is_cleanup_event_row_corrupted_error(error):
                print_cleanup_event_append_row_corrupted_log(
                    task_ref=task_ref,
                    event_type=event_type,
                    task_id=task_id,
                    task_hash=task_hash,
                    source_path=source_path,
                    target_path=target_path,
                    reason=str(error),
                )
                return
            print_cleanup_event_append_failed_log(
                task_ref=task_ref,
                event_type=event_type,
                task_id=task_id,
                task_hash=task_hash,
                source_path=source_path,
                target_path=target_path,
                error=error,
            )

    def _evaluate_pt_seed_window(
        self,
        *,
        task_ref: str,
        task_id: str,
        task_hash: str,
    ) -> str | None:
        return evaluate_cleanup_pt_seed_window(
            task_ref=task_ref,
            task_id=task_id,
            task_hash=task_hash,
            pt_min_seed_hours=self._pt_min_seed_hours,
            download_monitor_repo=self._download_monitor_repo,
            sqlite_utc_format=_SQLITE_UTC_FORMAT,
            state_unavailable_text=CLEANUP_PT_SEED_WINDOW_STATE_UNAVAILABLE_TEXT,
            blocked_template=CLEANUP_PT_SEED_WINDOW_BLOCKED_TEMPLATE,
            on_state_unavailable=lambda reason: print_cleanup_pt_seed_guard_state_unavailable_log(
                task_ref=task_ref,
                task_id=task_id,
                task_hash=task_hash,
                reason=reason,
                state_unavailable_fix_hint=CLEANUP_PT_SEED_WINDOW_STATE_UNAVAILABLE_FIX_HINT,
            ),
            on_lookup_failed=lambda error: print_cleanup_pt_seed_guard_lookup_failed_log(
                task_ref=task_ref,
                task_id=task_id,
                task_hash=task_hash,
                error=error,
                state_unavailable_fix_hint=CLEANUP_PT_SEED_WINDOW_STATE_UNAVAILABLE_FIX_HINT,
            ),
        )


def _is_cleanup_event_row_corrupted_error(error: Exception) -> bool:
    return isinstance(error, JobEventPersistenceError) and str(error).endswith("corrupted after read")


def parse_cleanup_query(text: str) -> str | None:
    cleaned_text = text.strip()
    matched = re.match(r"^(?:(?i:cleanup)|清理)(?:\s+(.*))?$", cleaned_text)
    if not matched:
        return None
    return (matched.group(1) or "").strip()


def parse_cleanup_inspect_query(text: str) -> str | None:
    cleaned_text = text.strip()
    matched = re.match(r"^(?:(?i:cleanup)\s+(?i:inspect)|清理检查)(?:\s+(.*))?$", cleaned_text)
    if not matched:
        return None
    return (matched.group(1) or "").strip()


def _validate_cleanup_paths(*, source_path: Path, target_path: Path) -> str | None:
    if not source_path.is_file() and not source_path.is_dir():
        return CLEANUP_SOURCE_TYPE_UNSUPPORTED_TEXT

    source_resolved = source_path.resolve(strict=False)
    target_resolved = target_path.resolve(strict=False)
    if (
        source_resolved == target_resolved
        or source_resolved in target_resolved.parents
        or target_resolved in source_resolved.parents
    ):
        return CLEANUP_GUARD_REJECTED_TEXT.format(
            source_path=str(source_path),
            target_path=str(target_path),
        )
    return None


def _delete_source_asset(source_path: Path) -> None:
    if source_path.is_dir():
        shutil.rmtree(source_path)
        return
    if source_path.is_file():
        source_path.unlink()
        return
    raise OSError(CLEANUP_SOURCE_TYPE_UNSUPPORTED_TEXT)


def build_cleanup_inspection(
    *,
    task_ref: str,
    resolved_identity: Any,
    correlation: Any,
    correlation_missing_text: str,
    target_missing_text: str,
    source_missing_text: str,
    validate_cleanup_paths: Callable[[Path, Path], str | None],
    evaluate_pt_seed_window: Callable[[str, str, str], str | None],
) -> CleanupInspection:
    if correlation is None:
        return CleanupInspection(
            query_ref=task_ref,
            task_ref=resolved_identity.task_ref,
            task_id=resolved_identity.task_id,
            task_hash=resolved_identity.task_hash,
            source_path="",
            target_path="",
            correlation_found=False,
            source_exists=None,
            target_exists=None,
            cleanup_allowed=False,
            conclusion=correlation_missing_text,
        )

    source_path = Path(correlation.source_path).expanduser()
    target_path = Path(correlation.target_path).expanduser()
    target_exists = target_path.exists()
    source_exists = source_path.exists()

    if not target_exists:
        conclusion = target_missing_text.format(target_path=str(target_path))
        cleanup_allowed = False
    elif not source_exists:
        conclusion = source_missing_text.format(source_path=str(source_path))
        cleanup_allowed = False
    else:
        guard_rejection = validate_cleanup_paths(source_path, target_path)
        if guard_rejection is not None:
            conclusion = guard_rejection
            cleanup_allowed = False
        else:
            pt_seed_guard_conclusion = evaluate_pt_seed_window(
                correlation.task_ref.strip() or resolved_identity.task_ref or task_ref,
                correlation.task_id.strip() or resolved_identity.task_id,
                correlation.task_hash.strip() or resolved_identity.task_hash,
            )
            if pt_seed_guard_conclusion is not None:
                conclusion = pt_seed_guard_conclusion
                cleanup_allowed = False
            else:
                conclusion = "已通过 cleanup 预检，可执行清理下载源资产。"
                cleanup_allowed = True

    return CleanupInspection(
        query_ref=task_ref,
        task_ref=correlation.task_ref.strip() or resolved_identity.task_ref,
        task_id=correlation.task_id.strip() or resolved_identity.task_id,
        task_hash=correlation.task_hash.strip() or resolved_identity.task_hash,
        source_path=str(source_path),
        target_path=str(target_path),
        correlation_found=True,
        source_exists=source_exists,
        target_exists=target_exists,
        cleanup_allowed=cleanup_allowed,
        conclusion=conclusion,
    )


def preferred_cleanup_ref(inspection: CleanupInspection) -> str:
    for value in (inspection.task_hash, inspection.task_id, inspection.task_ref, inspection.query_ref):
        cleaned_value = value.strip()
        if cleaned_value:
            return cleaned_value
    return inspection.query_ref


def resolve_cleanup_blocked_event_details(
    *,
    inspection: CleanupInspection,
    pt_seed_window_state_unavailable_text: str,
    pt_seed_window_blocked_fix_hint: str,
    pt_seed_window_state_unavailable_fix_hint: str,
    source_type_unsupported_text: str,
    source_type_unsupported_fix_hint: str,
    guard_rejected_fix_hint: str,
) -> tuple[str, str]:
    if inspection.conclusion.startswith("PT 最小保护窗口未满"):
        return "cleanup.pt_seed_window_blocked", pt_seed_window_blocked_fix_hint
    if inspection.conclusion == pt_seed_window_state_unavailable_text:
        return "cleanup.pt_seed_window_state_unavailable", pt_seed_window_state_unavailable_fix_hint
    if inspection.conclusion == source_type_unsupported_text:
        return "cleanup.source_type_unsupported", source_type_unsupported_fix_hint
    return "cleanup.guard_rejected", guard_rejected_fix_hint


def append_cleanup_follow_up(message: str, task_ref: str, follow_up_template: str) -> str:
    cleaned_ref = task_ref.strip()
    if not cleaned_ref:
        return message
    return f"{message}\n{follow_up_template.format(task_ref=cleaned_ref)}"


def append_cleanup_success_follow_up(message: str, task_ref: str, success_follow_up_template: str) -> str:
    cleaned_ref = task_ref.strip()
    if not cleaned_ref:
        return message
    return f"{message}\n{success_follow_up_template.format(task_ref=cleaned_ref)}"


def format_cleanup_inspect_follow_up(
    inspection: CleanupInspection,
    *,
    inspect_ready_follow_up_template: str,
    inspect_blocked_follow_up_template: str,
) -> str:
    task_ref = preferred_cleanup_ref(inspection).strip()
    if not task_ref:
        return ""
    if inspection.cleanup_allowed:
        return inspect_ready_follow_up_template.format(task_ref=task_ref)
    return inspect_blocked_follow_up_template.format(task_ref=task_ref)


def resolve_cleanup_blocked_outcome(
    *,
    inspection: CleanupInspection,
    follow_up_ref: str,
    correlation_missing_text: str,
    correlation_missing_fix_hint: str,
    target_missing_fix_hint: str,
    source_missing_fix_hint: str,
    pt_seed_window_state_unavailable_text: str,
    pt_seed_window_blocked_fix_hint: str,
    pt_seed_window_state_unavailable_fix_hint: str,
    source_type_unsupported_text: str,
    source_type_unsupported_fix_hint: str,
    guard_rejected_fix_hint: str,
    follow_up_template: str,
) -> CleanupBlockedOutcome | None:
    if not inspection.correlation_found:
        return CleanupBlockedOutcome(
            event_type="cleanup.correlation_missing",
            message=append_cleanup_follow_up(
                correlation_missing_text,
                follow_up_ref,
                follow_up_template,
            ),
            fix_hint=correlation_missing_fix_hint,
        )

    if inspection.target_exists is False:
        return CleanupBlockedOutcome(
            event_type="cleanup.target_missing",
            message=append_cleanup_follow_up(inspection.conclusion, follow_up_ref, follow_up_template),
            fix_hint=target_missing_fix_hint,
            source_path=inspection.source_path,
            target_path=inspection.target_path,
        )

    if inspection.source_exists is False:
        return CleanupBlockedOutcome(
            event_type="cleanup.source_missing",
            message=append_cleanup_follow_up(inspection.conclusion, follow_up_ref, follow_up_template),
            fix_hint=source_missing_fix_hint,
            source_path=inspection.source_path,
            target_path=inspection.target_path,
        )

    if inspection.cleanup_allowed:
        return None

    event_type, fix_hint = resolve_cleanup_blocked_event_details(
        inspection=inspection,
        pt_seed_window_state_unavailable_text=pt_seed_window_state_unavailable_text,
        pt_seed_window_blocked_fix_hint=pt_seed_window_blocked_fix_hint,
        pt_seed_window_state_unavailable_fix_hint=pt_seed_window_state_unavailable_fix_hint,
        source_type_unsupported_text=source_type_unsupported_text,
        source_type_unsupported_fix_hint=source_type_unsupported_fix_hint,
        guard_rejected_fix_hint=guard_rejected_fix_hint,
    )
    return CleanupBlockedOutcome(
        event_type=event_type,
        message=append_cleanup_follow_up(inspection.conclusion, follow_up_ref, follow_up_template),
        fix_hint=fix_hint,
        source_path=inspection.source_path,
        target_path=inspection.target_path,
    )


def execute_cleanup_delete(
    *,
    delete_source_asset: Callable[[Path], None],
    source_path: Path,
    target_path: Path,
    task_id: str,
    task_hash: str,
    follow_up_ref: str,
    cleanup_failed_text: str,
    cleanup_succeeded_text: str,
    follow_up_template: str,
    success_follow_up_template: str,
) -> CleanupDeleteExecutionResult:
    try:
        delete_source_asset(source_path)
    except OSError as error:
        return CleanupDeleteExecutionResult(
            success=False,
            event_type="cleanup.failed",
            message=append_cleanup_follow_up(
                cleanup_failed_text.format(reason=str(error)),
                follow_up_ref,
                follow_up_template,
            ),
            failure_reason=str(error),
        )

    return CleanupDeleteExecutionResult(
        success=True,
        event_type="cleanup.succeeded",
        message=append_cleanup_success_follow_up(
            cleanup_succeeded_text.format(
                task_id=task_id,
                task_hash=task_hash,
                source_path=str(source_path),
                target_path=str(target_path),
            ),
            follow_up_ref,
            success_follow_up_template,
        ),
    )


def render_cleanup_inspect_message(
    *,
    inspection: CleanupInspection,
    inspect_result_template: str,
    inspect_ready_follow_up_template: str,
    inspect_blocked_follow_up_template: str,
) -> str:
    lines = [
        inspect_result_template.format(
            query_ref=inspection.query_ref,
            task_id=inspection.task_id or "-",
            task_hash=inspection.task_hash or "-",
            correlation_status="已找到" if inspection.correlation_found else "未找到",
            source_path=inspection.source_path or "-",
            source_status=_format_cleanup_path_status(inspection.source_exists),
            target_path=inspection.target_path or "-",
            target_status=_format_cleanup_path_status(inspection.target_exists),
            guardrail_status="允许 cleanup" if inspection.cleanup_allowed else "拒绝 cleanup",
            conclusion=inspection.conclusion,
        )
    ]
    if inspection.cleanup_allowed or inspection.correlation_found:
        lines.append(
            format_cleanup_inspect_follow_up(
                inspection,
                inspect_ready_follow_up_template=inspect_ready_follow_up_template,
                inspect_blocked_follow_up_template=inspect_blocked_follow_up_template,
            )
        )
    return "\n".join(lines)


def run_cleanup_flow(
    *,
    task_ref: str,
    query_usage_text: str,
    inspect_cleanup: Callable[[str, int | None], CleanupInspection],
    preferred_cleanup_ref: Callable[[CleanupInspection], str],
    resolve_blocked_outcome: Callable[[CleanupInspection, str], CleanupBlockedOutcome | None],
    record_event: Callable[[str, CleanupInspection, str, str, str, str], None],
    log_blocked: Callable[[str, CleanupInspection, str, str, str], None],
    execute_delete: Callable[[Path, Path, CleanupInspection, str], CleanupDeleteExecutionResult],
    log_delete_failed: Callable[[str, CleanupInspection, Path, Path, CleanupDeleteExecutionResult], None],
    chat_id: int | None = None,
) -> CleanupFlowResult:
    cleaned_ref = task_ref.strip()
    if not cleaned_ref:
        return CleanupFlowResult(message=query_usage_text)

    inspection = inspect_cleanup(cleaned_ref, chat_id)
    task_ref_for_event = inspection.task_ref or cleaned_ref
    follow_up_ref = preferred_cleanup_ref(inspection)
    blocked_outcome = resolve_blocked_outcome(inspection, follow_up_ref)
    if blocked_outcome is not None:
        record_event(
            task_ref_for_event,
            inspection,
            blocked_outcome.event_type,
            blocked_outcome.message,
            blocked_outcome.source_path,
            blocked_outcome.target_path,
        )
        log_blocked(
            task_ref_for_event,
            inspection,
            blocked_outcome.event_type,
            blocked_outcome.fix_hint,
            blocked_outcome.source_path,
            blocked_outcome.target_path,
        )
        return CleanupFlowResult(message=blocked_outcome.message)

    source_path = Path(inspection.source_path).expanduser()
    target_path = Path(inspection.target_path).expanduser()
    delete_result = execute_delete(source_path, target_path, inspection, follow_up_ref)
    record_event(
        task_ref_for_event,
        inspection,
        delete_result.event_type,
        delete_result.message,
        str(source_path),
        str(target_path),
    )
    if not delete_result.success:
        log_delete_failed(task_ref_for_event, inspection, source_path, target_path, delete_result)
    return CleanupFlowResult(message=delete_result.message)


def evaluate_cleanup_pt_seed_window(
    *,
    task_ref: str,
    task_id: str,
    task_hash: str,
    pt_min_seed_hours: int,
    download_monitor_repo: Any,
    sqlite_utc_format: str,
    state_unavailable_text: str,
    blocked_template: str,
    on_state_unavailable: Callable[[str], None],
    on_lookup_failed: Callable[[Exception], None],
) -> str | None:
    cleaned_task_ref = task_ref.strip().lower()
    if pt_min_seed_hours <= 0 or cleaned_task_ref.startswith("bt-"):
        return None
    if download_monitor_repo is None:
        on_state_unavailable("download_monitor_repo missing")
        return state_unavailable_text

    try:
        record = download_monitor_repo.get_record(task_id=task_id, task_hash=task_hash)
    except (DownloadMonitorPersistenceError, sqlite3.Error) as error:
        on_lookup_failed(error)
        return state_unavailable_text

    if record is None or not record.completion_observed_at.strip():
        on_state_unavailable("completion_observed_at missing")
        return state_unavailable_text

    try:
        completion_observed_at = datetime.strptime(record.completion_observed_at, sqlite_utc_format).replace(tzinfo=UTC)
    except ValueError:
        on_state_unavailable(f"invalid completion_observed_at: {record.completion_observed_at}")
        return state_unavailable_text

    elapsed_hours = max(0.0, (datetime.now(UTC) - completion_observed_at).total_seconds() / 3600.0)
    if elapsed_hours < float(pt_min_seed_hours):
        return blocked_template.format(
            elapsed_hours=elapsed_hours,
            required_hours=pt_min_seed_hours,
        )
    return None


def print_cleanup_blocked_log(
    *,
    event_type: str,
    task_ref: str,
    reason: str,
    fix_hint: str,
    task_id: str = "",
    task_hash: str = "",
    source_path: str = "",
    target_path: str = "",
) -> None:
    details = [f"task_ref={task_ref}", f"event_type={event_type}"]
    if task_id.strip():
        details.append(f"task_id={task_id}")
    if task_hash.strip():
        details.append(f"task_hash={task_hash}")
    if source_path.strip():
        details.append(f"source={source_path}")
    if target_path.strip():
        details.append(f"target={target_path}")
    details_text = " ".join(details)
    emit_operational_log(
        title="cleanup 执行受阻",
        detail=f"{details_text} 结论={reason}",
        fix_hint=fix_hint,
    )


def print_cleanup_event_append_failed_log(
    *,
    task_ref: str,
    event_type: str,
    error: Exception,
    task_id: str = "",
    task_hash: str = "",
    source_path: str = "",
    target_path: str = "",
) -> None:
    details = [f"task_ref={task_ref}", f"event_type={event_type}"]
    if task_id.strip():
        details.append(f"task_id={task_id}")
    if task_hash.strip():
        details.append(f"task_hash={task_hash}")
    if source_path.strip():
        details.append(f"source={source_path}")
    if target_path.strip():
        details.append(f"target={target_path}")
    details_text = " ".join(details)
    emit_operational_log(
        title="cleanup 事件写入失败",
        detail=f"{details_text} 原因={error}",
        fix_hint="检查 SQLite job_event 是否可写、磁盘是否只读或已满；当前 cleanup 文本结果已返回，但这次执行记录未成功落盘。",
    )


def print_cleanup_event_append_result_missing_log(
    *,
    task_ref: str,
    event_type: str,
    reason: str,
    task_id: str = "",
    task_hash: str = "",
    source_path: str = "",
    target_path: str = "",
) -> None:
    details = [f"task_ref={task_ref}", f"event_type={event_type}"]
    if task_id.strip():
        details.append(f"task_id={task_id}")
    if task_hash.strip():
        details.append(f"task_hash={task_hash}")
    if source_path.strip():
        details.append(f"source={source_path}")
    if target_path.strip():
        details.append(f"target={target_path}")
    details_text = " ".join(details)
    emit_operational_log(
        title="cleanup 事件结果缺失",
        detail=f"{details_text} 原因={reason}",
        fix_hint="检查 job_event 写入后回读是否仍能拿到刚追加的 cleanup 事件；当前 cleanup 文本结果已返回，但这次执行记录真相还没有确认落稳。",
    )


def print_cleanup_event_append_row_corrupted_log(
    *,
    task_ref: str,
    event_type: str,
    reason: str,
    task_id: str = "",
    task_hash: str = "",
    source_path: str = "",
    target_path: str = "",
) -> None:
    details = [f"task_ref={task_ref}", f"event_type={event_type}"]
    if task_id.strip():
        details.append(f"task_id={task_id}")
    if task_hash.strip():
        details.append(f"task_hash={task_hash}")
    if source_path.strip():
        details.append(f"source={source_path}")
    if target_path.strip():
        details.append(f"target={target_path}")
    details_text = " ".join(details)
    emit_operational_log(
        title="cleanup 事件记录损坏",
        detail=f"{details_text} 原因={reason}",
        fix_hint="检查 job_event 读回事件里的 task_ref / event_type / source_path / target_path 是否仍是完整真相；当前 cleanup 文本结果已返回，但不会把这条坏事件当成已稳定落盘。",
    )


def print_cleanup_pt_seed_guard_lookup_failed_log(
    *,
    task_ref: str,
    task_id: str,
    task_hash: str,
    error: Exception,
    state_unavailable_fix_hint: str,
) -> None:
    emit_operational_log(
        title="cleanup PT 保护查询失败",
        detail=f"task_ref={task_ref} task_id={task_id or '-'} task_hash={task_hash or '-'} 错误={error}",
        fix_hint=state_unavailable_fix_hint,
    )


def print_cleanup_pt_seed_guard_state_unavailable_log(
    *,
    task_ref: str,
    task_id: str,
    task_hash: str,
    reason: str,
    state_unavailable_fix_hint: str,
) -> None:
    emit_operational_log(
        title="cleanup PT 保护真相缺失",
        detail=f"task_ref={task_ref} task_id={task_id or '-'} task_hash={task_hash or '-'} 原因={reason}",
        fix_hint=state_unavailable_fix_hint,
    )


def print_cleanup_delete_failed_log(
    *,
    task_ref: str,
    event_type: str,
    task_id: str,
    task_hash: str,
    source_path: str,
    target_path: str,
    failure_reason: str,
) -> None:
    emit_operational_log(
        title="cleanup 执行失败",
        detail=(
            f"task_ref={task_ref} event_type={event_type} task_id={task_id} task_hash={task_hash} "
            f"source={source_path} target={target_path} 原因={failure_reason}"
        ),
        fix_hint="检查 source_path 是否仍可访问、当前进程是否有删除权限，并确认库内目标路径仍然存在后再重试 cleanup。",
    )


def _format_cleanup_path_status(exists: bool | None) -> str:
    if exists is None:
        return "未找到关联"
    if exists:
        return "存在"
    return "不存在"

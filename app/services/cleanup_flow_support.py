from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.services.cleanup_inspection_support import CleanupInspection


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


def _format_cleanup_path_status(exists: bool | None) -> str:
    if exists is None:
        return "未找到关联"
    if exists:
        return "存在"
    return "不存在"

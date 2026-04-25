from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.services.cleanup_execution_support import CleanupDeleteExecutionResult
from app.services.cleanup_inspection_support import CleanupInspection


@dataclass(frozen=True, slots=True)
class CleanupFlowResult:
    message: str


def run_cleanup_flow(
    *,
    task_ref: str,
    query_usage_text: str,
    inspect_cleanup: Callable[[str, int | None], CleanupInspection],
    preferred_cleanup_ref: Callable[[CleanupInspection], str],
    resolve_blocked_outcome: Callable[[CleanupInspection, str], object | None],
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

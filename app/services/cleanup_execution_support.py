from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.services.cleanup_follow_up_support import append_cleanup_follow_up, append_cleanup_success_follow_up


@dataclass(frozen=True, slots=True)
class CleanupDeleteExecutionResult:
    success: bool
    event_type: str
    message: str
    failure_reason: str = ""


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

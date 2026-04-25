from __future__ import annotations

from app.db.job_event_repo import JobEventRepo

from app.services.cleanup_downloaded_source import (
    CLEANUP_EVENT_RESULT_MISSING_REASON,
    _is_cleanup_event_row_corrupted_error,
)
from app.services.cleanup_logging_support import (
    print_cleanup_event_append_failed_log,
    print_cleanup_event_append_result_missing_log,
    print_cleanup_event_append_row_corrupted_log,
)


def append_cleanup_event(
    *,
    job_event_repo: JobEventRepo,
    task_ref: str,
    event_type: str,
    message: str,
    task_id: str = "",
    task_hash: str = "",
    source_path: str = "",
    target_path: str = "",
) -> None:
    try:
        job_event_repo.append_event(
            task_ref=task_ref,
            task_id=task_id,
            task_hash=task_hash,
            event_type=event_type,
            message=message,
            source_path=source_path,
            target_path=target_path,
        )
    except Exception as error:
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

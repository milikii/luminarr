from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CleanupCorrelationResult:
    task_ref: str
    task_id: str
    task_hash: str
    source_path: str
    target_path: str


def build_cleanup_correlation_result(
    *,
    event: object,
    fallback_task_ref: str,
    fallback_task_id: str,
    fallback_task_hash: str,
    on_path_missing: Callable[[bool, bool], None],
) -> CleanupCorrelationResult | None:
    source_path = str(getattr(event, "source_path", "")).strip()
    target_path = str(getattr(event, "target_path", "")).strip()
    if not source_path or not target_path:
        on_path_missing(not source_path, not target_path)
        return None

    return CleanupCorrelationResult(
        task_ref=str(getattr(event, "task_ref", "")).strip() or fallback_task_ref,
        task_id=str(getattr(event, "task_id", "")).strip() or fallback_task_id,
        task_hash=str(getattr(event, "task_hash", "")).strip() or fallback_task_hash,
        source_path=source_path,
        target_path=target_path,
    )

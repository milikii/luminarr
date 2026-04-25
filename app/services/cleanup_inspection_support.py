from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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

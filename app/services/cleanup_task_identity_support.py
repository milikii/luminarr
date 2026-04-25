from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CleanupTaskIdentityResolution:
    lookup_task_ref: str
    lookup_task_id: str
    lookup_task_hash: str
    task_ref: str
    task_id: str
    task_hash: str


def resolve_cleanup_task_identity(
    *,
    task_ref: str,
    chat_id: int | None,
    job_lookup: Callable[[int, str], Any | None] | None,
    on_job_lookup_failed: Callable[[Exception], None],
) -> CleanupTaskIdentityResolution:
    resolved_task_ref = task_ref
    resolved_task_id = ""
    resolved_task_hash = ""
    lookup_task_ref = task_ref
    lookup_task_id = task_ref
    lookup_task_hash = task_ref

    if job_lookup is not None and chat_id is not None and chat_id > 0:
        try:
            job = job_lookup(chat_id, task_ref)
        except Exception as error:
            on_job_lookup_failed(error)
            job = None
        if job is not None:
            resolved_task_ref = (getattr(job, "task_ref", "") or task_ref).strip() or resolved_task_ref
            resolved_task_id = str(getattr(job, "task_id", "") or "").strip()
            resolved_task_hash = str(getattr(job, "task_hash", "") or "").strip()
            lookup_task_ref = resolved_task_ref
            lookup_task_id = resolved_task_id or lookup_task_id
            lookup_task_hash = resolved_task_hash or lookup_task_hash

    return CleanupTaskIdentityResolution(
        lookup_task_ref=lookup_task_ref,
        lookup_task_id=lookup_task_id,
        lookup_task_hash=lookup_task_hash,
        task_ref=resolved_task_ref,
        task_id=resolved_task_id,
        task_hash=resolved_task_hash,
    )

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any


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
    except Exception as error:
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

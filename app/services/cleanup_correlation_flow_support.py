from __future__ import annotations

from collections.abc import Callable
from typing import Any


def run_cleanup_correlation_lookup(
    *,
    resolve_task_identity: Callable[[str, int | None], Any],
    fetch_event: Callable[[Any], object | None],
    build_correlation_result: Callable[[Any, object], Any | None],
    task_ref: str,
    chat_id: int | None,
) -> tuple[Any, Any | None]:
    resolved_identity = resolve_task_identity(task_ref, chat_id)
    event = fetch_event(resolved_identity)
    if event is None:
        return resolved_identity, None
    correlation = build_correlation_result(resolved_identity, event)
    return resolved_identity, correlation

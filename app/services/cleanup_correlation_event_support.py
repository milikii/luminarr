from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

_EventT = TypeVar("_EventT")


def fetch_cleanup_correlation_event(
    *,
    fetch_event: Callable[[], _EventT | None],
    on_result_missing: Callable[[str], None],
    on_row_corrupted: Callable[[str], None],
    on_failed: Callable[[str], None],
    result_missing_reason: str,
    is_row_corrupted_reason: Callable[[str], bool],
) -> _EventT | None:
    try:
        return fetch_event()
    except Exception as error:
        reason = str(error)
        if reason == result_missing_reason:
            on_result_missing(reason)
            return None
        if is_row_corrupted_reason(reason):
            on_row_corrupted(reason)
            return None
        on_failed(reason)
        return None

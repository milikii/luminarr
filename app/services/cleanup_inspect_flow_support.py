from __future__ import annotations

from collections.abc import Callable

from app.services.cleanup_inspection_support import CleanupInspection


def run_cleanup_inspect_flow(
    *,
    task_ref: str,
    usage_text: str,
    inspect_cleanup: Callable[[str, int | None], CleanupInspection],
    render_message: Callable[[CleanupInspection], str],
    chat_id: int | None = None,
) -> str:
    cleaned_ref = task_ref.strip()
    if not cleaned_ref:
        return usage_text
    inspection = inspect_cleanup(cleaned_ref, chat_id)
    return render_message(inspection)

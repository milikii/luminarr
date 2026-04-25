from __future__ import annotations

from app.services.cleanup_inspection_support import CleanupInspection


def preferred_cleanup_ref(inspection: CleanupInspection) -> str:
    for value in (inspection.task_hash, inspection.task_id, inspection.task_ref, inspection.query_ref):
        cleaned_value = value.strip()
        if cleaned_value:
            return cleaned_value
    return inspection.query_ref


def resolve_cleanup_blocked_event_details(
    *,
    inspection: CleanupInspection,
    pt_seed_window_state_unavailable_text: str,
    pt_seed_window_blocked_fix_hint: str,
    pt_seed_window_state_unavailable_fix_hint: str,
    source_type_unsupported_text: str,
    source_type_unsupported_fix_hint: str,
    guard_rejected_fix_hint: str,
) -> tuple[str, str]:
    if inspection.conclusion.startswith("PT 最小保护窗口未满"):
        return "cleanup.pt_seed_window_blocked", pt_seed_window_blocked_fix_hint
    if inspection.conclusion == pt_seed_window_state_unavailable_text:
        return "cleanup.pt_seed_window_state_unavailable", pt_seed_window_state_unavailable_fix_hint
    if inspection.conclusion == source_type_unsupported_text:
        return "cleanup.source_type_unsupported", source_type_unsupported_fix_hint
    return "cleanup.guard_rejected", guard_rejected_fix_hint


def append_cleanup_follow_up(message: str, task_ref: str, follow_up_template: str) -> str:
    cleaned_ref = task_ref.strip()
    if not cleaned_ref:
        return message
    return f"{message}\n{follow_up_template.format(task_ref=cleaned_ref)}"


def append_cleanup_success_follow_up(message: str, task_ref: str, success_follow_up_template: str) -> str:
    cleaned_ref = task_ref.strip()
    if not cleaned_ref:
        return message
    return f"{message}\n{success_follow_up_template.format(task_ref=cleaned_ref)}"


def format_cleanup_inspect_follow_up(
    inspection: CleanupInspection,
    *,
    inspect_ready_follow_up_template: str,
    inspect_blocked_follow_up_template: str,
) -> str:
    task_ref = preferred_cleanup_ref(inspection).strip()
    if not task_ref:
        return ""
    if inspection.cleanup_allowed:
        return inspect_ready_follow_up_template.format(task_ref=task_ref)
    return inspect_blocked_follow_up_template.format(task_ref=task_ref)

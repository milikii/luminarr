from __future__ import annotations

from dataclasses import dataclass

from app.services.cleanup_follow_up_support import append_cleanup_follow_up, resolve_cleanup_blocked_event_details
from app.services.cleanup_inspection_support import CleanupInspection


@dataclass(frozen=True, slots=True)
class CleanupBlockedOutcome:
    event_type: str
    message: str
    fix_hint: str
    source_path: str = ""
    target_path: str = ""


def resolve_cleanup_blocked_outcome(
    *,
    inspection: CleanupInspection,
    follow_up_ref: str,
    correlation_missing_text: str,
    correlation_missing_fix_hint: str,
    target_missing_fix_hint: str,
    source_missing_fix_hint: str,
    pt_seed_window_state_unavailable_text: str,
    pt_seed_window_blocked_fix_hint: str,
    pt_seed_window_state_unavailable_fix_hint: str,
    source_type_unsupported_text: str,
    source_type_unsupported_fix_hint: str,
    guard_rejected_fix_hint: str,
    follow_up_template: str,
) -> CleanupBlockedOutcome | None:
    if not inspection.correlation_found:
        return CleanupBlockedOutcome(
            event_type="cleanup.correlation_missing",
            message=append_cleanup_follow_up(
                correlation_missing_text,
                follow_up_ref,
                follow_up_template,
            ),
            fix_hint=correlation_missing_fix_hint,
        )

    if inspection.target_exists is False:
        return CleanupBlockedOutcome(
            event_type="cleanup.target_missing",
            message=append_cleanup_follow_up(inspection.conclusion, follow_up_ref, follow_up_template),
            fix_hint=target_missing_fix_hint,
            source_path=inspection.source_path,
            target_path=inspection.target_path,
        )

    if inspection.source_exists is False:
        return CleanupBlockedOutcome(
            event_type="cleanup.source_missing",
            message=append_cleanup_follow_up(inspection.conclusion, follow_up_ref, follow_up_template),
            fix_hint=source_missing_fix_hint,
            source_path=inspection.source_path,
            target_path=inspection.target_path,
        )

    if inspection.cleanup_allowed:
        return None

    event_type, fix_hint = resolve_cleanup_blocked_event_details(
        inspection=inspection,
        pt_seed_window_state_unavailable_text=pt_seed_window_state_unavailable_text,
        pt_seed_window_blocked_fix_hint=pt_seed_window_blocked_fix_hint,
        pt_seed_window_state_unavailable_fix_hint=pt_seed_window_state_unavailable_fix_hint,
        source_type_unsupported_text=source_type_unsupported_text,
        source_type_unsupported_fix_hint=source_type_unsupported_fix_hint,
        guard_rejected_fix_hint=guard_rejected_fix_hint,
    )
    return CleanupBlockedOutcome(
        event_type=event_type,
        message=append_cleanup_follow_up(inspection.conclusion, follow_up_ref, follow_up_template),
        fix_hint=fix_hint,
        source_path=inspection.source_path,
        target_path=inspection.target_path,
    )

from __future__ import annotations

from app.services.cleanup_follow_up_support import format_cleanup_inspect_follow_up
from app.services.cleanup_inspection_support import CleanupInspection


def render_cleanup_inspect_message(
    *,
    inspection: CleanupInspection,
    inspect_result_template: str,
    inspect_ready_follow_up_template: str,
    inspect_blocked_follow_up_template: str,
) -> str:
    lines = [
        inspect_result_template.format(
            query_ref=inspection.query_ref,
            task_id=inspection.task_id or "-",
            task_hash=inspection.task_hash or "-",
            correlation_status="已找到" if inspection.correlation_found else "未找到",
            source_path=inspection.source_path or "-",
            source_status=_format_cleanup_path_status(inspection.source_exists),
            target_path=inspection.target_path or "-",
            target_status=_format_cleanup_path_status(inspection.target_exists),
            guardrail_status="允许 cleanup" if inspection.cleanup_allowed else "拒绝 cleanup",
            conclusion=inspection.conclusion,
        )
    ]
    if inspection.cleanup_allowed or inspection.correlation_found:
        lines.append(
            format_cleanup_inspect_follow_up(
                inspection,
                inspect_ready_follow_up_template=inspect_ready_follow_up_template,
                inspect_blocked_follow_up_template=inspect_blocked_follow_up_template,
            )
        )
    return "\n".join(lines)


def _format_cleanup_path_status(exists: bool | None) -> str:
    if exists is None:
        return "未找到关联"
    if exists:
        return "存在"
    return "不存在"

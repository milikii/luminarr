from __future__ import annotations


def print_cleanup_blocked_log(
    *,
    event_type: str,
    task_ref: str,
    reason: str,
    fix_hint: str,
    task_id: str = "",
    task_hash: str = "",
    source_path: str = "",
    target_path: str = "",
) -> None:
    details = [f"task_ref={task_ref}", f"event_type={event_type}"]
    if task_id.strip():
        details.append(f"task_id={task_id}")
    if task_hash.strip():
        details.append(f"task_hash={task_hash}")
    if source_path.strip():
        details.append(f"source={source_path}")
    if target_path.strip():
        details.append(f"target={target_path}")
    details_text = " ".join(details)
    print(
        f"\033[31m[cleanup 执行受阻]\033[0m {details_text} 结论={reason}",
        flush=True,
    )
    print(
        f"\033[33m[处理建议]\033[0m {fix_hint}",
        flush=True,
    )

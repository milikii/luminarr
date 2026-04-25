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


def print_cleanup_event_append_failed_log(
    *,
    task_ref: str,
    event_type: str,
    error: Exception,
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
        f"\033[31m[cleanup 事件写入失败]\033[0m {details_text} 原因={error}",
        flush=True,
    )
    print(
        "\033[33m[处理建议]\033[0m 检查 SQLite job_event 是否可写、磁盘是否只读或已满；"
        "当前 cleanup 文本结果已返回，但这次执行记录未成功落盘。",
        flush=True,
    )


def print_cleanup_event_append_result_missing_log(
    *,
    task_ref: str,
    event_type: str,
    reason: str,
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
        f"\033[31m[cleanup 事件结果缺失]\033[0m {details_text} 原因={reason}",
        flush=True,
    )
    print(
        "\033[33m[处理建议]\033[0m 检查 job_event 写入后回读是否仍能拿到刚追加的 cleanup 事件；"
        "当前 cleanup 文本结果已返回，但这次执行记录真相还没有确认落稳。",
        flush=True,
    )


def print_cleanup_event_append_row_corrupted_log(
    *,
    task_ref: str,
    event_type: str,
    reason: str,
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
        f"\033[31m[cleanup 事件记录损坏]\033[0m {details_text} 原因={reason}",
        flush=True,
    )
    print(
        "\033[33m[处理建议]\033[0m 检查 job_event 读回事件里的 task_ref / event_type / source_path / target_path 是否仍是完整真相；"
        "当前 cleanup 文本结果已返回，但不会把这条坏事件当成已稳定落盘。",
        flush=True,
    )


def print_cleanup_pt_seed_guard_lookup_failed_log(
    *,
    task_ref: str,
    task_id: str,
    task_hash: str,
    error: Exception,
    state_unavailable_fix_hint: str,
) -> None:
    print(
        f"\033[31m[cleanup PT 保护查询失败]\033[0m task_ref={task_ref} task_id={task_id or '-'} "
        f"task_hash={task_hash or '-'} 错误={error}",
        flush=True,
    )
    print(
        f"\033[33m[处理建议]\033[0m {state_unavailable_fix_hint}",
        flush=True,
    )


def print_cleanup_pt_seed_guard_state_unavailable_log(
    *,
    task_ref: str,
    task_id: str,
    task_hash: str,
    reason: str,
    state_unavailable_fix_hint: str,
) -> None:
    print(
        f"\033[31m[cleanup PT 保护真相缺失]\033[0m task_ref={task_ref} task_id={task_id or '-'} "
        f"task_hash={task_hash or '-'} 原因={reason}",
        flush=True,
    )
    print(
        f"\033[33m[处理建议]\033[0m {state_unavailable_fix_hint}",
        flush=True,
    )

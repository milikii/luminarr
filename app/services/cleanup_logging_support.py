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


def print_cleanup_delete_failed_log(
    *,
    task_ref: str,
    event_type: str,
    task_id: str,
    task_hash: str,
    source_path: str,
    target_path: str,
    failure_reason: str,
) -> None:
    print(
        f"\033[31m[cleanup 执行失败]\033[0m task_ref={task_ref} "
        f"event_type={event_type} task_id={task_id} task_hash={task_hash} "
        f"source={source_path} target={target_path} 原因={failure_reason}",
        flush=True,
    )
    print(
        "\033[33m[处理建议]\033[0m 检查 source_path 是否仍可访问、当前进程是否有删除权限，"
        "并确认库内目标路径仍然存在后再重试 cleanup。",
        flush=True,
    )


def print_cleanup_job_lookup_failed_log(*, task_ref: str, chat_id: int, error: Exception) -> None:
    print(
        f"\033[31m[cleanup 任务解析失败]\033[0m chat_id={chat_id} task_ref={task_ref} 原因={error}",
        flush=True,
    )
    print(
        "\033[33m[处理建议]\033[0m 检查 jobs 表按 chat_id/task_ref 的读取是否可用；"
        "当前会回退到原始 task_ref 继续尝试匹配 import 关联。",
        flush=True,
    )


def print_cleanup_correlation_result_missing_log(
    *,
    task_ref: str,
    lookup_task_ref: str,
    lookup_task_id: str,
    lookup_task_hash: str,
    reason: str,
) -> None:
    print(
        f"\033[31m[cleanup 关联结果缺失]\033[0m task_ref={task_ref} "
        f"lookup_task_ref={lookup_task_ref} lookup_task_id={lookup_task_id} "
        f"lookup_task_hash={lookup_task_hash} 原因={reason}",
        flush=True,
    )
    print(
        "\033[33m[处理建议]\033[0m 检查 job_event 关联查询返回是否仍带有完整事件列表；"
        "当前会按未找到关联停路，避免把缺失真相误判成普通“没有 import 关联”。",
        flush=True,
    )


def print_cleanup_correlation_row_corrupted_log(
    *,
    task_ref: str,
    lookup_task_ref: str,
    lookup_task_id: str,
    lookup_task_hash: str,
    reason: str,
) -> None:
    print(
        f"\033[31m[cleanup 关联记录损坏]\033[0m task_ref={task_ref} "
        f"lookup_task_ref={lookup_task_ref} lookup_task_id={lookup_task_id} "
        f"lookup_task_hash={lookup_task_hash} 原因={reason}",
        flush=True,
    )
    print(
        "\033[33m[处理建议]\033[0m 检查 job_event 导入成功关联里的 task_ref / event_type / source_path / target_path "
        "是否仍是完整真相；当前会按未找到关联停路，避免把坏记录误判成普通“没有 import 关联”。",
        flush=True,
    )


def print_cleanup_correlation_lookup_failed_log(
    *,
    task_ref: str,
    lookup_task_ref: str,
    lookup_task_id: str,
    lookup_task_hash: str,
    reason: str,
) -> None:
    print(
        f"\033[31m[cleanup 关联查询失败]\033[0m task_ref={task_ref} "
        f"lookup_task_ref={lookup_task_ref} lookup_task_id={lookup_task_id} "
        f"lookup_task_hash={lookup_task_hash} 原因={reason}",
        flush=True,
    )
    print(
        "\033[33m[处理建议]\033[0m 检查 SQLite job_event 是否可读、导入成功事件是否已落盘，"
        "再重试 cleanup。",
        flush=True,
    )


def print_cleanup_correlation_path_missing_log(
    *,
    task_ref: str,
    lookup_task_ref: str,
    lookup_task_id: str,
    lookup_task_hash: str,
    event_type: str,
    source_path_missing: bool,
    target_path_missing: bool,
) -> None:
    missing_fields: list[str] = []
    if source_path_missing:
        missing_fields.append("source_path")
    if target_path_missing:
        missing_fields.append("target_path")
    print(
        f"\033[31m[cleanup 关联路径缺失]\033[0m task_ref={task_ref} "
        f"lookup_task_ref={lookup_task_ref} lookup_task_id={lookup_task_id} "
        f"lookup_task_hash={lookup_task_hash} event_type={event_type} "
        f"missing_fields={','.join(missing_fields)}",
        flush=True,
    )
    print(
        "\033[33m[处理建议]\033[0m 检查 import.succeeded 事件是否带有完整 source_path / target_path；"
        "当前会按未找到关联停路，避免误删下载源资产。",
        flush=True,
    )

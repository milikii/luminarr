from __future__ import annotations


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

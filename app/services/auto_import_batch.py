from __future__ import annotations

import sqlite3
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from app.db.download_monitor_repo import (
    DownloadMonitorPersistenceError,
    DownloadMonitorRecord,
    DownloadMonitorRepo,
)

AUTO_IMPORT_COMPLETED_LIST_RESULT_MISSING_REASON = "auto import completed list result missing"

AutoImportRecordRunner = Callable[[DownloadMonitorRecord], Awaitable[str | None]]
AutoImportProgressPredicate = Callable[[DownloadMonitorRecord, str], bool]


@dataclass(frozen=True, slots=True)
class AutoImportBatchProgress:
    progressed: int
    replies: tuple[str, ...]
    state_unavailable: bool = False


class AutoImportCompletedListUnavailableError(RuntimeError):
    pass


def load_completed_auto_import_candidates(
    *,
    download_monitor_repo: DownloadMonitorRepo,
    limit: int,
) -> tuple[DownloadMonitorRecord, ...]:
    try:
        candidates = download_monitor_repo.list_completed_for_auto_import(limit=limit)
        if candidates is None:
            raise DownloadMonitorPersistenceError(AUTO_IMPORT_COMPLETED_LIST_RESULT_MISSING_REASON)
    except (DownloadMonitorPersistenceError, sqlite3.Error) as error:
        if str(error) == AUTO_IMPORT_COMPLETED_LIST_RESULT_MISSING_REASON:
            print(
                f"\033[31m[自动导入候选结果缺失]\033[0m limit={limit} 错误={error}\n"
                "\033[33m[处理建议]\033[0m 检查 download_monitor 已完成列表查询返回是否仍带有完整结果；"
                "当前这轮自动导入会直接停路，避免把缺失真相误判成“当前没有可导入候选”。",
                flush=True,
            )
        elif _is_auto_import_completed_row_corrupted_error(error):
            print(
                f"\033[31m[自动导入候选记录损坏]\033[0m limit={limit} 错误={error}\n"
                "\033[33m[处理建议]\033[0m 检查 download_monitor 已完成记录里的 chat_id / task_id / task_hash 等字段是否仍是完整真相；"
                "当前这轮自动导入会直接停路，避免把坏记录误判成普通读取失败后继续推进导入审批。",
                flush=True,
            )
        else:
            print(
                f"\033[31m[自动导入候选读取失败]\033[0m limit={limit} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/download_monitor 表读取是否正常；当前这轮自动导入会直接跳过，但已完成下载可能暂时不会进入导入审批。",
                flush=True,
            )
        raise AutoImportCompletedListUnavailableError(str(error)) from error
    return tuple(candidates)


async def run_auto_import_candidates(
    *,
    candidates: Sequence[DownloadMonitorRecord],
    run_for_record: AutoImportRecordRunner,
    count_as_progress: AutoImportProgressPredicate,
    state_unavailable_error: type[BaseException],
) -> AutoImportBatchProgress:
    replies: list[str] = []
    progressed = 0
    state_unavailable = False

    for candidate in candidates:
        try:
            reply = await run_for_record(candidate)
        except state_unavailable_error:
            state_unavailable = True
            continue
        if reply is None:
            continue
        replies.append(reply)
        if count_as_progress(candidate, reply):
            progressed += 1

    return AutoImportBatchProgress(
        progressed=progressed,
        replies=tuple(replies),
        state_unavailable=state_unavailable,
    )


def _is_auto_import_completed_row_corrupted_error(error: Exception) -> bool:
    return isinstance(error, DownloadMonitorPersistenceError) and str(error).endswith("corrupted after read")

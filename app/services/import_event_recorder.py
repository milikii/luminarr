from __future__ import annotations

import sqlite3
from collections.abc import Callable

from app.db.job_event_repo import JobEventPersistenceError, JobEventRepo

IsImportEventRowCorruptedErrorFunc = Callable[[Exception], bool]


class ImportEventRecorder:
    def __init__(
        self,
        *,
        job_event_repo: JobEventRepo | None,
        import_event_result_missing_reason: str,
        is_import_event_row_corrupted_error: IsImportEventRowCorruptedErrorFunc,
    ) -> None:
        self._job_event_repo = job_event_repo
        self._import_event_result_missing_reason = import_event_result_missing_reason
        self._is_import_event_row_corrupted_error = is_import_event_row_corrupted_error

    def record_event(
        self,
        *,
        task_ref: str,
        event_type: str,
        message: str,
        task_id: str = "",
        task_hash: str = "",
        source_path: str = "",
        target_path: str = "",
    ) -> None:
        if self._job_event_repo is None:
            return
        try:
            self._job_event_repo.append_event(
                task_ref=task_ref,
                task_id=task_id,
                task_hash=task_hash,
                event_type=event_type,
                message=message,
                source_path=source_path,
                target_path=target_path,
            )
        except JobEventPersistenceError as error:
            if str(error) == self._import_event_result_missing_reason:
                print(
                    f"\033[31m[导入事件结果缺失]\033[0m task_ref={task_ref} task_id={task_id} task_hash={task_hash} event_type={event_type} source={source_path} target={target_path} 错误=import event missing after append\n\033[33m[处理建议]\033[0m 检查 job_event 写入后回读是否仍能拿到刚追加的导入事件；当前导入流程会继续执行，但这次事件真相还没有确认落稳。",
                    flush=True,
                )
            elif self._is_import_event_row_corrupted_error(error):
                print(
                    f"\033[31m[导入事件记录损坏]\033[0m task_ref={task_ref} task_id={task_id} task_hash={task_hash} event_type={event_type} source={source_path} target={target_path} 错误={error}\n\033[33m[处理建议]\033[0m 检查 job_event 读回事件里的 task_ref / event_type / source_path / target_path 等真相字段是否仍然完整；当前导入流程会继续执行，但不会把这条坏事件当成已稳定落盘。",
                    flush=True,
                )
            else:
                print(
                    f"\033[31m[导入事件落盘失败]\033[0m task_ref={task_ref} task_id={task_id} task_hash={task_hash} event_type={event_type} source={source_path} target={target_path} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/job_event 表写入是否正常；当前导入流程会继续执行，但这次事件可能没有落盘。",
                    flush=True,
                )
        except sqlite3.Error as error:
            print(
                f"\033[31m[导入事件落盘失败]\033[0m task_ref={task_ref} task_id={task_id} task_hash={task_hash} event_type={event_type} source={source_path} target={target_path} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/job_event 表写入是否正常；当前导入流程会继续执行，但这次事件可能没有落盘。",
                flush=True,
            )

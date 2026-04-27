from __future__ import annotations

import sqlite3
from collections.abc import Callable

from app.db.job_repo import JobPersistenceError, JobRecord, JobRepo, WORKFLOW_IMPORT_TO_LIBRARY
from app.operational_logging import emit_operational_log

IMPORT_PENDING_JOB_RESULT_MISSING_REASON = "job missing after pending upsert"
IMPORT_PENDING_JOB_NONE_REASON = "import pending job result missing"
IMPORT_CLAIM_PENDING_JOB_RESULT_MISSING_REASON = "job missing during lease claim"
IMPORT_RESTORE_PENDING_JOB_RESULT_MISSING_REASON = "job missing during state transition"
IMPORT_MARK_COMPLETED_JOB_RESULT_MISSING_REASON = "import completed job result missing"

IsJobRowCorruptedErrorFunc = Callable[[Exception], bool]


class ImportJobState:
    def __init__(
        self,
        *,
        job_repo: JobRepo | None,
        is_job_row_corrupted_error: IsJobRowCorruptedErrorFunc,
    ) -> None:
        self._job_repo = job_repo
        self._is_job_row_corrupted_error = is_job_row_corrupted_error

    def record_pending_job(
        self,
        *,
        chat_id: int | None,
        user_id: int | None,
        task_ref: str,
        task_id: str,
        task_hash: str,
        payload_json: str = "",
    ) -> bool:
        if self._job_repo is None:
            return True
        try:
            pending_job = self._job_repo.upsert_import_job_pending(
                chat_id=chat_id,
                user_id=user_id,
                task_ref=task_ref,
                task_id=task_id,
                task_hash=task_hash,
                payload_json=payload_json,
            )
            if pending_job is None:
                raise JobPersistenceError(IMPORT_PENDING_JOB_NONE_REASON)
        except (JobPersistenceError, sqlite3.Error) as error:
            if str(error) in {
                IMPORT_PENDING_JOB_RESULT_MISSING_REASON,
                IMPORT_PENDING_JOB_NONE_REASON,
            }:
                emit_operational_log(
                    title="导入待确认任务结果缺失",
                    detail=f"chat_id={chat_id} user_id={user_id} task_ref={task_ref} task_id={task_id} task_hash={task_hash} 错误={error}",
                    fix_hint="检查 jobs 写入后回读是否仍能拿到刚创建的导入待确认任务；当前请求会直接返回待确认状态写入失败，避免把缺失真相误报成可确认导入。",
                )
            elif self._is_job_row_corrupted_error(error):
                emit_operational_log(
                    title="导入待确认任务记录损坏",
                    detail=f"chat_id={chat_id} user_id={user_id} task_ref={task_ref} task_id={task_id} task_hash={task_hash} 错误={error}",
                    fix_hint="检查 jobs 新写入待确认任务里的 job_id / chat_id / user_id / version 等字段是否仍是完整真相；当前请求会直接返回待确认状态写入失败，避免把坏任务记录误报成可确认导入。",
                )
            else:
                emit_operational_log(
                    title="导入待确认任务落盘失败",
                    detail=f"chat_id={chat_id} user_id={user_id} task_ref={task_ref} task_id={task_id} task_hash={task_hash} 错误={error}",
                    fix_hint="检查 SQLite/jobs 表写入是否正常；当前请求会直接返回待确认状态写入失败，避免把待确认任务真相缺口误报成可确认导入。",
                )
            return False
        return True

    def claim_pending_job(self, *, job: JobRecord, lease_owner: str) -> bool | None:
        if self._job_repo is None:
            return False
        try:
            claimed = self._job_repo.claim_lease(
                job_id=job.job_id,
                expected_version=job.version,
                lease_owner=lease_owner,
                workflow_type=WORKFLOW_IMPORT_TO_LIBRARY,
            )
        except (JobPersistenceError, sqlite3.Error) as error:
            if str(error) == IMPORT_CLAIM_PENDING_JOB_RESULT_MISSING_REASON:
                emit_operational_log(
                    title="导入确认任务抢占结果缺失",
                    detail=f"job_id={job.job_id} task_ref={job.task_ref} task_id={job.task_id} task_hash={job.task_hash} version={job.version} lease_owner={lease_owner} 错误={error}",
                    fix_hint="检查 jobs 表里该待确认任务是否仍存在，并确认抢占前后的 version/lease_owner 没有被其他路径改写；当前 confirm 会直接返回状态读取失败，避免把任务真相缺口误判成普通未持有执行权。",
                )
            else:
                emit_operational_log(
                    title="导入确认任务抢占失败",
                    detail=f"job_id={job.job_id} task_ref={job.task_ref} task_id={job.task_id} task_hash={job.task_hash} version={job.version} lease_owner={lease_owner} 错误={error}",
                    fix_hint="检查 SQLite/jobs 表 lease 更新是否正常；当前 confirm 会直接返回状态读取失败，避免把持久化异常继续混成普通未持有执行权。",
                )
            return None
        if claimed is False:
            emit_operational_log(
                title="导入确认任务抢占失败",
                detail=f"job_id={job.job_id} task_ref={job.task_ref} task_id={job.task_id} task_hash={job.task_hash} version={job.version} lease_owner={lease_owner} 错误=jobs.claim_lease rejected current state",
                fix_hint="检查 SQLite/jobs 表里的任务行是否仍存在、version/lease_owner 是否匹配，或是否已被其他路径抢先确认/取消；当前 confirm 会继续按 stale check 处理，避免把任务真相冲突静默混成普通未确认。",
            )
            return False
        return True

    def restore_pending_job(
        self,
        *,
        job_id: str,
        expected_version: int,
        lease_owner: str,
    ) -> None:
        if self._job_repo is None:
            return
        try:
            restored = self._job_repo.release_lease_to_pending(
                job_id=job_id,
                expected_version=expected_version,
                lease_owner=lease_owner,
                workflow_type=WORKFLOW_IMPORT_TO_LIBRARY,
            )
        except (JobPersistenceError, sqlite3.Error) as error:
            if str(error) == IMPORT_RESTORE_PENDING_JOB_RESULT_MISSING_REASON:
                emit_operational_log(
                    title="导入确认任务回退结果缺失",
                    detail=f"job_id={job_id} version={expected_version} lease_owner={lease_owner} 错误={error}",
                    fix_hint="检查 jobs 表里该待确认任务是否仍存在，以及 lease 回退后是否还能回读到待确认状态；当前审批已尝试退回待确认，但任务真相还没有确认回退成功。",
                )
            else:
                emit_operational_log(
                    title="导入确认任务回退失败",
                    detail=f"job_id={job_id} version={expected_version} lease_owner={lease_owner} 错误={error}",
                    fix_hint="检查 SQLite/jobs 表 lease 回退是否正常；当前审批已尝试退回待确认，但持久化状态可能仍停在执行中。",
                )
            return
        if restored is False:
            emit_operational_log(
                title="导入确认任务回退失败",
                detail=f"job_id={job_id} version={expected_version} lease_owner={lease_owner} 错误=jobs.release_lease_to_pending rejected current state",
                fix_hint="检查 SQLite/jobs 表里的任务行是否仍存在、version/lease_owner 是否匹配；当前审批已尝试退回待确认，但持久化状态可能仍停在执行中。",
            )

    def mark_completed_job(
        self,
        *,
        job_id: str,
        expected_version: int,
        lease_owner: str,
    ) -> bool | None:
        if self._job_repo is None:
            return True
        try:
            marked = self._job_repo.mark_completed(
                job_id=job_id,
                expected_version=expected_version,
                lease_owner=lease_owner,
                workflow_type=WORKFLOW_IMPORT_TO_LIBRARY,
            )
            if marked is None:
                raise JobPersistenceError(IMPORT_MARK_COMPLETED_JOB_RESULT_MISSING_REASON)
        except (JobPersistenceError, sqlite3.Error) as error:
            if str(error) == IMPORT_MARK_COMPLETED_JOB_RESULT_MISSING_REASON:
                emit_operational_log(
                    title="导入确认任务完结结果缺失",
                    detail=f"job_id={job_id} version={expected_version} lease_owner={lease_owner} 错误={error}",
                    fix_hint="检查 jobs 表里该任务是否仍存在，以及完成态更新后是否还能回读到最新状态；当前导入结果已返回，但任务真相还没有确认完结成功。",
                )
            else:
                emit_operational_log(
                    title="导入确认任务完结失败",
                    detail=f"job_id={job_id} version={expected_version} lease_owner={lease_owner} 错误={error}",
                    fix_hint="检查 SQLite/jobs 表完成态更新是否正常；当前导入结果已返回，但任务真相可能仍停留在待确认或执行中。",
                )
            return None
        if marked is False:
            emit_operational_log(
                title="导入确认任务完结失败",
                detail=f"job_id={job_id} version={expected_version} lease_owner={lease_owner} 错误=jobs.mark_completed rejected current state",
                fix_hint="检查 SQLite/jobs 表里的任务行是否仍存在、version/lease_owner 是否匹配；当前导入结果已返回，但任务真相可能仍停留在待确认或执行中。",
            )
            return False
        return True

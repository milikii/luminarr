from __future__ import annotations

import sqlite3

from app.db.job_repo import JobPersistenceError, JobRecord, JobRepo, WORKFLOW_ADD_TO_DOWNLOADER
from app.services.add_pending_context import PendingAddContext, pending_add_to_json

DOWNLOADER_CLAIM_PENDING_JOB_RESULT_MISSING_REASON = "job missing during lease claim"
DOWNLOADER_RESTORE_PENDING_JOB_RESULT_MISSING_REASON = "job missing during state transition"
DOWNLOADER_MARK_COMPLETED_JOB_RESULT_MISSING_REASON = "downloader completed job result missing"
JOB_LEASE_OWNER = "downloader_confirm"


class AddConfirmJobState:
    def __init__(self, *, job_repo: JobRepo | None) -> None:
        self._job_repo = job_repo

    def claim_pending_job(self, *, job: JobRecord, lease_owner: str) -> bool | None:
        if self._job_repo is None:
            return False
        try:
            claimed = self._job_repo.claim_lease(
                job_id=job.job_id,
                expected_version=job.version,
                lease_owner=lease_owner,
                workflow_type=WORKFLOW_ADD_TO_DOWNLOADER,
            )
        except (JobPersistenceError, sqlite3.Error) as error:
            if str(error) == DOWNLOADER_CLAIM_PENDING_JOB_RESULT_MISSING_REASON:
                print(
                    f"\033[31m[下载确认任务抢占结果缺失]\033[0m job_id={job.job_id} task_ref={job.task_ref} task_id={job.task_id} task_hash={job.task_hash} version={job.version} lease_owner={lease_owner} 错误={error}\n"
                    "\033[33m[处理建议]\033[0m 检查 jobs 表里该待确认任务是否仍存在，并确认抢占前后的 version/lease_owner 没有被其他路径改写；"
                    "当前 confirm 会直接返回状态读取失败，避免把任务真相缺口误判成普通未持有执行权。",
                    flush=True,
                )
            else:
                print(
                    f"\033[31m[下载确认任务抢占失败]\033[0m job_id={job.job_id} task_ref={job.task_ref} task_id={job.task_id} task_hash={job.task_hash} version={job.version} lease_owner={lease_owner} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表 lease 更新是否正常；当前 confirm 会直接返回状态读取失败，避免把持久化异常继续混成普通未持有执行权。",
                    flush=True,
                )
            return None
        if claimed is False:
            print(
                f"\033[31m[下载确认任务抢占失败]\033[0m job_id={job.job_id} task_ref={job.task_ref} task_id={job.task_id} task_hash={job.task_hash} version={job.version} lease_owner={lease_owner} 错误=jobs.claim_lease rejected current state\n\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表里的任务行是否仍存在、version/lease_owner 是否匹配，或是否已被其他路径抢先确认/取消；当前 confirm 会继续按 stale check 处理，避免把任务真相冲突静默混成普通未确认。",
                flush=True,
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
                workflow_type=WORKFLOW_ADD_TO_DOWNLOADER,
            )
        except (JobPersistenceError, sqlite3.Error) as error:
            if str(error) == DOWNLOADER_RESTORE_PENDING_JOB_RESULT_MISSING_REASON:
                print(
                    f"\033[31m[下载确认任务回退结果缺失]\033[0m job_id={job_id} version={expected_version} lease_owner={lease_owner} 错误={error}\n"
                    "\033[33m[处理建议]\033[0m 检查 jobs 表里该待确认任务是否仍存在，以及 lease 回退后是否还能回读到待确认状态；"
                    "当前审批已尝试退回待确认，但任务真相还没有确认回退成功。",
                    flush=True,
                )
            else:
                print(
                    f"\033[31m[下载确认任务回退失败]\033[0m job_id={job_id} version={expected_version} lease_owner={lease_owner} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表 lease 回退是否正常；当前审批已尝试退回待确认，但持久化状态可能仍停在执行中。",
                    flush=True,
                )
            return
        if restored is False:
            print(
                f"\033[31m[下载确认任务回退失败]\033[0m job_id={job_id} version={expected_version} lease_owner={lease_owner} 错误=jobs.release_lease_to_pending rejected current state\n\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表里的任务行是否仍存在、version/lease_owner 是否匹配；当前审批已尝试退回待确认，但持久化状态可能仍停在执行中。",
                flush=True,
            )

    def mark_completed_job(
        self,
        *,
        job_id: str,
        expected_version: int,
        lease_owner: str,
        completed_add: PendingAddContext,
    ) -> bool | None:
        if self._job_repo is None:
            return True
        try:
            marked = self._job_repo.mark_downloader_completed(
                job_id=job_id,
                expected_version=expected_version,
                lease_owner=lease_owner,
                task_id=completed_add.task_id,
                task_hash=completed_add.task_hash,
                payload_json=pending_add_to_json(completed_add),
            )
            if marked is None:
                raise JobPersistenceError(DOWNLOADER_MARK_COMPLETED_JOB_RESULT_MISSING_REASON)
        except (JobPersistenceError, sqlite3.Error) as error:
            if str(error) == DOWNLOADER_MARK_COMPLETED_JOB_RESULT_MISSING_REASON:
                print(
                    f"\033[31m[下载确认任务完结结果缺失]\033[0m job_id={job_id} task_ref={completed_add.task_ref} task_id={completed_add.task_id} task_hash={completed_add.task_hash} version={expected_version} lease_owner={lease_owner} 错误={error}\n"
                    "\033[33m[处理建议]\033[0m 检查 jobs 表里该任务是否仍存在，以及完成态更新后是否还能回读到最新状态；"
                    "当前下载结果已返回，但任务真相还没有确认完结成功。",
                    flush=True,
                )
            else:
                print(
                    f"\033[31m[下载确认任务完结失败]\033[0m job_id={job_id} task_ref={completed_add.task_ref} task_id={completed_add.task_id} task_hash={completed_add.task_hash} version={expected_version} lease_owner={lease_owner} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表完成态更新是否正常；当前下载结果已返回，但任务真相可能仍停留在待确认或执行中。",
                    flush=True,
                )
            return None
        if marked is False:
            print(
                f"\033[31m[下载确认任务完结失败]\033[0m job_id={job_id} task_ref={completed_add.task_ref} task_id={completed_add.task_id} task_hash={completed_add.task_hash} version={expected_version} lease_owner={lease_owner} 错误=jobs.mark_downloader_completed rejected current state\n\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表里的任务行是否仍存在、version/lease_owner 是否匹配；当前下载结果已返回，但任务真相可能仍停留在待确认或执行中。",
                flush=True,
            )
            return False
        return True

    def build_job_lease_owner(self, task_ref: str) -> str:
        cleaned_ref = task_ref.strip()
        if not cleaned_ref:
            return JOB_LEASE_OWNER
        return f"{JOB_LEASE_OWNER}:{cleaned_ref}"

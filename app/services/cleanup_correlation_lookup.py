from __future__ import annotations

from dataclasses import dataclass

from app.db.job_event_repo import JobEvent, JobEventPersistenceError, JobEventRepo
from app.db.job_repo import JobRepo

CLEANUP_CORRELATION_LOOKUP_RESULT_MISSING_REASON = "job_event list result missing during correlation lookup"


@dataclass(frozen=True, slots=True)
class ImportCorrelation:
    task_ref: str
    task_id: str
    task_hash: str
    source_path: str
    target_path: str


@dataclass(frozen=True, slots=True)
class ResolvedCleanupTaskIdentity:
    lookup_task_ref: str
    lookup_task_id: str
    lookup_task_hash: str
    task_ref: str
    task_id: str
    task_hash: str


class CleanupCorrelationLookup:
    def __init__(
        self,
        *,
        job_event_repo: JobEventRepo,
        job_repo: JobRepo | None,
    ) -> None:
        self._job_event_repo = job_event_repo
        self._job_repo = job_repo

    def find_import_correlation(
        self,
        *,
        task_ref: str,
        chat_id: int | None,
    ) -> tuple[ResolvedCleanupTaskIdentity, ImportCorrelation | None]:
        resolved_identity = self.resolve_task_identity(task_ref=task_ref, chat_id=chat_id)
        try:
            event = self._job_event_repo.find_latest_import_correlation(
                task_ref=resolved_identity.lookup_task_ref,
                task_id=resolved_identity.lookup_task_id,
                task_hash=resolved_identity.lookup_task_hash,
            )
        except Exception as error:
            if str(error) == CLEANUP_CORRELATION_LOOKUP_RESULT_MISSING_REASON:
                print(
                    f"\033[31m[cleanup 关联结果缺失]\033[0m task_ref={task_ref} "
                    f"lookup_task_ref={resolved_identity.lookup_task_ref} lookup_task_id={resolved_identity.lookup_task_id} "
                    f"lookup_task_hash={resolved_identity.lookup_task_hash} 原因={error}",
                    flush=True,
                )
                print(
                    "\033[33m[处理建议]\033[0m 检查 job_event 关联查询返回是否仍带有完整事件列表；"
                    "当前会按未找到关联停路，避免把缺失真相误判成普通“没有 import 关联”。",
                    flush=True,
                )
            elif _is_cleanup_correlation_row_corrupted_error(error):
                print(
                    f"\033[31m[cleanup 关联记录损坏]\033[0m task_ref={task_ref} "
                    f"lookup_task_ref={resolved_identity.lookup_task_ref} lookup_task_id={resolved_identity.lookup_task_id} "
                    f"lookup_task_hash={resolved_identity.lookup_task_hash} 原因={error}",
                    flush=True,
                )
                print(
                    "\033[33m[处理建议]\033[0m 检查 job_event 导入成功关联里的 task_ref / event_type / source_path / target_path "
                    "是否仍是完整真相；当前会按未找到关联停路，避免把坏记录误判成普通“没有 import 关联”。",
                    flush=True,
                )
            else:
                print(
                    f"\033[31m[cleanup 关联查询失败]\033[0m task_ref={task_ref} "
                    f"lookup_task_ref={resolved_identity.lookup_task_ref} lookup_task_id={resolved_identity.lookup_task_id} "
                    f"lookup_task_hash={resolved_identity.lookup_task_hash} 原因={error}",
                    flush=True,
                )
                print(
                    "\033[33m[处理建议]\033[0m 检查 SQLite job_event 是否可读、导入成功事件是否已落盘，"
                    "再重试 cleanup。",
                    flush=True,
                )
            return resolved_identity, None

        if event is None:
            return resolved_identity, None

        source_path = event.source_path.strip()
        target_path = event.target_path.strip()
        if not source_path or not target_path:
            _print_cleanup_correlation_path_missing_log(
                task_ref=task_ref,
                resolved_identity=resolved_identity,
                event=event,
                source_path_missing=not source_path,
                target_path_missing=not target_path,
            )
            return resolved_identity, None

        return resolved_identity, ImportCorrelation(
            task_ref=event.task_ref.strip() or resolved_identity.task_ref,
            task_id=event.task_id.strip() or resolved_identity.task_id,
            task_hash=event.task_hash.strip() or resolved_identity.task_hash,
            source_path=source_path,
            target_path=target_path,
        )

    def resolve_task_identity(
        self,
        *,
        task_ref: str,
        chat_id: int | None,
    ) -> ResolvedCleanupTaskIdentity:
        resolved_task_ref = task_ref
        resolved_task_id = ""
        resolved_task_hash = ""
        lookup_task_ref = task_ref
        lookup_task_id = task_ref
        lookup_task_hash = task_ref

        if self._job_repo is not None and chat_id is not None and chat_id > 0:
            try:
                job = self._job_repo.get_job_for_chat_ref(chat_id=chat_id, task_ref=task_ref)
            except Exception as error:
                _print_cleanup_job_lookup_failed_log(
                    task_ref=task_ref,
                    chat_id=chat_id,
                    error=error,
                )
                job = None
            if job is not None:
                resolved_task_ref = (job.task_ref or task_ref).strip() or resolved_task_ref
                resolved_task_id = (job.task_id or "").strip()
                resolved_task_hash = (job.task_hash or "").strip()
                lookup_task_ref = resolved_task_ref
                lookup_task_id = resolved_task_id or lookup_task_id
                lookup_task_hash = resolved_task_hash or lookup_task_hash

        return ResolvedCleanupTaskIdentity(
            lookup_task_ref=lookup_task_ref,
            lookup_task_id=lookup_task_id,
            lookup_task_hash=lookup_task_hash,
            task_ref=resolved_task_ref,
            task_id=resolved_task_id,
            task_hash=resolved_task_hash,
        )


def _is_cleanup_correlation_row_corrupted_error(error: Exception) -> bool:
    return isinstance(error, JobEventPersistenceError) and str(error).endswith("corrupted after read")


def _print_cleanup_job_lookup_failed_log(*, task_ref: str, chat_id: int, error: Exception) -> None:
    print(
        f"\033[31m[cleanup 任务解析失败]\033[0m chat_id={chat_id} task_ref={task_ref} 原因={error}",
        flush=True,
    )
    print(
        "\033[33m[处理建议]\033[0m 检查 jobs 表按 chat_id/task_ref 的读取是否可用；"
        "当前会回退到原始 task_ref 继续尝试匹配 import 关联。",
        flush=True,
    )


def _print_cleanup_correlation_path_missing_log(
    *,
    task_ref: str,
    resolved_identity: ResolvedCleanupTaskIdentity,
    event: JobEvent,
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
        f"lookup_task_ref={resolved_identity.lookup_task_ref} lookup_task_id={resolved_identity.lookup_task_id} "
        f"lookup_task_hash={resolved_identity.lookup_task_hash} event_type={event.event_type} "
        f"missing_fields={','.join(missing_fields)}",
        flush=True,
    )
    print(
        "\033[33m[处理建议]\033[0m 检查 import.succeeded 事件是否带有完整 source_path / target_path；"
        "当前会按未找到关联停路，避免误删下载源资产。",
        flush=True,
    )

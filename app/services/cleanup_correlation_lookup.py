from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.db.job_event_repo import JobEvent, JobEventPersistenceError, JobEventRepo
from app.db.job_repo import JobPersistenceError, JobRepo

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


@dataclass(frozen=True, slots=True)
class CleanupCorrelationResult:
    task_ref: str
    task_id: str
    task_hash: str
    source_path: str
    target_path: str


@dataclass(frozen=True, slots=True)
class CleanupTaskIdentityResolution:
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
        return run_cleanup_correlation_lookup(
            task_ref=task_ref,
            chat_id=chat_id,
            resolve_task_identity=lambda resolved_task_ref, resolved_chat_id: self.resolve_task_identity(
                task_ref=resolved_task_ref,
                chat_id=resolved_chat_id,
            ),
            fetch_event=lambda resolved_identity: fetch_cleanup_correlation_event(
                fetch_event=lambda: self._job_event_repo.find_latest_import_correlation(
                    task_ref=resolved_identity.lookup_task_ref,
                    task_id=resolved_identity.lookup_task_id,
                    task_hash=resolved_identity.lookup_task_hash,
                ),
                on_result_missing=lambda reason: _print_cleanup_correlation_result_missing_log(
                    task_ref=task_ref,
                    resolved_identity=resolved_identity,
                    reason=reason,
                ),
                on_row_corrupted=lambda reason: _print_cleanup_correlation_row_corrupted_log(
                    task_ref=task_ref,
                    resolved_identity=resolved_identity,
                    reason=reason,
                ),
                on_failed=lambda reason: _print_cleanup_correlation_lookup_failed_log(
                    task_ref=task_ref,
                    resolved_identity=resolved_identity,
                    reason=reason,
                ),
                result_missing_reason=CLEANUP_CORRELATION_LOOKUP_RESULT_MISSING_REASON,
                is_row_corrupted_reason=_is_cleanup_correlation_row_corrupted_reason,
            ),
            build_correlation_result=lambda resolved_identity, event: (
                None
                if (correlation := build_cleanup_correlation_result(
                    event=event,
                    fallback_task_ref=resolved_identity.task_ref,
                    fallback_task_id=resolved_identity.task_id,
                    fallback_task_hash=resolved_identity.task_hash,
                    on_path_missing=lambda source_path_missing, target_path_missing: _print_cleanup_correlation_path_missing_log(
                        task_ref=task_ref,
                        resolved_identity=resolved_identity,
                        event=event,
                        source_path_missing=source_path_missing,
                        target_path_missing=target_path_missing,
                    ),
                )) is None
                else ImportCorrelation(
                    task_ref=correlation.task_ref,
                    task_id=correlation.task_id,
                    task_hash=correlation.task_hash,
                    source_path=correlation.source_path,
                    target_path=correlation.target_path,
                )
            ),
        )

    def resolve_task_identity(
        self,
        *,
        task_ref: str,
        chat_id: int | None,
    ) -> ResolvedCleanupTaskIdentity:
        resolution = resolve_cleanup_task_identity(
            task_ref=task_ref,
            chat_id=chat_id,
            job_lookup=(
                (lambda resolved_chat_id, resolved_task_ref: self._job_repo.get_job_for_chat_ref(
                    chat_id=resolved_chat_id,
                    task_ref=resolved_task_ref,
                ))
                if self._job_repo is not None
                else None
            ),
            on_job_lookup_failed=lambda error: _print_cleanup_job_lookup_failed_log(
                task_ref=task_ref,
                chat_id=chat_id or 0,
                error=error,
            ),
        )

        return ResolvedCleanupTaskIdentity(
            lookup_task_ref=resolution.lookup_task_ref,
            lookup_task_id=resolution.lookup_task_id,
            lookup_task_hash=resolution.lookup_task_hash,
            task_ref=resolution.task_ref,
            task_id=resolution.task_id,
            task_hash=resolution.task_hash,
        )


def _is_cleanup_correlation_row_corrupted_reason(reason: str) -> bool:
    return reason.endswith("corrupted after read")


def run_cleanup_correlation_lookup(
    *,
    resolve_task_identity: Callable[[str, int | None], ResolvedCleanupTaskIdentity],
    fetch_event: Callable[[ResolvedCleanupTaskIdentity], object | None],
    build_correlation_result: Callable[[ResolvedCleanupTaskIdentity, object], CleanupCorrelationResult | None],
    task_ref: str,
    chat_id: int | None,
) -> tuple[ResolvedCleanupTaskIdentity, CleanupCorrelationResult | None]:
    resolved_identity = resolve_task_identity(task_ref, chat_id)
    event = fetch_event(resolved_identity)
    if event is None:
        return resolved_identity, None
    correlation = build_correlation_result(resolved_identity, event)
    return resolved_identity, correlation


def fetch_cleanup_correlation_event(
    *,
    fetch_event: Callable[[], object | None],
    on_result_missing: Callable[[str], None],
    on_row_corrupted: Callable[[str], None],
    on_failed: Callable[[str], None],
    result_missing_reason: str,
    is_row_corrupted_reason: Callable[[str], bool],
) -> object | None:
    try:
        return fetch_event()
    except (JobEventPersistenceError, sqlite3.Error) as error:
        reason = str(error)
        if reason == result_missing_reason:
            on_result_missing(reason)
            return None
        if is_row_corrupted_reason(reason):
            on_row_corrupted(reason)
            return None
        on_failed(reason)
        return None


def build_cleanup_correlation_result(
    *,
    event: object,
    fallback_task_ref: str,
    fallback_task_id: str,
    fallback_task_hash: str,
    on_path_missing: Callable[[bool, bool], None],
) -> CleanupCorrelationResult | None:
    source_path = str(getattr(event, "source_path", "")).strip()
    target_path = str(getattr(event, "target_path", "")).strip()
    if not source_path or not target_path:
        on_path_missing(not source_path, not target_path)
        return None

    return CleanupCorrelationResult(
        task_ref=str(getattr(event, "task_ref", "")).strip() or fallback_task_ref,
        task_id=str(getattr(event, "task_id", "")).strip() or fallback_task_id,
        task_hash=str(getattr(event, "task_hash", "")).strip() or fallback_task_hash,
        source_path=source_path,
        target_path=target_path,
    )


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


def _print_cleanup_correlation_result_missing_log(
    *,
    task_ref: str,
    resolved_identity: ResolvedCleanupTaskIdentity,
    reason: str,
) -> None:
    print(
        f"\033[31m[cleanup 关联结果缺失]\033[0m task_ref={task_ref} "
        f"lookup_task_ref={resolved_identity.lookup_task_ref} lookup_task_id={resolved_identity.lookup_task_id} "
        f"lookup_task_hash={resolved_identity.lookup_task_hash} 原因={reason}",
        flush=True,
    )
    print(
        "\033[33m[处理建议]\033[0m 检查 job_event 关联查询返回是否仍带有完整事件列表；"
        "当前会按未找到关联停路，避免把缺失真相误判成普通“没有 import 关联”。",
        flush=True,
    )


def _print_cleanup_correlation_row_corrupted_log(
    *,
    task_ref: str,
    resolved_identity: ResolvedCleanupTaskIdentity,
    reason: str,
) -> None:
    print(
        f"\033[31m[cleanup 关联记录损坏]\033[0m task_ref={task_ref} "
        f"lookup_task_ref={resolved_identity.lookup_task_ref} lookup_task_id={resolved_identity.lookup_task_id} "
        f"lookup_task_hash={resolved_identity.lookup_task_hash} 原因={reason}",
        flush=True,
    )
    print(
        "\033[33m[处理建议]\033[0m 检查 job_event 导入成功关联里的 task_ref / event_type / source_path / target_path "
        "是否仍是完整真相；当前会按未找到关联停路，避免把坏记录误判成普通“没有 import 关联”。",
        flush=True,
    )


def _print_cleanup_correlation_lookup_failed_log(
    *,
    task_ref: str,
    resolved_identity: ResolvedCleanupTaskIdentity,
    reason: str,
) -> None:
    print(
        f"\033[31m[cleanup 关联查询失败]\033[0m task_ref={task_ref} "
        f"lookup_task_ref={resolved_identity.lookup_task_ref} lookup_task_id={resolved_identity.lookup_task_id} "
        f"lookup_task_hash={resolved_identity.lookup_task_hash} 原因={reason}",
        flush=True,
    )
    print(
        "\033[33m[处理建议]\033[0m 检查 SQLite job_event 是否可读、导入成功事件是否已落盘，"
        "再重试 cleanup。",
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


def resolve_cleanup_task_identity(
    *,
    task_ref: str,
    chat_id: int | None,
    job_lookup: Callable[[int, str], Any | None] | None,
    on_job_lookup_failed: Callable[[Exception], None],
) -> CleanupTaskIdentityResolution:
    resolved_task_ref = task_ref
    resolved_task_id = ""
    resolved_task_hash = ""
    lookup_task_ref = task_ref
    lookup_task_id = task_ref
    lookup_task_hash = task_ref

    if job_lookup is not None and chat_id is not None and chat_id > 0:
        try:
            job = job_lookup(chat_id, task_ref)
        except (JobPersistenceError, sqlite3.Error) as error:
            on_job_lookup_failed(error)
            job = None
        if job is not None:
            resolved_task_ref = (getattr(job, "task_ref", "") or task_ref).strip() or resolved_task_ref
            resolved_task_id = str(getattr(job, "task_id", "") or "").strip()
            resolved_task_hash = str(getattr(job, "task_hash", "") or "").strip()
            lookup_task_ref = resolved_task_ref
            lookup_task_id = resolved_task_id or lookup_task_id
            lookup_task_hash = resolved_task_hash or lookup_task_hash

    return CleanupTaskIdentityResolution(
        lookup_task_ref=lookup_task_ref,
        lookup_task_id=lookup_task_id,
        lookup_task_hash=lookup_task_hash,
        task_ref=resolved_task_ref,
        task_id=resolved_task_id,
        task_hash=resolved_task_hash,
    )

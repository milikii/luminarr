from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from app.db.job_event_repo import JobEventRepo
from app.db.job_repo import JobRepo

CLEANUP_QUERY_USAGE_TEXT = "清理格式：cleanup <任务ID或Hash>"
CLEANUP_CORRELATION_MISSING_TEXT = "未找到带 source_path/target_path 的已导入关联，当前任务暂不能执行 cleanup。"
CLEANUP_TARGET_MISSING_TEXT = "库内目标路径不存在，已拒绝清理下载源资产：{target_path}"
CLEANUP_SOURCE_MISSING_TEXT = "下载源资产已不存在，无需清理：{source_path}"
CLEANUP_SOURCE_TYPE_UNSUPPORTED_TEXT = "下载源不是文件或目录，无法清理。"
CLEANUP_GUARD_REJECTED_TEXT = "检测到 source/target 路径关系异常，已拒绝清理：{source_path} -> {target_path}"
CLEANUP_FAILED_TEXT = "清理下载源资产失败：{reason}"
CLEANUP_SUCCEEDED_TEXT = (
    "已清理下载源资产。\n"
    "任务 ID: {task_id}\n"
    "任务 Hash: {task_hash}\n"
    "源路径: {source_path}\n"
    "保留目标: {target_path}"
)


@dataclass(frozen=True, slots=True)
class ImportCorrelation:
    task_ref: str
    task_id: str
    task_hash: str
    source_path: str
    target_path: str


class CleanupDownloadedSourceService:
    def __init__(
        self,
        job_event_repo: JobEventRepo,
        job_repo: JobRepo | None = None,
    ) -> None:
        self._job_event_repo = job_event_repo
        self._job_repo = job_repo

    def cleanup_by_task_ref(
        self,
        task_ref: str,
        *,
        chat_id: int | None = None,
    ) -> str:
        cleaned_ref = task_ref.strip()
        if not cleaned_ref:
            return CLEANUP_QUERY_USAGE_TEXT

        correlation = self._find_import_correlation(task_ref=cleaned_ref, chat_id=chat_id)
        if correlation is None:
            self._record_event(
                task_ref=cleaned_ref,
                event_type="cleanup.correlation_missing",
                message=CLEANUP_CORRELATION_MISSING_TEXT,
            )
            return CLEANUP_CORRELATION_MISSING_TEXT

        source_path = Path(correlation.source_path).expanduser()
        target_path = Path(correlation.target_path).expanduser()

        if not target_path.exists():
            message = CLEANUP_TARGET_MISSING_TEXT.format(target_path=str(target_path))
            self._record_event(
                task_ref=correlation.task_ref or cleaned_ref,
                task_id=correlation.task_id,
                task_hash=correlation.task_hash,
                event_type="cleanup.target_missing",
                message=message,
                source_path=str(source_path),
                target_path=str(target_path),
            )
            return message

        if not source_path.exists():
            message = CLEANUP_SOURCE_MISSING_TEXT.format(source_path=str(source_path))
            self._record_event(
                task_ref=correlation.task_ref or cleaned_ref,
                task_id=correlation.task_id,
                task_hash=correlation.task_hash,
                event_type="cleanup.source_missing",
                message=message,
                source_path=str(source_path),
                target_path=str(target_path),
            )
            return message

        guard_rejection = _validate_cleanup_paths(source_path=source_path, target_path=target_path)
        if guard_rejection is not None:
            self._record_event(
                task_ref=correlation.task_ref or cleaned_ref,
                task_id=correlation.task_id,
                task_hash=correlation.task_hash,
                event_type="cleanup.guard_rejected",
                message=guard_rejection,
                source_path=str(source_path),
                target_path=str(target_path),
            )
            return guard_rejection

        try:
            _delete_source_asset(source_path)
        except OSError as error:
            message = CLEANUP_FAILED_TEXT.format(reason=str(error))
            self._record_event(
                task_ref=correlation.task_ref or cleaned_ref,
                task_id=correlation.task_id,
                task_hash=correlation.task_hash,
                event_type="cleanup.failed",
                message=message,
                source_path=str(source_path),
                target_path=str(target_path),
            )
            print(
                f"\033[31m[下载源清理失败]\033[0m task_id={correlation.task_id} "
                f"task_hash={correlation.task_hash} source={source_path} 原因={error}",
                flush=True,
            )
            print(
                "\033[33m[处理建议]\033[0m 检查 source_path 是否仍可访问、当前进程是否有删除权限，"
                "并确认库内目标路径仍然存在后再重试 cleanup。",
                flush=True,
            )
            return message

        message = CLEANUP_SUCCEEDED_TEXT.format(
            task_id=correlation.task_id,
            task_hash=correlation.task_hash,
            source_path=str(source_path),
            target_path=str(target_path),
        )
        self._record_event(
            task_ref=correlation.task_ref or cleaned_ref,
            task_id=correlation.task_id,
            task_hash=correlation.task_hash,
            event_type="cleanup.succeeded",
            message=message,
            source_path=str(source_path),
            target_path=str(target_path),
        )
        return message

    def _find_import_correlation(
        self,
        *,
        task_ref: str,
        chat_id: int | None,
    ) -> ImportCorrelation | None:
        resolved_task_ref = task_ref
        resolved_task_id = task_ref
        resolved_task_hash = task_ref

        if self._job_repo is not None and chat_id is not None and chat_id > 0:
            try:
                job = self._job_repo.get_job_for_chat_ref(chat_id=chat_id, task_ref=task_ref)
            except Exception:
                job = None
            if job is not None:
                resolved_task_ref = job.task_ref or task_ref
                resolved_task_id = job.task_id or task_ref
                resolved_task_hash = job.task_hash or task_ref

        try:
            event = self._job_event_repo.find_latest_import_correlation(
                task_ref=resolved_task_ref,
                task_id=resolved_task_id,
                task_hash=resolved_task_hash,
            )
        except Exception as error:
            print(
                f"\033[31m[cleanup 关联查询失败]\033[0m task_ref={task_ref} 原因={error}",
                flush=True,
            )
            print(
                "\033[33m[处理建议]\033[0m 检查 SQLite job_event 是否可读、导入成功事件是否已落盘，"
                "再重试 cleanup。",
                flush=True,
            )
            return None
        if event is None:
            return None
        source_path = event.source_path.strip()
        target_path = event.target_path.strip()
        if not source_path or not target_path:
            return None
        return ImportCorrelation(
            task_ref=event.task_ref.strip() or resolved_task_ref,
            task_id=event.task_id.strip(),
            task_hash=event.task_hash.strip(),
            source_path=source_path,
            target_path=target_path,
        )

    def _record_event(
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
        except Exception:
            return


def parse_cleanup_query(text: str) -> str | None:
    cleaned_text = text.strip()
    matched = re.match(r"^(?:(?i:cleanup)|清理)(?:\s+(.*))?$", cleaned_text)
    if not matched:
        return None
    return (matched.group(1) or "").strip()


def _validate_cleanup_paths(*, source_path: Path, target_path: Path) -> str | None:
    if not source_path.is_file() and not source_path.is_dir():
        return CLEANUP_SOURCE_TYPE_UNSUPPORTED_TEXT

    source_resolved = source_path.resolve(strict=True)
    target_resolved = target_path.resolve(strict=True)
    if (
        source_resolved == target_resolved
        or source_resolved in target_resolved.parents
        or target_resolved in source_resolved.parents
    ):
        return CLEANUP_GUARD_REJECTED_TEXT.format(
            source_path=str(source_path),
            target_path=str(target_path),
        )
    return None


def _delete_source_asset(source_path: Path) -> None:
    if source_path.is_dir():
        shutil.rmtree(source_path)
        return
    if source_path.is_file():
        source_path.unlink()
        return
    raise OSError(CLEANUP_SOURCE_TYPE_UNSUPPORTED_TEXT)

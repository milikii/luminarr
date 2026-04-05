from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from app.db.job_event_repo import JobEventRepo
from app.db.job_repo import JobRepo

CLEANUP_QUERY_USAGE_TEXT = (
    "cleanup 用法：\n"
    "cleanup <任务ID或Hash> / 清理 <任务ID或Hash>：实际清理下载源资产\n"
    "cleanup inspect <任务ID或Hash> / 清理检查 <任务ID或Hash>：只读预检，不删除任何文件"
)
CLEANUP_INSPECT_QUERY_USAGE_TEXT = (
    "cleanup inspect 用法：\n"
    "cleanup inspect <任务ID或Hash> / 清理检查 <任务ID或Hash>：只读预检，不删除任何文件\n"
    "cleanup <任务ID或Hash> / 清理 <任务ID或Hash>：实际清理下载源资产"
)
CLEANUP_CORRELATION_MISSING_TEXT = "未找到带 source_path/target_path 的已导入关联，当前任务暂不能执行 cleanup。"
CLEANUP_TARGET_MISSING_TEXT = "库内目标路径不存在，已拒绝清理下载源资产：{target_path}"
CLEANUP_SOURCE_MISSING_TEXT = "下载源资产已不存在，无需清理：{source_path}"
CLEANUP_SOURCE_TYPE_UNSUPPORTED_TEXT = "下载源不是文件或目录，无法清理。"
CLEANUP_GUARD_REJECTED_TEXT = "检测到 source/target 路径关系异常，已拒绝清理：{source_path} -> {target_path}"
CLEANUP_FAILED_TEXT = "清理下载源资产失败：{reason}"
CLEANUP_INSPECT_RESULT_TEMPLATE = (
    "清理预检结果：\n"
    "查询引用: {query_ref}\n"
    "任务 ID: {task_id}\n"
    "任务 Hash: {task_hash}\n"
    "关联: {correlation_status}\n"
    "源路径: {source_path}\n"
    "源路径状态: {source_status}\n"
    "目标路径: {target_path}\n"
    "目标路径状态: {target_status}\n"
    "当前 guardrail: {guardrail_status}\n"
    "结论: {conclusion}"
)
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


@dataclass(frozen=True, slots=True)
class CleanupInspection:
    query_ref: str
    task_ref: str
    task_id: str
    task_hash: str
    source_path: str
    target_path: str
    correlation_found: bool
    source_exists: bool | None
    target_exists: bool | None
    cleanup_allowed: bool
    conclusion: str


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

        inspection = self._inspect_cleanup(task_ref=cleaned_ref, chat_id=chat_id)
        if not inspection.correlation_found:
            self._record_event(
                task_ref=cleaned_ref,
                event_type="cleanup.correlation_missing",
                message=CLEANUP_CORRELATION_MISSING_TEXT,
            )
            return CLEANUP_CORRELATION_MISSING_TEXT

        source_path = Path(inspection.source_path).expanduser()
        target_path = Path(inspection.target_path).expanduser()
        task_ref_for_event = inspection.task_ref or cleaned_ref

        if inspection.target_exists is False:
            message = inspection.conclusion
            self._record_event(
                task_ref=task_ref_for_event,
                task_id=inspection.task_id,
                task_hash=inspection.task_hash,
                event_type="cleanup.target_missing",
                message=message,
                source_path=str(source_path),
                target_path=str(target_path),
            )
            return message

        if inspection.source_exists is False:
            message = inspection.conclusion
            self._record_event(
                task_ref=task_ref_for_event,
                task_id=inspection.task_id,
                task_hash=inspection.task_hash,
                event_type="cleanup.source_missing",
                message=message,
                source_path=str(source_path),
                target_path=str(target_path),
            )
            return message

        if not inspection.cleanup_allowed:
            self._record_event(
                task_ref=task_ref_for_event,
                task_id=inspection.task_id,
                task_hash=inspection.task_hash,
                event_type="cleanup.guard_rejected",
                message=inspection.conclusion,
                source_path=str(source_path),
                target_path=str(target_path),
            )
            return inspection.conclusion

        try:
            _delete_source_asset(source_path)
        except OSError as error:
            message = CLEANUP_FAILED_TEXT.format(reason=str(error))
            self._record_event(
                task_ref=task_ref_for_event,
                task_id=inspection.task_id,
                task_hash=inspection.task_hash,
                event_type="cleanup.failed",
                message=message,
                source_path=str(source_path),
                target_path=str(target_path),
            )
            print(
                f"\033[31m[下载源清理失败]\033[0m task_id={inspection.task_id} "
                f"task_hash={inspection.task_hash} source={source_path} 原因={error}",
                flush=True,
            )
            print(
                "\033[33m[处理建议]\033[0m 检查 source_path 是否仍可访问、当前进程是否有删除权限，"
                "并确认库内目标路径仍然存在后再重试 cleanup。",
                flush=True,
            )
            return message

        message = CLEANUP_SUCCEEDED_TEXT.format(
            task_id=inspection.task_id,
            task_hash=inspection.task_hash,
            source_path=str(source_path),
            target_path=str(target_path),
        )
        self._record_event(
            task_ref=task_ref_for_event,
            task_id=inspection.task_id,
            task_hash=inspection.task_hash,
            event_type="cleanup.succeeded",
            message=message,
            source_path=str(source_path),
            target_path=str(target_path),
        )
        return message

    def inspect_by_task_ref(
        self,
        task_ref: str,
        *,
        chat_id: int | None = None,
    ) -> str:
        cleaned_ref = task_ref.strip()
        if not cleaned_ref:
            return CLEANUP_INSPECT_QUERY_USAGE_TEXT

        inspection = self._inspect_cleanup(task_ref=cleaned_ref, chat_id=chat_id)
        lines = [
            CLEANUP_INSPECT_RESULT_TEMPLATE.format(
                query_ref=inspection.query_ref,
                task_id=inspection.task_id or "-",
                task_hash=inspection.task_hash or "-",
                correlation_status="已找到" if inspection.correlation_found else "未找到",
                source_path=inspection.source_path or "-",
                source_status=_format_path_status(inspection.source_exists),
                target_path=inspection.target_path or "-",
                target_status=_format_path_status(inspection.target_exists),
                guardrail_status="允许 cleanup" if inspection.cleanup_allowed else "拒绝 cleanup",
                conclusion=inspection.conclusion,
            )
        ]
        if inspection.cleanup_allowed:
            lines.append(f"执行命令: cleanup {_preferred_cleanup_ref(inspection)}")
        return "\n".join(lines)

    def _inspect_cleanup(
        self,
        *,
        task_ref: str,
        chat_id: int | None,
    ) -> CleanupInspection:
        correlation = self._find_import_correlation(task_ref=task_ref, chat_id=chat_id)
        if correlation is None:
            return CleanupInspection(
                query_ref=task_ref,
                task_ref=task_ref,
                task_id="",
                task_hash="",
                source_path="",
                target_path="",
                correlation_found=False,
                source_exists=None,
                target_exists=None,
                cleanup_allowed=False,
                conclusion=CLEANUP_CORRELATION_MISSING_TEXT,
            )

        source_path = Path(correlation.source_path).expanduser()
        target_path = Path(correlation.target_path).expanduser()
        target_exists = target_path.exists()
        source_exists = source_path.exists()

        if not target_exists:
            conclusion = CLEANUP_TARGET_MISSING_TEXT.format(target_path=str(target_path))
            cleanup_allowed = False
        elif not source_exists:
            conclusion = CLEANUP_SOURCE_MISSING_TEXT.format(source_path=str(source_path))
            cleanup_allowed = False
        else:
            guard_rejection = _validate_cleanup_paths(source_path=source_path, target_path=target_path)
            if guard_rejection is not None:
                conclusion = guard_rejection
                cleanup_allowed = False
            else:
                conclusion = "已通过 cleanup 预检，可执行清理下载源资产。"
                cleanup_allowed = True

        return CleanupInspection(
            query_ref=task_ref,
            task_ref=correlation.task_ref.strip() or task_ref,
            task_id=correlation.task_id.strip(),
            task_hash=correlation.task_hash.strip(),
            source_path=str(source_path),
            target_path=str(target_path),
            correlation_found=True,
            source_exists=source_exists,
            target_exists=target_exists,
            cleanup_allowed=cleanup_allowed,
            conclusion=conclusion,
        )

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


def parse_cleanup_inspect_query(text: str) -> str | None:
    cleaned_text = text.strip()
    matched = re.match(r"^(?:(?i:cleanup)\s+(?i:inspect)|清理检查)(?:\s+(.*))?$", cleaned_text)
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


def _format_path_status(exists: bool | None) -> str:
    if exists is None:
        return "未找到关联"
    if exists:
        return "存在"
    return "不存在"


def _preferred_cleanup_ref(inspection: CleanupInspection) -> str:
    for value in (inspection.task_hash, inspection.task_id, inspection.task_ref, inspection.query_ref):
        cleaned_value = value.strip()
        if cleaned_value:
            return cleaned_value
    return inspection.query_ref

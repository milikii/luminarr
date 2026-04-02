from __future__ import annotations

import errno
import os
import re
from collections.abc import Awaitable, Callable
from pathlib import Path

from app.clients.transmission import TransmissionImportSource
from app.db.job_event_repo import JobEventRepo

GetImportSourceFunc = Callable[[str], Awaitable[TransmissionImportSource | None]]
RefreshMediaServerFunc = Callable[[], Awaitable[str]]

IMPORT_QUERY_USAGE_TEXT = "导入格式：import <任务ID或Hash>"
IMPORT_NOT_FOUND_TEXT = "未找到对应下载任务，请检查任务 ID/Hash。"
IMPORT_QUERY_FAILED_TEXT = "查询下载任务失败，请稍后重试。"
IMPORT_NOT_COMPLETED_TEXT = "任务尚未完成，当前进度 {progress:.1f}%，暂不能导入。"
IMPORT_SOURCE_MISSING_TEXT = "下载源路径不存在，无法导入。"
IMPORT_SOURCE_TYPE_UNSUPPORTED_TEXT = "下载源不是文件或目录，无法导入。"
IMPORT_TARGET_EXISTS_TEXT = "目标已存在，已拒绝覆盖：{target_path}"
IMPORT_PREPARE_TARGET_FAILED_TEXT = "创建目标目录失败：{target_path}"
IMPORT_HARDLINK_CROSS_FILESYSTEM_TEXT = "硬链接失败：源和目标不在同一文件系统。"
IMPORT_HARDLINK_FAILED_TEXT = "硬链接失败：{reason}"
IMPORT_REFRESH_FAILED_TEXT = "媒体库刷新失败：未知错误"
IMPORT_REFRESH_SUCCESS_TEXT = "媒体库刷新成功。"


class ImportToLibraryService:
    def __init__(
        self,
        get_import_source_func: GetImportSourceFunc,
        library_target_dir: str,
        refresh_media_server_func: RefreshMediaServerFunc | None = None,
        job_event_repo: JobEventRepo | None = None,
    ) -> None:
        self._get_import_source_func = get_import_source_func
        self._library_target_dir = Path(library_target_dir).expanduser()
        self._refresh_media_server_func = refresh_media_server_func
        self._job_event_repo = job_event_repo

    async def import_by_task_ref(self, task_ref: str) -> str:
        cleaned_ref = task_ref.strip()
        if not cleaned_ref:
            return IMPORT_QUERY_USAGE_TEXT

        try:
            import_source = await self._get_import_source_func(cleaned_ref)
        except Exception:
            self._record_event(
                task_ref=cleaned_ref,
                event_type="import.query_failed",
                message=IMPORT_QUERY_FAILED_TEXT,
            )
            return IMPORT_QUERY_FAILED_TEXT
        if import_source is None:
            self._record_event(
                task_ref=cleaned_ref,
                event_type="import.not_found",
                message=IMPORT_NOT_FOUND_TEXT,
            )
            return IMPORT_NOT_FOUND_TEXT

        progress = _clamp_progress(import_source.percent_done)
        if not _is_download_completed(import_source):
            self._record_event(
                task_ref=cleaned_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                event_type="import.not_completed",
                message=IMPORT_NOT_COMPLETED_TEXT.format(progress=progress),
            )
            return IMPORT_NOT_COMPLETED_TEXT.format(progress=progress)

        source_path = Path(import_source.download_dir) / import_source.name
        if not source_path.exists():
            self._record_event(
                task_ref=cleaned_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                event_type="import.source_missing",
                message=IMPORT_SOURCE_MISSING_TEXT,
            )
            return IMPORT_SOURCE_MISSING_TEXT

        target_root = self._library_target_dir
        try:
            target_root.mkdir(parents=True, exist_ok=True)
        except OSError:
            self._record_event(
                task_ref=cleaned_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                event_type="import.prepare_target_failed",
                message=IMPORT_PREPARE_TARGET_FAILED_TEXT.format(target_path=str(target_root)),
            )
            return IMPORT_PREPARE_TARGET_FAILED_TEXT.format(target_path=str(target_root))

        target_path = target_root / source_path.name
        if target_path.exists():
            self._record_event(
                task_ref=cleaned_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                event_type="import.target_exists",
                message=IMPORT_TARGET_EXISTS_TEXT.format(target_path=str(target_path)),
            )
            return IMPORT_TARGET_EXISTS_TEXT.format(target_path=str(target_path))

        try:
            _hardlink_import(source_path, target_path)
        except FileExistsError:
            self._record_event(
                task_ref=cleaned_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                event_type="import.target_exists",
                message=IMPORT_TARGET_EXISTS_TEXT.format(target_path=str(target_path)),
            )
            return IMPORT_TARGET_EXISTS_TEXT.format(target_path=str(target_path))
        except OSError as exc:
            if exc.errno == errno.EXDEV:
                self._record_event(
                    task_ref=cleaned_ref,
                    task_id=import_source.task_id,
                    task_hash=import_source.task_hash,
                    event_type="import.hardlink_cross_filesystem",
                    message=IMPORT_HARDLINK_CROSS_FILESYSTEM_TEXT,
                )
                return IMPORT_HARDLINK_CROSS_FILESYSTEM_TEXT
            self._record_event(
                task_ref=cleaned_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                event_type="import.hardlink_failed",
                message=IMPORT_HARDLINK_FAILED_TEXT.format(reason=str(exc)),
            )
            return IMPORT_HARDLINK_FAILED_TEXT.format(reason=str(exc))

        import_success_text = (
            f"导入成功：{import_source.name}\n"
            f"任务 ID: {import_source.task_id}\n"
            f"任务 Hash: {import_source.task_hash}\n"
            f"目标路径: {target_path}"
        )
        self._record_event(
            task_ref=cleaned_ref,
            task_id=import_source.task_id,
            task_hash=import_source.task_hash,
            event_type="import.succeeded",
            message=str(target_path),
        )

        if self._refresh_media_server_func is None:
            return import_success_text

        try:
            refresh_text = await self._refresh_media_server_func()
        except Exception:
            refresh_text = IMPORT_REFRESH_FAILED_TEXT
            self._record_event(
                task_ref=cleaned_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                event_type="refresh.failed",
                message=refresh_text,
            )
            return f"{import_success_text}\n{refresh_text}"
        if refresh_text == IMPORT_REFRESH_SUCCESS_TEXT:
            self._record_event(
                task_ref=cleaned_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                event_type="refresh.succeeded",
                message=refresh_text,
            )
        else:
            self._record_event(
                task_ref=cleaned_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                event_type="refresh.failed",
                message=refresh_text,
            )
        return f"{import_success_text}\n{refresh_text}"

    def _record_event(
        self,
        *,
        task_ref: str,
        event_type: str,
        message: str,
        task_id: str = "",
        task_hash: str = "",
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
            )
        except Exception:
            pass


def parse_import_query(text: str) -> str | None:
    cleaned_text = text.strip()
    matched = re.match(r"^(?:(?i:import)|导入)(?:\s+(.*))?$", cleaned_text)
    if not matched:
        return None
    return (matched.group(1) or "").strip()


def _is_download_completed(import_source: TransmissionImportSource) -> bool:
    if import_source.is_finished:
        return True
    return import_source.percent_done >= 1.0


def _clamp_progress(raw_progress: float) -> float:
    progress = raw_progress * 100
    if progress < 0:
        return 0.0
    if progress > 100:
        return 100.0
    return progress


def _hardlink_import(source_path: Path, target_path: Path) -> None:
    if source_path.is_file():
        os.link(source_path, target_path)
        return
    if source_path.is_dir():
        _hardlink_directory(source_path, target_path)
        return
    raise OSError(errno.EINVAL, IMPORT_SOURCE_TYPE_UNSUPPORTED_TEXT)


def _hardlink_directory(source_dir: Path, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=False)
    for current_dir, _, file_names in os.walk(source_dir):
        current_source = Path(current_dir)
        relative = current_source.relative_to(source_dir)
        current_target = target_dir / relative
        current_target.mkdir(parents=True, exist_ok=True)
        for file_name in file_names:
            src_file = current_source / file_name
            dst_file = current_target / file_name
            if dst_file.exists():
                raise FileExistsError(str(dst_file))
            os.link(src_file, dst_file)

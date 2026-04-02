from __future__ import annotations

import errno
import os
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from app.clients.transmission import TransmissionImportSource
from app.db.approval_repo import APPROVAL_STATUS_PENDING, ApprovalRepo
from app.db.job_event_repo import JobEventRepo

GetImportSourceFunc = Callable[[str], Awaitable[TransmissionImportSource | None]]
RefreshMediaServerFunc = Callable[[], Awaitable[str]]

IMPORT_QUERY_USAGE_TEXT = "导入格式：import <任务ID或Hash>"
CONFIRM_QUERY_USAGE_TEXT = "确认格式：confirm <任务ID或Hash>"
IMPORT_NOT_FOUND_TEXT = "未找到对应下载任务，请检查任务 ID/Hash。"
IMPORT_QUERY_FAILED_TEXT = "查询下载任务失败，请稍后重试。"
IMPORT_NOT_COMPLETED_TEXT = "任务尚未完成，当前进度 {progress:.1f}%，暂不能导入。"
IMPORT_SOURCE_MISSING_TEXT = "下载源路径不存在，无法导入。"
IMPORT_SOURCE_TYPE_UNSUPPORTED_TEXT = "下载源不是文件或目录，无法导入。"
IMPORT_TARGET_EXISTS_TEXT = "目标已存在，已拒绝覆盖：{target_path}"
IMPORT_PREPARE_TARGET_FAILED_TEXT = "创建目标目录失败：{target_path}"
IMPORT_HARDLINK_CROSS_FILESYSTEM_TEXT = "硬链接失败：源和目标不在同一文件系统。"
IMPORT_HARDLINK_FAILED_TEXT = "硬链接失败：{reason}"
IMPORT_APPROVAL_PENDING_TEXT = (
    "导入待确认：{name}\n"
    "任务 ID: {task_id}\n"
    "任务 Hash: {task_hash}\n"
    "请发送 confirm {task_ref} 执行导入。"
)
IMPORT_CONFIRM_NOT_PENDING_TEXT = "没有待确认的导入请求，请先发送 import <任务ID或Hash>。"
IMPORT_REFRESH_FAILED_TEXT = "媒体库刷新失败：未知错误"
IMPORT_REFRESH_SUCCESS_TEXT = "媒体库刷新成功。"


@dataclass(frozen=True, slots=True)
class PreparedImport:
    import_source: TransmissionImportSource
    source_path: Path
    target_path: Path


class ImportToLibraryService:
    def __init__(
        self,
        get_import_source_func: GetImportSourceFunc,
        library_target_dir: str,
        refresh_media_server_func: RefreshMediaServerFunc | None = None,
        job_event_repo: JobEventRepo | None = None,
        approval_repo: ApprovalRepo | None = None,
    ) -> None:
        self._get_import_source_func = get_import_source_func
        self._library_target_dir = Path(library_target_dir).expanduser()
        self._refresh_media_server_func = refresh_media_server_func
        self._job_event_repo = job_event_repo
        self._approval_repo = approval_repo
        self._pending_import_identities: set[tuple[str, str]] = set()
        self._pending_import_lease_versions: dict[tuple[str, str], int] = {}

    async def import_by_task_ref(self, task_ref: str) -> str:
        cleaned_ref = task_ref.strip()
        if not cleaned_ref:
            return IMPORT_QUERY_USAGE_TEXT

        prepared_import, error_text = await self._prepare_import(cleaned_ref)
        if prepared_import is None:
            return error_text

        import_source = prepared_import.import_source
        self._record_pending_approval(
            task_ref=cleaned_ref,
            task_id=import_source.task_id,
            task_hash=import_source.task_hash,
        )
        self._record_event(
            task_ref=cleaned_ref,
            task_id=import_source.task_id,
            task_hash=import_source.task_hash,
            event_type="import.approval_pending",
            message=cleaned_ref,
        )
        return IMPORT_APPROVAL_PENDING_TEXT.format(
            name=import_source.name,
            task_id=import_source.task_id,
            task_hash=import_source.task_hash,
            task_ref=cleaned_ref,
        )

    async def confirm_import_by_task_ref(self, task_ref: str) -> str:
        cleaned_ref = task_ref.strip()
        if not cleaned_ref:
            return CONFIRM_QUERY_USAGE_TEXT

        prepared_import, error_text = await self._prepare_import(cleaned_ref)
        if prepared_import is None:
            return error_text

        import_source = prepared_import.import_source
        stale_text = self._find_version_stale_rejection_text(
            task_id=import_source.task_id,
            task_hash=import_source.task_hash,
        )
        if stale_text is not None:
            self._record_event(
                task_ref=cleaned_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                event_type="import.stale_rejected",
                message=stale_text,
            )
            return stale_text

        expected_lease_version = self._resolve_pending_lease_version(
            task_id=import_source.task_id,
            task_hash=import_source.task_hash,
        )
        if expected_lease_version <= 0:
            self._record_event(
                task_ref=cleaned_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                event_type="import.confirm_not_pending",
                message=IMPORT_CONFIRM_NOT_PENDING_TEXT,
            )
            return IMPORT_CONFIRM_NOT_PENDING_TEXT

        approved = self._record_import_approval(
            task_ref=cleaned_ref,
            task_id=import_source.task_id,
            task_hash=import_source.task_hash,
            expected_lease_version=expected_lease_version,
        )
        if not approved:
            stale_text = self._find_version_stale_rejection_text(
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
            )
            rejection_text = stale_text or IMPORT_CONFIRM_NOT_PENDING_TEXT
            self._record_event(
                task_ref=cleaned_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                event_type="import.stale_rejected",
                message=rejection_text,
            )
            return rejection_text

        self._record_event(
            task_ref=cleaned_ref,
            task_id=import_source.task_id,
            task_hash=import_source.task_hash,
            event_type="import.approval_confirmed",
            message=cleaned_ref,
        )

        reply, imported = await self._execute_import(cleaned_ref, prepared_import)
        if imported:
            self._record_executed_lease_version(
                task_ref=cleaned_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                executed_lease_version=expected_lease_version,
            )
        else:
            self._restore_pending_approval(
                task_ref=cleaned_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                expected_lease_version=expected_lease_version,
            )
        return reply

    async def _prepare_import(self, task_ref: str) -> tuple[PreparedImport | None, str]:
        try:
            import_source = await self._get_import_source_func(task_ref)
        except Exception:
            self._record_event(
                task_ref=task_ref,
                event_type="import.query_failed",
                message=IMPORT_QUERY_FAILED_TEXT,
            )
            return None, IMPORT_QUERY_FAILED_TEXT

        if import_source is None:
            self._record_event(
                task_ref=task_ref,
                event_type="import.not_found",
                message=IMPORT_NOT_FOUND_TEXT,
            )
            return None, IMPORT_NOT_FOUND_TEXT

        progress = _clamp_progress(import_source.percent_done)
        if not _is_download_completed(import_source):
            message = IMPORT_NOT_COMPLETED_TEXT.format(progress=progress)
            self._record_event(
                task_ref=task_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                event_type="import.not_completed",
                message=message,
            )
            return None, message

        source_path = Path(import_source.download_dir) / import_source.name
        if not source_path.exists():
            self._record_event(
                task_ref=task_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                event_type="import.source_missing",
                message=IMPORT_SOURCE_MISSING_TEXT,
            )
            return None, IMPORT_SOURCE_MISSING_TEXT

        target_root = self._library_target_dir
        try:
            target_root.mkdir(parents=True, exist_ok=True)
        except OSError:
            message = IMPORT_PREPARE_TARGET_FAILED_TEXT.format(target_path=str(target_root))
            self._record_event(
                task_ref=task_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                event_type="import.prepare_target_failed",
                message=message,
            )
            return None, message

        target_path = target_root / source_path.name
        if target_path.exists():
            message = IMPORT_TARGET_EXISTS_TEXT.format(target_path=str(target_path))
            self._record_event(
                task_ref=task_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                event_type="import.target_exists",
                message=message,
            )
            return None, message

        return PreparedImport(import_source=import_source, source_path=source_path, target_path=target_path), ""

    async def _execute_import(self, task_ref: str, prepared_import: PreparedImport) -> tuple[str, bool]:
        import_source = prepared_import.import_source
        source_path = prepared_import.source_path
        target_path = prepared_import.target_path

        try:
            _hardlink_import(source_path, target_path)
        except FileExistsError:
            message = IMPORT_TARGET_EXISTS_TEXT.format(target_path=str(target_path))
            self._record_event(
                task_ref=task_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                event_type="import.target_exists",
                message=message,
            )
            return message, False
        except OSError as exc:
            if exc.errno == errno.EXDEV:
                self._record_event(
                    task_ref=task_ref,
                    task_id=import_source.task_id,
                    task_hash=import_source.task_hash,
                    event_type="import.hardlink_cross_filesystem",
                    message=IMPORT_HARDLINK_CROSS_FILESYSTEM_TEXT,
                )
                return IMPORT_HARDLINK_CROSS_FILESYSTEM_TEXT, False
            message = IMPORT_HARDLINK_FAILED_TEXT.format(reason=str(exc))
            self._record_event(
                task_ref=task_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                event_type="import.hardlink_failed",
                message=message,
            )
            return message, False

        import_success_text = (
            f"导入成功：{import_source.name}\n"
            f"任务 ID: {import_source.task_id}\n"
            f"任务 Hash: {import_source.task_hash}\n"
            f"目标路径: {target_path}"
        )
        self._record_event(
            task_ref=task_ref,
            task_id=import_source.task_id,
            task_hash=import_source.task_hash,
            event_type="import.succeeded",
            message=str(target_path),
        )

        if self._refresh_media_server_func is None:
            return import_success_text, True

        try:
            refresh_text = await self._refresh_media_server_func()
        except Exception:
            refresh_text = IMPORT_REFRESH_FAILED_TEXT
            self._record_event(
                task_ref=task_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                event_type="refresh.failed",
                message=refresh_text,
            )
            return f"{import_success_text}\n{refresh_text}", True

        if refresh_text == IMPORT_REFRESH_SUCCESS_TEXT:
            self._record_event(
                task_ref=task_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                event_type="refresh.succeeded",
                message=refresh_text,
            )
        else:
            self._record_event(
                task_ref=task_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                event_type="refresh.failed",
                message=refresh_text,
            )
        return f"{import_success_text}\n{refresh_text}", True

    def _record_pending_approval(self, *, task_ref: str, task_id: str, task_hash: str) -> int:
        identity = (task_id.strip(), task_hash.strip())
        if not identity[0] or not identity[1]:
            return 0

        in_memory_next_lease = self._pending_import_lease_versions.get(identity, 0) + 1
        lease_version = in_memory_next_lease

        if self._approval_repo is None:
            self._pending_import_lease_versions[identity] = lease_version
            self._pending_import_identities.add(identity)
            return lease_version
        try:
            requested_lease = self._approval_repo.request_import_approval(
                task_id=task_id,
                task_hash=task_hash,
                task_ref=task_ref,
            )
            if requested_lease > 0:
                lease_version = requested_lease
        except Exception:
            lease_version = in_memory_next_lease

        self._pending_import_lease_versions[identity] = lease_version
        self._pending_import_identities.add(identity)
        return lease_version

    def _record_import_approval(
        self,
        *,
        task_ref: str,
        task_id: str,
        task_hash: str,
        expected_lease_version: int,
    ) -> bool:
        identity = (task_id.strip(), task_hash.strip())
        if not identity[0] or not identity[1]:
            return False
        if expected_lease_version <= 0:
            return False

        if self._approval_repo is None:
            current_lease = self._pending_import_lease_versions.get(identity, 0)
            if identity not in self._pending_import_identities or current_lease != expected_lease_version:
                return False
            self._pending_import_identities.remove(identity)
            return True

        approved = False
        try:
            approved = self._approval_repo.approve_import(
                task_id=task_id,
                task_hash=task_hash,
                task_ref=task_ref,
                expected_lease_version=expected_lease_version,
            )
        except Exception:
            current_lease = self._pending_import_lease_versions.get(identity, 0)
            approved = identity in self._pending_import_identities and current_lease == expected_lease_version

        if approved and identity in self._pending_import_identities:
            self._pending_import_identities.remove(identity)
        return approved

    def _restore_pending_approval(
        self,
        *,
        task_ref: str,
        task_id: str,
        task_hash: str,
        expected_lease_version: int,
    ) -> None:
        identity = (task_id.strip(), task_hash.strip())
        if not identity[0] or not identity[1]:
            return
        if expected_lease_version <= 0:
            return
        self._pending_import_identities.add(identity)
        self._pending_import_lease_versions[identity] = expected_lease_version
        if self._approval_repo is None:
            return
        try:
            self._approval_repo.restore_import_pending(
                task_id=task_id,
                task_hash=task_hash,
                task_ref=task_ref,
                expected_lease_version=expected_lease_version,
            )
        except Exception:
            return

    def _record_executed_lease_version(
        self,
        *,
        task_ref: str,
        task_id: str,
        task_hash: str,
        executed_lease_version: int,
    ) -> None:
        _ = task_ref
        identity = (task_id.strip(), task_hash.strip())
        if identity[0] and identity[1] and executed_lease_version > 0:
            self._pending_import_lease_versions[identity] = executed_lease_version
        if self._approval_repo is None:
            return
        try:
            self._approval_repo.mark_import_executed(
                task_id=task_id,
                task_hash=task_hash,
                executed_lease_version=executed_lease_version,
            )
        except Exception:
            return

    def _resolve_pending_lease_version(self, *, task_id: str, task_hash: str) -> int:
        identity = (task_id.strip(), task_hash.strip())
        if not identity[0] or not identity[1]:
            return 0
        if self._approval_repo is None:
            if identity not in self._pending_import_identities:
                return 0
            return self._pending_import_lease_versions.get(identity, 1)

        try:
            approval_record = self._approval_repo.get_import_approval(task_id=task_id, task_hash=task_hash)
        except Exception:
            if identity not in self._pending_import_identities:
                return 0
            return self._pending_import_lease_versions.get(identity, 1)
        if approval_record is None:
            if identity not in self._pending_import_identities:
                return 0
            return self._pending_import_lease_versions.get(identity, 1)
        if approval_record.status != APPROVAL_STATUS_PENDING:
            return 0
        return max(0, approval_record.lease_version)

    def _find_version_stale_rejection_text(self, *, task_id: str, task_hash: str) -> str | None:
        if self._approval_repo is None:
            return None
        try:
            approval_record = self._approval_repo.get_import_approval(task_id=task_id, task_hash=task_hash)
        except Exception:
            return None
        if approval_record is None:
            return None
        if approval_record.lease_version <= 0:
            return None
        if approval_record.executed_version < approval_record.lease_version:
            return None

        stale_target_path = self._find_latest_import_target_path(task_id=task_id, task_hash=task_hash)
        if stale_target_path:
            return IMPORT_TARGET_EXISTS_TEXT.format(target_path=stale_target_path)
        return IMPORT_CONFIRM_NOT_PENDING_TEXT

    def _find_latest_import_target_path(self, *, task_id: str, task_hash: str) -> str | None:
        if self._job_event_repo is None:
            return None
        try:
            events = self._job_event_repo.list_events_for_task_identity(task_id=task_id, task_hash=task_hash)
        except Exception:
            return None
        for event in reversed(events):
            if event.event_type != "import.succeeded":
                continue
            target_path = event.message.strip()
            if target_path:
                return target_path
            return None
        return None

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


def parse_confirm_query(text: str) -> str | None:
    cleaned_text = text.strip()
    matched = re.match(r"^(?:(?i:confirm)|确认)(?:\s+(.*))?$", cleaned_text)
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

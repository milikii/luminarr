from __future__ import annotations

import errno
import json
import os
import re
import shutil
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from app.clients.transmission import TransmissionImportSource
from app.db.approval_repo import (
    APPROVAL_STATUS_PENDING,
    DEFAULT_PENDING_TIMEOUT_SECONDS,
    ApprovalRecord,
    ApprovalRepo,
)
from app.db.job_event_repo import JobEventRepo
from app.db.job_repo import JOB_STATE_PENDING_APPROVAL, JobRecord, JobRepo, WORKFLOW_IMPORT_TO_LIBRARY
from app.services.metadata_scraper import MetadataScrapeInput, MetadataScrapeResult
from app.services.subtitle_translator import SubtitleTranslateInput, SubtitleTranslateResult

GetImportSourceFunc = Callable[..., Awaitable[TransmissionImportSource | None]]
RefreshMediaServerFunc = Callable[[], Awaitable[str]]
MetadataScrapeFunc = Callable[[MetadataScrapeInput], Awaitable[MetadataScrapeResult]]
SubtitleTranslateFunc = Callable[[SubtitleTranslateInput], SubtitleTranslateResult]

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
IMPORT_COPY_APPROVAL_PENDING_TEXT = (
    "硬链接失败：源和目标不在同一文件系统。\n"
    "如需改用复制导入（会额外占用磁盘空间），请再次发送 confirm {task_ref}。"
)
IMPORT_COPY_FAILED_TEXT = "复制导入失败：{reason}"
IMPORT_APPROVAL_PENDING_TEXT = (
    "导入待确认：{name}\n"
    "任务 ID: {task_id}\n"
    "任务 Hash: {task_hash}\n"
    "请发送 confirm {task_ref} 执行导入。"
)
IMPORT_RAW_BT_UNSUPPORTED_TEXT = "当前任务属于 raw_bt 资源，不走媒体入库链。请直接到已选目标目录中使用文件。"
IMPORT_CANCELLED_TEXT = "已取消当前导入确认。请重新发送 import <任务ID或Hash>。"
IMPORT_CONFIRM_NOT_PENDING_TEXT = "没有待确认的导入请求，请先发送 import <任务ID或Hash>。"
IMPORT_CONFIRM_EXPIRED_TEXT = "导入确认已超时，请重新发送 import <任务ID或Hash>。"
IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT = "导入确认状态读取失败，请稍后重试。"
IMPORT_REFRESH_FAILED_TEXT = "媒体库刷新失败：未知错误"
IMPORT_REFRESH_SUCCESS_TEXT = "媒体库刷新成功。"
JOB_LEASE_OWNER = "import_confirm"
IMPORT_EXECUTION_MODE_COPY = "copy"
IMPORT_EXECUTION_MODE_HARDLINK = "hardlink"


@dataclass(frozen=True, slots=True)
class PreparedImport:
    import_source: TransmissionImportSource
    source_path: Path
    target_path: Path


@dataclass(frozen=True, slots=True)
class ConfirmExecutionContext:
    job: JobRecord
    approval_record: ApprovalRecord | None
    approval_lookup_failed: bool = False

    @property
    def lookup_task_ref(self) -> str:
        if self.job.task_hash:
            return self.job.task_hash
        if self.job.task_id:
            return self.job.task_id
        return self.job.task_ref


@dataclass(frozen=True, slots=True)
class ImportExecutionResult:
    reply: str
    imported: bool
    pending_copy_approval: bool = False


@dataclass(frozen=True, slots=True)
class ImportTargetLookupResult:
    target_path: str | None = None
    lookup_failed: bool = False


class ImportToLibraryService:
    def __init__(
        self,
        get_import_source_func: GetImportSourceFunc,
        library_target_dir: str,
        refresh_media_server_func: RefreshMediaServerFunc | None = None,
        scrape_metadata_func: MetadataScrapeFunc | None = None,
        translate_subtitle_func: SubtitleTranslateFunc | None = None,
        job_event_repo: JobEventRepo | None = None,
        approval_repo: ApprovalRepo | None = None,
        job_repo: JobRepo | None = None,
    ) -> None:
        self._get_import_source_func = get_import_source_func
        self._library_target_dir = Path(library_target_dir).expanduser()
        self._refresh_media_server_func = refresh_media_server_func
        self._scrape_metadata_func = scrape_metadata_func
        self._translate_subtitle_func = translate_subtitle_func
        self._job_event_repo = job_event_repo
        self._approval_repo = approval_repo
        self._job_repo = job_repo
        self._pending_import_identities: set[tuple[str, str]] = set()
        self._pending_import_lease_versions: dict[tuple[str, str], int] = {}
        self._pending_copy_fallback_identities: set[tuple[str, str]] = set()

    async def import_by_task_ref(
        self,
        task_ref: str,
        *,
        chat_id: int | None = None,
        user_id: int | None = None,
    ) -> str:
        cleaned_ref = task_ref.strip()
        if not cleaned_ref:
            return IMPORT_QUERY_USAGE_TEXT

        if self._is_raw_bt_task(chat_id=chat_id, task_ref=cleaned_ref):
            return IMPORT_RAW_BT_UNSUPPORTED_TEXT

        prepared_import, error_text = await self._prepare_import(cleaned_ref, chat_id=chat_id)
        if prepared_import is None:
            return error_text

        import_source = prepared_import.import_source
        self._record_pending_approval(
            task_ref=cleaned_ref,
            task_id=import_source.task_id,
            task_hash=import_source.task_hash,
        )
        self._record_pending_job(
            chat_id=chat_id,
            user_id=user_id,
            task_ref=cleaned_ref,
            task_id=import_source.task_id,
            task_hash=import_source.task_hash,
            payload_json="",
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

    async def confirm_import_by_task_ref(
        self,
        task_ref: str,
        *,
        chat_id: int | None = None,
        user_id: int | None = None,
    ) -> str:
        _ = user_id
        cleaned_ref = task_ref.strip()
        if not cleaned_ref:
            return CONFIRM_QUERY_USAGE_TEXT

        confirm_context = self._rebuild_confirm_context(task_ref=cleaned_ref, chat_id=chat_id)
        if confirm_context is not None and confirm_context.approval_lookup_failed:
            return IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT
        if confirm_context is not None and confirm_context.job.state != JOB_STATE_PENDING_APPROVAL:
            stale_text = self._find_version_stale_rejection_text(
                task_id=confirm_context.job.task_id,
                task_hash=confirm_context.job.task_hash,
            )
            rejection_text = stale_text or IMPORT_CONFIRM_NOT_PENDING_TEXT
            self._record_event(
                task_ref=cleaned_ref,
                task_id=confirm_context.job.task_id,
                task_hash=confirm_context.job.task_hash,
                event_type="import.confirm_not_pending",
                message=rejection_text,
            )
            return rejection_text

        claimed_job = False
        claimed_job_version = 0
        claimed_job_id = ""
        lease_owner = ""
        prepared_task_ref = cleaned_ref
        if confirm_context is not None:
            approval_record = confirm_context.approval_record
            if approval_record is None or approval_record.status != APPROVAL_STATUS_PENDING:
                stale_text = self._find_version_stale_rejection_text(
                    task_id=confirm_context.job.task_id,
                    task_hash=confirm_context.job.task_hash,
                )
                rejection_text = stale_text or IMPORT_CONFIRM_NOT_PENDING_TEXT
                self._record_event(
                    task_ref=cleaned_ref,
                    task_id=confirm_context.job.task_id,
                    task_hash=confirm_context.job.task_hash,
                    event_type="import.confirm_not_pending",
                    message=rejection_text,
                )
                return rejection_text
            expired_text = self._handle_expired_pending_confirm(task_ref=cleaned_ref, context=confirm_context)
            if expired_text is not None:
                return expired_text
            lease_owner = self._build_job_lease_owner(cleaned_ref)
            claimed_job = self._claim_pending_job(
                job=confirm_context.job,
                lease_owner=lease_owner,
            )
            if not claimed_job:
                stale_text = self._find_version_stale_rejection_text(
                    task_id=confirm_context.job.task_id,
                    task_hash=confirm_context.job.task_hash,
                )
                rejection_text = stale_text or IMPORT_CONFIRM_NOT_PENDING_TEXT
                self._record_event(
                    task_ref=cleaned_ref,
                    task_id=confirm_context.job.task_id,
                    task_hash=confirm_context.job.task_hash,
                    event_type="import.confirm_not_pending",
                    message=rejection_text,
                )
                return rejection_text
            claimed_job_id = confirm_context.job.job_id
            claimed_job_version = confirm_context.job.version
            prepared_task_ref = confirm_context.lookup_task_ref

        prepared_import, error_text = await self._prepare_import(prepared_task_ref, chat_id=chat_id)
        if prepared_import is None:
            if claimed_job:
                self._restore_pending_job(
                    job_id=claimed_job_id,
                    expected_version=claimed_job_version,
                    lease_owner=lease_owner,
                )
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
            if claimed_job:
                self._restore_pending_job(
                    job_id=claimed_job_id,
                    expected_version=claimed_job_version,
                    lease_owner=lease_owner,
                )
            return stale_text

        expected_lease_version = 0
        if confirm_context is not None and confirm_context.approval_record is not None:
            expected_lease_version = max(0, confirm_context.approval_record.lease_version)
        if expected_lease_version <= 0:
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
            if claimed_job:
                self._restore_pending_job(
                    job_id=claimed_job_id,
                    expected_version=claimed_job_version,
                    lease_owner=lease_owner,
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
            if claimed_job:
                self._restore_pending_job(
                    job_id=claimed_job_id,
                    expected_version=claimed_job_version,
                    lease_owner=lease_owner,
                )
            return rejection_text

        self._record_event(
            task_ref=cleaned_ref,
            task_id=import_source.task_id,
            task_hash=import_source.task_hash,
            event_type="import.approval_confirmed",
            message=cleaned_ref,
        )

        execution_mode = self._resolve_execution_mode(
            task_id=import_source.task_id,
            task_hash=import_source.task_hash,
            confirm_context=confirm_context,
        )
        execution = await self._execute_import(
            cleaned_ref,
            prepared_import,
            execution_mode=execution_mode,
        )
        if execution.imported:
            self._record_executed_lease_version(
                task_ref=cleaned_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                executed_lease_version=expected_lease_version,
            )
            self._clear_pending_copy_fallback(
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
            )
            if claimed_job:
                self._mark_completed_job(
                    job_id=claimed_job_id,
                    expected_version=claimed_job_version,
                    lease_owner=lease_owner,
                )
        elif execution.pending_copy_approval:
            self._record_copy_fallback_pending(
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
            )
            self._restore_pending_approval(
                task_ref=cleaned_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                expected_lease_version=expected_lease_version,
            )
            if confirm_context is not None:
                persisted = self._record_pending_job(
                    chat_id=confirm_context.job.chat_id,
                    user_id=confirm_context.job.user_id,
                    task_ref=confirm_context.job.task_ref or cleaned_ref,
                    task_id=import_source.task_id,
                    task_hash=import_source.task_hash,
                    payload_json=_copy_fallback_pending_to_json(),
                )
                if not persisted and claimed_job:
                    self._restore_pending_job(
                        job_id=claimed_job_id,
                        expected_version=claimed_job_version,
                        lease_owner=lease_owner,
                    )
        else:
            self._restore_pending_approval(
                task_ref=cleaned_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                expected_lease_version=expected_lease_version,
            )
            if execution_mode == IMPORT_EXECUTION_MODE_COPY:
                self._record_copy_fallback_pending(
                    task_id=import_source.task_id,
                    task_hash=import_source.task_hash,
                )
            else:
                self._clear_pending_copy_fallback(
                    task_id=import_source.task_id,
                    task_hash=import_source.task_hash,
                )
            if claimed_job:
                if execution_mode == IMPORT_EXECUTION_MODE_COPY:
                    persisted = self._record_pending_job(
                        chat_id=confirm_context.job.chat_id if confirm_context is not None else chat_id,
                        user_id=confirm_context.job.user_id if confirm_context is not None else user_id,
                        task_ref=confirm_context.job.task_ref if confirm_context is not None else cleaned_ref,
                        task_id=import_source.task_id,
                        task_hash=import_source.task_hash,
                        payload_json=_copy_fallback_pending_to_json(),
                    )
                    if not persisted:
                        self._restore_pending_job(
                            job_id=claimed_job_id,
                            expected_version=claimed_job_version,
                            lease_owner=lease_owner,
                        )
                else:
                    self._restore_pending_job(
                        job_id=claimed_job_id,
                        expected_version=claimed_job_version,
                        lease_owner=lease_owner,
                    )
        return execution.reply

    def cancel_pending_import(self, chat_id: int) -> str | None:
        if chat_id <= 0:
            return None
        if self._job_repo is None:
            return None

        try:
            pending_job = self._job_repo.get_latest_pending_import_job(chat_id=chat_id)
        except Exception as error:
            print(
                f"\033[31m[导入取消查询失败]\033[0m chat_id={chat_id} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表读取是否正常；当前取消请求会直接失败返回，避免把查询异常误判成“没有待取消导入”。",
                flush=True,
            )
            return None
        if pending_job is None:
            return None

        expected_lease_version = self._resolve_pending_lease_version(
            task_id=pending_job.task_id,
            task_hash=pending_job.task_hash,
        )
        if expected_lease_version <= 0:
            return None

        approval_cancelled = True
        if self._approval_repo is not None:
            try:
                approval_cancelled = self._approval_repo.cancel_import(
                    task_id=pending_job.task_id,
                    task_hash=pending_job.task_hash,
                    task_ref=pending_job.task_ref,
                    expected_lease_version=expected_lease_version,
                )
            except Exception as error:
                print(
                    f"\033[31m[导入取消审批更新失败]\033[0m task_ref={pending_job.task_ref} task_id={pending_job.task_id} task_hash={pending_job.task_hash} lease_version={expected_lease_version} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表更新是否正常；当前取消会直接失败返回，待确认导入状态可能仍残留。",
                    flush=True,
                )
                approval_cancelled = False

        if not approval_cancelled:
            return None

        try:
            cancelled = self._job_repo.cancel_pending_job(
                job_id=pending_job.job_id,
                expected_version=pending_job.version,
                workflow_type=WORKFLOW_IMPORT_TO_LIBRARY,
            )
        except Exception as error:
            print(
                f"\033[31m[导入取消任务更新失败]\033[0m task_ref={pending_job.task_ref} job_id={pending_job.job_id} task_id={pending_job.task_id} task_hash={pending_job.task_hash} version={pending_job.version} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表更新是否正常；当前审批可能已取消，但任务真相可能仍残留在待确认状态。",
                flush=True,
            )
            return None
        if not cancelled:
            return None
        self._clear_pending_copy_fallback(
            task_id=pending_job.task_id,
            task_hash=pending_job.task_hash,
        )

        self._record_event(
            task_ref=pending_job.task_ref,
            task_id=pending_job.task_id,
            task_hash=pending_job.task_hash,
            event_type="import.cancelled",
            message=IMPORT_CANCELLED_TEXT,
        )
        return IMPORT_CANCELLED_TEXT

    async def _get_import_source(
        self,
        task_ref: str,
        *,
        chat_id: int | None = None,
    ) -> TransmissionImportSource | None:
        if chat_id is None:
            return await self._get_import_source_func(task_ref)
        try:
            return await self._get_import_source_func(task_ref, chat_id)
        except TypeError:
            return await self._get_import_source_func(task_ref)

    async def _prepare_import(
        self,
        task_ref: str,
        *,
        chat_id: int | None = None,
    ) -> tuple[PreparedImport | None, str]:
        try:
            import_source = await self._get_import_source(task_ref, chat_id=chat_id)
        except Exception as error:
            print(
                f"\033[31m[导入源查询失败]\033[0m task_ref={task_ref} chat_id={chat_id or 0} 错误={error}\n\033[33m[处理建议]\033[0m 检查下载器状态查询、下载器路由和网络连通性；当前请求会返回查询失败文本，并记录 `import.query_failed` 事件。",
                flush=True,
            )
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
            print(
                f"\033[31m[导入源文件缺失]\033[0m task_ref={task_ref} task_id={import_source.task_id} task_hash={import_source.task_hash} source_path={source_path}\n\033[33m[处理建议]\033[0m 检查下载目录是否已被清理、移动或手工删除；确认下载源仍在后再重新执行导入。",
                flush=True,
            )
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
        except OSError as error:
            message = IMPORT_PREPARE_TARGET_FAILED_TEXT.format(target_path=str(target_root))
            print(
                f"\033[31m[导入目标目录创建失败]\033[0m task_ref={task_ref} task_id={import_source.task_id} task_hash={import_source.task_hash} target_path={target_root} 错误={error}\n\033[33m[处理建议]\033[0m 检查 LIBRARY_TARGET_DIR 是否存在、是否可写，以及当前进程对目标目录是否有创建权限；当前请求会直接失败返回。",
                flush=True,
            )
            self._record_event(
                task_ref=task_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                event_type="import.prepare_target_failed",
                message=message,
            )
            return None, message

        naming_truth = self._resolve_normalized_naming_truth(
            task_id=import_source.task_id,
            task_hash=import_source.task_hash,
            fallback_name=import_source.name,
        )
        normalized_target_name = _build_normalized_target_name(
            source_path=source_path,
            naming_truth=naming_truth,
        )
        target_path = target_root / normalized_target_name
        if target_path.exists():
            message = IMPORT_TARGET_EXISTS_TEXT.format(target_path=str(target_path))
            print(
                f"\033[31m[导入目标已存在]\033[0m task_ref={task_ref} task_id={import_source.task_id} task_hash={import_source.task_hash} target_path={target_path}\n\033[33m[处理建议]\033[0m 检查库目录里是否已有同名文件或目录；若这是历史残留，请先确认是否可复用或手动清理后再重试导入。",
                flush=True,
            )
            self._record_event(
                task_ref=task_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                event_type="import.target_exists",
                message=message,
            )
            return None, message

        return PreparedImport(import_source=import_source, source_path=source_path, target_path=target_path), ""

    def _is_raw_bt_task(self, *, chat_id: int | None, task_ref: str) -> bool:
        if self._job_repo is None or chat_id is None or chat_id <= 0:
            return False
        try:
            downloader_job = self._job_repo.get_downloader_job_for_chat_ref(chat_id=chat_id, task_ref=task_ref)
        except Exception as error:
            print(
                f"\033[31m[导入 raw_bt 判定查询失败]\033[0m chat_id={chat_id} task_ref={task_ref} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表读取是否正常；当前请求会按“不是 raw_bt”继续判断，但原本应被阻断的 raw_bt 任务可能继续进入入库链。",
                flush=True,
            )
            return False
        if downloader_job is None:
            return False
        cleaned_payload = downloader_job.payload_json.strip()
        if not cleaned_payload:
            self._log_raw_bt_payload_corrupted(
                chat_id=chat_id,
                task_ref=task_ref,
                payload_summary="payload_json empty",
            )
            return False
        try:
            payload = json.loads(cleaned_payload)
        except json.JSONDecodeError:
            self._log_raw_bt_payload_corrupted(
                chat_id=chat_id,
                task_ref=task_ref,
                payload_summary="payload_json invalid json",
            )
            return False
        if not isinstance(payload, dict):
            self._log_raw_bt_payload_corrupted(
                chat_id=chat_id,
                task_ref=task_ref,
                payload_summary="payload_json not object",
            )
            return False
        return payload.get("auto_import_enabled") is False

    def _log_raw_bt_payload_corrupted(self, *, chat_id: int, task_ref: str, payload_summary: str) -> None:
        print(
            f"\033[31m[导入 raw_bt 判定载荷损坏]\033[0m chat_id={chat_id} task_ref={task_ref} 载荷={payload_summary}\n\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表里的 payload_json 是否仍是完整下载任务上下文；当前请求会按“不是 raw_bt”继续判断，但原本应被阻断的 raw_bt 任务可能继续进入入库链。",
            flush=True,
        )

    def _resolve_normalized_naming_truth(
        self,
        *,
        task_id: str,
        task_hash: str,
        fallback_name: str,
    ) -> str:
        fallback = fallback_name.strip()
        if self._job_event_repo is None:
            return fallback
        try:
            events = self._job_event_repo.list_events_for_task_identity(task_id=task_id, task_hash=task_hash)
        except Exception as error:
            print(
                f"\033[31m[导入命名真相查询失败]\033[0m task_id={task_id} task_hash={task_hash} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/job_event 表读取是否正常；当前导入会退回下载源名称做命名，文件名可能缺少 downloader 已确认的标题真相。",
                flush=True,
            )
            return fallback
        for event in reversed(events):
            if event.event_type != "downloader.succeeded":
                continue
            title = event.message.strip()
            if title:
                return title
        return fallback

    async def _execute_import(
        self,
        task_ref: str,
        prepared_import: PreparedImport,
        *,
        execution_mode: str,
    ) -> ImportExecutionResult:
        import_source = prepared_import.import_source
        source_path = prepared_import.source_path
        target_path = prepared_import.target_path

        try:
            if execution_mode == IMPORT_EXECUTION_MODE_COPY:
                _copy_import(source_path, target_path)
            else:
                _hardlink_import(source_path, target_path)
        except FileExistsError:
            message = IMPORT_TARGET_EXISTS_TEXT.format(target_path=str(target_path))
            print(
                f"\033[31m[导入目标已存在]\033[0m task_ref={task_ref} task_id={import_source.task_id} task_hash={import_source.task_hash} target_path={target_path}\n\033[33m[处理建议]\033[0m 检查导入执行期间是否已有并发写入或历史文件落到相同目标；确认目标文件可复用或清理后再重试。",
                flush=True,
            )
            self._record_event(
                task_ref=task_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                event_type="import.target_exists",
                message=message,
            )
            return ImportExecutionResult(reply=message, imported=False)
        except OSError as exc:
            if execution_mode != IMPORT_EXECUTION_MODE_COPY and exc.errno == errno.EXDEV:
                prompt_text = IMPORT_COPY_APPROVAL_PENDING_TEXT.format(task_ref=task_ref)
                self._record_event(
                    task_ref=task_ref,
                    task_id=import_source.task_id,
                    task_hash=import_source.task_hash,
                    event_type="import.copy_fallback_pending",
                    message=prompt_text,
                )
                return ImportExecutionResult(
                    reply=prompt_text,
                    imported=False,
                    pending_copy_approval=True,
                )
            message = (
                IMPORT_COPY_FAILED_TEXT.format(reason=str(exc))
                if execution_mode == IMPORT_EXECUTION_MODE_COPY
                else IMPORT_HARDLINK_FAILED_TEXT.format(reason=str(exc))
            )
            if execution_mode == IMPORT_EXECUTION_MODE_COPY:
                print(
                    f"\033[31m[导入复制失败]\033[0m task_ref={task_ref} task_id={import_source.task_id} task_hash={import_source.task_hash} source_path={source_path} target_path={target_path} 错误={exc}\n\033[33m[处理建议]\033[0m 检查目标目录权限、磁盘空间和目标路径占用情况；如果是复制导入确认后的失败，修复后可重新执行 confirm {task_ref}。",
                    flush=True,
                )
            else:
                print(
                    f"\033[31m[导入硬链接失败]\033[0m task_ref={task_ref} task_id={import_source.task_id} task_hash={import_source.task_hash} source_path={source_path} target_path={target_path} 错误={exc}\n\033[33m[处理建议]\033[0m 检查下载目录与库目录权限、目标路径占用情况，以及跨文件系统场景是否应改走 copy fallback 后重试。",
                    flush=True,
                )
            self._record_event(
                task_ref=task_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                event_type=(
                    "import.copy_failed"
                    if execution_mode == IMPORT_EXECUTION_MODE_COPY
                    else "import.hardlink_failed"
                ),
                message=message,
            )
            return ImportExecutionResult(reply=message, imported=False)

        import_success_text = (
            f"导入成功：{import_source.name}\n"
            f"任务 ID: {import_source.task_id}\n"
            f"任务 Hash: {import_source.task_hash}\n"
            f"目标路径: {target_path}"
        )
        if execution_mode == IMPORT_EXECUTION_MODE_COPY:
            import_success_text = f"{import_success_text}\n导入方式: 复制"
        self._record_event(
            task_ref=task_ref,
            task_id=import_source.task_id,
            task_hash=import_source.task_hash,
            event_type="import.succeeded",
            message=str(target_path),
            source_path=str(source_path),
            target_path=str(target_path),
        )
        metadata_result = await self._try_scrape_metadata(
            task_ref=task_ref,
            import_source=import_source,
            target_path=target_path,
        )
        self._try_translate_subtitle(
            task_ref=task_ref,
            import_source=import_source,
            target_path=target_path,
            metadata_result=metadata_result,
        )

        if self._refresh_media_server_func is None:
            return ImportExecutionResult(reply=import_success_text, imported=True)

        try:
            refresh_text = await self._refresh_media_server_func()
        except Exception as error:
            print(
                f"\033[31m[媒体库刷新失败]\033[0m task_ref={task_ref} task_id={import_source.task_id} task_hash={import_source.task_hash} 错误={error}\n\033[33m[处理建议]\033[0m 检查媒体服务器地址、API Key 和网络连通性；当前导入成功不会回滚，但刷新结果会按失败文本返回。",
                flush=True,
            )
            refresh_text = IMPORT_REFRESH_FAILED_TEXT
            self._record_event(
                task_ref=task_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                event_type="refresh.failed",
                message=refresh_text,
            )
            return ImportExecutionResult(reply=f"{import_success_text}\n{refresh_text}", imported=True)

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
        return ImportExecutionResult(reply=f"{import_success_text}\n{refresh_text}", imported=True)

    async def _try_scrape_metadata(
        self,
        *,
        task_ref: str,
        import_source: TransmissionImportSource,
        target_path: Path,
    ) -> MetadataScrapeResult | None:
        if self._scrape_metadata_func is None:
            return None

        title, year = self._resolve_metadata_title_year(
            task_id=import_source.task_id,
            task_hash=import_source.task_hash,
            target_path=target_path,
        )
        scrape_input = MetadataScrapeInput(
            task_ref=task_ref,
            task_id=import_source.task_id,
            task_hash=import_source.task_hash,
            title=title,
            year=year,
            target_path=str(target_path),
        )
        try:
            result = await self._scrape_metadata_func(scrape_input)
        except Exception as exc:
            message = f"metadata 刮削执行异常：{exc}"
            self._record_event(
                task_ref=task_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                event_type="metadata.failed",
                message=message,
            )
            print(f"\033[31m[元数据刮削失败]\033[0m {message}", flush=True)
            print(
                "\033[33m[处理建议]\033[0m 检查 TMDB/Fanart 配置和网络，再重试 confirm 导入。",
                flush=True,
            )
            return None

        event_type = "metadata.succeeded" if result.success else "metadata.failed"
        self._record_event(
            task_ref=task_ref,
            task_id=import_source.task_id,
            task_hash=import_source.task_hash,
            event_type=event_type,
            message=result.message,
        )
        return result

    def _try_translate_subtitle(
        self,
        *,
        task_ref: str,
        import_source: TransmissionImportSource,
        target_path: Path,
        metadata_result: MetadataScrapeResult | None,
    ) -> None:
        if self._translate_subtitle_func is None:
            return
        metadata_path = ""
        if metadata_result is not None and metadata_result.metadata_path.strip():
            metadata_path = metadata_result.metadata_path.strip()
        else:
            metadata_path = str(_resolve_metadata_sidecar_path(target_path))
        translate_input = SubtitleTranslateInput(
            task_ref=task_ref,
            task_id=import_source.task_id,
            task_hash=import_source.task_hash,
            target_path=str(target_path),
            metadata_path=metadata_path,
        )
        try:
            result = self._translate_subtitle_func(translate_input)
        except Exception as exc:
            message = f"subtitle 翻译执行异常：{exc}"
            self._record_event(
                task_ref=task_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                event_type="subtitle.failed",
                message=message,
            )
            print(f"\033[31m[字幕翻译失败]\033[0m {message}", flush=True)
            print(
                "\033[33m[处理建议]\033[0m 检查字幕文件编码和目录写权限，再重试 confirm 导入。",
                flush=True,
            )
            return

        if result.skipped:
            event_type = "subtitle.skipped"
        elif result.success:
            event_type = "subtitle.succeeded"
        else:
            event_type = "subtitle.failed"
        self._record_event(
            task_ref=task_ref,
            task_id=import_source.task_id,
            task_hash=import_source.task_hash,
            event_type=event_type,
            message=result.message,
        )
        if event_type == "subtitle.failed":
            print(f"\033[31m[字幕翻译失败]\033[0m {result.message}", flush=True)
            print(
                "\033[33m[处理建议]\033[0m 检查字幕文件内容、编码和目录写权限，再重试 confirm 导入。",
                flush=True,
            )

    def _resolve_metadata_title_year(self, *, task_id: str, task_hash: str, target_path: Path) -> tuple[str, str]:
        fallback_title, fallback_year = _extract_title_year_for_scrape(target_path)
        naming_truth = self._resolve_normalized_naming_truth(
            task_id=task_id,
            task_hash=task_hash,
            fallback_name="",
        )
        if not naming_truth:
            return fallback_title, fallback_year

        title_from_truth, year_from_truth = _extract_title_year_from_text(naming_truth)
        title = title_from_truth or fallback_title
        year = year_from_truth or fallback_year
        return title, year

    def _record_pending_approval(self, *, task_ref: str, task_id: str, task_hash: str) -> int:
        identity = (task_id.strip(), task_hash.strip())
        if not identity[0] or not identity[1]:
            return 0
        self._pending_copy_fallback_identities.discard(identity)

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
                timeout_seconds=DEFAULT_PENDING_TIMEOUT_SECONDS,
            )
            if requested_lease > 0:
                lease_version = requested_lease
        except Exception as error:
            print(
                f"\033[31m[导入待确认审批落盘失败]\033[0m task_ref={task_ref} task_id={task_id} task_hash={task_hash} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表写入是否正常；当前请求会退回进程内待确认身份判断，重启后审批状态可能不一致。",
                flush=True,
            )
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
        except Exception as error:
            print(
                f"\033[31m[导入确认审批更新失败]\033[0m task_ref={task_ref} task_id={task_id} task_hash={task_hash} lease_version={expected_lease_version} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表更新是否正常；当前请求会退回进程内待确认身份判断，重启后审批状态可能不一致。",
                flush=True,
            )
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
        except Exception as error:
            print(
                f"\033[31m[导入审批回退失败]\033[0m task_ref={task_ref} task_id={task_id} task_hash={task_hash} lease_version={expected_lease_version} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表更新是否正常；当前进程内待确认身份已回退，但重启后审批状态可能不一致。",
                flush=True,
            )
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
        except Exception as error:
            print(
                f"\033[31m[导入执行版号回写失败]\033[0m task_id={task_id} task_hash={task_hash} lease_version={executed_lease_version} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表更新是否正常；当前进程内 lease 版本已前进，但持久化真相可能仍停留在旧值。",
                flush=True,
            )
            return

    def _record_pending_job(
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
            return False
        try:
            self._job_repo.upsert_import_job_pending(
                chat_id=chat_id,
                user_id=user_id,
                task_ref=task_ref,
                task_id=task_id,
                task_hash=task_hash,
                payload_json=payload_json,
            )
        except Exception as error:
            print(
                f"\033[31m[导入待确认任务落盘失败]\033[0m chat_id={chat_id} user_id={user_id} task_ref={task_ref} task_id={task_id} task_hash={task_hash} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表写入是否正常；当前请求会继续返回待确认文本，但重启后 confirm 上下文可能无法重建。",
                flush=True,
            )
            return False
        return True

    def _resolve_execution_mode(
        self,
        *,
        task_id: str,
        task_hash: str,
        confirm_context: ConfirmExecutionContext | None,
    ) -> str:
        identity = (task_id.strip(), task_hash.strip())
        if not identity[0] or not identity[1]:
            return IMPORT_EXECUTION_MODE_HARDLINK
        if confirm_context is not None:
            copy_fallback_pending, payload_problem = _parse_copy_fallback_pending_payload(confirm_context.job.payload_json)
            if copy_fallback_pending is True:
                return IMPORT_EXECUTION_MODE_COPY
            if copy_fallback_pending is None:
                self._log_copy_fallback_payload_corrupted(
                    task_id=task_id,
                    task_hash=task_hash,
                    payload_problem=payload_problem or "unknown",
                )
        if identity in self._pending_copy_fallback_identities:
            return IMPORT_EXECUTION_MODE_COPY
        return IMPORT_EXECUTION_MODE_HARDLINK

    def _record_copy_fallback_pending(self, *, task_id: str, task_hash: str) -> None:
        identity = (task_id.strip(), task_hash.strip())
        if not identity[0] or not identity[1]:
            return
        self._pending_copy_fallback_identities.add(identity)

    def _clear_pending_copy_fallback(self, *, task_id: str, task_hash: str) -> None:
        identity = (task_id.strip(), task_hash.strip())
        if not identity[0] or not identity[1]:
            return
        self._pending_copy_fallback_identities.discard(identity)

    def _log_copy_fallback_payload_corrupted(self, *, task_id: str, task_hash: str, payload_problem: str) -> None:
        print(
            f"\033[31m[导入执行模式载荷损坏]\033[0m task_id={task_id} task_hash={task_hash} 载荷={payload_problem}\n\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表里的 payload_json 是否仍是完整 copy-fallback 待确认上下文；当前 confirm 会按硬链接继续判断，但原本应进入复制导入确认的任务可能被误判。",
            flush=True,
        )

    def _rebuild_confirm_context(
        self,
        *,
        task_ref: str,
        chat_id: int | None,
    ) -> ConfirmExecutionContext | None:
        if self._job_repo is None or chat_id is None or chat_id <= 0:
            return None
        try:
            job = self._job_repo.get_import_job_for_chat_ref(chat_id=chat_id, task_ref=task_ref)
        except Exception as error:
            print(
                f"\033[31m[导入确认上下文查询失败]\033[0m chat_id={chat_id} task_ref={task_ref} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表查询是否正常；当前 confirm 会按“没有待确认导入”继续处理，但实际待确认上下文可能未能重建。",
                flush=True,
            )
            return None
        if job is None:
            return None

        approval_record: ApprovalRecord | None = None
        approval_lookup_failed = False
        if self._approval_repo is not None:
            try:
                approval_record = self._approval_repo.get_import_approval(
                    task_id=job.task_id,
                    task_hash=job.task_hash,
                )
            except Exception as error:
                print(
                    f"\033[31m[导入确认审批查询失败]\033[0m task_ref={task_ref} task_id={job.task_id} task_hash={job.task_hash} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表查询是否正常；当前 confirm 上下文会继续返回，但审批状态可能缺失。",
                    flush=True,
                )
                approval_record = None
                approval_lookup_failed = True
        return ConfirmExecutionContext(
            job=job,
            approval_record=approval_record,
            approval_lookup_failed=approval_lookup_failed,
        )

    def _claim_pending_job(self, *, job: JobRecord, lease_owner: str) -> bool:
        if self._job_repo is None:
            return False
        try:
            return self._job_repo.claim_lease(
                job_id=job.job_id,
                expected_version=job.version,
                lease_owner=lease_owner,
                workflow_type=WORKFLOW_IMPORT_TO_LIBRARY,
            )
        except Exception as error:
            print(
                f"\033[31m[导入确认任务抢占失败]\033[0m job_id={job.job_id} task_ref={job.task_ref} task_id={job.task_id} task_hash={job.task_hash} version={job.version} lease_owner={lease_owner} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表 lease 更新是否正常；当前 confirm 会按未持有执行权处理，但这次失败也可能不是业务真的冲突。",
                flush=True,
            )
            return False

    def _restore_pending_job(
        self,
        *,
        job_id: str,
        expected_version: int,
        lease_owner: str,
    ) -> None:
        if self._job_repo is None:
            return
        try:
            self._job_repo.release_lease_to_pending(
                job_id=job_id,
                expected_version=expected_version,
                lease_owner=lease_owner,
                workflow_type=WORKFLOW_IMPORT_TO_LIBRARY,
            )
        except Exception as error:
            print(
                f"\033[31m[导入确认任务回退失败]\033[0m job_id={job_id} version={expected_version} lease_owner={lease_owner} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表 lease 回退是否正常；当前审批已尝试退回待确认，但持久化状态可能仍停在执行中。",
                flush=True,
            )
            return

    def _mark_completed_job(
        self,
        *,
        job_id: str,
        expected_version: int,
        lease_owner: str,
    ) -> None:
        if self._job_repo is None:
            return
        try:
            self._job_repo.mark_completed(
                job_id=job_id,
                expected_version=expected_version,
                lease_owner=lease_owner,
                workflow_type=WORKFLOW_IMPORT_TO_LIBRARY,
            )
        except Exception as error:
            print(
                f"\033[31m[导入确认任务完结失败]\033[0m job_id={job_id} version={expected_version} lease_owner={lease_owner} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表完成态更新是否正常；当前导入结果已返回，但任务真相可能仍停留在待确认或执行中。",
                flush=True,
            )
            return

    def _build_job_lease_owner(self, task_ref: str) -> str:
        cleaned_ref = task_ref.strip()
        if not cleaned_ref:
            return JOB_LEASE_OWNER
        return f"{JOB_LEASE_OWNER}:{cleaned_ref}"

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
        except Exception as error:
            print(
                f"\033[31m[导入待确认版号查询失败]\033[0m task_id={task_id} task_hash={task_hash} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表查询是否正常；当前会退回进程内版号判断，但持久化真相可能已经变化。",
                flush=True,
            )
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
        except Exception as error:
            print(
                f"\033[31m[导入确认执行版号查询失败]\033[0m task_id={task_id} task_hash={task_hash} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表查询是否正常；当前 confirm 会直接返回状态读取失败，避免把持久化异常误判成普通没有待确认导入。",
                flush=True,
            )
            return IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT
        if approval_record is None:
            return None
        if approval_record.lease_version <= 0:
            return None
        if approval_record.executed_version < approval_record.lease_version:
            return None

        stale_target_lookup = self._find_latest_import_target_path(task_id=task_id, task_hash=task_hash)
        if stale_target_lookup.lookup_failed:
            return IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT
        if stale_target_lookup.target_path:
            return IMPORT_TARGET_EXISTS_TEXT.format(target_path=stale_target_lookup.target_path)
        return IMPORT_CONFIRM_NOT_PENDING_TEXT

    def _find_latest_import_target_path(self, *, task_id: str, task_hash: str) -> ImportTargetLookupResult:
        if self._job_event_repo is None:
            return ImportTargetLookupResult()
        try:
            correlation = self._job_event_repo.find_latest_import_correlation(
                task_id=task_id,
                task_hash=task_hash,
            )
        except Exception as error:
            print(
                f"\033[31m[导入目标路径查询失败]\033[0m task_id={task_id} task_hash={task_hash} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/job_event 表读取是否正常；当前 confirm 会直接返回状态读取失败，避免把持久化异常误判成“无导入目标路径”。",
                flush=True,
            )
            return ImportTargetLookupResult(lookup_failed=True)
        if correlation is None:
            return ImportTargetLookupResult()
        target_path = correlation.target_path.strip() or correlation.message.strip()
        if target_path:
            return ImportTargetLookupResult(target_path=target_path)
        return ImportTargetLookupResult()

    def _handle_expired_pending_confirm(self, *, task_ref: str, context: ConfirmExecutionContext) -> str | None:
        approval_record = context.approval_record
        if approval_record is None:
            return None
        approval_expired = self._is_pending_approval_expired(
            task_id=context.job.task_id,
            task_hash=context.job.task_hash,
            expected_lease_version=approval_record.lease_version,
        )
        if approval_expired is None:
            return IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT
        if not approval_expired:
            return None
        if self._approval_repo is not None:
            try:
                self._approval_repo.cancel_import(
                    task_id=context.job.task_id,
                    task_hash=context.job.task_hash,
                    task_ref=task_ref,
                    expected_lease_version=approval_record.lease_version,
                )
            except Exception as error:
                print(
                    f"\033[31m[导入确认超时审批取消失败]\033[0m task_ref={task_ref} task_id={context.job.task_id} task_hash={context.job.task_hash} lease_version={approval_record.lease_version} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表更新是否正常；当前会继续返回超时文本，但审批真相可能仍残留在 pending。",
                    flush=True,
                )
        if self._job_repo is not None and context.job.state == JOB_STATE_PENDING_APPROVAL:
            try:
                cancelled = self._job_repo.cancel_pending_job(
                    job_id=context.job.job_id,
                    expected_version=context.job.version,
                    workflow_type=WORKFLOW_IMPORT_TO_LIBRARY,
                )
            except Exception as error:
                print(
                    f"\033[31m[导入确认超时任务取消失败]\033[0m task_ref={task_ref} job_id={context.job.job_id} task_id={context.job.task_id} task_hash={context.job.task_hash} version={context.job.version} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表更新是否正常；当前会继续返回超时文本，但任务真相可能仍残留在待确认状态。",
                    flush=True,
                )
            else:
                if not cancelled:
                    print(
                        f"\033[31m[导入确认超时任务取消失败]\033[0m task_ref={task_ref} job_id={context.job.job_id} task_id={context.job.task_id} task_hash={context.job.task_hash} version={context.job.version} 错误=jobs.cancel_pending_job rejected current state\n\033[33m[处理建议]\033[0m 检查该任务是否已被其他路径抢先取消、确认或完结；当前会继续返回超时文本，但待确认任务真相可能已被其他状态迁移抢先改写。",
                        flush=True,
                    )
        self._clear_pending_copy_fallback(
            task_id=context.job.task_id,
            task_hash=context.job.task_hash,
        )
        self._record_event(
            task_ref=task_ref,
            task_id=context.job.task_id,
            task_hash=context.job.task_hash,
            event_type="import.approval_expired",
            message=IMPORT_CONFIRM_EXPIRED_TEXT,
        )
        return IMPORT_CONFIRM_EXPIRED_TEXT

    def _is_pending_approval_expired(
        self,
        *,
        task_id: str,
        task_hash: str,
        expected_lease_version: int,
    ) -> bool | None:
        if self._approval_repo is None:
            return False
        try:
            return self._approval_repo.is_import_pending_expired(
                task_id=task_id,
                task_hash=task_hash,
                expected_lease_version=expected_lease_version,
            )
        except Exception as error:
            print(
                f"\033[31m[导入确认过期判断失败]\033[0m task_id={task_id} task_hash={task_hash} lease_version={expected_lease_version} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表查询是否正常；当前 confirm 会直接返回状态读取失败，避免把持久化异常误判成“未过期”。",
                flush=True,
            )
            return None

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
        except Exception as error:
            print(
                f"\033[31m[导入事件落盘失败]\033[0m task_ref={task_ref} task_id={task_id} task_hash={task_hash} event_type={event_type} source={source_path} target={target_path} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/job_event 表写入是否正常；当前导入流程会继续执行，但这次事件可能没有落盘。",
                flush=True,
            )


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


def _copy_import(source_path: Path, target_path: Path) -> None:
    if source_path.is_file():
        if target_path.exists():
            raise FileExistsError(str(target_path))
        try:
            shutil.copy2(source_path, target_path)
        except Exception:
            _cleanup_partial_target(target_path)
            raise
        return
    if source_path.is_dir():
        try:
            shutil.copytree(source_path, target_path, copy_function=shutil.copy2)
        except Exception:
            _cleanup_partial_target(target_path)
            raise
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


def _cleanup_partial_target(target_path: Path) -> None:
    try:
        if target_path.is_dir():
            shutil.rmtree(target_path)
        elif target_path.exists() or target_path.is_symlink():
            target_path.unlink()
    except OSError as error:
        print(
            f"\033[31m[导入残留清理失败]\033[0m target={target_path} 错误={error}\n"
            "\033[33m[处理建议]\033[0m 检查目标路径是否被占用、是否仍有写权限，"
            "并手动清理这次失败导入留下的半成品文件或目录。",
            flush=True,
        )
        return


def _copy_fallback_pending_to_json() -> str:
    return json.dumps({"mode": IMPORT_EXECUTION_MODE_COPY}, ensure_ascii=False)


def _parse_copy_fallback_pending_payload(payload_json: str) -> tuple[bool | None, str | None]:
    cleaned_payload = payload_json.strip()
    if not cleaned_payload:
        return False, None
    try:
        payload = json.loads(cleaned_payload)
    except json.JSONDecodeError:
        return None, "payload_json invalid json"
    if not isinstance(payload, dict):
        return None, "payload_json not object"
    return str(payload.get("mode", "")).strip() == IMPORT_EXECUTION_MODE_COPY, None


def _extract_title_year_for_scrape(target_path: Path) -> tuple[str, str]:
    if target_path.is_file():
        base_name = target_path.stem
    else:
        base_name = target_path.name
    normalized = _normalize_name_tokens(base_name)
    year = _extract_movie_year(normalized)
    if year:
        title = _trim_title_before_year(normalized, year)
    else:
        title = normalized
    title = _sanitize_target_component(title)
    if not title:
        title = _sanitize_target_component(base_name)
    return title, year


def _extract_title_year_from_text(value: str) -> tuple[str, str]:
    normalized = _normalize_name_tokens(value)
    year = _extract_movie_year(normalized)
    if year:
        title = _trim_title_before_year(normalized, year)
    else:
        title = normalized
    title = title.strip()
    return title, year


def _resolve_metadata_sidecar_path(target_path: Path) -> Path:
    if target_path.is_dir():
        return target_path / ".luminarr.metadata.json"
    return target_path.with_suffix(".metadata.json")


def _build_normalized_target_name(*, source_path: Path, naming_truth: str) -> str:
    if source_path.is_file():
        source_base_name = source_path.stem
        suffix = source_path.suffix
    else:
        source_base_name = source_path.name
        suffix = ""

    raw_truth = naming_truth.strip() or source_base_name
    if suffix and raw_truth.lower().endswith(suffix.lower()):
        raw_truth = raw_truth[: -len(suffix)]

    normalized_truth = _normalize_name_tokens(raw_truth)
    normalized_source = _normalize_name_tokens(source_base_name)
    year = _extract_movie_year(normalized_truth) or _extract_movie_year(normalized_source)

    title_base = normalized_truth or normalized_source
    if year:
        title_base = _trim_title_before_year(title_base, year)
    if not title_base:
        title_base = normalized_source or source_base_name.strip()

    if year:
        final_base = f"{title_base} ({year})"
    else:
        final_base = title_base

    sanitized_base = _sanitize_target_component(final_base)
    if not sanitized_base:
        sanitized_base = _sanitize_target_component(normalized_source or source_base_name.strip())
    if not sanitized_base:
        sanitized_base = "unknown"

    if suffix:
        return f"{sanitized_base}{suffix}"
    return sanitized_base


def _normalize_name_tokens(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return ""
    cleaned = re.sub(r"[._]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _extract_movie_year(value: str) -> str:
    matched = re.search(r"(?<!\d)((?:19|20)\d{2})(?!\d)", value)
    if matched is None:
        return ""
    return matched.group(1)


def _trim_title_before_year(value: str, year: str) -> str:
    if not value or not year:
        return value.strip()
    matched = re.search(rf"(?<!\d){re.escape(year)}(?!\d)", value)
    if matched is None:
        return value.strip()
    prefix = value[: matched.start()].strip()
    if prefix:
        return prefix
    without_year = re.sub(rf"(?<!\d){re.escape(year)}(?!\d)", " ", value)
    return without_year.strip()


def _sanitize_target_component(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return ""
    cleaned = re.sub(r"[<>:\"/\\|?*\x00-\x1f]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .-_")
    cleaned = re.sub(r"[\(\[\{]+$", "", cleaned).strip(" .-_")
    return cleaned

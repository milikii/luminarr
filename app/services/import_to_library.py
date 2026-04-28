from __future__ import annotations

import re
import sqlite3
from collections.abc import Awaitable, Callable
from pathlib import Path

from app.clients.transmission import TransmissionImportSource
from app.db.approval_repo import (
    ApprovalRepo,
    ApprovalPersistenceError,
)
from app.db.job_event_repo import JobEventPersistenceError, JobEventRepo
from app.db.job_repo import JOB_STATE_PENDING_APPROVAL, JobPersistenceError, JobRecord, JobRepo, WORKFLOW_IMPORT_TO_LIBRARY
from app.operational_logging import emit_operational_log
from app.services import import_transfer_execution
from app.services.import_approval_state import ImportApprovalState, ImportTargetLookupResult
from app.services.import_confirm_execution_tail import ImportConfirmExecutionRequest, ImportConfirmExecutionTail
from app.services.import_confirm_expiry_state import ImportConfirmExpiryState
from app.services.import_confirm_preparation import ImportConfirmPreparation
from app.services.import_context_lookup import ConfirmExecutionContext, ImportContextLookup
from app.services.import_post_processing import ImportPostProcessingService, MetadataScrapeFunc, RefreshMediaServerFunc, SubtitleTranslateFunc
from app.services.import_prepare_state import ImportPrepareState, extract_title_year_for_scrape, extract_title_year_from_text
from app.services.import_transfer_execution import IMPORT_EXECUTION_MODE_COPY, ImportExecutionResult, PreparedImport
from app.services.media_identity import MEDIA_IDENTITY_EVENT_TYPE, media_identity_from_json
from app.services.workflow_trace_logger import WorkflowTraceLogger

GetImportSourceFunc = Callable[..., Awaitable[TransmissionImportSource | None]]

IMPORT_QUERY_USAGE_TEXT = "导入格式：import <任务ID或Hash>"
CONFIRM_QUERY_USAGE_TEXT = "确认格式：confirm <任务ID或Hash>"
IMPORT_NOT_FOUND_TEXT = "未找到对应下载任务，请检查任务 ID/Hash。"
IMPORT_QUERY_FAILED_TEXT = "查询下载任务失败，请稍后重试。"
IMPORT_NOT_COMPLETED_TEXT = "任务尚未完成，当前进度 {progress:.1f}%，暂不能导入。"
IMPORT_SOURCE_MISSING_TEXT = "下载源路径不存在，无法导入。"
IMPORT_SOURCE_TYPE_UNSUPPORTED_TEXT = "下载源不是文件或目录，无法导入。"
IMPORT_TARGET_EXISTS_TEXT = "目标已存在，已拒绝覆盖：{target_path}"
IMPORT_PREPARE_TARGET_FAILED_TEXT = "创建目标目录失败：{target_path}"
IMPORT_HARDLINK_FAILED_TEXT = "硬链接失败：{reason}"
IMPORT_PENDING_STATE_UNAVAILABLE_TEXT = "导入待确认状态写入失败，请稍后重试。"
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
IMPORT_CANCEL_STATE_UNAVAILABLE_TEXT = "导入取消状态读取失败，请稍后重试。"
IMPORT_CONFIRM_NOT_PENDING_TEXT = "没有待确认的导入请求，请先发送 import <任务ID或Hash>。"
IMPORT_CONFIRM_EXPIRED_TEXT = "导入确认已超时，请重新发送 import <任务ID或Hash>。"
IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT = "导入确认状态读取失败，请稍后重试。"
IMPORT_FINALIZATION_WARNING_TEXT = (
    "注意：导入已执行，但状态回写失败，请勿重复 confirm。\n"
    "请稍后检查 SQLite/approval_record 与 jobs 表，再确认当前导入任务状态。"
)
IMPORT_REFRESH_FAILED_TEXT = "媒体库刷新失败：未知错误"
JOB_LEASE_OWNER = "import_confirm"
PENDING_LEASE_LOOKUP_FAILED = -1
IMPORT_EVENT_RESULT_MISSING_REASON = "job_event missing after append"
IMPORT_PENDING_JOB_RESULT_MISSING_REASON = "job missing after pending upsert"
IMPORT_PENDING_JOB_NONE_REASON = "import pending job result missing"
IMPORT_CANCEL_PENDING_JOB_RESULT_MISSING_REASON = "import cancel pending job result missing"
IMPORT_CANCEL_PENDING_JOB_ROW_MISSING_REASON = "job missing during cancel"
IMPORT_CANCEL_APPROVAL_RESULT_MISSING_REASON = "approval_record missing during cancel"
IMPORT_CANCEL_APPROVAL_NONE_REASON = "import cancel approval result missing"
IMPORT_RESTORE_PENDING_APPROVAL_RESULT_MISSING_REASON = "import restore pending approval result missing"
IMPORT_RESTORE_PENDING_APPROVAL_ROW_MISSING_REASON = "approval_record missing during restore"
IMPORT_CLAIM_PENDING_JOB_RESULT_MISSING_REASON = "job missing during lease claim"
IMPORT_RESTORE_PENDING_JOB_RESULT_MISSING_REASON = "job missing during state transition"
IMPORT_MARK_COMPLETED_JOB_RESULT_MISSING_REASON = "import completed job result missing"
IMPORT_RAW_BT_LOOKUP_RESULT_MISSING_REASON = "downloader job missing during raw_bt check"
IMPORT_MEDIA_IDENTITY_RESULT_MISSING_REASON = "import media identity result missing"


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
        trace_log_path: Path | None = None,
    ) -> None:
        self._get_import_source_func = get_import_source_func
        self._library_target_dir = Path(library_target_dir).expanduser()
        self._approval_repo = approval_repo
        self._job_repo = job_repo
        self._job_event_repo = job_event_repo
        self._trace_logger = WorkflowTraceLogger(WORKFLOW_IMPORT_TO_LIBRARY, trace_log_path)
        self._context_lookup = ImportContextLookup(
            job_repo=job_repo,
            approval_repo=approval_repo,
            is_job_row_corrupted_error=_is_job_row_corrupted_error,
        )
        self._approval_state = ImportApprovalState(
            approval_repo=approval_repo,
            job_event_repo=job_event_repo,
            is_import_target_lookup_row_corrupted_error=_is_import_target_lookup_row_corrupted_error,
            import_confirm_state_unavailable_text=IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT,
            import_confirm_not_pending_text=IMPORT_CONFIRM_NOT_PENDING_TEXT,
            import_target_exists_text_template=IMPORT_TARGET_EXISTS_TEXT,
        )
        self._pending_import_identities = self._approval_state.pending_import_identities
        self._pending_import_lease_versions = self._approval_state.pending_import_lease_versions
        self._post_processing_service = ImportPostProcessingService(
            refresh_media_server_func=refresh_media_server_func,
            scrape_metadata_func=scrape_metadata_func,
            translate_subtitle_func=translate_subtitle_func,
            resolve_metadata_title_year_func=self._resolve_metadata_title_year,
            resolve_metadata_tmdb_id_func=self._resolve_confirmed_media_tmdb_id,
            record_event_func=self._record_event,
        )
        self._prepare_state = ImportPrepareState(
            get_import_source_func=get_import_source_func,
            library_target_dir=self._library_target_dir,
            job_event_repo=job_event_repo,
            record_event_func=self._record_event,
            import_query_failed_text=IMPORT_QUERY_FAILED_TEXT,
            import_not_found_text=IMPORT_NOT_FOUND_TEXT,
            import_not_completed_text_template=IMPORT_NOT_COMPLETED_TEXT,
            import_source_missing_text=IMPORT_SOURCE_MISSING_TEXT,
            import_prepare_target_failed_text_template=IMPORT_PREPARE_TARGET_FAILED_TEXT,
            import_target_exists_text_template=IMPORT_TARGET_EXISTS_TEXT,
        )
        self._confirm_preparation = ImportConfirmPreparation(
            import_confirm_not_pending_text=IMPORT_CONFIRM_NOT_PENDING_TEXT,
            import_confirm_state_unavailable_text=IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT,
            pending_lease_lookup_failed=PENDING_LEASE_LOOKUP_FAILED,
        )
        self._confirm_expiry_state = ImportConfirmExpiryState(
            approval_repo=approval_repo,
            job_repo=job_repo,
            import_confirm_state_unavailable_text=IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT,
            import_confirm_expired_text=IMPORT_CONFIRM_EXPIRED_TEXT,
            import_cancel_pending_job_result_missing_reason=IMPORT_CANCEL_PENDING_JOB_RESULT_MISSING_REASON,
            import_cancel_pending_job_row_missing_reason=IMPORT_CANCEL_PENDING_JOB_ROW_MISSING_REASON,
            job_state_pending_approval=JOB_STATE_PENDING_APPROVAL,
            workflow_import_to_library=WORKFLOW_IMPORT_TO_LIBRARY,
        )
        self._transfer_execution_service = import_transfer_execution.ImportTransferExecutionService(
            post_processing_service=self._post_processing_service,
            record_event_func=self._record_event,
            import_source_type_unsupported_text=IMPORT_SOURCE_TYPE_UNSUPPORTED_TEXT,
            import_target_exists_text_template=IMPORT_TARGET_EXISTS_TEXT,
            import_copy_approval_pending_text_template=IMPORT_COPY_APPROVAL_PENDING_TEXT,
            import_copy_failed_text_template=IMPORT_COPY_FAILED_TEXT,
            import_hardlink_failed_text_template=IMPORT_HARDLINK_FAILED_TEXT,
        )
        self._confirm_execution_tail = ImportConfirmExecutionTail(
            import_confirm_state_unavailable_text=IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT,
            import_finalization_warning_text=IMPORT_FINALIZATION_WARNING_TEXT,
            import_execution_mode_copy=IMPORT_EXECUTION_MODE_COPY,
        )
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

        raw_bt_task = self._is_raw_bt_task(chat_id=chat_id, task_ref=cleaned_ref)
        if raw_bt_task is None:
            return IMPORT_QUERY_FAILED_TEXT
        if raw_bt_task:
            return IMPORT_RAW_BT_UNSUPPORTED_TEXT

        prepared_import, error_text = await self._prepare_import(cleaned_ref, chat_id=chat_id)
        if prepared_import is None:
            return error_text

        return self._persist_pending_import(
            task_ref=cleaned_ref,
            import_source=prepared_import.import_source,
            chat_id=chat_id,
            user_id=user_id,
            record_pending_approval=self._record_pending_approval,
            record_pending_job=self._record_pending_job,
            record_event=self._record_event,
            log_trace=self._trace_logger.log,
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

        preparation, rejection_text = await self._confirm_preparation.prepare(
            task_ref=cleaned_ref,
            chat_id=chat_id,
            rebuild_confirm_context=self._rebuild_confirm_context,
            find_version_stale_rejection_text=self._find_version_stale_rejection_text,
            handle_expired_pending_confirm=self._handle_expired_pending_confirm,
            build_job_lease_owner=self._build_job_lease_owner,
            claim_pending_job=self._claim_pending_job,
            restore_pending_job=self._restore_pending_job,
            prepare_import=self._prepare_import,
            resolve_execution_mode=self._resolve_execution_mode,
            resolve_pending_lease_version=self._resolve_pending_lease_version,
            record_import_approval=self._record_import_approval,
            record_event=self._record_event,
        )
        if preparation is None:
            return rejection_text

        prepared_import = preparation.prepared_import
        import_source = prepared_import.import_source

        self._record_event(
            task_ref=cleaned_ref,
            task_id=import_source.task_id,
            task_hash=import_source.task_hash,
            event_type="import.approval_confirmed",
            message=cleaned_ref,
        )

        execution = await self._execute_import(
            cleaned_ref,
            prepared_import,
            execution_mode=preparation.execution_mode,
        )
        return self._confirm_execution_tail.finalize(
            request=ImportConfirmExecutionRequest(
                task_ref=cleaned_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                chat_id=chat_id,
                user_id=user_id,
                execution=execution,
                execution_mode=preparation.execution_mode,
                expected_lease_version=preparation.expected_lease_version,
                claimed_job=preparation.claimed_job,
                claimed_job_id=preparation.claimed_job_id,
                claimed_job_version=preparation.claimed_job_version,
                lease_owner=preparation.lease_owner,
                confirm_context=preparation.confirm_context,
            ),
            log_trace=self._trace_logger.log,
            restore_pending_approval=self._restore_pending_approval,
            restore_pending_job=self._restore_pending_job,
            record_executed_lease_version=self._record_executed_lease_version,
            mark_completed_job=self._mark_completed_job,
            record_pending_job=self._record_pending_job,
            record_copy_fallback_pending=self._record_copy_fallback_pending,
            clear_pending_copy_fallback=self._clear_pending_copy_fallback,
            copy_fallback_pending_to_json=self._copy_fallback_pending_to_json,
        )

    def cancel_pending_import(self, chat_id: int) -> str | None:
        if chat_id <= 0 or self._job_repo is None:
            return None

        pending_job, pending_lookup_failed = self._lookup_pending_import_job_for_cancel(chat_id=chat_id)
        if pending_job is None:
            if pending_lookup_failed:
                return IMPORT_CANCEL_STATE_UNAVAILABLE_TEXT
            return None

        expected_lease_version = self._resolve_pending_lease_version(
            task_id=pending_job.task_id,
            task_hash=pending_job.task_hash,
            allow_in_memory_fallback_on_error=False,
        )
        if expected_lease_version == PENDING_LEASE_LOOKUP_FAILED:
            self._log_import_cancel_state_error(
                title="导入取消状态读取失败",
                detail=f"task_ref={pending_job.task_ref} task_id={pending_job.task_id} task_hash={pending_job.task_hash} 原因=import approval pending lease lookup failed",
                fix_hint="检查 SQLite/approval_record 表查询是否正常；当前取消会直接返回状态读取失败，避免把审批查询异常误判成“没有待取消导入”。",
            )
            return IMPORT_CANCEL_STATE_UNAVAILABLE_TEXT
        if expected_lease_version <= 0:
            self._log_import_cancel_state_error(
                title="导入取消状态读取失败",
                detail=f"task_ref={pending_job.task_ref} task_id={pending_job.task_id} task_hash={pending_job.task_hash} 原因=import approval pending lease missing",
                fix_hint="检查 SQLite/approval_record 表里的待确认导入审批是否仍存在；当前取消会直接返回状态读取失败，避免把审批真相缺口误判成“没有待取消导入”。",
            )
            return IMPORT_CANCEL_STATE_UNAVAILABLE_TEXT

        approval_cancelled = self._cancel_pending_import_approval(
            job=pending_job,
            expected_lease_version=expected_lease_version,
        )
        if approval_cancelled is not True:
            return IMPORT_CANCEL_STATE_UNAVAILABLE_TEXT

        job_cancelled = self._cancel_pending_import_job(job=pending_job)
        if job_cancelled is not True:
            return IMPORT_CANCEL_STATE_UNAVAILABLE_TEXT

        self._clear_pending_copy_fallback(task_id=pending_job.task_id, task_hash=pending_job.task_hash)
        self._record_event(
            task_ref=pending_job.task_ref,
            task_id=pending_job.task_id,
            task_hash=pending_job.task_hash,
            event_type="import.cancelled",
            message=IMPORT_CANCELLED_TEXT,
        )
        return IMPORT_CANCELLED_TEXT

    def _log_expired_cancel_pending_job_result_missing(self, *, job: JobRecord, task_ref: str, reason: str) -> None:
        emit_operational_log(
            title="导入确认超时任务结果缺失",
            detail=f"task_ref={task_ref} job_id={job.job_id} task_id={job.task_id} task_hash={job.task_hash} version={job.version} 原因={reason}",
            fix_hint="检查 jobs 表里该待确认导入任务是否仍存在，以及超时取消后是否还能回读到最新状态；当前 confirm 会直接返回状态读取失败，避免把缺失真相误判成普通“导入确认已超时”。",
        )

    async def _prepare_import(
        self,
        task_ref: str,
        *,
        chat_id: int | None = None,
    ) -> tuple[PreparedImport | None, str]:
        return await self._prepare_state.prepare_import(task_ref=task_ref, chat_id=chat_id)

    def _is_raw_bt_task(self, *, chat_id: int | None, task_ref: str) -> bool | None:
        lookup = self._context_lookup.lookup_raw_bt_task(chat_id=chat_id, task_ref=task_ref)
        if lookup.error_kind == "row_corrupted":
            self._log_raw_bt_lookup_row_corrupted(
                chat_id=chat_id or 0,
                task_ref=task_ref,
                reason=lookup.detail,
            )
            return None
        if lookup.error_kind == "lookup_failed":
            self._log_raw_bt_lookup_failed(
                chat_id=chat_id or 0,
                task_ref=task_ref,
                reason=lookup.detail,
            )
            return None
        if lookup.error_kind == "result_missing":
            self._log_raw_bt_lookup_result_missing(
                chat_id=chat_id or 0,
                task_ref=task_ref,
                reason=IMPORT_RAW_BT_LOOKUP_RESULT_MISSING_REASON,
            )
            return None
        if lookup.error_kind == "payload_corrupted":
            self._log_raw_bt_payload_corrupted(
                chat_id=chat_id or 0,
                task_ref=task_ref,
                payload_summary=lookup.detail,
            )
            return None
        return lookup.is_raw_bt

    def _resolve_normalized_naming_truth(
        self,
        *,
        task_id: str,
        task_hash: str,
        fallback_name: str,
    ) -> str:
        return self._prepare_state.resolve_normalized_naming_truth(
            task_id=task_id,
            task_hash=task_hash,
            fallback_name=fallback_name,
        )

    async def _execute_import(
        self,
        task_ref: str,
        prepared_import: PreparedImport,
        *,
        execution_mode: str,
    ) -> ImportExecutionResult:
        return await self._transfer_execution_service.execute_import(
            task_ref=task_ref,
            prepared_import=prepared_import,
            execution_mode=execution_mode,
        )

    def _resolve_metadata_title_year(self, *, task_id: str, task_hash: str, target_path: Path) -> tuple[str, str]:
        fallback_title, fallback_year = extract_title_year_for_scrape(target_path)
        confirmed_media_identity = self._resolve_confirmed_media_identity(task_id=task_id, task_hash=task_hash)
        if confirmed_media_identity is not None:
            title = (
                confirmed_media_identity.get("title", "").strip()
                or confirmed_media_identity.get("original_title", "").strip()
                or fallback_title
            )
            year = confirmed_media_identity.get("year", "").strip() or fallback_year
            return title, year

        naming_truth = self._resolve_normalized_naming_truth(
            task_id=task_id,
            task_hash=task_hash,
            fallback_name="",
        )
        if not naming_truth:
            return fallback_title, fallback_year

        title_from_truth, year_from_truth = extract_title_year_from_text(naming_truth)
        title = title_from_truth or fallback_title
        year = year_from_truth or fallback_year
        return title, year

    def _resolve_confirmed_media_identity(self, *, task_id: str, task_hash: str) -> dict[str, str] | None:
        if self._job_event_repo is None:
            return None
        try:
            events = self._job_event_repo.list_events_for_task_identity(task_id=task_id, task_hash=task_hash)
            if events is None:
                raise JobEventPersistenceError(IMPORT_MEDIA_IDENTITY_RESULT_MISSING_REASON)
        except (JobEventPersistenceError, sqlite3.Error) as error:
            if str(error) == IMPORT_MEDIA_IDENTITY_RESULT_MISSING_REASON:
                self._log_import_media_identity_result_missing(task_id=task_id, task_hash=task_hash, reason=str(error))
            elif _is_import_media_identity_row_corrupted_error(error):
                self._log_import_media_identity_row_corrupted(task_id=task_id, task_hash=task_hash, reason=str(error))
            else:
                self._log_import_media_identity_query_failed(task_id=task_id, task_hash=task_hash, reason=str(error))
            return None
        for event in reversed(events):
            if event.event_type != MEDIA_IDENTITY_EVENT_TYPE:
                continue
            media_identity = media_identity_from_json(event.message)
            if media_identity is not None:
                return media_identity
        return None

    def _resolve_confirmed_media_tmdb_id(self, task_id: str, task_hash: str) -> str:
        confirmed_media_identity = self._resolve_confirmed_media_identity(task_id=task_id, task_hash=task_hash)
        if confirmed_media_identity is None:
            return ""
        return confirmed_media_identity.get("tmdb_id", "").strip()

    def _record_pending_approval(self, *, task_ref: str, task_id: str, task_hash: str) -> int:
        return self._approval_state.record_pending_approval_with_copy_fallback_reset(
            task_ref=task_ref,
            task_id=task_id,
            task_hash=task_hash,
            clear_pending_copy_fallback=self._clear_pending_copy_fallback,
        )

    def _record_import_approval(
        self,
        *,
        task_ref: str,
        task_id: str,
        task_hash: str,
        expected_lease_version: int,
    ) -> bool | None:
        return self._approval_state.record_import_approval(
            task_ref=task_ref,
            task_id=task_id,
            task_hash=task_hash,
            expected_lease_version=expected_lease_version,
        )

    def _restore_pending_approval(
        self,
        *,
        task_ref: str,
        task_id: str,
        task_hash: str,
        expected_lease_version: int,
    ) -> bool | None:
        return self._approval_state.restore_pending_approval(
            task_ref=task_ref,
            task_id=task_id,
            task_hash=task_hash,
            expected_lease_version=expected_lease_version,
        )

    def _record_executed_lease_version(
        self,
        *,
        task_ref: str,
        task_id: str,
        task_hash: str,
        executed_lease_version: int,
    ) -> bool | None:
        _ = task_ref
        return self._approval_state.record_executed_lease_version(
            task_id=task_id,
            task_hash=task_hash,
            executed_lease_version=executed_lease_version,
        )

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
            elif _is_job_row_corrupted_error(error):
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

    def _persist_pending_import(
        self,
        *,
        task_ref: str,
        import_source: TransmissionImportSource,
        chat_id: int | None,
        user_id: int | None,
        record_pending_approval: Callable[..., int],
        record_pending_job: Callable[..., bool],
        record_event: Callable[..., None],
        log_trace: Callable[..., None],
    ) -> str:
        expected_lease_version = record_pending_approval(
            task_ref=task_ref,
            task_id=import_source.task_id,
            task_hash=import_source.task_hash,
        )
        if expected_lease_version <= 0:
            return IMPORT_PENDING_STATE_UNAVAILABLE_TEXT
        if not record_pending_job(
            chat_id=chat_id,
            user_id=user_id,
            task_ref=task_ref,
            task_id=import_source.task_id,
            task_hash=import_source.task_hash,
            payload_json="",
        ):
            self._cancel_pending_approval_after_job_write_failure(
                task_ref=task_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                expected_lease_version=expected_lease_version,
            )
            return IMPORT_PENDING_STATE_UNAVAILABLE_TEXT
        record_event(
            task_ref=task_ref,
            task_id=import_source.task_id,
            task_hash=import_source.task_hash,
            event_type="import.approval_pending",
            message=task_ref,
        )
        log_trace(
            event="approval_pending",
            result="created",
            stage="pending",
            chat_id=chat_id,
            user_id=user_id,
            task_ref=task_ref,
            task_id=import_source.task_id,
            task_hash=import_source.task_hash,
            detail=import_source.name,
        )
        return IMPORT_APPROVAL_PENDING_TEXT.format(
            name=import_source.name,
            task_id=import_source.task_id,
            task_hash=import_source.task_hash,
            task_ref=task_ref,
        )

    def _cancel_pending_approval_after_job_write_failure(
        self,
        *,
        task_ref: str,
        task_id: str,
        task_hash: str,
        expected_lease_version: int,
    ) -> None:
        if self._approval_repo is None:
            return
        try:
            self._approval_repo.cancel_import(
                task_id=task_id,
                task_hash=task_hash,
                task_ref=task_ref,
                expected_lease_version=expected_lease_version,
            )
        except (ApprovalPersistenceError, sqlite3.Error) as error:
            emit_operational_log(
                title="导入取消审批更新失败",
                detail=f"task_ref={task_ref} task_id={task_id} task_hash={task_hash} lease_version={expected_lease_version} 错误={error}",
                fix_hint="检查 SQLite/approval_record 表更新是否正常；当前导入待确认创建会直接失败返回，但审批真相可能仍残留。",
            )

    def _lookup_pending_import_job_for_cancel(self, *, chat_id: int) -> tuple[JobRecord | None, bool]:
        pending_lookup_failed = False
        try:
            pending_job = self._job_repo.get_latest_pending_import_job(chat_id=chat_id)
        except (JobPersistenceError, sqlite3.Error) as error:
            self._log_import_cancel_state_error(
                title="导入取消查询失败",
                detail=f"chat_id={chat_id} 错误={error}",
                fix_hint="检查 SQLite/jobs 表读取是否正常；当前取消会直接返回状态读取失败，避免把查询异常误判成“没有待取消导入”。",
            )
            pending_job = None
            pending_lookup_failed = True
        return pending_job, pending_lookup_failed

    def _cancel_pending_import_approval(
        self,
        *,
        job: JobRecord,
        expected_lease_version: int,
    ) -> bool | None:
        if self._approval_repo is None:
            return True
        try:
            approval_cancelled = self._approval_repo.cancel_import(
                task_id=job.task_id,
                task_hash=job.task_hash,
                task_ref=job.task_ref,
                expected_lease_version=expected_lease_version,
            )
            if approval_cancelled is None:
                raise ApprovalPersistenceError(IMPORT_CANCEL_APPROVAL_NONE_REASON)
        except (ApprovalPersistenceError, sqlite3.Error) as error:
            if str(error) in {
                IMPORT_CANCEL_APPROVAL_RESULT_MISSING_REASON,
                IMPORT_CANCEL_APPROVAL_NONE_REASON,
            }:
                self._log_import_cancel_state_error(
                    title="导入取消审批结果缺失",
                    detail=f"task_ref={job.task_ref} task_id={job.task_id} task_hash={job.task_hash} lease_version={expected_lease_version} 错误={error}",
                    fix_hint=(
                        "检查 approval_record 表里该待确认导入审批是否仍存在，以及取消更新后是否还能回读到该行；"
                        "当前取消会直接返回状态读取失败，避免把缺失真相误判成普通状态冲突或普通“没有待取消导入”。"
                    ),
                )
            else:
                self._log_import_cancel_state_error(
                    title="导入取消审批更新失败",
                    detail=f"task_ref={job.task_ref} task_id={job.task_id} task_hash={job.task_hash} lease_version={expected_lease_version} 错误={error}",
                    fix_hint="检查 SQLite/approval_record 表更新是否正常；当前取消会直接失败返回，待确认导入状态可能仍残留。",
                )
            return None
        if not approval_cancelled:
            self._log_import_cancel_state_error(
                title="导入取消审批更新失败",
                detail=f"task_ref={job.task_ref} task_id={job.task_id} task_hash={job.task_hash} lease_version={expected_lease_version} 错误=approval_record missing or lease_version mismatch",
                fix_hint="检查 SQLite/approval_record 表里的待确认导入审批是否仍存在，或是否已被其他路径抢先取消/确认；当前取消会直接返回状态读取失败，避免把审批真相缺口误判成“没有待取消导入”。",
            )
            return False
        return True

    def _cancel_pending_import_job(self, *, job: JobRecord) -> bool | None:
        try:
            cancelled = self._job_repo.cancel_pending_job(
                job_id=job.job_id,
                expected_version=job.version,
                workflow_type=WORKFLOW_IMPORT_TO_LIBRARY,
            )
            if cancelled is None:
                raise JobPersistenceError(IMPORT_CANCEL_PENDING_JOB_RESULT_MISSING_REASON)
        except (JobPersistenceError, sqlite3.Error) as error:
            if str(error) in {
                IMPORT_CANCEL_PENDING_JOB_RESULT_MISSING_REASON,
                IMPORT_CANCEL_PENDING_JOB_ROW_MISSING_REASON,
            }:
                self._log_import_cancel_pending_job_result_missing(job=job, reason=str(error))
            else:
                self._log_import_cancel_state_error(
                    title="导入取消任务更新失败",
                    detail=f"task_ref={job.task_ref} job_id={job.job_id} task_id={job.task_id} task_hash={job.task_hash} version={job.version} 错误={error}",
                    fix_hint="检查 SQLite/jobs 表更新是否正常；当前审批可能已取消，但任务真相可能仍残留在待确认状态。",
                )
            return None
        if not cancelled:
            self._log_import_cancel_state_error(
                title="导入取消任务更新失败",
                detail=f"task_ref={job.task_ref} job_id={job.job_id} task_id={job.task_id} task_hash={job.task_hash} version={job.version} 错误=jobs.cancel_pending_job rejected current state",
                fix_hint="检查该任务是否已被其他路径抢先取消、确认或完结；当前审批可能已取消，但待确认任务真相可能已被其他状态迁移抢先改写。",
            )
            return False
        return True

    def _log_import_cancel_pending_job_result_missing(self, *, job: JobRecord, reason: str) -> None:
        self._log_import_cancel_state_error(
            title="导入取消任务结果缺失",
            detail=f"task_ref={job.task_ref} job_id={job.job_id} task_id={job.task_id} task_hash={job.task_hash} version={job.version} 原因={reason}",
            fix_hint="检查 jobs 表里该待确认导入任务是否仍存在，以及取消更新后是否还能回读到最新状态；当前审批可能已取消，但任务真相还没有确认取消成功。",
        )

    def _log_import_cancel_state_error(self, *, title: str, detail: str, fix_hint: str) -> None:
        emit_operational_log(title=title, detail=detail, fix_hint=fix_hint)

    def _resolve_execution_mode(
        self,
        *,
        task_id: str,
        task_hash: str,
        confirm_context: ConfirmExecutionContext | None,
    ) -> str | None:
        return self._transfer_execution_service.resolve_execution_mode(
            task_id=task_id,
            task_hash=task_hash,
            confirm_context=confirm_context,
        )

    def _record_copy_fallback_pending(self, *, task_id: str, task_hash: str) -> None:
        self._transfer_execution_service.record_copy_fallback_pending(task_id=task_id, task_hash=task_hash)

    def _clear_pending_copy_fallback(self, *, task_id: str, task_hash: str) -> None:
        self._transfer_execution_service.clear_pending_copy_fallback(task_id=task_id, task_hash=task_hash)

    def _copy_fallback_pending_to_json(self) -> str:
        return self._transfer_execution_service.pending_copy_fallback_payload_json()

    def _rebuild_confirm_context(
        self,
        *,
        task_ref: str,
        chat_id: int | None,
    ) -> tuple[ConfirmExecutionContext | None, bool]:
        lookup = self._context_lookup.rebuild_confirm_context(task_ref=task_ref, chat_id=chat_id)
        if lookup.lookup_failed:
            if lookup.job_error_kind == "row_corrupted":
                self._log_confirm_context_row_corrupted(
                    chat_id=chat_id or 0,
                    task_ref=task_ref,
                    reason=lookup.job_error_detail,
                )
            else:
                self._log_confirm_context_lookup_failed(
                    chat_id=chat_id or 0,
                    task_ref=task_ref,
                    reason=lookup.job_error_detail,
                )
            return None, True
        context = lookup.context
        if context is not None and context.approval_lookup_failed:
            self._log_confirm_approval_lookup_failed(
                task_ref=task_ref,
                task_id=context.job.task_id,
                task_hash=context.job.task_hash,
                reason=lookup.approval_error_detail,
            )
        return context, False

    def _claim_pending_job(self, *, job: JobRecord, lease_owner: str) -> bool | None:
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

    def _mark_completed_job(
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

    def _build_job_lease_owner(self, task_ref: str) -> str:
        cleaned_ref = task_ref.strip()
        if not cleaned_ref:
            return JOB_LEASE_OWNER
        return f"{JOB_LEASE_OWNER}:{cleaned_ref}"

    def _resolve_pending_lease_version(
        self,
        *,
        task_id: str,
        task_hash: str,
        allow_in_memory_fallback_on_error: bool = True,
    ) -> int:
        return self._approval_state.resolve_pending_lease_version(
            task_id=task_id,
            task_hash=task_hash,
            allow_in_memory_fallback_on_error=allow_in_memory_fallback_on_error,
        )

    def _find_version_stale_rejection_text(self, *, task_id: str, task_hash: str) -> str | None:
        return self._approval_state.find_version_stale_rejection_text(task_id=task_id, task_hash=task_hash)

    def _find_latest_import_target_path(self, *, task_id: str, task_hash: str) -> ImportTargetLookupResult:
        return self._approval_state.find_latest_import_target_path(task_id=task_id, task_hash=task_hash)

    def _handle_expired_pending_confirm(self, *, task_ref: str, context: ConfirmExecutionContext) -> str | None:
        return self._confirm_expiry_state.handle_expired_pending_confirm(
            task_ref=task_ref,
            context=context,
            is_pending_approval_expired=self._is_pending_approval_expired,
            clear_pending_copy_fallback=self._clear_pending_copy_fallback,
            record_event=self._record_event,
            log_expired_cancel_pending_job_result_missing=self._log_expired_cancel_pending_job_result_missing,
        )

    def _is_pending_approval_expired(
        self,
        *,
        task_id: str,
        task_hash: str,
        expected_lease_version: int,
    ) -> bool | None:
        return self._approval_state.is_pending_approval_expired(
            task_id=task_id,
            task_hash=task_hash,
            expected_lease_version=expected_lease_version,
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
        if self._job_event_repo is None:
            return
        details = (
            f"task_ref={task_ref} task_id={task_id} task_hash={task_hash} "
            f"event_type={event_type} source={source_path} target={target_path}"
        )
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
            if str(error) == IMPORT_EVENT_RESULT_MISSING_REASON:
                emit_operational_log(
                    title="导入事件结果缺失",
                    detail=f"{details} 错误=import event missing after append",
                    fix_hint="检查 job_event 写入后回读是否仍能拿到刚追加的导入事件；当前导入流程会继续执行，但这次事件真相还没有确认落稳。",
                )
            elif _is_import_event_row_corrupted_error(error):
                emit_operational_log(
                    title="导入事件记录损坏",
                    detail=f"{details} 错误={error}",
                    fix_hint="检查 job_event 读回事件里的 task_ref / event_type / source_path / target_path 等真相字段是否仍然完整；当前导入流程会继续执行，但不会把这条坏事件当成已稳定落盘。",
                )
            else:
                emit_operational_log(
                    title="导入事件落盘失败",
                    detail=f"{details} 错误={error}",
                    fix_hint="检查 SQLite/job_event 表写入是否正常；当前导入流程会继续执行，但这次事件可能没有落盘。",
                )
        except sqlite3.Error as error:
            emit_operational_log(
                title="导入事件落盘失败",
                detail=f"{details} 错误={error}",
                fix_hint="检查 SQLite/job_event 表写入是否正常；当前导入流程会继续执行，但这次事件可能没有落盘。",
            )

    def _log_import_media_identity_query_failed(self, *, task_id: str, task_hash: str, reason: str) -> None:
        emit_operational_log(
            title="导入媒体身份查询失败",
            detail=f"task_id={task_id} task_hash={task_hash} 错误={reason}",
            fix_hint="检查 SQLite/job_event 表读取是否正常；当前 metadata 入参会退回命名真相或文件名解析，避免把查询失败混成普通“无媒体身份”。",
        )

    def _log_import_media_identity_result_missing(self, *, task_id: str, task_hash: str, reason: str) -> None:
        emit_operational_log(
            title="导入媒体身份结果缺失",
            detail=f"task_id={task_id} task_hash={task_hash} 错误={reason}",
            fix_hint="检查 job_event 查询返回是否仍带有完整结果；当前 metadata 入参会退回命名真相或文件名解析，避免把缺失真相误判成“没有已确认媒体身份”。",
        )

    def _log_import_media_identity_row_corrupted(self, *, task_id: str, task_hash: str, reason: str) -> None:
        emit_operational_log(
            title="导入媒体身份记录损坏",
            detail=f"task_id={task_id} task_hash={task_hash} 错误={reason}",
            fix_hint="检查 job_event 里的 task_ref / event_type / message 等媒体身份字段是否仍是完整记录；当前 metadata 入参会退回命名真相或文件名解析，避免把坏记录混成普通查询失败。",
        )

    def _log_raw_bt_lookup_failed(self, *, chat_id: int, task_ref: str, reason: str) -> None:
        emit_operational_log(
            title="导入 raw_bt 判定查询失败",
            detail=f"chat_id={chat_id} task_ref={task_ref} 错误={reason}",
            fix_hint="检查 SQLite/jobs 表读取是否正常；当前请求会直接返回查询失败，避免把原本应被阻断的 raw_bt 任务继续送进入库链。",
        )

    def _log_raw_bt_payload_corrupted(self, *, chat_id: int, task_ref: str, payload_summary: str) -> None:
        emit_operational_log(
            title="导入 raw_bt 判定载荷损坏",
            detail=f"chat_id={chat_id} task_ref={task_ref} 载荷={payload_summary}",
            fix_hint="检查 SQLite/jobs 表里的 payload_json 是否仍是完整下载任务上下文；当前请求会直接返回查询失败，避免把原本应被阻断的 raw_bt 任务继续送进入库链。",
        )

    def _log_raw_bt_lookup_result_missing(self, *, chat_id: int, task_ref: str, reason: str) -> None:
        emit_operational_log(
            title="导入 raw_bt 判定结果缺失",
            detail=f"chat_id={chat_id} task_ref={task_ref} 错误={reason}",
            fix_hint="检查 SQLite/jobs 表里当前下载任务是否仍存在，并确认这条任务真相没有被提前清理；当前请求会直接返回查询失败，避免把 raw_bt 分类真相缺口误判成普通“不是 raw_bt”。",
        )

    def _log_raw_bt_lookup_row_corrupted(self, *, chat_id: int, task_ref: str, reason: str) -> None:
        emit_operational_log(
            title="导入 raw_bt 判定记录损坏",
            detail=f"chat_id={chat_id} task_ref={task_ref} 错误={reason}",
            fix_hint="检查 SQLite/jobs 表里当前下载任务的 job_id / chat_id / task_ref / payload_json 等真相字段；当前请求会直接返回查询失败，避免把坏任务记录误判成普通查询失败或普通“不是 raw_bt”。",
        )

    def _log_confirm_context_row_corrupted(self, *, chat_id: int, task_ref: str, reason: str) -> None:
        emit_operational_log(
            title="导入确认上下文记录损坏",
            detail=f"chat_id={chat_id} task_ref={task_ref} 错误={reason}",
            fix_hint="检查 SQLite/jobs 表里当前导入任务的 job_id / chat_id / task_ref / task_id / task_hash / version 等真相字段；当前 confirm 会直接返回状态读取失败，避免把坏任务记录误判成普通查询失败或“没有待确认导入”。",
        )

    def _log_confirm_context_lookup_failed(self, *, chat_id: int, task_ref: str, reason: str) -> None:
        emit_operational_log(
            title="导入确认上下文查询失败",
            detail=f"chat_id={chat_id} task_ref={task_ref} 错误={reason}",
            fix_hint="检查 SQLite/jobs 表查询是否正常；当前 confirm 会直接返回状态读取失败，避免把持久化异常误判成“没有待确认导入”或“未找到对应下载任务”。",
        )

    def _log_confirm_approval_lookup_failed(self, *, task_ref: str, task_id: str, task_hash: str, reason: str) -> None:
        emit_operational_log(
            title="导入确认审批查询失败",
            detail=f"task_ref={task_ref} task_id={task_id} task_hash={task_hash} 错误={reason}",
            fix_hint="检查 SQLite/approval_record 表查询是否正常；当前 confirm 会直接返回状态读取失败，避免把审批真相缺口误判成普通未确认状态。",
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


def _is_job_row_corrupted_error(error: Exception) -> bool:
    return isinstance(error, JobPersistenceError) and str(error).endswith("corrupted after read")


def _is_import_event_row_corrupted_error(error: Exception) -> bool:
    return isinstance(error, JobEventPersistenceError) and str(error).endswith("corrupted after read")


def _is_import_target_lookup_row_corrupted_error(error: Exception) -> bool:
    return isinstance(error, JobEventPersistenceError) and str(error).endswith("corrupted after read")


def _is_import_media_identity_row_corrupted_error(error: Exception) -> bool:
    return isinstance(error, JobEventPersistenceError) and str(error).endswith("corrupted after read")

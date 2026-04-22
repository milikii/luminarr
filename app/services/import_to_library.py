from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from pathlib import Path

from app.clients.transmission import TransmissionImportSource
from app.db.approval_repo import (
    APPROVAL_STATUS_PENDING,
    ApprovalRepo,
)
from app.db.job_event_repo import JobEventPersistenceError, JobEventRepo
from app.db.job_repo import JOB_STATE_PENDING_APPROVAL, JobPersistenceError, JobRecord, JobRepo, WORKFLOW_IMPORT_TO_LIBRARY
from app.services import import_transfer_execution
from app.services.import_approval_state import ImportApprovalState, ImportTargetLookupResult
from app.services.import_cancel_state import ImportCancelState
from app.services.import_context_lookup import ConfirmExecutionContext, ImportContextLookup
from app.services.import_job_state import ImportJobState
from app.services.import_post_processing import ImportPostProcessingService, MetadataScrapeFunc, RefreshMediaServerFunc, SubtitleTranslateFunc
from app.services.import_prepare_state import (
    ImportPrepareState,
    build_normalized_target_name as _build_normalized_target_name,
    extract_title_year_for_scrape as _extract_title_year_for_scrape,
    extract_title_year_from_text as _extract_title_year_from_text,
)
from app.services.import_transfer_execution import IMPORT_EXECUTION_MODE_COPY, ImportExecutionResult, PreparedImport
from app.trace_logging import log_trace_event

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
        self._job_event_repo = job_event_repo
        self._approval_repo = approval_repo
        self._job_repo = job_repo
        self._trace_log_path = trace_log_path
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
        self._job_state = ImportJobState(
            job_repo=job_repo,
            is_job_row_corrupted_error=_is_job_row_corrupted_error,
        )
        self._cancel_state = ImportCancelState(
            job_repo=job_repo,
            approval_repo=approval_repo,
            import_cancel_state_unavailable_text=IMPORT_CANCEL_STATE_UNAVAILABLE_TEXT,
            import_cancelled_text=IMPORT_CANCELLED_TEXT,
            pending_lease_lookup_failed=PENDING_LEASE_LOOKUP_FAILED,
            import_cancel_pending_job_result_missing_reason=IMPORT_CANCEL_PENDING_JOB_RESULT_MISSING_REASON,
            import_cancel_pending_job_row_missing_reason=IMPORT_CANCEL_PENDING_JOB_ROW_MISSING_REASON,
            import_cancel_approval_result_missing_reason=IMPORT_CANCEL_APPROVAL_RESULT_MISSING_REASON,
            import_cancel_approval_none_reason=IMPORT_CANCEL_APPROVAL_NONE_REASON,
        )
        self._pending_import_identities = self._approval_state.pending_import_identities
        self._pending_import_lease_versions = self._approval_state.pending_import_lease_versions
        self._post_processing_service = ImportPostProcessingService(
            refresh_media_server_func=refresh_media_server_func,
            scrape_metadata_func=scrape_metadata_func,
            translate_subtitle_func=translate_subtitle_func,
            resolve_metadata_title_year_func=self._resolve_metadata_title_year,
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
        self._transfer_execution_service = import_transfer_execution.ImportTransferExecutionService(
            post_processing_service=self._post_processing_service,
            record_event_func=self._record_event,
            import_source_type_unsupported_text=IMPORT_SOURCE_TYPE_UNSUPPORTED_TEXT,
            import_target_exists_text_template=IMPORT_TARGET_EXISTS_TEXT,
            import_copy_approval_pending_text_template=IMPORT_COPY_APPROVAL_PENDING_TEXT,
            import_copy_failed_text_template=IMPORT_COPY_FAILED_TEXT,
            import_hardlink_failed_text_template=IMPORT_HARDLINK_FAILED_TEXT,
        )

    def _log_trace(
        self,
        *,
        event: str,
        result: str,
        stage: str,
        chat_id: int | None = None,
        user_id: int | None = None,
        task_ref: str = "",
        task_id: str = "",
        task_hash: str = "",
        detail: str = "",
    ) -> None:
        log_trace_event(
            scope="workflow",
            workflow=WORKFLOW_IMPORT_TO_LIBRARY,
            event=event,
            result=result,
            stage=stage,
            log_path=self._trace_log_path,
            chat_id=chat_id,
            user_id=user_id,
            task_ref=task_ref,
            task_id=task_id,
            task_hash=task_hash,
            detail=detail,
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

        import_source = prepared_import.import_source
        expected_lease_version = self._record_pending_approval(
            task_ref=cleaned_ref,
            task_id=import_source.task_id,
            task_hash=import_source.task_hash,
        )
        if expected_lease_version <= 0:
            return IMPORT_PENDING_STATE_UNAVAILABLE_TEXT
        if not self._record_pending_job(
            chat_id=chat_id,
            user_id=user_id,
            task_ref=cleaned_ref,
            task_id=import_source.task_id,
            task_hash=import_source.task_hash,
            payload_json="",
        ):
            if self._approval_repo is not None:
                try:
                    self._approval_repo.cancel_import(
                        task_id=import_source.task_id,
                        task_hash=import_source.task_hash,
                        task_ref=cleaned_ref,
                        expected_lease_version=expected_lease_version,
                    )
                except Exception as error:
                    print(
                        f"\033[31m[导入取消审批更新失败]\033[0m task_ref={cleaned_ref} task_id={import_source.task_id} task_hash={import_source.task_hash} lease_version={expected_lease_version} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表更新是否正常；当前导入待确认创建会直接失败返回，但审批真相可能仍残留。",
                        flush=True,
                    )
            return IMPORT_PENDING_STATE_UNAVAILABLE_TEXT
        self._record_event(
            task_ref=cleaned_ref,
            task_id=import_source.task_id,
            task_hash=import_source.task_hash,
            event_type="import.approval_pending",
            message=cleaned_ref,
        )
        self._log_trace(
            event="approval_pending",
            result="created",
            stage="pending",
            chat_id=chat_id,
            user_id=user_id,
            task_ref=cleaned_ref,
            task_id=import_source.task_id,
            task_hash=import_source.task_hash,
            detail=import_source.name,
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

        confirm_context, confirm_context_lookup_failed = self._rebuild_confirm_context(
            task_ref=cleaned_ref,
            chat_id=chat_id,
        )
        if confirm_context_lookup_failed:
            return IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT
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
            if claimed_job is None:
                return IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT
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

        execution_mode = self._resolve_execution_mode(
            task_id=import_source.task_id,
            task_hash=import_source.task_hash,
            confirm_context=confirm_context,
        )
        if execution_mode is None:
            if claimed_job:
                self._restore_pending_job(
                    job_id=claimed_job_id,
                    expected_version=claimed_job_version,
                    lease_owner=lease_owner,
                )
            return IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT

        expected_lease_version = 0
        if confirm_context is not None and confirm_context.approval_record is not None:
            expected_lease_version = max(0, confirm_context.approval_record.lease_version)
        if expected_lease_version <= 0:
            expected_lease_version = self._resolve_pending_lease_version(
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                allow_in_memory_fallback_on_error=False,
            )
        if expected_lease_version == PENDING_LEASE_LOOKUP_FAILED:
            if claimed_job:
                self._restore_pending_job(
                    job_id=claimed_job_id,
                    expected_version=claimed_job_version,
                    lease_owner=lease_owner,
                )
            return IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT
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
        if approved is None:
            if claimed_job:
                self._restore_pending_job(
                    job_id=claimed_job_id,
                    expected_version=claimed_job_version,
                    lease_owner=lease_owner,
                )
            return IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT
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

        execution = await self._execute_import(
            cleaned_ref,
            prepared_import,
            execution_mode=execution_mode,
        )
        if execution.imported:
            self._log_trace(
                event="confirm_execute",
                result="imported",
                stage="execute",
                chat_id=chat_id,
                user_id=user_id,
                task_ref=cleaned_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                detail=execution.reply,
            )
            finalization_warning = ""
            lease_recorded = self._record_executed_lease_version(
                task_ref=cleaned_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                executed_lease_version=expected_lease_version,
            )
            if lease_recorded is not True:
                finalization_warning = IMPORT_FINALIZATION_WARNING_TEXT
            self._clear_pending_copy_fallback(
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
            )
            if claimed_job:
                job_completed = self._mark_completed_job(
                    job_id=claimed_job_id,
                    expected_version=claimed_job_version,
                    lease_owner=lease_owner,
                )
                if job_completed is not True:
                    finalization_warning = IMPORT_FINALIZATION_WARNING_TEXT
            if finalization_warning:
                self._log_trace(
                    event="confirm_finalize",
                    result="warning",
                    stage="completed",
                    chat_id=chat_id,
                    user_id=user_id,
                    task_ref=cleaned_ref,
                    task_id=import_source.task_id,
                    task_hash=import_source.task_hash,
                    detail=IMPORT_FINALIZATION_WARNING_TEXT,
                )
                return f"{execution.reply}\n\n{finalization_warning}"
            self._log_trace(
                event="confirm_finalize",
                result="succeeded",
                stage="completed",
                chat_id=chat_id,
                user_id=user_id,
                task_ref=cleaned_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                detail=execution.reply,
            )
        elif execution.pending_copy_approval:
            self._log_trace(
                event="confirm_execute",
                result="copy_fallback_pending",
                stage="execute",
                chat_id=chat_id,
                user_id=user_id,
                task_ref=cleaned_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                detail=execution.reply,
            )
            approval_restored = self._restore_pending_approval(
                task_ref=cleaned_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                expected_lease_version=expected_lease_version,
            )
            if approval_restored is not True:
                if claimed_job:
                    self._restore_pending_job(
                        job_id=claimed_job_id,
                        expected_version=claimed_job_version,
                        lease_owner=lease_owner,
                    )
                return IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT
            self._record_copy_fallback_pending(
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
            )
            if confirm_context is not None:
                persisted = self._record_pending_job(
                    chat_id=confirm_context.job.chat_id,
                    user_id=confirm_context.job.user_id,
                    task_ref=confirm_context.job.task_ref or cleaned_ref,
                    task_id=import_source.task_id,
                    task_hash=import_source.task_hash,
                    payload_json=self._copy_fallback_pending_to_json(),
                )
                if not persisted and claimed_job:
                    self._restore_pending_job(
                        job_id=claimed_job_id,
                        expected_version=claimed_job_version,
                        lease_owner=lease_owner,
                    )
        else:
            approval_restored = self._restore_pending_approval(
                task_ref=cleaned_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                expected_lease_version=expected_lease_version,
            )
            if approval_restored is not True:
                if claimed_job:
                    self._restore_pending_job(
                        job_id=claimed_job_id,
                        expected_version=claimed_job_version,
                        lease_owner=lease_owner,
                    )
                return IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT
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
                        payload_json=self._copy_fallback_pending_to_json(),
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
            self._log_trace(
                event="confirm_execute",
                result="failed",
                stage="execute",
                chat_id=chat_id,
                user_id=user_id,
                task_ref=cleaned_ref,
                task_id=import_source.task_id,
                task_hash=import_source.task_hash,
                detail=execution.reply,
            )
        return execution.reply

    def cancel_pending_import(self, chat_id: int) -> str | None:
        return self._cancel_state.cancel_pending_import(
            chat_id=chat_id,
            resolve_pending_lease_version=self._resolve_pending_lease_version,
            clear_pending_copy_fallback=self._clear_pending_copy_fallback,
            record_event=self._record_event,
        )

    def _log_expired_cancel_pending_job_result_missing(self, *, job: JobRecord, task_ref: str, reason: str) -> None:
        print(
            f"\033[31m[导入确认超时任务结果缺失]\033[0m task_ref={task_ref} job_id={job.job_id} task_id={job.task_id} task_hash={job.task_hash} version={job.version} 原因={reason}\n\033[33m[处理建议]\033[0m 检查 jobs 表里该待确认导入任务是否仍存在，以及超时取消后是否还能回读到最新状态；当前 confirm 会直接返回状态读取失败，避免把缺失真相误判成普通“导入确认已超时”。",
            flush=True,
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
            print(
                f"\033[31m[导入 raw_bt 判定查询失败]\033[0m chat_id={chat_id or 0} task_ref={task_ref} 错误={lookup.detail}\n\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表读取是否正常；当前请求会直接返回查询失败，避免把原本应被阻断的 raw_bt 任务继续送进入库链。",
                flush=True,
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

    def _log_raw_bt_payload_corrupted(self, *, chat_id: int, task_ref: str, payload_summary: str) -> None:
        print(
            f"\033[31m[导入 raw_bt 判定载荷损坏]\033[0m chat_id={chat_id} task_ref={task_ref} 载荷={payload_summary}\n\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表里的 payload_json 是否仍是完整下载任务上下文；当前请求会直接返回查询失败，避免把原本应被阻断的 raw_bt 任务继续送进入库链。",
            flush=True,
        )

    def _log_raw_bt_lookup_result_missing(self, *, chat_id: int, task_ref: str, reason: str) -> None:
        print(
            f"\033[31m[导入 raw_bt 判定结果缺失]\033[0m chat_id={chat_id} task_ref={task_ref} 错误={reason}\n"
            "\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表里当前下载任务是否仍存在，并确认这条任务真相没有被提前清理；"
            "当前请求会直接返回查询失败，避免把 raw_bt 分类真相缺口误判成普通“不是 raw_bt”。",
            flush=True,
        )

    def _log_raw_bt_lookup_row_corrupted(self, *, chat_id: int, task_ref: str, reason: str) -> None:
        print(
            f"\033[31m[导入 raw_bt 判定记录损坏]\033[0m chat_id={chat_id} task_ref={task_ref} 错误={reason}\n"
            "\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表里当前下载任务的 job_id / chat_id / task_ref / payload_json 等真相字段；"
            "当前请求会直接返回查询失败，避免把坏任务记录误判成普通查询失败或普通“不是 raw_bt”。",
            flush=True,
        )

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
        if identity[0] and identity[1]:
            self._clear_pending_copy_fallback(task_id=task_id, task_hash=task_hash)
        return self._approval_state.record_pending_approval(
            task_ref=task_ref,
            task_id=task_id,
            task_hash=task_hash,
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
        return self._job_state.record_pending_job(
            chat_id=chat_id,
            user_id=user_id,
            task_ref=task_ref,
            task_id=task_id,
            task_hash=task_hash,
            payload_json=payload_json,
        )

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
                print(
                    f"\033[31m[导入确认上下文记录损坏]\033[0m chat_id={chat_id or 0} task_ref={task_ref} 错误={lookup.job_error_detail}\n"
                    "\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表里当前导入任务的 job_id / chat_id / task_ref / task_id / task_hash / version 等真相字段；"
                    "当前 confirm 会直接返回状态读取失败，避免把坏任务记录误判成普通查询失败或“没有待确认导入”。",
                    flush=True,
                )
            else:
                print(
                    f"\033[31m[导入确认上下文查询失败]\033[0m chat_id={chat_id or 0} task_ref={task_ref} 错误={lookup.job_error_detail}\n\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表查询是否正常；当前 confirm 会直接返回状态读取失败，避免把持久化异常误判成“没有待确认导入”或“未找到对应下载任务”。",
                    flush=True,
                )
            return None, True
        context = lookup.context
        if context is not None and context.approval_lookup_failed:
            print(
                f"\033[31m[导入确认审批查询失败]\033[0m task_ref={task_ref} task_id={context.job.task_id} task_hash={context.job.task_hash} 错误={lookup.approval_error_detail}\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表查询是否正常；当前 confirm 会直接返回状态读取失败，避免把审批真相缺口误判成普通未确认状态。",
                flush=True,
            )
        return context, False

    def _claim_pending_job(self, *, job: JobRecord, lease_owner: str) -> bool | None:
        return self._job_state.claim_pending_job(job=job, lease_owner=lease_owner)

    def _restore_pending_job(
        self,
        *,
        job_id: str,
        expected_version: int,
        lease_owner: str,
    ) -> None:
        self._job_state.restore_pending_job(
            job_id=job_id,
            expected_version=expected_version,
            lease_owner=lease_owner,
        )

    def _mark_completed_job(
        self,
        *,
        job_id: str,
        expected_version: int,
        lease_owner: str,
    ) -> bool | None:
        return self._job_state.mark_completed_job(
            job_id=job_id,
            expected_version=expected_version,
            lease_owner=lease_owner,
        )

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
                approval_cancelled = self._approval_repo.cancel_import(
                    task_id=context.job.task_id,
                    task_hash=context.job.task_hash,
                    task_ref=task_ref,
                    expected_lease_version=approval_record.lease_version,
                )
            except Exception as error:
                print(
                    f"\033[31m[导入确认超时审批取消失败]\033[0m task_ref={task_ref} task_id={context.job.task_id} task_hash={context.job.task_hash} lease_version={approval_record.lease_version} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表更新是否正常；当前 confirm 会直接返回状态读取失败，避免把审批真相缺口误判成普通“导入确认已超时”。",
                    flush=True,
                )
                return IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT
            if not approval_cancelled:
                print(
                    f"\033[31m[导入确认超时审批取消失败]\033[0m task_ref={task_ref} task_id={context.job.task_id} task_hash={context.job.task_hash} lease_version={approval_record.lease_version} 错误=approval_record missing or lease_version mismatch\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表里的待确认导入审批是否仍存在，或是否已被其他路径抢先取消/确认；当前 confirm 会直接返回状态读取失败，避免把审批真相缺口误判成普通“导入确认已超时”。",
                    flush=True,
                )
                return IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT
        if self._job_repo is not None and context.job.state == JOB_STATE_PENDING_APPROVAL:
            try:
                cancelled = self._job_repo.cancel_pending_job(
                    job_id=context.job.job_id,
                    expected_version=context.job.version,
                    workflow_type=WORKFLOW_IMPORT_TO_LIBRARY,
                )
                if cancelled is None:
                    raise RuntimeError(IMPORT_CANCEL_PENDING_JOB_RESULT_MISSING_REASON)
            except Exception as error:
                if str(error) in {
                    IMPORT_CANCEL_PENDING_JOB_RESULT_MISSING_REASON,
                    IMPORT_CANCEL_PENDING_JOB_ROW_MISSING_REASON,
                }:
                    self._log_expired_cancel_pending_job_result_missing(
                        job=context.job,
                        task_ref=task_ref,
                        reason=str(error),
                    )
                else:
                    print(
                        f"\033[31m[导入确认超时任务取消失败]\033[0m task_ref={task_ref} job_id={context.job.job_id} task_id={context.job.task_id} task_hash={context.job.task_hash} version={context.job.version} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表更新是否正常；当前 confirm 会直接返回状态读取失败，避免把任务真相缺口误判成普通“导入确认已超时”。",
                        flush=True,
                    )
                return IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT
            else:
                if not cancelled:
                    print(
                        f"\033[31m[导入确认超时任务取消失败]\033[0m task_ref={task_ref} job_id={context.job.job_id} task_id={context.job.task_id} task_hash={context.job.task_hash} version={context.job.version} 错误=jobs.cancel_pending_job rejected current state\n\033[33m[处理建议]\033[0m 检查该任务是否已被其他路径抢先取消、确认或完结；当前 confirm 会直接返回状态读取失败，避免把任务状态迁移冲突误判成普通“导入确认已超时”。",
                        flush=True,
                    )
                    return IMPORT_CONFIRM_STATE_UNAVAILABLE_TEXT
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
            if str(error) == IMPORT_EVENT_RESULT_MISSING_REASON:
                print(
                    f"\033[31m[导入事件结果缺失]\033[0m task_ref={task_ref} task_id={task_id} task_hash={task_hash} event_type={event_type} source={source_path} target={target_path} 错误=import event missing after append\n\033[33m[处理建议]\033[0m 检查 job_event 写入后回读是否仍能拿到刚追加的导入事件；当前导入流程会继续执行，但这次事件真相还没有确认落稳。",
                    flush=True,
                )
            elif _is_import_event_row_corrupted_error(error):
                print(
                    f"\033[31m[导入事件记录损坏]\033[0m task_ref={task_ref} task_id={task_id} task_hash={task_hash} event_type={event_type} source={source_path} target={target_path} 错误={error}\n\033[33m[处理建议]\033[0m 检查 job_event 读回事件里的 task_ref / event_type / source_path / target_path 等真相字段是否仍然完整；当前导入流程会继续执行，但不会把这条坏事件当成已稳定落盘。",
                    flush=True,
                )
            else:
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


def _is_job_row_corrupted_error(error: Exception) -> bool:
    return isinstance(error, JobPersistenceError) and str(error).endswith("corrupted after read")


def _is_import_event_row_corrupted_error(error: Exception) -> bool:
    return isinstance(error, JobEventPersistenceError) and str(error).endswith("corrupted after read")


def _is_import_target_lookup_row_corrupted_error(error: Exception) -> bool:
    return isinstance(error, JobEventPersistenceError) and str(error).endswith("corrupted after read")

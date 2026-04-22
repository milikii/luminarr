from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from app.clients.transmission import TransmissionTask
from app.db.approval_repo import (
    APPROVAL_STATUS_PENDING,
    DEFAULT_PENDING_TIMEOUT_SECONDS,
    ApprovalRecord,
    ApprovalRepo,
)
from app.db.download_monitor_repo import DownloadMonitorRepo
from app.db.job_event_repo import JobEventRepo
from app.db.job_repo import JOB_STATE_PENDING_APPROVAL, JobRecord, JobRepo, WORKFLOW_ADD_TO_DOWNLOADER
from app.runtime.delivery import DeliveryAction, DeliveryHeader, DeliveryItem, DeliverySection, render_delivery_item
from app.services.add_pending_context import (
    CANDIDATE_SOURCE_MISSING_TEXT,
    SELECT_LOOKUP_FAILED_TEXT,
    SELECT_NOT_FOUND_TEXT,
    SELECT_OUT_OF_RANGE_TEXT,
    SELECT_USAGE_TEXT,
    AddPendingContextBuilder,
    PendingAddContext,
    pending_add_from_json,
    pending_add_to_json,
    to_completed_pending_add_context,
)
from app.services.add_execution_follow_up import AddExecutionFollowUpService
from app.services.search_media import SearchMediaService
from app.trace_logging import log_trace_event

AddTorrentFunc = Callable[..., Awaitable[TransmissionTask]]

ADD_FAILED_TEXT = "下载投递失败，请稍后重试。"
ADD_PENDING_STATE_UNAVAILABLE_TEXT = "下载待确认状态写入失败，请稍后重试。"
ADD_APPROVAL_PENDING_TEXT = (
    "下载待确认：{title}\n"
    "选择序号: {task_ref}\n"
    "请发送 confirm {task_ref} 执行下载。"
)
ADD_CANCELLED_TEXT = "已取消当前下载确认。请重新发送序号。"
ADD_CANCEL_STATE_UNAVAILABLE_TEXT = "下载取消状态读取失败，请稍后重试。"
ADD_CONFIRM_NOT_PENDING_TEXT = "没有待确认的下载请求，请先重新发送序号。"
ADD_CONFIRM_EXPIRED_TEXT = "下载确认已超时，请重新发送序号。"
ADD_CONFIRM_STATE_UNAVAILABLE_TEXT = "下载确认状态读取失败，请稍后重试。"
ADD_FINALIZATION_WARNING_TEXT = (
    "注意：下载已执行，但状态回写失败，请勿重复 confirm。\n"
    "请稍后用 status 查询任务状态，或检查 SQLite/approval_record 与 jobs 表。"
)
DOWNLOADER_PENDING_JOB_RESULT_MISSING_REASON = "job missing after pending upsert"
DOWNLOADER_PENDING_JOB_NONE_REASON = "downloader pending job result missing"
DOWNLOADER_CANCEL_PENDING_JOB_RESULT_MISSING_REASON = "downloader cancel pending job result missing"
DOWNLOADER_CANCEL_PENDING_JOB_ROW_MISSING_REASON = "job missing during cancel"
DOWNLOADER_CANCEL_APPROVAL_RESULT_MISSING_REASON = "approval_record missing during cancel"
DOWNLOADER_CANCEL_APPROVAL_NONE_REASON = "downloader cancel approval result missing"
DOWNLOADER_RESTORE_PENDING_APPROVAL_RESULT_MISSING_REASON = "downloader restore pending approval result missing"
DOWNLOADER_RESTORE_PENDING_APPROVAL_ROW_MISSING_REASON = "approval_record missing during restore"
DOWNLOAD_MONITOR_REGISTER_RESULT_MISSING_REASON = "download monitor state missing after register"
DOWNLOADER_PENDING_APPROVAL_RESULT_MISSING_REASON = "approval_record missing after pending request"
DOWNLOADER_PENDING_APPROVAL_NONE_REASON = "downloader pending approval result missing"
DOWNLOADER_PENDING_APPROVAL_ROW_CORRUPTED_REASON = "approval row lease version corrupted after read"
DOWNLOADER_APPROVE_RESULT_MISSING_REASON = "approval_record missing during approve"
DOWNLOADER_APPROVE_RESULT_NONE_REASON = "downloader approval result missing"
DOWNLOADER_CLAIM_PENDING_JOB_RESULT_MISSING_REASON = "job missing during lease claim"
DOWNLOADER_PENDING_EXPIRY_RESULT_MISSING_REASON = "approval_record missing during pending expiry check"
DOWNLOADER_EXECUTED_LEASE_RESULT_MISSING_REASON = "approval_record missing during executed version update"
DOWNLOADER_RESTORE_PENDING_JOB_RESULT_MISSING_REASON = "job missing during state transition"
DOWNLOADER_MARK_COMPLETED_JOB_RESULT_MISSING_REASON = "downloader completed job result missing"
CONFIRM_QUERY_USAGE_TEXT = "确认格式：confirm <任务ID或Hash>"
BT_SOURCE_UNSUPPORTED_TEXT = "当前 BT 执行只支持直接 magnet:? 链接，请重新发送磁力链接后重试。"
JOB_LEASE_OWNER = "downloader_confirm"
PENDING_LEASE_LOOKUP_FAILED = -1
DOWNLOADER_CONFIRM_CONTEXT_JOB_ROW_CORRUPTED_REASONS = frozenset(
    {
        "job row identity corrupted after read",
        "job row chat identity corrupted after read",
        "job row user identity corrupted after read",
        "job row version corrupted after read",
    }
)
APPROVAL_ROW_CORRUPTED_REASONS = frozenset(
    {
        "approval row identity corrupted after read",
        "approval row status corrupted after read",
        "approval row lease version corrupted after read",
        "approval row executed version corrupted after read",
    }
)
SUPPORTED_DELIVERY_CHANNELS = frozenset({"telegram", "feishu", "personal_wechat", "wecom"})
@dataclass(frozen=True, slots=True)
class ConfirmExecutionContext:
    job: JobRecord
    approval_record: ApprovalRecord | None
    pending_add: PendingAddContext
    approval_lookup_failed: bool = False


class AddToDownloaderService:
    def __init__(
        self,
        search_service: SearchMediaService,
        add_torrent_func: AddTorrentFunc,
        approval_repo: ApprovalRepo | None = None,
        job_repo: JobRepo | None = None,
        job_event_repo: JobEventRepo | None = None,
        download_monitor_repo: DownloadMonitorRepo | None = None,
        trace_log_path: Path | None = None,
    ) -> None:
        self._search_service = search_service
        self._add_torrent_func = add_torrent_func
        self._approval_repo = approval_repo
        self._job_repo = job_repo
        self._job_event_repo = job_event_repo
        self._download_monitor_repo = download_monitor_repo
        self._trace_log_path = trace_log_path
        self._pending_context_builder = AddPendingContextBuilder(search_service)
        self._pending_add_identities: set[tuple[str, str]] = set()
        self._pending_add_lease_versions: dict[tuple[str, str], int] = {}
        self._pending_add_contexts_by_chat_ref: dict[tuple[int, str], PendingAddContext] = {}
        self._latest_pending_task_ref_by_chat: dict[int, str] = {}
        self._execution_follow_up = AddExecutionFollowUpService(
            add_torrent_func=add_torrent_func,
            job_event_repo=job_event_repo,
            download_monitor_repo=download_monitor_repo,
            log_trace_func=self._log_trace,
            add_failed_text=ADD_FAILED_TEXT,
            download_monitor_register_result_missing_reason=DOWNLOAD_MONITOR_REGISTER_RESULT_MISSING_REASON,
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
            workflow=WORKFLOW_ADD_TO_DOWNLOADER,
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

    async def add_by_selection(
        self,
        chat_id: int,
        selection_text: str,
        *,
        user_id: int | None = None,
        channel: str | None = None,
        downloader_name: str = "",
        downloader_type: str = "transmission",
        download_dir: str = "",
        auto_import_enabled: bool = True,
    ) -> str:
        build_result = self._pending_context_builder.build_from_selection(
            chat_id=chat_id,
            selection_text=selection_text,
            downloader_name=downloader_name,
            downloader_type=downloader_type,
            download_dir=download_dir,
            auto_import_enabled=auto_import_enabled,
        )
        if build_result.pending_add is None:
            return build_result.error_text
        return self._persist_pending_add(
            chat_id=chat_id,
            user_id=user_id,
            pending_add=build_result.pending_add,
            channel=channel,
        )

    async def add_by_batch_selection(
        self,
        chat_id: int,
        selection_indexes: tuple[int, ...],
        *,
        user_id: int | None = None,
        channel: str | None = None,
        downloader_name: str = "",
        downloader_type: str = "transmission",
        download_dir: str = "",
        auto_import_enabled: bool = True,
    ) -> str:
        pending_adds: list[PendingAddContext] = []
        for index in selection_indexes:
            build_result = self._pending_context_builder.build_from_selection(
                chat_id=chat_id,
                selection_text=str(index),
                downloader_name=downloader_name,
                downloader_type=downloader_type,
                download_dir=download_dir,
                auto_import_enabled=auto_import_enabled,
            )
            if build_result.pending_add is None:
                return build_result.error_text
            pending_adds.append(build_result.pending_add)

        replies: list[str] = []
        for pending_add in pending_adds:
            replies.append(
                self._persist_pending_add(
                    chat_id=chat_id,
                    user_id=user_id,
                    pending_add=pending_add,
                    channel=channel,
                )
            )
        return "\n\n".join(replies)

    async def add_bt_source(
        self,
        *,
        chat_id: int,
        source: str,
        title: str,
        user_id: int | None = None,
        channel: str | None = None,
        downloader_name: str = "",
        downloader_type: str = "transmission",
        download_dir: str = "",
        auto_import_enabled: bool = True,
    ) -> str:
        cleaned_source = source.strip()
        if not cleaned_source.lower().startswith("magnet:?"):
            return BT_SOURCE_UNSUPPORTED_TEXT

        return await self.add_candidate_source(
            chat_id=chat_id,
            source=cleaned_source,
            title=title,
            user_id=user_id,
            channel=channel,
            downloader_name=downloader_name,
            downloader_type=downloader_type,
            download_dir=download_dir,
            auto_import_enabled=auto_import_enabled,
        )

    async def add_candidate_source(
        self,
        *,
        chat_id: int,
        source: str,
        title: str,
        user_id: int | None = None,
        channel: str | None = None,
        downloader_name: str = "",
        downloader_type: str = "transmission",
        download_dir: str = "",
        auto_import_enabled: bool = True,
    ) -> str:
        build_result = self._pending_context_builder.build_from_source(
            source=source,
            title=title,
            downloader_name=downloader_name,
            downloader_type=downloader_type,
            download_dir=download_dir,
            auto_import_enabled=auto_import_enabled,
        )
        if build_result.pending_add is None:
            return build_result.error_text
        return self._persist_pending_add(
            chat_id=chat_id,
            user_id=user_id,
            pending_add=build_result.pending_add,
            channel=channel,
        )

    async def confirm_add_by_task_ref(
        self,
        task_ref: str,
        *,
        chat_id: int | None = None,
        user_id: int | None = None,
    ) -> str:
        cleaned_ref = task_ref.strip()
        if not cleaned_ref:
            return CONFIRM_QUERY_USAGE_TEXT

        confirm_context, confirm_context_unavailable = self._rebuild_confirm_context(
            task_ref=cleaned_ref,
            chat_id=chat_id,
        )
        if confirm_context is None:
            if confirm_context_unavailable:
                return ADD_CONFIRM_STATE_UNAVAILABLE_TEXT
            in_memory_pending = self._get_in_memory_pending(chat_id=chat_id, task_ref=cleaned_ref)
            if in_memory_pending is None:
                return ADD_CONFIRM_NOT_PENDING_TEXT
            if self._job_repo is not None and chat_id is not None and chat_id > 0:
                self._log_pending_job_result_missing(
                    chat_id=chat_id,
                    task_ref=cleaned_ref,
                    task_id=in_memory_pending.task_id,
                    task_hash=in_memory_pending.task_hash,
                    stage="confirm",
                )
                return ADD_CONFIRM_STATE_UNAVAILABLE_TEXT
        else:
            if confirm_context.approval_lookup_failed:
                return ADD_CONFIRM_STATE_UNAVAILABLE_TEXT
            if confirm_context.job.state != JOB_STATE_PENDING_APPROVAL:
                stale_text = self._find_version_stale_rejection_text(
                    task_id=confirm_context.pending_add.task_id,
                    task_hash=confirm_context.pending_add.task_hash,
                )
                return stale_text or ADD_CONFIRM_NOT_PENDING_TEXT
            if (
                confirm_context.approval_record is None
                or confirm_context.approval_record.status != APPROVAL_STATUS_PENDING
            ):
                stale_text = self._find_version_stale_rejection_text(
                    task_id=confirm_context.pending_add.task_id,
                    task_hash=confirm_context.pending_add.task_hash,
                )
                return stale_text or ADD_CONFIRM_NOT_PENDING_TEXT
            expired_text = self._handle_expired_pending_confirm(
                task_ref=cleaned_ref,
                context=confirm_context,
                chat_id=chat_id,
            )
            if expired_text is not None:
                return expired_text

        claimed_job = False
        claimed_job_id = ""
        claimed_job_version = 0
        lease_owner = ""
        pending_add = confirm_context.pending_add if confirm_context is not None else in_memory_pending
        assert pending_add is not None

        if confirm_context is not None:
            lease_owner = self._build_job_lease_owner(cleaned_ref)
            claimed_job = self._claim_pending_job(job=confirm_context.job, lease_owner=lease_owner)
            if claimed_job is None:
                return ADD_CONFIRM_STATE_UNAVAILABLE_TEXT
            if not claimed_job:
                stale_text = self._find_version_stale_rejection_text(
                    task_id=pending_add.task_id,
                    task_hash=pending_add.task_hash,
                )
                return stale_text or ADD_CONFIRM_NOT_PENDING_TEXT
            claimed_job_id = confirm_context.job.job_id
            claimed_job_version = confirm_context.job.version

        stale_text = self._find_version_stale_rejection_text(
            task_id=pending_add.task_id,
            task_hash=pending_add.task_hash,
        )
        if stale_text is not None:
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
                task_id=pending_add.task_id,
                task_hash=pending_add.task_hash,
                allow_in_memory_fallback_on_error=False,
            )
        if expected_lease_version == PENDING_LEASE_LOOKUP_FAILED:
            if claimed_job:
                self._restore_pending_job(
                    job_id=claimed_job_id,
                    expected_version=claimed_job_version,
                    lease_owner=lease_owner,
                )
            return ADD_CONFIRM_STATE_UNAVAILABLE_TEXT
        if expected_lease_version <= 0:
            if claimed_job:
                self._restore_pending_job(
                    job_id=claimed_job_id,
                    expected_version=claimed_job_version,
                    lease_owner=lease_owner,
                )
            return ADD_CONFIRM_NOT_PENDING_TEXT

        approved = self._record_downloader_approval(
            task_ref=cleaned_ref,
            task_id=pending_add.task_id,
            task_hash=pending_add.task_hash,
            expected_lease_version=expected_lease_version,
        )
        if approved is None:
            if claimed_job:
                self._restore_pending_job(
                    job_id=claimed_job_id,
                    expected_version=claimed_job_version,
                    lease_owner=lease_owner,
                )
            return ADD_CONFIRM_STATE_UNAVAILABLE_TEXT
        if not approved:
            if claimed_job:
                self._restore_pending_job(
                    job_id=claimed_job_id,
                    expected_version=claimed_job_version,
                    lease_owner=lease_owner,
                )
            stale_text = self._find_version_stale_rejection_text(
                task_id=pending_add.task_id,
                task_hash=pending_add.task_hash,
            )
            return stale_text or ADD_CONFIRM_NOT_PENDING_TEXT

        self._record_event(
            task_ref=cleaned_ref,
            task_id=pending_add.task_id,
            task_hash=pending_add.task_hash,
            event_type="downloader.approval_confirmed",
            message=pending_add.title,
        )

        execution = await self._execution_follow_up.dispatch(
            task_ref=cleaned_ref,
            pending_add=pending_add,
            chat_id=chat_id,
            user_id=user_id,
        )
        if execution.result is None:
            approval_restored = self._restore_pending_approval(
                task_ref=cleaned_ref,
                task_id=pending_add.task_id,
                task_hash=pending_add.task_hash,
                expected_lease_version=expected_lease_version,
            )
            if claimed_job:
                self._restore_pending_job(
                    job_id=claimed_job_id,
                    expected_version=claimed_job_version,
                    lease_owner=lease_owner,
                )
            if approval_restored is not True:
                return ADD_CONFIRM_STATE_UNAVAILABLE_TEXT
            return execution.reply
        result = execution.result
        reply = execution.reply
        finalization_warning = ""
        lease_recorded = self._record_executed_lease_version(
            task_ref=cleaned_ref,
            task_id=pending_add.task_id,
            task_hash=pending_add.task_hash,
            executed_lease_version=expected_lease_version,
        )
        if lease_recorded is not True:
            finalization_warning = ADD_FINALIZATION_WARNING_TEXT
        approval_identity_moved = self._move_completed_approval_identity(
            current_task_id=pending_add.task_id,
            current_task_hash=pending_add.task_hash,
            new_task_id=pending_add.task_id,
            new_task_hash=result.task_hash,
        )
        if approval_identity_moved is not True:
            finalization_warning = ADD_FINALIZATION_WARNING_TEXT
        if claimed_job:
            completed_context = to_completed_pending_add_context(
                pending_add,
                actual_task_id=pending_add.task_id,
                actual_task_hash=result.task_hash,
            )
            job_completed = self._mark_completed_job(
                job_id=claimed_job_id,
                expected_version=claimed_job_version,
                lease_owner=lease_owner,
                completed_add=completed_context,
            )
            if job_completed is not True:
                finalization_warning = ADD_FINALIZATION_WARNING_TEXT
        self._clear_pending_context(chat_id=chat_id, task_ref=cleaned_ref)
        if finalization_warning:
            self._log_trace(
                event="confirm_finalize",
                result="warning",
                stage="completed",
                chat_id=chat_id,
                user_id=user_id,
                task_ref=cleaned_ref,
                task_id=result.task_id,
                task_hash=result.task_hash,
                detail=ADD_FINALIZATION_WARNING_TEXT,
            )
            return f"{reply}\n\n{finalization_warning}"
        self._log_trace(
            event="confirm_finalize",
            result="succeeded",
            stage="completed",
            chat_id=chat_id,
            user_id=user_id,
            task_ref=cleaned_ref,
            task_id=result.task_id,
            task_hash=result.task_hash,
            detail=result.title,
        )
        return reply

    def has_pending_add(self, chat_id: int, task_ref: str) -> bool | None:
        cleaned_ref = task_ref.strip()
        if chat_id <= 0 or not cleaned_ref:
            return False
        in_memory_pending = self._get_in_memory_pending(chat_id=chat_id, task_ref=cleaned_ref)
        if self._job_repo is not None:
            try:
                job = self._job_repo.get_downloader_job_for_chat_ref(chat_id=chat_id, task_ref=cleaned_ref)
            except Exception as error:
                print(
                    f"\033[31m[下载待确认查询失败]\033[0m chat_id={chat_id} task_ref={cleaned_ref} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表查询是否正常；若当前进程里也没有待确认上下文，这次请求会直接返回服务未就绪，避免把持久化异常误判成“没有待确认下载”。",
                    flush=True,
                )
                return True if in_memory_pending is not None else None
            if job is not None and job.state == JOB_STATE_PENDING_APPROVAL:
                return True
            if in_memory_pending is not None:
                self._log_pending_job_result_missing(
                    chat_id=chat_id,
                    task_ref=cleaned_ref,
                    task_id=in_memory_pending.task_id,
                    task_hash=in_memory_pending.task_hash,
                    stage="lookup",
                )
                return None
        return in_memory_pending is not None

    def cancel_pending_add(self, chat_id: int) -> str | None:
        if chat_id <= 0:
            return None

        pending_job: JobRecord | None = None
        pending_lookup_failed = False
        if self._job_repo is not None:
            try:
                pending_job = self._job_repo.get_latest_pending_downloader_job(chat_id=chat_id)
            except Exception as error:
                print(
                    f"\033[31m[下载取消查询失败]\033[0m chat_id={chat_id} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表查询是否正常；若当前进程里也没有待确认上下文，当前取消会直接返回状态读取失败，避免把持久化异常误判成“没有待取消下载”。",
                    flush=True,
                )
                pending_job = None
                pending_lookup_failed = True

        if pending_job is None:
            task_ref = self._latest_pending_task_ref_by_chat.get(chat_id, "").strip()
            if not task_ref:
                if pending_lookup_failed:
                    return ADD_CANCEL_STATE_UNAVAILABLE_TEXT
                return None
            pending_add = self._pending_add_contexts_by_chat_ref.get((chat_id, task_ref))
            if pending_add is None:
                if pending_lookup_failed:
                    return ADD_CANCEL_STATE_UNAVAILABLE_TEXT
                return None
            if pending_lookup_failed:
                return ADD_CANCEL_STATE_UNAVAILABLE_TEXT
            if self._job_repo is not None:
                self._log_pending_job_result_missing(
                    chat_id=chat_id,
                    task_ref=task_ref,
                    task_id=pending_add.task_id,
                    task_hash=pending_add.task_hash,
                    stage="cancel",
                )
                return ADD_CANCEL_STATE_UNAVAILABLE_TEXT
            expected_lease_version = self._resolve_pending_lease_version(
                task_id=pending_add.task_id,
                task_hash=pending_add.task_hash,
                allow_in_memory_fallback_on_error=False,
            )
            if expected_lease_version == PENDING_LEASE_LOOKUP_FAILED:
                self._log_cancel_state_unavailable(
                    task_ref=task_ref,
                    task_id=pending_add.task_id,
                    task_hash=pending_add.task_hash,
                    reason="downloader approval pending lease lookup failed",
                )
                return ADD_CANCEL_STATE_UNAVAILABLE_TEXT
            if expected_lease_version <= 0:
                self._log_cancel_state_unavailable(
                    task_ref=task_ref,
                    task_id=pending_add.task_id,
                    task_hash=pending_add.task_hash,
                    reason="downloader approval pending lease missing",
                )
                return ADD_CANCEL_STATE_UNAVAILABLE_TEXT
            approval_cancelled = self._cancel_pending_approval(
                task_ref=task_ref,
                task_id=pending_add.task_id,
                task_hash=pending_add.task_hash,
                expected_lease_version=expected_lease_version,
            )
            if not approval_cancelled:
                return ADD_CANCEL_STATE_UNAVAILABLE_TEXT
            self._clear_pending_context(chat_id=chat_id, task_ref=task_ref)
            self._record_event(
                task_ref=task_ref,
                task_id=pending_add.task_id,
                task_hash=pending_add.task_hash,
                event_type="downloader.cancelled",
                message=ADD_CANCELLED_TEXT,
            )
            return ADD_CANCELLED_TEXT

        pending_add, payload_problem = pending_add_from_json(pending_job.payload_json)
        if pending_add is None:
            print(
                f"\033[31m[下载取消载荷损坏]\033[0m chat_id={chat_id} task_ref={pending_job.task_ref} job_id={pending_job.job_id} task_id={pending_job.task_id} task_hash={pending_job.task_hash} 载荷={payload_problem or 'unknown'}\n\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表里的 payload_json 是否仍是完整待确认下载上下文；当前取消会直接返回状态读取失败，避免把持久化坏数据误判成“没有待取消下载”。",
                flush=True,
            )
            return ADD_CANCEL_STATE_UNAVAILABLE_TEXT

        expected_lease_version = self._resolve_pending_lease_version(
            task_id=pending_job.task_id,
            task_hash=pending_job.task_hash,
            allow_in_memory_fallback_on_error=False,
        )
        if expected_lease_version == PENDING_LEASE_LOOKUP_FAILED:
            self._log_cancel_state_unavailable(
                task_ref=pending_job.task_ref,
                task_id=pending_job.task_id,
                task_hash=pending_job.task_hash,
                reason="downloader approval pending lease lookup failed",
            )
            return ADD_CANCEL_STATE_UNAVAILABLE_TEXT
        if expected_lease_version <= 0:
            self._log_cancel_state_unavailable(
                task_ref=pending_job.task_ref,
                task_id=pending_job.task_id,
                task_hash=pending_job.task_hash,
                reason="downloader approval pending lease missing",
            )
            return ADD_CANCEL_STATE_UNAVAILABLE_TEXT

        approval_cancelled = self._cancel_pending_approval(
            task_ref=pending_job.task_ref,
            task_id=pending_job.task_id,
            task_hash=pending_job.task_hash,
            expected_lease_version=expected_lease_version,
        )
        if not approval_cancelled:
            return ADD_CANCEL_STATE_UNAVAILABLE_TEXT
        try:
            cancelled = self._job_repo.cancel_pending_job(
                job_id=pending_job.job_id,
                expected_version=pending_job.version,
                workflow_type=WORKFLOW_ADD_TO_DOWNLOADER,
            )
            if cancelled is None:
                raise RuntimeError(DOWNLOADER_CANCEL_PENDING_JOB_RESULT_MISSING_REASON)
        except Exception as error:
            if str(error) in {
                DOWNLOADER_CANCEL_PENDING_JOB_RESULT_MISSING_REASON,
                DOWNLOADER_CANCEL_PENDING_JOB_ROW_MISSING_REASON,
            }:
                self._log_cancel_pending_job_result_missing(pending_job=pending_job, reason=str(error))
            else:
                print(
                    f"\033[31m[下载取消任务更新失败]\033[0m task_ref={pending_job.task_ref} job_id={pending_job.job_id} task_id={pending_job.task_id} task_hash={pending_job.task_hash} version={pending_job.version} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表更新是否正常；当前审批可能已取消，但任务真相可能仍残留在待确认状态。",
                    flush=True,
                )
            return ADD_CANCEL_STATE_UNAVAILABLE_TEXT
        if not cancelled:
            print(
                f"\033[31m[下载取消任务更新失败]\033[0m task_ref={pending_job.task_ref} job_id={pending_job.job_id} task_id={pending_job.task_id} task_hash={pending_job.task_hash} version={pending_job.version} 错误=jobs.cancel_pending_job rejected current state\n\033[33m[处理建议]\033[0m 检查该任务是否已被其他路径抢先取消、确认或完结；当前审批可能已取消，但待确认任务真相可能已被其他状态迁移抢先改写。",
                flush=True,
            )
            return ADD_CANCEL_STATE_UNAVAILABLE_TEXT
        self._clear_pending_context(chat_id=chat_id, task_ref=pending_job.task_ref)
        self._record_event(
            task_ref=pending_job.task_ref,
            task_id=pending_job.task_id,
            task_hash=pending_job.task_hash,
            event_type="downloader.cancelled",
            message=ADD_CANCELLED_TEXT,
        )
        return ADD_CANCELLED_TEXT

    def _record_pending_approval(self, *, task_ref: str, task_id: str, task_hash: str) -> int:
        identity = (task_id.strip(), task_hash.strip())
        if not identity[0] or not identity[1]:
            return 0

        in_memory_next_lease = self._pending_add_lease_versions.get(identity, 0) + 1
        lease_version = in_memory_next_lease

        if self._approval_repo is None:
            self._pending_add_lease_versions[identity] = lease_version
            self._pending_add_identities.add(identity)
            return lease_version
        try:
            requested_lease = self._approval_repo.request_downloader_approval(
                task_id=task_id,
                task_hash=task_hash,
                task_ref=task_ref,
                timeout_seconds=DEFAULT_PENDING_TIMEOUT_SECONDS,
            )
            if type(requested_lease) is not int or requested_lease <= 0:
                raise RuntimeError(DOWNLOADER_PENDING_APPROVAL_NONE_REASON)
            lease_version = requested_lease
        except Exception as error:
            if str(error) in {
                DOWNLOADER_PENDING_APPROVAL_RESULT_MISSING_REASON,
                DOWNLOADER_PENDING_APPROVAL_NONE_REASON,
            }:
                print(
                    f"\033[31m[下载待确认审批结果缺失]\033[0m task_ref={task_ref} task_id={task_id} task_hash={task_hash} 错误={error}\n"
                    "\033[33m[处理建议]\033[0m 检查 approval_record 写入后回读是否仍能拿到当前待确认审批的 lease_version；"
                    "当前请求会直接返回待确认状态写入失败，避免把缺失真相误报成可确认下载。",
                    flush=True,
                )
            elif str(error) == DOWNLOADER_PENDING_APPROVAL_ROW_CORRUPTED_REASON:
                print(
                    f"\033[31m[下载待确认审批记录损坏]\033[0m task_ref={task_ref} task_id={task_id} task_hash={task_hash} 错误={error}\n"
                    "\033[33m[处理建议]\033[0m 检查 approval_record.lease_version 是否仍是正整数真相；"
                    "当前请求会直接返回待确认状态写入失败，避免把坏审批记录误报成可确认下载。",
                    flush=True,
                )
            else:
                print(
                    f"\033[31m[下载待确认审批落盘失败]\033[0m task_ref={task_ref} task_id={task_id} task_hash={task_hash} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表写入是否正常；当前请求会直接返回待确认状态写入失败，避免把审批真相缺口误报成可确认下载。",
                    flush=True,
                )
            return 0

        self._pending_add_lease_versions[identity] = lease_version
        self._pending_add_identities.add(identity)
        return lease_version

    def _record_downloader_approval(
        self,
        *,
        task_ref: str,
        task_id: str,
        task_hash: str,
        expected_lease_version: int,
    ) -> bool | None:
        identity = (task_id.strip(), task_hash.strip())
        if not identity[0] or not identity[1] or expected_lease_version <= 0:
            return False

        if self._approval_repo is None:
            current_lease = self._pending_add_lease_versions.get(identity, 0)
            if identity not in self._pending_add_identities or current_lease != expected_lease_version:
                return False
            self._pending_add_identities.remove(identity)
            return True

        approved = False
        try:
            approved = self._approval_repo.approve_downloader(
                task_id=task_id,
                task_hash=task_hash,
                task_ref=task_ref,
                expected_lease_version=expected_lease_version,
            )
            if approved is None:
                raise RuntimeError(DOWNLOADER_APPROVE_RESULT_NONE_REASON)
        except Exception as error:
            if str(error) in {
                DOWNLOADER_APPROVE_RESULT_MISSING_REASON,
                DOWNLOADER_APPROVE_RESULT_NONE_REASON,
            }:
                print(
                    f"\033[31m[下载确认审批结果缺失]\033[0m task_ref={task_ref} task_id={task_id} task_hash={task_hash} lease_version={expected_lease_version} 错误={error}\n"
                    "\033[33m[处理建议]\033[0m 检查 approval_record 表里该待确认下载审批是否仍存在，以及审批更新后是否还能回读到该行；"
                    "当前 confirm 会直接返回状态读取失败，避免把缺失真相误判成普通已确认或普通状态冲突。",
                    flush=True,
                )
                return None
            print(
                f"\033[31m[下载确认审批更新失败]\033[0m task_ref={task_ref} task_id={task_id} task_hash={task_hash} lease_version={expected_lease_version} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表更新是否正常；当前 confirm 会直接返回状态读取失败，避免把审批真相更新失败误判成下载已确认。",
                flush=True,
            )
            return None
        if not approved:
            print(
                f"\033[31m[下载确认审批更新失败]\033[0m task_ref={task_ref} task_id={task_id} task_hash={task_hash} lease_version={expected_lease_version} 错误=approval_record approve rejected current state\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表里的待确认下载审批是否仍存在、lease_version 是否匹配；当前 confirm 会按 not pending 处理，避免把审批真相状态冲突误判成已确认。",
                flush=True,
            )
            return False

        if approved and identity in self._pending_add_identities:
            self._pending_add_identities.remove(identity)
        return approved

    def _restore_pending_approval(
        self,
        *,
        task_ref: str,
        task_id: str,
        task_hash: str,
        expected_lease_version: int,
    ) -> bool | None:
        identity = (task_id.strip(), task_hash.strip())
        if not identity[0] or not identity[1] or expected_lease_version <= 0:
            return False
        self._pending_add_identities.add(identity)
        self._pending_add_lease_versions[identity] = expected_lease_version
        if self._approval_repo is None:
            return True
        try:
            restored = self._approval_repo.restore_downloader_pending(
                task_id=task_id,
                task_hash=task_hash,
                task_ref=task_ref,
                expected_lease_version=expected_lease_version,
            )
            if restored is None:
                raise RuntimeError(DOWNLOADER_RESTORE_PENDING_APPROVAL_RESULT_MISSING_REASON)
        except Exception as error:
            if str(error) in {
                DOWNLOADER_RESTORE_PENDING_APPROVAL_RESULT_MISSING_REASON,
                DOWNLOADER_RESTORE_PENDING_APPROVAL_ROW_MISSING_REASON,
            }:
                print(
                    f"\033[31m[下载审批回退结果缺失]\033[0m task_ref={task_ref} task_id={task_id} task_hash={task_hash} lease_version={expected_lease_version} 原因={error}\n\033[33m[处理建议]\033[0m 检查 approval_record 回退后是否还能立即回读到 pending 审批真相；当前进程内待确认身份已回退，但持久化审批状态还没有确认回退成功。",
                    flush=True,
                )
            else:
                print(
                    f"\033[31m[下载审批回退失败]\033[0m task_ref={task_ref} task_id={task_id} task_hash={task_hash} lease_version={expected_lease_version} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表更新是否正常；当前进程内待确认身份已回退，但重启后审批状态可能不一致。",
                    flush=True,
                )
            return None
        if restored is False:
            print(
                f"\033[31m[下载审批回退失败]\033[0m task_ref={task_ref} task_id={task_id} task_hash={task_hash} lease_version={expected_lease_version} 错误=approval_record restore rejected current state\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表里的审批行是否仍存在、lease_version 是否匹配；当前进程内待确认身份已回退，但重启后审批状态可能不一致。",
                flush=True,
            )
            return False
        return True

    def _cancel_pending_approval(
        self,
        *,
        task_ref: str,
        task_id: str,
        task_hash: str,
        expected_lease_version: int,
    ) -> bool:
        identity = (task_id.strip(), task_hash.strip())
        if not identity[0] or not identity[1] or expected_lease_version <= 0:
            return False

        self._pending_add_identities.discard(identity)
        if self._approval_repo is None:
            return True
        try:
            cancelled = self._approval_repo.cancel_downloader(
                task_id=task_id,
                task_hash=task_hash,
                task_ref=task_ref,
                expected_lease_version=expected_lease_version,
            )
            if cancelled is None:
                raise RuntimeError(DOWNLOADER_CANCEL_APPROVAL_NONE_REASON)
        except Exception as error:
            self._pending_add_identities.add(identity)
            if str(error) in {
                DOWNLOADER_CANCEL_APPROVAL_RESULT_MISSING_REASON,
                DOWNLOADER_CANCEL_APPROVAL_NONE_REASON,
            }:
                print(
                    f"\033[31m[下载取消审批结果缺失]\033[0m task_ref={task_ref} task_id={task_id} task_hash={task_hash} lease_version={expected_lease_version} 错误={error}\n"
                    "\033[33m[处理建议]\033[0m 检查 approval_record 表里该待确认下载审批是否仍存在，以及取消更新后是否还能回读到该行；"
                    "当前取消会直接返回状态读取失败，避免把缺失真相误判成普通状态冲突或普通“没有待取消下载”。",
                    flush=True,
                )
                return False
            print(
                f"\033[31m[下载取消审批更新失败]\033[0m task_ref={task_ref} task_id={task_id} task_hash={task_hash} lease_version={expected_lease_version} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表更新是否正常；当前取消会直接失败返回，待确认状态可能仍残留。",
                flush=True,
            )
            return False
        if not cancelled:
            self._pending_add_identities.add(identity)
            print(
                f"\033[31m[下载取消审批更新失败]\033[0m task_ref={task_ref} task_id={task_id} task_hash={task_hash} lease_version={expected_lease_version} 错误=approval_record missing or lease_version mismatch\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表里的待确认下载审批是否仍存在，或是否已被其他路径抢先取消/确认；当前取消会直接返回状态读取失败，避免把审批真相缺口误判成“没有待取消下载”。",
                flush=True,
            )
            return False
        return True

    def _log_cancel_state_unavailable(
        self,
        *,
        task_ref: str,
        task_id: str,
        task_hash: str,
        reason: str,
    ) -> None:
        print(
            f"\033[31m[下载取消状态读取失败]\033[0m task_ref={task_ref} task_id={task_id} task_hash={task_hash} 原因={reason}\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表里的待确认下载审批是否仍存在；当前取消会直接返回状态读取失败，避免把审批真相缺口误判成“没有待取消下载”。",
            flush=True,
        )

    def _log_cancel_pending_job_result_missing(self, *, pending_job: JobRecord, reason: str) -> None:
        print(
            f"\033[31m[下载取消任务结果缺失]\033[0m task_ref={pending_job.task_ref} job_id={pending_job.job_id} task_id={pending_job.task_id} task_hash={pending_job.task_hash} version={pending_job.version} 原因={reason}\n\033[33m[处理建议]\033[0m 检查 jobs 表里该待确认任务是否仍存在，以及取消更新后是否还能回读到最新状态；当前审批可能已取消，但任务真相还没有确认取消成功。",
            flush=True,
        )

    def _log_expired_cancel_pending_job_result_missing(self, *, job: JobRecord, task_ref: str, reason: str) -> None:
        print(
            f"\033[31m[下载确认超时任务结果缺失]\033[0m task_ref={task_ref} job_id={job.job_id} task_id={job.task_id} task_hash={job.task_hash} version={job.version} 原因={reason}\n\033[33m[处理建议]\033[0m 检查 jobs 表里该待确认任务是否仍存在，以及超时取消后是否还能回读到最新状态；当前 confirm 会直接返回状态读取失败，避免把缺失真相误判成普通“下载确认已超时”。",
            flush=True,
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
        identity = (task_id.strip(), task_hash.strip())
        if not identity[0] or not identity[1] or executed_lease_version <= 0:
            return False
        self._pending_add_lease_versions[identity] = executed_lease_version
        if self._approval_repo is None:
            return True
        try:
            self._approval_repo.mark_downloader_executed(
                task_id=task_id,
                task_hash=task_hash,
                executed_lease_version=executed_lease_version,
            )
        except Exception as error:
            if str(error) == DOWNLOADER_EXECUTED_LEASE_RESULT_MISSING_REASON:
                print(
                    f"\033[31m[下载执行版号结果缺失]\033[0m task_id={task_id} task_hash={task_hash} lease_version={executed_lease_version} 错误={error}\n"
                    "\033[33m[处理建议]\033[0m 检查 approval_record 更新后该审批行是否仍存在，并确认 executed_version 已被正确回写；"
                    "当前进程内 lease 版本已前进，但持久化真相还没有确认落稳。",
                    flush=True,
                )
            elif str(error) in APPROVAL_ROW_CORRUPTED_REASONS:
                print(
                    f"\033[31m[下载执行版号记录损坏]\033[0m task_id={task_id} task_hash={task_hash} lease_version={executed_lease_version} 错误={error}\n"
                    "\033[33m[处理建议]\033[0m 检查 approval_record 里的 lease_version / executed_version 等字段是否仍是完整真相；"
                    "当前进程内 lease 版本已前进，但不会把坏审批记录当成已稳定回写。",
                    flush=True,
                )
            else:
                print(
                    f"\033[31m[下载执行版号回写失败]\033[0m task_id={task_id} task_hash={task_hash} lease_version={executed_lease_version} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表更新是否正常；当前进程内 lease 版本已前进，但持久化真相可能仍停留在旧值。",
                    flush=True,
                )
            return None
        return True

    def _record_pending_context(self, *, chat_id: int, pending_add: PendingAddContext) -> None:
        if chat_id <= 0:
            return
        key = (chat_id, pending_add.task_ref)
        self._pending_add_contexts_by_chat_ref[key] = pending_add
        self._latest_pending_task_ref_by_chat[chat_id] = pending_add.task_ref

    def _move_completed_approval_identity(
        self,
        *,
        current_task_id: str,
        current_task_hash: str,
        new_task_id: str,
        new_task_hash: str,
    ) -> bool | None:
        if self._approval_repo is None:
            return True
        try:
            self._approval_repo.move_downloader_approval_identity(
                current_task_id=current_task_id,
                current_task_hash=current_task_hash,
                new_task_id=new_task_id,
                new_task_hash=new_task_hash,
            )
        except Exception as error:
            print(
                f"\033[31m[下载审批身份迁移失败]\033[0m current_task_id={current_task_id} current_task_hash={current_task_hash} new_task_id={new_task_id} new_task_hash={new_task_hash} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表里的下载审批是否仍存在，并确认 confirm 后审批主键已切到真实下载任务身份；当前下载已执行，但重启后的 stale confirm 保护可能不稳。",
                flush=True,
            )
            return None
        return True

    def _persist_pending_add(
        self,
        *,
        chat_id: int,
        user_id: int | None,
        pending_add: PendingAddContext,
        channel: str | None = None,
    ) -> str:
        expected_lease_version = self._record_pending_approval(
            task_ref=pending_add.task_ref,
            task_id=pending_add.task_id,
            task_hash=pending_add.task_hash,
        )
        if expected_lease_version <= 0:
            return ADD_PENDING_STATE_UNAVAILABLE_TEXT
        self._record_pending_context(chat_id=chat_id, pending_add=pending_add)
        if not self._record_pending_job(chat_id=chat_id, user_id=user_id, pending_add=pending_add):
            self._clear_pending_context(chat_id=chat_id, task_ref=pending_add.task_ref)
            self._cancel_pending_approval(
                task_ref=pending_add.task_ref,
                task_id=pending_add.task_id,
                task_hash=pending_add.task_hash,
                expected_lease_version=expected_lease_version,
            )
            return ADD_PENDING_STATE_UNAVAILABLE_TEXT
        self._record_event(
            task_ref=pending_add.task_ref,
            task_id=pending_add.task_id,
            task_hash=pending_add.task_hash,
            event_type="downloader.approval_pending",
            message=pending_add.title,
        )
        self._log_trace(
            event="approval_pending",
            result="created",
            stage="pending",
            chat_id=chat_id,
            user_id=user_id,
            task_ref=pending_add.task_ref,
            task_id=pending_add.task_id,
            task_hash=pending_add.task_hash,
            detail=pending_add.title,
        )
        if channel in SUPPORTED_DELIVERY_CHANNELS:
            return render_add_pending_reply(pending_add=pending_add, channel=channel)
        return ADD_APPROVAL_PENDING_TEXT.format(title=pending_add.title, task_ref=pending_add.task_ref)

    def _record_pending_job(
        self,
        *,
        chat_id: int,
        user_id: int | None,
        pending_add: PendingAddContext,
    ) -> bool:
        if self._job_repo is None:
            return True
        try:
            pending_job = self._job_repo.upsert_downloader_job_pending(
                chat_id=chat_id,
                user_id=user_id,
                task_ref=pending_add.task_ref,
                task_id=pending_add.task_id,
                task_hash=pending_add.task_hash,
                payload_json=pending_add_to_json(pending_add),
            )
            if pending_job is None:
                raise RuntimeError(DOWNLOADER_PENDING_JOB_NONE_REASON)
        except Exception as error:
            if str(error) in {
                DOWNLOADER_PENDING_JOB_RESULT_MISSING_REASON,
                DOWNLOADER_PENDING_JOB_NONE_REASON,
            }:
                print(
                    f"\033[31m[下载待确认任务结果缺失]\033[0m chat_id={chat_id} user_id={user_id} task_ref={pending_add.task_ref} task_id={pending_add.task_id} task_hash={pending_add.task_hash} 错误={error}\n\033[33m[处理建议]\033[0m 检查 jobs 写入后回读是否仍能拿到刚创建的待确认任务；当前请求会直接返回待确认状态写入失败，避免把缺失真相误报成可确认下载。",
                    flush=True,
                )
            elif str(error) in DOWNLOADER_CONFIRM_CONTEXT_JOB_ROW_CORRUPTED_REASONS:
                print(
                    f"\033[31m[下载待确认任务记录损坏]\033[0m chat_id={chat_id} user_id={user_id} task_ref={pending_add.task_ref} task_id={pending_add.task_id} task_hash={pending_add.task_hash} 错误={error}\n\033[33m[处理建议]\033[0m 检查 jobs 新写入待确认任务里的 job_id / chat_id / user_id / version 等字段是否仍是完整真相；当前请求会直接返回待确认状态写入失败，避免把坏任务记录误报成可确认下载。",
                    flush=True,
                )
            else:
                print(
                    f"\033[31m[下载待确认任务落盘失败]\033[0m chat_id={chat_id} user_id={user_id} task_ref={pending_add.task_ref} task_id={pending_add.task_id} task_hash={pending_add.task_hash} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表写入是否正常；当前请求会直接返回待确认状态写入失败，避免把待确认任务真相缺口误报成可确认下载。",
                    flush=True,
                )
            return False
        return True

    def _rebuild_confirm_context(
        self,
        *,
        task_ref: str,
        chat_id: int | None,
    ) -> tuple[ConfirmExecutionContext | None, bool]:
        if self._job_repo is None or chat_id is None or chat_id <= 0:
            return None, False
        try:
            job = self._job_repo.get_downloader_job_for_chat_ref(chat_id=chat_id, task_ref=task_ref)
        except Exception as error:
            if str(error) in DOWNLOADER_CONFIRM_CONTEXT_JOB_ROW_CORRUPTED_REASONS:
                print(
                    f"\033[31m[下载确认上下文记录损坏]\033[0m chat_id={chat_id} task_ref={task_ref} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表里该待确认下载任务的 job_id / chat_id / task_id / task_hash / version 是否仍是完整真相；当前 confirm 会直接返回状态读取失败，避免把坏记录误判成“没有待确认下载”。",
                    flush=True,
                )
            else:
                print(
                    f"\033[31m[下载确认上下文查询失败]\033[0m chat_id={chat_id} task_ref={task_ref} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表查询是否正常；当前 confirm 会直接返回状态读取失败，避免把持久化异常误判成“没有待确认下载”。",
                    flush=True,
                )
            return None, True
        if job is None:
            return None, False

        pending_add, payload_problem = pending_add_from_json(job.payload_json)
        if pending_add is None:
            print(
                f"\033[31m[下载确认上下文载荷损坏]\033[0m chat_id={chat_id} task_ref={task_ref} task_id={job.task_id} task_hash={job.task_hash} 载荷={payload_problem or 'unknown'}\n\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表里的 payload_json 是否仍是完整待确认下载上下文；若当前进程里也没有待确认上下文，当前 confirm 会直接返回状态读取失败，避免把持久化坏数据误判成“没有待确认下载”。",
                flush=True,
            )
            return None, True

        approval_record: ApprovalRecord | None = None
        approval_lookup_failed = False
        if self._approval_repo is not None:
            try:
                approval_record = self._approval_repo.get_downloader_approval(
                    task_id=job.task_id,
                    task_hash=job.task_hash,
                )
            except Exception as error:
                print(
                    f"\033[31m[下载确认审批查询失败]\033[0m task_ref={task_ref} task_id={job.task_id} task_hash={job.task_hash} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表查询是否正常；当前 confirm 会直接返回状态读取失败，避免把审批真相缺口误判成普通未确认状态。",
                    flush=True,
                )
                approval_record = None
                approval_lookup_failed = True
        return (
            ConfirmExecutionContext(
                job=job,
                approval_record=approval_record,
                pending_add=pending_add,
                approval_lookup_failed=approval_lookup_failed,
            ),
            False,
        )

    def _get_in_memory_pending(self, *, chat_id: int | None, task_ref: str) -> PendingAddContext | None:
        if chat_id is None or chat_id <= 0:
            return None
        return self._pending_add_contexts_by_chat_ref.get((chat_id, task_ref))

    def _log_pending_job_result_missing(
        self,
        *,
        chat_id: int,
        task_ref: str,
        task_id: str,
        task_hash: str,
        stage: str,
    ) -> None:
        if stage == "confirm":
            suggestion = (
                "检查 SQLite/jobs 表里的待确认下载任务是否仍存在；当前 confirm 会直接返回状态读取失败，"
                "避免把进程内残留上下文误判成仍可确认下载。"
            )
        elif stage == "cancel":
            suggestion = (
                "检查 SQLite/jobs 表里的待确认下载任务是否仍存在；当前取消会直接返回状态读取失败，"
                "避免把进程内残留上下文误判成仍可取消下载。"
            )
        else:
            suggestion = (
                "检查 SQLite/jobs 表里的待确认下载任务是否仍存在；当前入口会直接返回服务未就绪，"
                "避免把进程内残留上下文误判成普通仍有待确认下载。"
            )
        print(
            f"\033[31m[下载待确认任务结果缺失]\033[0m chat_id={chat_id} task_ref={task_ref} "
            f"task_id={task_id} task_hash={task_hash} 错误=jobs pending row missing while in-memory pending exists\n"
            f"\033[33m[处理建议]\033[0m {suggestion}",
            flush=True,
        )

    def _clear_pending_context(self, *, chat_id: int | None, task_ref: str) -> None:
        if chat_id is None or chat_id <= 0:
            return
        key = (chat_id, task_ref)
        self._pending_add_contexts_by_chat_ref.pop(key, None)
        if self._latest_pending_task_ref_by_chat.get(chat_id) == task_ref:
            self._latest_pending_task_ref_by_chat.pop(chat_id, None)

    def _claim_pending_job(self, *, job: JobRecord, lease_owner: str) -> bool | None:
        if self._job_repo is None:
            return False
        try:
            claimed = self._job_repo.claim_lease(
                job_id=job.job_id,
                expected_version=job.version,
                lease_owner=lease_owner,
                workflow_type=WORKFLOW_ADD_TO_DOWNLOADER,
            )
        except Exception as error:
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
                workflow_type=WORKFLOW_ADD_TO_DOWNLOADER,
            )
        except Exception as error:
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

    def _mark_completed_job(
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
                raise RuntimeError(DOWNLOADER_MARK_COMPLETED_JOB_RESULT_MISSING_REASON)
        except Exception as error:
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
        identity = (task_id.strip(), task_hash.strip())
        if not identity[0] or not identity[1]:
            return 0
        if self._approval_repo is None:
            if identity not in self._pending_add_identities:
                return 0
            return self._pending_add_lease_versions.get(identity, 1)

        try:
            approval_record = self._approval_repo.get_downloader_approval(task_id=task_id, task_hash=task_hash)
        except Exception as error:
            print(
                f"\033[31m[下载待确认版号查询失败]\033[0m task_id={task_id} task_hash={task_hash} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表查询是否正常；当前调用会按状态读取失败处理，避免把持久化真相异常继续混成进程内版号兜底。",
                flush=True,
            )
            if not allow_in_memory_fallback_on_error:
                return PENDING_LEASE_LOOKUP_FAILED
            if identity not in self._pending_add_identities:
                return 0
            return self._pending_add_lease_versions.get(identity, 1)
        if approval_record is None:
            if identity in self._pending_add_identities:
                print(
                    f"\033[31m[下载待确认版号查询失败]\033[0m task_id={task_id} task_hash={task_hash} 错误=approval_record missing while in-memory pending exists\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表里的待确认下载审批是否仍存在；当前调用会按状态读取失败处理，避免把审批真相缺口继续混成进程内版号兜底。",
                    flush=True,
                )
                if not allow_in_memory_fallback_on_error:
                    return PENDING_LEASE_LOOKUP_FAILED
                return self._pending_add_lease_versions.get(identity, 1)
            if identity not in self._pending_add_identities:
                return 0
            return self._pending_add_lease_versions.get(identity, 1)
        if approval_record.status != APPROVAL_STATUS_PENDING:
            return 0
        return max(0, approval_record.lease_version)

    def _find_version_stale_rejection_text(self, *, task_id: str, task_hash: str) -> str | None:
        if self._approval_repo is None:
            return None
        try:
            approval_record = self._approval_repo.get_downloader_approval(task_id=task_id, task_hash=task_hash)
        except Exception as error:
            if str(error) in APPROVAL_ROW_CORRUPTED_REASONS:
                print(
                    f"\033[31m[下载确认执行版号记录损坏]\033[0m task_id={task_id} task_hash={task_hash} 错误={error}\n\033[33m[处理建议]\033[0m 检查 approval_record 里的 status / lease_version / executed_version 等字段是否仍是完整真相；当前 confirm 会直接返回状态读取失败，避免把坏审批记录误判成普通没有待确认下载。",
                    flush=True,
                )
            else:
                print(
                    f"\033[31m[下载确认执行版号查询失败]\033[0m task_id={task_id} task_hash={task_hash} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表查询是否正常；当前 confirm 会直接返回状态读取失败，避免把持久化异常误判成普通没有待确认下载。",
                    flush=True,
                )
            return ADD_CONFIRM_STATE_UNAVAILABLE_TEXT
        if approval_record is None:
            print(
                f"\033[31m[下载确认执行版号查询失败]\033[0m task_id={task_id} task_hash={task_hash} 错误=approval_record missing during stale check\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表里的待确认下载审批是否仍存在；当前 confirm 会直接返回状态读取失败，避免把审批真相缺口误判成普通没有待确认下载。",
                flush=True,
            )
            return ADD_CONFIRM_STATE_UNAVAILABLE_TEXT
        if approval_record.lease_version <= 0:
            return None
        if approval_record.executed_version < approval_record.lease_version:
            return None
        return ADD_CONFIRM_NOT_PENDING_TEXT

    def _handle_expired_pending_confirm(
        self,
        *,
        task_ref: str,
        context: ConfirmExecutionContext,
        chat_id: int | None,
    ) -> str | None:
        approval_record = context.approval_record
        if approval_record is None:
            return None
        approval_expired = self._is_pending_approval_expired(
            task_id=context.pending_add.task_id,
            task_hash=context.pending_add.task_hash,
            expected_lease_version=approval_record.lease_version,
        )
        if approval_expired is None:
            return ADD_CONFIRM_STATE_UNAVAILABLE_TEXT
        if not approval_expired:
            return None
        approval_cancelled = self._cancel_pending_approval(
            task_ref=task_ref,
            task_id=context.pending_add.task_id,
            task_hash=context.pending_add.task_hash,
            expected_lease_version=approval_record.lease_version,
        )
        if not approval_cancelled:
            return ADD_CONFIRM_STATE_UNAVAILABLE_TEXT
        if self._job_repo is not None and context.job.state == JOB_STATE_PENDING_APPROVAL:
            try:
                cancelled = self._job_repo.cancel_pending_job(
                    job_id=context.job.job_id,
                    expected_version=context.job.version,
                    workflow_type=WORKFLOW_ADD_TO_DOWNLOADER,
                )
                if cancelled is None:
                    raise RuntimeError(DOWNLOADER_CANCEL_PENDING_JOB_RESULT_MISSING_REASON)
            except Exception as error:
                if str(error) in {
                    DOWNLOADER_CANCEL_PENDING_JOB_RESULT_MISSING_REASON,
                    DOWNLOADER_CANCEL_PENDING_JOB_ROW_MISSING_REASON,
                }:
                    self._log_expired_cancel_pending_job_result_missing(
                        job=context.job,
                        task_ref=task_ref,
                        reason=str(error),
                    )
                else:
                    print(
                        f"\033[31m[下载确认超时任务取消失败]\033[0m task_ref={task_ref} job_id={context.job.job_id} task_id={context.job.task_id} task_hash={context.job.task_hash} version={context.job.version} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表更新是否正常；当前 confirm 会直接返回状态读取失败，避免把任务真相缺口误判成普通“下载确认已超时”。",
                        flush=True,
                    )
                return ADD_CONFIRM_STATE_UNAVAILABLE_TEXT
            else:
                if not cancelled:
                    print(
                        f"\033[31m[下载确认超时任务取消失败]\033[0m task_ref={task_ref} job_id={context.job.job_id} task_id={context.job.task_id} task_hash={context.job.task_hash} version={context.job.version} 错误=jobs.cancel_pending_job rejected current state\n\033[33m[处理建议]\033[0m 检查该任务是否已被其他路径抢先取消、确认或完结；当前 confirm 会直接返回状态读取失败，避免把任务状态迁移冲突误判成普通“下载确认已超时”。",
                        flush=True,
                    )
                    return ADD_CONFIRM_STATE_UNAVAILABLE_TEXT
        self._clear_pending_context(chat_id=chat_id, task_ref=task_ref)
        self._record_event(
            task_ref=task_ref,
            task_id=context.pending_add.task_id,
            task_hash=context.pending_add.task_hash,
            event_type="downloader.approval_expired",
            message=ADD_CONFIRM_EXPIRED_TEXT,
        )
        return ADD_CONFIRM_EXPIRED_TEXT

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
            return self._approval_repo.is_downloader_pending_expired(
                task_id=task_id,
                task_hash=task_hash,
                expected_lease_version=expected_lease_version,
            )
        except Exception as error:
            if str(error) == DOWNLOADER_PENDING_EXPIRY_RESULT_MISSING_REASON:
                print(
                    f"\033[31m[下载确认过期结果缺失]\033[0m task_id={task_id} task_hash={task_hash} lease_version={expected_lease_version} 错误={error}\n"
                    "\033[33m[处理建议]\033[0m 检查 approval_record 表里的待确认下载审批是否仍存在，并确认对应 lease_version 没有被其他路径抢先改写；"
                    "当前 confirm 会直接返回状态读取失败，避免把审批真相缺口误判成普通“未过期”。",
                    flush=True,
                )
            elif str(error) in APPROVAL_ROW_CORRUPTED_REASONS:
                print(
                    f"\033[31m[下载确认过期审批记录损坏]\033[0m task_id={task_id} task_hash={task_hash} lease_version={expected_lease_version} 错误={error}\n"
                    "\033[33m[处理建议]\033[0m 检查 approval_record 里的 status / lease_version / executed_version 等字段是否仍是完整真相；"
                    "当前 confirm 会直接返回状态读取失败，避免把坏审批记录误判成普通“未过期”。",
                    flush=True,
                )
            else:
                print(
                    f"\033[31m[下载确认过期判断失败]\033[0m task_id={task_id} task_hash={task_hash} lease_version={expected_lease_version} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表查询是否正常；当前 confirm 会直接返回状态读取失败，避免把持久化异常误判成“未过期”。",
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
    ) -> None:
        self._execution_follow_up.record_event(
            task_ref=task_ref,
            task_id=task_id,
            task_hash=task_hash,
            event_type=event_type,
            message=message,
        )

    def _register_download_monitor(
        self,
        *,
        task_id: str,
        task_hash: str,
        title: str,
        chat_id: int | None,
        user_id: int | None,
    ) -> None:
        self._execution_follow_up.register_download_monitor(
            task_id=task_id,
            task_hash=task_hash,
            title=title,
            chat_id=chat_id,
            user_id=user_id,
        )


def render_add_pending_reply(*, pending_add: PendingAddContext, channel: str) -> str:
    return render_delivery_item(build_add_pending_delivery_item(pending_add), channel=channel)


def build_add_pending_delivery_item(pending_add: PendingAddContext) -> DeliveryItem:
    expire_minutes = max(1, DEFAULT_PENDING_TIMEOUT_SECONDS // 60)
    return DeliveryItem(
        header=DeliveryHeader(kind="approval", title="待确认：下载"),
        sections=(
            DeliverySection(
                label="任务信息",
                lines=(
                    f"片名：{pending_add.title}",
                    f"选择序号：{pending_add.task_ref}",
                ),
            ),
        ),
        actions=(
            DeliveryAction(label="确认下载", hint=f"发送 confirm {pending_add.task_ref}", kind="primary"),
            DeliveryAction(label="取消下载", hint=f"发送 cancel {pending_add.task_ref}", kind="secondary"),
        ),
        footer=f"过期时间：{expire_minutes} 分钟后",
        status="pending",
    )

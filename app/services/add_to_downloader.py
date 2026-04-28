from __future__ import annotations

import sqlite3
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path

from app.clients.transmission import TransmissionTask
from app.db.adult_content_registry_repo import AdultContentRegistryRepo
from app.db.approval_repo import (
    APPROVAL_STATUS_PENDING,
    DEFAULT_PENDING_TIMEOUT_SECONDS,
    ApprovalPersistenceError,
    ApprovalRepo,
)
from app.db.download_monitor_repo import DownloadMonitorRepo
from app.db.job_event_repo import JobEventRepo
from app.db.job_repo import JOB_STATE_PENDING_APPROVAL, JobPersistenceError, JobRecord, JobRepo
from app.operational_logging import emit_operational_log
from app.runtime.delivery import DeliveryAction, DeliveryHeader, DeliveryItem, DeliverySection, render_delivery_item
from app.services.add_adult_registry_state import AddAdultRegistryState
from app.services.add_confirm_context_state import AddConfirmContextState, ConfirmExecutionContext
from app.services.add_confirm_finalization_state import AddConfirmFinalizationState
from app.services.add_confirm_job_state import AddConfirmJobState
from app.services.add_cancel_state import AddCancelState
from app.services import add_pending_context
from app.services.add_pending_context import (
    AddPendingContextBuilder,
    AddPendingRuntimeState,
    PendingAddContext,
    pending_add_to_json,
)
from app.services.add_execution_follow_up import AddExecutionFollowUpService
from app.services.search_media import SearchMediaService
from app.services.workflow_trace_logger import WorkflowTraceLogger

AddTorrentFunc = Callable[..., Awaitable[TransmissionTask]]

CANDIDATE_SOURCE_MISSING_TEXT = add_pending_context.CANDIDATE_SOURCE_MISSING_TEXT
SELECT_LOOKUP_FAILED_TEXT = add_pending_context.SELECT_LOOKUP_FAILED_TEXT
SELECT_NOT_FOUND_TEXT = add_pending_context.SELECT_NOT_FOUND_TEXT
SELECT_OUT_OF_RANGE_TEXT = add_pending_context.SELECT_OUT_OF_RANGE_TEXT
SELECT_USAGE_TEXT = add_pending_context.SELECT_USAGE_TEXT
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
DOWNLOAD_MONITOR_REGISTER_RESULT_MISSING_REASON = "download monitor state missing after register"
CONFIRM_QUERY_USAGE_TEXT = "确认格式：confirm <任务ID或Hash>"
BT_SOURCE_UNSUPPORTED_TEXT = "当前 BT 执行只支持直接 magnet:? 链接，请重新发送磁力链接后重试。"
DOWNLOADER_CONFIRM_CONTEXT_JOB_ROW_CORRUPTED_REASONS = frozenset(
    {
        "job row identity corrupted after read",
        "job row chat identity corrupted after read",
        "job row user identity corrupted after read",
        "job row version corrupted after read",
    }
)
SUPPORTED_DELIVERY_CHANNELS = frozenset({"telegram", "feishu", "personal_wechat", "wecom"})


@dataclass(frozen=True, slots=True)
class ConfirmPreparationState:
    pending_add: PendingAddContext
    expected_lease_version: int
    claimed_job: bool
    claimed_job_id: str
    claimed_job_version: int
    lease_owner: str


@dataclass(frozen=True, slots=True)
class ConfirmAvailabilityResolution:
    confirm_context: ConfirmExecutionContext | None
    in_memory_pending: PendingAddContext | None


PENDING_LEASE_LOOKUP_FAILED = -1
DOWNLOADER_PENDING_EXPIRY_RESULT_MISSING_REASON = "approval_record missing during pending expiry check"
DOWNLOADER_PENDING_APPROVAL_RESULT_MISSING_REASON = "approval_record missing after pending request"
DOWNLOADER_PENDING_APPROVAL_NONE_REASON = "downloader pending approval result missing"
DOWNLOADER_PENDING_APPROVAL_ROW_CORRUPTED_REASON = "approval row lease version corrupted after read"
DOWNLOADER_APPROVE_RESULT_MISSING_REASON = "approval_record missing during approve"
DOWNLOADER_APPROVE_RESULT_NONE_REASON = "downloader approval result missing"
DOWNLOADER_CANCEL_APPROVAL_RESULT_MISSING_REASON = "approval_record missing during cancel"
DOWNLOADER_CANCEL_APPROVAL_NONE_REASON = "downloader cancel approval result missing"
DOWNLOADER_RESTORE_PENDING_APPROVAL_RESULT_MISSING_REASON = "downloader restore pending approval result missing"
DOWNLOADER_RESTORE_PENDING_APPROVAL_ROW_MISSING_REASON = "approval_record missing during restore"
DOWNLOADER_EXECUTED_LEASE_RESULT_MISSING_REASON = "approval_record missing during executed version update"
APPROVAL_ROW_CORRUPTED_REASONS = frozenset(
    {
        "approval row identity corrupted after read",
        "approval row status corrupted after read",
        "approval row lease version corrupted after read",
        "approval row executed version corrupted after read",
    }
)


@dataclass(slots=True)
class AddConfirmApprovalState:
    approval_repo: ApprovalRepo | None
    add_confirm_not_pending_text: str
    add_confirm_state_unavailable_text: str
    pending_add_identities: set[tuple[str, str]] = field(default_factory=set)
    pending_add_lease_versions: dict[tuple[str, str], int] = field(default_factory=dict)

    def resolve_pending_lease_version(
        self,
        *,
        task_id: str,
        task_hash: str,
        allow_in_memory_fallback_on_error: bool = True,
    ) -> int:
        identity = (task_id.strip(), task_hash.strip())
        if not identity[0] or not identity[1]:
            return 0
        if self.approval_repo is None:
            if identity not in self.pending_add_identities:
                return 0
            return self.pending_add_lease_versions.get(identity, 1)

        try:
            approval_record = self.approval_repo.get_downloader_approval(task_id=task_id, task_hash=task_hash)
        except (ApprovalPersistenceError, sqlite3.Error) as error:
            emit_operational_log(
                title="下载待确认版号查询失败",
                detail=f"task_id={task_id} task_hash={task_hash} 错误={error}",
                fix_hint="检查 SQLite/approval_record 表查询是否正常；当前调用会按状态读取失败处理，避免把持久化真相异常继续混成进程内版号兜底。",
            )
            if not allow_in_memory_fallback_on_error:
                return PENDING_LEASE_LOOKUP_FAILED
            if identity not in self.pending_add_identities:
                return 0
            return self.pending_add_lease_versions.get(identity, 1)
        if approval_record is None:
            if identity in self.pending_add_identities:
                emit_operational_log(
                    title="下载待确认版号查询失败",
                    detail=f"task_id={task_id} task_hash={task_hash} 错误=approval_record missing while in-memory pending exists",
                    fix_hint="检查 SQLite/approval_record 表里的待确认下载审批是否仍存在；当前调用会按状态读取失败处理，避免把审批真相缺口继续混成进程内版号兜底。",
                )
                if not allow_in_memory_fallback_on_error:
                    return PENDING_LEASE_LOOKUP_FAILED
                return self.pending_add_lease_versions.get(identity, 1)
            if identity not in self.pending_add_identities:
                return 0
            return self.pending_add_lease_versions.get(identity, 1)
        if approval_record.status != APPROVAL_STATUS_PENDING:
            return 0
        return max(0, approval_record.lease_version)

    def find_version_stale_rejection_text(self, *, task_id: str, task_hash: str) -> str | None:
        if self.approval_repo is None:
            return None
        try:
            approval_record = self.approval_repo.get_downloader_approval(task_id=task_id, task_hash=task_hash)
        except (ApprovalPersistenceError, sqlite3.Error) as error:
            if str(error) in APPROVAL_ROW_CORRUPTED_REASONS:
                emit_operational_log(
                    title="下载确认执行版号记录损坏",
                    detail=f"task_id={task_id} task_hash={task_hash} 错误={error}",
                    fix_hint="检查 approval_record 里的 status / lease_version / executed_version 等字段是否仍是完整真相；当前 confirm 会直接返回状态读取失败，避免把坏审批记录误判成普通没有待确认下载。",
                )
            else:
                emit_operational_log(
                    title="下载确认执行版号查询失败",
                    detail=f"task_id={task_id} task_hash={task_hash} 错误={error}",
                    fix_hint="检查 SQLite/approval_record 表查询是否正常；当前 confirm 会直接返回状态读取失败，避免把持久化异常误判成普通没有待确认下载。",
                )
            return self.add_confirm_state_unavailable_text
        if approval_record is None:
            emit_operational_log(
                title="下载确认执行版号查询失败",
                detail=f"task_id={task_id} task_hash={task_hash} 错误=approval_record missing during stale check",
                fix_hint="检查 SQLite/approval_record 表里的待确认下载审批是否仍存在；当前 confirm 会直接返回状态读取失败，避免把审批真相缺口误判成普通没有待确认下载。",
            )
            return self.add_confirm_state_unavailable_text
        if approval_record.lease_version <= 0:
            return None
        if approval_record.executed_version < approval_record.lease_version:
            return None
        return self.add_confirm_not_pending_text

    def is_pending_approval_expired(
        self,
        *,
        task_id: str,
        task_hash: str,
        expected_lease_version: int,
    ) -> bool | None:
        if self.approval_repo is None:
            return False
        try:
            return self.approval_repo.is_downloader_pending_expired(
                task_id=task_id,
                task_hash=task_hash,
                expected_lease_version=expected_lease_version,
            )
        except (ApprovalPersistenceError, sqlite3.Error) as error:
            if str(error) == DOWNLOADER_PENDING_EXPIRY_RESULT_MISSING_REASON:
                emit_operational_log(
                    title="下载确认过期结果缺失",
                    detail=f"task_id={task_id} task_hash={task_hash} lease_version={expected_lease_version} 错误={error}",
                    fix_hint="检查 approval_record 表里的待确认下载审批是否仍存在，并确认对应 lease_version 没有被其他路径抢先改写；当前 confirm 会直接返回状态读取失败，避免把审批真相缺口误判成普通“未过期”。",
                )
            elif str(error) in APPROVAL_ROW_CORRUPTED_REASONS:
                emit_operational_log(
                    title="下载确认过期审批记录损坏",
                    detail=f"task_id={task_id} task_hash={task_hash} lease_version={expected_lease_version} 错误={error}",
                    fix_hint="检查 approval_record 里的 status / lease_version / executed_version 等字段是否仍是完整真相；当前 confirm 会直接返回状态读取失败，避免把坏审批记录误判成普通“未过期”。",
                )
            else:
                emit_operational_log(
                    title="下载确认过期判断失败",
                    detail=f"task_id={task_id} task_hash={task_hash} lease_version={expected_lease_version} 错误={error}",
                    fix_hint="检查 SQLite/approval_record 表查询是否正常；当前 confirm 会直接返回状态读取失败，避免把持久化异常误判成“未过期”。",
                )
            return None

    def record_pending_approval(self, *, task_ref: str, task_id: str, task_hash: str) -> int:
        identity = (task_id.strip(), task_hash.strip())
        if not identity[0] or not identity[1]:
            return 0

        in_memory_next_lease = self.pending_add_lease_versions.get(identity, 0) + 1
        lease_version = in_memory_next_lease

        if self.approval_repo is None:
            self.pending_add_lease_versions[identity] = lease_version
            self.pending_add_identities.add(identity)
            return lease_version
        try:
            requested_lease = self.approval_repo.request_downloader_approval(
                task_id=task_id,
                task_hash=task_hash,
                task_ref=task_ref,
                timeout_seconds=DEFAULT_PENDING_TIMEOUT_SECONDS,
            )
            if type(requested_lease) is not int or requested_lease <= 0:
                raise ApprovalPersistenceError(DOWNLOADER_PENDING_APPROVAL_NONE_REASON)
            lease_version = requested_lease
        except (ApprovalPersistenceError, sqlite3.Error) as error:
            if str(error) in {
                DOWNLOADER_PENDING_APPROVAL_RESULT_MISSING_REASON,
                DOWNLOADER_PENDING_APPROVAL_NONE_REASON,
            }:
                emit_operational_log(
                    title="下载待确认审批结果缺失",
                    detail=f"task_ref={task_ref} task_id={task_id} task_hash={task_hash} 错误={error}",
                    fix_hint="检查 approval_record 写入后回读是否仍能拿到当前待确认审批的 lease_version；当前请求会直接返回待确认状态写入失败，避免把缺失真相误报成可确认下载。",
                )
            elif str(error) == DOWNLOADER_PENDING_APPROVAL_ROW_CORRUPTED_REASON:
                emit_operational_log(
                    title="下载待确认审批记录损坏",
                    detail=f"task_ref={task_ref} task_id={task_id} task_hash={task_hash} 错误={error}",
                    fix_hint="检查 approval_record.lease_version 是否仍是正整数真相；当前请求会直接返回待确认状态写入失败，避免把坏审批记录误报成可确认下载。",
                )
            else:
                emit_operational_log(
                    title="下载待确认审批落盘失败",
                    detail=f"task_ref={task_ref} task_id={task_id} task_hash={task_hash} 错误={error}",
                    fix_hint="检查 SQLite/approval_record 表写入是否正常；当前请求会直接返回待确认状态写入失败，避免把审批真相缺口误报成可确认下载。",
                )
            return 0

        self.pending_add_lease_versions[identity] = lease_version
        self.pending_add_identities.add(identity)
        return lease_version

    def record_downloader_approval(
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

        if self.approval_repo is None:
            current_lease = self.pending_add_lease_versions.get(identity, 0)
            if identity not in self.pending_add_identities or current_lease != expected_lease_version:
                return False
            self.pending_add_identities.remove(identity)
            return True

        try:
            approved = self.approval_repo.approve_downloader(
                task_id=task_id,
                task_hash=task_hash,
                task_ref=task_ref,
                expected_lease_version=expected_lease_version,
            )
            if approved is None:
                raise ApprovalPersistenceError(DOWNLOADER_APPROVE_RESULT_NONE_REASON)
        except (ApprovalPersistenceError, sqlite3.Error) as error:
            if str(error) in {
                DOWNLOADER_APPROVE_RESULT_MISSING_REASON,
                DOWNLOADER_APPROVE_RESULT_NONE_REASON,
            }:
                emit_operational_log(
                    title="下载确认审批结果缺失",
                    detail=f"task_ref={task_ref} task_id={task_id} task_hash={task_hash} lease_version={expected_lease_version} 错误={error}",
                    fix_hint="检查 approval_record 表里该待确认下载审批是否仍存在，以及审批更新后是否还能回读到该行；当前 confirm 会直接返回状态读取失败，避免把缺失真相误判成普通已确认或普通状态冲突。",
                )
                return None
            emit_operational_log(
                title="下载确认审批更新失败",
                detail=f"task_ref={task_ref} task_id={task_id} task_hash={task_hash} lease_version={expected_lease_version} 错误={error}",
                fix_hint="检查 SQLite/approval_record 表更新是否正常；当前 confirm 会直接返回状态读取失败，避免把审批真相更新失败误判成下载已确认。",
            )
            return None
        if not approved:
            emit_operational_log(
                title="下载确认审批更新失败",
                detail=f"task_ref={task_ref} task_id={task_id} task_hash={task_hash} lease_version={expected_lease_version} 错误=approval_record approve rejected current state",
                fix_hint="检查 SQLite/approval_record 表里的待确认下载审批是否仍存在、lease_version 是否匹配；当前 confirm 会按 not pending 处理，避免把审批真相状态冲突误判成已确认。",
            )
            return False

        if identity in self.pending_add_identities:
            self.pending_add_identities.remove(identity)
        return approved

    def restore_pending_approval(
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
        self.pending_add_identities.add(identity)
        self.pending_add_lease_versions[identity] = expected_lease_version
        if self.approval_repo is None:
            return True
        try:
            restored = self.approval_repo.restore_downloader_pending(
                task_id=task_id,
                task_hash=task_hash,
                task_ref=task_ref,
                expected_lease_version=expected_lease_version,
            )
            if restored is None:
                raise ApprovalPersistenceError(DOWNLOADER_RESTORE_PENDING_APPROVAL_RESULT_MISSING_REASON)
        except (ApprovalPersistenceError, sqlite3.Error) as error:
            if str(error) in {
                DOWNLOADER_RESTORE_PENDING_APPROVAL_RESULT_MISSING_REASON,
                DOWNLOADER_RESTORE_PENDING_APPROVAL_ROW_MISSING_REASON,
            }:
                emit_operational_log(
                    title="下载审批回退结果缺失",
                    detail=f"task_ref={task_ref} task_id={task_id} task_hash={task_hash} lease_version={expected_lease_version} 原因={error}",
                    fix_hint="检查 approval_record 回退后是否还能立即回读到 pending 审批真相；当前进程内待确认身份已回退，但持久化审批状态还没有确认回退成功。",
                )
            else:
                emit_operational_log(
                    title="下载审批回退失败",
                    detail=f"task_ref={task_ref} task_id={task_id} task_hash={task_hash} lease_version={expected_lease_version} 错误={error}",
                    fix_hint="检查 SQLite/approval_record 表更新是否正常；当前进程内待确认身份已回退，但重启后审批状态可能不一致。",
                )
            return None
        if restored is False:
            emit_operational_log(
                title="下载审批回退失败",
                detail=f"task_ref={task_ref} task_id={task_id} task_hash={task_hash} lease_version={expected_lease_version} 错误=approval_record restore rejected current state",
                fix_hint="检查 SQLite/approval_record 表里的审批行是否仍存在、lease_version 是否匹配；当前进程内待确认身份已回退，但重启后审批状态可能不一致。",
            )
            return False
        return True

    def cancel_pending_approval(
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

        self.pending_add_identities.discard(identity)
        if self.approval_repo is None:
            return True
        try:
            cancelled = self.approval_repo.cancel_downloader(
                task_id=task_id,
                task_hash=task_hash,
                task_ref=task_ref,
                expected_lease_version=expected_lease_version,
            )
            if cancelled is None:
                raise ApprovalPersistenceError(DOWNLOADER_CANCEL_APPROVAL_NONE_REASON)
        except (ApprovalPersistenceError, sqlite3.Error) as error:
            self.pending_add_identities.add(identity)
            if str(error) in {
                DOWNLOADER_CANCEL_APPROVAL_RESULT_MISSING_REASON,
                DOWNLOADER_CANCEL_APPROVAL_NONE_REASON,
            }:
                emit_operational_log(
                    title="下载取消审批结果缺失",
                    detail=f"task_ref={task_ref} task_id={task_id} task_hash={task_hash} lease_version={expected_lease_version} 错误={error}",
                    fix_hint="检查 approval_record 表里该待确认下载审批是否仍存在，以及取消更新后是否还能回读到该行；当前取消会直接返回状态读取失败，避免把缺失真相误判成普通状态冲突或普通“没有待取消下载”。",
                )
                return False
            emit_operational_log(
                title="下载取消审批更新失败",
                detail=f"task_ref={task_ref} task_id={task_id} task_hash={task_hash} lease_version={expected_lease_version} 错误={error}",
                fix_hint="检查 SQLite/approval_record 表更新是否正常；当前取消会直接失败返回，待确认状态可能仍残留。",
            )
            return False
        if not cancelled:
            self.pending_add_identities.add(identity)
            emit_operational_log(
                title="下载取消审批更新失败",
                detail=f"task_ref={task_ref} task_id={task_id} task_hash={task_hash} lease_version={expected_lease_version} 错误=approval_record missing or lease_version mismatch",
                fix_hint="检查 SQLite/approval_record 表里的待确认下载审批是否仍存在，或是否已被其他路径抢先取消/确认；当前取消会直接返回状态读取失败，避免把审批真相缺口误判成“没有待取消下载”。",
            )
            return False
        return True

    def record_executed_lease_version(
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
        self.pending_add_lease_versions[identity] = executed_lease_version
        if self.approval_repo is None:
            return True
        try:
            self.approval_repo.mark_downloader_executed(
                task_id=task_id,
                task_hash=task_hash,
                executed_lease_version=executed_lease_version,
            )
        except (ApprovalPersistenceError, sqlite3.Error) as error:
            if str(error) == DOWNLOADER_EXECUTED_LEASE_RESULT_MISSING_REASON:
                emit_operational_log(
                    title="下载执行版号结果缺失",
                    detail=f"task_id={task_id} task_hash={task_hash} lease_version={executed_lease_version} 错误={error}",
                    fix_hint="检查 approval_record 更新后该审批行是否仍存在，并确认 executed_version 已被正确回写；当前进程内 lease 版本已前进，但持久化真相还没有确认落稳。",
                )
            elif str(error) in APPROVAL_ROW_CORRUPTED_REASONS:
                emit_operational_log(
                    title="下载执行版号记录损坏",
                    detail=f"task_id={task_id} task_hash={task_hash} lease_version={executed_lease_version} 错误={error}",
                    fix_hint="检查 approval_record 里的 lease_version / executed_version 等字段是否仍是完整真相；当前进程内 lease 版本已前进，但不会把坏审批记录当成已稳定回写。",
                )
            else:
                emit_operational_log(
                    title="下载执行版号回写失败",
                    detail=f"task_id={task_id} task_hash={task_hash} lease_version={executed_lease_version} 错误={error}",
                    fix_hint="检查 SQLite/approval_record 表更新是否正常；当前进程内 lease 版本已前进，但持久化真相可能仍停留在旧值。",
                )
            return None
        return True

    def move_completed_approval_identity(
        self,
        *,
        current_task_id: str,
        current_task_hash: str,
        new_task_id: str,
        new_task_hash: str,
    ) -> bool | None:
        if self.approval_repo is None:
            return True
        try:
            self.approval_repo.move_downloader_approval_identity(
                current_task_id=current_task_id,
                current_task_hash=current_task_hash,
                new_task_id=new_task_id,
                new_task_hash=new_task_hash,
            )
        except (ApprovalPersistenceError, sqlite3.Error) as error:
            emit_operational_log(
                title="下载审批身份迁移失败",
                detail=f"current_task_id={current_task_id} current_task_hash={current_task_hash} new_task_id={new_task_id} new_task_hash={new_task_hash} 错误={error}",
                fix_hint="检查 SQLite/approval_record 表里的下载审批是否仍存在，并确认 confirm 后审批主键已切到真实下载任务身份；当前下载已执行，但重启后的 stale confirm 保护可能不稳。",
            )
            return None
        return True


class AddToDownloaderService:
    def __init__(
        self,
        search_service: SearchMediaService,
        add_torrent_func: AddTorrentFunc,
        approval_repo: ApprovalRepo | None = None,
        job_repo: JobRepo | None = None,
        job_event_repo: JobEventRepo | None = None,
        download_monitor_repo: DownloadMonitorRepo | None = None,
        adult_content_registry_repo: AdultContentRegistryRepo | None = None,
        trace_log_path: Path | None = None,
    ) -> None:
        self._search_service = search_service
        self._add_torrent_func = add_torrent_func
        self._approval_repo = approval_repo
        self._job_repo = job_repo
        self._job_event_repo = job_event_repo
        self._download_monitor_repo = download_monitor_repo
        self._trace_logger = WorkflowTraceLogger("add_to_downloader", trace_log_path)
        self._pending_context_builder = AddPendingContextBuilder(search_service)
        self._pending_runtime_state = AddPendingRuntimeState()
        self._adult_registry_state = AddAdultRegistryState(adult_content_registry_repo)
        self._confirm_approval_state = AddConfirmApprovalState(
            approval_repo=approval_repo,
            add_confirm_not_pending_text=ADD_CONFIRM_NOT_PENDING_TEXT,
            add_confirm_state_unavailable_text=ADD_CONFIRM_STATE_UNAVAILABLE_TEXT,
        )
        self._confirm_context_state = AddConfirmContextState(
            job_repo=job_repo,
            confirm_approval_state=self._confirm_approval_state,
            add_confirm_expired_text=ADD_CONFIRM_EXPIRED_TEXT,
            add_confirm_state_unavailable_text=ADD_CONFIRM_STATE_UNAVAILABLE_TEXT,
            job_row_corrupted_reasons=DOWNLOADER_CONFIRM_CONTEXT_JOB_ROW_CORRUPTED_REASONS,
            downloader_cancel_pending_job_result_missing_reason=DOWNLOADER_CANCEL_PENDING_JOB_RESULT_MISSING_REASON,
            downloader_cancel_pending_job_row_missing_reason=DOWNLOADER_CANCEL_PENDING_JOB_ROW_MISSING_REASON,
        )
        self._pending_add_identities = self._confirm_approval_state.pending_add_identities
        self._pending_add_lease_versions = self._confirm_approval_state.pending_add_lease_versions
        self._execution_follow_up = AddExecutionFollowUpService(
            add_torrent_func=add_torrent_func,
            job_event_repo=job_event_repo,
            download_monitor_repo=download_monitor_repo,
            adult_content_registry_repo=adult_content_registry_repo,
            log_trace_func=self._trace_logger.log,
            add_failed_text=ADD_FAILED_TEXT,
            download_monitor_register_result_missing_reason=DOWNLOAD_MONITOR_REGISTER_RESULT_MISSING_REASON,
        )
        self._confirm_finalization_state = AddConfirmFinalizationState(
            add_finalization_warning_text=ADD_FINALIZATION_WARNING_TEXT,
            log_trace_func=self._trace_logger.log,
        )
        self._confirm_job_state = AddConfirmJobState(job_repo=job_repo)
        self._cancel_state = AddCancelState(
            job_repo=job_repo,
            add_cancel_state_unavailable_text=ADD_CANCEL_STATE_UNAVAILABLE_TEXT,
            add_cancelled_text=ADD_CANCELLED_TEXT,
            pending_lease_lookup_failed=PENDING_LEASE_LOOKUP_FAILED,
            downloader_cancel_pending_job_result_missing_reason=DOWNLOADER_CANCEL_PENDING_JOB_RESULT_MISSING_REASON,
            downloader_cancel_pending_job_row_missing_reason=DOWNLOADER_CANCEL_PENDING_JOB_ROW_MISSING_REASON,
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
        pending_adds = []
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

        availability, rejection_text = self._resolve_confirm_availability(
            task_ref=cleaned_ref,
            chat_id=chat_id,
            job_repo_available=self._job_repo is not None,
            find_version_stale_rejection_text=self._find_version_stale_rejection_text,
            handle_expired_pending_confirm=self._handle_expired_pending_confirm,
        )
        if availability is None:
            assert rejection_text is not None
            return rejection_text

        preparation, rejection_text = self._prepare_confirm(
            task_ref=cleaned_ref,
            confirm_context=availability.confirm_context,
            in_memory_pending=availability.in_memory_pending,
            find_version_stale_rejection_text=self._find_version_stale_rejection_text,
            resolve_pending_lease_version=self._resolve_pending_lease_version,
            record_downloader_approval=self._record_downloader_approval,
        )
        if preparation is None:
            assert rejection_text is not None
            return rejection_text
        pending_add = preparation.pending_add

        return await self._run_confirm_execution_tail(
            task_ref=cleaned_ref,
            pending_add=pending_add,
            chat_id=chat_id,
            user_id=user_id,
            expected_lease_version=preparation.expected_lease_version,
            claimed_job=preparation.claimed_job,
            claimed_job_id=preparation.claimed_job_id,
            claimed_job_version=preparation.claimed_job_version,
            lease_owner=preparation.lease_owner,
        )

    def _prepare_confirm(
        self,
        *,
        task_ref: str,
        confirm_context: ConfirmExecutionContext | None,
        in_memory_pending: PendingAddContext | None,
        find_version_stale_rejection_text: Callable[..., str | None],
        resolve_pending_lease_version: Callable[..., int],
        record_downloader_approval: Callable[..., bool | None],
    ) -> tuple[ConfirmPreparationState | None, str | None]:
        claimed_job = False
        claimed_job_id = ""
        claimed_job_version = 0
        lease_owner = ""
        pending_add = confirm_context.pending_add if confirm_context is not None else in_memory_pending
        assert pending_add is not None

        if confirm_context is not None:
            lease_owner = self._build_job_lease_owner(task_ref)
            claimed_job = self._claim_pending_job(job=confirm_context.job, lease_owner=lease_owner)
            if claimed_job is None:
                return None, ADD_CONFIRM_STATE_UNAVAILABLE_TEXT
            if not claimed_job:
                stale_text = find_version_stale_rejection_text(
                    task_id=pending_add.task_id,
                    task_hash=pending_add.task_hash,
                )
                return None, stale_text or ADD_CONFIRM_NOT_PENDING_TEXT
            claimed_job_id = confirm_context.job.job_id
            claimed_job_version = confirm_context.job.version

        stale_text = find_version_stale_rejection_text(
            task_id=pending_add.task_id,
            task_hash=pending_add.task_hash,
        )
        if stale_text is not None:
            self._restore_claim_if_needed(
                claimed_job=claimed_job,
                claimed_job_id=claimed_job_id,
                claimed_job_version=claimed_job_version,
                lease_owner=lease_owner,
            )
            return None, stale_text

        expected_lease_version = 0
        if confirm_context is not None and confirm_context.approval_record is not None:
            expected_lease_version = max(0, confirm_context.approval_record.lease_version)
        if expected_lease_version <= 0:
            expected_lease_version = resolve_pending_lease_version(
                task_id=pending_add.task_id,
                task_hash=pending_add.task_hash,
                allow_in_memory_fallback_on_error=False,
            )
        if expected_lease_version == PENDING_LEASE_LOOKUP_FAILED:
            self._restore_claim_if_needed(
                claimed_job=claimed_job,
                claimed_job_id=claimed_job_id,
                claimed_job_version=claimed_job_version,
                lease_owner=lease_owner,
            )
            return None, ADD_CONFIRM_STATE_UNAVAILABLE_TEXT
        if expected_lease_version <= 0:
            self._restore_claim_if_needed(
                claimed_job=claimed_job,
                claimed_job_id=claimed_job_id,
                claimed_job_version=claimed_job_version,
                lease_owner=lease_owner,
            )
            return None, ADD_CONFIRM_NOT_PENDING_TEXT

        approved = record_downloader_approval(
            task_ref=task_ref,
            task_id=pending_add.task_id,
            task_hash=pending_add.task_hash,
            expected_lease_version=expected_lease_version,
        )
        if approved is None:
            self._restore_claim_if_needed(
                claimed_job=claimed_job,
                claimed_job_id=claimed_job_id,
                claimed_job_version=claimed_job_version,
                lease_owner=lease_owner,
            )
            return None, ADD_CONFIRM_STATE_UNAVAILABLE_TEXT
        if not approved:
            self._restore_claim_if_needed(
                claimed_job=claimed_job,
                claimed_job_id=claimed_job_id,
                claimed_job_version=claimed_job_version,
                lease_owner=lease_owner,
            )
            stale_text = find_version_stale_rejection_text(
                task_id=pending_add.task_id,
                task_hash=pending_add.task_hash,
            )
            return None, stale_text or ADD_CONFIRM_NOT_PENDING_TEXT

        return (
            ConfirmPreparationState(
                pending_add=pending_add,
                expected_lease_version=expected_lease_version,
                claimed_job=claimed_job,
                claimed_job_id=claimed_job_id,
                claimed_job_version=claimed_job_version,
                lease_owner=lease_owner,
            ),
            None,
        )

    def _restore_claim_if_needed(
        self,
        *,
        claimed_job: bool,
        claimed_job_id: str,
        claimed_job_version: int,
        lease_owner: str,
    ) -> None:
        if not claimed_job:
            return
        self._restore_pending_job(
            job_id=claimed_job_id,
            expected_version=claimed_job_version,
            lease_owner=lease_owner,
        )

    def _resolve_confirm_availability(
        self,
        *,
        task_ref: str,
        chat_id: int | None,
        job_repo_available: bool,
        find_version_stale_rejection_text: Callable[..., str | None],
        handle_expired_pending_confirm: Callable[..., str | None],
    ) -> tuple[ConfirmAvailabilityResolution | None, str | None]:
        confirm_context, confirm_context_unavailable = self._rebuild_confirm_context(
            task_ref=task_ref,
            chat_id=chat_id,
        )
        if confirm_context is None:
            return self._resolve_missing_confirm_context(
                task_ref=task_ref,
                chat_id=chat_id,
                confirm_context_unavailable=confirm_context_unavailable,
                job_repo_available=job_repo_available,
            )

        if confirm_context.approval_lookup_failed:
            return None, ADD_CONFIRM_STATE_UNAVAILABLE_TEXT
        if confirm_context.job.state != JOB_STATE_PENDING_APPROVAL:
            return None, self._resolve_not_pending_rejection_text(
                task_id=confirm_context.pending_add.task_id,
                task_hash=confirm_context.pending_add.task_hash,
                find_version_stale_rejection_text=find_version_stale_rejection_text,
            )
        if (
            confirm_context.approval_record is None
            or confirm_context.approval_record.status != APPROVAL_STATUS_PENDING
        ):
            return None, self._resolve_not_pending_rejection_text(
                task_id=confirm_context.pending_add.task_id,
                task_hash=confirm_context.pending_add.task_hash,
                find_version_stale_rejection_text=find_version_stale_rejection_text,
            )
        expired_text = handle_expired_pending_confirm(
            task_ref=task_ref,
            context=confirm_context,
            chat_id=chat_id,
        )
        if expired_text is not None:
            return None, expired_text
        return ConfirmAvailabilityResolution(confirm_context=confirm_context, in_memory_pending=None), None

    def _resolve_missing_confirm_context(
        self,
        *,
        task_ref: str,
        chat_id: int | None,
        confirm_context_unavailable: bool,
        job_repo_available: bool,
    ) -> tuple[ConfirmAvailabilityResolution | None, str | None]:
        if confirm_context_unavailable:
            return None, ADD_CONFIRM_STATE_UNAVAILABLE_TEXT
        in_memory_pending = self._get_in_memory_pending(chat_id=chat_id, task_ref=task_ref)
        if in_memory_pending is None:
            return None, ADD_CONFIRM_NOT_PENDING_TEXT
        if job_repo_available and chat_id is not None and chat_id > 0:
            self._log_pending_job_result_missing(
                chat_id=chat_id,
                task_ref=task_ref,
                task_id=in_memory_pending.task_id,
                task_hash=in_memory_pending.task_hash,
                stage="confirm",
            )
            return None, ADD_CONFIRM_STATE_UNAVAILABLE_TEXT
        return ConfirmAvailabilityResolution(confirm_context=None, in_memory_pending=in_memory_pending), None

    def _resolve_not_pending_rejection_text(
        self,
        *,
        task_id: str,
        task_hash: str,
        find_version_stale_rejection_text: Callable[..., str | None],
    ) -> str:
        stale_text = find_version_stale_rejection_text(task_id=task_id, task_hash=task_hash)
        return stale_text or ADD_CONFIRM_NOT_PENDING_TEXT

    def has_pending_add(self, chat_id: int, task_ref: str) -> bool | None:
        cleaned_ref = task_ref.strip()
        if chat_id <= 0 or not cleaned_ref:
            return False
        in_memory_pending = self._get_in_memory_pending(chat_id=chat_id, task_ref=cleaned_ref)
        if self._job_repo is None:
            return in_memory_pending is not None
        try:
            job = self._job_repo.get_downloader_job_for_chat_ref(chat_id=chat_id, task_ref=cleaned_ref)
        except (JobPersistenceError, sqlite3.Error) as error:
            emit_operational_log(
                title="下载待确认查询失败",
                detail=f"chat_id={chat_id} task_ref={cleaned_ref} 错误={error}",
                fix_hint="检查 SQLite/jobs 表查询是否正常；若当前进程里也没有待确认上下文，这次请求会直接返回服务未就绪，避免把持久化异常误判成“没有待确认下载”。",
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
        return False

    def cancel_pending_add(self, chat_id: int) -> str | None:
        return self._cancel_state.cancel_pending_add(
            chat_id=chat_id,
            resolve_pending_lease_version=self._resolve_pending_lease_version,
            get_latest_pending_task_ref=self._pending_runtime_state.get_latest_task_ref,
            get_in_memory_pending=self._get_in_memory_pending,
            log_pending_job_result_missing=self._log_pending_job_result_missing,
            cancel_pending_approval=self._cancel_pending_approval,
            clear_pending_context=self._clear_pending_context,
            record_event=self._execution_follow_up.record_event,
        )

    def _record_pending_approval(self, *, task_ref: str, task_id: str, task_hash: str) -> int:
        return self._confirm_approval_state.record_pending_approval(
            task_ref=task_ref,
            task_id=task_id,
            task_hash=task_hash,
        )

    def _record_downloader_approval(
        self,
        *,
        task_ref: str,
        task_id: str,
        task_hash: str,
        expected_lease_version: int,
    ) -> bool | None:
        return self._confirm_approval_state.record_downloader_approval(
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
        return self._confirm_approval_state.restore_pending_approval(
            task_ref=task_ref,
            task_id=task_id,
            task_hash=task_hash,
            expected_lease_version=expected_lease_version,
        )

    def _cancel_pending_approval(
        self,
        *,
        task_ref: str,
        task_id: str,
        task_hash: str,
        expected_lease_version: int,
    ) -> bool:
        return self._confirm_approval_state.cancel_pending_approval(
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
        return self._confirm_approval_state.record_executed_lease_version(
            task_ref=task_ref,
            task_id=task_id,
            task_hash=task_hash,
            executed_lease_version=executed_lease_version,
        )

    def _record_pending_context(self, *, chat_id: int, pending_add: PendingAddContext) -> None:
        self._pending_runtime_state.record(chat_id=chat_id, pending_add=pending_add)

    def _move_completed_approval_identity(
        self,
        *,
        current_task_id: str,
        current_task_hash: str,
        new_task_id: str,
        new_task_hash: str,
    ) -> bool | None:
        return self._confirm_approval_state.move_completed_approval_identity(
            current_task_id=current_task_id,
            current_task_hash=current_task_hash,
            new_task_id=new_task_id,
            new_task_hash=new_task_hash,
        )

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
        self._execution_follow_up.record_event(
            task_ref=pending_add.task_ref,
            task_id=pending_add.task_id,
            task_hash=pending_add.task_hash,
            event_type="downloader.approval_pending",
            message=pending_add.title,
        )
        self._trace_logger.log(
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
            reply = render_add_pending_reply(pending_add=pending_add, channel=channel)
        else:
            reply = ADD_APPROVAL_PENDING_TEXT.format(title=pending_add.title, task_ref=pending_add.task_ref)
            extra_lines: list[str] = []
            if pending_add.adult_display_id:
                extra_lines.append(f"番号: {pending_add.adult_display_id}")
            if pending_add.adult_archive_category:
                extra_lines.append(f"分类: {pending_add.adult_archive_category}")
            if pending_add.adult_history_text:
                extra_lines.append(pending_add.adult_history_text)
            if extra_lines:
                reply = f"{reply}\n" + "\n".join(extra_lines)
        if reply != ADD_PENDING_STATE_UNAVAILABLE_TEXT:
            self._adult_registry_state.record_pending(pending_add=pending_add)
        return reply

    async def _run_confirm_execution_tail(
        self,
        *,
        task_ref: str,
        pending_add: PendingAddContext,
        chat_id: int | None,
        user_id: int | None,
        expected_lease_version: int,
        claimed_job: bool,
        claimed_job_id: str,
        claimed_job_version: int,
        lease_owner: str,
    ) -> str:
        self._execution_follow_up.record_event(
            task_ref=task_ref,
            task_id=pending_add.task_id,
            task_hash=pending_add.task_hash,
            event_type="downloader.approval_confirmed",
            message=pending_add.title,
        )

        execution = await self._execution_follow_up.dispatch(
            task_ref=task_ref,
            pending_add=pending_add,
            chat_id=chat_id,
            user_id=user_id,
        )
        if execution.result is None:
            approval_restored = self._restore_pending_approval(
                task_ref=task_ref,
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
        return self._confirm_finalization_state.finalize_confirmation(
            task_ref=task_ref,
            pending_add=pending_add,
            result=result,
            reply=reply,
            chat_id=chat_id,
            user_id=user_id,
            expected_lease_version=expected_lease_version,
            claimed_job=claimed_job,
            claimed_job_id=claimed_job_id,
            claimed_job_version=claimed_job_version,
            lease_owner=lease_owner,
            record_executed_lease_version=self._record_executed_lease_version,
            move_completed_approval_identity=self._move_completed_approval_identity,
            mark_completed_job=self._mark_completed_job,
            clear_pending_context=self._clear_pending_context,
        )

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
                raise JobPersistenceError(DOWNLOADER_PENDING_JOB_NONE_REASON)
        except (JobPersistenceError, sqlite3.Error) as error:
            if str(error) in {
                DOWNLOADER_PENDING_JOB_RESULT_MISSING_REASON,
                DOWNLOADER_PENDING_JOB_NONE_REASON,
            }:
                emit_operational_log(
                    title="下载待确认任务结果缺失",
                    detail=f"chat_id={chat_id} user_id={user_id} task_ref={pending_add.task_ref} task_id={pending_add.task_id} task_hash={pending_add.task_hash} 错误={error}",
                    fix_hint="检查 jobs 写入后回读是否仍能拿到刚创建的待确认任务；当前请求会直接返回待确认状态写入失败，避免把缺失真相误报成可确认下载。",
                )
            elif str(error) in DOWNLOADER_CONFIRM_CONTEXT_JOB_ROW_CORRUPTED_REASONS:
                emit_operational_log(
                    title="下载待确认任务记录损坏",
                    detail=f"chat_id={chat_id} user_id={user_id} task_ref={pending_add.task_ref} task_id={pending_add.task_id} task_hash={pending_add.task_hash} 错误={error}",
                    fix_hint="检查 jobs 新写入待确认任务里的 job_id / chat_id / user_id / version 等字段是否仍是完整真相；当前请求会直接返回待确认状态写入失败，避免把坏任务记录误报成可确认下载。",
                )
            else:
                emit_operational_log(
                    title="下载待确认任务落盘失败",
                    detail=f"chat_id={chat_id} user_id={user_id} task_ref={pending_add.task_ref} task_id={pending_add.task_id} task_hash={pending_add.task_hash} 错误={error}",
                    fix_hint="检查 SQLite/jobs 表写入是否正常；当前请求会直接返回待确认状态写入失败，避免把待确认任务真相缺口误报成可确认下载。",
                )
            return False
        return True

    def _rebuild_confirm_context(
        self,
        *,
        task_ref: str,
        chat_id: int | None,
    ) -> tuple[ConfirmExecutionContext | None, bool]:
        return self._confirm_context_state.rebuild_confirm_context(
            task_ref=task_ref,
            chat_id=chat_id,
        )

    def _get_in_memory_pending(self, *, chat_id: int | None, task_ref: str) -> PendingAddContext | None:
        return self._pending_runtime_state.get(chat_id=chat_id, task_ref=task_ref)

    def _log_pending_job_result_missing(
        self,
        *,
        chat_id: int,
        task_ref: str,
        task_id: str,
        task_hash: str,
        stage: str,
    ) -> None:
        self._pending_runtime_state.log_pending_job_result_missing(
            chat_id=chat_id,
            task_ref=task_ref,
            task_id=task_id,
            task_hash=task_hash,
            stage=stage,
        )

    def _clear_pending_context(self, *, chat_id: int | None, task_ref: str) -> None:
        self._pending_runtime_state.clear(chat_id=chat_id, task_ref=task_ref)

    def _claim_pending_job(self, *, job: JobRecord, lease_owner: str) -> bool | None:
        return self._confirm_job_state.claim_pending_job(job=job, lease_owner=lease_owner)

    def _restore_pending_job(
        self,
        *,
        job_id: str,
        expected_version: int,
        lease_owner: str,
    ) -> None:
        self._confirm_job_state.restore_pending_job(
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
        completed_add: PendingAddContext,
    ) -> bool | None:
        return self._confirm_job_state.mark_completed_job(
            job_id=job_id,
            expected_version=expected_version,
            lease_owner=lease_owner,
            completed_add=completed_add,
        )

    def _build_job_lease_owner(self, task_ref: str) -> str:
        return self._confirm_job_state.build_job_lease_owner(task_ref)

    def _resolve_pending_lease_version(
        self,
        *,
        task_id: str,
        task_hash: str,
        allow_in_memory_fallback_on_error: bool = True,
    ) -> int:
        return self._confirm_approval_state.resolve_pending_lease_version(
            task_id=task_id,
            task_hash=task_hash,
            allow_in_memory_fallback_on_error=allow_in_memory_fallback_on_error,
        )

    def _find_version_stale_rejection_text(self, *, task_id: str, task_hash: str) -> str | None:
        return self._confirm_approval_state.find_version_stale_rejection_text(task_id=task_id, task_hash=task_hash)

    def _handle_expired_pending_confirm(
        self,
        *,
        task_ref: str,
        context: ConfirmExecutionContext,
        chat_id: int | None,
    ) -> str | None:
        return self._confirm_context_state.handle_expired_pending_confirm(
            task_ref=task_ref,
            context=context,
            chat_id=chat_id,
            is_pending_approval_expired=self._is_pending_approval_expired,
            cancel_pending_approval=self._cancel_pending_approval,
            clear_pending_context=self._clear_pending_context,
            record_event=self._execution_follow_up.record_event,
        )

    def _is_pending_approval_expired(
        self,
        *,
        task_id: str,
        task_hash: str,
        expected_lease_version: int,
    ) -> bool | None:
        return self._confirm_approval_state.is_pending_approval_expired(
            task_id=task_id,
            task_hash=task_hash,
            expected_lease_version=expected_lease_version,
        )


def render_add_pending_reply(*, pending_add: PendingAddContext, channel: str) -> str:
    return render_delivery_item(build_add_pending_delivery_item(pending_add), channel=channel)


def build_add_pending_delivery_item(pending_add: PendingAddContext) -> DeliveryItem:
    expire_minutes = max(1, DEFAULT_PENDING_TIMEOUT_SECONDS // 60)
    task_lines = [
        f"片名：{pending_add.title}",
        f"选择序号：{pending_add.task_ref}",
    ]
    if pending_add.adult_display_id:
        task_lines.append(f"番号：{pending_add.adult_display_id}")
    if pending_add.adult_archive_category:
        task_lines.append(f"分类：{pending_add.adult_archive_category}")
    if pending_add.adult_history_text:
        task_lines.append(pending_add.adult_history_text)
    return DeliveryItem(
        header=DeliveryHeader(kind="approval", title="待确认：下载"),
        sections=(
            DeliverySection(
                label="任务信息",
                lines=tuple(task_lines),
            ),
        ),
        actions=(
            DeliveryAction(label="确认下载", hint=f"发送 confirm {pending_add.task_ref}", kind="primary"),
            DeliveryAction(label="取消下载", hint=f"发送 cancel {pending_add.task_ref}", kind="secondary"),
        ),
        footer=f"过期时间：{expire_minutes} 分钟后",
        status="pending",
    )

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from app.db.approval_repo import (
    APPROVAL_STATUS_PENDING,
    DEFAULT_PENDING_TIMEOUT_SECONDS,
    ApprovalPersistenceError,
    ApprovalRepo,
)

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
            print(
                f"\033[31m[下载待确认版号查询失败]\033[0m task_id={task_id} task_hash={task_hash} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表查询是否正常；当前调用会按状态读取失败处理，避免把持久化真相异常继续混成进程内版号兜底。",
                flush=True,
            )
            if not allow_in_memory_fallback_on_error:
                return PENDING_LEASE_LOOKUP_FAILED
            if identity not in self.pending_add_identities:
                return 0
            return self.pending_add_lease_versions.get(identity, 1)
        if approval_record is None:
            if identity in self.pending_add_identities:
                print(
                    f"\033[31m[下载待确认版号查询失败]\033[0m task_id={task_id} task_hash={task_hash} 错误=approval_record missing while in-memory pending exists\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表里的待确认下载审批是否仍存在；当前调用会按状态读取失败处理，避免把审批真相缺口继续混成进程内版号兜底。",
                    flush=True,
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
                print(
                    f"\033[31m[下载确认执行版号记录损坏]\033[0m task_id={task_id} task_hash={task_hash} 错误={error}\n\033[33m[处理建议]\033[0m 检查 approval_record 里的 status / lease_version / executed_version 等字段是否仍是完整真相；当前 confirm 会直接返回状态读取失败，避免把坏审批记录误判成普通没有待确认下载。",
                    flush=True,
                )
            else:
                print(
                    f"\033[31m[下载确认执行版号查询失败]\033[0m task_id={task_id} task_hash={task_hash} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表查询是否正常；当前 confirm 会直接返回状态读取失败，避免把持久化异常误判成普通没有待确认下载。",
                    flush=True,
                )
            return self.add_confirm_state_unavailable_text
        if approval_record is None:
            print(
                f"\033[31m[下载确认执行版号查询失败]\033[0m task_id={task_id} task_hash={task_hash} 错误=approval_record missing during stale check\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表里的待确认下载审批是否仍存在；当前 confirm 会直接返回状态读取失败，避免把审批真相缺口误判成普通没有待确认下载。",
                flush=True,
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
            self.pending_add_identities.add(identity)
            print(
                f"\033[31m[下载取消审批更新失败]\033[0m task_ref={task_ref} task_id={task_id} task_hash={task_hash} lease_version={expected_lease_version} 错误=approval_record missing or lease_version mismatch\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表里的待确认下载审批是否仍存在，或是否已被其他路径抢先取消/确认；当前取消会直接返回状态读取失败，避免把审批真相缺口误判成“没有待取消下载”。",
                flush=True,
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
            print(
                f"\033[31m[下载审批身份迁移失败]\033[0m current_task_id={current_task_id} current_task_hash={current_task_hash} new_task_id={new_task_id} new_task_hash={new_task_hash} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表里的下载审批是否仍存在，并确认 confirm 后审批主键已切到真实下载任务身份；当前下载已执行，但重启后的 stale confirm 保护可能不稳。",
                flush=True,
            )
            return None
        return True

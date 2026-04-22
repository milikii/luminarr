from __future__ import annotations

from dataclasses import dataclass, field

from app.db.approval_repo import APPROVAL_STATUS_PENDING, ApprovalRepo

PENDING_LEASE_LOOKUP_FAILED = -1
DOWNLOADER_PENDING_EXPIRY_RESULT_MISSING_REASON = "approval_record missing during pending expiry check"
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
        except Exception as error:
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

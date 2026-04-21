from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.db.approval_repo import APPROVAL_STATUS_PENDING, DEFAULT_PENDING_TIMEOUT_SECONDS, ApprovalRepo
from app.db.job_event_repo import JobEventRepo

PENDING_LEASE_LOOKUP_FAILED = -1
IMPORT_PENDING_APPROVAL_RESULT_MISSING_REASON = "approval_record missing after pending request"
IMPORT_PENDING_APPROVAL_NONE_REASON = "import pending approval result missing"
IMPORT_PENDING_APPROVAL_ROW_CORRUPTED_REASON = "approval row lease version corrupted after read"
IMPORT_APPROVE_RESULT_MISSING_REASON = "approval_record missing during approve"
IMPORT_APPROVE_RESULT_NONE_REASON = "import approval result missing"
IMPORT_EXECUTED_LEASE_RESULT_MISSING_REASON = "approval_record missing during executed version update"
IMPORT_TARGET_LOOKUP_RESULT_MISSING_REASON = "job_event list result missing during correlation lookup"
IMPORT_PENDING_EXPIRY_RESULT_MISSING_REASON = "approval_record missing during pending expiry check"
APPROVAL_ROW_CORRUPTED_REASONS = frozenset(
    {
        "approval row identity corrupted after read",
        "approval row status corrupted after read",
        "approval row lease version corrupted after read",
        "approval row executed version corrupted after read",
    }
)

IsImportTargetLookupRowCorruptedErrorFunc = Callable[[Exception], bool]


@dataclass(frozen=True, slots=True)
class ImportTargetLookupResult:
    target_path: str | None = None
    lookup_failed: bool = False


class ImportApprovalState:
    def __init__(
        self,
        *,
        approval_repo: ApprovalRepo | None,
        job_event_repo: JobEventRepo | None,
        is_import_target_lookup_row_corrupted_error: IsImportTargetLookupRowCorruptedErrorFunc,
        import_confirm_state_unavailable_text: str,
        import_confirm_not_pending_text: str,
        import_target_exists_text_template: str,
    ) -> None:
        self._approval_repo = approval_repo
        self._job_event_repo = job_event_repo
        self._is_import_target_lookup_row_corrupted_error = is_import_target_lookup_row_corrupted_error
        self._import_confirm_state_unavailable_text = import_confirm_state_unavailable_text
        self._import_confirm_not_pending_text = import_confirm_not_pending_text
        self._import_target_exists_text_template = import_target_exists_text_template
        self.pending_import_identities: set[tuple[str, str]] = set()
        self.pending_import_lease_versions: dict[tuple[str, str], int] = {}

    def record_pending_approval(self, *, task_ref: str, task_id: str, task_hash: str) -> int:
        identity = (task_id.strip(), task_hash.strip())
        if not identity[0] or not identity[1]:
            return 0

        in_memory_next_lease = self.pending_import_lease_versions.get(identity, 0) + 1
        lease_version = in_memory_next_lease

        if self._approval_repo is None:
            self.pending_import_lease_versions[identity] = lease_version
            self.pending_import_identities.add(identity)
            return lease_version
        try:
            requested_lease = self._approval_repo.request_import_approval(
                task_id=task_id,
                task_hash=task_hash,
                task_ref=task_ref,
                timeout_seconds=DEFAULT_PENDING_TIMEOUT_SECONDS,
            )
            if type(requested_lease) is not int or requested_lease <= 0:
                raise RuntimeError(IMPORT_PENDING_APPROVAL_NONE_REASON)
            lease_version = requested_lease
        except Exception as error:
            if str(error) in {
                IMPORT_PENDING_APPROVAL_RESULT_MISSING_REASON,
                IMPORT_PENDING_APPROVAL_NONE_REASON,
            }:
                print(
                    f"\033[31m[导入待确认审批结果缺失]\033[0m task_ref={task_ref} task_id={task_id} task_hash={task_hash} 错误={error}\n"
                    "\033[33m[处理建议]\033[0m 检查 approval_record 写入后回读是否仍能拿到当前待确认导入审批的 lease_version；"
                    "当前请求会直接返回待确认状态写入失败，避免把缺失真相误报成可确认导入。",
                    flush=True,
                )
            elif str(error) == IMPORT_PENDING_APPROVAL_ROW_CORRUPTED_REASON:
                print(
                    f"\033[31m[导入待确认审批记录损坏]\033[0m task_ref={task_ref} task_id={task_id} task_hash={task_hash} 错误={error}\n"
                    "\033[33m[处理建议]\033[0m 检查 approval_record.lease_version 是否仍是正整数真相；"
                    "当前请求会直接返回待确认状态写入失败，避免把坏审批记录误报成可确认导入。",
                    flush=True,
                )
            else:
                print(
                    f"\033[31m[导入待确认审批落盘失败]\033[0m task_ref={task_ref} task_id={task_id} task_hash={task_hash} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表写入是否正常；当前请求会直接返回待确认状态写入失败，避免把审批真相缺口误报成可确认导入。",
                    flush=True,
                )
            return 0

        self.pending_import_lease_versions[identity] = lease_version
        self.pending_import_identities.add(identity)
        return lease_version

    def record_import_approval(
        self,
        *,
        task_ref: str,
        task_id: str,
        task_hash: str,
        expected_lease_version: int,
    ) -> bool | None:
        identity = (task_id.strip(), task_hash.strip())
        if not identity[0] or not identity[1]:
            return False
        if expected_lease_version <= 0:
            return False

        if self._approval_repo is None:
            current_lease = self.pending_import_lease_versions.get(identity, 0)
            if identity not in self.pending_import_identities or current_lease != expected_lease_version:
                return False
            self.pending_import_identities.remove(identity)
            return True

        approved = False
        try:
            approved = self._approval_repo.approve_import(
                task_id=task_id,
                task_hash=task_hash,
                task_ref=task_ref,
                expected_lease_version=expected_lease_version,
            )
            if approved is None:
                raise RuntimeError(IMPORT_APPROVE_RESULT_NONE_REASON)
        except Exception as error:
            if str(error) in {
                IMPORT_APPROVE_RESULT_MISSING_REASON,
                IMPORT_APPROVE_RESULT_NONE_REASON,
            }:
                print(
                    f"\033[31m[导入确认审批结果缺失]\033[0m task_ref={task_ref} task_id={task_id} task_hash={task_hash} lease_version={expected_lease_version} 错误={error}\n"
                    "\033[33m[处理建议]\033[0m 检查 approval_record 表里该待确认导入审批是否仍存在，以及审批更新后是否还能回读到该行；"
                    "当前 confirm 会直接返回状态读取失败，避免把缺失真相误判成普通已确认或普通状态冲突。",
                    flush=True,
                )
                return None
            print(
                f"\033[31m[导入确认审批更新失败]\033[0m task_ref={task_ref} task_id={task_id} task_hash={task_hash} lease_version={expected_lease_version} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表更新是否正常；当前 confirm 会直接返回状态读取失败，避免把审批真相更新失败误判成导入已确认。",
                flush=True,
            )
            return None
        if not approved:
            print(
                f"\033[31m[导入确认审批更新失败]\033[0m task_ref={task_ref} task_id={task_id} task_hash={task_hash} lease_version={expected_lease_version} 错误=approval_record approve rejected current state\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表里的待确认导入审批是否仍存在、lease_version 是否匹配；当前 confirm 会按 not pending 处理，避免把审批真相状态冲突误判成已确认。",
                flush=True,
            )
            return False

        if approved and identity in self.pending_import_identities:
            self.pending_import_identities.remove(identity)
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
        if not identity[0] or not identity[1]:
            return False
        if expected_lease_version <= 0:
            return False
        self.pending_import_identities.add(identity)
        self.pending_import_lease_versions[identity] = expected_lease_version
        if self._approval_repo is None:
            return True
        try:
            restored = self._approval_repo.restore_import_pending(
                task_id=task_id,
                task_hash=task_hash,
                task_ref=task_ref,
                expected_lease_version=expected_lease_version,
            )
            if restored is None:
                raise RuntimeError("import restore pending approval result missing")
        except Exception as error:
            if str(error) in {
                "import restore pending approval result missing",
                "approval_record missing during restore",
            }:
                print(
                    f"\033[31m[导入审批回退结果缺失]\033[0m task_ref={task_ref} task_id={task_id} task_hash={task_hash} lease_version={expected_lease_version} 原因={error}\n\033[33m[处理建议]\033[0m 检查 approval_record 回退后是否还能立即回读到 pending 审批真相；当前进程内待确认身份已回退，但持久化审批状态还没有确认回退成功。",
                    flush=True,
                )
            else:
                print(
                    f"\033[31m[导入审批回退失败]\033[0m task_ref={task_ref} task_id={task_id} task_hash={task_hash} lease_version={expected_lease_version} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表更新是否正常；当前进程内待确认身份已回退，但重启后审批状态可能不一致。",
                    flush=True,
                )
            return None
        if restored is False:
            print(
                f"\033[31m[导入审批回退失败]\033[0m task_ref={task_ref} task_id={task_id} task_hash={task_hash} lease_version={expected_lease_version} 错误=approval_record restore rejected current state\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表里的审批行是否仍存在、lease_version 是否匹配；当前进程内待确认身份已回退，但重启后审批状态可能不一致。",
                flush=True,
            )
            return False
        return True

    def record_executed_lease_version(
        self,
        *,
        task_id: str,
        task_hash: str,
        executed_lease_version: int,
    ) -> bool | None:
        identity = (task_id.strip(), task_hash.strip())
        if not identity[0] or not identity[1] or executed_lease_version <= 0:
            return False
        self.pending_import_lease_versions[identity] = executed_lease_version
        if self._approval_repo is None:
            return True
        try:
            self._approval_repo.mark_import_executed(
                task_id=task_id,
                task_hash=task_hash,
                executed_lease_version=executed_lease_version,
            )
        except Exception as error:
            if str(error) == IMPORT_EXECUTED_LEASE_RESULT_MISSING_REASON:
                print(
                    f"\033[31m[导入执行版号结果缺失]\033[0m task_id={task_id} task_hash={task_hash} lease_version={executed_lease_version} 错误={error}\n"
                    "\033[33m[处理建议]\033[0m 检查 approval_record 更新后该审批行是否仍存在，并确认 executed_version 已被正确回写；"
                    "当前进程内 lease 版本已前进，但持久化真相还没有确认落稳。",
                    flush=True,
                )
            elif str(error) in APPROVAL_ROW_CORRUPTED_REASONS:
                print(
                    f"\033[31m[导入执行版号记录损坏]\033[0m task_id={task_id} task_hash={task_hash} lease_version={executed_lease_version} 错误={error}\n"
                    "\033[33m[处理建议]\033[0m 检查 approval_record 里的 lease_version / executed_version 等字段是否仍是完整真相；"
                    "当前进程内 lease 版本已前进，但不会把坏审批记录当成已稳定回写。",
                    flush=True,
                )
            else:
                print(
                    f"\033[31m[导入执行版号回写失败]\033[0m task_id={task_id} task_hash={task_hash} lease_version={executed_lease_version} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表更新是否正常；当前进程内 lease 版本已前进，但持久化真相可能仍停留在旧值。",
                    flush=True,
                )
            return None
        return True

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
        if self._approval_repo is None:
            if identity not in self.pending_import_identities:
                return 0
            return self.pending_import_lease_versions.get(identity, 1)

        try:
            approval_record = self._approval_repo.get_import_approval(task_id=task_id, task_hash=task_hash)
        except Exception as error:
            print(
                f"\033[31m[导入待确认版号查询失败]\033[0m task_id={task_id} task_hash={task_hash} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表查询是否正常；当前调用会按状态读取失败处理，避免把持久化真相异常继续混成进程内版号兜底。",
                flush=True,
            )
            if not allow_in_memory_fallback_on_error:
                return PENDING_LEASE_LOOKUP_FAILED
            if identity not in self.pending_import_identities:
                return 0
            return self.pending_import_lease_versions.get(identity, 1)
        if approval_record is None:
            if identity in self.pending_import_identities:
                print(
                    f"\033[31m[导入待确认版号查询失败]\033[0m task_id={task_id} task_hash={task_hash} 错误=approval_record missing while in-memory pending exists\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表里的待确认导入审批是否仍存在；当前调用会按状态读取失败处理，避免把审批真相缺口继续混成进程内版号兜底。",
                    flush=True,
                )
                if not allow_in_memory_fallback_on_error:
                    return PENDING_LEASE_LOOKUP_FAILED
                return self.pending_import_lease_versions.get(identity, 1)
            if identity not in self.pending_import_identities:
                return 0
            return self.pending_import_lease_versions.get(identity, 1)
        if approval_record.status != APPROVAL_STATUS_PENDING:
            return 0
        return max(0, approval_record.lease_version)

    def find_version_stale_rejection_text(self, *, task_id: str, task_hash: str) -> str | None:
        if self._approval_repo is None:
            return None
        try:
            approval_record = self._approval_repo.get_import_approval(task_id=task_id, task_hash=task_hash)
        except Exception as error:
            if str(error) in APPROVAL_ROW_CORRUPTED_REASONS:
                print(
                    f"\033[31m[导入确认执行版号记录损坏]\033[0m task_id={task_id} task_hash={task_hash} 错误={error}\n\033[33m[处理建议]\033[0m 检查 approval_record 里的 status / lease_version / executed_version 等字段是否仍是完整真相；当前 confirm 会直接返回状态读取失败，避免把坏审批记录误判成普通没有待确认导入。",
                    flush=True,
                )
            else:
                print(
                    f"\033[31m[导入确认执行版号查询失败]\033[0m task_id={task_id} task_hash={task_hash} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表查询是否正常；当前 confirm 会直接返回状态读取失败，避免把持久化异常误判成普通没有待确认导入。",
                    flush=True,
                )
            return self._import_confirm_state_unavailable_text
        if approval_record is None:
            print(
                f"\033[31m[导入确认执行版号查询失败]\033[0m task_id={task_id} task_hash={task_hash} 错误=approval_record missing during stale check\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表里的待确认导入审批是否仍存在；当前 confirm 会直接返回状态读取失败，避免把审批真相缺口误判成普通没有待确认导入。",
                flush=True,
            )
            return self._import_confirm_state_unavailable_text
        if approval_record.lease_version <= 0:
            return None
        if approval_record.executed_version < approval_record.lease_version:
            return None

        stale_target_lookup = self.find_latest_import_target_path(task_id=task_id, task_hash=task_hash)
        if stale_target_lookup.lookup_failed:
            return self._import_confirm_state_unavailable_text
        if stale_target_lookup.target_path:
            return self._import_target_exists_text_template.format(target_path=stale_target_lookup.target_path)
        return self._import_confirm_not_pending_text

    def find_latest_import_target_path(self, *, task_id: str, task_hash: str) -> ImportTargetLookupResult:
        if self._job_event_repo is None:
            return ImportTargetLookupResult()
        try:
            correlation = self._job_event_repo.find_latest_import_correlation(
                task_id=task_id,
                task_hash=task_hash,
            )
        except Exception as error:
            if str(error) == IMPORT_TARGET_LOOKUP_RESULT_MISSING_REASON:
                print(
                    f"\033[31m[导入目标路径结果缺失]\033[0m task_id={task_id} task_hash={task_hash} 错误={error}\n"
                    "\033[33m[处理建议]\033[0m 检查 job_event 关联查询返回是否仍带有完整事件列表；"
                    "当前 confirm 会直接返回状态读取失败，避免把缺失真相误判成普通“无导入目标路径”。",
                    flush=True,
                )
            elif self._is_import_target_lookup_row_corrupted_error(error):
                print(
                    f"\033[31m[导入目标路径记录损坏]\033[0m task_id={task_id} task_hash={task_hash} 错误={error}\n"
                    "\033[33m[处理建议]\033[0m 检查 job_event 导入成功关联里的 task_ref / event_type / target_path / message "
                    "是否仍是完整真相；当前 confirm 会直接返回状态读取失败，避免把坏记录误判成普通“无导入目标路径”。",
                    flush=True,
                )
            else:
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
        print(
            f"\033[31m[导入目标路径缺失]\033[0m task_id={task_id} task_hash={task_hash} 错误=import correlation target path missing\n"
            "\033[33m[处理建议]\033[0m 检查 import.succeeded 事件是否仍带有 target_path 或 message；"
            "当前会按无导入目标路径处理，避免把结构化路径缺失误判成普通“没有历史导入终态”。",
            flush=True,
        )
        return ImportTargetLookupResult()

    def is_pending_approval_expired(
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
            if str(error) == IMPORT_PENDING_EXPIRY_RESULT_MISSING_REASON:
                print(
                    f"\033[31m[导入确认过期结果缺失]\033[0m task_id={task_id} task_hash={task_hash} lease_version={expected_lease_version} 错误={error}\n"
                    "\033[33m[处理建议]\033[0m 检查 approval_record 表里的待确认导入审批是否仍存在，并确认对应 lease_version 没有被其他路径抢先改写；"
                    "当前 confirm 会直接返回状态读取失败，避免把审批真相缺口误判成普通“未过期”。",
                    flush=True,
                )
            elif str(error) in APPROVAL_ROW_CORRUPTED_REASONS:
                print(
                    f"\033[31m[导入确认过期审批记录损坏]\033[0m task_id={task_id} task_hash={task_hash} lease_version={expected_lease_version} 错误={error}\n"
                    "\033[33m[处理建议]\033[0m 检查 approval_record 里的 status / lease_version / executed_version 等字段是否仍是完整真相；"
                    "当前 confirm 会直接返回状态读取失败，避免把坏审批记录误判成普通“未过期”。",
                    flush=True,
                )
            else:
                print(
                    f"\033[31m[导入确认过期判断失败]\033[0m task_id={task_id} task_hash={task_hash} lease_version={expected_lease_version} 错误={error}\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表查询是否正常；当前 confirm 会直接返回状态读取失败，避免把持久化异常误判成“未过期”。",
                    flush=True,
                )
            return None

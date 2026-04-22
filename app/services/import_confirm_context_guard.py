from __future__ import annotations

from app.services.import_context_lookup import ConfirmExecutionContext, ImportContextLookup


class ImportConfirmContextGuard:
    def __init__(self, *, context_lookup: ImportContextLookup) -> None:
        self._context_lookup = context_lookup

    def rebuild_confirm_context(
        self,
        *,
        task_ref: str,
        chat_id: int | None,
    ) -> tuple[ConfirmExecutionContext | None, bool]:
        lookup = self._context_lookup.rebuild_confirm_context(task_ref=task_ref, chat_id=chat_id)
        if lookup.lookup_failed:
            if lookup.job_error_kind == "row_corrupted":
                self._log_context_row_corrupted(
                    chat_id=chat_id or 0,
                    task_ref=task_ref,
                    reason=lookup.job_error_detail,
                )
            else:
                self._log_context_lookup_failed(
                    chat_id=chat_id or 0,
                    task_ref=task_ref,
                    reason=lookup.job_error_detail,
                )
            return None, True
        context = lookup.context
        if context is not None and context.approval_lookup_failed:
            self._log_approval_lookup_failed(
                task_ref=task_ref,
                task_id=context.job.task_id,
                task_hash=context.job.task_hash,
                reason=lookup.approval_error_detail,
            )
        return context, False

    def _log_context_row_corrupted(self, *, chat_id: int, task_ref: str, reason: str) -> None:
        print(
            f"\033[31m[导入确认上下文记录损坏]\033[0m chat_id={chat_id} task_ref={task_ref} 错误={reason}\n"
            "\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表里当前导入任务的 job_id / chat_id / task_ref / task_id / task_hash / version 等真相字段；"
            "当前 confirm 会直接返回状态读取失败，避免把坏任务记录误判成普通查询失败或“没有待确认导入”。",
            flush=True,
        )

    def _log_context_lookup_failed(self, *, chat_id: int, task_ref: str, reason: str) -> None:
        print(
            f"\033[31m[导入确认上下文查询失败]\033[0m chat_id={chat_id} task_ref={task_ref} 错误={reason}\n\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表查询是否正常；当前 confirm 会直接返回状态读取失败，避免把持久化异常误判成“没有待确认导入”或“未找到对应下载任务”。",
            flush=True,
        )

    def _log_approval_lookup_failed(self, *, task_ref: str, task_id: str, task_hash: str, reason: str) -> None:
        print(
            f"\033[31m[导入确认审批查询失败]\033[0m task_ref={task_ref} task_id={task_id} task_hash={task_hash} 错误={reason}\n\033[33m[处理建议]\033[0m 检查 SQLite/approval_record 表查询是否正常；当前 confirm 会直接返回状态读取失败，避免把审批真相缺口误判成普通未确认状态。",
            flush=True,
        )

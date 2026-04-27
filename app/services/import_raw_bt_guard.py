from __future__ import annotations

from app.operational_logging import emit_operational_log
from app.services.import_context_lookup import ImportContextLookup


class ImportRawBtGuard:
    def __init__(
        self,
        *,
        context_lookup: ImportContextLookup,
        raw_bt_lookup_result_missing_reason: str,
    ) -> None:
        self._context_lookup = context_lookup
        self._raw_bt_lookup_result_missing_reason = raw_bt_lookup_result_missing_reason

    def is_raw_bt_task(self, *, chat_id: int | None, task_ref: str) -> bool | None:
        lookup = self._context_lookup.lookup_raw_bt_task(chat_id=chat_id, task_ref=task_ref)
        if lookup.error_kind == "row_corrupted":
            self._log_lookup_row_corrupted(
                chat_id=chat_id or 0,
                task_ref=task_ref,
                reason=lookup.detail,
            )
            return None
        if lookup.error_kind == "lookup_failed":
            self._log_lookup_failed(
                chat_id=chat_id or 0,
                task_ref=task_ref,
                reason=lookup.detail,
            )
            return None
        if lookup.error_kind == "result_missing":
            self._log_lookup_result_missing(
                chat_id=chat_id or 0,
                task_ref=task_ref,
                reason=self._raw_bt_lookup_result_missing_reason,
            )
            return None
        if lookup.error_kind == "payload_corrupted":
            self._log_payload_corrupted(
                chat_id=chat_id or 0,
                task_ref=task_ref,
                payload_summary=lookup.detail,
            )
            return None
        return lookup.is_raw_bt

    def _log_lookup_failed(self, *, chat_id: int, task_ref: str, reason: str) -> None:
        emit_operational_log(
            title="导入 raw_bt 判定查询失败",
            detail=f"chat_id={chat_id} task_ref={task_ref} 错误={reason}",
            fix_hint="检查 SQLite/jobs 表读取是否正常；当前请求会直接返回查询失败，避免把原本应被阻断的 raw_bt 任务继续送进入库链。",
        )

    def _log_payload_corrupted(self, *, chat_id: int, task_ref: str, payload_summary: str) -> None:
        emit_operational_log(
            title="导入 raw_bt 判定载荷损坏",
            detail=f"chat_id={chat_id} task_ref={task_ref} 载荷={payload_summary}",
            fix_hint="检查 SQLite/jobs 表里的 payload_json 是否仍是完整下载任务上下文；当前请求会直接返回查询失败，避免把原本应被阻断的 raw_bt 任务继续送进入库链。",
        )

    def _log_lookup_result_missing(self, *, chat_id: int, task_ref: str, reason: str) -> None:
        emit_operational_log(
            title="导入 raw_bt 判定结果缺失",
            detail=f"chat_id={chat_id} task_ref={task_ref} 错误={reason}",
            fix_hint="检查 SQLite/jobs 表里当前下载任务是否仍存在，并确认这条任务真相没有被提前清理；当前请求会直接返回查询失败，避免把 raw_bt 分类真相缺口误判成普通“不是 raw_bt”。",
        )

    def _log_lookup_row_corrupted(self, *, chat_id: int, task_ref: str, reason: str) -> None:
        emit_operational_log(
            title="导入 raw_bt 判定记录损坏",
            detail=f"chat_id={chat_id} task_ref={task_ref} 错误={reason}",
            fix_hint="检查 SQLite/jobs 表里当前下载任务的 job_id / chat_id / task_ref / payload_json 等真相字段；当前请求会直接返回查询失败，避免把坏任务记录误判成普通查询失败或普通“不是 raw_bt”。",
        )

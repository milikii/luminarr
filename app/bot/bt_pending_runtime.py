from __future__ import annotations

import json
from collections.abc import MutableMapping

from app.db.bt_pending_repo import BtPendingRepo
from app.operational_logging import emit_operational_log

BT_PENDING_REPO_KEY = "bt_pending_repo"
BT_PENDING_MISSING_AFTER_UPSERT_REASON = "bt_pending_state missing after upsert"
BT_PENDING_CLEAR_RESULT_MISSING_REASON = "bt_pending_state clear result missing"
BT_PENDING_STAGE_EMPTY_AFTER_READ_REASON = "bt_pending_state stage empty after read"


def resolve_bt_pending_repo(
    bot_data: MutableMapping[str, object],
    bt_pending_repo_key: str,
) -> BtPendingRepo | None:
    pending_repo = bot_data.get(bt_pending_repo_key)
    if isinstance(pending_repo, BtPendingRepo):
        return pending_repo
    return None


def serialize_bt_pending_payload(payload: dict[str, object]) -> str:
    try:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return "{}"


def deserialize_bt_pending_payload(payload_json: str) -> tuple[dict[str, object], str | None]:
    if not payload_json.strip():
        return {}, "payload_json empty"
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError:
        return {}, "payload_json invalid json"
    if not isinstance(payload, dict):
        return {}, "payload_json not object"
    return payload, None


def is_bt_pending_row_corrupted_reason(reason: str) -> bool:
    return reason == BT_PENDING_STAGE_EMPTY_AFTER_READ_REASON


def log_bt_pending_payload_corruption(*, chat_id: int | None, stage: str, reason: str) -> None:
    _log_bt_pending_state_error(
        title="BT 待处理载荷损坏",
        chat_id=chat_id,
        stage=stage,
        reason=reason,
        fix_hint="检查 bt_pending_state.payload_json 是否仍是合法 JSON，且包含当前 stage 需要的字段。",
    )


def log_bt_pending_clear_failed(*, chat_id: int | None, stage: str, reason: str) -> None:
    _log_bt_pending_state_error(
        title="BT 待处理清理失败",
        chat_id=chat_id,
        stage=stage,
        reason=reason,
        fix_hint="检查 bt_pending_state 表删除是否正常；当前进程内待处理状态已尽量清掉，但重启后旧状态可能仍残留。",
    )


def log_bt_pending_clear_result_missing(*, chat_id: int | None, stage: str, reason: str) -> None:
    _log_bt_pending_state_error(
        title="BT 待处理清理结果缺失",
        chat_id=chat_id,
        stage=stage,
        reason=reason,
        fix_hint="检查 bt_pending_state 删除返回是否仍带有明确结果；当前进程内待处理状态已尽量回滚，避免把缺失真相误判成已清理成功。",
    )


def log_bt_pending_read_failed(*, chat_id: int | None, stage: str, reason: str) -> None:
    _log_bt_pending_state_error(
        title="BT 待处理读取失败",
        chat_id=chat_id,
        stage=stage,
        reason=reason,
        fix_hint="检查 bt_pending_state 表读取是否正常；当前相关入口会按状态不可用处理，避免把 SQLite 读取异常误判成“没有待处理状态”。",
    )


def log_bt_pending_row_corrupted(*, chat_id: int | None, stage: str, reason: str) -> None:
    _log_bt_pending_state_error(
        title="BT 待处理记录损坏",
        chat_id=chat_id,
        stage=stage,
        reason=reason,
        fix_hint="检查 bt_pending_state.stage 是否仍是完整真相；当前相关入口会按状态不可用处理，避免把坏记录误判成“没有待处理状态”。",
    )


def log_bt_pending_persist_failed(*, chat_id: int | None, stage: str, reason: str) -> None:
    _log_bt_pending_state_error(
        title="BT 待处理持久化失败",
        chat_id=chat_id,
        stage=stage,
        reason=reason,
        fix_hint="检查 bt_pending_state 表写入是否正常；当前进程内待处理状态仍保留，但重启后可能丢失这一步的上下文。",
    )


def log_bt_pending_missing_after_upsert(*, chat_id: int | None, stage: str, reason: str) -> None:
    _log_bt_pending_state_error(
        title="BT 待处理写入后记录缺失",
        chat_id=chat_id,
        stage=stage,
        reason=reason,
        fix_hint=(
            "检查 bt_pending_state 表是否被并发删除或触发器回滚；"
            "如需继续当前 BT follow-up，请先确认 SQLite 写入后能立即回读该记录。"
        ),
    )


def _log_bt_pending_state_error(
    *,
    title: str,
    chat_id: int | None,
    stage: str,
    reason: str,
    fix_hint: str,
) -> None:
    emit_operational_log(
        title=title,
        detail=f"chat_id={chat_id if chat_id is not None else '-'} stage={stage} 原因={reason}",
        fix_hint=fix_hint,
    )

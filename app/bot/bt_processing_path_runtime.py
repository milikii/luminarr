from __future__ import annotations

import json
from collections.abc import MutableMapping
from typing import Literal

from app.db.bt_pending_repo import (
    BT_PENDING_STAGE_PROCESSING_PATH,
    BtPendingPersistenceError,
    BtPendingRepo,
)

BT_PROCESSING_PATH_PROMPT_TEXT = (
    "已识别为直接磁力下载需求。\n"
    "请回复以下链路之一：观影 PT 链 / BT 成人链\n"
    "对应含义：按观影资源流程处理 / 按成人 BT 归档流程处理"
)
BT_PROCESSING_PATH_CANCELLED_TEXT = "已取消当前 BT 处理链选择，请重新发送磁力或 BT 指令。"
BT_PROCESSING_PATH_PENDING_REMINDER_TEXT = (
    "当前正在等待 BT 处理链选择。\n"
    "请回复：观影 PT 链 / BT 成人链"
)
BT_PROCESSING_PATH_PENDING_BY_CHAT_KEY = "bt_processing_path_pending_by_chat"
_BT_PENDING_REPO_KEY = "bt_pending_repo"
_BT_PENDING_MISSING_AFTER_UPSERT_REASON = "bt_pending_state missing after upsert"
_BT_PENDING_CLEAR_RESULT_MISSING_REASON = "bt_pending_state clear result missing"
_BT_PENDING_STAGE_EMPTY_AFTER_READ_REASON = "bt_pending_state stage empty after read"


def _resolve_bt_processing_path_pending_by_chat(bot_data: MutableMapping[str, object]) -> dict[int, str]:
    pending_by_chat = bot_data.get(BT_PROCESSING_PATH_PENDING_BY_CHAT_KEY)
    if isinstance(pending_by_chat, dict):
        return pending_by_chat
    resolved_pending_by_chat: dict[int, str] = {}
    bot_data[BT_PROCESSING_PATH_PENDING_BY_CHAT_KEY] = resolved_pending_by_chat
    return resolved_pending_by_chat


def _resolve_bt_pending_repo(
    bot_data: MutableMapping[str, object],
    bt_pending_repo_key: str,
) -> BtPendingRepo | None:
    pending_repo = bot_data.get(bt_pending_repo_key)
    if isinstance(pending_repo, BtPendingRepo):
        return pending_repo
    return None


def _serialize_bt_pending_payload(payload: dict[str, object]) -> str:
    try:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return "{}"


def _deserialize_bt_pending_payload(payload_json: str) -> tuple[dict[str, object], str | None]:
    if not payload_json.strip():
        return {}, "payload_json empty"
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError:
        return {}, "payload_json invalid json"
    if not isinstance(payload, dict):
        return {}, "payload_json not object"
    return payload, None


def _log_bt_pending_payload_corruption(*, chat_id: int | None, stage: str, reason: str) -> None:
    print(
        f"\033[31m[BT 待处理载荷损坏]\033[0m chat_id={chat_id if chat_id is not None else '-'} stage={stage} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 bt_pending_state.payload_json 是否仍是合法 JSON，且包含当前 stage 需要的字段。",
        flush=True,
    )


def _log_bt_pending_clear_failed(*, chat_id: int | None, stage: str, reason: str) -> None:
    print(
        f"\033[31m[BT 待处理清理失败]\033[0m chat_id={chat_id if chat_id is not None else '-'} stage={stage} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 bt_pending_state 表删除是否正常；当前进程内待处理状态已尽量清掉，但重启后旧状态可能仍残留。",
        flush=True,
    )


def _log_bt_pending_clear_result_missing(*, chat_id: int | None, stage: str, reason: str) -> None:
    print(
        f"\033[31m[BT 待处理清理结果缺失]\033[0m chat_id={chat_id if chat_id is not None else '-'} stage={stage} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 bt_pending_state 删除返回是否仍带有明确结果；当前进程内待处理状态已尽量回滚，避免把缺失真相误判成已清理成功。",
        flush=True,
    )


def _log_bt_pending_read_failed(*, chat_id: int | None, stage: str, reason: str) -> None:
    print(
        f"\033[31m[BT 待处理读取失败]\033[0m chat_id={chat_id if chat_id is not None else '-'} stage={stage} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 bt_pending_state 表读取是否正常；当前相关入口会按状态不可用处理，避免把 SQLite 读取异常误判成“没有待处理状态”。",
        flush=True,
    )


def _log_bt_pending_row_corrupted(*, chat_id: int | None, stage: str, reason: str) -> None:
    print(
        f"\033[31m[BT 待处理记录损坏]\033[0m chat_id={chat_id if chat_id is not None else '-'} stage={stage} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 bt_pending_state.stage 是否仍是完整真相；当前相关入口会按状态不可用处理，避免把坏记录误判成“没有待处理状态”。",
        flush=True,
    )


def _is_bt_pending_row_corrupted_reason(reason: str) -> bool:
    return reason == _BT_PENDING_STAGE_EMPTY_AFTER_READ_REASON


def _log_bt_pending_persist_failed(*, chat_id: int | None, stage: str, reason: str) -> None:
    print(
        f"\033[31m[BT 待处理持久化失败]\033[0m chat_id={chat_id if chat_id is not None else '-'} stage={stage} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 bt_pending_state 表写入是否正常；当前进程内待处理状态仍保留，但重启后可能丢失这一步的上下文。",
        flush=True,
    )


def _log_bt_pending_missing_after_upsert(*, chat_id: int | None, stage: str, reason: str) -> None:
    print(
        f"\033[31m[BT 待处理写入后记录缺失]\033[0m chat_id={chat_id if chat_id is not None else '-'} stage={stage} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 bt_pending_state 表是否被并发删除或触发器回滚；"
        "如需继续当前 BT follow-up，请先确认 SQLite 写入后能立即回读该记录。",
        flush=True,
    )


def set_bt_processing_path_pending(
    *,
    bot_data: MutableMapping[str, object],
    chat_id: int | None,
    source: str,
    bt_pending_repo_key: str = _BT_PENDING_REPO_KEY,
) -> bool:
    if chat_id is None or chat_id <= 0:
        return False
    pending_by_chat = _resolve_bt_processing_path_pending_by_chat(bot_data)
    cleaned_source = source.strip()
    pending_by_chat[chat_id] = cleaned_source
    pending_repo = _resolve_bt_pending_repo(bot_data, bt_pending_repo_key)
    if pending_repo is None:
        return True
    try:
        pending_repo.upsert_pending(
            chat_id=chat_id,
            stage=BT_PENDING_STAGE_PROCESSING_PATH,
            payload_json=_serialize_bt_pending_payload({"source": cleaned_source}),
        )
    except BtPendingPersistenceError as error:
        if str(error) == _BT_PENDING_MISSING_AFTER_UPSERT_REASON:
            _log_bt_pending_missing_after_upsert(
                chat_id=chat_id,
                stage=BT_PENDING_STAGE_PROCESSING_PATH,
                reason=str(error),
            )
        else:
            _log_bt_pending_persist_failed(
                chat_id=chat_id,
                stage=BT_PENDING_STAGE_PROCESSING_PATH,
                reason=str(error),
            )
        pending_by_chat.pop(chat_id, None)
        return False
    except Exception as error:
        _log_bt_pending_persist_failed(
            chat_id=chat_id,
            stage=BT_PENDING_STAGE_PROCESSING_PATH,
            reason=str(error),
        )
        pending_by_chat.pop(chat_id, None)
        return False
    return True


def is_bt_processing_path_pending(
    *,
    bot_data: MutableMapping[str, object],
    chat_id: int | None,
    bt_pending_repo_key: str = _BT_PENDING_REPO_KEY,
) -> bool | None:
    if chat_id is None or chat_id <= 0:
        return False
    pending_by_chat = _resolve_bt_processing_path_pending_by_chat(bot_data)
    if chat_id in pending_by_chat:
        return True
    pending_repo = _resolve_bt_pending_repo(bot_data, bt_pending_repo_key)
    if pending_repo is None:
        return False
    try:
        pending_state = pending_repo.get_pending(chat_id=chat_id)
    except Exception as error:
        if _is_bt_pending_row_corrupted_reason(str(error)):
            _log_bt_pending_row_corrupted(
                chat_id=chat_id,
                stage=BT_PENDING_STAGE_PROCESSING_PATH,
                reason=str(error),
            )
        else:
            _log_bt_pending_read_failed(
                chat_id=chat_id,
                stage=BT_PENDING_STAGE_PROCESSING_PATH,
                reason=str(error),
            )
        return None
    if pending_state is None or pending_state.stage != BT_PENDING_STAGE_PROCESSING_PATH:
        return False
    payload, payload_error = _deserialize_bt_pending_payload(pending_state.payload_json)
    if payload_error is not None:
        _log_bt_pending_payload_corruption(chat_id=chat_id, stage=pending_state.stage, reason=payload_error)
        return None
    pending_source = str(payload.get("source", "")).strip()
    if not pending_source:
        _log_bt_pending_payload_corruption(
            chat_id=chat_id,
            stage=pending_state.stage,
            reason="payload.source missing",
        )
        return None
    pending_by_chat[chat_id] = pending_source
    return True


def clear_bt_processing_path_pending(
    *,
    bot_data: MutableMapping[str, object],
    chat_id: int | None,
    bt_pending_repo_key: str = _BT_PENDING_REPO_KEY,
) -> bool | None:
    if chat_id is None or chat_id <= 0:
        return False
    pending_by_chat = _resolve_bt_processing_path_pending_by_chat(bot_data)
    pending_source = pending_by_chat.pop(chat_id, None)
    cleared = pending_source is not None
    pending_repo = _resolve_bt_pending_repo(bot_data, bt_pending_repo_key)
    if pending_repo is None:
        return cleared
    try:
        cleared_result = pending_repo.clear_pending(chat_id=chat_id, expected_stage=BT_PENDING_STAGE_PROCESSING_PATH)
        if cleared_result is None:
            raise BtPendingPersistenceError(_BT_PENDING_CLEAR_RESULT_MISSING_REASON)
        return cleared_result or cleared
    except Exception as error:
        if str(error) == _BT_PENDING_CLEAR_RESULT_MISSING_REASON:
            _log_bt_pending_clear_result_missing(
                chat_id=chat_id,
                stage=BT_PENDING_STAGE_PROCESSING_PATH,
                reason=str(error),
            )
        else:
            _log_bt_pending_clear_failed(chat_id=chat_id, stage=BT_PENDING_STAGE_PROCESSING_PATH, reason=str(error))
        if isinstance(pending_source, str):
            pending_by_chat[chat_id] = pending_source
        return None


def pop_bt_processing_path_pending(
    *,
    bot_data: MutableMapping[str, object],
    chat_id: int | None,
    bt_pending_repo_key: str = _BT_PENDING_REPO_KEY,
) -> str | Literal[False] | None:
    if chat_id is None or chat_id <= 0:
        return None
    pending_by_chat = _resolve_bt_processing_path_pending_by_chat(bot_data)
    pending_source = pending_by_chat.pop(chat_id, None)
    if isinstance(pending_source, str):
        pending_repo = _resolve_bt_pending_repo(bot_data, bt_pending_repo_key)
        if pending_repo is not None:
            try:
                cleared_result = pending_repo.clear_pending(
                    chat_id=chat_id,
                    expected_stage=BT_PENDING_STAGE_PROCESSING_PATH,
                )
                if cleared_result is None:
                    raise BtPendingPersistenceError(_BT_PENDING_CLEAR_RESULT_MISSING_REASON)
            except Exception as error:
                pending_by_chat[chat_id] = pending_source
                if str(error) == _BT_PENDING_CLEAR_RESULT_MISSING_REASON:
                    _log_bt_pending_clear_result_missing(
                        chat_id=chat_id,
                        stage=BT_PENDING_STAGE_PROCESSING_PATH,
                        reason=str(error),
                    )
                else:
                    _log_bt_pending_clear_failed(
                        chat_id=chat_id,
                        stage=BT_PENDING_STAGE_PROCESSING_PATH,
                        reason=str(error),
                    )
                return False
        return pending_source

    pending_repo = _resolve_bt_pending_repo(bot_data, bt_pending_repo_key)
    if pending_repo is None:
        return None
    try:
        pending_state = pending_repo.get_pending(chat_id=chat_id)
    except Exception as error:
        if _is_bt_pending_row_corrupted_reason(str(error)):
            _log_bt_pending_row_corrupted(
                chat_id=chat_id,
                stage=BT_PENDING_STAGE_PROCESSING_PATH,
                reason=str(error),
            )
        else:
            _log_bt_pending_read_failed(
                chat_id=chat_id,
                stage=BT_PENDING_STAGE_PROCESSING_PATH,
                reason=str(error),
            )
        return None
    if pending_state is None or pending_state.stage != BT_PENDING_STAGE_PROCESSING_PATH:
        return None
    payload, payload_error = _deserialize_bt_pending_payload(pending_state.payload_json)
    if payload_error is not None:
        _log_bt_pending_payload_corruption(chat_id=chat_id, stage=pending_state.stage, reason=payload_error)
        return None
    pending_source = str(payload.get("source", "")).strip()
    if not pending_source:
        _log_bt_pending_payload_corruption(
            chat_id=chat_id,
            stage=pending_state.stage,
            reason="payload.source missing",
        )
        return None
    try:
        cleared_result = pending_repo.clear_pending(chat_id=chat_id, expected_stage=BT_PENDING_STAGE_PROCESSING_PATH)
        if cleared_result is None:
            raise BtPendingPersistenceError(_BT_PENDING_CLEAR_RESULT_MISSING_REASON)
    except Exception as error:
        pending_by_chat[chat_id] = pending_source
        if str(error) == _BT_PENDING_CLEAR_RESULT_MISSING_REASON:
            _log_bt_pending_clear_result_missing(
                chat_id=chat_id,
                stage=BT_PENDING_STAGE_PROCESSING_PATH,
                reason=str(error),
            )
        else:
            _log_bt_pending_clear_failed(chat_id=chat_id, stage=BT_PENDING_STAGE_PROCESSING_PATH, reason=str(error))
        return False
    return pending_source

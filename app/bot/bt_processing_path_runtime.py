from __future__ import annotations

import sqlite3
from collections.abc import MutableMapping
from typing import Literal

from app.bot.bt_pending_runtime import (
    BT_PENDING_CLEAR_RESULT_MISSING_REASON as _BT_PENDING_CLEAR_RESULT_MISSING_REASON,
    BT_PENDING_MISSING_AFTER_UPSERT_REASON as _BT_PENDING_MISSING_AFTER_UPSERT_REASON,
    BT_PENDING_REPO_KEY as _BT_PENDING_REPO_KEY,
    deserialize_bt_pending_payload as _deserialize_bt_pending_payload,
    is_bt_pending_row_corrupted_reason as _is_bt_pending_row_corrupted_reason,
    log_bt_pending_clear_failed as _log_bt_pending_clear_failed,
    log_bt_pending_clear_result_missing as _log_bt_pending_clear_result_missing,
    log_bt_pending_missing_after_upsert as _log_bt_pending_missing_after_upsert,
    log_bt_pending_payload_corruption as _log_bt_pending_payload_corruption,
    log_bt_pending_persist_failed as _log_bt_pending_persist_failed,
    log_bt_pending_read_failed as _log_bt_pending_read_failed,
    log_bt_pending_row_corrupted as _log_bt_pending_row_corrupted,
    resolve_bt_pending_repo as _resolve_bt_pending_repo,
    serialize_bt_pending_payload as _serialize_bt_pending_payload,
)
from app.db.bt_pending_repo import (
    BT_PENDING_STAGE_PROCESSING_PATH,
    BtPendingPersistenceError,
)

BT_PROCESSING_PATH_PROMPT_TEXT = (
    "已识别为直接磁力下载需求。\n"
    "请从以下链路中选择。\n"
    "\n"
    "处理链\n"
    "观影 PT 链：按观影资源流程处理\n"
    "BT 成人链：按成人 BT 归档流程处理\n"
    "\n"
    "下一步\n"
    "观影 PT 链：发送 观影 PT 链\n"
    "BT 成人链：发送 BT 成人链"
)
BT_PROCESSING_PATH_CANCELLED_TEXT = "已取消当前 BT 处理链选择，请重新发送磁力或 BT 指令。"
BT_PROCESSING_PATH_PENDING_REMINDER_TEXT = (
    "当前正在等待 BT 处理链选择。\n"
    "请从以下链路中选择。\n"
    "\n"
    "下一步\n"
    "观影 PT 链：发送 观影 PT 链\n"
    "BT 成人链：发送 BT 成人链"
)
BT_PROCESSING_PATH_PENDING_BY_CHAT_KEY = "bt_processing_path_pending_by_chat"


def _resolve_bt_processing_path_pending_by_chat(bot_data: MutableMapping[str, object]) -> dict[int, str]:
    pending_by_chat = bot_data.get(BT_PROCESSING_PATH_PENDING_BY_CHAT_KEY)
    if isinstance(pending_by_chat, dict):
        return pending_by_chat
    resolved_pending_by_chat: dict[int, str] = {}
    bot_data[BT_PROCESSING_PATH_PENDING_BY_CHAT_KEY] = resolved_pending_by_chat
    return resolved_pending_by_chat


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
    except sqlite3.Error as error:
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
    except (BtPendingPersistenceError, sqlite3.Error) as error:
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
    except (BtPendingPersistenceError, sqlite3.Error) as error:
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
            except (BtPendingPersistenceError, sqlite3.Error) as error:
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
    except (BtPendingPersistenceError, sqlite3.Error) as error:
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
    except (BtPendingPersistenceError, sqlite3.Error) as error:
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

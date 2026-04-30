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
    BT_PENDING_STAGE_CLASSIFICATION,
    BtPendingPersistenceError,
)

BT_CLASSIFICATION_PROMPT_TEXT = (
    "已记录后续处理链：影视入库链。\n"
    "请从以下媒体类型中选择。\n"
    "\n"
    "媒体类型\n"
    "movie：电影\n"
    "series：剧集\n"
    "anime：动漫\n"
    "\n"
    "下一步\n"
    "电影：发送 movie\n"
    "剧集：发送 series\n"
    "动漫：发送 anime"
)
BT_CLASSIFICATION_CANCELLED_TEXT = "已取消当前 BT 媒体类型选择，请重新发送磁力或 BT 指令。"
BT_CLASSIFICATION_PENDING_REMINDER_TEXT = (
    "当前正在等待 BT 媒体类型选择。\n"
    "请从以下媒体类型中选择。\n"
    "\n"
    "下一步\n"
    "电影：发送 movie\n"
    "剧集：发送 series\n"
    "动漫：发送 anime"
)
BT_CLASSIFICATION_PENDING_BY_CHAT_KEY = "bt_classification_pending_by_chat"


def _resolve_bt_classification_pending_by_chat(bot_data: MutableMapping[str, object]) -> dict[int, str]:
    pending_by_chat = bot_data.get(BT_CLASSIFICATION_PENDING_BY_CHAT_KEY)
    if isinstance(pending_by_chat, dict):
        return pending_by_chat
    resolved_pending_by_chat: dict[int, str] = {}
    bot_data[BT_CLASSIFICATION_PENDING_BY_CHAT_KEY] = resolved_pending_by_chat
    return resolved_pending_by_chat


def set_bt_classification_pending(
    *,
    bot_data: MutableMapping[str, object],
    chat_id: int | None,
    query: str,
    bt_pending_repo_key: str = _BT_PENDING_REPO_KEY,
) -> bool:
    if chat_id is None or chat_id <= 0:
        return False
    pending_by_chat = _resolve_bt_classification_pending_by_chat(bot_data)
    cleaned_query = query.strip()
    pending_by_chat[chat_id] = cleaned_query
    pending_repo = _resolve_bt_pending_repo(bot_data, bt_pending_repo_key)
    if pending_repo is None:
        return True
    try:
        pending_repo.upsert_pending(
            chat_id=chat_id,
            stage=BT_PENDING_STAGE_CLASSIFICATION,
            payload_json=_serialize_bt_pending_payload({"query": cleaned_query}),
        )
    except BtPendingPersistenceError as error:
        if str(error) == _BT_PENDING_MISSING_AFTER_UPSERT_REASON:
            _log_bt_pending_missing_after_upsert(
                chat_id=chat_id,
                stage=BT_PENDING_STAGE_CLASSIFICATION,
                reason=str(error),
            )
        else:
            _log_bt_pending_persist_failed(
                chat_id=chat_id,
                stage=BT_PENDING_STAGE_CLASSIFICATION,
                reason=str(error),
            )
        pending_by_chat.pop(chat_id, None)
        return False
    except sqlite3.Error as error:
        _log_bt_pending_persist_failed(
            chat_id=chat_id,
            stage=BT_PENDING_STAGE_CLASSIFICATION,
            reason=str(error),
        )
        pending_by_chat.pop(chat_id, None)
        return False
    return True


def is_bt_classification_pending(
    *,
    bot_data: MutableMapping[str, object],
    chat_id: int | None,
    bt_pending_repo_key: str = _BT_PENDING_REPO_KEY,
) -> bool | None:
    if chat_id is None or chat_id <= 0:
        return False
    pending_by_chat = _resolve_bt_classification_pending_by_chat(bot_data)
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
                stage=BT_PENDING_STAGE_CLASSIFICATION,
                reason=str(error),
            )
        else:
            _log_bt_pending_read_failed(
                chat_id=chat_id,
                stage=BT_PENDING_STAGE_CLASSIFICATION,
                reason=str(error),
            )
        return None
    if pending_state is None or pending_state.stage != BT_PENDING_STAGE_CLASSIFICATION:
        return False
    payload, payload_error = _deserialize_bt_pending_payload(pending_state.payload_json)
    if payload_error is not None:
        _log_bt_pending_payload_corruption(chat_id=chat_id, stage=pending_state.stage, reason=payload_error)
        return None
    pending_query = str(payload.get("query", "")).strip()
    if not pending_query:
        _log_bt_pending_payload_corruption(
            chat_id=chat_id,
            stage=pending_state.stage,
            reason="payload.query missing",
        )
        return None
    pending_by_chat[chat_id] = pending_query
    return True


def clear_bt_classification_pending(
    *,
    bot_data: MutableMapping[str, object],
    chat_id: int | None,
    bt_pending_repo_key: str = _BT_PENDING_REPO_KEY,
) -> bool | None:
    if chat_id is None or chat_id <= 0:
        return False
    pending_by_chat = _resolve_bt_classification_pending_by_chat(bot_data)
    pending_query = pending_by_chat.pop(chat_id, None)
    cleared = pending_query is not None
    pending_repo = _resolve_bt_pending_repo(bot_data, bt_pending_repo_key)
    if pending_repo is None:
        return cleared
    try:
        cleared_result = pending_repo.clear_pending(chat_id=chat_id, expected_stage=BT_PENDING_STAGE_CLASSIFICATION)
        if cleared_result is None:
            raise BtPendingPersistenceError(_BT_PENDING_CLEAR_RESULT_MISSING_REASON)
        return cleared_result or cleared
    except (BtPendingPersistenceError, sqlite3.Error) as error:
        if str(error) == _BT_PENDING_CLEAR_RESULT_MISSING_REASON:
            _log_bt_pending_clear_result_missing(
                chat_id=chat_id,
                stage=BT_PENDING_STAGE_CLASSIFICATION,
                reason=str(error),
            )
        else:
            _log_bt_pending_clear_failed(chat_id=chat_id, stage=BT_PENDING_STAGE_CLASSIFICATION, reason=str(error))
        if isinstance(pending_query, str):
            pending_by_chat[chat_id] = pending_query
        return None


def pop_bt_classification_pending(
    *,
    bot_data: MutableMapping[str, object],
    chat_id: int | None,
    bt_pending_repo_key: str = _BT_PENDING_REPO_KEY,
) -> str | Literal[False] | None:
    if chat_id is None or chat_id <= 0:
        return None
    pending_by_chat = _resolve_bt_classification_pending_by_chat(bot_data)
    pending_query = pending_by_chat.pop(chat_id, None)
    if isinstance(pending_query, str):
        pending_repo = _resolve_bt_pending_repo(bot_data, bt_pending_repo_key)
        if pending_repo is not None:
            try:
                cleared_result = pending_repo.clear_pending(
                    chat_id=chat_id,
                    expected_stage=BT_PENDING_STAGE_CLASSIFICATION,
                )
                if cleared_result is None:
                    raise BtPendingPersistenceError(_BT_PENDING_CLEAR_RESULT_MISSING_REASON)
            except (BtPendingPersistenceError, sqlite3.Error) as error:
                pending_by_chat[chat_id] = pending_query
                if str(error) == _BT_PENDING_CLEAR_RESULT_MISSING_REASON:
                    _log_bt_pending_clear_result_missing(
                        chat_id=chat_id,
                        stage=BT_PENDING_STAGE_CLASSIFICATION,
                        reason=str(error),
                    )
                else:
                    _log_bt_pending_clear_failed(
                        chat_id=chat_id,
                        stage=BT_PENDING_STAGE_CLASSIFICATION,
                        reason=str(error),
                    )
                return False
        return pending_query

    pending_repo = _resolve_bt_pending_repo(bot_data, bt_pending_repo_key)
    if pending_repo is None:
        return None
    try:
        pending_state = pending_repo.get_pending(chat_id=chat_id)
    except (BtPendingPersistenceError, sqlite3.Error) as error:
        if _is_bt_pending_row_corrupted_reason(str(error)):
            _log_bt_pending_row_corrupted(
                chat_id=chat_id,
                stage=BT_PENDING_STAGE_CLASSIFICATION,
                reason=str(error),
            )
        else:
            _log_bt_pending_read_failed(
                chat_id=chat_id,
                stage=BT_PENDING_STAGE_CLASSIFICATION,
                reason=str(error),
            )
        return None
    if pending_state is None or pending_state.stage != BT_PENDING_STAGE_CLASSIFICATION:
        return None
    payload, payload_error = _deserialize_bt_pending_payload(pending_state.payload_json)
    if payload_error is not None:
        _log_bt_pending_payload_corruption(chat_id=chat_id, stage=pending_state.stage, reason=payload_error)
        return None
    pending_query = str(payload.get("query", "")).strip()
    if not pending_query:
        _log_bt_pending_payload_corruption(
            chat_id=chat_id,
            stage=pending_state.stage,
            reason="payload.query missing",
        )
        return None
    try:
        cleared_result = pending_repo.clear_pending(chat_id=chat_id, expected_stage=BT_PENDING_STAGE_CLASSIFICATION)
        if cleared_result is None:
            raise BtPendingPersistenceError(_BT_PENDING_CLEAR_RESULT_MISSING_REASON)
    except (BtPendingPersistenceError, sqlite3.Error) as error:
        pending_by_chat[chat_id] = pending_query
        if str(error) == _BT_PENDING_CLEAR_RESULT_MISSING_REASON:
            _log_bt_pending_clear_result_missing(
                chat_id=chat_id,
                stage=BT_PENDING_STAGE_CLASSIFICATION,
                reason=str(error),
            )
        else:
            _log_bt_pending_clear_failed(chat_id=chat_id, stage=BT_PENDING_STAGE_CLASSIFICATION, reason=str(error))
        return False
    return pending_query

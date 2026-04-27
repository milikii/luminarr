from __future__ import annotations

import sqlite3
from collections.abc import Awaitable, Callable

from telegram import Update
from telegram.ext import ContextTypes

from app.db.telegram_update_repo import TelegramUpdatePersistenceError
from app.db.telegram_update_repo import TelegramUpdateRepo


def build_telegram_reply_func(
    reply_func: Callable[[str], Awaitable[object]],
    *,
    formatter: Callable[[str], str],
) -> Callable[[str], Awaitable[object]]:
    async def wrapped(text: str) -> object:
        return await reply_func(formatter(text))

    return wrapped


def resolve_telegram_chat_id(
    update: Update,
    *,
    callback_query: object | None = None,
) -> int | None:
    chat = getattr(update, "effective_chat", None)
    chat_id = getattr(chat, "id", None)
    if isinstance(chat_id, int):
        return chat_id

    if callback_query is None:
        return None

    message = getattr(callback_query, "message", None)
    callback_chat = getattr(message, "chat", None)
    callback_chat_id = getattr(callback_chat, "id", None)
    if isinstance(callback_chat_id, int):
        return callback_chat_id
    return None


def resolve_telegram_user_id(
    update: Update,
    *,
    callback_query: object | None = None,
) -> int | None:
    user = getattr(update, "effective_user", None)
    user_id = getattr(user, "id", None)
    if isinstance(user_id, int):
        return user_id

    if callback_query is None:
        return None

    callback_user = getattr(callback_query, "from_user", None)
    callback_user_id = getattr(callback_user, "id", None)
    if isinstance(callback_user_id, int):
        return callback_user_id
    return None


def resolve_telegram_callback_message(update: Update, callback_query: object) -> object | None:
    message = getattr(update, "effective_message", None)
    if message is not None:
        return message
    return getattr(callback_query, "message", None)


def record_telegram_message_update(
    *,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    telegram_update_repo_key: str,
) -> bool:
    update_repo = context.application.bot_data.get(telegram_update_repo_key)
    if not isinstance(update_repo, TelegramUpdateRepo):
        return True

    update_id = getattr(update, "update_id", 0)
    if not isinstance(update_id, int):
        return True

    chat_id = resolve_telegram_chat_id(update)
    user_id = resolve_telegram_user_id(update)
    try:
        recorded = update_repo.record_message_update(
            update_id=update_id,
            chat_id=chat_id,
            user_id=user_id,
        )
        if recorded is None:
            raise TelegramUpdatePersistenceError("telegram update record result missing")
        return recorded
    except (TelegramUpdatePersistenceError, sqlite3.Error) as error:
        _log_telegram_update_record_error(
            source_type="message",
            source_id=str(update_id),
            chat_id=chat_id,
            user_id=user_id,
            error=error,
        )
        return False


def record_telegram_callback_update(
    *,
    callback_query_id: str,
    chat_id: int | None,
    user_id: int | None,
    context: ContextTypes.DEFAULT_TYPE,
    telegram_update_repo_key: str,
) -> bool:
    update_repo = context.application.bot_data.get(telegram_update_repo_key)
    if not isinstance(update_repo, TelegramUpdateRepo):
        return True

    try:
        recorded = update_repo.record_callback_update(
            callback_query_id=callback_query_id,
            chat_id=chat_id,
            user_id=user_id,
        )
        if recorded is None:
            raise TelegramUpdatePersistenceError("telegram update record result missing")
        return recorded
    except (TelegramUpdatePersistenceError, sqlite3.Error) as error:
        _log_telegram_update_record_error(
            source_type="callback",
            source_id=callback_query_id,
            chat_id=chat_id,
            user_id=user_id,
            error=error,
        )
        return False


def _log_telegram_update_record_error(
    *,
    source_type: str,
    source_id: str,
    chat_id: int | None,
    user_id: int | None,
    error: Exception,
) -> None:
    error_text = str(error)
    if error_text == "telegram update record result missing":
        print(
            f"\033[31m[Telegram 更新去重结果缺失]\033[0m source_type={source_type} "
            f"source_id={source_id.strip() or '-'} chat_id={chat_id if chat_id is not None else '-'} "
            f"user_id={user_id if user_id is not None else '-'} 原因={error_text}\n"
            "\033[33m[处理建议]\033[0m 检查 telegram_updates 写入返回是否仍带有明确布尔结果；"
            "当前 update 会停止继续处理，避免把去重真相缺口误判成普通重复消息。",
            flush=True,
        )
        return

    print(
        f"\033[31m[Telegram 更新去重落盘失败]\033[0m source_type={source_type} "
        f"source_id={source_id.strip() or '-'} chat_id={chat_id if chat_id is not None else '-'} "
        f"user_id={user_id if user_id is not None else '-'} 原因={error_text}\n"
        "\033[33m[处理建议]\033[0m 检查 SQLite/telegram_updates 表写入是否正常；"
        "当前 update 会停止继续处理，避免在去重真相缺失时重复执行副作用。",
        flush=True,
    )

from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping

from app.bot.bt_classification_runtime import clear_bt_classification_pending
from app.bot.bt_processing_path_runtime import (
    BT_PROCESSING_PATH_PROMPT_TEXT,
    clear_bt_processing_path_pending,
    set_bt_processing_path_pending,
)
from app.bot.bt_tmdb_association_runtime import clear_bt_tmdb_association_pending
from app.bot.query_text_runtime import is_bt_direct_intent
from app.bot.raw_bt_destination_runtime import clear_raw_bt_destination_pending

PrivateChatReplyFunc = Callable[[str], Awaitable[object]]


async def handle_bt_direct_intent_query(
    *,
    query: str,
    bot_data: MutableMapping[str, object],
    reply_func: PrivateChatReplyFunc,
    chat_id: int | None,
    tg,
) -> bool:
    if not is_bt_direct_intent(query):
        return False
    cleared_processing_path = clear_bt_processing_path_pending(
        bot_data=bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=tg.BT_PENDING_REPO_KEY,
    )
    if cleared_processing_path is None:
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True
    cleared_raw_bt_destination = clear_raw_bt_destination_pending(
        bot_data=bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=tg.BT_PENDING_REPO_KEY,
    )
    if cleared_raw_bt_destination is None:
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True
    cleared_tmdb_association = clear_bt_tmdb_association_pending(
        bot_data=bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=tg.BT_PENDING_REPO_KEY,
    )
    if cleared_tmdb_association is None:
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True
    cleared_classification = clear_bt_classification_pending(
        bot_data=bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=tg.BT_PENDING_REPO_KEY,
    )
    if cleared_classification is None:
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True
    if not set_bt_processing_path_pending(
        bot_data=bot_data,
        chat_id=chat_id,
        source=query,
        bt_pending_repo_key=tg.BT_PENDING_REPO_KEY,
    ):
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True
    await reply_func(BT_PROCESSING_PATH_PROMPT_TEXT)
    return True

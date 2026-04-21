from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping

from app.bot.bt_classification_runtime import pop_bt_classification_pending
from app.bot.private_chat_bt_processing_runtime import (
    build_media_import_bt_flow_reply,
    clear_bt_follow_up_conflicts,
)

PrivateChatReplyFunc = Callable[[str], Awaitable[object]]


async def handle_bt_classification_follow_up(
    *,
    bot_data: MutableMapping[str, object],
    reply_func: PrivateChatReplyFunc,
    chat_id: int | None,
    bt_classification_pending: bool,
    bt_classification: str | None,
    tg,
) -> bool:
    if bt_classification is None or not bt_classification_pending:
        return False
    bt_source = pop_bt_classification_pending(
        bot_data=bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=tg.BT_PENDING_REPO_KEY,
    )
    if bt_source is False or not bt_source:
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True
    if clear_bt_follow_up_conflicts(
        bot_data=bot_data,
        chat_id=chat_id,
        tg=tg,
    ) is None:
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True
    await reply_func(
        build_media_import_bt_flow_reply(
            bot_data=bot_data,
            chat_id=chat_id,
            source=bt_source,
            media_kind=bt_classification,
            tg=tg,
        )
    )
    return True

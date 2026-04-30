from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping

from app.bot.query_text_runtime import is_duplicate_override_text

PrivateChatReplyFunc = Callable[[str], Awaitable[object]]


async def handle_bt_duplicate_override_follow_up(
    *,
    query: str,
    bot_data: MutableMapping[str, object],
    execution_gate,
    reply_func: PrivateChatReplyFunc,
    chat_id: int | None,
    tg,
) -> bool:
    if not is_duplicate_override_text(query):
        return False
    add_service = bot_data.get(tg.ADD_TO_DOWNLOADER_SERVICE_KEY)
    if not isinstance(add_service, tg.AddToDownloaderService):
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True
    reply = await execution_gate.run(
        tg.ACTION_ADD_TO_DOWNLOADER,
        lambda: add_service.continue_duplicate_add(chat_id=chat_id),
    )
    await reply_func(reply)
    return True

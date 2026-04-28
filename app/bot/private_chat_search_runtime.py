from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping

from app.bot.search_recovery_runtime import search_with_reactive_recovery

PrivateChatReplyFunc = Callable[[str], Awaitable[object]]
SEARCH_CAPABILITY_UNAVAILABLE_TEXT_BOT_DATA_KEY = "search_capability_unavailable_text"
SEARCH_CAPABILITY_UNAVAILABLE_TEXT = (
    "搜索能力当前不可用：缺少 PROWLARR_BASE_URL / PROWLARR_API_KEY。\n"
    "请补齐配置后重试。"
)


async def _handle_bt_pending_reminders(
    *,
    reply_func: PrivateChatReplyFunc,
    bt_processing_path_pending: bool,
    bt_classification_pending: bool,
    tg,
) -> bool:
    if bt_processing_path_pending:
        await reply_func(tg.BT_PROCESSING_PATH_PENDING_REMINDER_TEXT)
        return True
    if bt_classification_pending:
        await reply_func(tg.BT_CLASSIFICATION_PENDING_REMINDER_TEXT)
        return True
    return False


async def handle_search_query_fallback(
    *,
    bot_data: MutableMapping[str, object],
    execution_gate,
    reply_func: PrivateChatReplyFunc,
    query: str,
    chat_id: int | None,
    channel: str,
    bt_processing_path_pending: bool,
    bt_classification_pending: bool,
    tg,
) -> bool:
    search_service = bot_data.get(tg.SEARCH_SERVICE_KEY)
    if not isinstance(search_service, tg.SearchMediaService):
        unavailable_text = bot_data.get(SEARCH_CAPABILITY_UNAVAILABLE_TEXT_BOT_DATA_KEY)
        if isinstance(unavailable_text, str) and unavailable_text.strip():
            await reply_func(unavailable_text.strip())
        else:
            await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True
    unavailable_text = bot_data.get(SEARCH_CAPABILITY_UNAVAILABLE_TEXT_BOT_DATA_KEY)
    if isinstance(unavailable_text, str) and unavailable_text.strip():
        await reply_func(unavailable_text.strip())
        return True
    if await _handle_bt_pending_reminders(
        reply_func=reply_func,
        bt_processing_path_pending=bt_processing_path_pending,
        bt_classification_pending=bt_classification_pending,
        tg=tg,
    ):
        return True
    reply = await execution_gate.run(
        tg.ACTION_SEARCH_MEDIA,
        lambda: search_with_reactive_recovery(
            search_service=search_service,
            query=query,
            chat_id=chat_id,
            channel=channel,
            safe_text=tg.LLM_PHYSICAL_FAILURE_SAFE_TEXT,
        ),
    )
    await reply_func(reply)
    return True

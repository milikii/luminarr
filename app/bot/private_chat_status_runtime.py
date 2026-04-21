from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping

PrivateChatReplyFunc = Callable[[str], Awaitable[object]]


async def handle_status_query(
    *,
    query: str,
    bot_data: MutableMapping[str, object],
    execution_gate,
    reply_func: PrivateChatReplyFunc,
    chat_id: int | None,
    channel: str,
    tg,
) -> bool:
    task_ref = tg.parse_status_query(query)
    if task_ref is None:
        return False

    status_service = bot_data.get(tg.GET_DOWNLOAD_STATUS_SERVICE_KEY)
    if not isinstance(status_service, tg.GetDownloadStatusService):
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True

    reply = await execution_gate.run(
        tg.ACTION_GET_DOWNLOAD_STATUS,
        lambda: status_service.get_status_text(task_ref, chat_id=chat_id, channel=channel),
    )
    await reply_func(reply)
    return True

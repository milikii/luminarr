from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping

PrivateChatReplyFunc = Callable[[str], Awaitable[object]]
ResolveDownloaderExecutionFunc = Callable[[], tuple[object | None, str | None]]


async def handle_digit_selection_query(
    *,
    bot_data: MutableMapping[str, object],
    execution_gate,
    reply_func: PrivateChatReplyFunc,
    query: str,
    chat_id: int | None,
    user_id: int | None,
    channel: str,
    resolve_downloader_execution: ResolveDownloaderExecutionFunc,
    tg,
) -> bool:
    if not query.isdigit():
        return False
    search_service = bot_data.get(tg.SEARCH_SERVICE_KEY)
    if isinstance(search_service, tg.SearchMediaService) and chat_id is not None:
        clarification_pending = search_service.is_clarification_pending(chat_id)
        if clarification_pending is None:
            await reply_func(tg.SERVICE_NOT_READY_TEXT)
            return True
        if clarification_pending:
            await reply_func(tg.CLARIFICATION_SELECTION_BLOCKED_TEXT)
            return True

    add_service = bot_data.get(tg.ADD_TO_DOWNLOADER_SERVICE_KEY)
    if not isinstance(add_service, tg.AddToDownloaderService):
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True
    if chat_id is None:
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True
    downloader_execution, resolution_error = resolve_downloader_execution()
    if resolution_error is not None:
        await reply_func(resolution_error)
        return True
    reply = await execution_gate.run(
        tg.ACTION_ADD_TO_DOWNLOADER,
        lambda: add_service.add_by_selection(
            chat_id,
            query,
            user_id=user_id,
            channel=channel,
            downloader_name=downloader_execution.name if downloader_execution is not None else "",
            downloader_type=downloader_execution.downloader_type if downloader_execution is not None else "transmission",
            download_dir=downloader_execution.download_dir if downloader_execution is not None else "",
        ),
    )
    await reply_func(reply)
    return True

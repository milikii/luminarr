from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping

PrivateChatReplyFunc = Callable[[str], Awaitable[object]]


async def handle_import_query(
    *,
    query: str,
    bot_data: MutableMapping[str, object],
    execution_gate,
    reply_func: PrivateChatReplyFunc,
    chat_id: int | None,
    user_id: int | None,
    tg,
) -> bool:
    import_ref = tg.parse_import_query(query)
    if import_ref is None:
        return False

    import_service = bot_data.get(tg.IMPORT_TO_LIBRARY_SERVICE_KEY)
    if not isinstance(import_service, tg.ImportToLibraryService):
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True

    reply = await execution_gate.run(
        tg.ACTION_IMPORT_TO_LIBRARY,
        lambda: import_service.auto_import_by_task_ref(
            import_ref,
            chat_id=chat_id,
            user_id=user_id,
        ),
    )
    await reply_func(reply)
    return True

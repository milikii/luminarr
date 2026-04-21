from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping

from app.bot.execution_runtime import run_sync_with_policy, watchlist_policy_action

PrivateChatReplyFunc = Callable[[str], Awaitable[object]]


async def handle_watchlist_query(
    *,
    query: str,
    bot_data: MutableMapping[str, object],
    execution_gate,
    reply_func: PrivateChatReplyFunc,
    chat_id: int | None,
    tg,
) -> bool:
    watchlist_command = tg.parse_watchlist_query(query)
    if watchlist_command is None:
        return False

    watchlist_service = bot_data.get(tg.MANAGE_WATCHLIST_SERVICE_KEY)
    if not isinstance(watchlist_service, tg.ManageWatchlistService):
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True

    reply = await run_sync_with_policy(
        execution_gate,
        watchlist_policy_action(watchlist_command.action),
        lambda: watchlist_service.handle(
            watchlist_command,
            chat_id=chat_id,
        ),
    )
    await reply_func(reply)
    return True

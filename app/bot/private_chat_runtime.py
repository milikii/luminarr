from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping
from types import SimpleNamespace

from app.bot.telegram_bot import handle_private_chat_query_text


async def dispatch_private_chat_text(
    *,
    query: str,
    reply_func: Callable[[str], Awaitable[object]],
    chat_id: int | None,
    user_id: int | None,
    bot_data: MutableMapping[str, object],
) -> None:
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data=bot_data,
        )
    )
    await handle_private_chat_query_text(
        query=query,
        reply_func=reply_func,
        chat_id=chat_id,
        user_id=user_id,
        context=context,
    )

from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping
from pathlib import Path

from app.trace_logging import TRACE_LOG_PATH_BOT_DATA_KEY, log_trace_event

PrivateChatReplyFunc = Callable[[str], Awaitable[object]]


def prepare_private_chat_reply_with_trace(
    *,
    bot_data: MutableMapping[str, object],
    reply_func: PrivateChatReplyFunc,
    channel: str,
    chat_id: int | None,
    user_id: int | None,
    query: str,
) -> PrivateChatReplyFunc:
    trace_log_path = _resolve_trace_log_path(bot_data)
    _log_private_chat_inbound(
        trace_log_path=trace_log_path,
        channel=channel,
        chat_id=chat_id,
        user_id=user_id,
        query=query,
    )

    async def reply_with_trace(reply_text: str) -> object:
        result = await reply_func(reply_text)
        log_trace_event(
            scope="private_chat",
            event="reply",
            result="sent",
            log_path=trace_log_path,
            channel=channel,
            action="reply",
            chat_id=chat_id,
            user_id=user_id,
            query=query,
            reply_text=reply_text,
        )
        return result

    return reply_with_trace


def _resolve_trace_log_path(bot_data: MutableMapping[str, object]) -> Path | None:
    trace_log_path = bot_data.get(TRACE_LOG_PATH_BOT_DATA_KEY)
    if isinstance(trace_log_path, Path):
        return trace_log_path
    return None


def _log_private_chat_inbound(
    *,
    trace_log_path: Path | None,
    channel: str,
    chat_id: int | None,
    user_id: int | None,
    query: str,
) -> None:
    log_trace_event(
        scope="private_chat",
        event="inbound",
        result="received",
        log_path=trace_log_path,
        channel=channel,
        action="query",
        chat_id=chat_id,
        user_id=user_id,
        query=query,
    )

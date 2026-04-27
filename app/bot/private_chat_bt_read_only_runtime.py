from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping

from app.bot.query_text_runtime import (
    extract_bt_batch_preview_request,
    extract_bt_read_only_query,
)
from app.operational_logging import format_operational_log_message

PrivateChatReplyFunc = Callable[[str], Awaitable[object]]


def _log_bt_read_only_helper_error(*, query: str, error: Exception) -> None:
    print(
        format_operational_log_message(
            title="BT 只读探索失败",
            detail=f"查询={query} 原因={error}",
            fix_hint="检查 BT 来源配置、站点可达性和网络连通性后重试。",
        ),
        flush=True,
    )


async def _run_bt_read_only_request(
    *,
    bot_data: MutableMapping[str, object],
    execution_gate,
    reply_func: PrivateChatReplyFunc,
    search_runner: Callable[[object], object],
    helper_query: str,
    tg,
) -> bool:
    search_service = bot_data.get(tg.SEARCH_SERVICE_KEY)
    if not isinstance(search_service, tg.SearchMediaService):
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True
    try:
        reply = await execution_gate.run(
            tg.ACTION_BT_READ_ONLY_HELPER,
            lambda: search_runner(search_service),
        )
    except Exception as error:
        _log_bt_read_only_helper_error(query=helper_query, error=error)
        await reply_func(tg.BT_READ_ONLY_HELPER_FAILED_TEXT)
        return True
    await reply_func(reply)
    return True


async def handle_bt_read_only_query(
    *,
    query: str,
    bot_data: MutableMapping[str, object],
    execution_gate,
    reply_func: PrivateChatReplyFunc,
    chat_id: int | None,
    tg,
) -> bool:
    bt_read_only_query = extract_bt_read_only_query(query)
    if bt_read_only_query:
        return await _run_bt_read_only_request(
            bot_data=bot_data,
            execution_gate=execution_gate,
            reply_func=reply_func,
            search_runner=lambda search_service: search_service.search_bt_read_only_and_format(bt_read_only_query),
            helper_query=bt_read_only_query,
            tg=tg,
        )

    bt_batch_preview_request = extract_bt_batch_preview_request(query)
    if bt_batch_preview_request is None:
        return False

    return await _run_bt_read_only_request(
        bot_data=bot_data,
        execution_gate=execution_gate,
        reply_func=reply_func,
        search_runner=lambda search_service: search_service.search_bt_batch_preview_and_format_for_chat(
            bt_batch_preview_request,
            chat_id=chat_id,
        ),
        helper_query=bt_batch_preview_request.query,
        tg=tg,
    )

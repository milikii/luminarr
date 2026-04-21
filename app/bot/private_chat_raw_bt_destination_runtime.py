from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping

from app.bot.raw_bt_destination_runtime import (
    clear_raw_bt_destination_pending,
    get_raw_bt_destination_pending,
    handle_raw_bt_destination_query as handle_shared_raw_bt_destination_query,
    log_pure_bt_search_error,
)

PrivateChatReplyFunc = Callable[[str], Awaitable[object]]


async def handle_raw_bt_destination_follow_up(
    *,
    bot_data: MutableMapping[str, object],
    reply_func: PrivateChatReplyFunc,
    query: str,
    chat_id: int | None,
    user_id: int | None,
    resolve_downloader_execution: Callable[[], tuple[object | None, str | None]],
    tg,
) -> bool:
    raw_bt_destination_pending = get_raw_bt_destination_pending(
        bot_data=bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=tg.BT_PENDING_REPO_KEY,
    )
    if raw_bt_destination_pending is False:
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True
    if raw_bt_destination_pending is None:
        return False
    reply = await handle_shared_raw_bt_destination_query(
        query=query,
        pending=raw_bt_destination_pending,
        chat_id=chat_id,
        user_id=user_id,
        bot_data=bot_data,
        add_to_downloader_service_key=tg.ADD_TO_DOWNLOADER_SERVICE_KEY,
        search_service_key=tg.SEARCH_SERVICE_KEY,
        clear_pending=lambda: clear_raw_bt_destination_pending(
            bot_data=bot_data,
            chat_id=chat_id,
            bt_pending_repo_key=tg.BT_PENDING_REPO_KEY,
        ),
        resolve_downloader_execution=resolve_downloader_execution,
        log_pure_bt_search_error=lambda pure_bt_query, error: log_pure_bt_search_error(
            query=pure_bt_query,
            error=error,
        ),
        service_not_ready_text=tg.SERVICE_NOT_READY_TEXT,
        bt_source_required_text=tg.BT_SOURCE_REQUIRED_TEXT,
        pure_bt_search_failed_text=tg.PURE_BT_SEARCH_FAILED_TEXT,
        pure_bt_candidate_selected_template=tg.PURE_BT_CANDIDATE_SELECTED_TEMPLATE,
        pure_bt_candidate_not_found_template=tg.PURE_BT_CANDIDATE_NOT_FOUND_TEMPLATE,
    )
    await reply_func(reply)
    return True

from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping

from app.bot.bt_tmdb_association_runtime import (
    clear_bt_tmdb_association_pending,
    get_bt_tmdb_association_pending,
    log_bt_tmdb_association_error,
    resolve_bt_tmdb_candidates_lookup,
)
from app.bot.bt_tmdb_association_runtime import (
    handle_bt_tmdb_association_query as handle_shared_bt_tmdb_association_query,
)

PrivateChatReplyFunc = Callable[[str], Awaitable[object]]


async def handle_bt_tmdb_follow_up(
    *,
    bot_data: MutableMapping[str, object],
    reply_func: PrivateChatReplyFunc,
    query: str,
    chat_id: int | None,
    user_id: int | None,
    resolve_downloader_execution: Callable[[], tuple[object | None, str | None]],
    tg,
) -> bool:
    bt_tmdb_pending = get_bt_tmdb_association_pending(
        bot_data=bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=tg.BT_PENDING_REPO_KEY,
    )
    if bt_tmdb_pending is False:
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True
    if bt_tmdb_pending is None:
        return False
    reply = await handle_shared_bt_tmdb_association_query(
        query=query,
        pending=bt_tmdb_pending,
        chat_id=chat_id,
        user_id=user_id,
        bot_data=bot_data,
        add_to_downloader_service_key=tg.ADD_TO_DOWNLOADER_SERVICE_KEY,
        clear_pending=lambda: clear_bt_tmdb_association_pending(
            bot_data=bot_data,
            chat_id=chat_id,
            bt_pending_repo_key=tg.BT_PENDING_REPO_KEY,
        ),
        resolve_candidates_lookup=lambda media_kind: resolve_bt_tmdb_candidates_lookup(
            bot_data=bot_data,
            media_kind=media_kind,
            bt_tmdb_movie_candidates_lookup_key=tg.BT_TMDB_MOVIE_CANDIDATES_LOOKUP_KEY,
            bt_tmdb_tv_candidates_lookup_key=tg.BT_TMDB_TV_CANDIDATES_LOOKUP_KEY,
        ),
        resolve_downloader_execution=resolve_downloader_execution,
        log_bt_tmdb_association_error=lambda media_kind, raw_query, error: log_bt_tmdb_association_error(
            media_kind=media_kind,
            query=raw_query,
            error=error,
        ),
        service_not_ready_text=tg.SERVICE_NOT_READY_TEXT,
        bt_tmdb_association_service_not_ready_text=tg.BT_TMDB_ASSOCIATION_SERVICE_NOT_READY_TEXT,
        bt_source_required_text=tg.BT_SOURCE_REQUIRED_TEXT,
    )
    await reply_func(reply)
    return True

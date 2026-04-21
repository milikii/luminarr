from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping

from app.bot.bt_classification_runtime import (
    is_bt_classification_pending,
    pop_bt_classification_pending,
)
from app.bot.bt_processing_path_runtime import (
    is_bt_processing_path_pending,
)
from app.bot.private_chat_bt_processing_runtime import (
    build_media_import_bt_flow_reply,
    clear_bt_follow_up_conflicts,
    handle_bt_processing_path_follow_up,
)
from app.bot.bt_tmdb_association_runtime import (
    clear_bt_tmdb_association_pending,
    get_bt_tmdb_association_pending,
    handle_bt_tmdb_association_query as handle_shared_bt_tmdb_association_query,
    log_bt_tmdb_association_error,
    resolve_bt_tmdb_candidates_lookup,
)
from app.bot.downloader_execution_runtime import resolve_bound_downloader_execution as resolve_shared_bound_downloader_execution
from app.bot.execution_runtime import (
    resolve_execution_gate,
    run_sync_with_policy,
)
from app.bot.private_chat_bt_direct_runtime import (
    handle_bt_direct_intent_query as handle_shared_bt_direct_intent_query,
)
from app.bot.private_chat_bt_batch_confirm_runtime import (
    handle_bt_batch_confirm_query as handle_shared_bt_batch_confirm_query,
)
from app.bot.private_chat_bt_read_only_runtime import (
    handle_bt_read_only_query as handle_shared_bt_read_only_query,
)
from app.bot.private_chat_bt_subscription_runtime import (
    handle_bt_subscription_query as handle_shared_bt_subscription_query,
)
from app.bot.private_chat_cleanup_runtime import (
    handle_cleanup_query as handle_shared_cleanup_query,
)
from app.bot.private_chat_frustration_runtime import (
    handle_frustration_query as handle_shared_frustration_query,
)
from app.bot.query_text_runtime import (
    parse_bt_classification_choice,
    parse_bt_processing_path_choice,
    parse_bt_processing_path_legacy_shortcut,
)
from app.bot.private_chat_confirm_runtime import handle_confirm_query as handle_shared_confirm_query
from app.bot.private_chat_selection_runtime import handle_digit_selection_query as handle_shared_digit_selection_query
from app.bot.raw_bt_destination_runtime import (
    clear_raw_bt_destination_pending,
    get_raw_bt_destination_pending,
    handle_raw_bt_destination_query as handle_shared_raw_bt_destination_query,
    log_pure_bt_search_error,
)
from app.bot import telegram_bot as telegram_runtime
from app.bot.private_chat_import_runtime import handle_import_query as handle_shared_import_query
from app.bot.private_chat_login_runtime import handle_personal_wechat_login_query as handle_shared_personal_wechat_login_query
from app.bot.private_chat_search_runtime import handle_search_query_fallback as handle_shared_search_query_fallback
from app.bot.private_chat_status_runtime import handle_status_query as handle_shared_status_query
from app.bot.private_chat_trace_runtime import prepare_private_chat_reply_with_trace
from app.bot.private_chat_watchlist_runtime import handle_watchlist_query as handle_shared_watchlist_query

PrivateChatReplyFunc = Callable[[str], Awaitable[object]]


def _resolve_bound_downloader_execution(
    *,
    bot_data: MutableMapping[str, object],
    role: str,
    tg,
):
    return resolve_shared_bound_downloader_execution(
        bot_data=bot_data,
        role=role,
        downloader_role_binding_key=tg.DOWNLOADER_ROLE_BINDING_KEY,
        downloader_instances_key=tg.DOWNLOADER_INSTANCES_KEY,
        config_missing_template=tg.DOWNLOADER_EXECUTION_CONFIG_MISSING_TEMPLATE,
    )


async def _handle_bt_classification_follow_up(
    *,
    bot_data: MutableMapping[str, object],
    reply_func: PrivateChatReplyFunc,
    chat_id: int | None,
    bt_classification_pending: bool,
    bt_classification: str | None,
    tg,
) -> bool:
    if bt_classification is None or not bt_classification_pending:
        return False
    bt_source = pop_bt_classification_pending(
        bot_data=bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=tg.BT_PENDING_REPO_KEY,
    )
    if bt_source is False or not bt_source:
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True
    if clear_bt_follow_up_conflicts(
        bot_data=bot_data,
        chat_id=chat_id,
        tg=tg,
    ) is None:
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True
    await reply_func(
        build_media_import_bt_flow_reply(
            bot_data=bot_data,
            chat_id=chat_id,
            source=bt_source,
            media_kind=bt_classification,
            tg=tg,
        )
    )
    return True


async def _handle_bt_tmdb_follow_up(
    *,
    bot_data: MutableMapping[str, object],
    reply_func: PrivateChatReplyFunc,
    query: str,
    chat_id: int | None,
    user_id: int | None,
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
        resolve_downloader_execution=lambda: _resolve_bound_downloader_execution(
            bot_data=bot_data,
            role="bt",
            tg=tg,
        ),
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


async def _handle_raw_bt_destination_follow_up(
    *,
    bot_data: MutableMapping[str, object],
    reply_func: PrivateChatReplyFunc,
    query: str,
    chat_id: int | None,
    user_id: int | None,
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
        resolve_downloader_execution=lambda: _resolve_bound_downloader_execution(
            bot_data=bot_data,
            role="bt",
            tg=tg,
        ),
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


async def _handle_confirm_query(
    *,
    bot_data: MutableMapping[str, object],
    execution_gate,
    reply_func: PrivateChatReplyFunc,
    confirm_ref: str | None,
    chat_id: int | None,
    user_id: int | None,
    tg,
) -> bool:
    return await handle_shared_confirm_query(
        bot_data=bot_data,
        execution_gate=execution_gate,
        reply_func=reply_func,
        confirm_ref=confirm_ref,
        chat_id=chat_id,
        user_id=user_id,
        tg=tg,
    )


async def _handle_digit_selection_query(
    *,
    bot_data: MutableMapping[str, object],
    execution_gate,
    reply_func: PrivateChatReplyFunc,
    query: str,
    chat_id: int | None,
    user_id: int | None,
    channel: str,
    tg,
) -> bool:
    return await handle_shared_digit_selection_query(
        bot_data=bot_data,
        execution_gate=execution_gate,
        reply_func=reply_func,
        query=query,
        chat_id=chat_id,
        user_id=user_id,
        channel=channel,
        resolve_downloader_execution=lambda: _resolve_bound_downloader_execution(bot_data=bot_data, role="pt", tg=tg),
        tg=tg,
    )


async def dispatch_private_chat_text(
    *,
    query: str,
    reply_func: Callable[[str], Awaitable[object]],
    chat_id: int | None,
    user_id: int | None,
    channel: str = "unknown",
    bot_data: MutableMapping[str, object],
) -> None:
    await handle_private_chat_query_text(
        query=query,
        reply_func=reply_func,
        chat_id=chat_id,
        user_id=user_id,
        channel=channel,
        bot_data=bot_data,
    )


async def handle_private_chat_query_text(
    *,
    query: str,
    reply_func: Callable[[str], Awaitable[object]],
    chat_id: int | None,
    user_id: int | None,
    channel: str = "unknown",
    bot_data: MutableMapping[str, object],
) -> None:
    tg = telegram_runtime
    execution_gate = resolve_execution_gate(
        bot_data=bot_data,
        execution_gate_key=tg.EXECUTION_GATE_KEY,
    )
    reply_func = prepare_private_chat_reply_with_trace(
        bot_data=bot_data,
        reply_func=reply_func,
        channel=channel,
        chat_id=chat_id,
        user_id=user_id,
        query=query,
    )
    if await handle_shared_frustration_query(
        query=query,
        bot_data=bot_data,
        execution_gate=execution_gate,
        reply_func=reply_func,
        chat_id=chat_id,
        tg=tg,
    ):
        return

    if await handle_shared_bt_direct_intent_query(
        query=query,
        bot_data=bot_data,
        reply_func=reply_func,
        chat_id=chat_id,
        tg=tg,
    ):
        return

    if await handle_shared_personal_wechat_login_query(
        query=query,
        bot_data=bot_data,
        execution_gate=execution_gate,
        reply_func=reply_func,
        chat_id=chat_id,
        tg=tg,
    ):
        return

    if await handle_shared_bt_read_only_query(
        query=query,
        bot_data=bot_data,
        execution_gate=execution_gate,
        reply_func=reply_func,
        chat_id=chat_id,
        tg=tg,
    ):
        return

    if await handle_shared_bt_batch_confirm_query(
        query=query,
        bot_data=bot_data,
        execution_gate=execution_gate,
        reply_func=reply_func,
        chat_id=chat_id,
        user_id=user_id,
        channel=channel,
        resolve_downloader_execution=lambda: _resolve_bound_downloader_execution(
            bot_data=bot_data,
            role="bt",
            tg=tg,
        ),
        tg=tg,
    ):
        return

    bt_classification = parse_bt_classification_choice(query)
    bt_processing_path = parse_bt_processing_path_choice(query)
    bt_processing_shortcut = parse_bt_processing_path_legacy_shortcut(query)
    bt_processing_path_pending = is_bt_processing_path_pending(
        bot_data=bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=tg.BT_PENDING_REPO_KEY,
    )
    if bt_processing_path_pending is None:
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return
    bt_classification_pending = is_bt_classification_pending(
        bot_data=bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=tg.BT_PENDING_REPO_KEY,
    )
    if bt_classification_pending is None:
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return
    if await handle_bt_processing_path_follow_up(
        bot_data=bot_data,
        reply_func=reply_func,
        chat_id=chat_id,
        bt_processing_path_pending=bt_processing_path_pending,
        bt_processing_path=bt_processing_path,
        bt_processing_shortcut=bt_processing_shortcut,
        tg=tg,
    ):
        return

    if await _handle_bt_classification_follow_up(
        bot_data=bot_data,
        reply_func=reply_func,
        chat_id=chat_id,
        bt_classification_pending=bt_classification_pending,
        bt_classification=bt_classification,
        tg=tg,
    ):
        return

    if await handle_shared_status_query(
        query=query,
        bot_data=bot_data,
        execution_gate=execution_gate,
        reply_func=reply_func,
        chat_id=chat_id,
        channel=channel,
        tg=tg,
    ):
        return

    if await handle_shared_watchlist_query(
        query=query,
        bot_data=bot_data,
        execution_gate=execution_gate,
        reply_func=reply_func,
        chat_id=chat_id,
        tg=tg,
    ):
        return

    if await handle_shared_bt_subscription_query(
        query=query,
        bot_data=bot_data,
        execution_gate=execution_gate,
        reply_func=reply_func,
        chat_id=chat_id,
        user_id=user_id,
        tg=tg,
    ):
        return

    if await handle_shared_import_query(
        query=query,
        bot_data=bot_data,
        execution_gate=execution_gate,
        reply_func=reply_func,
        chat_id=chat_id,
        user_id=user_id,
        tg=tg,
    ):
        return

    if await handle_shared_cleanup_query(
        query=query,
        bot_data=bot_data,
        execution_gate=execution_gate,
        reply_func=reply_func,
        chat_id=chat_id,
        user_id=user_id,
        channel=channel,
        tg=tg,
    ):
        return

    if await _handle_confirm_query(
        bot_data=bot_data,
        execution_gate=execution_gate,
        reply_func=reply_func,
        confirm_ref=tg.parse_confirm_query(query),
        chat_id=chat_id,
        user_id=user_id,
        tg=tg,
    ):
        return

    if await _handle_bt_tmdb_follow_up(
        bot_data=bot_data,
        reply_func=reply_func,
        query=query,
        chat_id=chat_id,
        user_id=user_id,
        tg=tg,
    ):
        return

    if await _handle_raw_bt_destination_follow_up(
        bot_data=bot_data,
        reply_func=reply_func,
        query=query,
        chat_id=chat_id,
        user_id=user_id,
        tg=tg,
    ):
        return

    if await _handle_digit_selection_query(
        bot_data=bot_data,
        execution_gate=execution_gate,
        reply_func=reply_func,
        query=query,
        chat_id=chat_id,
        user_id=user_id,
        channel=channel,
        tg=tg,
    ):
        return

    await handle_shared_search_query_fallback(
        bot_data=bot_data,
        execution_gate=execution_gate,
        reply_func=reply_func,
        query=query,
        chat_id=chat_id,
        channel=channel,
        bt_processing_path_pending=bt_processing_path_pending,
        bt_classification_pending=bt_classification_pending,
        tg=tg,
    )

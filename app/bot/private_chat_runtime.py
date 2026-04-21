from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping
from dataclasses import dataclass
from functools import partial

from app.bot.bt_classification_runtime import (
    is_bt_classification_pending,
)
from app.bot.private_chat_bt_classification_runtime import (
    handle_bt_classification_follow_up,
)
from app.bot.private_chat_bt_tmdb_runtime import (
    handle_bt_tmdb_follow_up,
)
from app.bot.private_chat_downloader_execution_runtime import (
    resolve_private_chat_bound_downloader_execution,
)
from app.bot.private_chat_raw_bt_destination_runtime import (
    handle_raw_bt_destination_follow_up,
)
from app.bot.bt_processing_path_runtime import (
    is_bt_processing_path_pending,
)
from app.bot.private_chat_bt_processing_runtime import (
    handle_bt_processing_path_follow_up,
)
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
from app.bot import telegram_bot as telegram_runtime
from app.bot.private_chat_import_runtime import handle_import_query as handle_shared_import_query
from app.bot.private_chat_login_runtime import handle_personal_wechat_login_query as handle_shared_personal_wechat_login_query
from app.bot.private_chat_search_runtime import handle_search_query_fallback as handle_shared_search_query_fallback
from app.bot.private_chat_status_runtime import handle_status_query as handle_shared_status_query
from app.bot.private_chat_trace_runtime import prepare_private_chat_reply_with_trace
from app.bot.private_chat_watchlist_runtime import handle_watchlist_query as handle_shared_watchlist_query

PrivateChatReplyFunc = Callable[[str], Awaitable[object]]


@dataclass(frozen=True, slots=True)
class _BtFollowUpPrecheck:
    bt_classification: str | None
    bt_processing_path: str | None
    bt_processing_shortcut: str | None
    bt_processing_path_pending: bool
    bt_classification_pending: bool


def _prepare_private_chat_runtime_bootstrap(
    *,
    query: str,
    reply_func: PrivateChatReplyFunc,
    channel: str,
    chat_id: int | None,
    user_id: int | None,
    bot_data: MutableMapping[str, object],
) -> tuple[object, object, PrivateChatReplyFunc]:
    tg = telegram_runtime
    return (
        tg,
        resolve_execution_gate(
            bot_data=bot_data,
            execution_gate_key=tg.EXECUTION_GATE_KEY,
        ),
        prepare_private_chat_reply_with_trace(
            bot_data=bot_data,
            reply_func=reply_func,
            channel=channel,
            chat_id=chat_id,
            user_id=user_id,
            query=query,
        ),
    )

async def _resolve_bt_follow_up_precheck(
    *,
    query: str,
    bot_data: MutableMapping[str, object],
    reply_func: PrivateChatReplyFunc,
    chat_id: int | None,
    tg,
) -> _BtFollowUpPrecheck | None:
    bt_processing_path_pending = is_bt_processing_path_pending(
        bot_data=bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=tg.BT_PENDING_REPO_KEY,
    )
    if bt_processing_path_pending is None:
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return None

    bt_classification_pending = is_bt_classification_pending(
        bot_data=bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=tg.BT_PENDING_REPO_KEY,
    )
    if bt_classification_pending is None:
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return None

    return _BtFollowUpPrecheck(
        bt_classification=parse_bt_classification_choice(query),
        bt_processing_path=parse_bt_processing_path_choice(query),
        bt_processing_shortcut=parse_bt_processing_path_legacy_shortcut(query),
        bt_processing_path_pending=bt_processing_path_pending,
        bt_classification_pending=bt_classification_pending,
    )


async def _handle_bt_follow_up_routes(
    *,
    query: str,
    bot_data: MutableMapping[str, object],
    reply_func: PrivateChatReplyFunc,
    chat_id: int | None,
    tg,
) -> _BtFollowUpPrecheck | None:
    bt_follow_up_precheck = await _resolve_bt_follow_up_precheck(
        query=query,
        bot_data=bot_data,
        reply_func=reply_func,
        chat_id=chat_id,
        tg=tg,
    )
    if bt_follow_up_precheck is None:
        return None

    if await handle_bt_processing_path_follow_up(
        bot_data=bot_data,
        reply_func=reply_func,
        chat_id=chat_id,
        bt_processing_path_pending=bt_follow_up_precheck.bt_processing_path_pending,
        bt_processing_path=bt_follow_up_precheck.bt_processing_path,
        bt_processing_shortcut=bt_follow_up_precheck.bt_processing_shortcut,
        tg=tg,
    ):
        return None

    if await handle_bt_classification_follow_up(
        bot_data=bot_data,
        reply_func=reply_func,
        chat_id=chat_id,
        bt_classification_pending=bt_follow_up_precheck.bt_classification_pending,
        bt_classification=bt_follow_up_precheck.bt_classification,
        tg=tg,
    ):
        return None

    return bt_follow_up_precheck


async def _handle_opening_routes(
    *,
    query: str,
    bot_data: MutableMapping[str, object],
    execution_gate,
    reply_func: PrivateChatReplyFunc,
    chat_id: int | None,
    user_id: int | None,
    channel: str,
    resolve_bt_downloader_execution,
    tg,
) -> bool:
    if await handle_shared_frustration_query(
        query=query,
        bot_data=bot_data,
        execution_gate=execution_gate,
        reply_func=reply_func,
        chat_id=chat_id,
        tg=tg,
    ):
        return True

    if await handle_shared_bt_direct_intent_query(
        query=query,
        bot_data=bot_data,
        reply_func=reply_func,
        chat_id=chat_id,
        tg=tg,
    ):
        return True

    if await handle_shared_personal_wechat_login_query(
        query=query,
        bot_data=bot_data,
        execution_gate=execution_gate,
        reply_func=reply_func,
        chat_id=chat_id,
        tg=tg,
    ):
        return True

    if await handle_shared_bt_read_only_query(
        query=query,
        bot_data=bot_data,
        execution_gate=execution_gate,
        reply_func=reply_func,
        chat_id=chat_id,
        tg=tg,
    ):
        return True

    return await handle_shared_bt_batch_confirm_query(
        query=query,
        bot_data=bot_data,
        execution_gate=execution_gate,
        reply_func=reply_func,
        chat_id=chat_id,
        user_id=user_id,
        channel=channel,
        resolve_downloader_execution=resolve_bt_downloader_execution,
        tg=tg,
    )


async def _handle_execution_gated_shared_routes(
    *,
    query: str,
    bot_data: MutableMapping[str, object],
    execution_gate,
    reply_func: PrivateChatReplyFunc,
    chat_id: int | None,
    user_id: int | None,
    channel: str,
    tg,
) -> bool:
    if await handle_shared_status_query(
        query=query,
        bot_data=bot_data,
        execution_gate=execution_gate,
        reply_func=reply_func,
        chat_id=chat_id,
        channel=channel,
        tg=tg,
    ):
        return True

    if await handle_shared_watchlist_query(
        query=query,
        bot_data=bot_data,
        execution_gate=execution_gate,
        reply_func=reply_func,
        chat_id=chat_id,
        tg=tg,
    ):
        return True

    if await handle_shared_bt_subscription_query(
        query=query,
        bot_data=bot_data,
        execution_gate=execution_gate,
        reply_func=reply_func,
        chat_id=chat_id,
        user_id=user_id,
        tg=tg,
    ):
        return True

    if await handle_shared_import_query(
        query=query,
        bot_data=bot_data,
        execution_gate=execution_gate,
        reply_func=reply_func,
        chat_id=chat_id,
        user_id=user_id,
        tg=tg,
    ):
        return True

    return await handle_shared_cleanup_query(
        query=query,
        bot_data=bot_data,
        execution_gate=execution_gate,
        reply_func=reply_func,
        chat_id=chat_id,
        user_id=user_id,
        channel=channel,
        tg=tg,
    )


async def _handle_tail_routes(
    *,
    query: str,
    bot_data: MutableMapping[str, object],
    execution_gate,
    reply_func: PrivateChatReplyFunc,
    chat_id: int | None,
    user_id: int | None,
    channel: str,
    bt_follow_up_precheck: _BtFollowUpPrecheck,
    resolve_bt_downloader_execution,
    resolve_pt_downloader_execution,
    tg,
) -> bool:
    if await handle_shared_confirm_query(
        bot_data=bot_data,
        execution_gate=execution_gate,
        reply_func=reply_func,
        confirm_ref=tg.parse_confirm_query(query),
        chat_id=chat_id,
        user_id=user_id,
        tg=tg,
    ):
        return True

    if await handle_bt_tmdb_follow_up(
        bot_data=bot_data,
        reply_func=reply_func,
        query=query,
        chat_id=chat_id,
        user_id=user_id,
        resolve_downloader_execution=resolve_bt_downloader_execution,
        tg=tg,
    ):
        return True

    if await handle_raw_bt_destination_follow_up(
        bot_data=bot_data,
        reply_func=reply_func,
        query=query,
        chat_id=chat_id,
        user_id=user_id,
        resolve_downloader_execution=resolve_bt_downloader_execution,
        tg=tg,
    ):
        return True

    if await handle_shared_digit_selection_query(
        bot_data=bot_data,
        execution_gate=execution_gate,
        reply_func=reply_func,
        query=query,
        chat_id=chat_id,
        user_id=user_id,
        channel=channel,
        resolve_downloader_execution=resolve_pt_downloader_execution,
        tg=tg,
    ):
        return True

    await handle_shared_search_query_fallback(
        bot_data=bot_data,
        execution_gate=execution_gate,
        reply_func=reply_func,
        query=query,
        chat_id=chat_id,
        channel=channel,
        bt_processing_path_pending=bt_follow_up_precheck.bt_processing_path_pending,
        bt_classification_pending=bt_follow_up_precheck.bt_classification_pending,
        tg=tg,
    )
    return True

async def handle_private_chat_query_text(
    *,
    query: str,
    reply_func: Callable[[str], Awaitable[object]],
    chat_id: int | None,
    user_id: int | None,
    channel: str = "unknown",
    bot_data: MutableMapping[str, object],
) -> None:
    tg, execution_gate, reply_func = _prepare_private_chat_runtime_bootstrap(
        query=query,
        reply_func=reply_func,
        channel=channel,
        chat_id=chat_id,
        user_id=user_id,
        bot_data=bot_data,
    )
    resolve_bt_downloader_execution = partial(
        resolve_private_chat_bound_downloader_execution,
        bot_data=bot_data,
        role="bt",
        tg=tg,
    )
    resolve_pt_downloader_execution = partial(
        resolve_private_chat_bound_downloader_execution,
        bot_data=bot_data,
        role="pt",
        tg=tg,
    )
    if await _handle_opening_routes(
        query=query,
        bot_data=bot_data,
        execution_gate=execution_gate,
        reply_func=reply_func,
        chat_id=chat_id,
        user_id=user_id,
        channel=channel,
        resolve_bt_downloader_execution=resolve_bt_downloader_execution,
        tg=tg,
    ):
        return

    bt_follow_up_precheck = await _handle_bt_follow_up_routes(
        query=query,
        bot_data=bot_data,
        reply_func=reply_func,
        chat_id=chat_id,
        tg=tg,
    )
    if bt_follow_up_precheck is None:
        return

    if await _handle_execution_gated_shared_routes(
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

    await _handle_tail_routes(
        query=query,
        bot_data=bot_data,
        execution_gate=execution_gate,
        reply_func=reply_func,
        chat_id=chat_id,
        user_id=user_id,
        channel=channel,
        bt_follow_up_precheck=bt_follow_up_precheck,
        resolve_bt_downloader_execution=resolve_bt_downloader_execution,
        resolve_pt_downloader_execution=resolve_pt_downloader_execution,
        tg=tg,
    )

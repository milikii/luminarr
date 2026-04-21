from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping

from app.bot.bt_classification_runtime import clear_bt_classification_pending
from app.bot.bt_processing_path_runtime import pop_bt_processing_path_pending
from app.bot.bt_tmdb_association_runtime import (
    clear_bt_tmdb_association_pending,
    enter_media_import_bt_flow,
)
from app.bot.raw_bt_destination_runtime import clear_raw_bt_destination_pending, enter_pure_bt_flow

PrivateChatReplyFunc = Callable[[str], Awaitable[object]]


def clear_bt_follow_up_conflicts(
    *,
    bot_data: MutableMapping[str, object],
    chat_id: int | None,
    tg,
    clear_classification_pending: bool = False,
) -> bool | None:
    cleared_raw_bt_destination = clear_raw_bt_destination_pending(
        bot_data=bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=tg.BT_PENDING_REPO_KEY,
    )
    if cleared_raw_bt_destination is None:
        return None
    cleared_tmdb_association = clear_bt_tmdb_association_pending(
        bot_data=bot_data,
        chat_id=chat_id,
        bt_pending_repo_key=tg.BT_PENDING_REPO_KEY,
    )
    if cleared_tmdb_association is None:
        return None
    if clear_classification_pending:
        clear_bt_classification_pending(
            bot_data=bot_data,
            chat_id=chat_id,
            bt_pending_repo_key=tg.BT_PENDING_REPO_KEY,
        )
    return True


def build_media_import_bt_flow_reply(
    *,
    bot_data: MutableMapping[str, object],
    chat_id: int | None,
    source: str,
    media_kind: str | None,
    tg,
) -> str:
    return enter_media_import_bt_flow(
        bot_data=bot_data,
        chat_id=chat_id,
        source=source,
        media_kind=media_kind,
        bt_pending_repo_key=tg.BT_PENDING_REPO_KEY,
        service_not_ready_text=tg.SERVICE_NOT_READY_TEXT,
    )


def build_pure_bt_flow_reply(
    *,
    bot_data: MutableMapping[str, object],
    chat_id: int | None,
    source: str,
    tg,
) -> str:
    return enter_pure_bt_flow(
        bot_data=bot_data,
        chat_id=chat_id,
        source=source,
        raw_bt_destination_options_key=tg.RAW_BT_DESTINATION_OPTIONS_KEY,
        bt_pending_repo_key=tg.BT_PENDING_REPO_KEY,
        raw_bt_destination_service_not_ready_text=tg.RAW_BT_DESTINATION_SERVICE_NOT_READY_TEXT,
        service_not_ready_text=tg.SERVICE_NOT_READY_TEXT,
    )


async def handle_bt_processing_path_follow_up(
    *,
    bot_data: MutableMapping[str, object],
    reply_func: PrivateChatReplyFunc,
    chat_id: int | None,
    bt_processing_path_pending: bool,
    bt_processing_path: str | None,
    bt_processing_shortcut: tuple[str, str | None] | None,
    tg,
) -> bool:
    if not bt_processing_path_pending:
        return False
    if bt_processing_path is None and bt_processing_shortcut is None:
        return False
    bt_source = pop_bt_processing_path_pending(
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
        clear_classification_pending=True,
    ) is None:
        await reply_func(tg.SERVICE_NOT_READY_TEXT)
        return True
    if bt_processing_path == "media_import":
        await reply_func(
            build_media_import_bt_flow_reply(
                bot_data=bot_data,
                chat_id=chat_id,
                source=bt_source,
                media_kind=None,
                tg=tg,
            )
        )
        return True
    if bt_processing_path == "pure_bt":
        await reply_func(
            build_pure_bt_flow_reply(
                bot_data=bot_data,
                chat_id=chat_id,
                source=bt_source,
                tg=tg,
            )
        )
        return True
    if bt_processing_shortcut is None:
        return False
    shortcut_path, shortcut_media_kind = bt_processing_shortcut
    if shortcut_path == "pure_bt":
        await reply_func(
            build_pure_bt_flow_reply(
                bot_data=bot_data,
                chat_id=chat_id,
                source=bt_source,
                tg=tg,
            )
        )
        return True
    await reply_func(
        build_media_import_bt_flow_reply(
            bot_data=bot_data,
            chat_id=chat_id,
            source=bt_source,
            media_kind=shortcut_media_kind,
            tg=tg,
        )
    )
    return True

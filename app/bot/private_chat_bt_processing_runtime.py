from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping
from urllib.parse import parse_qs, urlparse

from app.bot.bt_classification_runtime import clear_bt_classification_pending
from app.bot.bt_processing_path_runtime import pop_bt_processing_path_pending
from app.bot.bt_tmdb_association_runtime import (
    clear_bt_tmdb_association_pending,
    enter_media_import_bt_flow,
)
from app.bot.raw_bt_destination_runtime import clear_raw_bt_destination_pending, enter_pure_bt_flow
from app.services.add_pending_context import build_bt_task_ref
from app.services.add_to_downloader import AddToDownloaderService

PrivateChatReplyFunc = Callable[[str], Awaitable[object]]
ResolveDownloaderExecutionFunc = Callable[[], tuple[object | None, str | None]]


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


def _extract_magnet_display_title(source: str) -> str:
    parsed = urlparse(source.strip())
    query = parse_qs(parsed.query, keep_blank_values=False)
    display_name = next((item.strip() for item in query.get("dn", ()) if item.strip()), "")
    if display_name:
        return display_name
    return f"磁力资源 {build_bt_task_ref(source)}"


async def build_adult_bt_flow_reply(
    *,
    bot_data: MutableMapping[str, object],
    chat_id: int | None,
    user_id: int | None,
    channel: str,
    source: str,
    resolve_bt_downloader_execution: ResolveDownloaderExecutionFunc,
    tg,
) -> str:
    if chat_id is None or chat_id <= 0:
        return tg.SERVICE_NOT_READY_TEXT
    add_service = bot_data.get(tg.ADD_TO_DOWNLOADER_SERVICE_KEY)
    if not isinstance(add_service, AddToDownloaderService):
        return tg.SERVICE_NOT_READY_TEXT
    downloader_execution, config_missing_text = resolve_bt_downloader_execution()
    if config_missing_text:
        return config_missing_text
    downloader_name = ""
    downloader_type = "transmission"
    download_dir = ""
    if downloader_execution is not None:
        downloader_name = str(getattr(downloader_execution, "name", "")).strip()
        downloader_type = str(getattr(downloader_execution, "downloader_type", "")).strip() or "transmission"
        download_dir = str(getattr(downloader_execution, "download_dir", "")).strip()
    return await add_service.add_bt_source(
        chat_id=chat_id,
        source=source,
        title=_extract_magnet_display_title(source),
        user_id=user_id,
        channel=channel,
        downloader_name=downloader_name,
        downloader_type=downloader_type,
        download_dir=download_dir,
        auto_import_enabled=False,
    )


async def handle_bt_processing_path_follow_up(
    *,
    bot_data: MutableMapping[str, object],
    reply_func: PrivateChatReplyFunc,
    chat_id: int | None,
    user_id: int | None,
    channel: str,
    resolve_bt_downloader_execution: ResolveDownloaderExecutionFunc,
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
    if bt_processing_path == "adult_bt":
        await reply_func(
            await build_adult_bt_flow_reply(
                bot_data=bot_data,
                chat_id=chat_id,
                user_id=user_id,
                channel=channel,
                source=bt_source,
                resolve_bt_downloader_execution=resolve_bt_downloader_execution,
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

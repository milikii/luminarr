from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes, MessageHandler, filters

from app.bot.channel_contact_runtime import CHANNEL_CONTACT_REGISTRY_KEY, ChannelContactRegistry
from app.config import DownloaderInstanceConfig, DownloaderRoleBinding, RawBtDestinationOption
from app.db.bt_pending_repo import BtPendingRepo
from app.db.job_repo import JobRepo
from app.db.telegram_update_repo import TelegramUpdateRepo
from app.runtime.execution_policy import ExecutionGate
from app.bot.sidecar_host_runtime import SIDECAR_HOST_SEND_TEXT_FUNC_KEY
from app.services.add_to_downloader import AddToDownloaderService
from app.services.cleanup_downloaded_source import CleanupDownloadedSourceService
from app.services.get_download_status import GetDownloadStatusService
from app.services.import_to_library import ImportToLibraryService
from app.services.manage_bt_subscription import ManageBtSubscriptionService
from app.services.manage_watchlist import ManageWatchlistService
from app.services.post_download_auto_import import PostDownloadAutoImportService
from app.services.search_media import SearchMediaService
from app.bot.telegram_sidecar_runtime import (
    start_telegram_application_lifecycle,
    stop_telegram_application_lifecycle,
)
from app.bot.telegram_delivery_runtime import (
    build_telegram_send_media_func,
    build_telegram_send_text_func,
)
from app.bot.telegram_reply_formatter import format_telegram_reply
from app.bot.telegram_update_runtime import (
    build_telegram_download_image_func,
    build_telegram_reply_func,
    record_telegram_callback_update,
    record_telegram_message_update,
    resolve_telegram_callback_message,
    resolve_telegram_chat_id,
    resolve_telegram_user_id,
)


async def handle_telegram_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from app.bot.private_chat_runtime import handle_private_chat_query_text as dispatch_private_chat_text
    from app.bot import telegram_bot as tg

    message = update.effective_message
    if message is None:
        return
    query_text = str((message.text or message.caption or "")).strip()
    if not query_text:
        return

    chat_id = resolve_telegram_chat_id(update)
    user_id = resolve_telegram_user_id(update)
    if not record_telegram_message_update(
        update=update,
        context=context,
        telegram_update_repo_key=tg.TELEGRAM_UPDATE_REPO_KEY,
    ):
        return

    await dispatch_private_chat_text(
        query=query_text,
        reply_func=build_telegram_reply_func(
            message.reply_text,
            formatter=format_telegram_reply,
            reply_photo_func=getattr(message, "reply_photo", None),
            chat_id=chat_id,
            send_text_func=context.application.bot_data.get(tg.TELEGRAM_SEND_TEXT_FUNC_KEY),
            send_media_func=context.application.bot_data.get(tg.TELEGRAM_SEND_MEDIA_FUNC_KEY),
            download_image_func=context.application.bot_data.get(tg.TELEGRAM_DOWNLOAD_IMAGE_FUNC_KEY),
        ),
        chat_id=chat_id,
        user_id=user_id,
        channel="telegram",
        bot_data=context.application.bot_data,
    )


async def handle_telegram_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from app.bot.private_chat_runtime import handle_private_chat_query_text as dispatch_private_chat_text
    from app.bot import telegram_bot as tg

    callback_query = getattr(update, "callback_query", None)
    if callback_query is None:
        return

    chat_id = resolve_telegram_chat_id(update, callback_query=callback_query)
    user_id = resolve_telegram_user_id(update, callback_query=callback_query)
    callback_query_id = str(getattr(callback_query, "id", "") or "").strip()
    if not record_telegram_callback_update(
        callback_query_id=callback_query_id,
        chat_id=chat_id,
        user_id=user_id,
        context=context,
        telegram_update_repo_key=tg.TELEGRAM_UPDATE_REPO_KEY,
    ):
        return

    answer_func = getattr(callback_query, "answer", None)
    if callable(answer_func):
        await answer_func()

    message = resolve_telegram_callback_message(update, callback_query)
    if message is None:
        return

    query = str(getattr(callback_query, "data", "") or "").strip()
    if not query:
        return

    await dispatch_private_chat_text(
        query=query,
        reply_func=build_telegram_reply_func(
            message.reply_text,
            formatter=format_telegram_reply,
            reply_photo_func=getattr(message, "reply_photo", None),
            chat_id=chat_id,
            send_text_func=context.application.bot_data.get(tg.TELEGRAM_SEND_TEXT_FUNC_KEY),
            send_media_func=context.application.bot_data.get(tg.TELEGRAM_SEND_MEDIA_FUNC_KEY),
            download_image_func=context.application.bot_data.get(tg.TELEGRAM_DOWNLOAD_IMAGE_FUNC_KEY),
        ),
        chat_id=chat_id,
        user_id=user_id,
        channel="telegram",
        bot_data=context.application.bot_data,
    )


def build_telegram_application(
    token: str,
    search_service: SearchMediaService,
    add_to_downloader_service: AddToDownloaderService,
    get_download_status_service: GetDownloadStatusService,
    import_to_library_service: ImportToLibraryService,
    cleanup_downloaded_source_service: CleanupDownloadedSourceService,
    manage_watchlist_service: ManageWatchlistService,
    manage_bt_subscription_service: ManageBtSubscriptionService,
    post_download_auto_import_service: PostDownloadAutoImportService | None = None,
    telegram_update_repo: TelegramUpdateRepo | None = None,
    job_repo: JobRepo | None = None,
    execution_gate: ExecutionGate | None = None,
    bt_pending_repo: BtPendingRepo | None = None,
    bt_tmdb_movie_candidates_lookup_func=None,
    bt_tmdb_tv_candidates_lookup_func=None,
    raw_bt_destination_options: tuple[RawBtDestinationOption, ...] = (),
    downloader_instances: tuple[DownloaderInstanceConfig, ...] = (),
    downloader_role_binding: DownloaderRoleBinding | None = None,
    outbound_proxy_url: str = "",
    channel_contact_registry: ChannelContactRegistry | None = None,
) -> Application:
    from app.bot import telegram_bot as tg

    builder = (
        Application.builder()
        .token(token)
        .post_init(start_telegram_application_lifecycle)
        .post_shutdown(stop_telegram_application_lifecycle)
        .connect_timeout(20.0)
        .read_timeout(20.0)
        .write_timeout(20.0)
        .pool_timeout(20.0)
        .get_updates_connect_timeout(20.0)
        .get_updates_read_timeout(20.0)
        .get_updates_write_timeout(20.0)
        .get_updates_pool_timeout(20.0)
    )
    cleaned_proxy_url = outbound_proxy_url.strip()
    if cleaned_proxy_url:
        builder = builder.proxy(cleaned_proxy_url).get_updates_proxy(cleaned_proxy_url)
    application = builder.build()
    application.bot_data[tg.SEARCH_SERVICE_KEY] = search_service
    application.bot_data[tg.ADD_TO_DOWNLOADER_SERVICE_KEY] = add_to_downloader_service
    application.bot_data[tg.GET_DOWNLOAD_STATUS_SERVICE_KEY] = get_download_status_service
    application.bot_data[tg.IMPORT_TO_LIBRARY_SERVICE_KEY] = import_to_library_service
    if post_download_auto_import_service is not None:
        application.bot_data[tg.POST_DOWNLOAD_AUTO_IMPORT_SERVICE_KEY] = post_download_auto_import_service
    application.bot_data[tg.CLEANUP_DOWNLOADED_SOURCE_SERVICE_KEY] = cleanup_downloaded_source_service
    application.bot_data[tg.MANAGE_WATCHLIST_SERVICE_KEY] = manage_watchlist_service
    application.bot_data[tg.MANAGE_BT_SUBSCRIPTION_SERVICE_KEY] = manage_bt_subscription_service
    application.bot_data[tg.EXECUTION_GATE_KEY] = execution_gate or ExecutionGate()
    application.bot_data[tg.DOWNLOADER_INSTANCES_KEY] = downloader_instances
    application.bot_data[tg.DOWNLOADER_ROLE_BINDING_KEY] = downloader_role_binding
    if channel_contact_registry is not None:
        application.bot_data[CHANNEL_CONTACT_REGISTRY_KEY] = channel_contact_registry
    application.bot_data[tg.TELEGRAM_SEND_MEDIA_FUNC_KEY] = build_telegram_send_media_func(application)
    send_text_func = build_telegram_send_text_func(application)
    application.bot_data[tg.TELEGRAM_SEND_TEXT_FUNC_KEY] = send_text_func
    application.bot_data[tg.TELEGRAM_DOWNLOAD_IMAGE_FUNC_KEY] = build_telegram_download_image_func(
        proxy_url=outbound_proxy_url,
    )
    application.bot_data[SIDECAR_HOST_SEND_TEXT_FUNC_KEY] = send_text_func
    if bt_tmdb_movie_candidates_lookup_func is not None:
        application.bot_data[tg.BT_TMDB_MOVIE_CANDIDATES_LOOKUP_KEY] = bt_tmdb_movie_candidates_lookup_func
    if bt_tmdb_tv_candidates_lookup_func is not None:
        application.bot_data[tg.BT_TMDB_TV_CANDIDATES_LOOKUP_KEY] = bt_tmdb_tv_candidates_lookup_func
    application.bot_data[tg.RAW_BT_DESTINATION_OPTIONS_KEY] = raw_bt_destination_options
    if bt_pending_repo is not None:
        application.bot_data[tg.BT_PENDING_REPO_KEY] = bt_pending_repo
    if telegram_update_repo is not None:
        application.bot_data[tg.TELEGRAM_UPDATE_REPO_KEY] = telegram_update_repo
    if job_repo is not None:
        application.bot_data[tg.JOB_REPO_KEY] = job_repo
    application.add_handler(MessageHandler((filters.TEXT | filters.CAPTION) & ~filters.COMMAND, handle_telegram_message))
    application.add_handler(CallbackQueryHandler(handle_telegram_callback_query))
    return application

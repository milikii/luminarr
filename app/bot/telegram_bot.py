from __future__ import annotations

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from app.services.add_to_downloader import AddToDownloaderService
from app.services.get_download_status import GetDownloadStatusService, parse_status_query
from app.services.import_to_library import (
    ImportToLibraryService,
    parse_confirm_query,
    parse_import_query,
)
from app.services.search_media import SearchMediaService

SERVICE_NOT_READY_TEXT = "服务未就绪，请稍后重试。"
SEARCH_SERVICE_KEY = "search_media_service"
ADD_TO_DOWNLOADER_SERVICE_KEY = "add_to_downloader_service"
GET_DOWNLOAD_STATUS_SERVICE_KEY = "get_download_status_service"
IMPORT_TO_LIBRARY_SERVICE_KEY = "import_to_library_service"


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return

    query = (message.text or "").strip()
    task_ref = parse_status_query(query)
    if task_ref is not None:
        status_service = context.application.bot_data.get(GET_DOWNLOAD_STATUS_SERVICE_KEY)
        if not isinstance(status_service, GetDownloadStatusService):
            await message.reply_text(SERVICE_NOT_READY_TEXT)
            return
        reply = await status_service.get_status_text(task_ref)
        await message.reply_text(reply)
        return

    import_ref = parse_import_query(query)
    if import_ref is not None:
        import_service = context.application.bot_data.get(IMPORT_TO_LIBRARY_SERVICE_KEY)
        if not isinstance(import_service, ImportToLibraryService):
            await message.reply_text(SERVICE_NOT_READY_TEXT)
            return
        reply = await import_service.import_by_task_ref(import_ref)
        await message.reply_text(reply)
        return

    confirm_ref = parse_confirm_query(query)
    if confirm_ref is not None:
        import_service = context.application.bot_data.get(IMPORT_TO_LIBRARY_SERVICE_KEY)
        if not isinstance(import_service, ImportToLibraryService):
            await message.reply_text(SERVICE_NOT_READY_TEXT)
            return
        reply = await import_service.confirm_import_by_task_ref(confirm_ref)
        await message.reply_text(reply)
        return

    if query.isdigit():
        add_service = context.application.bot_data.get(ADD_TO_DOWNLOADER_SERVICE_KEY)
        if not isinstance(add_service, AddToDownloaderService):
            await message.reply_text(SERVICE_NOT_READY_TEXT)
            return

        chat = update.effective_chat
        if chat is None:
            await message.reply_text(SERVICE_NOT_READY_TEXT)
            return
        reply = await add_service.add_by_selection(chat.id, query)
        await message.reply_text(reply)
        return

    search_service = context.application.bot_data.get(SEARCH_SERVICE_KEY)
    if not isinstance(search_service, SearchMediaService):
        await message.reply_text(SERVICE_NOT_READY_TEXT)
        return

    chat = update.effective_chat
    chat_id = chat.id if chat is not None else None
    reply = await search_service.search_and_format(query, chat_id=chat_id)
    await message.reply_text(reply)


def build_application(
    token: str,
    search_service: SearchMediaService,
    add_to_downloader_service: AddToDownloaderService,
    get_download_status_service: GetDownloadStatusService,
    import_to_library_service: ImportToLibraryService,
) -> Application:
    application = Application.builder().token(token).build()
    application.bot_data[SEARCH_SERVICE_KEY] = search_service
    application.bot_data[ADD_TO_DOWNLOADER_SERVICE_KEY] = add_to_downloader_service
    application.bot_data[GET_DOWNLOAD_STATUS_SERVICE_KEY] = get_download_status_service
    application.bot_data[IMPORT_TO_LIBRARY_SERVICE_KEY] = import_to_library_service
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return application

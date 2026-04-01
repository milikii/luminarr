from __future__ import annotations

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from app.services.search_media import SearchMediaService

SERVICE_NOT_READY_TEXT = "服务未就绪，请稍后重试。"
SEARCH_SERVICE_KEY = "search_media_service"


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return

    service = context.application.bot_data.get(SEARCH_SERVICE_KEY)
    if not isinstance(service, SearchMediaService):
        await message.reply_text(SERVICE_NOT_READY_TEXT)
        return

    query = (message.text or "").strip()
    reply = await service.search_and_format(query)
    await message.reply_text(reply)


def build_application(token: str, search_service: SearchMediaService) -> Application:
    application = Application.builder().token(token).build()
    application.bot_data[SEARCH_SERVICE_KEY] = search_service
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return application

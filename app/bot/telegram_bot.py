from __future__ import annotations

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

CONFIRM_TEXT = "✅ 我收到了"


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    message = update.effective_message
    if message is None:
        return
    await message.reply_text(CONFIRM_TEXT)


def build_application(token: str) -> Application:
    application = Application.builder().token(token).build()
    application.add_handler(MessageHandler(filters.ALL, handle_message))
    return application

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

from telegram.error import TelegramError
from telegram.ext import Application

from app.operational_logging import emit_operational_log

TELEGRAM_PHOTO_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif"})
TelegramSendMediaFunc = Callable[[int, str | Path, str | None], Awaitable[object]]
TelegramSendTextFunc = Callable[..., Awaitable[object]]


def build_telegram_send_media_func(application: Application):
    async def send_media(chat_id: int, file_path: str | Path, caption: str | None = None) -> object:
        return await _send_telegram_media(
            application=application,
            chat_id=chat_id,
            file_path=Path(file_path).expanduser(),
            caption=caption,
        )

    return send_media


def build_telegram_send_text_func(application: Application):
    async def send_text(*, chat_id: int, text: str) -> object:
        return await application.bot.send_message(chat_id=chat_id, text=text)

    return send_text


async def _send_telegram_media(
    *,
    application: Application,
    chat_id: int,
    file_path: Path,
    caption: str | None,
) -> object:
    if not file_path.is_file():
        emit_operational_log(
            title="Telegram 媒资发送失败",
            detail=f"chat_id={chat_id} 文件不存在={file_path}",
            fix_hint="检查二维码/文件是否已生成到本地路径，并确认当前进程对该路径有读取权限。",
        )
        raise FileNotFoundError(str(file_path))

    try:
        if _is_telegram_photo_path(file_path):
            return await application.bot.send_photo(
                chat_id=chat_id,
                photo=file_path,
                caption=caption,
            )
        return await application.bot.send_document(
            chat_id=chat_id,
            document=file_path,
            caption=caption,
            filename=file_path.name,
        )
    except TelegramError as error:
        emit_operational_log(
            title="Telegram 媒资发送失败",
            detail=f"chat_id={chat_id} 文件={file_path} 原因={error}",
            fix_hint="检查 Telegram chat_id 是否仍有效、Bot 是否具备发送媒资权限，以及本地文件是否可被 Telegram API 正常读取。",
        )
        raise


def _is_telegram_photo_path(file_path: Path) -> bool:
    return file_path.suffix.lower() in TELEGRAM_PHOTO_SUFFIXES

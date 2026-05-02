from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from telegram.ext import Application

from app.bot.telegram_reply_formatter import _has_telegram_html
from app.operational_logging import emit_operational_log

TELEGRAM_PHOTO_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif"})
TELEGRAM_CALLBACK_DATA_MAX_BYTES = 64
_SEND_ACTION_LINE_PATTERN = re.compile(r"^(?P<label>[^：]+)：发送\s+(?P<query>.+?)\s*$")
_URL_ACTION_LINE_PATTERN = re.compile(r"^(?P<label>[^：]+)：打开\s+(?P<url>https?://\S+)$")
TelegramSendMediaFunc = Callable[
    [int, str | Path, str | None, str | None, InlineKeyboardMarkup | None],
    Awaitable[object],
]
TelegramSendTextFunc = Callable[..., Awaitable[object]]


def build_telegram_send_media_func(application: Application):
    async def send_media(
        chat_id: int,
        file_path: str | Path,
        caption: str | None = None,
        parse_mode: str | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> object:
        return await _send_telegram_media(
            application=application,
            chat_id=chat_id,
            file_path=Path(file_path).expanduser(),
            caption=caption,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )

    return send_media


def build_telegram_send_text_func(application: Application):
    async def send_text(*, chat_id: int, text: str) -> object:
        reply_markup = _build_inline_keyboard_markup(text)
        kwargs: dict = {"chat_id": chat_id, "text": text}
        if _has_telegram_html(text):
            kwargs["parse_mode"] = "HTML"
        if reply_markup is not None:
            kwargs["reply_markup"] = reply_markup
        return await application.bot.send_message(**kwargs)

    return send_text


async def _send_telegram_media(
    *,
    application: Application,
    chat_id: int,
    file_path: Path,
    caption: str | None,
    parse_mode: str | None = None,
    reply_markup: InlineKeyboardMarkup | None = None,
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
            kwargs = {"chat_id": chat_id, "photo": file_path, "caption": caption}
            if parse_mode:
                kwargs["parse_mode"] = parse_mode
            if reply_markup is not None:
                kwargs["reply_markup"] = reply_markup
            return await application.bot.send_photo(**kwargs)
        kwargs = {"chat_id": chat_id, "document": file_path, "caption": caption, "filename": file_path.name}
        if parse_mode:
            kwargs["parse_mode"] = parse_mode
        if reply_markup is not None:
            kwargs["reply_markup"] = reply_markup
        return await application.bot.send_document(**kwargs)
    except TelegramError as error:
        emit_operational_log(
            title="Telegram 媒资发送失败",
            detail=f"chat_id={chat_id} 文件={file_path} 原因={error}",
            fix_hint="检查 Telegram chat_id 是否仍有效、Bot 是否具备发送媒资权限，以及本地文件是否可被 Telegram API 正常读取。",
        )
        raise


def _is_telegram_photo_path(file_path: Path) -> bool:
    return file_path.suffix.lower() in TELEGRAM_PHOTO_SUFFIXES


def _build_inline_keyboard_markup(text: str) -> InlineKeyboardMarkup | None:
    action_rows = _extract_inline_action_rows(text)
    if not action_rows:
        return None

    keyboard_rows: list[list[InlineKeyboardButton]] = []
    current_row: list[InlineKeyboardButton] = []
    for button in action_rows:
        callback_query = str(getattr(button, "callback_data", "") or "")
        if callback_query and len(callback_query.encode("utf-8")) > TELEGRAM_CALLBACK_DATA_MAX_BYTES:
            continue
        current_row.append(button)
        if len(current_row) >= 2:
            keyboard_rows.append(current_row)
            current_row = []
    if current_row:
        keyboard_rows.append(current_row)
    if not keyboard_rows:
        return None
    return InlineKeyboardMarkup(keyboard_rows)


def _extract_inline_action_rows(text: str) -> tuple[InlineKeyboardButton, ...]:
    in_actions = False
    action_rows: list[InlineKeyboardButton] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line == "下一步":
            in_actions = True
            continue
        if not in_actions:
            continue
        url_match = _URL_ACTION_LINE_PATTERN.match(line)
        if url_match is not None:
            label = str(url_match.group("label") or "").strip()
            url = str(url_match.group("url") or "").strip()
            if label and url:
                action_rows.append(InlineKeyboardButton(text=label, url=url))
            continue
        send_match = _SEND_ACTION_LINE_PATTERN.match(line)
        if send_match is None:
            continue
        label = str(send_match.group("label") or "").strip()
        query = str(send_match.group("query") or "").strip()
        if not label or not query:
            continue
        action_rows.append(InlineKeyboardButton(text=label, callback_data=query))
    return tuple(action_rows)

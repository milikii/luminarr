from __future__ import annotations

import inspect
import sqlite3
import shutil
import tempfile
import textwrap
from collections.abc import Awaitable, Callable
from pathlib import Path
import re
from urllib.parse import urlparse

import httpx
from PIL import Image, ImageDraw, ImageFont

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.bot.telegram_reply_formatter import _has_telegram_html
from app.db.telegram_update_repo import TelegramUpdatePersistenceError
from app.db.telegram_update_repo import TelegramUpdateRepo
from app.operational_logging import emit_operational_log

TelegramReplyTextFunc = Callable[[str], Awaitable[object]]
TelegramSendTextFunc = Callable[..., Awaitable[object]]
TelegramSendMediaFunc = Callable[[int, str | Path, str | None, str | None, InlineKeyboardMarkup | None], Awaitable[object]]
DownloadImageFunc = Callable[[str], Awaitable[bytes]]


def build_telegram_download_image_func(*, proxy_url: str = "") -> DownloadImageFunc:
    async def download_image(url: str) -> bytes:
        cleaned_url = url.strip()
        if not cleaned_url:
            return b""
        async with httpx.AsyncClient(timeout=20.0, proxy=proxy_url.strip() or None) as client:
            response = await client.get(cleaned_url)
        response.raise_for_status()
        return response.content

    return download_image


def build_telegram_reply_func(
    reply_func: TelegramReplyTextFunc,
    *,
    formatter: Callable[[str], str],
    reply_photo_func: Callable[..., Awaitable[object]] | None = None,
    chat_id: int | None = None,
    send_text_func: TelegramSendTextFunc | None = None,
    send_media_func: TelegramSendMediaFunc | None = None,
    download_image_func: DownloadImageFunc | None = None,
) -> Callable[[str], Awaitable[object]]:
    async def wrapped(text: str) -> object:
        formatted_text = formatter(text)
        if reply_photo_func is not None and _is_adult_bt_poster_caption_reply(formatted_text):
            return await _reply_adult_bt_poster_caption_message(
                reply_text_func=reply_func,
                reply_photo_func=reply_photo_func,
                text=formatted_text,
            )
        if (
            chat_id is not None
            and send_text_func is not None
            and send_media_func is not None
            and download_image_func is not None
            and not _is_adult_bt_poster_caption_reply(formatted_text)
            and _is_candidate_card_reply(formatted_text)
        ):
            return await _send_candidate_card_messages(
                reply_text_func=reply_func,
                send_text_func=send_text_func,
                send_media_func=send_media_func,
                download_image_func=download_image_func,
                chat_id=chat_id,
                text=formatted_text,
            )
        if reply_photo_func is not None and _is_candidate_card_reply(formatted_text):
            return await _reply_candidate_card_messages(
                reply_text_func=reply_func,
                reply_photo_func=reply_photo_func,
                text=formatted_text,
            )
        return await reply_func(formatted_text)

    return wrapped


_CANDIDATE_BLOCK_START_RE = re.compile(r"^【(?P<index>\d+)】\s+")
_STRIP_HTML_RE = re.compile(r"</?(?:b|i|u|s|code|pre|a)\b[^>]*>")
_ADULT_BT_CARD_PREFIX = "【成人资源候选】"
_URL_ACTION_LINE_PATTERN = re.compile(r"^(?P<label>[^：]+)：打开\s+(?P<url>https?://\S+)$")
_SEND_ACTION_LINE_PATTERN = re.compile(r"^(?P<label>[^：]+)：发送\s+(?P<query>.+?)\s*$")
_PLACEHOLDER_POSTER_SIZE = (720, 1080)
_PLACEHOLDER_BACKGROUND = "#101A29"
_PLACEHOLDER_PANEL = "#22324A"
_PLACEHOLDER_ACCENT = "#E0B04B"
_PLACEHOLDER_TEXT = "#F5F7FA"
_PLACEHOLDER_SUBTEXT = "#B8C4D6"


def _strip_telegram_html_tags(text: str) -> str:
    text = _STRIP_HTML_RE.sub("", text)
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", "\"")
    return text


def _is_candidate_card_reply(text: str) -> bool:
    stripped_text = text.strip()
    return stripped_text.startswith("【候选作品】") or stripped_text.startswith(_ADULT_BT_CARD_PREFIX)


def _is_adult_bt_poster_caption_reply(text: str) -> bool:
    stripped_text = text.strip()
    if not stripped_text.startswith(_ADULT_BT_CARD_PREFIX):
        return False
    return any(line.strip().startswith("海报:") for line in stripped_text.splitlines())


async def _reply_adult_bt_poster_caption_message(
    *,
    reply_text_func: TelegramReplyTextFunc,
    reply_photo_func: Callable[..., Awaitable[object]],
    text: str,
) -> object:
    poster_url, caption, action_lines = _split_adult_bt_poster_caption_reply(text)
    reply_markup = _build_adult_bt_inline_keyboard(action_lines)
    if poster_url and caption:
        try:
            kwargs: dict = {"photo": poster_url, "caption": caption, "parse_mode": "HTML"}
            if reply_markup is not None:
                kwargs["reply_markup"] = reply_markup
            return await reply_photo_func(**kwargs)
        except Exception as error:
            emit_operational_log(
                title="Telegram 成人资源海报发送失败",
                detail=f"url={poster_url} 原因={error}",
                fix_hint="检查 Telegram 侧图片 URL、Bot 媒体发送权限和 HTML caption 长度；当前会退回纯文本成人资源卡。",
            )
    return await _send_or_reply_text(
        reply_text_func=reply_text_func,
        send_text_func=None,
        chat_id=None,
        text=_compose_adult_bt_text_fallback(
            poster_url=poster_url,
            caption=caption,
            action_lines=action_lines,
        ),
    )


def _split_adult_bt_poster_caption_reply(text: str) -> tuple[str, str, list[str]]:
    poster_url = ""
    caption_lines: list[str] = []
    action_lines: list[str] = []
    in_actions = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if not in_actions and caption_lines:
                caption_lines.append("")
            continue
        if line.startswith("海报:"):
            poster_url = line.removeprefix("海报:").strip()
            continue
        if line == "下一步":
            in_actions = True
            action_lines.append(line)
            continue
        if in_actions:
            action_lines.append(line)
            continue
        if line.startswith(_ADULT_BT_CARD_PREFIX):
            continue
        caption_lines.append(line)
    while caption_lines and not caption_lines[-1]:
        caption_lines.pop()
    return poster_url, "\n".join(caption_lines).strip(), action_lines


def _build_adult_bt_inline_keyboard(action_lines: list[str]) -> InlineKeyboardMarkup | None:
    buttons: list[InlineKeyboardButton] = []
    for line in action_lines:
        if line == "下一步":
            continue
        url_match = _URL_ACTION_LINE_PATTERN.match(line)
        if url_match is not None:
            label = str(url_match.group("label") or "").strip()
            url = str(url_match.group("url") or "").strip()
            if label and url:
                buttons.append(InlineKeyboardButton(text=label, url=url))
            continue
        send_match = _SEND_ACTION_LINE_PATTERN.match(line)
        if send_match is None:
            continue
        label = str(send_match.group("label") or "").strip()
        query = str(send_match.group("query") or "").strip()
        if label and query and len(query.encode("utf-8")) <= 64:
            buttons.append(InlineKeyboardButton(text=label, callback_data=query))
    if not buttons:
        return None
    rows = [buttons[index : index + 2] for index in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(rows)


def _compose_adult_bt_text_fallback(*, poster_url: str, caption: str, action_lines: list[str]) -> str:
    parts: list[str] = []
    cleaned_poster_url = poster_url.strip()
    if cleaned_poster_url:
        parts.append(f"海报: {cleaned_poster_url}")
    if caption.strip():
        parts.append(caption.strip())
    if action_lines:
        parts.append("\n".join(action_lines).strip())
    return "\n\n".join(part for part in parts if part).strip()


async def _reply_candidate_card_messages(
    *,
    reply_text_func: TelegramReplyTextFunc,
    reply_photo_func: Callable[..., Awaitable[object]],
    text: str,
) -> object:
    header_lines, candidate_blocks, action_lines = _split_candidate_card_reply(text)

    last_result: object | None = None
    if header_lines:
        last_result = await _send_or_reply_text(
            reply_text_func=reply_text_func,
            send_text_func=None,
            chat_id=None,
            text="\n".join(header_lines),
        )
    for block in candidate_blocks:
        poster_url, cleaned_lines = _extract_candidate_block_media(block)
        caption = _resolve_candidate_block_caption(cleaned_lines)
        reply_markup = _build_candidate_selection_inline_keyboard(cleaned_lines)
        placeholder_artifact: Path | None = None
        media_source: str | Path | None = poster_url
        if not media_source:
            placeholder_artifact = _build_candidate_placeholder_media_artifact(cleaned_lines)
            media_source = placeholder_artifact
        if media_source and caption:
            try:
                kwargs: dict[str, object] = {"photo": media_source, "caption": caption}
                if _has_telegram_html(caption):
                    kwargs["parse_mode"] = "HTML"
                if reply_markup is not None:
                    kwargs["reply_markup"] = reply_markup
                last_result = await reply_photo_func(**kwargs)
                continue
            except Exception as error:
                emit_operational_log(
                    title="Telegram 候选海报发送失败",
                    detail=f"url={str(media_source)} 原因={error}",
                    fix_hint="检查 Telegram 侧媒体发送权限、图片格式和候选海报 URL；当前会退回纯文本候选卡，不影响后续数字确认。",
                )
            finally:
                _cleanup_temp_media_artifact(placeholder_artifact)
        last_result = await _send_or_reply_text(
            reply_text_func=reply_text_func,
            send_text_func=None,
            chat_id=None,
            text=caption,
        )
    if action_lines:
        last_result = await _send_or_reply_text(
            reply_text_func=reply_text_func,
            send_text_func=None,
            chat_id=None,
            text="\n".join(action_lines),
        )
    return last_result


async def _send_candidate_card_messages(
    *,
    reply_text_func: TelegramReplyTextFunc,
    send_text_func: TelegramSendTextFunc,
    send_media_func: TelegramSendMediaFunc,
    download_image_func: DownloadImageFunc,
    chat_id: int,
    text: str,
) -> object:
    header_lines, candidate_blocks, action_lines = _split_candidate_card_reply(text)
    cleaned_blocks: list[list[str]] = []
    for block in candidate_blocks:
        poster_url, cleaned_lines = _extract_candidate_block_media(block)
        reply_markup = _build_candidate_selection_inline_keyboard(cleaned_lines)
        sent_as_media = False
        artifact: Path | None
        if poster_url:
            artifact = await _download_candidate_media_artifact(
                download_image_func=download_image_func,
                poster_url=poster_url,
            )
        else:
            artifact = _build_candidate_placeholder_media_artifact(cleaned_lines)
        if artifact is None:
            cleaned_blocks.append(cleaned_lines)
            continue
        try:
            try:
                caption = _resolve_candidate_block_caption(cleaned_lines)
                parse_mode = "HTML" if caption and _has_telegram_html(caption) else None
                await _call_send_media_func(
                    send_media_func=send_media_func,
                    chat_id=chat_id,
                    artifact=artifact,
                    caption=caption,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup,
                )
                sent_as_media = True
            except Exception as error:
                emit_operational_log(
                    title="Telegram 候选海报发送失败",
                    detail=f"url={poster_url or str(artifact)} 原因={error}",
                    fix_hint="检查 Telegram 侧媒体发送权限、图片格式和候选海报 URL；当前会退回纯文本候选卡，不影响后续数字确认。",
                )
        finally:
            _cleanup_temp_media_artifact(artifact)
        if not sent_as_media:
            cleaned_blocks.append(cleaned_lines)
    cleaned_text = _compose_candidate_card_text(
        header_lines=_normalize_candidate_card_header_lines(
            header_lines=header_lines,
            has_remaining_candidate_blocks=bool(cleaned_blocks),
        ),
        candidate_blocks=cleaned_blocks,
        action_lines=action_lines,
    )
    return await _send_or_reply_text(
        reply_text_func=reply_text_func,
        send_text_func=send_text_func,
        chat_id=chat_id,
        text=cleaned_text,
    )


def _split_candidate_card_reply(text: str) -> tuple[list[str], list[list[str]], list[str]]:
    lines = [line.rstrip() for line in text.splitlines()]
    header_lines: list[str] = []
    action_lines: list[str] = []
    candidate_blocks: list[list[str]] = []
    current_block: list[str] = []
    in_actions = False
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if line == "下一步":
            in_actions = True
            if current_block:
                candidate_blocks.append(current_block)
                current_block = []
            action_lines.append(line)
            continue
        if in_actions:
            action_lines.append(line)
            continue
        if _CANDIDATE_BLOCK_START_RE.match(line):
            if current_block:
                candidate_blocks.append(current_block)
            current_block = [line]
            continue
        if current_block:
            current_block.append(line)
        else:
            header_lines.append(line)
    if current_block:
        candidate_blocks.append(current_block)
    return header_lines, candidate_blocks, action_lines


def _extract_candidate_block_media(block: list[str]) -> tuple[str, list[str]]:
    poster_url = ""
    cleaned_lines: list[str] = []
    for line in block:
        poster_match = re.match(r"^海报[:：]\s*(?P<url>https?://\S+)$", line.strip())
        if poster_match is not None:
            poster_url = str(poster_match.group("url") or "").strip()
            continue
        cleaned_lines.append(line.strip())
    return poster_url, cleaned_lines


def _build_candidate_selection_inline_keyboard(block_lines: list[str]) -> InlineKeyboardMarkup | None:
    if not block_lines:
        return None
    first_line = _strip_telegram_html_tags(block_lines[0]).strip()
    match = _CANDIDATE_BLOCK_START_RE.match(first_line)
    if match is None:
        return None
    index = str(match.group("index") or "").strip()
    if not index or len(index.encode("utf-8")) > 64:
        return None
    return InlineKeyboardMarkup([[InlineKeyboardButton(text=f"确认作品 {index}", callback_data=index)]])


def _build_candidate_placeholder_media_artifact(block_lines: list[str]) -> Path | None:
    artifact_dir = Path(tempfile.mkdtemp(prefix="luminarr-telegram-card-"))
    artifact_path = artifact_dir / "poster.jpg"
    title = _resolve_candidate_placeholder_title(block_lines)
    try:
        image = Image.new("RGB", _PLACEHOLDER_POSTER_SIZE, _PLACEHOLDER_BACKGROUND)
        draw = ImageDraw.Draw(image)
        panel_bounds = (52, 80, _PLACEHOLDER_POSTER_SIZE[0] - 52, _PLACEHOLDER_POSTER_SIZE[1] - 80)
        draw.rounded_rectangle(panel_bounds, radius=28, fill=_PLACEHOLDER_PANEL)
        draw.rectangle((96, 148, _PLACEHOLDER_POSTER_SIZE[0] - 96, 166), fill=_PLACEHOLDER_ACCENT)

        brand_font = _load_placeholder_font(30)
        title_font = _load_placeholder_font(46)
        subtitle_font = _load_placeholder_font(24)
        body_font = _load_placeholder_font(26)

        draw.text((96, 196), "Luminarr", fill=_PLACEHOLDER_ACCENT, font=brand_font)
        draw.text((96, 246), "Poster unavailable", fill=_PLACEHOLDER_TEXT, font=subtitle_font)

        wrapped_title = "\n".join(textwrap.wrap(title, width=16, break_long_words=True)[:4]) or "Candidate"
        draw.multiline_text(
            (96, 326),
            wrapped_title,
            fill=_PLACEHOLDER_TEXT,
            font=title_font,
            spacing=14,
        )
        draw.text(
            (96, _PLACEHOLDER_POSTER_SIZE[1] - 186),
            "TMDB and Fanart did not provide a poster for this candidate.",
            fill=_PLACEHOLDER_SUBTEXT,
            font=body_font,
        )
        image.save(artifact_path, format="JPEG", quality=90)
        return artifact_path
    except Exception as error:
        emit_operational_log(
            title="Telegram 候选占位海报生成失败",
            detail=f"title={title} 原因={error}",
            fix_hint="检查 Pillow 运行环境与本地临时目录写权限；当前会退回纯文本候选卡。",
        )
        shutil.rmtree(artifact_dir, ignore_errors=True)
        return None


def _load_placeholder_font(size: int) -> ImageFont.ImageFont:
    font_candidates = (
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    )
    for font_path in font_candidates:
        try:
            return ImageFont.truetype(font_path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _resolve_candidate_placeholder_title(block_lines: list[str]) -> str:
    if not block_lines:
        return "Candidate"
    first_line = _strip_telegram_html_tags(block_lines[0]).strip()
    return _CANDIDATE_BLOCK_START_RE.sub("", first_line).strip() or "Candidate"


async def _download_candidate_media_artifact(
    *,
    download_image_func: DownloadImageFunc,
    poster_url: str,
) -> Path | None:
    try:
        payload = await download_image_func(poster_url)
    except Exception as error:
        emit_operational_log(
            title="Telegram 候选海报下载失败",
            detail=f"url={poster_url} 原因={error}",
            fix_hint="检查海报 URL、代理和站点可达性；当前会退回纯文本候选卡，不影响后续数字确认。",
        )
        return None
    if not payload:
        return None
    artifact_dir = Path(tempfile.mkdtemp(prefix="luminarr-telegram-card-"))
    artifact_path = artifact_dir / f"poster{_resolve_media_suffix(poster_url)}"
    artifact_path.write_bytes(payload)
    return artifact_path


def _resolve_media_suffix(poster_url: str) -> str:
    suffix = Path(urlparse(poster_url).path).suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        return suffix
    return ".jpg"


def _cleanup_temp_media_artifact(artifact_path: Path | None) -> None:
    if artifact_path is None:
        return
    try:
        if artifact_path.exists():
            artifact_path.unlink()
    finally:
        shutil.rmtree(artifact_path.parent, ignore_errors=True)


def _resolve_candidate_block_caption(block_lines: list[str]) -> str | None:
    if not block_lines:
        return None
    clean_lines = [line.strip() for line in block_lines if line.strip()]
    if not clean_lines:
        return None
    caption = "\n".join(clean_lines)
    if len(caption) > 1000:
        caption = caption[:997] + "..."
    return caption


async def _call_send_media_func(
    *,
    send_media_func: TelegramSendMediaFunc,
    chat_id: int,
    artifact: Path,
    caption: str | None,
    parse_mode: str | None,
    reply_markup: InlineKeyboardMarkup | None,
) -> object:
    try:
        signature = inspect.signature(send_media_func)
    except (TypeError, ValueError):
        signature = None
    if signature is not None and "reply_markup" in signature.parameters:
        return await send_media_func(
            chat_id,
            artifact,
            caption,
            parse_mode,
            reply_markup=reply_markup,
        )
    return await send_media_func(chat_id, artifact, caption, parse_mode)


def _compose_candidate_card_text(
    *,
    header_lines: list[str],
    candidate_blocks: list[list[str]],
    action_lines: list[str],
) -> str:
    lines: list[str] = []
    if header_lines:
        lines.extend(header_lines)
    for block in candidate_blocks:
        block_lines = [line for line in block if line.strip()]
        if not block_lines:
            continue
        if lines:
            lines.append("")
        lines.extend(block_lines)
    if action_lines:
        if lines:
            lines.append("")
        lines.extend(action_lines)
    return "\n".join(lines).strip()


def _normalize_candidate_card_header_lines(
    *,
    header_lines: list[str],
    has_remaining_candidate_blocks: bool,
) -> list[str]:
    if has_remaining_candidate_blocks:
        return header_lines
    return [line for line in header_lines if line != "先确认最可能的作品："]


async def _send_or_reply_text(
    *,
    reply_text_func: TelegramReplyTextFunc,
    send_text_func: TelegramSendTextFunc | None,
    chat_id: int | None,
    text: str,
) -> object:
    if send_text_func is not None and chat_id is not None:
        return await send_text_func(chat_id=chat_id, text=text)
    if _has_telegram_html(text):
        return await reply_text_func(text, parse_mode="HTML")
    return await reply_text_func(text)


def resolve_telegram_chat_id(
    update: Update,
    *,
    callback_query: object | None = None,
) -> int | None:
    chat = getattr(update, "effective_chat", None)
    chat_id = getattr(chat, "id", None)
    if isinstance(chat_id, int):
        return chat_id

    if callback_query is None:
        return None

    message = getattr(callback_query, "message", None)
    callback_chat = getattr(message, "chat", None)
    callback_chat_id = getattr(callback_chat, "id", None)
    if isinstance(callback_chat_id, int):
        return callback_chat_id
    return None


def resolve_telegram_user_id(
    update: Update,
    *,
    callback_query: object | None = None,
) -> int | None:
    user = getattr(update, "effective_user", None)
    user_id = getattr(user, "id", None)
    if isinstance(user_id, int):
        return user_id

    if callback_query is None:
        return None

    callback_user = getattr(callback_query, "from_user", None)
    callback_user_id = getattr(callback_user, "id", None)
    if isinstance(callback_user_id, int):
        return callback_user_id
    return None


def resolve_telegram_callback_message(update: Update, callback_query: object) -> object | None:
    message = getattr(update, "effective_message", None)
    if message is not None:
        return message
    return getattr(callback_query, "message", None)


def record_telegram_message_update(
    *,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    telegram_update_repo_key: str,
) -> bool:
    update_repo = context.application.bot_data.get(telegram_update_repo_key)
    if not isinstance(update_repo, TelegramUpdateRepo):
        return True

    update_id = getattr(update, "update_id", 0)
    if not isinstance(update_id, int):
        return True

    chat_id = resolve_telegram_chat_id(update)
    user_id = resolve_telegram_user_id(update)
    try:
        recorded = update_repo.record_message_update(
            update_id=update_id,
            chat_id=chat_id,
            user_id=user_id,
        )
        if recorded is None:
            raise TelegramUpdatePersistenceError("telegram update record result missing")
        return recorded
    except (TelegramUpdatePersistenceError, sqlite3.Error) as error:
        _log_telegram_update_record_error(
            source_type="message",
            source_id=str(update_id),
            chat_id=chat_id,
            user_id=user_id,
            error=error,
        )
        return False


def record_telegram_callback_update(
    *,
    callback_query_id: str,
    chat_id: int | None,
    user_id: int | None,
    context: ContextTypes.DEFAULT_TYPE,
    telegram_update_repo_key: str,
) -> bool:
    update_repo = context.application.bot_data.get(telegram_update_repo_key)
    if not isinstance(update_repo, TelegramUpdateRepo):
        return True

    try:
        recorded = update_repo.record_callback_update(
            callback_query_id=callback_query_id,
            chat_id=chat_id,
            user_id=user_id,
        )
        if recorded is None:
            raise TelegramUpdatePersistenceError("telegram update record result missing")
        return recorded
    except (TelegramUpdatePersistenceError, sqlite3.Error) as error:
        _log_telegram_update_record_error(
            source_type="callback",
            source_id=callback_query_id,
            chat_id=chat_id,
            user_id=user_id,
            error=error,
        )
        return False


def _log_telegram_update_record_error(
    *,
    source_type: str,
    source_id: str,
    chat_id: int | None,
    user_id: int | None,
    error: Exception,
) -> None:
    error_text = str(error)
    if error_text == "telegram update record result missing":
        emit_operational_log(
            title="Telegram 更新去重结果缺失",
            detail=(
                f"source_type={source_type} source_id={source_id.strip() or '-'} "
                f"chat_id={chat_id if chat_id is not None else '-'} "
                f"user_id={user_id if user_id is not None else '-'} 原因={error_text}"
            ),
            fix_hint="检查 telegram_updates 写入返回是否仍带有明确布尔结果；当前 update 会停止继续处理，避免把去重真相缺口误判成普通重复消息。",
        )
        return

    emit_operational_log(
        title="Telegram 更新去重落盘失败",
        detail=(
            f"source_type={source_type} source_id={source_id.strip() or '-'} "
            f"chat_id={chat_id if chat_id is not None else '-'} "
            f"user_id={user_id if user_id is not None else '-'} 原因={error_text}"
        ),
        fix_hint="检查 SQLite/telegram_updates 表写入是否正常；当前 update 会停止继续处理，避免在去重真相缺失时重复执行副作用。",
    )

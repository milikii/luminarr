from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.telegram_delivery_runtime import build_telegram_send_media_func, build_telegram_send_text_func
from app.runtime.delivery import DeliveryAction, DeliveryHeader, DeliveryItem, DeliverySection, render_telegram_text


def test_build_telegram_send_text_func_sends_message() -> None:
    send_message = AsyncMock(return_value="text-message")
    sender = build_telegram_send_text_func(SimpleNamespace(bot=SimpleNamespace(send_message=send_message)))

    result = asyncio.run(sender(chat_id=1001, text="扫码成功"))

    assert result == "text-message"
    send_message.assert_awaited_once_with(chat_id=1001, text="扫码成功")


def test_build_telegram_send_text_func_sends_plain_text_without_reply_markup() -> None:
    send_message = AsyncMock(return_value="text-message")
    sender = build_telegram_send_text_func(SimpleNamespace(bot=SimpleNamespace(send_message=send_message)))
    text = render_telegram_text(
        DeliveryItem(
            header=DeliveryHeader(kind="status", title="下载状态"),
            sections=(DeliverySection(label="当前进度", lines=("任务：hash-87", "进度：100%")),),
            actions=(),
            status="success",
        )
    )

    result = asyncio.run(sender(chat_id=1001, text=text))

    assert result == "text-message"
    send_message.assert_awaited_once_with(chat_id=1001, text="下载状态 ✓\n\n当前进度\n任务：hash-87\n进度：100%")


def test_build_telegram_send_text_func_sends_inline_keyboard_when_actions_exist() -> None:
    send_message = AsyncMock(return_value="text-message")
    sender = build_telegram_send_text_func(SimpleNamespace(bot=SimpleNamespace(send_message=send_message)))
    text = render_telegram_text(
        DeliveryItem(
            header=DeliveryHeader(kind="approval", title="待确认：下载"),
            sections=(DeliverySection(label="任务信息", lines=("片名：Dune 2021", "选择序号：hash-87")),),
            actions=(
                DeliveryAction(label="确认下载", hint="发送 confirm hash-87", kind="primary"),
                DeliveryAction(label="取消下载", hint="发送 cancel hash-87", kind="secondary"),
                DeliveryAction(label="查看状态", hint="发送 status hash-87", kind="secondary"),
            ),
            status="pending",
        )
    )

    result = asyncio.run(sender(chat_id=1001, text=text))

    assert result == "text-message"
    send_message.assert_awaited_once()
    kwargs = send_message.await_args.kwargs
    assert kwargs["chat_id"] == 1001
    assert kwargs["text"] == text
    reply_markup = kwargs["reply_markup"]
    assert isinstance(reply_markup, InlineKeyboardMarkup)
    assert tuple(tuple(button.text for button in row) for row in reply_markup.inline_keyboard) == (
        ("确认下载", "取消下载"),
        ("查看状态",),
    )
    assert tuple(tuple(button.callback_data for button in row) for row in reply_markup.inline_keyboard) == (
        ("confirm hash-87", "cancel hash-87"),
        ("status hash-87",),
    )


def test_build_telegram_send_text_func_supports_url_inline_actions() -> None:
    send_message = AsyncMock(return_value="text-message")
    sender = build_telegram_send_text_func(SimpleNamespace(bot=SimpleNamespace(send_message=send_message)))
    text = "\n".join(
        (
            "成人资源候选",
            "",
            "下一步",
            "🌐 查看详情 (avmoo)：打开 https://avmoo.shop/cn/movie/4221ec1035fdf66f",
            "➡️ 下一步：发送 magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12",
        )
    )

    result = asyncio.run(sender(chat_id=1001, text=text))

    assert result == "text-message"
    reply_markup = send_message.await_args.kwargs["reply_markup"]
    assert isinstance(reply_markup, InlineKeyboardMarkup)
    first_button, second_button = reply_markup.inline_keyboard[0]
    assert first_button.text == "🌐 查看详情 (avmoo)"
    assert first_button.url == "https://avmoo.shop/cn/movie/4221ec1035fdf66f"
    assert second_button.text == "➡️ 下一步"
    assert second_button.callback_data == "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12"


def test_build_telegram_send_text_func_skips_oversized_callback_queries() -> None:
    send_message = AsyncMock(return_value="text-message")
    sender = build_telegram_send_text_func(SimpleNamespace(bot=SimpleNamespace(send_message=send_message)))
    long_query = "search " + ("很长的查询" * 20)
    text = render_telegram_text(
        DeliveryItem(
            header=DeliveryHeader(kind="search_results", title="搜索：长查询"),
            sections=(DeliverySection(label="候选结果", lines=("1. Dune (2021)",)),),
            actions=(
                DeliveryAction(label="开始下载", hint="发送 select 1", kind="primary"),
                DeliveryAction(label="换关键词", hint=f"发送 {long_query}", kind="secondary"),
            ),
            status="success",
        )
    )

    result = asyncio.run(sender(chat_id=1001, text=text))

    assert result == "text-message"
    send_message.assert_awaited_once()
    reply_markup = send_message.await_args.kwargs["reply_markup"]
    assert isinstance(reply_markup, InlineKeyboardMarkup)
    assert tuple(tuple(button.text for button in row) for row in reply_markup.inline_keyboard) == (("开始下载",),)
    assert tuple(tuple(button.callback_data for button in row) for row in reply_markup.inline_keyboard) == (
        ("select 1",),
    )


def test_build_telegram_send_media_func_uses_document_for_non_image_path(
    tmp_path: Path,
) -> None:
    send_document = AsyncMock(return_value="document-message")
    sender = build_telegram_send_media_func(
        SimpleNamespace(
            bot=SimpleNamespace(
                send_photo=AsyncMock(),
                send_document=send_document,
            )
        )
    )
    file_path = tmp_path / "wechat-login.txt"
    file_path.write_text("login-token", encoding="utf-8")

    result = asyncio.run(sender(1001, file_path, "登录辅助文件"))

    assert result == "document-message"
    send_document.assert_awaited_once_with(
        chat_id=1001,
        document=file_path,
        caption="登录辅助文件",
        filename="wechat-login.txt",
    )


def test_build_telegram_send_media_func_passes_reply_markup_to_photo_messages(tmp_path: Path) -> None:
    send_photo = AsyncMock(return_value="photo-message")
    sender = build_telegram_send_media_func(
        SimpleNamespace(
            bot=SimpleNamespace(
                send_photo=send_photo,
                send_document=AsyncMock(),
            )
        )
    )
    file_path = tmp_path / "candidate.jpg"
    file_path.write_bytes(b"poster")
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton(text="确认作品 1", callback_data="1")]])

    result = asyncio.run(sender(1001, file_path, "候选卡片", "HTML", reply_markup))

    assert result == "photo-message"
    send_photo.assert_awaited_once_with(
        chat_id=1001,
        photo=file_path,
        caption="候选卡片",
        parse_mode="HTML",
        reply_markup=reply_markup,
    )


def test_build_telegram_send_media_func_logs_missing_file_and_raises(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    sender = build_telegram_send_media_func(
        SimpleNamespace(
            bot=SimpleNamespace(
                send_photo=AsyncMock(),
                send_document=AsyncMock(),
            )
        )
    )
    missing_path = tmp_path / "missing-qr.png"

    with pytest.raises(FileNotFoundError):
        asyncio.run(sender(1001, missing_path, "微信登录二维码"))

    captured = capsys.readouterr()
    assert "[Telegram 媒资发送失败]" in captured.out
    assert "文件不存在" in captured.out
    assert "[处理建议]" in captured.out

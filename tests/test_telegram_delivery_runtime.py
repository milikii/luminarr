from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.bot.telegram_delivery_runtime import build_telegram_send_media_func, build_telegram_send_text_func


def test_build_telegram_send_text_func_sends_message() -> None:
    send_message = AsyncMock(return_value="text-message")
    sender = build_telegram_send_text_func(SimpleNamespace(bot=SimpleNamespace(send_message=send_message)))

    result = asyncio.run(sender(chat_id=1001, text="扫码成功"))

    assert result == "text-message"
    send_message.assert_awaited_once_with(chat_id=1001, text="扫码成功")


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

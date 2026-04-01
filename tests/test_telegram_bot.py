from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.bot.telegram_bot import CONFIRM_TEXT, handle_message


def test_handle_message_replies_fixed_text() -> None:
    reply_text = AsyncMock()
    message = SimpleNamespace(reply_text=reply_text)
    update = SimpleNamespace(effective_message=message)

    asyncio.run(handle_message(update, None))

    reply_text.assert_awaited_once_with(CONFIRM_TEXT)


def test_handle_message_ignores_empty_update() -> None:
    update = SimpleNamespace(effective_message=None)
    asyncio.run(handle_message(update, None))

from __future__ import annotations

import asyncio
from collections.abc import MutableMapping
from typing import Any


class NonTelegramRuntimeHost:
    """Minimal asyncio host for sidecars that do not need Telegram polling."""

    def __init__(self, *, bot_data: MutableMapping[str, object] | None = None) -> None:
        self.bot_data: MutableMapping[str, object] = {} if bot_data is None else bot_data
        self._stop_event: asyncio.Event | None = None

    def create_task(self, coroutine, *, name: str) -> asyncio.Task[Any]:
        return asyncio.create_task(coroutine, name=name)

    async def wait_until_stopped(self) -> None:
        stop_event = asyncio.Event()
        self._stop_event = stop_event
        try:
            await stop_event.wait()
        finally:
            self._stop_event = None

    def stop(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()

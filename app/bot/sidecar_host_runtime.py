from __future__ import annotations

from collections.abc import Awaitable, MutableMapping
from typing import Any, Protocol

SIDECAR_HOST_SEND_TEXT_FUNC_KEY = "sidecar_host_send_text_func"


class SidecarHost(Protocol):
    """Minimal host boundary required by sidecars and schedulers."""

    bot_data: MutableMapping[str, object]

    def create_task(self, coroutine: Awaitable[Any], *, name: str) -> object:
        """Schedule a background task owned by the host."""


def resolve_sidecar_host_send_text_func(
    *,
    bot_data: MutableMapping[str, object],
    send_text_func_key: str = SIDECAR_HOST_SEND_TEXT_FUNC_KEY,
):
    """Resolve the host-injected text sender callback if present."""

    send_text_func = bot_data.get(send_text_func_key)
    if not callable(send_text_func):
        return None
    return send_text_func

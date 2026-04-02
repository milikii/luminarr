from __future__ import annotations

from collections.abc import Awaitable, Callable

RefreshFunc = Callable[[], Awaitable[None]]

REFRESH_SUCCESS_TEXT = "媒体库刷新成功。"
REFRESH_FAILED_TEXT_TEMPLATE = "媒体库刷新失败：{reason}"
REFRESH_FAILED_UNKNOWN_REASON = "未知错误"


class RefreshMediaServerService:
    def __init__(self, refresh_func: RefreshFunc) -> None:
        self._refresh_func = refresh_func

    async def refresh_text(self) -> str:
        try:
            await self._refresh_func()
        except Exception as exc:
            reason = str(exc).strip() or REFRESH_FAILED_UNKNOWN_REASON
            return REFRESH_FAILED_TEXT_TEMPLATE.format(reason=reason)
        return REFRESH_SUCCESS_TEXT

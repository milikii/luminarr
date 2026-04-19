from __future__ import annotations

from collections.abc import Awaitable, Callable

RefreshFunc = Callable[[], Awaitable[None]]

REFRESH_SUCCESS_TEXT = "媒体库刷新成功。"
REFRESH_FAILED_TEXT_TEMPLATE = "媒体库刷新失败：{reason}"
REFRESH_FAILED_UNKNOWN_REASON = "未知错误"


class RefreshMediaServerService:
    def __init__(self, refresh_func: RefreshFunc, *, provider_name: str = "media-server") -> None:
        self._refresh_func = refresh_func
        self._provider_name = provider_name.strip() or "media-server"

    async def refresh_text(self) -> str:
        try:
            await self._refresh_func()
        except Exception as exc:
            reason = str(exc).strip() or REFRESH_FAILED_UNKNOWN_REASON
            print(
                f"\033[31m[媒体库刷新失败]\033[0m provider={self._provider_name} 错误={reason}\n"
                "\033[33m[处理建议]\033[0m 检查媒体服务器地址、API Key 和网络连通性；当前会返回刷新失败文本，但导入成功不会回滚。",
                flush=True,
            )
            return REFRESH_FAILED_TEXT_TEMPLATE.format(reason=reason)
        return REFRESH_SUCCESS_TEXT

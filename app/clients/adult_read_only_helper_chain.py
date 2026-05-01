from __future__ import annotations

from collections.abc import Awaitable, Callable

import httpx

from app.clients.javlibrary_helper import JavLibraryReadOnlyMatch
from app.operational_logging import emit_operational_log

AdultReadOnlyLookupFunc = Callable[[str], Awaitable[JavLibraryReadOnlyMatch | None]]


def compose_adult_read_only_lookup_func(
    *,
    avmoo_lookup_func: AdultReadOnlyLookupFunc,
    javlibrary_lookup_func: AdultReadOnlyLookupFunc,
) -> AdultReadOnlyLookupFunc:
    async def lookup(lookup_text: str) -> JavLibraryReadOnlyMatch | None:
        try:
            avmoo_match = await avmoo_lookup_func(lookup_text)
        except httpx.HTTPError as error:
            emit_operational_log(
                title="Avmoo 只读补全失败",
                detail=f"query={lookup_text} 错误={error}",
                fix_hint="检查 Avmoo 可达性、代理和 HTML 结构；当前会继续尝试 JavLibrary 备援补全。",
            )
            avmoo_match = None
        if avmoo_match is not None:
            return avmoo_match
        return await javlibrary_lookup_func(lookup_text)

    return lookup

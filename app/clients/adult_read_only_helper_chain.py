from __future__ import annotations

from collections.abc import Awaitable, Callable

import httpx

from app.clients.javlibrary_helper import JavLibraryReadOnlyMatch
from app.operational_logging import emit_operational_log

AdultReadOnlyLookupFunc = Callable[[str], Awaitable[JavLibraryReadOnlyMatch | None]]


def compose_adult_read_only_lookup_func(
    *,
    avmoo_lookup_func: AdultReadOnlyLookupFunc,
    caribbeancom_lookup_func: AdultReadOnlyLookupFunc | None = None,
    avsox_lookup_func: AdultReadOnlyLookupFunc | None = None,
    javbus_lookup_func: AdultReadOnlyLookupFunc | None = None,
    javlibrary_lookup_func: AdultReadOnlyLookupFunc,
) -> AdultReadOnlyLookupFunc:
    async def lookup(lookup_text: str) -> JavLibraryReadOnlyMatch | None:
        caribbeancom_match = await _lookup_optional_helper(
            lookup_text,
            source_label="Caribbeancom",
            lookup_func=caribbeancom_lookup_func,
        )
        if caribbeancom_match is not None:
            return caribbeancom_match
        avmoo_match = await _lookup_optional_helper(
            lookup_text,
            source_label="Avmoo",
            lookup_func=avmoo_lookup_func,
        )
        if avmoo_match is not None:
            return avmoo_match
        for source_label, lookup_func in (
            ("Avsox", avsox_lookup_func),
            ("JavBus", javbus_lookup_func),
        ):
            helper_match = await _lookup_optional_helper(
                lookup_text,
                source_label=source_label,
                lookup_func=lookup_func,
            )
            if helper_match is not None:
                return helper_match
        return await javlibrary_lookup_func(lookup_text)

    return lookup


async def _lookup_optional_helper(
    lookup_text: str,
    *,
    source_label: str,
    lookup_func: AdultReadOnlyLookupFunc | None,
) -> JavLibraryReadOnlyMatch | None:
    if lookup_func is None:
        return None
    try:
        return await lookup_func(lookup_text)
    except httpx.HTTPError as error:
        emit_operational_log(
            title=f"{source_label} 只读补全失败",
            detail=f"query={lookup_text} 错误={error}",
            fix_hint=f"检查 {source_label} 可达性、代理和 HTML 结构；当前会继续尝试后续成人只读补全源。",
        )
        return None

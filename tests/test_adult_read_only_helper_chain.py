from __future__ import annotations

import asyncio

import httpx

from app.clients.adult_read_only_helper_chain import compose_adult_read_only_lookup_func
from app.clients.javlibrary_helper import JavLibraryReadOnlyMatch


def _build_match(*, source_site: str) -> JavLibraryReadOnlyMatch:
    return JavLibraryReadOnlyMatch(
        normalized_content_id="censored:ssis-123",
        display_id="SSIS-123",
        archive_category="censored",
        title="SSIS-123 Sample Title",
        detail_url=f"https://{source_site}.example/detail",
        source_site=source_site,
    )


def test_composed_adult_read_only_lookup_prefers_avmoo_over_javlibrary() -> None:
    calls: list[str] = []

    async def avmoo_lookup(lookup_text: str) -> JavLibraryReadOnlyMatch | None:
        calls.append(f"avmoo:{lookup_text}")
        return _build_match(source_site="avmoo")

    async def javlibrary_lookup(lookup_text: str) -> JavLibraryReadOnlyMatch | None:
        calls.append(f"javlibrary:{lookup_text}")
        raise AssertionError("JavLibrary backup should not be called after Avmoo match")

    lookup = compose_adult_read_only_lookup_func(
        avmoo_lookup_func=avmoo_lookup,
        javlibrary_lookup_func=javlibrary_lookup,
    )

    match = asyncio.run(lookup("SSIS-123"))

    assert match is not None
    assert match.source_site == "avmoo"
    assert calls == ["avmoo:SSIS-123"]


def test_composed_adult_read_only_lookup_falls_back_to_javlibrary_on_avmoo_miss() -> None:
    calls: list[str] = []

    async def avmoo_lookup(lookup_text: str) -> JavLibraryReadOnlyMatch | None:
        calls.append(f"avmoo:{lookup_text}")
        return None

    async def javlibrary_lookup(lookup_text: str) -> JavLibraryReadOnlyMatch | None:
        calls.append(f"javlibrary:{lookup_text}")
        return _build_match(source_site="javlibrary")

    lookup = compose_adult_read_only_lookup_func(
        avmoo_lookup_func=avmoo_lookup,
        javlibrary_lookup_func=javlibrary_lookup,
    )

    match = asyncio.run(lookup("SSIS-123"))

    assert match is not None
    assert match.source_site == "javlibrary"
    assert calls == ["avmoo:SSIS-123", "javlibrary:SSIS-123"]


def test_composed_adult_read_only_lookup_falls_back_to_javlibrary_on_avmoo_http_error(capsys) -> None:
    calls: list[str] = []

    async def avmoo_lookup(lookup_text: str) -> JavLibraryReadOnlyMatch | None:
        calls.append(f"avmoo:{lookup_text}")
        raise httpx.ConnectError("timeout", request=httpx.Request("GET", "https://avmoo.shop"))

    async def javlibrary_lookup(lookup_text: str) -> JavLibraryReadOnlyMatch | None:
        calls.append(f"javlibrary:{lookup_text}")
        return _build_match(source_site="javlibrary")

    lookup = compose_adult_read_only_lookup_func(
        avmoo_lookup_func=avmoo_lookup,
        javlibrary_lookup_func=javlibrary_lookup,
    )

    match = asyncio.run(lookup("SSIS-123"))

    assert match is not None
    assert match.source_site == "javlibrary"
    assert calls == ["avmoo:SSIS-123", "javlibrary:SSIS-123"]
    output = capsys.readouterr().out
    assert "[Avmoo 只读补全失败]" in output
    assert "timeout" in output

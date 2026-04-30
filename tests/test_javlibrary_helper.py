from __future__ import annotations

import asyncio

import httpx

from app.clients.javlibrary_helper import JavLibraryReadOnlyHelperClient


def test_javlibrary_read_only_helper_follows_search_result_to_detail(monkeypatch) -> None:
    requests: list[str] = []

    class FakeAsyncClient:
        def __init__(self, **_: object) -> None:
            pass

        async def __aenter__(self) -> FakeAsyncClient:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, url: str) -> httpx.Response:
            requests.append(url)
            if url == "https://www.javlibrary.com/tw/vl_searchbyid.php?keyword=SSIS-123":
                return httpx.Response(
                    200,
                    text=(
                        '<div class="videos">'
                        '<a href="./?v=javli0001" title="SSIS-123 Sample Title">'
                        "SSIS-123 Sample Title"
                        "</a>"
                        "</div>"
                    ),
                    request=httpx.Request("GET", url),
                )
            if url == "https://www.javlibrary.com/tw/?v=javli0001":
                return httpx.Response(
                    200,
                    text=(
                        '<div id="video_title"><a rel="bookmark">SSIS-123 Sample Title</a></div>'
                        '<div id="video_id"><table><tr><td class="text">SSIS-123</td></tr></table></div>'
                        '<img id="video_jacket_img" src="//img.example/ssis-123.jpg">'
                        '<span class="header">发行日期:</span><span class="text">2026-04-01</span>'
                        '<span class="header">长度:</span><span class="text">120分钟</span>'
                        '<span class="header">导演:</span><span class="text">Director A</span>'
                        '<span class="header">制作商:</span><span class="text">S1</span>'
                        '<span class="header">系列:</span><span class="text">Secret Mission</span>'
                        '<span class="header">类别:</span><span class="text">Drama Nurse</span>'
                        '<span class="star"><a>Aki</a></span><span class="star"><a>Mei</a></span>'
                    ),
                    request=httpx.Request("GET", url),
                )
            raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient(**kwargs))

    client = JavLibraryReadOnlyHelperClient()
    match = asyncio.run(client.lookup("SSIS-123"))

    assert requests == [
        "https://www.javlibrary.com/tw/vl_searchbyid.php?keyword=SSIS-123",
        "https://www.javlibrary.com/tw/?v=javli0001",
    ]
    assert match is not None
    assert match.normalized_content_id == "censored:ssis-123"
    assert match.display_id == "SSIS-123"
    assert match.archive_category == "censored"
    assert match.title == "SSIS-123 Sample Title"
    assert match.detail_url == "https://www.javlibrary.com/tw/?v=javli0001"
    assert match.poster_url == "https://img.example/ssis-123.jpg"
    assert match.release_date == "2026-04-01"
    assert match.duration == "120分钟"
    assert match.director == "Director A"
    assert match.studio == "S1"
    assert match.series == "Secret Mission"
    assert match.genres == ("Drama", "Nurse")
    assert match.actors == ("Aki", "Mei")


def test_javlibrary_read_only_helper_accepts_direct_detail_response(monkeypatch) -> None:
    requests: list[str] = []

    class FakeAsyncClient:
        def __init__(self, **_: object) -> None:
            pass

        async def __aenter__(self) -> FakeAsyncClient:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, url: str) -> httpx.Response:
            requests.append(url)
            return httpx.Response(
                200,
                text="<title>SSIS-456 Another Sample - JAVLibrary</title>",
                request=httpx.Request("GET", "https://www.javlibrary.com/tw/?v=javli0002"),
            )

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient(**kwargs))

    client = JavLibraryReadOnlyHelperClient()
    match = asyncio.run(client.lookup("ssis456"))

    assert requests == ["https://www.javlibrary.com/tw/vl_searchbyid.php?keyword=SSIS-456"]
    assert match is not None
    assert match.normalized_content_id == "censored:ssis-456"
    assert match.display_id == "SSIS-456"
    assert match.title == "SSIS-456 Another Sample"
    assert match.detail_url == "https://www.javlibrary.com/tw/?v=javli0002"


def test_javlibrary_read_only_helper_ignores_non_censored_lookup(monkeypatch) -> None:
    class FakeAsyncClient:
        def __init__(self, **_: object) -> None:
            raise AssertionError("httpx client should not be created for unsupported lookup")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient(**kwargs))

    client = JavLibraryReadOnlyHelperClient()

    assert asyncio.run(client.lookup("FC2-PPV-1234567")) is None

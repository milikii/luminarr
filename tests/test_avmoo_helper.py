from __future__ import annotations

import asyncio

import httpx

from app.clients.avmoo_helper import AvmooReadOnlyHelperClient


SEARCH_HTML = """
<html>
  <body>
    <a class="movie-box" href="//avmoo.shop/cn/movie/4221ec1035fdf66f">
      <div class="photo-frame">
        <img src="//jp.netcdn.space/digital/video/ssis00483/ssis00483ps.jpg" title="SSIS-483 Search Title">
      </div>
      <div class="photo-info">
        <span>SSIS-483 Search Title</span>
        <date>SSIS-483</date>
        <date>2023-05-01</date>
      </div>
    </a>
  </body>
</html>
"""

DETAIL_HTML = """
<html>
  <head><title>SSIS-483 Detail Title - Avmoo</title></head>
  <body>
    <a class="bigImage" href="//jp.netcdn.space/digital/video/ssis00483/ssis00483pl.jpg">
      <img src="//jp.netcdn.space/digital/video/ssis00483/ssis00483ps.jpg">
    </a>
    <h3>SSIS-483 Detail Title</h3>
    <p><span class="header">识别码:</span> SSIS-483</p>
    <p><span class="header">发行时间:</span> 2023-05-01</p>
    <p><span class="header">长度:</span> 120分钟</p>
    <p><span class="header">导演:</span> <a href="/cn/director/director-a">Director A</a></p>
    <p><span class="header">制作商:</span> <a href="/cn/studio/s1">S1</a></p>
    <p><span class="header">发行商:</span> <a href="/cn/label/s1-label">S1 Label</a></p>
    <p><span class="header">系列:</span> <a href="/cn/series/secret">Secret Mission</a></p>
    <p><span class="header">类别:</span> <a class="genre">Drama</a> <a class="genre">Nurse</a></p>
    <a class="avatar-box" href="/cn/star/aki"><span>Aki</span></a>
    <a class="avatar-box" href="/cn/star/mei"><span>Mei</span></a>
  </body>
</html>
"""

DETAIL_HTML_WITH_SIBLING_HEADER_ROWS = """
<html>
  <head><title>SSIS-483 Detail Title - Avmoo</title></head>
  <body>
    <a class="bigImage" href="//jp.netcdn.space/digital/video/ssis00483/ssis00483pl.jpg">
      <img src="//jp.netcdn.space/digital/video/ssis00483/ssis00483ps.jpg">
    </a>
    <h3>SSIS-483 Detail Title</h3>
    <p><span class="header">识别码:</span> SSIS-483</p>
    <p><span class="header">发行时间:</span> 2023-05-01</p>
    <p><span class="header">长度:</span> 120分钟</p>
    <p><span class="header">制作商:</span></p>
    <p><a href="/cn/studio/s1">S1</a></p>
    <p><span class="header">发行商:</span></p>
    <p><a href="/cn/label/s1-label">S1 Label</a></p>
    <p><span class="header">系列:</span></p>
    <p><a href="/cn/series/secret">Secret Mission</a></p>
    <p><span class="header">类别:</span></p>
    <p><a class="genre">Drama</a> <a class="genre">Nurse</a></p>
    <a class="avatar-box" href="/cn/star/aki"><span>Aki</span></a>
  </body>
</html>
"""


def test_avmoo_read_only_helper_follows_search_result_to_detail(monkeypatch) -> None:
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
            if url == "https://avmoo.shop/cn/search/SSIS-483":
                return httpx.Response(200, text=SEARCH_HTML, request=httpx.Request("GET", url))
            if url == "https://avmoo.shop/cn/movie/4221ec1035fdf66f":
                return httpx.Response(200, text=DETAIL_HTML, request=httpx.Request("GET", url))
            raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient(**kwargs))

    client = AvmooReadOnlyHelperClient()
    match = asyncio.run(client.lookup("SSIS-483"))

    assert requests == [
        "https://avmoo.shop/cn/search/SSIS-483",
        "https://avmoo.shop/cn/movie/4221ec1035fdf66f",
    ]
    assert match is not None
    assert match.normalized_content_id == "censored:ssis-483"
    assert match.display_id == "SSIS-483"
    assert match.archive_category == "censored"
    assert match.source_site == "avmoo"
    assert match.title == "SSIS-483 Detail Title"
    assert match.detail_url == "https://avmoo.shop/cn/movie/4221ec1035fdf66f"
    assert match.poster_url == "https://jp.netcdn.space/digital/video/ssis00483/ssis00483pl.jpg"
    assert match.release_date == "2023-05-01"
    assert match.runtime == "120分钟"
    assert match.duration == "120分钟"
    assert match.director == "Director A"
    assert match.maker == "S1"
    assert match.studio == "S1"
    assert match.label == "S1 Label"
    assert match.series == "Secret Mission"
    assert match.genres == ("Drama", "Nurse")
    assert match.actors == ("Aki", "Mei")


def test_avmoo_read_only_helper_accepts_direct_detail_response(monkeypatch) -> None:
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
                text=DETAIL_HTML,
                request=httpx.Request("GET", "https://avmoo.shop/cn/movie/4221ec1035fdf66f"),
            )

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient(**kwargs))

    client = AvmooReadOnlyHelperClient()
    match = asyncio.run(client.lookup("ssis483"))

    assert requests == ["https://avmoo.shop/cn/search/SSIS-483"]
    assert match is not None
    assert match.normalized_content_id == "censored:ssis-483"
    assert match.display_id == "SSIS-483"
    assert match.source_site == "avmoo"
    assert match.detail_url == "https://avmoo.shop/cn/movie/4221ec1035fdf66f"


def test_avmoo_read_only_helper_extracts_sibling_header_rows(monkeypatch) -> None:
    class FakeAsyncClient:
        def __init__(self, **_: object) -> None:
            pass

        async def __aenter__(self) -> FakeAsyncClient:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, url: str) -> httpx.Response:
            return httpx.Response(
                200,
                text=DETAIL_HTML_WITH_SIBLING_HEADER_ROWS,
                request=httpx.Request("GET", "https://avmoo.shop/cn/movie/4221ec1035fdf66f"),
            )

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient(**kwargs))

    client = AvmooReadOnlyHelperClient()
    match = asyncio.run(client.lookup("SSIS-483"))

    assert match is not None
    assert match.maker == "S1"
    assert match.studio == "S1"
    assert match.label == "S1 Label"
    assert match.series == "Secret Mission"
    assert match.genres == ("Drama", "Nurse")


def test_avmoo_read_only_helper_ignores_non_censored_lookup(monkeypatch) -> None:
    class FakeAsyncClient:
        def __init__(self, **_: object) -> None:
            raise AssertionError("httpx client should not be created for unsupported lookup")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient(**kwargs))

    client = AvmooReadOnlyHelperClient()

    assert asyncio.run(client.lookup("FC2-PPV-1234567")) is None

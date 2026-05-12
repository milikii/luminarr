from __future__ import annotations

import asyncio

import httpx

from app.clients.avsox_helper import AvsoxReadOnlyHelperClient

SEARCH_HTML = """
<html>
  <body>
    <a class="movie-box" href="//avsox.click/cn/movie/abc123">
      <div class="photo-frame">
        <img src="//img.example/ssis00483/cover-small.jpg" title="SSIS-483 Search Title">
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
  <head><title>SSIS-483 Avsox Detail - AVSOX</title></head>
  <body>
    <a class="bigImage" href="//img.example/ssis00483/cover-large.jpg">
      <img src="//img.example/ssis00483/cover-small.jpg">
    </a>
    <h3>SSIS-483 Avsox Detail</h3>
    <p><span class="header">识别码:</span> SSIS-483</p>
    <p><span class="header">发行时间:</span> 2023-05-01</p>
    <p><span class="header">长度:</span> 118分钟</p>
    <p><span class="header">制作商:</span> <a href="/cn/studio/s1">S1</a></p>
    <p><span class="header">类别:</span> <a class="genre">Drama</a> <a class="genre">Nurse</a></p>
    <a class="avatar-box" href="/cn/star/aki"><span>Aki</span></a>
  </body>
</html>
"""


def test_avsox_read_only_helper_follows_search_result_to_detail(monkeypatch) -> None:
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
            if url == "https://avsox.click/cn/search/SSIS-483":
                return httpx.Response(200, text=SEARCH_HTML, request=httpx.Request("GET", url))
            if url == "https://avsox.click/cn/movie/abc123":
                return httpx.Response(200, text=DETAIL_HTML, request=httpx.Request("GET", url))
            raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient(**kwargs))

    client = AvsoxReadOnlyHelperClient()
    match = asyncio.run(client.lookup("SSIS-483"))

    assert requests == [
        "https://avsox.click/cn/search/SSIS-483",
        "https://avsox.click/cn/movie/abc123",
    ]
    assert match is not None
    assert match.normalized_content_id == "censored:ssis-483"
    assert match.display_id == "SSIS-483"
    assert match.archive_category == "censored"
    assert match.source_site == "avsox"
    assert match.title == "SSIS-483 Avsox Detail"
    assert match.detail_url == "https://avsox.click/cn/movie/abc123"
    assert match.poster_url == "https://img.example/ssis00483/cover-large.jpg"
    assert match.release_date == "2023-05-01"
    assert match.runtime == "118分钟"
    assert match.studio == "S1"
    assert match.genres == ("Drama", "Nurse")
    assert match.actors == ("Aki",)


def test_avsox_read_only_helper_ignores_non_censored_lookup(monkeypatch) -> None:
    class FakeAsyncClient:
        def __init__(self, **_: object) -> None:
            raise AssertionError("httpx client should not be created for unsupported lookup")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient(**kwargs))

    client = AvsoxReadOnlyHelperClient()

    assert asyncio.run(client.lookup("FC2-PPV-1234567")) is None

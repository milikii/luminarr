from __future__ import annotations

import asyncio

import httpx

from app.clients.javbus_helper import JavBusReadOnlyHelperClient

SEARCH_HTML = """
<html>
  <body>
    <a class="movie-box" href="/SSIS-123">
      <div class="photo-frame">
        <img src="/pics/cover-small.jpg" title="SSIS-123 Bus Search Title">
      </div>
      <div class="photo-info">
        <span>SSIS-123 Bus Search Title</span>
        <date>SSIS-123</date>
      </div>
    </a>
  </body>
</html>
"""


DETAIL_HTML = """
<html>
  <head><title>SSIS-123 Bus Detail - JavBus</title></head>
  <body>
    <a class="bigImage" href="/pics/cover-large.jpg">
      <img src="/pics/cover-small.jpg">
    </a>
    <h3>SSIS-123 Bus Detail</h3>
    <p><span class="header">識別碼:</span> SSIS-123</p>
    <p><span class="header">發行日期:</span> 2024-01-02</p>
    <p><span class="header">長度:</span> 121分鐘</p>
    <p><span class="header">製作商:</span> <a href="/studio/s1">S1</a></p>
    <p><span class="header">系列:</span> <a href="/series/secret">Secret Mission</a></p>
    <p><span class="header">類別:</span> <a class="genre">Drama</a> <a class="genre">Nurse</a></p>
    <a class="avatar-box" href="/star/aki"><span>Aki</span></a>
    <a class="avatar-box" href="/star/mei"><span>Mei</span></a>
  </body>
</html>
"""


def test_javbus_read_only_helper_follows_search_result_to_detail(monkeypatch) -> None:
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
            if url == "https://www.javbus.com/search/SSIS-123":
                return httpx.Response(200, text=SEARCH_HTML, request=httpx.Request("GET", url))
            if url == "https://www.javbus.com/SSIS-123":
                return httpx.Response(200, text=DETAIL_HTML, request=httpx.Request("GET", url))
            raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient(**kwargs))

    client = JavBusReadOnlyHelperClient()
    match = asyncio.run(client.lookup("SSIS-123"))

    assert requests == [
        "https://www.javbus.com/search/SSIS-123",
        "https://www.javbus.com/SSIS-123",
    ]
    assert match is not None
    assert match.normalized_content_id == "censored:ssis-123"
    assert match.display_id == "SSIS-123"
    assert match.archive_category == "censored"
    assert match.source_site == "javbus"
    assert match.title == "SSIS-123 Bus Detail"
    assert match.detail_url == "https://www.javbus.com/SSIS-123"
    assert match.poster_url == "https://www.javbus.com/pics/cover-large.jpg"
    assert match.release_date == "2024-01-02"
    assert match.runtime == "121分鐘"
    assert match.studio == "S1"
    assert match.series == "Secret Mission"
    assert match.genres == ("Drama", "Nurse")
    assert match.actors == ("Aki", "Mei")


def test_javbus_read_only_helper_ignores_non_censored_lookup(monkeypatch) -> None:
    class FakeAsyncClient:
        def __init__(self, **_: object) -> None:
            raise AssertionError("httpx client should not be created for unsupported lookup")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient(**kwargs))

    client = JavBusReadOnlyHelperClient()

    assert asyncio.run(client.lookup("FC2-PPV-1234567")) is None

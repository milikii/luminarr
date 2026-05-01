from __future__ import annotations

import asyncio

import httpx

from app.clients.caribbeancom_helper import CaribbeancomReadOnlyHelperClient


DETAIL_HTML = """
<html>
  <head>
    <title>CARIB-042123-001 Caribbean Detail</title>
    <meta property="og:image" content="https://www.caribbeancom.com/moviepages/042123-001/images/l_l.jpg">
  </head>
  <body>
    <h1>CARIB-042123-001 Caribbean Detail</h1>
    <span class="movie-id">042123-001</span>
    <span class="release-date">2023/04/21</span>
    <span class="movie-info"> 120min </span>
    <a href="/actress/aki/">Aki</a>
    <a href="/actress/mei/">Mei</a>
  </body>
</html>
"""


def test_caribbeancom_read_only_helper_reads_exact_direct_uncensored_page(monkeypatch) -> None:
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
            if url == "https://www.caribbeancom.com/moviepages/042123-001/index.html":
                return httpx.Response(200, text=DETAIL_HTML, request=httpx.Request("GET", url))
            raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient(**kwargs))

    client = CaribbeancomReadOnlyHelperClient()
    match = asyncio.run(client.lookup("CARIB-042123-001"))

    assert requests == ["https://www.caribbeancom.com/moviepages/042123-001/index.html"]
    assert match is not None
    assert match.normalized_content_id == "carib:042123-001"
    assert match.display_id == "CARIB-042123-001"
    assert match.archive_category == "uncensored"
    assert match.source_site == "caribbeancom"
    assert match.title == "CARIB-042123-001 Caribbean Detail"
    assert match.detail_url == "https://www.caribbeancom.com/moviepages/042123-001/index.html"
    assert match.poster_url == "https://www.caribbeancom.com/moviepages/042123-001/images/l_l.jpg"
    assert match.release_date == "2023/04/21"
    assert match.runtime == "120min"
    assert match.actors == ("Aki", "Mei")


def test_caribbeancom_read_only_helper_ignores_non_carib_lookup(monkeypatch) -> None:
    class FakeAsyncClient:
        def __init__(self, **_: object) -> None:
            raise AssertionError("httpx client should not be created for unsupported lookup")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient(**kwargs))

    client = CaribbeancomReadOnlyHelperClient()

    assert asyncio.run(client.lookup("SSIS-123")) is None
    assert asyncio.run(client.lookup("1PON-042123-001")) is None

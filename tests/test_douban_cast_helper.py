from __future__ import annotations

import asyncio
from pathlib import Path

import httpx

from app.clients.douban_cast_helper import DoubanCastHelperClient


def test_douban_cast_helper_sends_browser_like_headers(monkeypatch) -> None:
    seen_requests: list[httpx.Request] = []

    class FakeAsyncClient:
        def __init__(self, **kwargs: object) -> None:
            self._headers = kwargs.get("headers")

        async def __aenter__(self) -> FakeAsyncClient:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, url: str) -> httpx.Response:
            request = httpx.Request("GET", url, headers=self._headers)
            seen_requests.append(request)
            if url == "https://movie.douban.test/j/subject_suggest?q=Akron":
                return httpx.Response(
                    200,
                    json=[
                        {
                            "id": "361018",
                            "title": "爱的进行时",
                            "sub_title": "Akron",
                            "year": "2015",
                        }
                    ],
                    request=request,
                )
            if url == "https://movie.douban.test/subject/361018/?dt_dapp=1":
                return httpx.Response(
                    200,
                    text=(
                        '<li class="celebrity" data-original-name="Matthew Frias">'
                        '<a title="马修·弗莱斯">马修·弗莱斯</a>'
                        '<span class="role" title="饰 班尼·克鲁兹">饰 班尼·克鲁兹</span>'
                        "</li>"
                    ),
                    request=request,
                )
            raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient(**kwargs))

    client = DoubanCastHelperClient(base_url="https://movie.douban.test")
    asyncio.run(client.lookup(title="Akron", original_title="Akron", year="2015"))

    assert [str(request.url) for request in seen_requests] == [
        "https://movie.douban.test/j/subject_suggest?q=Akron",
        "https://movie.douban.test/subject/361018/?dt_dapp=1",
    ]
    for request in seen_requests:
        assert request.headers["User-Agent"].startswith("Mozilla/5.0")
        assert request.headers["Accept"] == "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        assert request.headers["Accept-Language"] == "zh-CN,zh;q=0.9,en;q=0.8"
        assert request.headers["Referer"] == "https://movie.douban.test/"


def test_douban_cast_helper_uses_original_title_fallback_and_parses_cast_fixture(monkeypatch) -> None:
    fixture_html = (
        Path(__file__).resolve().parent / "fixtures" / "douban_subject_cast.html"
    ).read_text(encoding="utf-8")
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
            if url == "https://movie.douban.test/j/subject_suggest?q=%E7%88%B1%E7%9A%84%E8%BF%9B%E8%A1%8C%E6%97%B6":
                return httpx.Response(200, json=[], request=httpx.Request("GET", url))
            if url == "https://movie.douban.test/j/subject_suggest?q=Akron":
                return httpx.Response(
                    200,
                    json=[
                        {
                            "id": "361018",
                            "title": "爱的进行时",
                            "sub_title": "Akron",
                            "year": "2015",
                        }
                    ],
                    request=httpx.Request("GET", url),
                )
            if url == "https://movie.douban.test/subject/361018/?dt_dapp=1":
                return httpx.Response(200, text=fixture_html, request=httpx.Request("GET", url))
            raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient(**kwargs))

    client = DoubanCastHelperClient(base_url="https://movie.douban.test")
    matches = asyncio.run(client.lookup(title="爱的进行时", original_title="Akron", year="2015"))

    assert requests == [
        "https://movie.douban.test/j/subject_suggest?q=%E7%88%B1%E7%9A%84%E8%BF%9B%E8%A1%8C%E6%97%B6",
        "https://movie.douban.test/j/subject_suggest?q=Akron",
        "https://movie.douban.test/subject/361018/?dt_dapp=1",
    ]
    assert [
        (match.order, match.original_name, match.localized_name, match.localized_character)
        for match in matches
    ] == [
        (0, "Matthew Frias", "马修·弗莱斯", "班尼·克鲁兹"),
        (1, "Edmund Donovan", "埃德蒙·多诺万", "克里斯托弗"),
    ]

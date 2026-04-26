from __future__ import annotations

import asyncio
import httpx

from app.clients.web_source import (
    JAVBUS_RULE,
    NYAA_RULE,
    TOKYOTOSHO_RULE,
    SUKEBEI_RULE,
    UnsupportedWebSourcePageError,
    WebSourceClient,
    is_supported_web_source_page_url,
    looks_like_web_source_page_request,
    parse_web_source_html,
    resolve_supported_web_source_page_request,
)
from app.services.bt_sources import BtSourceAdapter, BtSourceProvider, build_bt_candidate_dedupe_key


def test_bt_source_adapter_normalizes_candidates_and_deduplicates_by_info_hash() -> None:
    async def prowlarr_search(_: str) -> list[dict[str, object]]:
        return [
            {
                "title": "Frieren S01E01 1080p",
                "magnetUrl": "magnet:?xt=urn:btih:ABCDEF1234567890ABCDEF1234567890ABCDEF12&dn=frieren",
                "seeders": "12",
                "size": "2048",
                "indexer": {"name": "Prowlarr-A"},
            }
        ]

    async def web_source_search(_: str) -> list[dict[str, object]]:
        return [
            {
                "title": "Frieren S01E01 1080p",
                "downloadUrl": "https://example.com/frieren-e01.torrent",
                "infoHash": "abcdef1234567890abcdef1234567890abcdef12",
                "seeders": 99,
                "size": 4096,
                "indexerName": "Web-A",
            },
            {
                "title": "Frieren S01E02 720p",
                "downloadUrl": "https://example.com/frieren-e02.torrent",
            },
        ]

    adapter = BtSourceAdapter(
        (
            BtSourceProvider(name="prowlarr", search_func=prowlarr_search),
            BtSourceProvider(name="websource", search_func=web_source_search),
        )
    )

    results = asyncio.run(adapter.search("frieren"))

    assert len(results) == 2

    first = results[0]
    assert first["title"] == "Frieren S01E01 1080p"
    assert first["source"].startswith("magnet:?xt=urn:btih:")
    assert first["magnetUrl"] == first["source"]
    assert first["infoHash"] == "abcdef1234567890abcdef1234567890abcdef12"
    assert first["seeders"] == 12
    assert first["size"] == 2048
    assert first["indexerName"] == "Prowlarr-A"
    assert first["parsedMediaName"].title == "Frieren"
    assert first["parsedMediaName"].season == 1
    assert first["parsedMediaName"].episode == 1
    assert build_bt_candidate_dedupe_key(first) == "info_hash:abcdef1234567890abcdef1234567890abcdef12"

    second = results[1]
    assert second["title"] == "Frieren S01E02 720p"
    assert second["source"] == "https://example.com/frieren-e02.torrent"
    assert second["downloadUrl"] == "https://example.com/frieren-e02.torrent"
    assert second["indexerName"] == "websource"
    assert second["parsedMediaName"].episode == 2


def test_bt_source_adapter_skips_candidates_without_title_or_source() -> None:
    async def broken_search(_: str) -> list[dict[str, object]]:
        return [
            {"title": "", "downloadUrl": "https://example.com/invalid.torrent"},
            {"title": "missing source"},
        ]

    adapter = BtSourceAdapter((BtSourceProvider(name="broken", search_func=broken_search),))

    results = asyncio.run(adapter.search("frieren"))

    assert results == []


def test_bt_source_adapter_only_persists_exact_adult_id_and_skips_keyword_only_guess() -> None:
    async def adult_search(_: str) -> list[dict[str, object]]:
        return [
            {
                "title": "【中文字幕】 一本道 042123_001 1080p 无码流出",
                "downloadUrl": "https://example.com/1pon-042123-001.torrent",
            },
            {
                "title": "麻豆 中文字幕 无码流出 合集",
                "downloadUrl": "https://example.com/madou-collection.torrent",
            },
        ]

    adapter = BtSourceAdapter((BtSourceProvider(name="adult", search_func=adult_search),))

    results = asyncio.run(adapter.search("adult"))

    assert len(results) == 2
    assert results[0]["adult_content_id"] == "1pon:042123-001"
    assert results[0]["adult_archive_category"] == "uncensored"
    assert results[0]["adult_display_id"] == "1PON-042123-001"
    assert "adult_content_id" not in results[1]
    assert "adult_archive_category" not in results[1]
    assert "adult_display_id" not in results[1]


def test_parse_web_source_html_extracts_size_and_seeders_for_nyaa() -> None:
    html = """
    <table>
      <tbody>
        <tr class="default">
          <td class="text-center"><a href="/?c=1_2">Anime</a></td>
          <td colspan="2">
            <a href="/view/123" title="Frieren S01E01 1080p">Frieren S01E01 1080p</a>
            <a href="/download/123.torrent">torrent</a>
            <a href="magnet:?xt=urn:btih:ABCDEF1234567890ABCDEF1234567890ABCDEF12&amp;dn=frieren">magnet</a>
          </td>
          <td class="text-center">1.5 GiB</td>
          <td class="text-center">2026-04-05 12:00</td>
          <td class="text-center">88</td>
          <td class="text-center">4</td>
          <td class="text-center">1024</td>
        </tr>
      </tbody>
    </table>
    """

    results = parse_web_source_html(html, rule=NYAA_RULE)

    assert len(results) == 1
    first = results[0]
    assert first["title"] == "Frieren S01E01 1080p"
    assert first["source"].startswith("magnet:?xt=urn:btih:ABCDEF1234567890ABCDEF1234567890ABCDEF12")
    assert first["indexerName"] == "nyaa"
    assert first["seeders"] == 88
    assert first["size"] == int(1.5 * 1024 * 1024 * 1024)


def test_parse_web_source_html_extracts_tokyotosho_candidate() -> None:
    html = """
    <table>
      <tbody>
        <tr>
          <td><a href="/details.php?id=777">SSIS-123 Sample Title</a></td>
          <td><a href="magnet:?xt=urn:btih:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA&dn=ssis-123">magnet</a></td>
          <td>2.1 GiB</td>
          <td>52</td>
        </tr>
      </tbody>
    </table>
    """

    results = parse_web_source_html(html, rule=TOKYOTOSHO_RULE)

    assert len(results) == 1
    first = results[0]
    assert first["title"] == "SSIS-123 Sample Title"
    assert first["source"].startswith("magnet:?xt=urn:btih:AAAAAAAA")
    assert first["indexerName"] == "tokyotosho"
    assert first["seeders"] == 52


def test_web_source_client_passes_proxy_to_httpx(monkeypatch) -> None:
    client_kwargs: list[dict[str, object]] = []

    class FakeAsyncClient:
        def __init__(self, **kwargs: object) -> None:
            client_kwargs.append(dict(kwargs))

        async def __aenter__(self) -> FakeAsyncClient:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, url: str) -> httpx.Response:
            return httpx.Response(200, text="<html></html>", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient(**kwargs))

    client = WebSourceClient(rule=NYAA_RULE, proxy_url="http://192.168.2.110:7890")
    result = asyncio.run(client.search("frieren"))

    assert result == []
    assert client_kwargs
    assert client_kwargs[0]["proxy"] == "http://192.168.2.110:7890"


def test_web_source_client_search_supports_javbus_detail_follow_up(monkeypatch) -> None:
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
                return httpx.Response(
                    200,
                    text=(
                        '<a class="movie-box" href="/SSIS-123">'
                        '<img title="SSIS-123 Sample Title" />'
                        "<date>SSIS-123</date>"
                        "</a>"
                    ),
                    request=httpx.Request("GET", url),
                )
            if url == "https://www.javbus.com/SSIS-123":
                return httpx.Response(
                    200,
                    text='<a href="magnet:?xt=urn:btih:BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB&dn=ssis-123">magnet</a>',
                    request=httpx.Request("GET", url),
                )
            raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient(**kwargs))

    client = WebSourceClient(rule=JAVBUS_RULE)
    results = asyncio.run(client.search("SSIS-123"))

    assert requests == [
        "https://www.javbus.com/search/SSIS-123",
        "https://www.javbus.com/SSIS-123",
    ]
    assert len(results) == 1
    assert results[0]["title"] == "SSIS-123 Sample Title"
    assert results[0]["source"].startswith("magnet:?xt=urn:btih:BBBBBBBB")


def test_is_supported_web_source_page_url_accepts_nyaa_user_search_list_home_pagination_sort_and_category_sort_pages() -> None:
    assert is_supported_web_source_page_url("https://nyaa.si/")
    assert is_supported_web_source_page_url("https://nyaa.si/?c=1_2")
    assert is_supported_web_source_page_url("https://nyaa.si/?u=subsplease")
    assert is_supported_web_source_page_url("https://nyaa.si/?u=subsplease&s=seeders&o=desc")
    assert is_supported_web_source_page_url("https://nyaa.si/?f=0&c=1_2&u=subsplease")
    assert is_supported_web_source_page_url("https://nyaa.si/?f=0&c=1_2&q=frieren")
    assert is_supported_web_source_page_url("https://nyaa.si/?c=1_2&q=frieren")
    assert is_supported_web_source_page_url("https://nyaa.si/?q=frieren")
    assert is_supported_web_source_page_url("https://nyaa.si/?q=frieren&p=2")
    assert is_supported_web_source_page_url("https://nyaa.si/?c=1_2&q=frieren&p=2")
    assert is_supported_web_source_page_url("https://nyaa.si/?f=0&c=1_2&q=frieren&p=2")
    assert is_supported_web_source_page_url("https://nyaa.si/?f=0&c=1_2&q=frieren&s=seeders&o=desc")
    assert is_supported_web_source_page_url("https://nyaa.si/?f=0&c=1_2&q=frieren&s=seeders&o=desc&p=2")
    assert is_supported_web_source_page_url("https://nyaa.si/?f=0&c=1_2&p=2")
    assert is_supported_web_source_page_url("https://nyaa.si/?p=2")
    assert is_supported_web_source_page_url("https://nyaa.si/?s=seeders&o=desc")
    assert is_supported_web_source_page_url("https://nyaa.si/?s=seeders&o=desc&p=2")
    assert is_supported_web_source_page_url("https://nyaa.si/?c=1_2&s=seeders&o=desc")
    assert is_supported_web_source_page_url("https://nyaa.si/?c=1_2&s=seeders&o=desc&p=2")
    assert is_supported_web_source_page_url("https://nyaa.si/?f=0&c=1_2&u=subsplease&s=seeders&o=desc")
    assert not is_supported_web_source_page_url("https://nyaa.si/view/123")
    assert not is_supported_web_source_page_url("https://nyaa.si/?offset=32")
    assert not is_supported_web_source_page_url("https://nyaa.si/?s=seeders")
    assert not is_supported_web_source_page_url("https://nyaa.si/?c=1_2&s=seeders")
    assert not is_supported_web_source_page_url("https://nyaa.si/?f=0&c=1_2&q=frieren&s=seeders")
    assert not is_supported_web_source_page_url("https://nyaa.si/?f=0&c=1_2&u=subsplease&s=seeders")
    assert not is_supported_web_source_page_url("https://example.com/?q=frieren")


def test_is_supported_web_source_page_url_rejects_non_preview_sites() -> None:
    assert not is_supported_web_source_page_url("https://www.tokyotosho.info/search.php?terms=SSIS-123", rule=TOKYOTOSHO_RULE)
    assert is_supported_web_source_page_url("https://sukebei.nyaa.si/?u=offkab", rule=SUKEBEI_RULE)


def test_resolve_supported_web_source_page_request_appends_page_number() -> None:
    assert resolve_supported_web_source_page_request("https://nyaa.si/") == "https://nyaa.si/"
    assert resolve_supported_web_source_page_request("https://nyaa.si/?c=1_2") == "https://nyaa.si/?c=1_2"
    assert resolve_supported_web_source_page_request("https://nyaa.si/?u=subsplease") == "https://nyaa.si/?u=subsplease"
    assert (
        resolve_supported_web_source_page_request("https://nyaa.si/?f=0&c=1_2&q=frieren")
        == "https://nyaa.si/?f=0&c=1_2&q=frieren"
    )
    assert (
        resolve_supported_web_source_page_request("https://nyaa.si/?c=1_2&q=frieren")
        == "https://nyaa.si/?c=1_2&q=frieren"
    )
    assert looks_like_web_source_page_request("https://nyaa.si/?f=0&c=1_2&u=subsplease p=2")
    assert resolve_supported_web_source_page_request("https://nyaa.si/?q=frieren") == "https://nyaa.si/?q=frieren"
    assert resolve_supported_web_source_page_request("https://nyaa.si/?q=frieren&p=2") == "https://nyaa.si/?q=frieren&p=2"
    assert (
        resolve_supported_web_source_page_request("https://nyaa.si/?c=1_2&q=frieren&p=2")
        == "https://nyaa.si/?c=1_2&q=frieren&p=2"
    )
    assert looks_like_web_source_page_request("https://nyaa.si/?u=subsplease p=2")
    assert (
        resolve_supported_web_source_page_request("https://nyaa.si/?u=subsplease p=2")
        == "https://nyaa.si/?u=subsplease&p=2"
    )
    assert (
        resolve_supported_web_source_page_request("https://nyaa.si/?f=0&c=1_2&u=subsplease p=2")
        == "https://nyaa.si/?f=0&c=1_2&u=subsplease&p=2"
    )
    assert resolve_supported_web_source_page_request("https://nyaa.si/ p=2") == "https://nyaa.si/?p=2"
    assert (
        resolve_supported_web_source_page_request("https://nyaa.si/?s=seeders&o=desc p=2")
        == "https://nyaa.si/?s=seeders&o=desc&p=2"
    )
    assert (
        resolve_supported_web_source_page_request("https://nyaa.si/?c=1_2&s=seeders&o=desc p=2")
        == "https://nyaa.si/?c=1_2&s=seeders&o=desc&p=2"
    )
    assert (
        resolve_supported_web_source_page_request("https://nyaa.si/?f=0&c=1_2&u=subsplease&s=seeders&o=desc p=2")
        == "https://nyaa.si/?f=0&c=1_2&u=subsplease&s=seeders&o=desc&p=2"
    )
    assert (
        resolve_supported_web_source_page_request("https://nyaa.si/?f=0&c=1_2&q=frieren&s=seeders&o=desc p=2")
        == "https://nyaa.si/?f=0&c=1_2&q=frieren&s=seeders&o=desc&p=2"
    )
    assert resolve_supported_web_source_page_request("https://nyaa.si/?c=1_2&s=seeders p=2") is None
    assert resolve_supported_web_source_page_request("https://nyaa.si/?f=0&c=1_2&u=subsplease&s=seeders p=2") is None
    assert resolve_supported_web_source_page_request("https://nyaa.si/?f=0&c=1_2&q=frieren&s=seeders p=2") is None
    assert resolve_supported_web_source_page_request("https://example.com/list/42 p=2") is None


def test_is_supported_web_source_page_url_accepts_uncategorized_user_sort_page_number() -> None:
    assert is_supported_web_source_page_url("https://nyaa.si/?u=subsplease&s=seeders&o=desc&p=2")


def test_resolve_supported_web_source_page_request_appends_uncategorized_user_sort_page_number() -> None:
    assert (
        resolve_supported_web_source_page_request("https://nyaa.si/?u=subsplease&s=seeders&o=desc p=2")
        == "https://nyaa.si/?u=subsplease&s=seeders&o=desc&p=2"
    )


def test_web_source_client_search_page_rejects_unsupported_url() -> None:
    client = WebSourceClient(rule=NYAA_RULE)

    try:
        asyncio.run(client.search_page("https://example.com/?q=frieren"))
    except UnsupportedWebSourcePageError as error:
        assert str(error) == "https://example.com/?q=frieren"
    else:
        raise AssertionError("expected UnsupportedWebSourcePageError")


def test_bt_source_adapter_search_page_uses_page_provider() -> None:
    async def unexpected_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("search provider should not be used for page preview")

    async def page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?f=0&c=1_2&u=subsplease"
        return [
            {
                "title": "Frieren S01E01 1080p",
                "downloadUrl": "https://example.com/frieren-e01.torrent",
                "seeders": 10,
            }
        ]

    adapter = BtSourceAdapter(
        (
            BtSourceProvider(name="prowlarr", search_func=unexpected_search),
            BtSourceProvider(name="websource", search_func=unexpected_search, page_search_func=page_search),
        )
    )

    results = asyncio.run(adapter.search_page("https://nyaa.si/?f=0&c=1_2&u=subsplease"))

    assert len(results) == 1
    assert results[0]["title"] == "Frieren S01E01 1080p"
    assert results[0]["indexerName"] == "websource"


def test_bt_source_adapter_search_page_uses_page_provider_for_uncategorized_user_page() -> None:
    async def unexpected_search(_: str) -> list[dict[str, object]]:
        raise AssertionError("search provider should not be used for page preview")

    async def page_search(page_url: str) -> list[dict[str, object]]:
        assert page_url == "https://nyaa.si/?u=subsplease"
        return [
            {
                "title": "Frieren S01E01 1080p",
                "downloadUrl": "https://example.com/frieren-e01.torrent",
                "seeders": 10,
            }
        ]

    adapter = BtSourceAdapter(
        (
            BtSourceProvider(name="prowlarr", search_func=unexpected_search),
            BtSourceProvider(name="websource", search_func=unexpected_search, page_search_func=page_search),
        )
    )

    results = asyncio.run(adapter.search_page("https://nyaa.si/?u=subsplease"))

    assert len(results) == 1
    assert results[0]["title"] == "Frieren S01E01 1080p"
    assert results[0]["indexerName"] == "websource"

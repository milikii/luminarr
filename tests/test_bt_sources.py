from __future__ import annotations

import asyncio
import httpx

from app.clients.web_source import (
    NYAA_RULE,
    UnsupportedWebSourcePageError,
    WebSourceClient,
    is_supported_web_source_page_url,
    parse_web_source_html,
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


def test_is_supported_web_source_page_url_accepts_nyaa_user_and_search_pages() -> None:
    assert is_supported_web_source_page_url("https://nyaa.si/?f=0&c=1_2&u=subsplease")
    assert is_supported_web_source_page_url("https://nyaa.si/?f=0&c=1_2&q=frieren&p=2")
    assert not is_supported_web_source_page_url("https://nyaa.si/view/123")
    assert not is_supported_web_source_page_url("https://example.com/?q=frieren")


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

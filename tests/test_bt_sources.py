from __future__ import annotations

import asyncio

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
    assert build_bt_candidate_dedupe_key(first) == "info_hash:abcdef1234567890abcdef1234567890abcdef12"

    second = results[1]
    assert second["title"] == "Frieren S01E02 720p"
    assert second["source"] == "https://example.com/frieren-e02.torrent"
    assert second["downloadUrl"] == "https://example.com/frieren-e02.torrent"
    assert second["indexerName"] == "websource"


def test_bt_source_adapter_skips_candidates_without_title_or_source() -> None:
    async def broken_search(_: str) -> list[dict[str, object]]:
        return [
            {"title": "", "downloadUrl": "https://example.com/invalid.torrent"},
            {"title": "missing source"},
        ]

    adapter = BtSourceAdapter((BtSourceProvider(name="broken", search_func=broken_search),))

    results = asyncio.run(adapter.search("frieren"))

    assert results == []

from __future__ import annotations

from app.services.search_media import SearchMediaService


async def _fake_ambiguous_search(query: str) -> list[dict[str, object]]:
    assert query == "Dune"
    return [
        {"title": "Dune 1984 1080p BluRay", "year": 1984, "downloadUrl": "https://example.com/dune-1984.torrent"},
        {"title": "Dune 2021 2160p WEB-DL", "year": 2021, "downloadUrl": "https://example.com/dune-2021.torrent"},
        {
            "title": "Dune Part Two 2024 2160p WEB-DL",
            "year": 2024,
            "downloadUrl": "https://example.com/dune-part-two.torrent",
        },
    ]


def test_title_only_ambiguous_search_returns_candidates_instead_of_year_prompt() -> None:
    service = SearchMediaService(_fake_ambiguous_search)

    text = _run(service.search_and_format("Dune", chat_id=1001))

    assert "片名可能有多个版本" not in text
    assert "请补充更具体信息" not in text
    assert "搜索结果：Dune" in text
    assert "Dune 1984 1080p BluRay (1984)" in text
    assert "Dune 2021 2160p WEB-DL (2021)" in text
    assert service.get_cached_candidate(1001, 1) is not None
    assert not service.is_clarification_pending(1001)


def test_year_qualified_ambiguous_search_keeps_candidate_selection_path() -> None:
    async def fake_search(query: str) -> list[dict[str, object]]:
        assert query == "Dune 2021"
        return [
            {"title": "Dune 1984 1080p BluRay", "year": 1984, "downloadUrl": "https://example.com/dune-1984.torrent"},
            {"title": "Dune 2021 2160p WEB-DL", "year": 2021, "downloadUrl": "https://example.com/dune-2021.torrent"},
        ]

    service = SearchMediaService(fake_search)

    text = _run(service.search_and_format("Dune 2021", chat_id=1001))

    assert "片名可能有多个版本" not in text
    assert "搜索结果：Dune 2021" in text
    assert "Dune 2021 2160p WEB-DL (2021)" in text
    assert service.get_cached_candidate(1001, 1) is not None


def test_ambiguous_search_dedupes_duplicate_title_year_candidates() -> None:
    async def fake_search(query: str) -> list[dict[str, object]]:
        assert query == "Infernal Affairs"
        return [
            {
                "title": "Infernal Affairs 2002 1080p BluRay",
                "year": 2002,
                "downloadUrl": "https://example.com/infernal-affairs-a.torrent",
            },
            {
                "title": "Infernal Affairs 2002 1080p BluRay",
                "year": 2002,
                "downloadUrl": "https://example.com/infernal-affairs-b.torrent",
            },
            {
                "title": "Infernal Affairs II 2003 1080p BluRay",
                "year": 2003,
                "downloadUrl": "https://example.com/infernal-affairs-ii.torrent",
            },
            {
                "title": "Infernal Affairs III 2003 1080p BluRay",
                "year": 2003,
                "downloadUrl": "https://example.com/infernal-affairs-iii.torrent",
            },
        ]

    service = SearchMediaService(fake_search)

    text = _run(service.search_and_format("Infernal Affairs", chat_id=1001))

    assert "片名可能有多个版本" not in text
    assert text.count("Infernal Affairs 2002 1080p BluRay (2002)") == 1
    assert "Infernal Affairs II 2003 1080p BluRay (2003)" in text


def _run(coroutine):
    import asyncio

    return asyncio.run(coroutine)

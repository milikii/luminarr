from __future__ import annotations

from types import SimpleNamespace

from app.services.search_media import (
    _build_media_bt_candidate,
    _dedupe_media_bt_results_by_title,
    _derive_media_title_fallback_queries,
    order_media_bt_results,
)


def test_dedupes_media_bt_results_by_title_with_same_resolution() -> None:
    results = _dedupe_media_bt_results_by_title(
        [
            {"title": "Dune 2021 1080p"},
            {"title": "Dune 2021 1080p"},
            {"title": "Dune 2021 720p"},
        ]
    )

    assert results == [{"title": "Dune 2021 1080p"}, {"title": "Dune 2021 720p"}]


def test_derive_media_title_fallback_queries_uses_common_tokens_and_year() -> None:
    queries = _derive_media_title_fallback_queries(
        [
            {"title": "Dune Part Two 2160p"},
            {"title": "Dune Part Two WEBRip"},
            {"title": "Dune Part Two 2024"},
        ],
        query="Dune 2024",
    )

    assert queries == ("dune part two 2024",)


def test_build_media_bt_candidate_requires_source_and_title() -> None:
    assert _build_media_bt_candidate({"title": "Dune"}) is None
    assert _build_media_bt_candidate({"downloadUrl": "https://example.com/dune.torrent"}) is None


def test_order_media_bt_results_uses_scored_candidate_order_and_remainder(monkeypatch) -> None:
    from app.services import search_media as module

    calls: list[str] = []
    candidate_one = SimpleNamespace(name="one")
    candidate_two = SimpleNamespace(name="two")

    def fake_build(item):
        if item["title"] == "A":
            return candidate_one
        if item["title"] == "B":
            return candidate_two
        return None

    def fake_filter(candidates, context, rules):  # noqa: ANN001
        calls.append(context.query)
        return [
            SimpleNamespace(candidate=candidate_two, drop_reason=None, score=2.0),
            SimpleNamespace(candidate=candidate_one, drop_reason=None, score=1.0),
        ]

    monkeypatch.setattr(module, "_build_media_bt_candidate", fake_build)
    monkeypatch.setattr(module, "filter_candidates", fake_filter)
    monkeypatch.setattr(module, "load_bt_scoring_rules", lambda: {})

    ordered = order_media_bt_results(
        [
            {"title": "A"},
            {"title": "B"},
            {"title": "Remainder"},
        ],
        query="query",
    )

    assert calls == ["query"]
    assert [item["title"] for item in ordered] == ["B", "A", "Remainder"]

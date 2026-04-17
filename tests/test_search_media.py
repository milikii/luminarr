from __future__ import annotations

from collections.abc import Awaitable
from pathlib import Path

import pytest

from app.clients.tmdb import TmdbMovie
from app.db.candidate_repo import CandidateMappingRepo
from app.db.clarification_repo import ClarificationRepo
from app.db.sqlite import SqliteDatabase
from app.services.search_media import (
    BT_READ_ONLY_EMPTY_QUERY_TEXT,
    BT_READ_ONLY_NOTICE_TEXT,
    BT_READ_ONLY_NO_RESULT_TEXT_TEMPLATE,
    CANDIDATE_STATE_UNAVAILABLE_TEXT,
    CLARIFICATION_CLEAR_STATE_UNAVAILABLE_TEXT,
    CLARIFICATION_PENDING_STATE_UNAVAILABLE_TEXT,
    EMPTY_QUERY_TEXT,
    NO_RESULT_TEXT_TEMPLATE,
    SearchMediaService,
    parse_movie_query,
)


async def _fake_search_with_results(query: str) -> list[dict[str, object]]:
    assert query == "dune"
    return [
        {
            "title": "Dune: Part Two",
            "year": 2024,
            "quality": "2160p",
            "size": 8 * 1024 * 1024 * 1024,
            "indexer": {"name": "IndexerA"},
        },
        {
            "title": "Dune (2021)",
            "year": 2021,
            "resolution": "1080p",
            "size": 2 * 1024 * 1024 * 1024,
            "indexerName": "IndexerB",
        },
    ]


async def _fake_search_empty(query: str) -> list[dict[str, object]]:
    assert query == "unknown"
    return []


async def _fake_raw_search(query: str) -> list[dict[str, object]]:
    assert query == "dune bt"
    return [
        {
            "title": "Dune 2021 1080p",
            "source": "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12",
            "seeders": 8,
        }
    ]


async def _fake_search_ambiguous(query: str) -> list[dict[str, object]]:
    assert query == "Dune"
    return [
        {"title": "Dune (1984) 1080p BluRay", "year": 1984, "size": 2 * 1024 * 1024 * 1024},
        {"title": "Dune (2000) 1080p WEB-DL", "year": 2000, "size": 3 * 1024 * 1024 * 1024},
        {"title": "Dune (2021) 2160p WEB-DL", "year": 2021, "size": 9 * 1024 * 1024 * 1024},
    ]


def test_search_and_format_with_results() -> None:
    service = SearchMediaService(_fake_search_with_results)
    text = _run(service.search_and_format("dune"))
    assert "电影海报卡片" in text
    assert "片名: dune" in text
    assert "年份: -" in text
    assert "别名: -" in text
    assert "海报: 暂未接入图片" in text
    assert "搜索结果：dune" in text
    assert "1. Dune: Part Two (2024)" in text
    assert "画质: 2160p | 大小: 8.0 GB | 站点: IndexerA" in text
    assert "2. Dune (2021) (2021)" in text
    assert "画质: 1080p | 大小: 2.0 GB | 站点: IndexerB" in text
    assert text.index("电影海报卡片") < text.index("搜索结果：dune")


def test_search_and_format_empty_query() -> None:
    service = SearchMediaService(_fake_search_with_results)
    text = _run(service.search_and_format("   "))
    assert text == EMPTY_QUERY_TEXT


def test_search_and_format_no_result() -> None:
    service = SearchMediaService(_fake_search_empty)
    text = _run(service.search_and_format("unknown"))
    assert text == NO_RESULT_TEXT_TEMPLATE.format(query="unknown")


def test_search_raw_candidates_uses_dedicated_raw_search_func() -> None:
    service = SearchMediaService(_fake_search_with_results, raw_search_func=_fake_raw_search)
    results = _run(service.search_raw_candidates("dune bt"))

    assert len(results) == 1
    assert results[0]["title"] == "Dune 2021 1080p"
    assert results[0]["source"].startswith("magnet:?xt=urn:btih:")


def test_search_bt_read_only_and_format_uses_raw_search_func() -> None:
    async def fake_raw_search(query: str) -> list[dict[str, object]]:
        assert query == "dune bt"
        return [
            {
                "title": "Dune 2021 1080p",
                "source": "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12",
                "infoHash": "abcdef1234567890abcdef1234567890abcdef12",
                "seeders": 8,
                "size": 2 * 1024 * 1024 * 1024,
                "indexerName": "Nyaa",
                "sourceProvider": "nyaa",
            }
        ]

    service = SearchMediaService(_fake_search_with_results, raw_search_func=fake_raw_search)
    text = _run(service.search_bt_read_only_and_format("dune bt"))

    assert "BT 只读探索结果：dune bt" in text
    assert "1. Dune 2021 1080p" in text
    assert "站点: Nyaa | 来源入口: nyaa | 做种: 8 | 大小: 2.0 GB" in text
    assert "链接参考: magnet | infoHash=abcdef1234567890abcdef1234567890abcdef12" in text
    assert BT_READ_ONLY_NOTICE_TEXT in text


def test_search_bt_read_only_and_format_empty_query() -> None:
    service = SearchMediaService(_fake_search_with_results, raw_search_func=_fake_raw_search)
    text = _run(service.search_bt_read_only_and_format("   "))

    assert text == BT_READ_ONLY_EMPTY_QUERY_TEXT


def test_search_bt_read_only_and_format_no_result() -> None:
    service = SearchMediaService(_fake_search_with_results, raw_search_func=_fake_search_empty)
    text = _run(service.search_bt_read_only_and_format("unknown"))

    assert text == BT_READ_ONLY_NO_RESULT_TEXT_TEMPLATE.format(query="unknown")


def test_search_bt_read_only_and_format_logs_raw_search_failure(capsys) -> None:
    async def fake_raw_search(_: str) -> list[dict[str, object]]:
        raise RuntimeError("bt source unavailable")

    service = SearchMediaService(_fake_search_with_results, raw_search_func=fake_raw_search)

    with pytest.raises(RuntimeError, match="bt source unavailable"):
        _run(service.search_bt_read_only_and_format("dune bt"))

    output = capsys.readouterr().out
    assert "[BT 只读搜索失败]" in output
    assert "query=dune bt" in output


def test_search_and_format_returns_clarification_for_ambiguous_query() -> None:
    service = SearchMediaService(_fake_search_ambiguous)
    text = _run(service.search_and_format("Dune", chat_id=1001))
    assert "片名可能有多个版本：Dune" in text
    assert "只读探索参考：" in text
    assert "- Dune (1984) 1080p BluRay (1984)" in text
    assert service.is_clarification_pending(1001)
    assert service.get_cached_candidate(1001, 1) is None


def test_clarification_pending_persists_for_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()

    before_restart_service = SearchMediaService(
        _fake_search_ambiguous,
        clarification_repo=ClarificationRepo(database),
    )
    _run(before_restart_service.search_and_format("Dune", chat_id=1001))

    after_restart_service = SearchMediaService(
        _fake_search_with_results,
        clarification_repo=ClarificationRepo(SqliteDatabase(str(db_path))),
    )
    assert after_restart_service.is_clarification_pending(1001)
    assert after_restart_service.clear_clarification_pending(1001)
    assert not after_restart_service.is_clarification_pending(1001)


def test_search_success_clears_persisted_clarification_pending(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()
    repo = ClarificationRepo(database)

    pending_service = SearchMediaService(_fake_search_empty, clarification_repo=repo)
    _run(pending_service.search_and_format("unknown", chat_id=1001))

    clear_service = SearchMediaService(
        _fake_search_with_results,
        clarification_repo=ClarificationRepo(SqliteDatabase(str(db_path))),
    )
    _run(clear_service.search_and_format("dune", chat_id=1001))

    verify_service = SearchMediaService(
        _fake_search_with_results,
        clarification_repo=ClarificationRepo(SqliteDatabase(str(db_path))),
    )
    assert not verify_service.is_clarification_pending(1001)


def test_search_success_returns_state_unavailable_when_clarification_clear_fails(tmp_path: Path, capsys) -> None:
    class ClearFailsClarificationRepo(ClarificationRepo):
        def clear_pending(self, *, chat_id: int) -> bool:
            raise RuntimeError(f"db down for {chat_id}")

    db_path = tmp_path / "state.sqlite3"
    database = SqliteDatabase(str(db_path))
    database.initialize()
    ClarificationRepo(database).upsert_pending(chat_id=1001, query="unknown")

    service = SearchMediaService(
        _fake_search_with_results,
        clarification_repo=ClearFailsClarificationRepo(SqliteDatabase(str(db_path))),
    )

    text = _run(service.search_and_format("dune", chat_id=1001))

    assert text == CLARIFICATION_CLEAR_STATE_UNAVAILABLE_TEXT
    assert service.get_cached_candidate(1001, 1) is None
    assert service.is_clarification_pending(1001)
    output = capsys.readouterr().out
    assert "[搜索澄清态清理失败]" in output
    assert "db down for 1001" in output


def test_search_clarification_pending_logs_persistence_failure(tmp_path: Path, capsys) -> None:
    class MissingRowClarificationRepo(ClarificationRepo):
        def get_pending_query(self, *, chat_id: int) -> str | None:
            _ = chat_id
            return None

    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    service = SearchMediaService(
        _fake_search_ambiguous,
        clarification_repo=MissingRowClarificationRepo(database),
    )

    text = _run(service.search_and_format("Dune", chat_id=1001))

    assert text == CLARIFICATION_PENDING_STATE_UNAVAILABLE_TEXT
    assert not service.is_clarification_pending(1001)
    output = capsys.readouterr().out
    assert "[搜索澄清态写入后记录缺失]" in output
    assert "[处理建议]" in output
    assert "clarification_state missing after upsert" in output


def test_search_no_result_returns_state_unavailable_when_clarification_persist_fails(tmp_path: Path, capsys) -> None:
    class MissingRowClarificationRepo(ClarificationRepo):
        def get_pending_query(self, *, chat_id: int) -> str | None:
            _ = chat_id
            return None

    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    service = SearchMediaService(
        _fake_search_empty,
        clarification_repo=MissingRowClarificationRepo(database),
    )

    text = _run(service.search_and_format("unknown", chat_id=1001))

    assert text == CLARIFICATION_PENDING_STATE_UNAVAILABLE_TEXT
    assert service.get_cached_candidate(1001, 1) is None
    assert not service.is_clarification_pending(1001)
    output = capsys.readouterr().out
    assert "[搜索澄清态写入后记录缺失]" in output
    assert "[处理建议]" in output
    assert "clarification_state missing after upsert" in output


def test_search_candidate_persist_logs_persistence_failure(tmp_path: Path, capsys) -> None:
    class MissingCandidateRowRepo(CandidateMappingRepo):
        def _count_candidates(self, *, chat_id: int) -> int:
            _ = chat_id
            return 0

    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    service = SearchMediaService(
        _fake_search_with_results,
        candidate_repo=MissingCandidateRowRepo(database),
    )

    text = _run(service.search_and_format("dune", chat_id=1001))

    assert text == CANDIDATE_STATE_UNAVAILABLE_TEXT
    assert service.get_cached_candidate(1001, 1) is None
    output = capsys.readouterr().out
    assert "[搜索候选写入后记录不一致]" in output
    assert "[处理建议]" in output
    assert "candidate_mapping count mismatch after save" in output


def test_search_no_result_returns_state_unavailable_when_candidate_persist_fails(tmp_path: Path, capsys) -> None:
    class MissingCandidateRowRepo(CandidateMappingRepo):
        def _count_candidates(self, *, chat_id: int) -> int:
            _ = chat_id
            return 1

    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    service = SearchMediaService(
        _fake_search_empty,
        candidate_repo=MissingCandidateRowRepo(database),
    )

    text = _run(service.search_and_format("unknown", chat_id=1001))

    assert text == CANDIDATE_STATE_UNAVAILABLE_TEXT
    assert service.get_cached_candidate(1001, 1) is None
    output = capsys.readouterr().out
    assert "[搜索候选写入后记录不一致]" in output
    assert "[处理建议]" in output
    assert "candidate_mapping count mismatch after save" in output


def test_clear_clarification_pending_logs_persistence_failure(capsys) -> None:
    repo = type("BoomRepo", (), {"clear_pending": lambda self, chat_id: (_ for _ in ()).throw(RuntimeError("db down"))})()
    service = SearchMediaService(_fake_search_with_results, clarification_repo=repo)
    service._clarification_pending_by_chat[1001] = "Dune"
    assert service.clear_clarification_pending(1001) is False
    assert service._clarification_pending_by_chat[1001] == "Dune"
    assert "[搜索澄清态清理失败]" in capsys.readouterr().out


def test_clear_clarification_pending_logs_missing_clear_result(capsys) -> None:
    repo = type("MissingRepo", (), {"clear_pending": lambda self, chat_id: None})()
    service = SearchMediaService(_fake_search_with_results, clarification_repo=repo)
    service._clarification_pending_by_chat[1001] = "Dune"

    assert service.clear_clarification_pending(1001) is False
    assert service._clarification_pending_by_chat[1001] == "Dune"
    output = capsys.readouterr().out
    assert "[搜索澄清态清理结果缺失]" in output
    assert "clarification clear result missing" in output
    assert "[处理建议]" in output


def test_is_clarification_pending_logs_persistence_failure(capsys) -> None:
    repo = type("BoomRepo", (), {"get_pending_query": lambda self, chat_id: (_ for _ in ()).throw(RuntimeError("db down"))})()
    service = SearchMediaService(_fake_search_with_results, clarification_repo=repo)
    assert service.is_clarification_pending(1001) is None
    output = capsys.readouterr().out
    assert "[搜索澄清态读取失败]" in output
    assert "当前相关入口会按状态不可用处理" in output


def test_load_persisted_clarification_query_distinguishes_repo_failure_from_missing_state() -> None:
    missing_repo = type("MissingRepo", (), {"get_pending_query": lambda self, chat_id: None})()
    failed_repo = type("BoomRepo", (), {"get_pending_query": lambda self, chat_id: (_ for _ in ()).throw(RuntimeError("db down"))})()

    missing_service = SearchMediaService(_fake_search_with_results, clarification_repo=missing_repo)
    failed_service = SearchMediaService(_fake_search_with_results, clarification_repo=failed_repo)

    missing_result = missing_service._load_persisted_clarification_query(chat_id=1001)
    failed_result = failed_service._load_persisted_clarification_query(chat_id=1001)

    assert missing_result.query is None
    assert missing_result.load_failed is False
    assert failed_result.query is None
    assert failed_result.load_failed is True


def test_clear_cached_candidates_logs_candidate_persistence_failure(capsys) -> None:
    repo = type("BoomRepo", (), {"clear_candidates": lambda self, chat_id: (_ for _ in ()).throw(RuntimeError("db down"))})()
    service = SearchMediaService(_fake_search_with_results, candidate_repo=repo)
    service._recent_candidates_by_chat[1001] = [{"title": "Dune"}]

    assert service.clear_cached_candidates(1001) is False
    assert service._recent_candidates_by_chat[1001] == [{"title": "Dune"}]
    assert "[搜索候选清理失败]" in capsys.readouterr().out


def test_clear_cached_candidates_logs_missing_candidate_clear_result(capsys) -> None:
    repo = type("MissingRepo", (), {"clear_candidates": lambda self, chat_id: None})()
    service = SearchMediaService(_fake_search_with_results, candidate_repo=repo)
    service._recent_candidates_by_chat[1001] = [{"title": "Dune"}]

    assert service.clear_cached_candidates(1001) is False
    assert service._recent_candidates_by_chat[1001] == [{"title": "Dune"}]
    output = capsys.readouterr().out
    assert "[搜索候选清理结果缺失]" in output
    assert "candidate clear result missing" in output
    assert "[处理建议]" in output


def test_get_cached_candidate_logs_candidate_payload_corruption(tmp_path: Path, capsys) -> None:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO candidate_mapping (
                chat_id,
                selection_index,
                candidate_json,
                updated_at
            ) VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (1001, 1, "{"),
        )
        connection.commit()

    service = SearchMediaService(
        _fake_search_with_results,
        candidate_repo=CandidateMappingRepo(database),
    )

    assert service.get_cached_candidate(1001, 1) is None
    output = capsys.readouterr().out
    assert "[搜索候选载荷损坏]" in output
    assert "当前相关入口会按候选读取失败或状态不可用处理" in output


def test_has_cached_candidates_distinguishes_lookup_failure(capsys) -> None:
    repo = type("BoomRepo", (), {"get_candidate": lambda self, chat_id, index: (_ for _ in ()).throw(RuntimeError("db down"))})()
    service = SearchMediaService(_fake_search_with_results, candidate_repo=repo)

    assert service.has_cached_candidates(1001) is None

    output = capsys.readouterr().out
    assert "[搜索候选读取失败]" in output
    assert "chat_id=1001" in output
    assert "index=1" in output
    assert "[处理建议]" in output
    assert "当前相关入口会按候选读取失败或状态不可用处理" in output


async def _fake_search_quality_from_title(query: str) -> list[dict[str, object]]:
    assert query == "dune"
    return [
        {
            "title": "Dune 1984 1080p AMZN WEB-DL DDP 5.1 H.264-vase",
            "size": 10 * 1024 * 1024 * 1024,
            "indexerName": "BeyondHD",
        }
    ]


def test_search_and_format_guesses_quality_from_title() -> None:
    service = SearchMediaService(_fake_search_quality_from_title)
    text = _run(service.search_and_format("dune"))
    assert "画质: 1080p WEB-DL" in text


async def _fake_search_tmdb_hit(query: str) -> list[dict[str, object]]:
    assert query == "Interstellar 2014"
    return [
        {
            "title": "Interstellar 2014 1080p BluRay",
            "year": 2014,
            "size": 2 * 1024 * 1024 * 1024,
            "indexerName": "IndexerA",
        }
    ]


async def _fake_lookup_tmdb_movie(title: str, year: str) -> TmdbMovie | None:
    assert title == "星际穿越"
    assert year == "2014"
    return TmdbMovie(title="Interstellar", original_title="Interstellar", year="2014")


def test_search_and_format_uses_tmdb_first_when_available() -> None:
    service = SearchMediaService(
        _fake_search_tmdb_hit,
        lookup_movie_func=_fake_lookup_tmdb_movie,
    )
    text = _run(service.search_and_format("星际穿越 (2014)"))
    assert "电影海报卡片" in text
    assert "片名: Interstellar" in text
    assert "年份: 2014" in text
    assert "别名: -" in text
    assert "搜索结果：星际穿越 (2014)" in text
    assert "Interstellar 2014 1080p BluRay" in text


def test_search_and_format_tmdb_english_hit_stops_before_original() -> None:
    seen_queries: list[str] = []

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        if query == "Interstellar 2014":
            return [
                {
                    "title": "Interstellar 2014 1080p BluRay",
                    "year": 2014,
                    "size": 2 * 1024 * 1024 * 1024,
                    "indexerName": "IndexerA",
                }
            ]
        return []

    async def fake_tmdb_lookup(_: str, __: str) -> TmdbMovie | None:
        return TmdbMovie(title="Interstellar", original_title="星际穿越", year="2014")

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("星际穿越 (2014)"))

    assert seen_queries == ["Interstellar 2014"]
    assert "电影海报卡片" in text
    assert "片名: 星际穿越" in text
    assert "年份: 2014" in text
    assert "别名: Interstellar" in text
    assert "Interstellar 2014 1080p BluRay" in text


def test_search_and_format_fallbacks_to_tmdb_original_when_english_miss() -> None:
    seen_queries: list[str] = []

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        if query == "Interstellar 2014":
            return []
        if query == "星际穿越 2014":
            return [
                {
                    "title": "星际穿越 2014 1080p BluRay",
                    "year": 2014,
                    "size": 2 * 1024 * 1024 * 1024,
                    "indexerName": "IndexerB",
                }
            ]
        return []

    async def fake_tmdb_lookup(_: str, __: str) -> TmdbMovie | None:
        return TmdbMovie(title="Interstellar", original_title="星际穿越", year="2014")

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("星际穿越 (2014)"))

    assert seen_queries == ["Interstellar 2014", "星际穿越 2014"]
    assert "星际穿越 2014 1080p BluRay" in text


def test_search_and_format_deduplicates_same_tmdb_titles() -> None:
    seen_queries: list[str] = []

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_queries.append(query)
        return []

    async def fake_tmdb_lookup(_: str, __: str) -> TmdbMovie | None:
        return TmdbMovie(title="Interstellar", original_title="Interstellar", year="2014")

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("星际穿越 (2014)"))

    assert seen_queries == ["Interstellar 2014"]
    assert text == NO_RESULT_TEXT_TEMPLATE.format(query="星际穿越 (2014)")


def test_search_and_format_fallbacks_to_normalized_query_when_tmdb_empty() -> None:
    seen_query: dict[str, str] = {}

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_query["value"] = query
        return []

    async def fake_tmdb_lookup(title: str, year: str) -> TmdbMovie | None:
        assert title == "Dune"
        assert year == "2021"
        return None

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("Dune (2021)"))
    assert seen_query["value"] == "Dune 2021"
    assert text == NO_RESULT_TEXT_TEMPLATE.format(query="Dune (2021)")


def test_search_and_format_fallbacks_to_normalized_query_when_tmdb_failed() -> None:
    seen_query: dict[str, str] = {}

    async def fake_search(query: str) -> list[dict[str, object]]:
        seen_query["value"] = query
        return []

    async def fake_tmdb_lookup(_: str, __: str) -> TmdbMovie | None:
        raise RuntimeError("tmdb unavailable")

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)
    text = _run(service.search_and_format("Dune 2021"))
    assert seen_query["value"] == "Dune 2021"
    assert text == NO_RESULT_TEXT_TEMPLATE.format(query="Dune 2021")


def test_search_and_format_logs_tmdb_failure(capsys) -> None:
    async def fake_search(query: str) -> list[dict[str, object]]:
        assert query == "Dune 2021"
        return []

    async def fake_tmdb_lookup(_: str, __: str) -> TmdbMovie | None:
        raise RuntimeError("tmdb unavailable")

    service = SearchMediaService(fake_search, lookup_movie_func=fake_tmdb_lookup)

    text = _run(service.search_and_format("Dune 2021"))

    assert text == NO_RESULT_TEXT_TEMPLATE.format(query="Dune 2021")
    output = capsys.readouterr().out
    assert "[TMDB 查询失败]" in output
    assert "query=Dune 2021" in output


def test_search_and_format_logs_search_backend_failure(capsys) -> None:
    async def fake_search(_: str) -> list[dict[str, object]]:
        raise RuntimeError("indexer unavailable")

    service = SearchMediaService(fake_search)

    with pytest.raises(RuntimeError, match="indexer unavailable"):
        _run(service.search_and_format("Dune 2021"))

    output = capsys.readouterr().out
    assert "[搜索源查询失败]" in output
    assert "query=Dune 2021" in output


def test_parse_movie_query_parentheses_year() -> None:
    parsed = parse_movie_query("Dune (2021)")
    assert parsed.title == "Dune"
    assert parsed.year == "2021"


def test_parse_movie_query_suffix_year() -> None:
    parsed = parse_movie_query("Dune 2021")
    assert parsed.title == "Dune"
    assert parsed.year == "2021"


def test_parse_movie_query_keeps_title_when_no_year() -> None:
    parsed = parse_movie_query("  Dune   Part   Two  ")
    assert parsed.title == "Dune Part Two"
    assert parsed.year == ""


def _run(coroutine: Awaitable[str]) -> str:
    import asyncio

    return asyncio.run(coroutine)

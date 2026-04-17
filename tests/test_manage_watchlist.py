from __future__ import annotations

import sqlite3
from pathlib import Path

from app.db.sqlite import SqliteDatabase
from app.db.watchlist_repo import WatchlistRepo
from app.services.manage_watchlist import (
    WATCHLIST_ADD_FAILED_TEXT,
    WATCHLIST_ADD_USAGE_TEXT,
    WATCHLIST_EMPTY_TEXT,
    WATCHLIST_LIST_FAILED_TEXT,
    WATCHLIST_CLEAR_FAILED_TEXT,
    WATCHLIST_REMOVE_FAILED_TEXT,
    WATCHLIST_REMOVE_USAGE_TEXT,
    ManageWatchlistService,
    parse_watchlist_query,
)


def test_parse_watchlist_query_supports_list_add_remove_clear() -> None:
    list_command = parse_watchlist_query("watchlist")
    assert list_command is not None
    assert list_command.action == "list"

    add_command = parse_watchlist_query("watchlist add dune 2021")
    assert add_command is not None
    assert add_command.action == "add"
    assert add_command.arg == "dune 2021"

    remove_command = parse_watchlist_query("watchlist remove 7")
    assert remove_command is not None
    assert remove_command.action == "remove"
    assert remove_command.arg == "7"

    clear_command = parse_watchlist_query("想看 清空")
    assert clear_command is not None
    assert clear_command.action == "clear"

    series_command = parse_watchlist_query("watchlist add series 三体 2023")
    assert series_command is not None
    assert series_command.action == "add"
    assert series_command.arg == "series 三体 2023"


def test_parse_watchlist_query_non_watchlist_text_returns_none() -> None:
    assert parse_watchlist_query("dune 2021") is None
    assert parse_watchlist_query("") is None


def test_manage_watchlist_add_list_remove_clear(tmp_path: Path) -> None:
    service = ManageWatchlistService(WatchlistRepo(_make_database(tmp_path)))

    assert service.handle(parse_watchlist_query("watchlist list"), chat_id=1001) == WATCHLIST_EMPTY_TEXT

    added_text = service.handle(parse_watchlist_query("watchlist add dune 2021"), chat_id=1001)
    assert "已加入想看：dune (2021)" in added_text
    assert "类型: 电影" in added_text
    assert "条目ID:" in added_text
    movie_item_id = int(added_text.rsplit(":", maxsplit=1)[1].strip())

    duplicate_text = service.handle(parse_watchlist_query("想看 add dune 2021"), chat_id=1001)
    assert "想看已存在：dune (2021)" in duplicate_text
    assert "类型: 电影" in duplicate_text
    assert str(movie_item_id) in duplicate_text

    series_text = service.handle(parse_watchlist_query("watchlist add series 三体 2023"), chat_id=1001)
    assert "已加入想看：三体 (2023)" in series_text
    assert "类型: 剧集" in series_text
    assert "条目ID:" in series_text
    series_item_id = int(series_text.rsplit(":", maxsplit=1)[1].strip())

    anime_text = service.handle(parse_watchlist_query("想看 add anime 葬送的芙莉莲 2023"), chat_id=1001)
    assert "已加入想看：葬送的芙莉莲 (2023)" in anime_text
    assert "类型: 动漫" in anime_text
    assert "条目ID:" in anime_text
    anime_item_id = int(anime_text.rsplit(":", maxsplit=1)[1].strip())

    list_text = service.handle(parse_watchlist_query("watchlist list"), chat_id=1001)
    assert f"[{movie_item_id}] dune (2021) | 类型: 电影" in list_text
    assert f"[{series_item_id}] 三体 (2023) | 类型: 剧集" in list_text
    assert f"[{anime_item_id}] 葬送的芙莉莲 (2023) | 类型: 动漫" in list_text

    removed_text = service.handle(parse_watchlist_query(f"watchlist remove {series_item_id}"), chat_id=1001)
    assert removed_text == f"已删除想看条目：{series_item_id}"

    assert service.handle(parse_watchlist_query("watchlist clear"), chat_id=1001) == "已清空想看清单，共删除 2 条。"


def test_manage_watchlist_validation_errors(tmp_path: Path) -> None:
    service = ManageWatchlistService(WatchlistRepo(_make_database(tmp_path)))

    assert service.handle(parse_watchlist_query("watchlist add"), chat_id=1001) == WATCHLIST_ADD_USAGE_TEXT
    assert service.handle(parse_watchlist_query("watchlist add series"), chat_id=1001) == WATCHLIST_ADD_USAGE_TEXT
    assert service.handle(parse_watchlist_query("watchlist remove"), chat_id=1001) == WATCHLIST_REMOVE_USAGE_TEXT
    assert service.handle(parse_watchlist_query("watchlist remove x"), chat_id=1001) == WATCHLIST_REMOVE_USAGE_TEXT


def test_manage_watchlist_list_returns_failure_text_when_repo_raises(tmp_path: Path, capsys) -> None:
    repo = WatchlistRepo(_make_database(tmp_path))

    def _crash_list_items(**_: object) -> None:
        raise RuntimeError("db down")

    repo.list_items = _crash_list_items  # type: ignore[method-assign]
    service = ManageWatchlistService(repo)

    reply = service.handle(parse_watchlist_query("watchlist list"), chat_id=1001)

    assert reply == WATCHLIST_LIST_FAILED_TEXT
    captured = capsys.readouterr()
    assert "[想看清单读取失败]" in captured.out
    assert "db down" in captured.out


def test_manage_watchlist_list_returns_failure_text_when_repo_returns_none(tmp_path: Path, capsys) -> None:
    repo = WatchlistRepo(_make_database(tmp_path))

    def _missing_list_items(**_: object) -> None:
        return None

    repo.list_items = _missing_list_items  # type: ignore[method-assign]
    service = ManageWatchlistService(repo)

    reply = service.handle(parse_watchlist_query("watchlist list"), chat_id=1001)

    assert reply == WATCHLIST_LIST_FAILED_TEXT
    captured = capsys.readouterr()
    assert "[想看清单结果缺失]" in captured.out
    assert "[处理建议]" in captured.out
    assert "watchlist list result missing" in captured.out


def test_manage_watchlist_add_returns_failure_text_when_repo_returns_none(tmp_path: Path, capsys) -> None:
    repo = WatchlistRepo(_make_database(tmp_path))

    def _fail_add_item(**_: object) -> None:
        return None

    repo.add_item = _fail_add_item  # type: ignore[method-assign]
    service = ManageWatchlistService(repo)

    reply = service.handle(parse_watchlist_query("watchlist add dune 2021"), chat_id=1001)

    assert reply == WATCHLIST_ADD_FAILED_TEXT
    captured = capsys.readouterr()
    assert "[想看写入结果缺失]" in captured.out
    assert "[处理建议]" in captured.out
    assert "watchlist add result missing" in captured.out


def test_manage_watchlist_add_logs_missing_row_after_insert(tmp_path: Path, capsys) -> None:
    class MissingRowWatchlistRepo(WatchlistRepo):
        def get_item_by_id(self, *, chat_id: int, item_id: int):
            return None

    service = ManageWatchlistService(MissingRowWatchlistRepo(_make_database(tmp_path)))

    reply = service.handle(parse_watchlist_query("watchlist add dune 2021"), chat_id=1001)

    assert reply == WATCHLIST_ADD_FAILED_TEXT
    captured = capsys.readouterr()
    assert "[想看写入后条目缺失]" in captured.out
    assert "[处理建议]" in captured.out
    assert "watchlist_item missing after insert" in captured.out


def test_manage_watchlist_add_returns_failure_text_when_repo_raises(tmp_path: Path, capsys) -> None:
    repo = WatchlistRepo(_make_database(tmp_path))

    def _crash_add_item(**_: object) -> None:
        raise RuntimeError("db down")

    repo.add_item = _crash_add_item  # type: ignore[method-assign]
    service = ManageWatchlistService(repo)

    reply = service.handle(parse_watchlist_query("watchlist add dune 2021"), chat_id=1001)

    assert reply == WATCHLIST_ADD_FAILED_TEXT
    captured = capsys.readouterr()
    assert "[想看写入失败]" in captured.out
    assert "db down" in captured.out


def test_manage_watchlist_remove_returns_failure_text_when_repo_raises(tmp_path: Path, capsys) -> None:
    repo = WatchlistRepo(_make_database(tmp_path))

    def _crash_remove_item(**_: object) -> None:
        raise RuntimeError("db down")

    repo.remove_item = _crash_remove_item  # type: ignore[method-assign]
    service = ManageWatchlistService(repo)

    reply = service.handle(parse_watchlist_query("watchlist remove 7"), chat_id=1001)

    assert reply == WATCHLIST_REMOVE_FAILED_TEXT
    captured = capsys.readouterr()
    assert "[想看删除失败]" in captured.out
    assert "db down" in captured.out


def test_manage_watchlist_remove_returns_failure_text_when_repo_returns_none(tmp_path: Path, capsys) -> None:
    repo = WatchlistRepo(_make_database(tmp_path))

    def _missing_remove_item(**_: object) -> None:
        return None

    repo.remove_item = _missing_remove_item  # type: ignore[method-assign]
    service = ManageWatchlistService(repo)

    reply = service.handle(parse_watchlist_query("watchlist remove 7"), chat_id=1001)

    assert reply == WATCHLIST_REMOVE_FAILED_TEXT
    captured = capsys.readouterr()
    assert "[想看删除结果缺失]" in captured.out
    assert "[处理建议]" in captured.out
    assert "watchlist remove result missing" in captured.out


def test_manage_watchlist_clear_returns_failure_text_when_repo_raises(tmp_path: Path, capsys) -> None:
    repo = WatchlistRepo(_make_database(tmp_path))

    def _crash_clear_items(**_: object) -> None:
        raise RuntimeError("db down")

    repo.clear_items = _crash_clear_items  # type: ignore[method-assign]
    service = ManageWatchlistService(repo)

    reply = service.handle(parse_watchlist_query("watchlist clear"), chat_id=1001)

    assert reply == WATCHLIST_CLEAR_FAILED_TEXT
    captured = capsys.readouterr()
    assert "[想看清单清空失败]" in captured.out
    assert "db down" in captured.out


def test_manage_watchlist_clear_returns_failure_text_when_repo_returns_none(tmp_path: Path, capsys) -> None:
    repo = WatchlistRepo(_make_database(tmp_path))

    def _missing_clear_items(**_: object) -> None:
        return None

    repo.clear_items = _missing_clear_items  # type: ignore[method-assign]
    service = ManageWatchlistService(repo)

    reply = service.handle(parse_watchlist_query("watchlist clear"), chat_id=1001)

    assert reply == WATCHLIST_CLEAR_FAILED_TEXT
    captured = capsys.readouterr()
    assert "[想看清单清空结果缺失]" in captured.out
    assert "[处理建议]" in captured.out
    assert "watchlist clear result missing" in captured.out


def test_watchlist_repo_persists_for_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    before_restart_db = SqliteDatabase(str(db_path))
    before_restart_db.initialize()
    before_restart_repo = WatchlistRepo(before_restart_db)
    created = before_restart_repo.add_item(chat_id=1001, title="三体", year="2023", media_kind="series")
    assert created is not None

    after_restart_repo = WatchlistRepo(SqliteDatabase(str(db_path)))
    items = after_restart_repo.list_items(chat_id=1001)
    assert len(items) == 1
    assert items[0].title == "三体"
    assert items[0].year == "2023"
    assert items[0].media_kind == "series"


def test_watchlist_repo_allows_same_title_year_across_media_kinds(tmp_path: Path) -> None:
    repo = WatchlistRepo(_make_database(tmp_path))

    movie_created = repo.add_item(chat_id=1001, title="dune", year="2021", media_kind="movie")
    assert movie_created is not None
    assert movie_created[1] is True

    series_created = repo.add_item(chat_id=1001, title="dune", year="2021", media_kind="series")
    assert series_created is not None
    assert series_created[1] is True
    assert series_created[0].media_kind == "series"

    items = repo.list_items(chat_id=1001)
    assert len(items) == 2


def test_watchlist_repo_migrates_existing_rows_to_movie_kind(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE watchlist_item (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                year TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(chat_id, title, year)
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_watchlist_item_chat_id ON watchlist_item(chat_id)"
        )
        connection.execute(
            """
            INSERT INTO watchlist_item (
                chat_id,
                title,
                year,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (1001, "dune", "2021"),
        )
        connection.commit()

    database = SqliteDatabase(str(db_path))
    database.initialize()
    repo = WatchlistRepo(database)

    items = repo.list_items(chat_id=1001)
    assert len(items) == 1
    assert items[0].title == "dune"
    assert items[0].media_kind == "movie"

    created = repo.add_item(chat_id=1001, title="dune", year="2021", media_kind="series")
    assert created is not None
    assert created[1] is True


def _make_database(tmp_path: Path) -> SqliteDatabase:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    return database

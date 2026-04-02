from __future__ import annotations

from pathlib import Path

from app.db.sqlite import SqliteDatabase
from app.db.watchlist_repo import WatchlistRepo
from app.services.manage_watchlist import (
    WATCHLIST_ADD_USAGE_TEXT,
    WATCHLIST_CLEAR_EMPTY_TEXT,
    WATCHLIST_EMPTY_TEXT,
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


def test_parse_watchlist_query_non_watchlist_text_returns_none() -> None:
    assert parse_watchlist_query("dune 2021") is None
    assert parse_watchlist_query("") is None


def test_manage_watchlist_add_list_remove_clear(tmp_path: Path) -> None:
    service = ManageWatchlistService(WatchlistRepo(_make_database(tmp_path)))

    assert service.handle(parse_watchlist_query("watchlist list"), chat_id=1001) == WATCHLIST_EMPTY_TEXT

    added_text = service.handle(parse_watchlist_query("watchlist add dune 2021"), chat_id=1001)
    assert "已加入想看：dune (2021)" in added_text
    assert "条目ID:" in added_text
    item_id = int(added_text.rsplit(":", maxsplit=1)[1].strip())

    duplicate_text = service.handle(parse_watchlist_query("想看 add dune 2021"), chat_id=1001)
    assert "想看已存在：dune (2021)" in duplicate_text
    assert str(item_id) in duplicate_text

    list_text = service.handle(parse_watchlist_query("watchlist list"), chat_id=1001)
    assert f"[{item_id}] dune (2021)" in list_text

    removed_text = service.handle(parse_watchlist_query(f"watchlist remove {item_id}"), chat_id=1001)
    assert removed_text == f"已删除想看条目：{item_id}"

    assert service.handle(parse_watchlist_query("watchlist clear"), chat_id=1001) == WATCHLIST_CLEAR_EMPTY_TEXT


def test_manage_watchlist_validation_errors(tmp_path: Path) -> None:
    service = ManageWatchlistService(WatchlistRepo(_make_database(tmp_path)))

    assert service.handle(parse_watchlist_query("watchlist add"), chat_id=1001) == WATCHLIST_ADD_USAGE_TEXT
    assert service.handle(parse_watchlist_query("watchlist remove"), chat_id=1001) == WATCHLIST_REMOVE_USAGE_TEXT
    assert service.handle(parse_watchlist_query("watchlist remove x"), chat_id=1001) == WATCHLIST_REMOVE_USAGE_TEXT


def test_watchlist_repo_persists_for_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    before_restart_db = SqliteDatabase(str(db_path))
    before_restart_db.initialize()
    before_restart_repo = WatchlistRepo(before_restart_db)
    created = before_restart_repo.add_item(chat_id=1001, title="dune", year="2021")
    assert created is not None

    after_restart_repo = WatchlistRepo(SqliteDatabase(str(db_path)))
    items = after_restart_repo.list_items(chat_id=1001)
    assert len(items) == 1
    assert items[0].title == "dune"
    assert items[0].year == "2021"


def _make_database(tmp_path: Path) -> SqliteDatabase:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    return database

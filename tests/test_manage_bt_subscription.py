from __future__ import annotations

import asyncio
from pathlib import Path

from app.db.bt_subscription_repo import BtSubscriptionRepo
from app.db.sqlite import SqliteDatabase
from app.services.add_to_downloader import AddToDownloaderService
from app.services.manage_bt_subscription import (
    BtSubscriptionDispatchContext,
    ManageBtSubscriptionService,
    parse_bt_subscription_query,
)
from app.services.search_media import SearchMediaService


async def _fake_search(_: str) -> list[dict[str, object]]:
    return []


async def _fake_subscription_search(_: str) -> list[dict[str, object]]:
    return [
        {
            "title": "Frieren S01E01 1080p",
            "downloadUrl": "https://example.com/frieren-s01e01.torrent",
        }
    ]


async def _fake_add_torrent(source: str, downloader_name: str = "", download_dir: str = "") -> object:
    class _Task:
        task_id = "task-1"
        task_hash = "hash-1"

    _ = (source, downloader_name, download_dir)
    return _Task()


def test_parse_bt_subscription_query_supports_list_add_remove_clear_and_run() -> None:
    assert parse_bt_subscription_query("btsub") == parse_bt_subscription_query("btsub list")
    assert parse_bt_subscription_query("btsub run") is not None
    assert parse_bt_subscription_query("btsub add anime 葬送的芙莉莲 2023") is not None
    assert parse_bt_subscription_query("btsub remove 7") is not None
    assert parse_bt_subscription_query("btsub clear") is not None
    assert parse_bt_subscription_query("watchlist list") is None


def test_manage_bt_subscription_add_list_remove_clear_and_restart(tmp_path: Path) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)
    add_service = AddToDownloaderService(SearchMediaService(_fake_search), _fake_add_torrent)
    service = ManageBtSubscriptionService(repo, _fake_search, add_service)

    added_text = service.handle(
        parse_bt_subscription_query("btsub add series 三体 2023"),
        chat_id=1001,
    )
    assert "已加入 BT 订阅" in added_text
    assert "类型: 剧集" in added_text

    list_text = service.handle(parse_bt_subscription_query("btsub list"), chat_id=1001)
    assert "BT 订阅清单" in list_text
    assert "三体" in list_text

    restarted_service = ManageBtSubscriptionService(
        BtSubscriptionRepo(_make_database(tmp_path)),
        _fake_search,
        add_service,
    )
    restarted_list = restarted_service.handle(parse_bt_subscription_query("btsub list"), chat_id=1001)
    assert "三体" in restarted_list

    remove_text = restarted_service.handle(parse_bt_subscription_query("btsub remove 1"), chat_id=1001)
    assert remove_text == "已删除 BT 订阅条目：1"
    clear_text = restarted_service.handle(parse_bt_subscription_query("btsub clear"), chat_id=1001)
    assert clear_text == "BT 订阅清单本来就是空的。"


def test_bt_subscription_run_once_enqueues_new_candidate_and_skips_seen_source(tmp_path: Path) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)
    repo.add_item(chat_id=1001, title="葬送的芙莉莲", year="2023", media_kind="anime")
    add_service = AddToDownloaderService(SearchMediaService(_fake_search), _fake_add_torrent)
    service = ManageBtSubscriptionService(repo, _fake_subscription_search, add_service)
    dispatch_context = BtSubscriptionDispatchContext(
        downloader_name="tr-main",
        downloader_type="transmission",
        download_dir="/data/downloads/tr",
    )

    first_reply = asyncio.run(
        service.run_once(
            chat_id=1001,
            user_id=2001,
            dispatch_context=dispatch_context,
        )
    )
    assert "BT 订阅扫描完成：共扫描 1 条，命中新资源 1 条。" in first_reply
    assert "下载待确认：" in first_reply
    assert "Frieren S01E01 1080p" in first_reply

    item = repo.list_items(chat_id=1001)[0]
    assert item.last_seen_source == "https://example.com/frieren-s01e01.torrent"
    assert item.last_seen_title == "Frieren S01E01 1080p"

    second_reply = asyncio.run(
        service.run_once(
            chat_id=1001,
            user_id=2001,
            dispatch_context=dispatch_context,
        )
    )
    assert second_reply == "BT 订阅扫描完成：共扫描 1 条，当前没有新资源。"


def _make_database(tmp_path: Path) -> SqliteDatabase:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    return database

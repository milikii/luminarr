from __future__ import annotations

import asyncio
from pathlib import Path

from app.db.bt_subscription_repo import BtSubscriptionPersistenceError, BtSubscriptionRepo
from app.db.sqlite import SqliteDatabase
from app.services.add_to_downloader import AddToDownloaderService
from app.services.manage_bt_subscription import (
    BT_SUBSCRIPTION_ADD_FAILED_TEXT,
    BT_SUBSCRIPTION_CLEAR_FAILED_TEXT,
    BT_SUBSCRIPTION_LIST_FAILED_TEXT,
    BT_SUBSCRIPTION_REMOVE_FAILED_TEXT,
    BT_SUBSCRIPTION_RUN_FAILED_TEXT,
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


def test_manage_bt_subscription_add_returns_failure_text_when_repo_returns_none(tmp_path: Path, capsys) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)

    def _fail_add_item(**_: object) -> None:
        return None

    repo.add_item = _fail_add_item  # type: ignore[method-assign]
    add_service = AddToDownloaderService(SearchMediaService(_fake_search), _fake_add_torrent)
    service = ManageBtSubscriptionService(repo, _fake_search, add_service)

    reply = service.handle(parse_bt_subscription_query("btsub add anime 葬送的芙莉莲 2023"), chat_id=1001)

    assert reply == BT_SUBSCRIPTION_ADD_FAILED_TEXT
    captured = capsys.readouterr()
    assert "[BT 订阅写入失败]" in captured.out
    assert "[处理建议]" in captured.out
    assert "bt subscription add result missing" in captured.out


def test_manage_bt_subscription_add_logs_missing_row_after_insert(tmp_path: Path, capsys) -> None:
    class MissingRowBtSubscriptionRepo(BtSubscriptionRepo):
        def add_item(self, *, chat_id: int, title: str, year: str, media_kind: str):
            raise BtSubscriptionPersistenceError("bt_subscription_item missing after insert")

    database = _make_database(tmp_path)
    repo = MissingRowBtSubscriptionRepo(database)
    add_service = AddToDownloaderService(SearchMediaService(_fake_search), _fake_add_torrent)
    service = ManageBtSubscriptionService(repo, _fake_search, add_service)

    reply = service.handle(parse_bt_subscription_query("btsub add anime 葬送的芙莉莲 2023"), chat_id=1001)

    assert reply == BT_SUBSCRIPTION_ADD_FAILED_TEXT
    captured = capsys.readouterr()
    assert "[BT 订阅写入失败]" in captured.out
    assert "bt_subscription_item missing after insert" in captured.out


def test_manage_bt_subscription_add_returns_failure_text_when_repo_raises(tmp_path: Path, capsys) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)

    def _crash_add_item(**_: object) -> None:
        raise RuntimeError("db down")

    repo.add_item = _crash_add_item  # type: ignore[method-assign]
    add_service = AddToDownloaderService(SearchMediaService(_fake_search), _fake_add_torrent)
    service = ManageBtSubscriptionService(repo, _fake_search, add_service)

    reply = service.handle(parse_bt_subscription_query("btsub add anime 葬送的芙莉莲 2023"), chat_id=1001)

    assert reply == BT_SUBSCRIPTION_ADD_FAILED_TEXT
    captured = capsys.readouterr()
    assert "[BT 订阅写入失败]" in captured.out
    assert "db down" in captured.out


def test_manage_bt_subscription_list_returns_failure_text_when_repo_raises(tmp_path: Path, capsys) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)

    def _crash_list_items(**_: object) -> None:
        raise RuntimeError("db down")

    repo.list_items = _crash_list_items  # type: ignore[method-assign]
    add_service = AddToDownloaderService(SearchMediaService(_fake_search), _fake_add_torrent)
    service = ManageBtSubscriptionService(repo, _fake_search, add_service)

    reply = service.handle(parse_bt_subscription_query("btsub list"), chat_id=1001)

    assert reply == BT_SUBSCRIPTION_LIST_FAILED_TEXT
    captured = capsys.readouterr()
    assert "[BT 订阅清单读取失败]" in captured.out
    assert "db down" in captured.out


def test_manage_bt_subscription_list_returns_failure_text_when_repo_returns_none(tmp_path: Path, capsys) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)

    def _missing_list_items(**_: object) -> None:
        return None

    repo.list_items = _missing_list_items  # type: ignore[method-assign]
    add_service = AddToDownloaderService(SearchMediaService(_fake_search), _fake_add_torrent)
    service = ManageBtSubscriptionService(repo, _fake_search, add_service)

    reply = service.handle(parse_bt_subscription_query("btsub list"), chat_id=1001)

    assert reply == BT_SUBSCRIPTION_LIST_FAILED_TEXT
    captured = capsys.readouterr()
    assert "[BT 订阅清单读取失败]" in captured.out
    assert "[处理建议]" in captured.out
    assert "bt subscription list result missing" in captured.out


def test_manage_bt_subscription_remove_returns_failure_text_when_repo_raises(tmp_path: Path, capsys) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)

    def _crash_remove_item(**_: object) -> None:
        raise RuntimeError("db down")

    repo.remove_item = _crash_remove_item  # type: ignore[method-assign]
    add_service = AddToDownloaderService(SearchMediaService(_fake_search), _fake_add_torrent)
    service = ManageBtSubscriptionService(repo, _fake_search, add_service)

    reply = service.handle(parse_bt_subscription_query("btsub remove 7"), chat_id=1001)

    assert reply == BT_SUBSCRIPTION_REMOVE_FAILED_TEXT
    captured = capsys.readouterr()
    assert "[BT 订阅删除失败]" in captured.out
    assert "db down" in captured.out


def test_manage_bt_subscription_remove_returns_failure_text_when_repo_returns_none(tmp_path: Path, capsys) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)

    def _missing_remove_item(**_: object) -> None:
        return None

    repo.remove_item = _missing_remove_item  # type: ignore[method-assign]
    add_service = AddToDownloaderService(SearchMediaService(_fake_search), _fake_add_torrent)
    service = ManageBtSubscriptionService(repo, _fake_search, add_service)

    reply = service.handle(parse_bt_subscription_query("btsub remove 7"), chat_id=1001)

    assert reply == BT_SUBSCRIPTION_REMOVE_FAILED_TEXT
    captured = capsys.readouterr()
    assert "[BT 订阅删除失败]" in captured.out
    assert "[处理建议]" in captured.out
    assert "bt subscription remove result missing" in captured.out


def test_manage_bt_subscription_clear_returns_failure_text_when_repo_raises(tmp_path: Path, capsys) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)

    def _crash_clear_items(**_: object) -> None:
        raise RuntimeError("db down")

    repo.clear_items = _crash_clear_items  # type: ignore[method-assign]
    add_service = AddToDownloaderService(SearchMediaService(_fake_search), _fake_add_torrent)
    service = ManageBtSubscriptionService(repo, _fake_search, add_service)

    reply = service.handle(parse_bt_subscription_query("btsub clear"), chat_id=1001)

    assert reply == BT_SUBSCRIPTION_CLEAR_FAILED_TEXT
    captured = capsys.readouterr()
    assert "[BT 订阅清单清空失败]" in captured.out
    assert "db down" in captured.out


def test_manage_bt_subscription_clear_returns_failure_text_when_repo_returns_none(tmp_path: Path, capsys) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)

    def _missing_clear_items(**_: object) -> None:
        return None

    repo.clear_items = _missing_clear_items  # type: ignore[method-assign]
    add_service = AddToDownloaderService(SearchMediaService(_fake_search), _fake_add_torrent)
    service = ManageBtSubscriptionService(repo, _fake_search, add_service)

    reply = service.handle(parse_bt_subscription_query("btsub clear"), chat_id=1001)

    assert reply == BT_SUBSCRIPTION_CLEAR_FAILED_TEXT
    captured = capsys.readouterr()
    assert "[BT 订阅清单清空失败]" in captured.out
    assert "[处理建议]" in captured.out
    assert "bt subscription clear result missing" in captured.out


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


def test_bt_subscription_run_once_prefers_new_ranked_candidate(tmp_path: Path) -> None:
    async def _ranked_search(_: str) -> list[dict[str, object]]:
        return [
            {
                "title": "Frieren S01E01 1080p",
                "downloadUrl": "https://example.com/already-seen.torrent",
                "seeders": 99,
                "size": 2_000_000_000,
            },
            {
                "title": "Frieren S01E01 CAM",
                "downloadUrl": "https://example.com/cam.torrent",
                "seeders": 500,
                "size": 3_000_000_000,
            },
            {
                "title": "Frieren S01E01 720p",
                "downloadUrl": "https://example.com/720p.torrent",
                "seeders": 50,
                "size": 1_500_000_000,
            },
            {
                "title": "Frieren S01E01 1080p",
                "downloadUrl": "https://example.com/1080p.torrent",
                "seeders": 20,
                "size": 2_200_000_000,
            },
        ]

    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)
    created = repo.add_item(chat_id=1001, title="葬送的芙莉莲", year="2023", media_kind="anime")
    assert created is not None
    item, _ = created
    assert repo.update_last_seen(
        chat_id=1001,
        item_id=item.item_id,
        source="https://example.com/already-seen.torrent",
        title="Frieren S01E01 1080p",
    )

    add_service = AddToDownloaderService(SearchMediaService(_fake_search), _fake_add_torrent)
    service = ManageBtSubscriptionService(repo, _ranked_search, add_service)
    dispatch_context = BtSubscriptionDispatchContext(
        downloader_name="tr-main",
        downloader_type="transmission",
        download_dir="/data/downloads/tr",
    )

    reply = asyncio.run(
        service.run_once(
            chat_id=1001,
            user_id=2001,
            dispatch_context=dispatch_context,
        )
    )

    assert "命中资源: Frieren S01E01 1080p" in reply
    item = repo.list_items(chat_id=1001)[0]
    assert item.last_seen_source == "https://example.com/1080p.torrent"
    assert item.last_seen_title == "Frieren S01E01 1080p"


def test_bt_subscription_run_once_warns_when_last_seen_truth_is_not_updated(tmp_path: Path, capsys) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)
    created = repo.add_item(chat_id=1001, title="葬送的芙莉莲", year="2023", media_kind="anime")
    assert created is not None

    def _fail_update_last_seen(**_: object) -> bool:
        return False

    repo.update_last_seen = _fail_update_last_seen  # type: ignore[method-assign]
    add_service = AddToDownloaderService(SearchMediaService(_fake_search), _fake_add_torrent)
    service = ManageBtSubscriptionService(repo, _fake_subscription_search, add_service)
    dispatch_context = BtSubscriptionDispatchContext(
        downloader_name="tr-main",
        downloader_type="transmission",
        download_dir="/data/downloads/tr",
    )

    reply = asyncio.run(
        service.run_once(
            chat_id=1001,
            user_id=2001,
            dispatch_context=dispatch_context,
        )
    )

    assert "下载待确认：" in reply
    assert "最近资源真相未更新" in reply
    assert repo.list_items(chat_id=1001)[0].last_seen_source == ""
    captured = capsys.readouterr()
    assert "[BT 订阅最近资源回写失败]" in captured.out
    assert "[处理建议]" in captured.out
    assert "bt subscription last_seen update result missing" in captured.out


def test_bt_subscription_run_once_logs_missing_row_during_last_seen_update(tmp_path: Path, capsys) -> None:
    class MissingRowBtSubscriptionRepo(BtSubscriptionRepo):
        def update_last_seen(self, *, chat_id: int, item_id: int, source: str, title: str) -> bool:
            raise BtSubscriptionPersistenceError("bt_subscription_item missing during last_seen update")

    database = _make_database(tmp_path)
    repo = MissingRowBtSubscriptionRepo(database)
    created = repo.add_item(chat_id=1001, title="葬送的芙莉莲", year="2023", media_kind="anime")
    assert created is not None
    add_service = AddToDownloaderService(SearchMediaService(_fake_search), _fake_add_torrent)
    service = ManageBtSubscriptionService(repo, _fake_subscription_search, add_service)
    dispatch_context = BtSubscriptionDispatchContext(
        downloader_name="tr-main",
        downloader_type="transmission",
        download_dir="/data/downloads/tr",
    )

    reply = asyncio.run(
        service.run_once(
            chat_id=1001,
            user_id=2001,
            dispatch_context=dispatch_context,
        )
    )

    assert "下载待确认：" in reply
    assert "最近资源真相未更新" in reply
    captured = capsys.readouterr()
    assert "[BT 订阅最近资源回写失败]" in captured.out
    assert "bt_subscription_item missing during last_seen update" in captured.out


def test_bt_subscription_run_once_returns_failure_text_when_scan_items_raise(tmp_path: Path, capsys) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)

    def _crash_list_items(**_: object) -> None:
        raise RuntimeError("db down")

    repo.list_items = _crash_list_items  # type: ignore[method-assign]
    add_service = AddToDownloaderService(SearchMediaService(_fake_search), _fake_add_torrent)
    service = ManageBtSubscriptionService(repo, _fake_subscription_search, add_service)
    dispatch_context = BtSubscriptionDispatchContext(
        downloader_name="tr-main",
        downloader_type="transmission",
        download_dir="/data/downloads/tr",
    )

    reply = asyncio.run(
        service.run_once(
            chat_id=1001,
            user_id=2001,
            dispatch_context=dispatch_context,
        )
    )

    assert reply == BT_SUBSCRIPTION_RUN_FAILED_TEXT
    captured = capsys.readouterr()
    assert "[BT 订阅扫描读取失败]" in captured.out
    assert "chat_id=1001" in captured.out
    assert "db down" in captured.out
    assert "[处理建议]" in captured.out


def test_bt_subscription_run_once_returns_failure_text_when_scan_items_return_none(
    tmp_path: Path,
    capsys,
) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)

    def _missing_list_items(**_: object) -> None:
        return None

    repo.list_items = _missing_list_items  # type: ignore[method-assign]
    add_service = AddToDownloaderService(SearchMediaService(_fake_search), _fake_add_torrent)
    service = ManageBtSubscriptionService(repo, _fake_subscription_search, add_service)
    dispatch_context = BtSubscriptionDispatchContext(
        downloader_name="tr-main",
        downloader_type="transmission",
        download_dir="/data/downloads/tr",
    )

    reply = asyncio.run(
        service.run_once(
            chat_id=1001,
            user_id=2001,
            dispatch_context=dispatch_context,
        )
    )

    assert reply == BT_SUBSCRIPTION_RUN_FAILED_TEXT
    captured = capsys.readouterr()
    assert "[BT 订阅扫描读取失败]" in captured.out
    assert "chat_id=1001" in captured.out
    assert "bt subscription scan items result missing" in captured.out
    assert "[处理建议]" in captured.out


def test_bt_subscription_run_once_returns_failure_text_when_pending_creation_is_unavailable(
    tmp_path: Path,
    capsys,
) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)
    repo.add_item(chat_id=1001, title="葬送的芙莉莲", year="2023", media_kind="anime")
    add_service = AddToDownloaderService(SearchMediaService(_fake_search), _fake_add_torrent)

    async def _fail_add_candidate_source(**_: object) -> str:
        return "下载待确认状态写入失败，请稍后重试。"

    add_service.add_candidate_source = _fail_add_candidate_source  # type: ignore[method-assign]
    service = ManageBtSubscriptionService(repo, _fake_subscription_search, add_service)
    dispatch_context = BtSubscriptionDispatchContext(
        downloader_name="tr-main",
        downloader_type="transmission",
        download_dir="/data/downloads/tr",
    )

    reply = asyncio.run(
        service.run_once(
            chat_id=1001,
            user_id=2001,
            dispatch_context=dispatch_context,
        )
    )

    assert reply == BT_SUBSCRIPTION_RUN_FAILED_TEXT
    captured = capsys.readouterr()
    assert "[BT 订阅待确认创建失败]" in captured.out
    assert "chat_id=1001" in captured.out
    assert "下载待确认状态写入失败，请稍后重试。" in captured.out
    assert "[处理建议]" in captured.out


def test_bt_subscription_scheduler_tick_reuses_ranked_candidate_selection(tmp_path: Path) -> None:
    async def _scheduler_search(_: str) -> list[dict[str, object]]:
        return [
            {
                "title": "Frieren S01E01 CAM",
                "downloadUrl": "https://example.com/cam.torrent",
                "seeders": 500,
                "size": 3_000_000_000,
            },
            {
                "title": "Frieren S01E01 720p",
                "downloadUrl": "https://example.com/720p.torrent",
                "seeders": 30,
                "size": 1_500_000_000,
            },
        ]

    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)
    repo.add_item(chat_id=1001, title="葬送的芙莉莲", year="2023", media_kind="anime")
    add_service = AddToDownloaderService(SearchMediaService(_fake_search), _fake_add_torrent)
    service = ManageBtSubscriptionService(repo, _scheduler_search, add_service)
    dispatch_context = BtSubscriptionDispatchContext(
        downloader_name="tr-main",
        downloader_type="transmission",
        download_dir="/data/downloads/tr",
    )

    notifications = asyncio.run(
        service.run_scheduler_tick(
            dispatch_context=dispatch_context,
        )
    )

    assert notifications
    chat_id, reply = notifications[0]
    assert chat_id == 1001
    assert "命中资源: Frieren S01E01 720p" in reply


def test_bt_subscription_run_once_warns_when_pending_creation_is_partially_unavailable(tmp_path: Path) -> None:
    async def _multi_item_search(query: str) -> list[dict[str, object]]:
        return [
            {
                "title": f"{query} 1080p",
                "downloadUrl": f"https://example.com/{query}.torrent",
            }
        ]

    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)
    repo.add_item(chat_id=1001, title="葬送的芙莉莲", year="2023", media_kind="anime")
    repo.add_item(chat_id=1001, title="沙丘", year="2021", media_kind="movie")
    add_service = AddToDownloaderService(SearchMediaService(_fake_search), _fake_add_torrent)
    pending_texts = iter(
        (
            "下载待确认：Frieren S01E01 1080p\n选择序号: hash-1\n请发送 confirm hash-1 执行下载。",
            "下载待确认状态写入失败，请稍后重试。",
        )
    )

    async def _mixed_add_candidate_source(**_: object) -> str:
        return next(pending_texts)

    add_service.add_candidate_source = _mixed_add_candidate_source  # type: ignore[method-assign]
    service = ManageBtSubscriptionService(repo, _multi_item_search, add_service)
    dispatch_context = BtSubscriptionDispatchContext(
        downloader_name="tr-main",
        downloader_type="transmission",
        download_dir="/data/downloads/tr",
    )

    reply = asyncio.run(
        service.run_once(
            chat_id=1001,
            user_id=2001,
            dispatch_context=dispatch_context,
        )
    )

    assert "BT 订阅扫描完成：共扫描 2 条，命中新资源 1 条。" in reply
    assert "下载待确认：Frieren S01E01 1080p" in reply
    assert "本轮有命中的 BT 订阅未能创建下载待确认" in reply


def test_bt_subscription_scheduler_tick_skips_chat_when_scan_items_raise(tmp_path: Path, capsys) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)
    repo.add_item(chat_id=1001, title="葬送的芙莉莲", year="2023", media_kind="anime")

    def _crash_list_items(*, chat_id: int) -> None:
        raise RuntimeError(f"db down for {chat_id}")

    repo.list_items = _crash_list_items  # type: ignore[method-assign]
    add_service = AddToDownloaderService(SearchMediaService(_fake_search), _fake_add_torrent)
    service = ManageBtSubscriptionService(repo, _fake_subscription_search, add_service)
    dispatch_context = BtSubscriptionDispatchContext(
        downloader_name="tr-main",
        downloader_type="transmission",
        download_dir="/data/downloads/tr",
    )

    notifications = asyncio.run(
        service.run_scheduler_tick(
            dispatch_context=dispatch_context,
        )
    )

    assert notifications is None
    captured = capsys.readouterr()
    assert "[BT 订阅扫描读取失败]" in captured.out
    assert "chat_id=1001" in captured.out
    assert "db down for 1001" in captured.out


def test_bt_subscription_scheduler_tick_skips_chat_when_scan_items_return_none(
    tmp_path: Path,
    capsys,
) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)
    repo.add_item(chat_id=1001, title="葬送的芙莉莲", year="2023", media_kind="anime")

    def _missing_list_items(*, chat_id: int) -> None:
        _ = chat_id
        return None

    repo.list_items = _missing_list_items  # type: ignore[method-assign]
    add_service = AddToDownloaderService(SearchMediaService(_fake_search), _fake_add_torrent)
    service = ManageBtSubscriptionService(repo, _fake_subscription_search, add_service)
    dispatch_context = BtSubscriptionDispatchContext(
        downloader_name="tr-main",
        downloader_type="transmission",
        download_dir="/data/downloads/tr",
    )

    notifications = asyncio.run(
        service.run_scheduler_tick(
            dispatch_context=dispatch_context,
        )
    )

    assert notifications is None
    captured = capsys.readouterr()
    assert "[BT 订阅扫描读取失败]" in captured.out
    assert "chat_id=1001" in captured.out
    assert "bt subscription scan items result missing" in captured.out


def test_bt_subscription_scheduler_tick_returns_none_when_chat_id_lookup_raises(
    tmp_path: Path,
    capsys,
) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)

    def _crash_list_chat_ids() -> None:
        raise RuntimeError("db down")

    repo.list_chat_ids = _crash_list_chat_ids  # type: ignore[method-assign]
    add_service = AddToDownloaderService(SearchMediaService(_fake_search), _fake_add_torrent)
    service = ManageBtSubscriptionService(repo, _fake_subscription_search, add_service)
    dispatch_context = BtSubscriptionDispatchContext(
        downloader_name="tr-main",
        downloader_type="transmission",
        download_dir="/data/downloads/tr",
    )

    notifications = asyncio.run(
        service.run_scheduler_tick(
            dispatch_context=dispatch_context,
        )
    )

    assert notifications is None
    captured = capsys.readouterr()
    assert "[BT 订阅扫描 chat 列表读取失败]" in captured.out
    assert "db down" in captured.out
    assert "[处理建议]" in captured.out


def test_bt_subscription_scheduler_tick_surfaces_invalid_chat_identity_row(tmp_path: Path, capsys) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO bt_subscription_item (
                chat_id,
                title,
                year,
                media_kind,
                last_seen_source,
                last_seen_title,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, '', '', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                0,
                "葬送的芙莉莲",
                "2023",
                "anime",
            ),
        )
        connection.commit()

    add_service = AddToDownloaderService(SearchMediaService(_fake_search), _fake_add_torrent)
    service = ManageBtSubscriptionService(repo, _fake_subscription_search, add_service)
    dispatch_context = BtSubscriptionDispatchContext(
        downloader_name="tr-main",
        downloader_type="transmission",
        download_dir="/data/downloads/tr",
    )

    notifications = asyncio.run(
        service.run_scheduler_tick(
            dispatch_context=dispatch_context,
        )
    )

    assert notifications is None
    captured = capsys.readouterr()
    assert "[BT 订阅扫描 chat 列表读取失败]" in captured.out
    assert "bt_subscription_item chat identity corrupted in chat list after read" in captured.out


def test_bt_subscription_scheduler_tick_warns_when_last_seen_update_raises(tmp_path: Path, capsys) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)
    created = repo.add_item(chat_id=1001, title="葬送的芙莉莲", year="2023", media_kind="anime")
    assert created is not None

    def _crash_update_last_seen(**_: object) -> bool:
        raise RuntimeError("db down")

    repo.update_last_seen = _crash_update_last_seen  # type: ignore[method-assign]
    add_service = AddToDownloaderService(SearchMediaService(_fake_search), _fake_add_torrent)
    service = ManageBtSubscriptionService(repo, _fake_subscription_search, add_service)
    dispatch_context = BtSubscriptionDispatchContext(
        downloader_name="tr-main",
        downloader_type="transmission",
        download_dir="/data/downloads/tr",
    )

    notifications = asyncio.run(
        service.run_scheduler_tick(
            dispatch_context=dispatch_context,
        )
    )

    assert notifications
    chat_id, reply = notifications[0]
    assert chat_id == 1001
    assert "下载待确认：" in reply
    assert "最近资源真相未更新" in reply
    captured = capsys.readouterr()
    assert "[BT 订阅最近资源回写失败]" in captured.out
    assert "db down" in captured.out


def test_bt_subscription_scheduler_tick_skips_chat_when_pending_creation_is_unavailable(
    tmp_path: Path,
    capsys,
) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)
    repo.add_item(chat_id=1001, title="葬送的芙莉莲", year="2023", media_kind="anime")
    add_service = AddToDownloaderService(SearchMediaService(_fake_search), _fake_add_torrent)

    async def _fail_add_candidate_source(**_: object) -> str:
        return "下载待确认状态写入失败，请稍后重试。"

    add_service.add_candidate_source = _fail_add_candidate_source  # type: ignore[method-assign]
    service = ManageBtSubscriptionService(repo, _fake_subscription_search, add_service)
    dispatch_context = BtSubscriptionDispatchContext(
        downloader_name="tr-main",
        downloader_type="transmission",
        download_dir="/data/downloads/tr",
    )

    notifications = asyncio.run(
        service.run_scheduler_tick(
            dispatch_context=dispatch_context,
        )
    )

    assert notifications is None
    captured = capsys.readouterr()
    assert "[BT 订阅待确认创建失败]" in captured.out
    assert "chat_id=1001" in captured.out
    assert "下载待确认状态写入失败，请稍后重试。" in captured.out
    assert "[处理建议]" in captured.out


def _make_database(tmp_path: Path) -> SqliteDatabase:
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    return database

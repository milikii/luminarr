from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

import httpx

from app.db.bt_subscription_repo import BtSubscriptionItem, BtSubscriptionPersistenceError, BtSubscriptionRepo
from app.db.sqlite import SqliteDatabase
from app.services.add_to_downloader import AddToDownloaderService
from app.services.bt_candidate_scorer import DEFAULT_BT_SCORING_RULES, BTScoringRules
from app.services.bt_subscription_command import (
    BT_SUBSCRIPTION_ADULT_ONLY_TEXT,
    ParsedBtSubscriptionAddRequest,
    format_bt_subscription_add_result,
    format_bt_subscription_clear_result,
    format_bt_subscription_list,
    format_bt_subscription_remove_result,
    parse_bt_subscription_add_request,
    parse_bt_subscription_query,
)
from app.services.manage_bt_subscription import (
    BT_SUBSCRIPTION_ADD_FAILED_TEXT,
    BT_SUBSCRIPTION_CLEAR_FAILED_TEXT,
    BT_SUBSCRIPTION_LAST_SEEN_ITEM_MISSING_WARNING_TEXT,
    BT_SUBSCRIPTION_LIST_FAILED_TEXT,
    BT_SUBSCRIPTION_PENDING_CREATION_FAILED_TEXT,
    BT_SUBSCRIPTION_REMOVE_FAILED_TEXT,
    BT_SUBSCRIPTION_RUN_FAILED_TEXT,
    BtSubscriptionDispatchContext,
    ManageBtSubscriptionService,
)
from app.services.search_media import SearchMediaService

_ADULT_QUERY = "SSIS-123"
_ADULT_CONTENT_ID = "censored:ssis-123"


async def _fake_search(_: str) -> list[dict[str, object]]:
    return []


async def _fake_subscription_search(_: str) -> list[dict[str, object]]:
    return [_adult_candidate("SSIS-123 1080p", "https://example.com/ssis-123-1080p.torrent")]


async def _fake_add_torrent(source: str, downloader_name: str = "", download_dir: str = "") -> object:
    class _Task:
        task_id = "task-1"
        task_hash = "hash-1"

    _ = (source, downloader_name, download_dir)
    return _Task()


def _adult_candidate(
    title: str,
    download_url: str,
    *,
    seeders: int | None = None,
    size: int | None = None,
) -> dict[str, object]:
    candidate: dict[str, object] = {
        "title": title,
        "downloadUrl": download_url,
        "adult_content_id": _ADULT_CONTENT_ID,
        "adult_archive_category": "censored",
        "adult_display_id": _ADULT_QUERY,
    }
    if seeders is not None:
        candidate["seeders"] = seeders
    if size is not None:
        candidate["size"] = size
    return candidate


def test_parse_bt_subscription_query_supports_list_add_remove_clear_and_run() -> None:
    assert parse_bt_subscription_query("btsub") == parse_bt_subscription_query("btsub list")
    assert parse_bt_subscription_query("btsub run") is not None
    assert parse_bt_subscription_query("btsub add SSIS-123") is not None
    assert parse_bt_subscription_query("btsub remove 7") is not None
    assert parse_bt_subscription_query("btsub clear") is not None
    assert parse_bt_subscription_query("watchlist list") is None


def test_parse_bt_subscription_add_request_extracts_adult_identifier() -> None:
    assert parse_bt_subscription_add_request("SSIS-123") == ParsedBtSubscriptionAddRequest(
        media_kind="adult",
        title="SSIS-123",
        year="",
    )
    assert parse_bt_subscription_add_request("anime 葬送的芙莉莲 2023") is None


def test_bt_subscription_command_helper_formats_list_and_mutation_replies() -> None:
    item = _make_bt_subscription_item(
        item_id=7,
        title="SSIS-123",
        year="",
        media_kind="adult",
        last_seen_title="SSIS-123 1080p",
    )

    assert "BT 订阅清单：" in format_bt_subscription_list([item])
    assert "上次命中资源: SSIS-123 1080p" in format_bt_subscription_list([item])
    assert "已加入 BT 订阅" in format_bt_subscription_add_result(item, is_created=True)
    assert format_bt_subscription_remove_result(7, removed=False) == "未找到对应 BT 订阅条目。"
    assert format_bt_subscription_clear_result(2) == "已清空 BT 订阅清单，共删除 2 条。"


def test_manage_bt_subscription_add_list_remove_clear_and_restart(tmp_path: Path) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)
    add_service = AddToDownloaderService(SearchMediaService(_fake_search), _fake_add_torrent)
    service = ManageBtSubscriptionService(repo, _fake_search, add_service)

    added_text = service.handle(
        parse_bt_subscription_query("btsub add SSIS-123"),
        chat_id=1001,
    )
    assert "已加入 BT 订阅" in added_text
    assert "类型: 成人" in added_text

    list_text = service.handle(parse_bt_subscription_query("btsub list"), chat_id=1001)
    assert "BT 订阅清单" in list_text
    assert "SSIS-123" in list_text

    restarted_service = ManageBtSubscriptionService(
        BtSubscriptionRepo(_make_database(tmp_path)),
        _fake_search,
        add_service,
    )
    restarted_list = restarted_service.handle(parse_bt_subscription_query("btsub list"), chat_id=1001)
    assert "SSIS-123" in restarted_list

    remove_text = restarted_service.handle(parse_bt_subscription_query("btsub remove 1"), chat_id=1001)
    assert remove_text == "已删除 BT 订阅条目：1"
    clear_text = restarted_service.handle(parse_bt_subscription_query("btsub clear"), chat_id=1001)
    assert clear_text == "BT 订阅清单本来就是空的。"


def test_manage_bt_subscription_add_rejects_non_adult_input(tmp_path: Path) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)
    add_service = AddToDownloaderService(SearchMediaService(_fake_search), _fake_add_torrent)
    service = ManageBtSubscriptionService(repo, _fake_search, add_service)

    reply = service.handle(parse_bt_subscription_query("btsub add anime 葬送的芙莉莲 2023"), chat_id=1001)

    assert reply == BT_SUBSCRIPTION_ADULT_ONLY_TEXT


def test_manage_bt_subscription_add_returns_failure_text_when_repo_returns_none(tmp_path: Path, capsys) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)

    def _fail_add_item(**_: object) -> None:
        return None

    repo.add_item = _fail_add_item  # type: ignore[method-assign]
    add_service = AddToDownloaderService(SearchMediaService(_fake_search), _fake_add_torrent)
    service = ManageBtSubscriptionService(repo, _fake_search, add_service)

    reply = service.handle(parse_bt_subscription_query("btsub add SSIS-123"), chat_id=1001)

    assert reply == BT_SUBSCRIPTION_ADD_FAILED_TEXT
    captured = capsys.readouterr()
    assert "[BT 订阅写入结果缺失]" in captured.out
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

    reply = service.handle(parse_bt_subscription_query("btsub add SSIS-123"), chat_id=1001)

    assert reply == BT_SUBSCRIPTION_ADD_FAILED_TEXT
    captured = capsys.readouterr()
    assert "[BT 订阅写入后条目缺失]" in captured.out
    assert "[处理建议]" in captured.out
    assert "bt_subscription_item missing after insert" in captured.out


def test_manage_bt_subscription_add_surfaces_row_corruption(tmp_path: Path, capsys) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)

    def _corrupted_add_item(**_: object) -> None:
        raise BtSubscriptionPersistenceError("bt_subscription_item media kind corrupted after read")

    repo.add_item = _corrupted_add_item  # type: ignore[method-assign]
    add_service = AddToDownloaderService(SearchMediaService(_fake_search), _fake_add_torrent)
    service = ManageBtSubscriptionService(repo, _fake_search, add_service)

    reply = service.handle(parse_bt_subscription_query("btsub add SSIS-123"), chat_id=1001)

    assert reply == BT_SUBSCRIPTION_ADD_FAILED_TEXT
    captured = capsys.readouterr()
    assert "[BT 订阅写入命中坏记录]" in captured.out
    assert "[处理建议]" in captured.out
    assert "bt_subscription_item media kind corrupted after read" in captured.out


def test_manage_bt_subscription_add_returns_failure_text_when_repo_raises(tmp_path: Path, capsys) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)

    def _crash_add_item(**_: object) -> None:
        raise sqlite3.OperationalError("db down")

    repo.add_item = _crash_add_item  # type: ignore[method-assign]
    add_service = AddToDownloaderService(SearchMediaService(_fake_search), _fake_add_torrent)
    service = ManageBtSubscriptionService(repo, _fake_search, add_service)

    reply = service.handle(parse_bt_subscription_query("btsub add SSIS-123"), chat_id=1001)

    assert reply == BT_SUBSCRIPTION_ADD_FAILED_TEXT
    captured = capsys.readouterr()
    assert "[BT 订阅写入失败]" in captured.out
    assert "db down" in captured.out


def test_manage_bt_subscription_list_returns_failure_text_when_repo_raises(tmp_path: Path, capsys) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)

    def _crash_list_items(**_: object) -> None:
        raise sqlite3.OperationalError("db down")

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
    assert "[BT 订阅清单结果缺失]" in captured.out
    assert "[处理建议]" in captured.out
    assert "bt subscription list result missing" in captured.out


def test_manage_bt_subscription_list_surfaces_row_corruption(tmp_path: Path, capsys) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)

    def _corrupted_list_items(**_: object) -> None:
        raise BtSubscriptionPersistenceError("bt_subscription_item media kind corrupted after read")

    repo.list_items = _corrupted_list_items  # type: ignore[method-assign]
    add_service = AddToDownloaderService(SearchMediaService(_fake_search), _fake_add_torrent)
    service = ManageBtSubscriptionService(repo, _fake_search, add_service)

    reply = service.handle(parse_bt_subscription_query("btsub list"), chat_id=1001)

    assert reply == BT_SUBSCRIPTION_LIST_FAILED_TEXT
    captured = capsys.readouterr()
    assert "[BT 订阅清单记录损坏]" in captured.out
    assert "[处理建议]" in captured.out
    assert "bt_subscription_item media kind corrupted after read" in captured.out


def test_manage_bt_subscription_remove_returns_failure_text_when_repo_raises(tmp_path: Path, capsys) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)

    def _crash_remove_item(**_: object) -> None:
        raise sqlite3.OperationalError("db down")

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
    assert "[BT 订阅删除结果缺失]" in captured.out
    assert "[处理建议]" in captured.out
    assert "bt subscription remove result missing" in captured.out


def test_manage_bt_subscription_remove_surfaces_row_corruption(tmp_path: Path, capsys) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)

    def _corrupted_remove_item(**_: object) -> None:
        raise BtSubscriptionPersistenceError("bt_subscription_item media kind corrupted after read")

    repo.remove_item = _corrupted_remove_item  # type: ignore[method-assign]
    add_service = AddToDownloaderService(SearchMediaService(_fake_search), _fake_add_torrent)
    service = ManageBtSubscriptionService(repo, _fake_search, add_service)

    reply = service.handle(parse_bt_subscription_query("btsub remove 7"), chat_id=1001)

    assert reply == BT_SUBSCRIPTION_REMOVE_FAILED_TEXT
    captured = capsys.readouterr()
    assert "[BT 订阅删除命中坏记录]" in captured.out
    assert "[处理建议]" in captured.out
    assert "bt_subscription_item media kind corrupted after read" in captured.out


def test_manage_bt_subscription_clear_returns_failure_text_when_repo_raises(tmp_path: Path, capsys) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)

    def _crash_clear_items(**_: object) -> None:
        raise sqlite3.OperationalError("db down")

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
    assert "[BT 订阅清单清空结果缺失]" in captured.out
    assert "[处理建议]" in captured.out
    assert "bt subscription clear result missing" in captured.out


def test_manage_bt_subscription_clear_surfaces_row_corruption(tmp_path: Path, capsys) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)

    def _corrupted_clear_items(**_: object) -> None:
        raise BtSubscriptionPersistenceError("bt_subscription_item media kind corrupted after read")

    repo.clear_items = _corrupted_clear_items  # type: ignore[method-assign]
    add_service = AddToDownloaderService(SearchMediaService(_fake_search), _fake_add_torrent)
    service = ManageBtSubscriptionService(repo, _fake_search, add_service)

    reply = service.handle(parse_bt_subscription_query("btsub clear"), chat_id=1001)

    assert reply == BT_SUBSCRIPTION_CLEAR_FAILED_TEXT
    captured = capsys.readouterr()
    assert "[BT 订阅清单清空命中坏记录]" in captured.out
    assert "[处理建议]" in captured.out
    assert "bt_subscription_item media kind corrupted after read" in captured.out


def test_manage_bt_subscription_run_once_logs_scan_failure_when_search_raises(tmp_path: Path, capsys) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)
    repo.add_item(chat_id=1001, title=_ADULT_QUERY, year="", media_kind="adult")

    async def _boom(_: str) -> list[dict[str, object]]:
        raise httpx.ConnectError("bt source unavailable", request=httpx.Request("GET", "https://example.com"))

    add_service = AddToDownloaderService(SearchMediaService(_fake_search), _fake_add_torrent)
    service = ManageBtSubscriptionService(repo, _boom, add_service)
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

    assert reply == "BT 订阅扫描完成：共扫描 1 条，当前没有新资源。"
    captured = capsys.readouterr()
    assert "[BT 订阅扫描失败]" in captured.out
    assert "bt source unavailable" in captured.out


def test_bt_subscription_run_once_enqueues_new_candidate_and_skips_seen_source(tmp_path: Path) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)
    repo.add_item(chat_id=1001, title=_ADULT_QUERY, year="", media_kind="adult")
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
    assert "SSIS-123 1080p" in first_reply

    item = repo.list_items(chat_id=1001)[0]
    assert item.last_seen_source == "https://example.com/ssis-123-1080p.torrent"
    assert item.last_seen_title == "SSIS-123 1080p"

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
            _adult_candidate("SSIS-123 1080p", "https://example.com/already-seen.torrent", seeders=99, size=2_000_000_000),
            _adult_candidate("SSIS-123 CAM", "https://example.com/cam.torrent", seeders=500, size=3_000_000_000),
            _adult_candidate("SSIS-123 720p", "https://example.com/720p.torrent", seeders=50, size=1_500_000_000),
            _adult_candidate("SSIS-123 1080p", "https://example.com/1080p.torrent", seeders=20, size=2_200_000_000),
        ]

    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)
    created = repo.add_item(chat_id=1001, title=_ADULT_QUERY, year="", media_kind="adult")
    assert created is not None
    item, _ = created
    assert repo.update_last_seen(
        chat_id=1001,
        item_id=item.item_id,
        source="https://example.com/already-seen.torrent",
        title="SSIS-123 1080p",
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

    assert "命中资源: SSIS-123 720p" in reply
    item = repo.list_items(chat_id=1001)[0]
    assert item.last_seen_source == "https://example.com/720p.torrent"
    assert item.last_seen_title == "SSIS-123 720p"


def test_bt_subscription_run_once_uses_shared_bt_scoring_rules(tmp_path: Path, monkeypatch) -> None:
    async def _ranked_search(_: str) -> list[dict[str, object]]:
        return [
            _adult_candidate("SSIS-123 1080p", "https://example.com/1080p.torrent", seeders=20, size=2_200_000_000),
            _adult_candidate("SSIS-123 720p", "https://example.com/720p.torrent", seeders=20, size=1_500_000_000),
        ]

    custom_rules = BTScoringRules(
        weights=dict(DEFAULT_BT_SCORING_RULES.weights),
        resolution_scores={
            "2160p": 0.0,
            "1080p": 0.1,
            "720p": 1.0,
            None: 0.0,
        },
        source_type_scores=dict(DEFAULT_BT_SCORING_RULES.source_type_scores),
        codec_scores=dict(DEFAULT_BT_SCORING_RULES.codec_scores),
        release_group_preferred=DEFAULT_BT_SCORING_RULES.release_group_preferred,
    )
    monkeypatch.setattr("app.services.bt_subscription_candidate_helpers.load_bt_scoring_rules", lambda: custom_rules)

    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)
    repo.add_item(chat_id=1001, title=_ADULT_QUERY, year="", media_kind="adult")
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

    assert "命中资源: SSIS-123 720p" in reply
    item = repo.list_items(chat_id=1001)[0]
    assert item.last_seen_source == "https://example.com/720p.torrent"
    assert item.last_seen_title == "SSIS-123 720p"


def test_bt_subscription_run_once_warns_when_last_seen_truth_is_not_updated(tmp_path: Path, capsys) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)
    created = repo.add_item(chat_id=1001, title=_ADULT_QUERY, year="", media_kind="adult")
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
    assert "[BT 订阅最近资源回写结果缺失]" in captured.out
    assert "[处理建议]" in captured.out
    assert "bt subscription last_seen update result missing" in captured.out


def test_bt_subscription_run_once_warns_when_last_seen_truth_update_returns_none(tmp_path: Path, capsys) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)
    created = repo.add_item(chat_id=1001, title=_ADULT_QUERY, year="", media_kind="adult")
    assert created is not None

    def _missing_update_last_seen(**_: object) -> None:
        return None

    repo.update_last_seen = _missing_update_last_seen  # type: ignore[method-assign]
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
    assert "[BT 订阅最近资源回写结果缺失]" in captured.out
    assert "[处理建议]" in captured.out
    assert "bt subscription last_seen update result missing" in captured.out


def test_bt_subscription_run_once_logs_missing_row_during_last_seen_update(tmp_path: Path, capsys) -> None:
    class MissingRowBtSubscriptionRepo(BtSubscriptionRepo):
        def update_last_seen(self, *, chat_id: int, item_id: int, source: str, title: str) -> bool:
            raise BtSubscriptionPersistenceError("bt_subscription_item missing during last_seen update")

    database = _make_database(tmp_path)
    repo = MissingRowBtSubscriptionRepo(database)
    created = repo.add_item(chat_id=1001, title=_ADULT_QUERY, year="", media_kind="adult")
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
    assert BT_SUBSCRIPTION_LAST_SEEN_ITEM_MISSING_WARNING_TEXT in reply
    captured = capsys.readouterr()
    assert "[BT 订阅最近资源回写条目缺失]" in captured.out
    assert "[处理建议]" in captured.out
    assert "bt_subscription_item missing during last_seen update" in captured.out


def test_bt_subscription_run_once_logs_row_corruption_during_last_seen_update(tmp_path: Path, capsys) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)
    created = repo.add_item(chat_id=1001, title=_ADULT_QUERY, year="", media_kind="adult")
    assert created is not None

    def _corrupted_update_last_seen(**_: object) -> bool:
        raise BtSubscriptionPersistenceError("bt_subscription_item media kind corrupted after read")

    repo.update_last_seen = _corrupted_update_last_seen  # type: ignore[method-assign]
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
    assert "[BT 订阅最近资源回写命中坏记录]" in captured.out
    assert "[处理建议]" in captured.out
    assert "bt_subscription_item media kind corrupted after read" in captured.out


def test_bt_subscription_run_once_returns_failure_text_when_scan_items_raise(tmp_path: Path, capsys) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)

    def _crash_list_items(**_: object) -> None:
        raise sqlite3.OperationalError("db down")

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
    assert "[BT 订阅扫描结果缺失]" in captured.out
    assert "chat_id=1001" in captured.out
    assert "bt subscription scan items result missing" in captured.out
    assert "[处理建议]" in captured.out


def test_bt_subscription_run_once_surfaces_scan_item_row_corruption(tmp_path: Path, capsys) -> None:
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
                1001,
                "",
                "",
                "adult",
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

    reply = asyncio.run(
        service.run_once(
            chat_id=1001,
            user_id=2001,
            dispatch_context=dispatch_context,
        )
    )

    assert reply == BT_SUBSCRIPTION_RUN_FAILED_TEXT
    captured = capsys.readouterr()
    assert "[BT 订阅扫描记录损坏]" in captured.out
    assert "chat_id=1001" in captured.out
    assert "bt_subscription_item row identity corrupted after read" in captured.out
    assert "[处理建议]" in captured.out


def test_bt_subscription_run_once_returns_failure_text_when_pending_creation_is_unavailable(
    tmp_path: Path,
    capsys,
) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)
    repo.add_item(chat_id=1001, title=_ADULT_QUERY, year="", media_kind="adult")
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

    assert reply == BT_SUBSCRIPTION_PENDING_CREATION_FAILED_TEXT
    captured = capsys.readouterr()
    assert "[BT 订阅待确认创建失败]" in captured.out
    assert "chat_id=1001" in captured.out
    assert "下载待确认状态写入失败，请稍后重试。" in captured.out
    assert "[处理建议]" in captured.out


def test_bt_subscription_run_once_warns_when_legacy_non_adult_item_is_skipped(tmp_path: Path, capsys) -> None:
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
                1001,
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

    reply = asyncio.run(
        service.run_once(
            chat_id=1001,
            user_id=2001,
            dispatch_context=dispatch_context,
        )
    )

    assert "BT 订阅扫描完成：共扫描 1 条，当前没有新资源。" in reply
    assert "当前有 1 条旧 BT 订阅已超出成人 BT 边界" in reply
    captured = capsys.readouterr()
    assert "[BT 订阅条目已超出当前边界]" in captured.out
    assert "[处理建议]" in captured.out


def test_bt_subscription_scheduler_tick_skips_legacy_non_adult_item_without_notification(tmp_path: Path, capsys) -> None:
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
                1001,
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

    first_notifications = asyncio.run(
        service.run_scheduler_tick(
            dispatch_context=dispatch_context,
        )
    )

    assert first_notifications
    assert first_notifications[0][0] == 1001
    assert "当前有 1 条旧 BT 订阅已超出成人 BT 边界" in first_notifications[0][1]
    captured = capsys.readouterr()
    assert "[BT 订阅条目已超出当前边界]" in captured.out
    assert "[处理建议]" in captured.out

    second_notifications = asyncio.run(
        service.run_scheduler_tick(
            dispatch_context=dispatch_context,
        )
    )

    assert second_notifications == ()


def test_bt_subscription_scheduler_tick_reuses_ranked_candidate_selection(tmp_path: Path) -> None:
    async def _scheduler_search(_: str) -> list[dict[str, object]]:
        return [
            _adult_candidate("SSIS-123 CAM", "https://example.com/cam.torrent", seeders=500, size=3_000_000_000),
            _adult_candidate("SSIS-123 720p", "https://example.com/720p.torrent", seeders=30, size=1_500_000_000),
        ]

    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)
    repo.add_item(chat_id=1001, title=_ADULT_QUERY, year="", media_kind="adult")
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
    assert "命中资源: SSIS-123 720p" in reply


def test_bt_subscription_scheduler_tick_skips_duplicate_last_seen_title_from_new_source(tmp_path: Path) -> None:
    async def _scheduler_search(_: str) -> list[dict[str, object]]:
        return [
            _adult_candidate("SSIS-123 1080p", "https://example.com/mirror-1080p.torrent", seeders=60, size=2_100_000_000),
            _adult_candidate("SSIS-123 720p", "https://example.com/720p.torrent", seeders=30, size=1_500_000_000),
        ]

    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)
    created = repo.add_item(chat_id=1001, title=_ADULT_QUERY, year="", media_kind="adult")
    assert created is not None
    item, _ = created
    assert repo.update_last_seen(
        chat_id=1001,
        item_id=item.item_id,
        source="https://example.com/old-1080p.torrent",
        title="SSIS-123 1080p",
    )

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
    assert "命中资源: SSIS-123 720p" in reply


def test_bt_subscription_run_once_warns_when_pending_creation_is_partially_unavailable(tmp_path: Path) -> None:
    async def _multi_item_search(query: str) -> list[dict[str, object]]:
        return [
            {
                "title": f"{query} 1080p",
                "downloadUrl": f"https://example.com/{query}.torrent",
                "adult_content_id": f"censored:{query.lower()}",
                "adult_archive_category": "censored",
                "adult_display_id": query,
            }
        ]

    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)
    repo.add_item(chat_id=1001, title=_ADULT_QUERY, year="", media_kind="adult")
    repo.add_item(chat_id=1001, title="IPX-001", year="", media_kind="adult")
    add_service = AddToDownloaderService(SearchMediaService(_fake_search), _fake_add_torrent)
    pending_texts = iter(
        (
            "下载待确认：SSIS-123 1080p\n选择序号: hash-1\n请发送 confirm hash-1 执行下载。",
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
    assert "下载待确认：SSIS-123 1080p" in reply
    assert "本轮有命中的 BT 订阅未能创建下载待确认" in reply


def test_bt_subscription_scheduler_tick_skips_chat_when_scan_items_raise(tmp_path: Path, capsys) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)
    repo.add_item(chat_id=1001, title=_ADULT_QUERY, year="", media_kind="adult")

    def _crash_list_items(*, chat_id: int) -> None:
        raise sqlite3.OperationalError(f"db down for {chat_id}")

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
    repo.add_item(chat_id=1001, title=_ADULT_QUERY, year="", media_kind="adult")

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
    assert "[BT 订阅扫描结果缺失]" in captured.out
    assert "chat_id=1001" in captured.out
    assert "bt subscription scan items result missing" in captured.out


def test_bt_subscription_scheduler_tick_skips_chat_when_scan_item_row_is_corrupted(
    tmp_path: Path,
    capsys,
) -> None:
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
                1001,
                "",
                "",
                "adult",
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
    assert "[BT 订阅扫描记录损坏]" in captured.out
    assert "chat_id=1001" in captured.out
    assert "bt_subscription_item row identity corrupted after read" in captured.out
    assert "[处理建议]" in captured.out


def test_bt_subscription_scheduler_tick_returns_none_when_chat_id_lookup_raises(
    tmp_path: Path,
    capsys,
) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)

    def _crash_list_chat_ids() -> None:
        raise sqlite3.OperationalError("db down")

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


def test_bt_subscription_scheduler_tick_returns_none_when_chat_id_lookup_returns_none(
    tmp_path: Path,
    capsys,
) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)

    def _missing_list_chat_ids() -> None:
        return None

    repo.list_chat_ids = _missing_list_chat_ids  # type: ignore[method-assign]
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
    assert "[BT 订阅扫描 chat 列表结果缺失]" in captured.out
    assert "bt subscription chat list result missing" in captured.out
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
                _ADULT_QUERY,
                "",
                "adult",
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
    assert "[BT 订阅扫描 chat 列表记录损坏]" in captured.out
    assert "[处理建议]" in captured.out
    assert "bt_subscription_item chat identity corrupted in chat list after read" in captured.out


def test_bt_subscription_scheduler_tick_warns_when_last_seen_update_raises(tmp_path: Path, capsys) -> None:
    database = _make_database(tmp_path)
    repo = BtSubscriptionRepo(database)
    created = repo.add_item(chat_id=1001, title=_ADULT_QUERY, year="", media_kind="adult")
    assert created is not None

    def _crash_update_last_seen(**_: object) -> bool:
        raise sqlite3.OperationalError("db down")

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
    repo.add_item(chat_id=1001, title=_ADULT_QUERY, year="", media_kind="adult")
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


def _make_bt_subscription_item(
    *,
    item_id: int,
    title: str,
    year: str,
    media_kind: str,
    last_seen_title: str = "",
) -> BtSubscriptionItem:
    return BtSubscriptionItem(
        item_id=item_id,
        chat_id=1001,
        title=title,
        year=year,
        media_kind=media_kind,
        last_seen_source="https://example.com/item.torrent" if last_seen_title else "",
        last_seen_title=last_seen_title,
        created_at="2026-04-19 00:00:00",
        updated_at="2026-04-19 00:00:00",
    )

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

from app.bot.execution_runtime import bt_subscription_policy_action
from app.bot.private_chat_bt_subscription_runtime import (
    BT_SUBSCRIPTION_CAPABILITY_UNAVAILABLE_TEXT,
    BT_SUBSCRIPTION_CAPABILITY_UNAVAILABLE_TEXT_BOT_DATA_KEY,
    handle_bt_subscription_query,
)
from app.bot import telegram_bot as tg
from app.config import DownloaderInstanceConfig, DownloaderRoleBinding
from app.db.bt_subscription_repo import BtSubscriptionRepo
from app.db.sqlite import SqliteDatabase
from app.services.add_to_downloader import AddToDownloaderService
from app.services.bt_subscription_command import parse_bt_subscription_query
from app.services.manage_bt_subscription import (
    BtSubscriptionDispatchContext,
    ManageBtSubscriptionService,
)
from app.services.search_media import SearchMediaService


class _ExecutionGate:
    def __init__(self) -> None:
        self.actions: list[str] = []

    async def run(self, action: str, callback):
        self.actions.append(action)
        return await callback()


async def _fake_search(_: str) -> list[dict[str, object]]:
    return []


def _make_database(tmp_path: Path) -> SqliteDatabase:
    database = SqliteDatabase(str(tmp_path / "bt_subscription.db"))
    database.initialize()
    return database


def _build_bt_subscription_service(tmp_path: Path) -> ManageBtSubscriptionService:
    search_service = SearchMediaService(_fake_search)
    add_service = AddToDownloaderService(search_service, AsyncMock())
    return ManageBtSubscriptionService(
        bt_subscription_repo=BtSubscriptionRepo(_make_database(tmp_path)),
        search_func=_fake_search,
        add_to_downloader_service=add_service,
    )


def test_handle_bt_subscription_query_returns_false_for_other_queries() -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()

    handled = asyncio.run(
        handle_bt_subscription_query(
            query="dune",
            bot_data={},
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            user_id=2001,
            tg=tg,
        )
    )

    assert handled is False
    assert execution_gate.actions == []
    reply_func.assert_not_awaited()


def test_handle_bt_subscription_query_routes_to_service(tmp_path: Path) -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()
    bt_subscription_service = _build_bt_subscription_service(tmp_path)

    handled = asyncio.run(
        handle_bt_subscription_query(
            query="btsub add anime 葬送的芙莉莲 2023",
            bot_data={tg.MANAGE_BT_SUBSCRIPTION_SERVICE_KEY: bt_subscription_service},
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            user_id=2001,
            tg=tg,
        )
    )

    assert handled is True
    command = parse_bt_subscription_query("btsub add anime 葬送的芙莉莲 2023")
    assert command is not None
    assert execution_gate.actions == [bt_subscription_policy_action(command)]
    reply_func.assert_awaited_once()
    sent_text = reply_func.await_args.args[0]
    assert "已加入 BT 订阅" in sent_text
    assert "葬送的芙莉莲" in sent_text


def test_handle_bt_subscription_query_run_uses_bound_downloader_context(tmp_path: Path) -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()
    bt_subscription_service = _build_bt_subscription_service(tmp_path)
    bt_subscription_service.run_once = AsyncMock(return_value="BT 订阅扫描完成：共扫描 0 条，当前没有新资源。")

    handled = asyncio.run(
        handle_bt_subscription_query(
            query="btsub run",
            bot_data={
                tg.MANAGE_BT_SUBSCRIPTION_SERVICE_KEY: bt_subscription_service,
                tg.DOWNLOADER_ROLE_BINDING_KEY: DownloaderRoleBinding(pt_downloader="", bt_downloader="bt"),
                tg.DOWNLOADER_INSTANCES_KEY: (
                    DownloaderInstanceConfig(
                        name="bt",
                        downloader_type="qbittorrent",
                        base_url="http://127.0.0.1:18098",
                        download_dir="/downloads/bt",
                    ),
                ),
            },
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            user_id=2001,
            tg=tg,
        )
    )

    assert handled is True
    command = parse_bt_subscription_query("btsub run")
    assert command is not None
    assert execution_gate.actions == [bt_subscription_policy_action(command)]
    bt_subscription_service.run_once.assert_awaited_once_with(
        chat_id=1001,
        user_id=2001,
        dispatch_context=BtSubscriptionDispatchContext(
            downloader_name="bt",
            downloader_type="qbittorrent",
            download_dir="/downloads/bt",
        ),
    )
    reply_func.assert_awaited_once_with("BT 订阅扫描完成：共扫描 0 条，当前没有新资源。")


def test_handle_bt_subscription_query_replies_service_not_ready_when_missing_service() -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()

    handled = asyncio.run(
        handle_bt_subscription_query(
            query="btsub list",
            bot_data={},
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            user_id=2001,
            tg=tg,
        )
    )

    assert handled is True
    assert execution_gate.actions == []
    reply_func.assert_awaited_once_with(tg.SERVICE_NOT_READY_TEXT)


def test_handle_bt_subscription_query_run_replies_explicit_unavailable_text_when_subscription_scan_is_disabled(
    tmp_path: Path,
) -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()
    bt_subscription_service = _build_bt_subscription_service(tmp_path)

    handled = asyncio.run(
        handle_bt_subscription_query(
            query="btsub run",
            bot_data={
                tg.MANAGE_BT_SUBSCRIPTION_SERVICE_KEY: bt_subscription_service,
                BT_SUBSCRIPTION_CAPABILITY_UNAVAILABLE_TEXT_BOT_DATA_KEY: (
                    BT_SUBSCRIPTION_CAPABILITY_UNAVAILABLE_TEXT
                ),
            },
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            user_id=2001,
            tg=tg,
        )
    )

    assert handled is True
    assert execution_gate.actions == []
    reply_func.assert_awaited_once_with(BT_SUBSCRIPTION_CAPABILITY_UNAVAILABLE_TEXT)


def test_handle_bt_subscription_query_list_still_routes_when_subscription_scan_is_disabled(
    tmp_path: Path,
) -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()
    bt_subscription_service = _build_bt_subscription_service(tmp_path)

    handled = asyncio.run(
        handle_bt_subscription_query(
            query="btsub list",
            bot_data={
                tg.MANAGE_BT_SUBSCRIPTION_SERVICE_KEY: bt_subscription_service,
                BT_SUBSCRIPTION_CAPABILITY_UNAVAILABLE_TEXT_BOT_DATA_KEY: (
                    BT_SUBSCRIPTION_CAPABILITY_UNAVAILABLE_TEXT
                ),
            },
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            user_id=2001,
            tg=tg,
        )
    )

    assert handled is True
    command = parse_bt_subscription_query("btsub list")
    assert command is not None
    assert execution_gate.actions == [bt_subscription_policy_action(command)]
    reply_func.assert_awaited_once_with("BT 订阅清单为空。")


def test_handle_bt_subscription_query_add_still_routes_when_subscription_scan_is_disabled(
    tmp_path: Path,
) -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()
    bt_subscription_service = _build_bt_subscription_service(tmp_path)

    handled = asyncio.run(
        handle_bt_subscription_query(
            query="btsub add anime 葬送的芙莉莲 2023",
            bot_data={
                tg.MANAGE_BT_SUBSCRIPTION_SERVICE_KEY: bt_subscription_service,
                BT_SUBSCRIPTION_CAPABILITY_UNAVAILABLE_TEXT_BOT_DATA_KEY: (
                    BT_SUBSCRIPTION_CAPABILITY_UNAVAILABLE_TEXT
                ),
            },
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            user_id=2001,
            tg=tg,
        )
    )

    assert handled is True
    command = parse_bt_subscription_query("btsub add anime 葬送的芙莉莲 2023")
    assert command is not None
    assert execution_gate.actions == [bt_subscription_policy_action(command)]
    reply_func.assert_awaited_once()
    assert "已加入 BT 订阅" in reply_func.await_args.args[0]


def test_handle_bt_subscription_query_remove_still_routes_when_subscription_scan_is_disabled(
    tmp_path: Path,
) -> None:
    bt_subscription_service = _build_bt_subscription_service(tmp_path)
    bt_subscription_service.handle(
        parse_bt_subscription_query("btsub add anime 葬送的芙莉莲 2023"),
        chat_id=1001,
    )
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()

    handled = asyncio.run(
        handle_bt_subscription_query(
            query="btsub remove 1",
            bot_data={
                tg.MANAGE_BT_SUBSCRIPTION_SERVICE_KEY: bt_subscription_service,
                BT_SUBSCRIPTION_CAPABILITY_UNAVAILABLE_TEXT_BOT_DATA_KEY: (
                    BT_SUBSCRIPTION_CAPABILITY_UNAVAILABLE_TEXT
                ),
            },
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            user_id=2001,
            tg=tg,
        )
    )

    assert handled is True
    command = parse_bt_subscription_query("btsub remove 1")
    assert command is not None
    assert execution_gate.actions == [bt_subscription_policy_action(command)]
    reply_func.assert_awaited_once_with("已删除 BT 订阅条目：1")


def test_handle_bt_subscription_query_clear_still_routes_when_subscription_scan_is_disabled(
    tmp_path: Path,
) -> None:
    bt_subscription_service = _build_bt_subscription_service(tmp_path)
    bt_subscription_service.handle(
        parse_bt_subscription_query("btsub add anime 葬送的芙莉莲 2023"),
        chat_id=1001,
    )
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()

    handled = asyncio.run(
        handle_bt_subscription_query(
            query="btsub clear",
            bot_data={
                tg.MANAGE_BT_SUBSCRIPTION_SERVICE_KEY: bt_subscription_service,
                BT_SUBSCRIPTION_CAPABILITY_UNAVAILABLE_TEXT_BOT_DATA_KEY: (
                    BT_SUBSCRIPTION_CAPABILITY_UNAVAILABLE_TEXT
                ),
            },
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            user_id=2001,
            tg=tg,
        )
    )

    assert handled is True
    command = parse_bt_subscription_query("btsub clear")
    assert command is not None
    assert execution_gate.actions == [bt_subscription_policy_action(command)]
    reply_func.assert_awaited_once_with("已清空 BT 订阅清单，共删除 1 条。")


def test_handle_bt_subscription_query_run_replies_config_missing_when_binding_points_to_unknown_instance(
    tmp_path: Path,
) -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()
    bt_subscription_service = _build_bt_subscription_service(tmp_path)

    handled = asyncio.run(
        handle_bt_subscription_query(
            query="btsub run",
            bot_data={
                tg.MANAGE_BT_SUBSCRIPTION_SERVICE_KEY: bt_subscription_service,
                tg.DOWNLOADER_ROLE_BINDING_KEY: DownloaderRoleBinding(pt_downloader="", bt_downloader="missing"),
                tg.DOWNLOADER_INSTANCES_KEY: (),
            },
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            user_id=2001,
            tg=tg,
        )
    )

    assert handled is True
    assert execution_gate.actions == []
    reply_func.assert_awaited_once_with("下载器角色 BT 绑定的实例不存在：missing。请检查配置后重试。")

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

from app.bot import telegram_bot as tg
from app.bot.execution_runtime import watchlist_policy_action
from app.bot.private_chat_watchlist_runtime import handle_watchlist_query
from app.db.bt_subscription_repo import BtSubscriptionRepo
from app.db.sqlite import SqliteDatabase
from app.db.watchlist_repo import WatchlistRepo
from app.services.manage_watchlist import ManageWatchlistService


class _ExecutionGate:
    def __init__(self) -> None:
        self.actions: list[str] = []

    async def run(self, action: str, callback):
        self.actions.append(action)
        return await callback()


def _make_database(tmp_path: Path) -> SqliteDatabase:
    database = SqliteDatabase(str(tmp_path / "watchlist.db"))
    database.initialize()
    return database


def test_handle_watchlist_query_returns_false_for_other_queries() -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()

    handled = asyncio.run(
        handle_watchlist_query(
            query="dune",
            bot_data={},
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            tg=tg,
        )
    )

    assert handled is False
    assert execution_gate.actions == []
    reply_func.assert_not_awaited()


def test_handle_watchlist_query_routes_to_watchlist_service(tmp_path: Path) -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()
    watchlist_service = ManageWatchlistService(WatchlistRepo(_make_database(tmp_path)))

    handled = asyncio.run(
        handle_watchlist_query(
            query="watchlist add dune 2021",
            bot_data={tg.MANAGE_WATCHLIST_SERVICE_KEY: watchlist_service},
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            tg=tg,
        )
    )

    assert handled is True
    assert execution_gate.actions == [watchlist_policy_action("add")]
    reply_func.assert_awaited_once()
    sent_text = reply_func.await_args.args[0]
    assert "已加入想看" in sent_text
    assert "dune" in sent_text


def test_handle_watchlist_query_routes_list_to_read_only_policy(tmp_path: Path) -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()
    watchlist_service = ManageWatchlistService(WatchlistRepo(_make_database(tmp_path)))

    handled = asyncio.run(
        handle_watchlist_query(
            query="watchlist list",
            bot_data={tg.MANAGE_WATCHLIST_SERVICE_KEY: watchlist_service},
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            tg=tg,
        )
    )

    assert handled is True
    assert execution_gate.actions == [watchlist_policy_action("list")]
    reply_func.assert_awaited_once()


def test_handle_watchlist_query_routes_sync_to_mutation_policy(tmp_path: Path) -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()
    database = _make_database(tmp_path)
    watchlist_service = ManageWatchlistService(
        WatchlistRepo(database),
        bt_subscription_repo=BtSubscriptionRepo(database),
    )
    watchlist_service.handle(tg.parse_watchlist_query("watchlist add dune 2021"), chat_id=1001)

    handled = asyncio.run(
        handle_watchlist_query(
            query="watchlist sync",
            bot_data={tg.MANAGE_WATCHLIST_SERVICE_KEY: watchlist_service},
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            tg=tg,
        )
    )

    assert handled is True
    assert execution_gate.actions == [watchlist_policy_action("sync")]
    reply_func.assert_awaited_once()
    assert "想看清单当前只服务 PT 主线" in reply_func.await_args.args[0]


def test_handle_watchlist_query_replies_service_not_ready_when_missing_service() -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()

    handled = asyncio.run(
        handle_watchlist_query(
            query="watchlist list",
            bot_data={},
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            tg=tg,
        )
    )

    assert handled is True
    assert execution_gate.actions == []
    reply_func.assert_awaited_once_with(tg.SERVICE_NOT_READY_TEXT)

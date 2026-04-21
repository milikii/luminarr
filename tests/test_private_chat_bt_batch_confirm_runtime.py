from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from app.bot.downloader_execution_runtime import resolve_bound_downloader_execution
from app.bot.private_chat_bt_batch_confirm_runtime import handle_bt_batch_confirm_query
from app.bot import telegram_bot as tg
from app.config import DownloaderInstanceConfig, DownloaderRoleBinding
from app.services.add_to_downloader import AddToDownloaderService
from app.services.search_media import SearchMediaService


class _ExecutionGate:
    def __init__(self) -> None:
        self.actions: list[str] = []

    async def run(self, action: str, callback):
        self.actions.append(action)
        return await callback()


async def _fake_search(query: str) -> list[dict[str, object]]:
    return [
        {
            "title": f"title-{query}",
            "year": 2026,
            "quality": "1080p",
            "size": 1024,
            "indexerName": "idx",
            "downloadUrl": "https://example.com/sample.torrent",
        }
    ]


def _resolve_downloader_execution(bot_data: dict[str, object]):
    return lambda: resolve_bound_downloader_execution(
        bot_data=bot_data,
        role="bt",
        downloader_role_binding_key=tg.DOWNLOADER_ROLE_BINDING_KEY,
        downloader_instances_key=tg.DOWNLOADER_INSTANCES_KEY,
        config_missing_template=tg.DOWNLOADER_EXECUTION_CONFIG_MISSING_TEMPLATE,
    )


def test_handle_bt_batch_confirm_query_returns_false_for_other_queries() -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()

    handled = asyncio.run(
        handle_bt_batch_confirm_query(
            query="dune",
            bot_data={},
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            user_id=2001,
            channel="telegram",
            resolve_downloader_execution=lambda: (None, None),
            tg=tg,
        )
    )

    assert handled is False
    assert execution_gate.actions == []
    reply_func.assert_not_awaited()


def test_handle_bt_batch_confirm_query_replies_invalid_selection() -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()

    handled = asyncio.run(
        handle_bt_batch_confirm_query(
            query="bt批量确认 1-a",
            bot_data={},
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            user_id=2001,
            channel="telegram",
            resolve_downloader_execution=lambda: (None, None),
            tg=tg,
        )
    )

    assert handled is True
    assert execution_gate.actions == []
    reply_func.assert_awaited_once_with(
        "BT 批量确认编号格式无效：1-a\n请使用 1-3 或 2,4,6 这类范围表达。"
    )


def test_handle_bt_batch_confirm_query_routes_to_add_service() -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()
    search_service = SearchMediaService(_fake_search)
    add_service = AddToDownloaderService(search_service, AsyncMock())
    add_service.add_by_batch_selection = AsyncMock(return_value="批量下载待确认。")  # type: ignore[method-assign]
    bot_data = {
        tg.ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
        tg.DOWNLOADER_ROLE_BINDING_KEY: DownloaderRoleBinding(pt_downloader="", bt_downloader="bt"),
        tg.DOWNLOADER_INSTANCES_KEY: (
            DownloaderInstanceConfig(name="bt", downloader_type="qbittorrent", base_url="", download_dir="/downloads/bt"),
        ),
    }

    handled = asyncio.run(
        handle_bt_batch_confirm_query(
            query="bt批量确认 1-2",
            bot_data=bot_data,
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            user_id=2001,
            channel="personal_wechat",
            resolve_downloader_execution=_resolve_downloader_execution(bot_data),
            tg=tg,
        )
    )

    assert handled is True
    assert execution_gate.actions == [tg.ACTION_ADD_TO_DOWNLOADER]
    add_service.add_by_batch_selection.assert_awaited_once_with(
        1001,
        (1, 2),
        user_id=2001,
        channel="personal_wechat",
        downloader_name="bt",
        downloader_type="qbittorrent",
        download_dir="/downloads/bt",
        auto_import_enabled=False,
    )
    reply_func.assert_awaited_once_with("批量下载待确认。")


def test_handle_bt_batch_confirm_query_replies_service_not_ready_without_add_service() -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()

    handled = asyncio.run(
        handle_bt_batch_confirm_query(
            query="bt批量确认 1-2",
            bot_data={},
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            user_id=2001,
            channel="telegram",
            resolve_downloader_execution=lambda: (None, None),
            tg=tg,
        )
    )

    assert handled is True
    assert execution_gate.actions == []
    reply_func.assert_awaited_once_with(tg.SERVICE_NOT_READY_TEXT)


def test_handle_bt_batch_confirm_query_replies_config_missing_for_bound_downloader() -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()
    search_service = SearchMediaService(_fake_search)
    add_service = AddToDownloaderService(search_service, AsyncMock())
    bot_data = {
        tg.ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
        tg.DOWNLOADER_ROLE_BINDING_KEY: DownloaderRoleBinding(pt_downloader="", bt_downloader="bt"),
        tg.DOWNLOADER_INSTANCES_KEY: (),
    }

    handled = asyncio.run(
        handle_bt_batch_confirm_query(
            query="bt批量确认 1-2",
            bot_data=bot_data,
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            user_id=2001,
            channel="telegram",
            resolve_downloader_execution=_resolve_downloader_execution(bot_data),
            tg=tg,
        )
    )

    assert handled is True
    assert execution_gate.actions == []
    reply_func.assert_awaited_once_with(
        tg.DOWNLOADER_EXECUTION_CONFIG_MISSING_TEMPLATE.format(role="BT", name="bt")
    )

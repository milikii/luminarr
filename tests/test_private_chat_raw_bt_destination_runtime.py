from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from app.bot import telegram_bot as tg
from app.bot.private_chat_raw_bt_destination_runtime import handle_raw_bt_destination_follow_up
from app.bot.raw_bt_destination_runtime import RawBtDestinationPending
from app.config import RawBtDestinationOption
from app.services.add_to_downloader import AddToDownloaderService
from app.services.search_media import SearchMediaService


async def _fake_search(_: str) -> list[dict[str, object]]:
    return []


def test_handle_raw_bt_destination_follow_up_returns_false_without_pending() -> None:
    reply_func = AsyncMock()

    handled = asyncio.run(
        handle_raw_bt_destination_follow_up(
            bot_data={},
            reply_func=reply_func,
            query="1",
            chat_id=1001,
            user_id=2001,
            resolve_downloader_execution=lambda: (None, None),
            tg=tg,
        )
    )

    assert handled is False
    reply_func.assert_not_awaited()


def test_handle_raw_bt_destination_follow_up_selection_succeeds() -> None:
    reply_func = AsyncMock()
    add_service = AddToDownloaderService(SearchMediaService(_fake_search), AsyncMock())

    handled = asyncio.run(
        handle_raw_bt_destination_follow_up(
            bot_data={
                tg.ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
                "raw_bt_destination_pending_by_chat": {
                    1001: RawBtDestinationPending(
                        options=(
                            RawBtDestinationOption(
                                key="downloads",
                                label="下载目录",
                                target_dir="/data/raw/downloads",
                            ),
                            RawBtDestinationOption(
                                key="archive",
                                label="归档目录",
                                target_dir="/data/raw/archive",
                            ),
                        ),
                        source="下载这个 BT",
                    )
                },
            },
            reply_func=reply_func,
            query="2",
            chat_id=1001,
            user_id=2001,
            resolve_downloader_execution=lambda: (None, None),
            tg=tg,
        )
    )

    assert handled is True
    sent_text = reply_func.await_args.args[0]
    assert "已记录 raw_bt 目标目录。" in sent_text
    assert "目录键: archive" in sent_text
    assert "目标路径: /data/raw/archive" in sent_text
    assert "当前还缺少实际的磁力链接" in sent_text


def test_handle_raw_bt_destination_follow_up_replies_service_not_ready_without_add_service() -> None:
    reply_func = AsyncMock()

    handled = asyncio.run(
        handle_raw_bt_destination_follow_up(
            bot_data={
                "raw_bt_destination_pending_by_chat": {
                    1001: RawBtDestinationPending(
                        options=(
                            RawBtDestinationOption(
                                key="downloads",
                                label="下载目录",
                                target_dir="/data/raw/downloads",
                            ),
                        ),
                        source="下载这个 BT",
                    )
                }
            },
            reply_func=reply_func,
            query="1",
            chat_id=1001,
            user_id=2001,
            resolve_downloader_execution=lambda: (None, None),
            tg=tg,
        )
    )

    assert handled is True
    reply_func.assert_awaited_once_with(tg.SERVICE_NOT_READY_TEXT)

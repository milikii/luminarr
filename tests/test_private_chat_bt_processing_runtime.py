from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from app.bot import telegram_bot as tg
from app.bot.private_chat_bt_processing_runtime import handle_bt_processing_path_follow_up
from app.config import RawBtDestinationOption


def test_handle_bt_processing_path_follow_up_returns_false_without_pending() -> None:
    reply_func = AsyncMock()

    handled = asyncio.run(
        handle_bt_processing_path_follow_up(
            bot_data={},
            reply_func=reply_func,
            chat_id=1001,
            bt_processing_path_pending=False,
            bt_processing_path=None,
            bt_processing_shortcut=None,
            tg=tg,
        )
    )

    assert handled is False
    reply_func.assert_not_awaited()


def test_handle_bt_processing_path_follow_up_routes_media_import_choice_to_classification_prompt() -> None:
    reply_func = AsyncMock()

    handled = asyncio.run(
        handle_bt_processing_path_follow_up(
            bot_data={"bt_processing_path_pending_by_chat": {1001: "magnet:?xt=urn:btih:abcdef1234567890"}},
            reply_func=reply_func,
            chat_id=1001,
            bt_processing_path_pending=True,
            bt_processing_path="media_import",
            bt_processing_shortcut=None,
            tg=tg,
        )
    )

    assert handled is True
    reply_func.assert_awaited_once_with(tg.BT_CLASSIFICATION_PROMPT_TEXT)


def test_handle_bt_processing_path_follow_up_routes_pure_bt_choice_to_destination_prompt() -> None:
    reply_func = AsyncMock()

    handled = asyncio.run(
        handle_bt_processing_path_follow_up(
            bot_data={
                "bt_processing_path_pending_by_chat": {1001: "magnet:?xt=urn:btih:abcdef1234567890"},
                tg.RAW_BT_DESTINATION_OPTIONS_KEY: (
                    RawBtDestinationOption(
                        key="downloads",
                        label="下载目录",
                        target_dir="/data/raw/downloads",
                    ),
                ),
            },
            reply_func=reply_func,
            chat_id=1001,
            bt_processing_path_pending=True,
            bt_processing_path="pure_bt",
            bt_processing_shortcut=None,
            tg=tg,
        )
    )

    assert handled is True
    sent_text = reply_func.await_args.args[0]
    assert "请选择预设目标目录：" in sent_text
    assert "1. 下载目录 [downloads] -> /data/raw/downloads" in sent_text


def test_handle_bt_processing_path_follow_up_routes_legacy_movie_shortcut_to_tmdb_prompt() -> None:
    reply_func = AsyncMock()

    handled = asyncio.run(
        handle_bt_processing_path_follow_up(
            bot_data={"bt_processing_path_pending_by_chat": {1001: "magnet:?xt=urn:btih:abcdef1234567890"}},
            reply_func=reply_func,
            chat_id=1001,
            bt_processing_path_pending=True,
            bt_processing_path=None,
            bt_processing_shortcut=("media_import", "movie"),
            tg=tg,
        )
    )

    assert handled is True
    sent_text = reply_func.await_args.args[0]
    assert "已记录本次 BT 分类：电影（movie）。" in sent_text
    assert "请继续发送片名，可带年份" in sent_text


def test_handle_bt_processing_path_follow_up_replies_service_not_ready_without_pending_source() -> None:
    reply_func = AsyncMock()

    handled = asyncio.run(
        handle_bt_processing_path_follow_up(
            bot_data={},
            reply_func=reply_func,
            chat_id=1001,
            bt_processing_path_pending=True,
            bt_processing_path="media_import",
            bt_processing_shortcut=None,
            tg=tg,
        )
    )

    assert handled is True
    reply_func.assert_awaited_once_with(tg.SERVICE_NOT_READY_TEXT)

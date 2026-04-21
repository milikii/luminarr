from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from app.bot import telegram_bot as tg
from app.bot.private_chat_bt_classification_runtime import handle_bt_classification_follow_up


def test_handle_bt_classification_follow_up_returns_false_without_pending() -> None:
    reply_func = AsyncMock()

    handled = asyncio.run(
        handle_bt_classification_follow_up(
            bot_data={},
            reply_func=reply_func,
            chat_id=1001,
            bt_classification_pending=False,
            bt_classification=None,
            tg=tg,
        )
    )

    assert handled is False
    reply_func.assert_not_awaited()


def test_handle_bt_classification_follow_up_routes_movie_choice_to_tmdb_prompt() -> None:
    reply_func = AsyncMock()

    handled = asyncio.run(
        handle_bt_classification_follow_up(
            bot_data={"bt_classification_pending_by_chat": {1001: "magnet:?xt=urn:btih:abcdef1234567890"}},
            reply_func=reply_func,
            chat_id=1001,
            bt_classification_pending=True,
            bt_classification="movie",
            tg=tg,
        )
    )

    assert handled is True
    sent_text = reply_func.await_args.args[0]
    assert "已记录本次 BT 分类：电影（movie）。" in sent_text
    assert "请继续发送片名，可带年份" in sent_text


def test_handle_bt_classification_follow_up_routes_series_choice_to_tmdb_prompt() -> None:
    reply_func = AsyncMock()

    handled = asyncio.run(
        handle_bt_classification_follow_up(
            bot_data={"bt_classification_pending_by_chat": {1001: "magnet:?xt=urn:btih:abcdef1234567890"}},
            reply_func=reply_func,
            chat_id=1001,
            bt_classification_pending=True,
            bt_classification="series",
            tg=tg,
        )
    )

    assert handled is True
    sent_text = reply_func.await_args.args[0]
    assert "已记录本次 BT 分类：剧集（series）。" in sent_text
    assert "请继续发送片名，可带年份" in sent_text


def test_handle_bt_classification_follow_up_replies_service_not_ready_without_pending_source() -> None:
    reply_func = AsyncMock()

    handled = asyncio.run(
        handle_bt_classification_follow_up(
            bot_data={},
            reply_func=reply_func,
            chat_id=1001,
            bt_classification_pending=True,
            bt_classification="movie",
            tg=tg,
        )
    )

    assert handled is True
    reply_func.assert_awaited_once_with(tg.SERVICE_NOT_READY_TEXT)

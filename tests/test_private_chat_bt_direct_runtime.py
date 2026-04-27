from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.bot.private_chat_bt_direct_runtime import handle_bt_direct_intent_query
from app.bot import telegram_bot as tg
from app.db.bt_pending_repo import BtPendingRepo
from app.db.sqlite import SqliteDatabase


def _make_database(tmp_path: Path) -> SqliteDatabase:
    database = SqliteDatabase(str(tmp_path / "bt_direct.db"))
    database.initialize()
    return database


def test_handle_bt_direct_intent_query_returns_false_for_other_queries() -> None:
    reply_func = AsyncMock()

    handled = asyncio.run(
        handle_bt_direct_intent_query(
            query="dune",
            bot_data={},
            reply_func=reply_func,
            chat_id=1001,
            tg=tg,
        )
    )

    assert handled is False
    reply_func.assert_not_awaited()


def test_handle_bt_direct_intent_query_prompts_for_processing_path() -> None:
    reply_func = AsyncMock()

    handled = asyncio.run(
        handle_bt_direct_intent_query(
            query="magnet:?xt=urn:btih:abcdef1234567890",
            bot_data={},
            reply_func=reply_func,
            chat_id=1001,
            tg=tg,
        )
    )

    assert handled is True
    reply_func.assert_awaited_once_with(tg.BT_PROCESSING_PATH_PROMPT_TEXT)
    sent_text = reply_func.await_args.args[0]
    assert "观影 PT 链 / BT 成人链" in sent_text
    assert "按观影资源流程处理 / 按成人 BT 归档流程处理" in sent_text


def test_handle_bt_direct_intent_query_replies_service_not_ready_when_persist_fails(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class _FailingPendingRepo(BtPendingRepo):
        def upsert_pending(self, *, chat_id: int, stage: str, payload_json: str = "") -> None:
            raise sqlite3.OperationalError("db down")

    reply_func = AsyncMock()

    handled = asyncio.run(
        handle_bt_direct_intent_query(
            query="magnet:?xt=urn:btih:abcdef1234567890",
            bot_data={tg.BT_PENDING_REPO_KEY: _FailingPendingRepo(_make_database(tmp_path))},
            reply_func=reply_func,
            chat_id=1001,
            tg=tg,
        )
    )
    captured = capsys.readouterr()

    assert handled is True
    reply_func.assert_awaited_once_with(tg.SERVICE_NOT_READY_TEXT)
    assert "[BT 待处理持久化失败]" in captured.out
    assert "stage=processing_path" in captured.out


def test_handle_bt_direct_intent_query_replies_service_not_ready_when_clear_fails(
    capsys: pytest.CaptureFixture[str],
) -> None:
    class _FailingPendingRepo(BtPendingRepo):
        def clear_pending(self, *, chat_id: int, expected_stage: str | None = None) -> bool:
            if expected_stage == "processing_path":
                raise sqlite3.OperationalError("db down")
            return False

    reply_func = AsyncMock()

    handled = asyncio.run(
        handle_bt_direct_intent_query(
            query="magnet:?xt=urn:btih:abcdef1234567890",
            bot_data={
                tg.BT_PENDING_REPO_KEY: _FailingPendingRepo(SqliteDatabase(":memory:")),
                "bt_processing_path_pending_by_chat": {1001: "magnet:?xt=urn:btih:old"},
            },
            reply_func=reply_func,
            chat_id=1001,
            tg=tg,
        )
    )
    captured = capsys.readouterr()

    assert handled is True
    reply_func.assert_awaited_once_with(tg.SERVICE_NOT_READY_TEXT)
    assert "[BT 待处理清理失败]" in captured.out
    assert "stage=processing_path" in captured.out

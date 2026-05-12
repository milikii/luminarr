from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from app.bot import telegram_bot as tg
from app.bot.bt_processing_path_runtime import set_bt_processing_path_pending
from app.bot.private_chat_frustration_runtime import handle_frustration_query
from app.db.bt_pending_repo import BtPendingRepo
from app.db.job_repo import JobRepo
from app.db.sqlite import SqliteDatabase
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


def _make_database(tmp_path: Path) -> SqliteDatabase:
    database = SqliteDatabase(str(tmp_path / "frustration.db"))
    database.initialize()
    return database


def test_handle_frustration_query_returns_false_for_other_queries() -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()

    handled = asyncio.run(
        handle_frustration_query(
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


def test_handle_frustration_query_cancels_pending_add_via_job_repo(tmp_path: Path) -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()
    job_repo = JobRepo(_make_database(tmp_path))
    job_repo.upsert_downloader_job_pending(
        chat_id=1001,
        user_id=2001,
        task_ref="1",
        task_id="selection:1",
        task_hash="hash-1",
        payload_json="{}",
    )
    add_service = AddToDownloaderService(SearchMediaService(_fake_search), AsyncMock())
    add_service.cancel_pending_add = Mock(return_value="已取消当前下载确认。请重新发送序号。")  # type: ignore[method-assign]

    handled = asyncio.run(
        handle_frustration_query(
            query="取消",
            bot_data={
                tg.JOB_REPO_KEY: job_repo,
                tg.ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
            },
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            tg=tg,
        )
    )

    assert handled is True
    assert execution_gate.actions == [tg.ACTION_CANCEL_PENDING_APPROVAL]
    add_service.cancel_pending_add.assert_called_once_with(1001)
    reply_func.assert_awaited_once_with("已取消当前下载确认。请重新发送序号。")


def test_handle_frustration_query_resets_search_clarification() -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()
    search_service = SearchMediaService(_fake_search)
    search_service._clarification_pending_by_chat[1001] = "dune"

    handled = asyncio.run(
        handle_frustration_query(
            query="取消",
            bot_data={tg.SEARCH_SERVICE_KEY: search_service},
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            tg=tg,
        )
    )

    assert handled is True
    assert execution_gate.actions == [tg.ACTION_RESET_CLARIFICATION]
    reply_func.assert_awaited_once_with(tg.CLARIFICATION_RESET_TEXT)


def test_handle_frustration_query_clears_bt_processing_path_pending(tmp_path: Path) -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()
    database = _make_database(tmp_path)
    bot_data = {tg.BT_PENDING_REPO_KEY: BtPendingRepo(database)}
    assert set_bt_processing_path_pending(
        bot_data=bot_data,
        chat_id=1001,
        source="magnet:?xt=urn:btih:abcdef1234567890",
        bt_pending_repo_key=tg.BT_PENDING_REPO_KEY,
    )

    handled = asyncio.run(
        handle_frustration_query(
            query="取消",
            bot_data=bot_data,
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            tg=tg,
        )
    )

    assert handled is True
    assert execution_gate.actions == []
    reply_func.assert_awaited_once_with(tg.BT_PROCESSING_PATH_CANCELLED_TEXT)


def test_handle_frustration_query_logs_pending_job_lookup_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()
    job_repo = JobRepo(_make_database(tmp_path))
    job_repo.get_latest_pending_job = Mock(side_effect=sqlite3.OperationalError("sqlite busy"))  # type: ignore[method-assign]

    handled = asyncio.run(
        handle_frustration_query(
            query="取消",
            bot_data={tg.JOB_REPO_KEY: job_repo},
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            tg=tg,
        )
    )
    captured = capsys.readouterr()

    assert handled is True
    assert execution_gate.actions == []
    reply_func.assert_awaited_once_with(tg.SERVICE_NOT_READY_TEXT)
    assert "[待处理任务查询失败]" in captured.out
    assert "chat_id=1001" in captured.out
    assert "sqlite busy" in captured.out

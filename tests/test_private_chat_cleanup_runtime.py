from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock

from app.bot import telegram_bot as tg
from app.bot.private_chat_cleanup_runtime import handle_cleanup_query
from app.db.job_event_repo import JobEventRepo
from app.db.sqlite import SqliteDatabase
from app.services.cleanup_downloaded_source import CleanupDownloadedSourceService


class _ExecutionGate:
    def __init__(self) -> None:
        self.actions: list[str] = []

    async def run(self, action: str, callback):
        self.actions.append(action)
        return await callback()


def _make_database(tmp_path: Path) -> SqliteDatabase:
    database = SqliteDatabase(str(tmp_path / "cleanup.db"))
    database.initialize()
    return database


def test_handle_cleanup_query_returns_false_for_other_queries() -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()

    handled = asyncio.run(
        handle_cleanup_query(
            query="dune",
            bot_data={},
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            user_id=2001,
            channel="telegram",
            tg=tg,
        )
    )

    assert handled is False
    assert execution_gate.actions == []
    reply_func.assert_not_awaited()


def test_handle_cleanup_query_routes_to_cleanup_service(
    tmp_path: Path,
    capsys,
) -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()
    cleanup_service = CleanupDownloadedSourceService(JobEventRepo(_make_database(tmp_path)))
    cleanup_service.cleanup_by_task_ref = Mock(return_value="已清理下载源资产。")

    handled = asyncio.run(
        handle_cleanup_query(
            query="cleanup hash-87",
            bot_data={tg.CLEANUP_DOWNLOADED_SOURCE_SERVICE_KEY: cleanup_service},
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            user_id=2001,
            channel="telegram",
            tg=tg,
        )
    )

    assert handled is True
    assert execution_gate.actions == [tg.ACTION_CLEANUP_DOWNLOADER_SOURCE]
    cleanup_service.cleanup_by_task_ref.assert_called_once_with("hash-87", chat_id=1001)
    reply_func.assert_awaited_once_with("已清理下载源资产。")
    captured = capsys.readouterr()
    assert "[cleanup 私聊 smoke]" in captured.out
    assert "action=cleanup" in captured.out


def test_handle_cleanup_query_routes_cleanup_inspect_to_cleanup_service(
    tmp_path: Path,
    capsys,
) -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()
    cleanup_service = CleanupDownloadedSourceService(JobEventRepo(_make_database(tmp_path)))
    cleanup_service.inspect_by_task_ref = Mock(return_value="清理预检结果。")

    handled = asyncio.run(
        handle_cleanup_query(
            query="cleanup inspect hash-87",
            bot_data={tg.CLEANUP_DOWNLOADED_SOURCE_SERVICE_KEY: cleanup_service},
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            user_id=2001,
            channel="telegram",
            tg=tg,
        )
    )

    assert handled is True
    assert execution_gate.actions == [tg.ACTION_CLEANUP_INSPECT]
    cleanup_service.inspect_by_task_ref.assert_called_once_with("hash-87", chat_id=1001)
    reply_func.assert_awaited_once_with("清理预检结果。")
    captured = capsys.readouterr()
    assert "[cleanup 私聊 smoke]" in captured.out
    assert "action=cleanup_inspect" in captured.out


def test_handle_cleanup_query_replies_service_not_ready(
    capsys,
) -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()

    handled = asyncio.run(
        handle_cleanup_query(
            query="cleanup hash-87",
            bot_data={},
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            user_id=2001,
            channel="telegram",
            tg=tg,
        )
    )

    assert handled is True
    assert execution_gate.actions == []
    reply_func.assert_awaited_once_with(tg.SERVICE_NOT_READY_TEXT)
    captured = capsys.readouterr()
    assert "[cleanup 服务未就绪]" in captured.out
    assert "动作=cleanup" in captured.out
    assert "[处理建议]" in captured.out

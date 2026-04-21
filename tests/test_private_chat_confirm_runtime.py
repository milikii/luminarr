from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.bot import telegram_bot as tg
from app.bot.private_chat_confirm_runtime import handle_confirm_query
from app.db.job_repo import JobRepo
from app.db.sqlite import SqliteDatabase
from app.services.add_to_downloader import AddToDownloaderService
from app.services.import_to_library import ImportToLibraryService
from app.services.search_media import SearchMediaService


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
    database = SqliteDatabase(str(tmp_path / "state.sqlite3"))
    database.initialize()
    return database


def _build_bot_data() -> dict[str, object]:
    search_service = SearchMediaService(_fake_search)
    add_service = AddToDownloaderService(search_service, AsyncMock())
    import_service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies")
    return {
        tg.ADD_TO_DOWNLOADER_SERVICE_KEY: add_service,
        tg.IMPORT_TO_LIBRARY_SERVICE_KEY: import_service,
    }


class _ExecutionGateStub:
    def __init__(self) -> None:
        self.run = AsyncMock(side_effect=self._run)

    async def _run(self, _action: str, handler):
        result = handler()
        if asyncio.iscoroutine(result):
            return await result
        return result


def test_handle_confirm_query_routes_workflow_add(tmp_path: Path) -> None:
    reply_text = AsyncMock()
    execution_gate = _ExecutionGateStub()
    bot_data = _build_bot_data()
    job_repo = JobRepo(_make_database(tmp_path))
    job_repo.get_job_for_chat_ref = Mock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(workflow_type=tg.WORKFLOW_ADD_TO_DOWNLOADER)
    )
    add_service = bot_data[tg.ADD_TO_DOWNLOADER_SERVICE_KEY]
    assert isinstance(add_service, AddToDownloaderService)
    add_service.confirm_add_by_task_ref = AsyncMock(return_value="下载确认成功")  # type: ignore[method-assign]

    handled = asyncio.run(
        handle_confirm_query(
            bot_data=bot_data | {tg.JOB_REPO_KEY: job_repo},
            execution_gate=execution_gate,
            reply_func=reply_text,
            confirm_ref="87",
            chat_id=1001,
            user_id=2001,
            tg=tg,
        )
    )

    assert handled is True
    execution_gate.run.assert_awaited_once()
    add_service.confirm_add_by_task_ref.assert_awaited_once_with("87", chat_id=1001, user_id=2001)
    reply_text.assert_awaited_once_with("下载确认成功")


def test_handle_confirm_query_stops_on_job_lookup_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reply_text = AsyncMock()
    execution_gate = _ExecutionGateStub()
    bot_data = _build_bot_data()
    job_repo = JobRepo(_make_database(tmp_path))
    job_repo.get_job_for_chat_ref = Mock(side_effect=RuntimeError("disk i/o error"))  # type: ignore[method-assign]

    handled = asyncio.run(
        handle_confirm_query(
            bot_data=bot_data | {tg.JOB_REPO_KEY: job_repo},
            execution_gate=execution_gate,
            reply_func=reply_text,
            confirm_ref="87",
            chat_id=1001,
            user_id=2001,
            tg=tg,
        )
    )
    captured = capsys.readouterr()

    assert handled is True
    reply_text.assert_awaited_once_with(tg.SERVICE_NOT_READY_TEXT)
    execution_gate.run.assert_not_awaited()
    assert "[确认关联任务查询失败]" in captured.out
    assert "task_ref=87" in captured.out
    assert "disk i/o error" in captured.out


def test_handle_confirm_query_falls_back_to_import_when_no_pending_add() -> None:
    reply_text = AsyncMock()
    execution_gate = _ExecutionGateStub()
    bot_data = _build_bot_data()
    add_service = bot_data[tg.ADD_TO_DOWNLOADER_SERVICE_KEY]
    import_service = bot_data[tg.IMPORT_TO_LIBRARY_SERVICE_KEY]
    assert isinstance(add_service, AddToDownloaderService)
    assert isinstance(import_service, ImportToLibraryService)
    add_service.has_pending_add = Mock(return_value=False)  # type: ignore[method-assign]
    import_service.confirm_import_by_task_ref = AsyncMock(return_value="导入确认成功")  # type: ignore[method-assign]

    handled = asyncio.run(
        handle_confirm_query(
            bot_data=bot_data,
            execution_gate=execution_gate,
            reply_func=reply_text,
            confirm_ref="hash-87",
            chat_id=1001,
            user_id=2001,
            tg=tg,
        )
    )

    assert handled is True
    add_service.has_pending_add.assert_called_once_with(1001, "hash-87")
    execution_gate.run.assert_awaited_once()
    import_service.confirm_import_by_task_ref.assert_awaited_once_with("hash-87", chat_id=1001, user_id=2001)
    reply_text.assert_awaited_once_with("导入确认成功")

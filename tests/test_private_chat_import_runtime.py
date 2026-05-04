from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from app.bot.private_chat_import_runtime import handle_import_query
from app.bot import telegram_bot as tg
from app.services.import_to_library import ImportToLibraryService


class _ExecutionGate:
    def __init__(self) -> None:
        self.actions: list[str] = []

    async def run(self, action: str, callback):
        self.actions.append(action)
        return await callback()


def test_handle_import_query_returns_false_for_other_queries() -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()

    handled = asyncio.run(
        handle_import_query(
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


def test_handle_import_query_routes_to_import_service() -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()
    import_service = ImportToLibraryService(AsyncMock(return_value=None), "/data/library/movies")
    import_service.import_by_task_ref = AsyncMock(return_value="导入成功\n\n后处理总结")

    handled = asyncio.run(
        handle_import_query(
            query="import 87",
            bot_data={tg.IMPORT_TO_LIBRARY_SERVICE_KEY: import_service},
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            user_id=2001,
            tg=tg,
        )
    )

    assert handled is True
    assert execution_gate.actions == [tg.ACTION_IMPORT_TO_LIBRARY]
    reply_func.assert_awaited_once_with("导入成功\n\n后处理总结")
    import_service.import_by_task_ref.assert_awaited_once_with("87", chat_id=1001, user_id=2001)


def test_handle_import_query_replies_service_not_ready_when_missing_service() -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()

    handled = asyncio.run(
        handle_import_query(
            query="import 87",
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

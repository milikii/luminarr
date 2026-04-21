from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from app.bot.private_chat_status_runtime import handle_status_query
from app.bot import telegram_bot as tg
from app.clients.transmission import TransmissionTaskStatus
from app.services.get_download_status import GetDownloadStatusService


class _ExecutionGate:
    def __init__(self) -> None:
        self.actions: list[str] = []

    async def run(self, action: str, callback):
        self.actions.append(action)
        return await callback()


def test_handle_status_query_returns_false_for_other_queries() -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()

    handled = asyncio.run(
        handle_status_query(
            query="dune",
            bot_data={},
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            channel="telegram",
            tg=tg,
        )
    )

    assert handled is False
    assert execution_gate.actions == []
    reply_func.assert_not_awaited()


def test_handle_status_query_routes_to_status_service() -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()
    status_service = GetDownloadStatusService(
        AsyncMock(
            return_value=TransmissionTaskStatus(
                task_id="87",
                task_hash="b305bf",
                name="Dune 1984",
                status_code=4,
                percent_done=0.5,
                rate_download=1024,
                eta_seconds=30,
            )
        )
    )

    handled = asyncio.run(
        handle_status_query(
            query="status 87",
            bot_data={tg.GET_DOWNLOAD_STATUS_SERVICE_KEY: status_service},
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            channel="personal_wechat",
            tg=tg,
        )
    )

    assert handled is True
    assert execution_gate.actions == [tg.ACTION_GET_DOWNLOAD_STATUS]
    reply_func.assert_awaited_once()
    sent_text = reply_func.await_args.args[0]
    assert sent_text.startswith("【下载状态】 ⏳")
    assert "查询对象：87" in sent_text


def test_handle_status_query_replies_service_not_ready_when_missing_service() -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()

    handled = asyncio.run(
        handle_status_query(
            query="status 87",
            bot_data={},
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            channel="telegram",
            tg=tg,
        )
    )

    assert handled is True
    assert execution_gate.actions == []
    reply_func.assert_awaited_once_with(tg.SERVICE_NOT_READY_TEXT)

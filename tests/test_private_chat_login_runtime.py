from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from app.bot.personal_wechat_login import (
    PERSONAL_WECHAT_LOGIN_SERVICE_KEY,
    PERSONAL_WECHAT_LOGIN_STARTED_TEXT,
    PersonalWeChatLoginService,
)
from app.bot.private_chat_login_runtime import handle_personal_wechat_login_query
from app.bot import telegram_bot as tg


class _ExecutionGate:
    def __init__(self) -> None:
        self.actions: list[str] = []

    async def run(self, action: str, callback):
        self.actions.append(action)
        return await callback()


def test_handle_personal_wechat_login_query_returns_false_for_other_queries() -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()

    handled = asyncio.run(
        handle_personal_wechat_login_query(
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


def test_handle_personal_wechat_login_query_starts_login_when_ready(tmp_path: Path) -> None:
    async def start_login_func(*, api_base_url: str, force: bool = False) -> object:
        return SimpleNamespace(
            qrcode_url="https://wx.example/qrcode.png",
            session_key="session-1",
            message="ok",
        )

    async def wait_login_func(*, session_key: str, api_base_url: str, verbose: bool) -> object:
        return SimpleNamespace(
            connected=True,
            account_id="wx-account-runtime",
            bot_token="bot-token-runtime",
            base_url="https://ilinkai.weixin.qq.com",
            user_id="wx-user-runtime",
        )

    def build_qr_artifact(_: str) -> object:
        qr_dir = tmp_path / "runtime-login-qr"
        qr_dir.mkdir()
        file_path = qr_dir / "wechat-login.png"
        file_path.write_bytes(b"png")
        return SimpleNamespace(dir_path=qr_dir, file_path=file_path)

    service = PersonalWeChatLoginService(
        start_login_func=start_login_func,
        wait_login_func=wait_login_func,
        save_account_func=Mock(),
        register_account_func=Mock(),
        clear_stale_accounts_func=Mock(),
        close_client_func=AsyncMock(),
        qr_artifact_builder=build_qr_artifact,
    )
    reply_func = AsyncMock()
    send_media = AsyncMock(return_value="document-ok")
    send_text = AsyncMock(return_value="message-ok")
    execution_gate = _ExecutionGate()

    handled = asyncio.run(
        handle_personal_wechat_login_query(
            query="微信登录",
            bot_data={
                PERSONAL_WECHAT_LOGIN_SERVICE_KEY: service,
                tg.TELEGRAM_SEND_MEDIA_FUNC_KEY: send_media,
                tg.TELEGRAM_SEND_TEXT_FUNC_KEY: send_text,
            },
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            tg=tg,
        )
    )
    if service._wait_task is not None:
        asyncio.run(service._wait_task)

    assert handled is True
    assert execution_gate.actions == [tg.ACTION_PERSONAL_WECHAT_LOGIN]
    reply_func.assert_awaited_once_with(PERSONAL_WECHAT_LOGIN_STARTED_TEXT)
    send_media.assert_awaited_once()
    send_text.assert_awaited_once_with(
        chat_id=1001,
        text="personal WeChat 登录成功。\n账号 ID: wx-account-runtime\n用户 ID: wx-user-runtime",
    )


def test_handle_personal_wechat_login_query_replies_service_not_ready_when_missing_sender() -> None:
    reply_func = AsyncMock()
    execution_gate = _ExecutionGate()

    handled = asyncio.run(
        handle_personal_wechat_login_query(
            query="微信登录",
            bot_data={},
            execution_gate=execution_gate,
            reply_func=reply_func,
            chat_id=1001,
            tg=tg,
        )
    )

    assert handled is True
    assert execution_gate.actions == []
    reply_func.assert_awaited_once_with(tg.SERVICE_NOT_READY_TEXT)

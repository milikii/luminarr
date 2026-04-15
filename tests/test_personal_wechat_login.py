from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from app.bot.personal_wechat_login import (
    PERSONAL_WECHAT_LOGIN_BUSY_TEXT,
    PERSONAL_WECHAT_LOGIN_QR_CAPTION,
    PERSONAL_WECHAT_LOGIN_REUSED_TEXT,
    PERSONAL_WECHAT_LOGIN_STARTED_TEXT,
    PersonalWeChatLoginService,
    parse_personal_wechat_login_query,
)


def test_parse_personal_wechat_login_query() -> None:
    assert parse_personal_wechat_login_query("微信登录")
    assert not parse_personal_wechat_login_query("微信 登录")
    assert not parse_personal_wechat_login_query("dune")


def test_personal_wechat_login_service_starts_login_sends_qr_and_notifies_success(tmp_path: Path) -> None:
    async def start_login_func(**_: object) -> object:
        return SimpleNamespace(
            qrcode_url="https://login.example/qr/123",
            session_key="session-123",
            message="ok",
        )

    async def wait_login_func(**_: object) -> object:
        return SimpleNamespace(
            connected=True,
            account_id="wx-account-1",
            bot_token="bot-token-1",
            base_url="https://ilinkai.weixin.qq.com",
            user_id="wx-user-1",
        )

    captured_paths: list[Path] = []

    async def send_media(chat_id: int, file_path: str | Path, caption: str | None = None) -> object:
        resolved_path = Path(file_path)
        assert chat_id == 1001
        assert caption == PERSONAL_WECHAT_LOGIN_QR_CAPTION
        assert resolved_path.is_file()
        assert resolved_path.suffix == ".png"
        captured_paths.append(resolved_path)
        return "document-ok"

    send_text = AsyncMock()
    save_account = Mock()
    register_account = Mock()
    clear_stale_accounts = Mock()

    def build_qr_artifact(_: str):
        qr_dir = tmp_path / "qr-artifact"
        qr_dir.mkdir()
        file_path = qr_dir / "wechat-login.png"
        file_path.write_bytes(b"png")
        return SimpleNamespace(dir_path=qr_dir, file_path=file_path)

    async def close_client() -> None:
        return None

    async def run_case() -> None:
        service = PersonalWeChatLoginService(
            start_login_func=start_login_func,
            wait_login_func=wait_login_func,
            save_account_func=save_account,
            register_account_func=register_account,
            clear_stale_accounts_func=clear_stale_accounts,
            close_client_func=close_client,
            qr_artifact_builder=build_qr_artifact,
        )

        reply = await service.start_login(
            chat_id=1001,
            send_media_func=send_media,
            send_text_func=send_text,
        )

        assert reply == PERSONAL_WECHAT_LOGIN_STARTED_TEXT
        assert service._wait_task is not None
        await service._wait_task

    asyncio.run(run_case())

    assert len(captured_paths) == 1
    assert not captured_paths[0].exists()
    save_account.assert_called_once_with(
        "wx-account-1",
        token="bot-token-1",
        base_url="https://ilinkai.weixin.qq.com",
        user_id="wx-user-1",
    )
    register_account.assert_called_once_with("wx-account-1")
    clear_stale_accounts.assert_called_once_with("wx-account-1", "wx-user-1")
    send_text.assert_awaited_once_with(
        chat_id=1001,
        text="personal WeChat 登录成功。\n账号 ID: wx-account-1\n用户 ID: wx-user-1",
    )


def test_personal_wechat_login_service_reuses_active_qr_for_same_chat(tmp_path: Path) -> None:
    release_wait = asyncio.Event()

    async def start_login_func(**_: object) -> object:
        return SimpleNamespace(
            qrcode_url="https://login.example/qr/reuse",
            session_key="session-reuse",
            message="ok",
        )

    async def wait_login_func(**_: object) -> object:
        await release_wait.wait()
        return SimpleNamespace(
            connected=True,
            account_id="wx-account-2",
            bot_token="bot-token-2",
            base_url="https://ilinkai.weixin.qq.com",
            user_id="wx-user-2",
        )

    send_media = AsyncMock(return_value="document-ok")

    def build_qr_artifact(_: str):
        qr_dir = tmp_path / "reuse-qr"
        qr_dir.mkdir(exist_ok=True)
        file_path = qr_dir / "wechat-login.png"
        file_path.write_bytes(b"png")
        return SimpleNamespace(dir_path=qr_dir, file_path=file_path)

    async def close_client() -> None:
        return None

    async def run_case() -> None:
        service = PersonalWeChatLoginService(
            start_login_func=start_login_func,
            wait_login_func=wait_login_func,
            save_account_func=Mock(),
            register_account_func=Mock(),
            clear_stale_accounts_func=Mock(),
            close_client_func=close_client,
            qr_artifact_builder=build_qr_artifact,
        )

        first_reply = await service.start_login(
            chat_id=1001,
            send_media_func=send_media,
            send_text_func=AsyncMock(),
        )
        second_reply = await service.start_login(
            chat_id=1001,
            send_media_func=send_media,
            send_text_func=AsyncMock(),
        )
        busy_reply = await service.start_login(
            chat_id=1002,
            send_media_func=send_media,
            send_text_func=AsyncMock(),
        )

        assert first_reply == PERSONAL_WECHAT_LOGIN_STARTED_TEXT
        assert second_reply == PERSONAL_WECHAT_LOGIN_REUSED_TEXT
        assert busy_reply == PERSONAL_WECHAT_LOGIN_BUSY_TEXT
        assert send_media.await_count == 2
        assert service._wait_task is not None
        release_wait.set()
        await service._wait_task

    asyncio.run(run_case())


def test_personal_wechat_login_logs_qr_cleanup_failure(tmp_path: Path, monkeypatch, capsys) -> None:
    async def start_login_func(**_: object) -> object:
        return SimpleNamespace(
            qrcode_url="https://login.example/qr/cleanup",
            session_key="session-cleanup",
            message="ok",
        )

    async def wait_login_func(**_: object) -> object:
        return SimpleNamespace(
            connected=True,
            account_id="wx-account-cleanup",
            bot_token="bot-token-cleanup",
            base_url="https://ilinkai.weixin.qq.com",
            user_id="wx-user-cleanup",
        )

    qr_dir = tmp_path / "cleanup-qr"
    qr_dir.mkdir()
    qr_file = qr_dir / "wechat-login.png"
    qr_file.write_bytes(b"png")

    def build_qr_artifact(_: str):
        return SimpleNamespace(dir_path=qr_dir, file_path=qr_file)

    original_unlink = type(qr_file).unlink

    def _raise_cleanup_failure(self: Path, *args, **kwargs) -> None:
        if self == qr_file:
            raise OSError("file busy")
        return original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(type(qr_file), "unlink", _raise_cleanup_failure)

    async def run_case() -> None:
        service = PersonalWeChatLoginService(
            start_login_func=start_login_func,
            wait_login_func=wait_login_func,
            save_account_func=Mock(),
            register_account_func=Mock(),
            clear_stale_accounts_func=Mock(),
            close_client_func=AsyncMock(),
            qr_artifact_builder=build_qr_artifact,
        )

        reply = await service.start_login(
            chat_id=1001,
            send_media_func=AsyncMock(return_value="document-ok"),
            send_text_func=AsyncMock(),
        )

        assert reply == PERSONAL_WECHAT_LOGIN_STARTED_TEXT
        assert service._wait_task is not None
        await service._wait_task

    asyncio.run(run_case())

    output = capsys.readouterr().out
    assert "[personal WeChat 二维码清理失败]" in output
    assert str(qr_file) in output
    assert "file busy" in output
    assert "[处理建议]" in output

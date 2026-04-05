from __future__ import annotations

import asyncio
import contextlib
import shutil
import tempfile
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

PERSONAL_WECHAT_LOGIN_SERVICE_KEY = "personal_wechat_login_service"
PERSONAL_WECHAT_LOGIN_QR_CAPTION = "微信登录二维码（SVG 文件）"
PERSONAL_WECHAT_LOGIN_STARTED_TEXT = (
    "已发起 personal WeChat 登录。\n"
    "二维码文件已回传到当前 Telegram 私聊，请直接打开并扫码。\n"
    "当前这一步只补登录入口，暂不接微信私聊文本命令。"
)
PERSONAL_WECHAT_LOGIN_REUSED_TEXT = (
    "当前已有进行中的 personal WeChat 登录。\n"
    "已将同一份二维码文件重新回传到当前 Telegram 私聊，请继续扫码。"
)
PERSONAL_WECHAT_LOGIN_BUSY_TEXT = "当前已有其他私聊触发的 personal WeChat 登录，请等待它完成或失败后再重试。"
PERSONAL_WECHAT_LOGIN_NOT_READY_TEXT = (
    "personal WeChat 登录未就绪，请先安装 wechat-clawbot，并确认当前环境可访问微信 iLink 服务。"
)
PERSONAL_WECHAT_LOGIN_START_FAILED_TEMPLATE = "personal WeChat 登录启动失败：{reason}\n请稍后重新发送“微信登录”重试。"
PERSONAL_WECHAT_LOGIN_RESULT_FAILED_TEMPLATE = "personal WeChat 登录未完成：{reason}\n请重新发送“微信登录”获取新二维码。"
PERSONAL_WECHAT_LOGIN_RESULT_SUCCESS_TEMPLATE = (
    "personal WeChat 登录成功。\n"
    "账号 ID: {account_id}\n"
    "用户 ID: {user_id}"
)
PERSONAL_WECHAT_LOGIN_QUERY_ALIASES = frozenset({"微信登录"})

try:
    import qrcode
    from qrcode.image.svg import SvgImage
    from wechat_clawbot.api.client import close_shared_client
    from wechat_clawbot.auth.accounts import (
        DEFAULT_BASE_URL as DEFAULT_WECHAT_API_BASE_URL,
        clear_stale_accounts_for_user_id,
        register_weixin_account_id,
        save_weixin_account,
    )
    from wechat_clawbot.auth.login_qr import start_weixin_login_with_qr, wait_for_weixin_login
except ImportError as import_error:  # pragma: no cover - exercised via availability checks
    qrcode = None
    SvgImage = None
    DEFAULT_WECHAT_API_BASE_URL = "https://ilinkai.weixin.qq.com"
    start_weixin_login_with_qr = None
    wait_for_weixin_login = None
    save_weixin_account = None
    register_weixin_account_id = None
    clear_stale_accounts_for_user_id = None
    close_shared_client = None
    _PERSONAL_WECHAT_IMPORT_ERROR = import_error
else:
    _PERSONAL_WECHAT_IMPORT_ERROR = None

TelegramSendMediaFunc = Callable[[int, str | Path, str | None], Awaitable[object]]
TelegramSendTextFunc = Callable[..., Awaitable[object]]


@dataclass(frozen=True, slots=True)
class QrArtifact:
    dir_path: Path
    file_path: Path


def parse_personal_wechat_login_query(query: str) -> bool:
    return query.strip() in PERSONAL_WECHAT_LOGIN_QUERY_ALIASES


def _build_qr_svg_artifact(qr_content: str) -> QrArtifact:
    if qrcode is None or SvgImage is None:
        raise RuntimeError("qrcode svg support is unavailable")
    qr_dir = Path(tempfile.mkdtemp(prefix="luminarr-wechat-login-"))
    qr_file_path = qr_dir / "wechat-login.svg"
    qr_code = qrcode.QRCode(border=2, box_size=8)
    qr_code.add_data(qr_content)
    qr_code.make(fit=True)
    image = qr_code.make_image(image_factory=SvgImage)
    image.save(qr_file_path)
    return QrArtifact(dir_path=qr_dir, file_path=qr_file_path)


def _cleanup_qr_artifact(artifact: QrArtifact | None) -> None:
    if artifact is None:
        return
    with contextlib.suppress(FileNotFoundError):
        artifact.file_path.unlink()
    with contextlib.suppress(FileNotFoundError):
        shutil.rmtree(artifact.dir_path)


class PersonalWeChatLoginService:
    def __init__(
        self,
        *,
        api_base_url: str = DEFAULT_WECHAT_API_BASE_URL,
        start_login_func: Callable[..., Awaitable[object]] | None = start_weixin_login_with_qr,
        wait_login_func: Callable[..., Awaitable[object]] | None = wait_for_weixin_login,
        save_account_func: Callable[..., None] | None = save_weixin_account,
        register_account_func: Callable[[str], None] | None = register_weixin_account_id,
        clear_stale_accounts_func: Callable[[str, str], None] | None = clear_stale_accounts_for_user_id,
        close_client_func: Callable[[], Awaitable[None]] | None = close_shared_client,
        qr_artifact_builder: Callable[[str], QrArtifact] = _build_qr_svg_artifact,
    ) -> None:
        self._api_base_url = api_base_url.rstrip("/") or DEFAULT_WECHAT_API_BASE_URL
        self._start_login_func = start_login_func
        self._wait_login_func = wait_login_func
        self._save_account_func = save_account_func
        self._register_account_func = register_account_func
        self._clear_stale_accounts_func = clear_stale_accounts_func
        self._close_client_func = close_client_func
        self._qr_artifact_builder = qr_artifact_builder
        self._lock = asyncio.Lock()
        self._active_chat_id: int | None = None
        self._active_qr_artifact: QrArtifact | None = None
        self._wait_task: asyncio.Task[None] | None = None

    def is_available(self) -> bool:
        return all(
            dependency is not None
            for dependency in (
                self._start_login_func,
                self._wait_login_func,
                self._save_account_func,
                self._register_account_func,
                self._close_client_func,
            )
        )

    async def start_login(
        self,
        *,
        chat_id: int,
        send_media_func: TelegramSendMediaFunc,
        send_text_func: TelegramSendTextFunc | None = None,
    ) -> str:
        if chat_id <= 0:
            return PERSONAL_WECHAT_LOGIN_NOT_READY_TEXT
        if not self.is_available():
            reason = _PERSONAL_WECHAT_IMPORT_ERROR or "wechat-clawbot dependency is missing"
            print(
                f"\033[31m[personal WeChat 登录未就绪]\033[0m 原因={reason}\n"
                "\033[33m[处理建议]\033[0m 安装 wechat-clawbot，并确认 qrcode SVG 依赖可用。"
            )
            return PERSONAL_WECHAT_LOGIN_NOT_READY_TEXT

        async with self._lock:
            if self._wait_task is not None and self._wait_task.done():
                await self._finalize_active_login_locked()

            if self._wait_task is not None and not self._wait_task.done():
                if self._active_chat_id != chat_id:
                    return PERSONAL_WECHAT_LOGIN_BUSY_TEXT
                artifact = self._active_qr_artifact
                if artifact is None or not artifact.file_path.is_file():
                    await self._finalize_active_login_locked()
                else:
                    try:
                        await send_media_func(chat_id, artifact.file_path, PERSONAL_WECHAT_LOGIN_QR_CAPTION)
                    except Exception as error:
                        print(
                            f"\033[31m[personal WeChat 二维码回传失败]\033[0m chat_id={chat_id} 原因={error}\n"
                            "\033[33m[处理建议]\033[0m 检查 Telegram 私聊是否仍有效，并确认临时二维码文件仍可读取。"
                        )
                        return PERSONAL_WECHAT_LOGIN_START_FAILED_TEMPLATE.format(reason="二维码回传失败，请查看日志")
                    return PERSONAL_WECHAT_LOGIN_REUSED_TEXT

            try:
                start_result = await self._start_login_func(
                    api_base_url=self._api_base_url,
                    force=True,
                )
            except Exception as error:
                print(
                    f"\033[31m[personal WeChat 登录启动失败]\033[0m 原因={error}\n"
                    "\033[33m[处理建议]\033[0m 检查当前环境是否能访问微信 iLink 服务，并确认依赖安装完整。"
                )
                return PERSONAL_WECHAT_LOGIN_START_FAILED_TEMPLATE.format(reason=str(error))

            qr_content = str(getattr(start_result, "qrcode_url", "") or "").strip()
            session_key = str(getattr(start_result, "session_key", "") or "").strip()
            message = str(getattr(start_result, "message", "") or "").strip()
            if not qr_content or not session_key:
                reason = message or "未拿到二维码内容"
                print(
                    f"\033[31m[personal WeChat 登录启动失败]\033[0m 原因={reason}\n"
                    "\033[33m[处理建议]\033[0m 检查微信二维码接口返回值是否变化。"
                )
                return PERSONAL_WECHAT_LOGIN_START_FAILED_TEMPLATE.format(reason=reason)

            try:
                qr_artifact = self._qr_artifact_builder(qr_content)
            except Exception as error:
                print(
                    f"\033[31m[personal WeChat 二维码生成失败]\033[0m 原因={error}\n"
                    "\033[33m[处理建议]\033[0m 检查 qrcode SVG 依赖，并确认 /tmp 可写。"
                )
                return PERSONAL_WECHAT_LOGIN_START_FAILED_TEMPLATE.format(reason="二维码文件生成失败，请查看日志")

            try:
                await send_media_func(chat_id, qr_artifact.file_path, PERSONAL_WECHAT_LOGIN_QR_CAPTION)
            except Exception as error:
                _cleanup_qr_artifact(qr_artifact)
                print(
                    f"\033[31m[personal WeChat 二维码回传失败]\033[0m chat_id={chat_id} 原因={error}\n"
                    "\033[33m[处理建议]\033[0m 检查 Telegram 文件发送权限，并确认当前私聊仍可接收文档。"
                )
                return PERSONAL_WECHAT_LOGIN_START_FAILED_TEMPLATE.format(reason="二维码回传失败，请查看日志")

            self._active_chat_id = chat_id
            self._active_qr_artifact = qr_artifact
            self._wait_task = asyncio.create_task(
                self._wait_for_login_result(
                    chat_id=chat_id,
                    session_key=session_key,
                    send_text_func=send_text_func,
                ),
                name="personal_wechat_login_wait",
            )
            return PERSONAL_WECHAT_LOGIN_STARTED_TEXT

    async def shutdown(self) -> None:
        task: asyncio.Task[None] | None = None
        async with self._lock:
            task = self._wait_task
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await self._finalize_active_login()
        if self._close_client_func is not None:
            await self._close_client_func()

    async def _wait_for_login_result(
        self,
        *,
        chat_id: int,
        session_key: str,
        send_text_func: TelegramSendTextFunc | None,
    ) -> None:
        try:
            wait_result = await self._wait_login_func(
                session_key=session_key,
                api_base_url=self._api_base_url,
                verbose=False,
            )
            if not bool(getattr(wait_result, "connected", False)):
                reason = str(getattr(wait_result, "message", "") or "登录未完成").strip()
                print(
                    f"\033[31m[personal WeChat 登录未完成]\033[0m chat_id={chat_id} 原因={reason}\n"
                    "\033[33m[处理建议]\033[0m 重新发送“微信登录”获取新二维码，并在有效期内完成扫码。"
                )
                await self._notify_result(
                    chat_id=chat_id,
                    send_text_func=send_text_func,
                    text=PERSONAL_WECHAT_LOGIN_RESULT_FAILED_TEMPLATE.format(reason=reason),
                )
                return

            account_id = str(getattr(wait_result, "account_id", "") or "").strip()
            bot_token = str(getattr(wait_result, "bot_token", "") or "").strip()
            base_url = str(getattr(wait_result, "base_url", "") or self._api_base_url).strip()
            user_id = str(getattr(wait_result, "user_id", "") or "-").strip() or "-"
            if not account_id or not bot_token:
                reason = "登录成功回包缺少 account_id 或 bot_token"
                print(
                    f"\033[31m[personal WeChat 登录结果无效]\033[0m chat_id={chat_id} 原因={reason}\n"
                    "\033[33m[处理建议]\033[0m 检查微信 iLink 登录回包结构是否变化。"
                )
                await self._notify_result(
                    chat_id=chat_id,
                    send_text_func=send_text_func,
                    text=PERSONAL_WECHAT_LOGIN_RESULT_FAILED_TEMPLATE.format(reason=reason),
                )
                return

            self._save_account_func(
                account_id,
                token=bot_token,
                base_url=base_url,
                user_id=None if user_id == "-" else user_id,
            )
            self._register_account_func(account_id)
            if user_id != "-" and self._clear_stale_accounts_func is not None:
                self._clear_stale_accounts_func(account_id, user_id)
            await self._notify_result(
                chat_id=chat_id,
                send_text_func=send_text_func,
                text=PERSONAL_WECHAT_LOGIN_RESULT_SUCCESS_TEMPLATE.format(
                    account_id=account_id,
                    user_id=user_id,
                ),
            )
        except asyncio.CancelledError:
            raise
        except Exception as error:
            print(
                f"\033[31m[personal WeChat 登录等待失败]\033[0m chat_id={chat_id} 原因={error}\n"
                "\033[33m[处理建议]\033[0m 检查微信 iLink 长轮询是否可达，并重新发送“微信登录”触发新一轮登录。"
            )
            await self._notify_result(
                chat_id=chat_id,
                send_text_func=send_text_func,
                text=PERSONAL_WECHAT_LOGIN_RESULT_FAILED_TEMPLATE.format(reason=str(error)),
            )
        finally:
            await self._finalize_active_login()
            if self._close_client_func is not None:
                await self._close_client_func()

    async def _notify_result(
        self,
        *,
        chat_id: int,
        send_text_func: TelegramSendTextFunc | None,
        text: str,
    ) -> None:
        if send_text_func is None:
            return
        try:
            await send_text_func(chat_id=chat_id, text=text)
        except Exception as error:
            print(
                f"\033[31m[personal WeChat 登录结果通知失败]\033[0m chat_id={chat_id} 原因={error}\n"
                "\033[33m[处理建议]\033[0m 检查 Telegram bot 是否仍可向该私聊发文本消息。"
            )

    async def _finalize_active_login(self) -> None:
        async with self._lock:
            await self._finalize_active_login_locked()

    async def _finalize_active_login_locked(self) -> None:
        self._wait_task = None
        self._active_chat_id = None
        qr_artifact = self._active_qr_artifact
        self._active_qr_artifact = None
        _cleanup_qr_artifact(qr_artifact)


__all__ = [
    "PERSONAL_WECHAT_LOGIN_BUSY_TEXT",
    "PERSONAL_WECHAT_LOGIN_NOT_READY_TEXT",
    "PERSONAL_WECHAT_LOGIN_QR_CAPTION",
    "PERSONAL_WECHAT_LOGIN_REUSED_TEXT",
    "PERSONAL_WECHAT_LOGIN_SERVICE_KEY",
    "PERSONAL_WECHAT_LOGIN_STARTED_TEXT",
    "PersonalWeChatLoginService",
    "parse_personal_wechat_login_query",
]

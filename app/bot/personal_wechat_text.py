from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable, MutableMapping
from dataclasses import dataclass
from pathlib import Path

from app.bot.channel_identity import project_channel_chat_id, project_channel_user_id
from app.bot.cleanup_smoke_logging import log_cleanup_private_chat_smoke
from app.bot.private_chat_runtime import dispatch_private_chat_text

PERSONAL_WECHAT_CHANNEL = "personal_wechat"
PERSONAL_WECHAT_TEXT_SERVICE_KEY = "personal_wechat_text_service"
PERSONAL_WECHAT_LONG_POLL_TIMEOUT_MS = 35_000
PERSONAL_WECHAT_RETRY_DELAY_SECONDS = 2.0
PERSONAL_WECHAT_BACKOFF_DELAY_SECONDS = 30.0
PERSONAL_WECHAT_MAX_CONSECUTIVE_FAILURES = 3

try:
    from wechat_clawbot.api.client import (
        WeixinApiOptions,
        close_shared_client,
        get_updates,
    )
    from wechat_clawbot.api.session_guard import (
        SESSION_EXPIRED_ERRCODE,
        get_remaining_pause_ms,
        is_session_paused,
        pause_session,
    )
    from wechat_clawbot.api.types import MessageItemType, MessageType
    from wechat_clawbot.auth.accounts import (
        DEFAULT_BASE_URL as DEFAULT_WECHAT_API_BASE_URL,
        list_weixin_account_ids,
        load_weixin_account,
    )
    from wechat_clawbot.messaging.inbound import (
        get_context_token,
        restore_context_tokens,
        set_context_token,
    )
    from wechat_clawbot.messaging.send import send_message_weixin
    from wechat_clawbot.storage.sync_buf import (
        get_sync_buf_file_path,
        load_get_updates_buf,
        save_get_updates_buf,
    )
except ImportError as import_error:  # pragma: no cover - exercised via availability checks
    WeixinApiOptions = None
    MessageItemType = None
    MessageType = None
    DEFAULT_WECHAT_API_BASE_URL = "https://ilinkai.weixin.qq.com"
    get_updates = None
    send_message_weixin = None
    close_shared_client = None
    list_weixin_account_ids = None
    load_weixin_account = None
    restore_context_tokens = None
    get_context_token = None
    set_context_token = None
    get_sync_buf_file_path = None
    load_get_updates_buf = None
    save_get_updates_buf = None
    is_session_paused = None
    get_remaining_pause_ms = None
    pause_session = None
    SESSION_EXPIRED_ERRCODE = -14
    _PERSONAL_WECHAT_TEXT_IMPORT_ERROR = import_error
else:
    _PERSONAL_WECHAT_TEXT_IMPORT_ERROR = None

LoadAccountFunc = Callable[[str], object | None]
ListAccountIdsFunc = Callable[[], list[str]]
RestoreContextTokensFunc = Callable[[str], None]
GetContextTokenFunc = Callable[[str, str], str | None]
SetContextTokenFunc = Callable[[str, str, str], None]
GetSyncBufFilePathFunc = Callable[[str], Path]
LoadSyncBufFunc = Callable[[Path], str | None]
SaveSyncBufFunc = Callable[[Path, str], None]
GetUpdatesFunc = Callable[..., Awaitable[object]]
SendTextFunc = Callable[[str, str, object], Awaitable[object]]
CloseClientFunc = Callable[[], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class PersonalWeChatPrivateTextEvent:
    account_id: str
    from_user_id: str
    message_id: str
    text: str
    context_token: str | None = None


def parse_personal_wechat_private_text_event(
    *,
    account_id: str,
    message: object,
) -> PersonalWeChatPrivateTextEvent | None:
    if MessageType is None or MessageItemType is None:
        return None

    cleaned_account_id = account_id.strip()
    if not cleaned_account_id:
        return None

    message_type = getattr(message, "message_type", None)
    if int(message_type or 0) != int(MessageType.USER):
        return None

    if str(getattr(message, "group_id", "") or "").strip():
        return None

    from_user_id = str(getattr(message, "from_user_id", "") or "").strip()
    if not from_user_id:
        return None

    text = _extract_text_from_item_list(getattr(message, "item_list", None))
    if not text:
        return None

    context_token = str(getattr(message, "context_token", "") or "").strip() or None
    message_id = str(getattr(message, "message_id", "") or "").strip()
    return PersonalWeChatPrivateTextEvent(
        account_id=cleaned_account_id,
        from_user_id=from_user_id,
        message_id=message_id,
        text=text,
        context_token=context_token,
    )


async def handle_personal_wechat_private_text_event(
    *,
    account_id: str,
    message: object,
    bot_data: MutableMapping[str, object],
    reply_text_func: Callable[[PersonalWeChatPrivateTextEvent, str], Awaitable[object]],
) -> PersonalWeChatPrivateTextEvent | None:
    event = parse_personal_wechat_private_text_event(
        account_id=account_id,
        message=message,
    )
    if event is None:
        return None

    async def reply_with_event(reply_text: str) -> object:
        result = await reply_text_func(event, reply_text)
        log_cleanup_private_chat_smoke(
            channel=PERSONAL_WECHAT_CHANNEL,
            query=event.text,
            reply_text=reply_text,
            chat_id=project_channel_chat_id(
                channel=PERSONAL_WECHAT_CHANNEL,
                external_chat_id=event.from_user_id,
            ),
            user_id=project_channel_user_id(
                channel=PERSONAL_WECHAT_CHANNEL,
                external_user_id=event.from_user_id,
            ),
        )
        return result

    await dispatch_private_chat_text(
        query=event.text,
        reply_func=reply_with_event,
        chat_id=project_channel_chat_id(
            channel=PERSONAL_WECHAT_CHANNEL,
            external_chat_id=event.from_user_id,
        ),
        user_id=project_channel_user_id(
            channel=PERSONAL_WECHAT_CHANNEL,
            external_user_id=event.from_user_id,
        ),
        bot_data=bot_data,
    )
    return event


def _extract_text_from_item_list(item_list: object) -> str:
    if MessageItemType is None or not isinstance(item_list, list):
        return ""

    for item in item_list:
        if int(getattr(item, "type", 0) or 0) != int(MessageItemType.TEXT):
            continue
        text_item = getattr(item, "text_item", None)
        text = str(getattr(text_item, "text", "") or "").strip()
        if text:
            return text
    return ""


class PersonalWeChatTextService:
    def __init__(
        self,
        *,
        list_account_ids_func: ListAccountIdsFunc | None = list_weixin_account_ids,
        load_account_func: LoadAccountFunc | None = load_weixin_account,
        restore_context_tokens_func: RestoreContextTokensFunc | None = restore_context_tokens,
        get_context_token_func: GetContextTokenFunc | None = get_context_token,
        set_context_token_func: SetContextTokenFunc | None = set_context_token,
        get_sync_buf_file_path_func: GetSyncBufFilePathFunc | None = get_sync_buf_file_path,
        load_sync_buf_func: LoadSyncBufFunc | None = load_get_updates_buf,
        save_sync_buf_func: SaveSyncBufFunc | None = save_get_updates_buf,
        get_updates_func: GetUpdatesFunc | None = get_updates,
        send_text_func: SendTextFunc | None = send_message_weixin,
        close_client_func: CloseClientFunc | None = close_shared_client,
        long_poll_timeout_ms: int = PERSONAL_WECHAT_LONG_POLL_TIMEOUT_MS,
    ) -> None:
        self._list_account_ids_func = list_account_ids_func
        self._load_account_func = load_account_func
        self._restore_context_tokens_func = restore_context_tokens_func
        self._get_context_token_func = get_context_token_func
        self._set_context_token_func = set_context_token_func
        self._get_sync_buf_file_path_func = get_sync_buf_file_path_func
        self._load_sync_buf_func = load_sync_buf_func
        self._save_sync_buf_func = save_sync_buf_func
        self._get_updates_func = get_updates_func
        self._send_text_func = send_text_func
        self._close_client_func = close_client_func
        self._long_poll_timeout_ms = long_poll_timeout_ms
        self._stop_event: asyncio.Event | None = None
        self._poll_task: asyncio.Task[None] | None = None

    def is_available(self) -> bool:
        return (
            WeixinApiOptions is not None
            and self._list_account_ids_func is not None
            and self._load_account_func is not None
            and self._restore_context_tokens_func is not None
            and self._get_sync_buf_file_path_func is not None
            and self._load_sync_buf_func is not None
            and self._save_sync_buf_func is not None
            and self._get_updates_func is not None
            and self._send_text_func is not None
        )

    async def start(self, *, bot_data: MutableMapping[str, object]) -> None:
        if self._poll_task is not None and not self._poll_task.done():
            return

        if not self.is_available():
            reason = _PERSONAL_WECHAT_TEXT_IMPORT_ERROR or "wechat-clawbot dependency is missing"
            print(
                f"\033[31m[personal WeChat 私聊文本未就绪]\033[0m 原因={reason}\n"
                "\033[33m[处理建议]\033[0m 安装 wechat-clawbot，并确认当前环境可访问微信 iLink 服务。"
            )
            return

        account_state = self._resolve_single_account_state()
        if account_state is None:
            return

        account_id, base_url, token = account_state
        self._restore_context_tokens_func(account_id)
        stop_event = asyncio.Event()
        self._stop_event = stop_event
        self._poll_task = asyncio.create_task(
            self._poll_updates_loop(
                account_id=account_id,
                base_url=base_url,
                token=token,
                bot_data=bot_data,
                stop_event=stop_event,
            ),
            name="personal_wechat_text_poll",
        )
        print(f"\033[32m[personal WeChat 私聊文本已启动]\033[0m account_id={account_id}")

    async def shutdown(self) -> None:
        stop_event = self._stop_event
        poll_task = self._poll_task
        self._stop_event = None
        self._poll_task = None
        if isinstance(stop_event, asyncio.Event):
            stop_event.set()
        if isinstance(poll_task, asyncio.Task):
            poll_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await poll_task
        if self._close_client_func is not None:
            await self._close_client_func()

    def _resolve_single_account_state(self) -> tuple[str, str, str] | None:
        raw_account_ids = self._list_account_ids_func() or []
        seen_account_ids: set[str] = set()
        resolved_accounts: list[tuple[str, str, str]] = []
        empty_token_accounts: list[str] = []

        for raw_account_id in raw_account_ids:
            account_id = str(raw_account_id or "").strip()
            if not account_id or account_id in seen_account_ids:
                continue
            seen_account_ids.add(account_id)
            account = self._load_account_func(account_id)
            if account is None:
                continue
            token = str(getattr(account, "token", "") or "").strip()
            if not token:
                empty_token_accounts.append(account_id)
                continue
            base_url = str(getattr(account, "base_url", "") or "").strip() or DEFAULT_WECHAT_API_BASE_URL
            resolved_accounts.append((account_id, base_url, token))

        if not resolved_accounts:
            if empty_token_accounts:
                print(
                    "\033[31m[personal WeChat 私聊文本未启动]\033[0m 原因=检测到已保存账号，但缺少可用 token。\n"
                    "\033[33m[处理建议]\033[0m 重新发送“微信登录”刷新当前 personal WeChat 凭据。"
                )
            return None

        if len(resolved_accounts) > 1:
            print(
                "\033[31m[personal WeChat 私聊文本未启动]\033[0m 原因=当前检测到多个已保存的 personal WeChat 账号。\n"
                "\033[33m[处理建议]\033[0m 当前只支持单账号最小基线，请只保留一个可用账号后重启服务。"
            )
            return None

        return resolved_accounts[0]

    async def _poll_updates_loop(
        self,
        *,
        account_id: str,
        base_url: str,
        token: str,
        bot_data: MutableMapping[str, object],
        stop_event: asyncio.Event,
    ) -> None:
        sync_file_path = self._get_sync_buf_file_path_func(account_id)
        get_updates_buf = self._load_sync_buf_func(sync_file_path) or ""
        next_timeout_ms = self._long_poll_timeout_ms
        consecutive_failures = 0

        while not stop_event.is_set():
            try:
                if self._is_session_paused(account_id):
                    await self._sleep_with_stop(
                        delay_seconds=self._get_remaining_pause_seconds(account_id),
                        stop_event=stop_event,
                    )
                    continue

                response = await self._get_updates_func(
                    base_url=base_url,
                    token=token,
                    get_updates_buf=get_updates_buf,
                    timeout_ms=next_timeout_ms,
                )

                response_timeout = getattr(response, "longpolling_timeout_ms", None)
                if isinstance(response_timeout, int) and response_timeout > 0:
                    next_timeout_ms = response_timeout

                if self._is_api_error(response):
                    if self._is_session_expired(response):
                        self._pause_session(account_id)
                        pause_seconds = self._get_remaining_pause_seconds(account_id)
                        print(
                            f"\033[31m[personal WeChat 会话已过期]\033[0m account_id={account_id} "
                            f"errcode={getattr(response, 'errcode', None)} errmsg={getattr(response, 'errmsg', '')}\n"
                            "\033[33m[处理建议]\033[0m 重新发送“微信登录”刷新凭据，并在下次启动后重试 personal WeChat 私聊。"
                        )
                        consecutive_failures = 0
                        await self._sleep_with_stop(delay_seconds=pause_seconds, stop_event=stop_event)
                        continue

                    consecutive_failures += 1
                    print(
                        f"\033[31m[personal WeChat 长轮询失败]\033[0m account_id={account_id} "
                        f"ret={getattr(response, 'ret', None)} errcode={getattr(response, 'errcode', None)} "
                        f"errmsg={getattr(response, 'errmsg', '')}\n"
                        "\033[33m[处理建议]\033[0m 检查微信 iLink 服务、当前登录态和网络连通性。"
                    )
                    await self._sleep_for_failure(
                        consecutive_failures=consecutive_failures,
                        stop_event=stop_event,
                    )
                    if consecutive_failures >= PERSONAL_WECHAT_MAX_CONSECUTIVE_FAILURES:
                        consecutive_failures = 0
                    continue

                consecutive_failures = 0
                next_buf = getattr(response, "get_updates_buf", None)
                if isinstance(next_buf, str) and next_buf and next_buf != get_updates_buf:
                    get_updates_buf = next_buf
                    self._save_sync_buf_func(sync_file_path, get_updates_buf)

                for message in list(getattr(response, "msgs", None) or []):
                    await self._handle_inbound_message(
                        account_id=account_id,
                        base_url=base_url,
                        token=token,
                        message=message,
                        bot_data=bot_data,
                    )
            except asyncio.CancelledError:
                raise
            except Exception as error:
                if stop_event.is_set():
                    return
                consecutive_failures += 1
                print(
                    f"\033[31m[personal WeChat 长轮询异常]\033[0m account_id={account_id} 原因={error}\n"
                    "\033[33m[处理建议]\033[0m 检查当前 personal WeChat 凭据、微信 iLink 服务和本地网络后重试。"
                )
                await self._sleep_for_failure(
                    consecutive_failures=consecutive_failures,
                    stop_event=stop_event,
                )
                if consecutive_failures >= PERSONAL_WECHAT_MAX_CONSECUTIVE_FAILURES:
                    consecutive_failures = 0

    async def _handle_inbound_message(
        self,
        *,
        account_id: str,
        base_url: str,
        token: str,
        message: object,
        bot_data: MutableMapping[str, object],
    ) -> None:
        parsed_event = parse_personal_wechat_private_text_event(
            account_id=account_id,
            message=message,
        )
        if parsed_event is None:
            return

        if parsed_event.context_token and self._set_context_token_func is not None:
            self._set_context_token_func(account_id, parsed_event.from_user_id, parsed_event.context_token)

        async def reply_text_func(event: PersonalWeChatPrivateTextEvent, reply_text: str) -> object:
            context_token = event.context_token
            if not context_token and self._get_context_token_func is not None:
                cached_context_token = self._get_context_token_func(account_id, event.from_user_id)
                context_token = str(cached_context_token or "").strip() or None
            opts = WeixinApiOptions(
                base_url=base_url,
                token=token,
                context_token=context_token,
            )
            return await self._send_text_func(event.from_user_id, reply_text, opts)

        try:
            await handle_personal_wechat_private_text_event(
                account_id=account_id,
                message=message,
                bot_data=bot_data,
                reply_text_func=reply_text_func,
            )
        except Exception as error:
            print(
                f"\033[31m[personal WeChat 私聊消息处理失败]\033[0m account_id={account_id} "
                f"user_id={parsed_event.from_user_id} 原因={error}\n"
                "\033[33m[处理建议]\033[0m 检查 shared private-chat runtime 依赖、当前登录态和微信文本消息内容。"
            )

    async def _sleep_for_failure(
        self,
        *,
        consecutive_failures: int,
        stop_event: asyncio.Event,
    ) -> None:
        delay_seconds = PERSONAL_WECHAT_RETRY_DELAY_SECONDS
        if consecutive_failures >= PERSONAL_WECHAT_MAX_CONSECUTIVE_FAILURES:
            delay_seconds = PERSONAL_WECHAT_BACKOFF_DELAY_SECONDS
        await self._sleep_with_stop(
            delay_seconds=delay_seconds,
            stop_event=stop_event,
        )

    async def _sleep_with_stop(
        self,
        *,
        delay_seconds: float,
        stop_event: asyncio.Event,
    ) -> None:
        if delay_seconds <= 0:
            return
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=delay_seconds)
        except asyncio.TimeoutError:
            return

    def _is_api_error(self, response: object) -> bool:
        ret = getattr(response, "ret", None)
        errcode = getattr(response, "errcode", None)
        return (ret is not None and ret != 0) or (errcode is not None and errcode != 0)

    def _is_session_expired(self, response: object) -> bool:
        ret = getattr(response, "ret", None)
        errcode = getattr(response, "errcode", None)
        return ret == SESSION_EXPIRED_ERRCODE or errcode == SESSION_EXPIRED_ERRCODE

    def _is_session_paused(self, account_id: str) -> bool:
        if is_session_paused is None:
            return False
        return is_session_paused(account_id)

    def _get_remaining_pause_seconds(self, account_id: str) -> float:
        if get_remaining_pause_ms is None:
            return 0.0
        remaining_ms = get_remaining_pause_ms(account_id)
        if remaining_ms <= 0:
            return 0.0
        return remaining_ms / 1000.0

    def _pause_session(self, account_id: str) -> None:
        if pause_session is None:
            return
        pause_session(account_id)


__all__ = [
    "PERSONAL_WECHAT_CHANNEL",
    "PERSONAL_WECHAT_TEXT_SERVICE_KEY",
    "PersonalWeChatPrivateTextEvent",
    "PersonalWeChatTextService",
    "handle_personal_wechat_private_text_event",
    "parse_personal_wechat_private_text_event",
]

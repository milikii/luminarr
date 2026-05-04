from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping

from app.bot.channel_contact_runtime import resolve_channel_contact
from app.operational_logging import emit_operational_log

FEISHU_CHANNEL = "feishu"
PERSONAL_WECHAT_CHANNEL = "personal_wechat"
WECOM_CHANNEL = "wecom"

SharedSendTextFunc = Callable[[int, str], Awaitable[object]]
TelegramSendTextFunc = Callable[..., Awaitable[object]]


def build_shared_private_chat_send_text_func(
    *,
    bot_data: Mapping[str, object],
    telegram_send_text_func: TelegramSendTextFunc | None = None,
    feishu_send_text_func: SharedSendTextFunc | None = None,
    personal_wechat_send_text_func: SharedSendTextFunc | None = None,
) -> SharedSendTextFunc:
    async def send_text(chat_id: int, text: str) -> object:
        contact = resolve_channel_contact(bot_data, internal_chat_id=chat_id)
        if contact is not None:
            if contact.channel == FEISHU_CHANNEL and feishu_send_text_func is not None:
                return await feishu_send_text_func(chat_id, text)
            if contact.channel == PERSONAL_WECHAT_CHANNEL and personal_wechat_send_text_func is not None:
                return await personal_wechat_send_text_func(chat_id, text)
            if contact.channel == WECOM_CHANNEL:
                raise RuntimeError(f"shared private chat send unsupported for channel: {WECOM_CHANNEL}")

        if telegram_send_text_func is not None:
            return await telegram_send_text_func(chat_id=chat_id, text=text)

        channel_name = contact.channel if contact is not None else "-"
        raise RuntimeError(f"shared private chat send unavailable for chat_id={chat_id} channel={channel_name}")

    return send_text


def build_feishu_proactive_send_text_func(*, bot_data: Mapping[str, object]) -> SharedSendTextFunc:
    async def send_text(chat_id: int, text: str) -> object:
        contact = resolve_channel_contact(bot_data, internal_chat_id=chat_id)
        if contact is None or contact.channel != FEISHU_CHANNEL:
            raise RuntimeError(f"feishu contact missing for chat_id={chat_id}")
        client = bot_data.get("feishu_client")
        send_private_text = getattr(client, "send_private_text", None)
        if not callable(send_private_text):
            raise RuntimeError("feishu client send_private_text unavailable")
        return await send_private_text(chat_id=contact.external_chat_id, text=text)

    return send_text


def build_personal_wechat_proactive_send_text_func(*, bot_data: Mapping[str, object]) -> SharedSendTextFunc:
    async def send_text(chat_id: int, text: str) -> object:
        contact = resolve_channel_contact(bot_data, internal_chat_id=chat_id)
        if contact is None or contact.channel != PERSONAL_WECHAT_CHANNEL:
            raise RuntimeError(f"personal_wechat contact missing for chat_id={chat_id}")
        service = bot_data.get("personal_wechat_text_service")
        send_private_text = getattr(service, "send_proactive_text", None)
        if not callable(send_private_text):
            raise RuntimeError("personal wechat proactive send unavailable")
        return await send_private_text(external_chat_id=contact.external_chat_id, text=text)

    return send_text


def log_shared_private_chat_send_error(*, chat_id: int, error: Exception) -> None:
    emit_operational_log(
        title="共享私聊后台通知失败",
        detail=f"chat_id={chat_id} 原因={error}",
        fix_hint="检查聊天身份映射、渠道主动发送能力和网络连通性；当前后台通知已跳过，不影响内部任务真相。",
    )

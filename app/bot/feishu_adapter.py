from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Mapping, MutableMapping
from dataclasses import dataclass
from typing import Any

from app.bot.channel_contact_runtime import record_channel_contact
from app.bot.channel_identity import project_channel_chat_id, project_channel_user_id
from app.bot.cleanup_smoke_logging import log_cleanup_private_chat_smoke
from app.bot.private_chat_runtime import handle_private_chat_query_text as dispatch_private_chat_text
from app.clients.feishu import FeishuClient

FEISHU_CHANNEL = "feishu"
FEISHU_PRIVATE_TEXT_EVENT_TYPE = "im.message.receive_v1"


@dataclass(frozen=True, slots=True)
class FeishuPrivateTextEvent:
    event_id: str
    message_id: str
    chat_id: str
    user_open_id: str
    text: str


def parse_feishu_private_text_event(payload: Mapping[str, Any]) -> FeishuPrivateTextEvent | None:
    header = payload.get("header")
    event = payload.get("event")
    if not isinstance(header, Mapping) or not isinstance(event, Mapping):
        return None

    event_type = str(header.get("event_type", "")).strip()
    if event_type != FEISHU_PRIVATE_TEXT_EVENT_TYPE:
        return None

    message = event.get("message")
    sender = event.get("sender")
    if not isinstance(message, Mapping) or not isinstance(sender, Mapping):
        return None

    chat_type = str(message.get("chat_type", "")).strip().lower()
    if chat_type != "p2p":
        return None

    message_type = str(message.get("message_type", "")).strip().lower()
    if message_type != "text":
        return None

    chat_id = str(message.get("chat_id", "")).strip()
    message_id = str(message.get("message_id", "")).strip()
    user_open_id = _extract_sender_open_id(sender)
    text = _extract_text_from_content(message.get("content"))
    if not chat_id or not user_open_id or not text:
        return None

    return FeishuPrivateTextEvent(
        event_id=str(header.get("event_id", "")).strip(),
        message_id=message_id,
        chat_id=chat_id,
        user_open_id=user_open_id,
        text=text,
    )


def parse_feishu_sdk_private_text_event(payload: object) -> FeishuPrivateTextEvent | None:
    header = getattr(payload, "header", None)
    event = getattr(payload, "event", None)
    if header is None or event is None:
        return None

    event_type = str(getattr(header, "event_type", "") or "").strip()
    if event_type != FEISHU_PRIVATE_TEXT_EVENT_TYPE:
        return None

    message = getattr(event, "message", None)
    sender = getattr(event, "sender", None)
    if message is None or sender is None:
        return None

    chat_type = str(getattr(message, "chat_type", "") or "").strip().lower()
    if chat_type != "p2p":
        return None

    message_type = str(getattr(message, "message_type", "") or "").strip().lower()
    if message_type != "text":
        return None

    chat_id = str(getattr(message, "chat_id", "") or "").strip()
    message_id = str(getattr(message, "message_id", "") or "").strip()
    sender_id = getattr(sender, "sender_id", None)
    user_open_id = str(getattr(sender_id, "open_id", "") or "").strip()
    text = _extract_text_from_content(getattr(message, "content", None))
    if not chat_id or not user_open_id or not text:
        return None

    return FeishuPrivateTextEvent(
        event_id=str(getattr(header, "event_id", "") or "").strip(),
        message_id=message_id,
        chat_id=chat_id,
        user_open_id=user_open_id,
        text=text,
    )


async def route_feishu_private_text_event(
    *,
    event: FeishuPrivateTextEvent,
    bot_data: MutableMapping[str, object],
    reply_text_func: Callable[[FeishuPrivateTextEvent, str], Awaitable[object]],
) -> None:
    chat_id = project_channel_chat_id(channel=FEISHU_CHANNEL, external_chat_id=event.chat_id)
    user_id = project_channel_user_id(channel=FEISHU_CHANNEL, external_user_id=event.user_open_id)
    record_channel_contact(
        bot_data,
        channel=FEISHU_CHANNEL,
        internal_chat_id=chat_id,
        external_chat_id=event.chat_id,
        external_user_id=event.user_open_id,
    )

    async def reply_with_event(reply_text: str) -> object:
        result = await reply_text_func(event, reply_text)
        log_cleanup_private_chat_smoke(
            channel=FEISHU_CHANNEL,
            query=event.text,
            reply_text=reply_text,
            chat_id=chat_id,
            user_id=user_id,
        )
        return result

    await dispatch_private_chat_text(
        query=event.text,
        reply_func=reply_with_event,
        chat_id=chat_id,
        user_id=user_id,
        channel=FEISHU_CHANNEL,
        bot_data=bot_data,
    )


async def handle_feishu_private_text_event(
    *,
    payload: Mapping[str, Any],
    bot_data: MutableMapping[str, object],
    reply_text_func: Callable[[FeishuPrivateTextEvent, str], Awaitable[object]],
) -> str | None:
    event = parse_feishu_private_text_event(payload)
    if event is None:
        return None

    await route_feishu_private_text_event(
        event=event,
        bot_data=bot_data,
        reply_text_func=reply_text_func,
    )
    return None


def build_feishu_reply_text_func(
    feishu_client: FeishuClient,
) -> Callable[[FeishuPrivateTextEvent, str], Awaitable[object]]:
    async def reply_text(event: FeishuPrivateTextEvent, reply_text: str) -> object:
        return await feishu_client.send_private_text(chat_id=event.chat_id, text=reply_text)

    return reply_text


def _extract_sender_open_id(sender: Mapping[str, Any]) -> str:
    sender_id = sender.get("sender_id")
    if not isinstance(sender_id, Mapping):
        return ""
    return str(sender_id.get("open_id", "")).strip()


def _extract_text_from_content(raw_content: object) -> str:
    if not isinstance(raw_content, str):
        return ""
    try:
        content = json.loads(raw_content)
    except json.JSONDecodeError:
        return ""
    if not isinstance(content, dict):
        return ""
    return str(content.get("text", "")).strip()

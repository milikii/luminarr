from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Mapping, MutableMapping
from dataclasses import dataclass
from typing import Any

from app.bot.channel_identity import project_channel_chat_id, project_channel_user_id
from app.bot.private_chat_runtime import dispatch_private_chat_text

FEISHU_CHANNEL = "feishu"
FEISHU_URL_VERIFICATION_TYPE = "url_verification"
FEISHU_PRIVATE_TEXT_EVENT_TYPE = "im.message.receive_v1"


@dataclass(frozen=True, slots=True)
class FeishuPrivateTextEvent:
    event_id: str
    message_id: str
    chat_id: str
    user_open_id: str
    text: str


def get_feishu_url_verification_challenge(payload: Mapping[str, Any]) -> str | None:
    payload_type = str(payload.get("type", "")).strip().lower()
    if payload_type != FEISHU_URL_VERIFICATION_TYPE:
        return None
    challenge = str(payload.get("challenge", "")).strip()
    return challenge or None


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


async def handle_feishu_private_text_event(
    *,
    payload: Mapping[str, Any],
    bot_data: MutableMapping[str, object],
    reply_text_func: Callable[[FeishuPrivateTextEvent, str], Awaitable[object]],
) -> str | None:
    challenge = get_feishu_url_verification_challenge(payload)
    if challenge is not None:
        return challenge

    event = parse_feishu_private_text_event(payload)
    if event is None:
        return None

    async def reply_with_event(reply_text: str) -> object:
        return await reply_text_func(event, reply_text)

    await dispatch_private_chat_text(
        query=event.text,
        reply_func=reply_with_event,
        chat_id=project_channel_chat_id(channel=FEISHU_CHANNEL, external_chat_id=event.chat_id),
        user_id=project_channel_user_id(channel=FEISHU_CHANNEL, external_user_id=event.user_open_id),
        bot_data=bot_data,
    )
    return None


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

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Awaitable, Callable, MutableMapping
from dataclasses import dataclass

from app.bot.channel_identity import project_channel_chat_id, project_channel_user_id
from app.bot.private_chat_runtime import dispatch_private_chat_text

WECOM_CHANNEL = "wecom"


@dataclass(frozen=True, slots=True)
class WeComPrivateTextEvent:
    corp_id: str
    user_id: str
    msg_id: str
    agent_id: str
    text: str


def parse_wecom_private_text_event(payload_xml: bytes | str) -> WeComPrivateTextEvent | None:
    normalized_xml = _normalize_xml_payload(payload_xml)
    if not normalized_xml:
        return None

    try:
        root = ET.fromstring(normalized_xml)
    except ET.ParseError:
        return None

    if _read_xml_text(root, "MsgType").lower() != "text":
        return None

    corp_id = _read_xml_text(root, "ToUserName")
    user_id = _read_xml_text(root, "FromUserName")
    text = _read_xml_text(root, "Content")
    if not corp_id or not user_id or not text:
        return None

    return WeComPrivateTextEvent(
        corp_id=corp_id,
        user_id=user_id,
        msg_id=_read_xml_text(root, "MsgId"),
        agent_id=_read_xml_text(root, "AgentID"),
        text=text,
    )


async def handle_wecom_private_text_event(
    *,
    payload_xml: bytes | str,
    bot_data: MutableMapping[str, object],
    reply_text_func: Callable[[WeComPrivateTextEvent, str], Awaitable[object]],
) -> WeComPrivateTextEvent | None:
    event = parse_wecom_private_text_event(payload_xml)
    if event is None:
        return None

    async def reply_with_event(reply_text: str) -> object:
        return await reply_text_func(event, reply_text)

    await dispatch_private_chat_text(
        query=event.text,
        reply_func=reply_with_event,
        chat_id=project_channel_chat_id(
            channel=WECOM_CHANNEL,
            external_chat_id=_resolve_private_chat_external_id(event),
        ),
        user_id=project_channel_user_id(
            channel=WECOM_CHANNEL,
            external_user_id=event.user_id,
        ),
        bot_data=bot_data,
    )
    return event


def _resolve_private_chat_external_id(event: WeComPrivateTextEvent) -> str:
    return event.user_id


def _normalize_xml_payload(payload_xml: bytes | str) -> str:
    if isinstance(payload_xml, bytes):
        try:
            return payload_xml.decode("utf-8").strip()
        except UnicodeDecodeError:
            return ""
    return payload_xml.strip()


def _read_xml_text(root: ET.Element, tag_name: str) -> str:
    element = root.find(tag_name)
    if element is None or element.text is None:
        return ""
    return element.text.strip()

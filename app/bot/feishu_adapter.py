from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Mapping, MutableMapping
from dataclasses import dataclass
from typing import Any

from app.bot.channel_identity import project_channel_chat_id, project_channel_user_id
from app.bot.private_chat_runtime import dispatch_private_chat_text
from app.clients.feishu import FeishuClient

FEISHU_CHANNEL = "feishu"
FEISHU_URL_VERIFICATION_TYPE = "url_verification"
FEISHU_PRIVATE_TEXT_EVENT_TYPE = "im.message.receive_v1"
FEISHU_JSON_CONTENT_TYPE = "application/json; charset=utf-8"


@dataclass(frozen=True, slots=True)
class FeishuWebhookHttpResponse:
    status_code: int
    body: bytes = b""
    content_type: str = FEISHU_JSON_CONTENT_TYPE


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


def build_feishu_reply_text_func(
    feishu_client: FeishuClient,
) -> Callable[[FeishuPrivateTextEvent, str], Awaitable[object]]:
    async def reply_text(event: FeishuPrivateTextEvent, reply_text: str) -> object:
        return await feishu_client.send_private_text(chat_id=event.chat_id, text=reply_text)

    return reply_text


async def handle_feishu_webhook_http_request(
    *,
    body: bytes | str,
    bot_data: MutableMapping[str, object],
    reply_text_func: Callable[[FeishuPrivateTextEvent, str], Awaitable[object]],
) -> FeishuWebhookHttpResponse:
    try:
        payload = _decode_feishu_webhook_payload(body)
    except ValueError as error:
        print(
            f"\033[31m[Feishu webhook 请求体无效]\033[0m 原因={error}\n"
            "\033[33m[处理建议]\033[0m 检查 Feishu webhook 是否按 JSON 推送，并确认请求体未被代理层改写。"
        )
        return _build_json_response(
            status_code=400,
            payload={"code": 400, "msg": "invalid request body"},
        )

    try:
        challenge = await handle_feishu_private_text_event(
            payload=payload,
            bot_data=bot_data,
            reply_text_func=reply_text_func,
        )
    except Exception as error:
        print(
            f"\033[31m[Feishu webhook 处理失败]\033[0m 原因={error}\n"
            "\033[33m[处理建议]\033[0m 检查 Feishu 配置、shared private-chat runtime 依赖和当前请求内容后重试。"
        )
        return _build_json_response(
            status_code=500,
            payload={"code": 500, "msg": "internal error"},
        )

    if challenge is not None:
        return _build_json_response(status_code=200, payload={"challenge": challenge})
    return _build_json_response(status_code=200, payload={"code": 0})


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


def _decode_feishu_webhook_payload(body: bytes | str) -> Mapping[str, Any]:
    decoded_body = body.decode("utf-8") if isinstance(body, bytes) else body
    cleaned_body = decoded_body.strip()
    if not cleaned_body:
        raise ValueError("empty body")
    try:
        payload = json.loads(cleaned_body)
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid json: {error.msg}") from error
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a json object")
    return payload


def _build_json_response(*, status_code: int, payload: Mapping[str, Any]) -> FeishuWebhookHttpResponse:
    return FeishuWebhookHttpResponse(
        status_code=status_code,
        body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    )

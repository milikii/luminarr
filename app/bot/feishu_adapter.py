from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Awaitable, Callable, Mapping, MutableMapping
from dataclasses import dataclass
from typing import Any

from app.bot.channel_identity import project_channel_chat_id, project_channel_user_id
from app.bot.cleanup_smoke_logging import log_cleanup_private_chat_smoke
from app.bot.private_chat_runtime import dispatch_private_chat_text
from app.clients.feishu import FeishuClient

FEISHU_CHANNEL = "feishu"
FEISHU_URL_VERIFICATION_TYPE = "url_verification"
FEISHU_PRIVATE_TEXT_EVENT_TYPE = "im.message.receive_v1"
FEISHU_JSON_CONTENT_TYPE = "application/json; charset=utf-8"
FEISHU_REQUEST_TIMESTAMP_HEADER = "x-lark-request-timestamp"
FEISHU_REQUEST_NONCE_HEADER = "x-lark-request-nonce"
FEISHU_REQUEST_SIGNATURE_HEADER = "x-lark-signature"
FEISHU_ENCRYPT_KEY_BOT_DATA_KEY = "feishu_encrypt_key"


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
        bot_data=bot_data,
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


async def handle_feishu_webhook_http_request(
    *,
    body: bytes | str,
    headers: Mapping[str, str] | None,
    bot_data: MutableMapping[str, object],
    reply_text_func: Callable[[FeishuPrivateTextEvent, str], Awaitable[object]],
) -> FeishuWebhookHttpResponse:
    raw_body = _normalize_request_body(body)
    try:
        payload = _decode_feishu_webhook_payload(raw_body)
    except ValueError as error:
        print(
            f"\033[31m[Feishu webhook 请求体无效]\033[0m 原因={error}\n"
            "\033[33m[处理建议]\033[0m 检查 Feishu webhook 是否按 JSON 推送，并确认请求体未被代理层改写。"
        )
        return _build_json_response(
            status_code=400,
            payload={"code": 400, "msg": "invalid request body"},
        )

    challenge = get_feishu_url_verification_challenge(payload)
    if challenge is None:
        encrypt_key = str(bot_data.get(FEISHU_ENCRYPT_KEY_BOT_DATA_KEY, "")).strip()
        verification_response = _build_signature_verification_failure_response(
            raw_body=raw_body,
            headers=headers,
            encrypt_key=encrypt_key,
        )
        if verification_response is not None:
            return verification_response

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


def _normalize_request_body(body: bytes | str) -> bytes:
    if isinstance(body, bytes):
        return body
    return body.encode("utf-8")


def _decode_feishu_webhook_payload(body: bytes) -> Mapping[str, Any]:
    decoded_body = body.decode("utf-8")
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


def _build_signature_verification_failure_response(
    *,
    raw_body: bytes,
    headers: Mapping[str, str] | None,
    encrypt_key: str,
) -> FeishuWebhookHttpResponse | None:
    if not encrypt_key:
        print(
            "\033[31m[Feishu webhook 验签配置缺失]\033[0m 未配置 FEISHU_ENCRYPT_KEY。\n"
            "\033[33m[处理建议]\033[0m 配置 FEISHU_ENCRYPT_KEY 后重启服务，再重新发送 Feishu 事件。"
        )
        return _build_json_response(status_code=500, payload={"code": 500, "msg": "feishu signature not configured"})

    normalized_headers = _normalize_headers(headers)
    timestamp = normalized_headers.get(FEISHU_REQUEST_TIMESTAMP_HEADER, "").strip()
    if not timestamp:
        print(
            "\033[31m[Feishu webhook 时间戳缺失]\033[0m 缺少 X-Lark-Request-Timestamp。\n"
            "\033[33m[处理建议]\033[0m 检查 Feishu 事件订阅验签头是否透传到当前 webhook。"
        )
        return _build_json_response(status_code=400, payload={"code": 400, "msg": "missing request timestamp"})
    try:
        int(timestamp)
    except ValueError:
        print(
            f"\033[31m[Feishu webhook 时间戳异常]\033[0m 值={timestamp}\n"
            "\033[33m[处理建议]\033[0m 检查 X-Lark-Request-Timestamp 是否为合法整数。"
        )
        return _build_json_response(status_code=400, payload={"code": 400, "msg": "invalid request timestamp"})

    nonce = normalized_headers.get(FEISHU_REQUEST_NONCE_HEADER, "").strip()
    if not nonce:
        print(
            "\033[31m[Feishu webhook nonce 缺失]\033[0m 缺少 X-Lark-Request-Nonce。\n"
            "\033[33m[处理建议]\033[0m 检查 Feishu 事件订阅验签头是否透传到当前 webhook。"
        )
        return _build_json_response(status_code=401, payload={"code": 401, "msg": "missing request nonce"})

    signature = normalized_headers.get(FEISHU_REQUEST_SIGNATURE_HEADER, "").strip().lower()
    if not signature:
        print(
            "\033[31m[Feishu webhook 签名缺失]\033[0m 缺少 X-Lark-Signature。\n"
            "\033[33m[处理建议]\033[0m 检查 Feishu 事件订阅验签头是否透传到当前 webhook。"
        )
        return _build_json_response(status_code=401, payload={"code": 401, "msg": "missing request signature"})

    expected_signature = _build_expected_signature(
        timestamp=timestamp,
        nonce=nonce,
        encrypt_key=encrypt_key,
        raw_body=raw_body,
    )
    if not hmac.compare_digest(signature, expected_signature):
        print(
            "\033[31m[Feishu webhook 验签失败]\033[0m X-Lark-Signature 不匹配。\n"
            "\033[33m[处理建议]\033[0m 检查 FEISHU_ENCRYPT_KEY、请求体是否被代理改写，以及验签头是否来自 Feishu。"
        )
        return _build_json_response(status_code=401, payload={"code": 401, "msg": "invalid request signature"})
    return None


def _build_expected_signature(
    *,
    timestamp: str,
    nonce: str,
    encrypt_key: str,
    raw_body: bytes,
) -> str:
    signature_source = timestamp.encode("utf-8") + nonce.encode("utf-8") + encrypt_key.encode("utf-8") + raw_body
    return hashlib.sha256(signature_source).hexdigest()


def _normalize_headers(headers: Mapping[str, str] | None) -> dict[str, str]:
    if headers is None:
        return {}
    return {str(key).strip().lower(): str(value).strip() for key, value in headers.items()}


def _build_json_response(*, status_code: int, payload: Mapping[str, Any]) -> FeishuWebhookHttpResponse:
    return FeishuWebhookHttpResponse(
        status_code=status_code,
        body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    )

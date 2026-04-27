from __future__ import annotations

import base64
import binascii
import hashlib
import os
import time
import xml.etree.ElementTree as ET
from collections.abc import Awaitable, Callable, Mapping, MutableMapping
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from app.bot.channel_identity import project_channel_chat_id, project_channel_user_id
from app.bot.cleanup_smoke_logging import log_cleanup_private_chat_smoke
from app.bot.private_chat_runtime import handle_private_chat_query_text as dispatch_private_chat_text

WECOM_CHANNEL = "wecom"
WECOM_XML_CONTENT_TYPE = "application/xml; charset=utf-8"
WECOM_TEXT_CONTENT_TYPE = "text/plain; charset=utf-8"
WECOM_SUCCESS_RESPONSE = b"success"
WECOM_TOKEN_BOT_DATA_KEY = "wecom_token"
WECOM_ENCODING_AES_KEY_BOT_DATA_KEY = "wecom_encoding_aes_key"
WECOM_RECEIVE_ID_BOT_DATA_KEY = "wecom_receive_id"
WECOM_REQUEST_SIGNATURE_QUERY_KEY = "msg_signature"
WECOM_REQUEST_TIMESTAMP_QUERY_KEY = "timestamp"
WECOM_REQUEST_NONCE_QUERY_KEY = "nonce"
WECOM_REQUEST_ECHOSTR_QUERY_KEY = "echostr"
WECOM_PKCS7_BLOCK_SIZE = 32


@dataclass(frozen=True, slots=True)
class WeComWebhookHttpResponse:
    status_code: int
    body: bytes = b""
    content_type: str = WECOM_TEXT_CONTENT_TYPE


@dataclass(frozen=True, slots=True)
class WeComCallbackCryptoConfig:
    token: str
    encoding_aes_key: str
    receive_id: str


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

    chat_id = project_channel_chat_id(
        channel=WECOM_CHANNEL,
        external_chat_id=_resolve_private_chat_external_id(event),
    )
    user_id = project_channel_user_id(
        channel=WECOM_CHANNEL,
        external_user_id=event.user_id,
    )

    async def reply_with_event(reply_text: str) -> object:
        result = await reply_text_func(event, reply_text)
        log_cleanup_private_chat_smoke(
            channel=WECOM_CHANNEL,
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
        channel=WECOM_CHANNEL,
        bot_data=bot_data,
    )
    return event


async def handle_wecom_callback_http_request(
    *,
    method: str,
    query_params: Mapping[str, object] | None,
    body: bytes | str = b"",
    bot_data: MutableMapping[str, object],
) -> WeComWebhookHttpResponse:
    crypto_config = _resolve_callback_crypto_config(bot_data)
    if crypto_config is None:
        print(
            "\033[31m[WeCom callback 配置缺失]\033[0m 缺少 WECOM_TOKEN、WECOM_ENCODING_AES_KEY 或 WECOM_RECEIVE_ID。\n"
            "\033[33m[处理建议]\033[0m 同时配置这三项后重启服务，再重新触发 WeCom 回调。"
        )
        return WeComWebhookHttpResponse(status_code=500, body=b"wecom callback not configured")

    normalized_method = method.strip().upper()
    normalized_query = _normalize_query_params(query_params)
    if normalized_method == "GET":
        return _handle_wecom_callback_url_verification(
            query_params=normalized_query,
            crypto_config=crypto_config,
        )
    if normalized_method != "POST":
        return WeComWebhookHttpResponse(status_code=405, body=b"method not allowed")

    raw_encrypt = _extract_encrypt_from_callback_body(body)
    if not raw_encrypt:
        print(
            "\033[31m[WeCom callback 请求体无效]\033[0m 缺少 Encrypt 节点或 XML 结构不合法。\n"
            "\033[33m[处理建议]\033[0m 检查 WeCom 回调是否开启加密模式，并确认代理层没有改写原始 XML。"
        )
        return WeComWebhookHttpResponse(status_code=400, body=b"invalid callback body")

    decrypted_payload_xml, verification_response = _verify_and_decrypt_ciphertext(
        encrypted_text=raw_encrypt,
        query_params=normalized_query,
        crypto_config=crypto_config,
        request_kind="callback body",
    )
    if verification_response is not None:
        return verification_response

    reply_holder: list[tuple[WeComPrivateTextEvent, str]] = []

    async def capture_reply(event: WeComPrivateTextEvent, reply_text: str) -> object:
        reply_holder.append((event, reply_text))
        return None

    try:
        event = await handle_wecom_private_text_event(
            payload_xml=decrypted_payload_xml,
            bot_data=bot_data,
            reply_text_func=capture_reply,
        )
    except Exception as error:
        print(
            f"\033[31m[WeCom callback 处理失败]\033[0m 原因={error}\n"
            "\033[33m[处理建议]\033[0m 检查 shared private-chat runtime 依赖、WeCom 明文 XML 和当前请求签名后重试。"
        )
        return WeComWebhookHttpResponse(status_code=500, body=b"internal error")

    if event is None or not reply_holder:
        return WeComWebhookHttpResponse(status_code=200, body=WECOM_SUCCESS_RESPONSE)

    _, reply_text = reply_holder[-1]
    timestamp = normalized_query.get(WECOM_REQUEST_TIMESTAMP_QUERY_KEY) or str(int(time.time()))
    nonce = normalized_query.get(WECOM_REQUEST_NONCE_QUERY_KEY) or _build_random_nonce()
    response_xml = _build_encrypted_reply_envelope_xml(
        event=event,
        reply_text=reply_text,
        timestamp=timestamp,
        nonce=nonce,
        crypto_config=crypto_config,
    )
    return WeComWebhookHttpResponse(
        status_code=200,
        body=response_xml.encode("utf-8"),
        content_type=WECOM_XML_CONTENT_TYPE,
    )


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


def _resolve_callback_crypto_config(bot_data: Mapping[str, object]) -> WeComCallbackCryptoConfig | None:
    token = str(bot_data.get(WECOM_TOKEN_BOT_DATA_KEY, "")).strip()
    encoding_aes_key = str(bot_data.get(WECOM_ENCODING_AES_KEY_BOT_DATA_KEY, "")).strip()
    receive_id = str(bot_data.get(WECOM_RECEIVE_ID_BOT_DATA_KEY, "")).strip()
    if not token or not encoding_aes_key or not receive_id:
        return None
    return WeComCallbackCryptoConfig(
        token=token,
        encoding_aes_key=encoding_aes_key,
        receive_id=receive_id,
    )


def _normalize_query_params(query_params: Mapping[str, object] | None) -> dict[str, str]:
    if query_params is None:
        return {}

    normalized: dict[str, str] = {}
    for key, value in query_params.items():
        normalized_key = str(key).strip()
        if not normalized_key:
            continue
        normalized[normalized_key] = _normalize_query_value(value)
    return normalized


def _normalize_query_value(value: object) -> str:
    if isinstance(value, (list, tuple)):
        if not value:
            return ""
        return str(value[0]).strip()
    return str(value or "").strip()


def _handle_wecom_callback_url_verification(
    *,
    query_params: Mapping[str, str],
    crypto_config: WeComCallbackCryptoConfig,
) -> WeComWebhookHttpResponse:
    echostr = query_params.get(WECOM_REQUEST_ECHOSTR_QUERY_KEY, "")
    if not echostr:
        print(
            "\033[31m[WeCom URL 校验参数缺失]\033[0m 缺少 echostr。\n"
            "\033[33m[处理建议]\033[0m 检查 WeCom callback URL 校验请求是否完整透传到当前服务。"
        )
        return WeComWebhookHttpResponse(status_code=400, body=b"missing echostr")

    decrypted_echo, verification_response = _verify_and_decrypt_ciphertext(
        encrypted_text=echostr,
        query_params=query_params,
        crypto_config=crypto_config,
        request_kind="echostr",
    )
    if verification_response is not None:
        return verification_response

    return WeComWebhookHttpResponse(status_code=200, body=decrypted_echo.encode("utf-8"))


def _verify_and_decrypt_ciphertext(
    *,
    encrypted_text: str,
    query_params: Mapping[str, str],
    crypto_config: WeComCallbackCryptoConfig,
    request_kind: str,
) -> tuple[str, WeComWebhookHttpResponse | None]:
    timestamp = query_params.get(WECOM_REQUEST_TIMESTAMP_QUERY_KEY, "")
    nonce = query_params.get(WECOM_REQUEST_NONCE_QUERY_KEY, "")
    signature = query_params.get(WECOM_REQUEST_SIGNATURE_QUERY_KEY, "").lower()

    if not timestamp:
        print(
            "\033[31m[WeCom callback 时间戳缺失]\033[0m 缺少 timestamp。\n"
            "\033[33m[处理建议]\033[0m 检查 WeCom 回调 query string 是否完整透传。"
        )
        return "", WeComWebhookHttpResponse(status_code=400, body=b"missing timestamp")
    if not nonce:
        print(
            "\033[31m[WeCom callback nonce 缺失]\033[0m 缺少 nonce。\n"
            "\033[33m[处理建议]\033[0m 检查 WeCom 回调 query string 是否完整透传。"
        )
        return "", WeComWebhookHttpResponse(status_code=400, body=b"missing nonce")
    if not signature:
        print(
            "\033[31m[WeCom callback 签名缺失]\033[0m 缺少 msg_signature。\n"
            "\033[33m[处理建议]\033[0m 检查 WeCom 回调 query string 是否完整透传。"
        )
        return "", WeComWebhookHttpResponse(status_code=401, body=b"missing msg_signature")

    expected_signature = _build_callback_signature(
        token=crypto_config.token,
        timestamp=timestamp,
        nonce=nonce,
        encrypted_text=encrypted_text,
    )
    if signature != expected_signature:
        print(
            f"\033[31m[WeCom callback 签名校验失败]\033[0m 类型={request_kind}\n"
            "\033[33m[处理建议]\033[0m 检查 WECOM_TOKEN、query string 和加密体是否与 WeCom 原始请求一致。"
        )
        return "", WeComWebhookHttpResponse(status_code=401, body=b"invalid msg_signature")

    try:
        plaintext = _decrypt_wecom_ciphertext(
            encrypted_text=encrypted_text,
            crypto_config=crypto_config,
        )
    except ValueError as error:
        print(
            f"\033[31m[WeCom callback 解密失败]\033[0m 类型={request_kind} 原因={error}\n"
            "\033[33m[处理建议]\033[0m 检查 WECOM_ENCODING_AES_KEY、WECOM_RECEIVE_ID 和回调原始密文是否匹配。"
        )
        return "", WeComWebhookHttpResponse(status_code=400, body=b"invalid encrypted payload")

    return plaintext, None


def _extract_encrypt_from_callback_body(body: bytes | str) -> str:
    normalized_xml = _normalize_xml_payload(body)
    if not normalized_xml:
        return ""
    try:
        root = ET.fromstring(normalized_xml)
    except ET.ParseError:
        return ""
    return _read_xml_text(root, "Encrypt")


def _decrypt_wecom_ciphertext(
    *,
    encrypted_text: str,
    crypto_config: WeComCallbackCryptoConfig,
) -> str:
    aes_key = _decode_encoding_aes_key(crypto_config.encoding_aes_key)
    encrypted_bytes = _decode_wecom_base64(encrypted_text)
    decryptor = Cipher(algorithms.AES(aes_key), modes.CBC(aes_key[:16])).decryptor()
    padded_plaintext = decryptor.update(encrypted_bytes) + decryptor.finalize()
    plaintext = _remove_pkcs7_padding(padded_plaintext)
    if len(plaintext) < 20:
        raise ValueError("解密后的消息体长度不足")

    message_length = int.from_bytes(plaintext[16:20], byteorder="big")
    content_end = 20 + message_length
    if len(plaintext) < content_end:
        raise ValueError("解密后的消息体长度非法")

    message_bytes = plaintext[20:content_end]
    receive_id = plaintext[content_end:].decode("utf-8")
    if receive_id != crypto_config.receive_id:
        raise ValueError(f"receive_id 不匹配：{receive_id}")
    return message_bytes.decode("utf-8")


def _build_encrypted_reply_envelope_xml(
    *,
    event: WeComPrivateTextEvent,
    reply_text: str,
    timestamp: str,
    nonce: str,
    crypto_config: WeComCallbackCryptoConfig,
) -> str:
    reply_payload_xml = _build_wecom_text_reply_xml(event=event, reply_text=reply_text)
    encrypted_reply = _encrypt_wecom_plaintext(
        plaintext=reply_payload_xml,
        crypto_config=crypto_config,
    )
    signature = _build_callback_signature(
        token=crypto_config.token,
        timestamp=timestamp,
        nonce=nonce,
        encrypted_text=encrypted_reply,
    )
    return (
        "<xml>"
        f"<Encrypt><![CDATA[{encrypted_reply}]]></Encrypt>"
        f"<MsgSignature><![CDATA[{signature}]]></MsgSignature>"
        f"<TimeStamp>{timestamp}</TimeStamp>"
        f"<Nonce><![CDATA[{nonce}]]></Nonce>"
        "</xml>"
    )


def _build_wecom_text_reply_xml(*, event: WeComPrivateTextEvent, reply_text: str) -> str:
    create_time = str(int(time.time()))
    return (
        "<xml>"
        f"<ToUserName><![CDATA[{event.user_id}]]></ToUserName>"
        f"<FromUserName><![CDATA[{event.corp_id}]]></FromUserName>"
        f"<CreateTime>{create_time}</CreateTime>"
        "<MsgType><![CDATA[text]]></MsgType>"
        f"<Content><![CDATA[{reply_text}]]></Content>"
        "</xml>"
    )


def _encrypt_wecom_plaintext(
    *,
    plaintext: str,
    crypto_config: WeComCallbackCryptoConfig,
) -> str:
    aes_key = _decode_encoding_aes_key(crypto_config.encoding_aes_key)
    message_bytes = plaintext.encode("utf-8")
    raw_plaintext = (
        os.urandom(16)
        + len(message_bytes).to_bytes(4, byteorder="big")
        + message_bytes
        + crypto_config.receive_id.encode("utf-8")
    )
    padded_plaintext = _add_pkcs7_padding(raw_plaintext)
    encryptor = Cipher(algorithms.AES(aes_key), modes.CBC(aes_key[:16])).encryptor()
    encrypted_bytes = encryptor.update(padded_plaintext) + encryptor.finalize()
    return base64.b64encode(encrypted_bytes).decode("utf-8")


def _build_callback_signature(
    *,
    token: str,
    timestamp: str,
    nonce: str,
    encrypted_text: str,
) -> str:
    signature_source = "".join(sorted((token, timestamp, nonce, encrypted_text)))
    return hashlib.sha1(signature_source.encode("utf-8")).hexdigest()


def _decode_encoding_aes_key(encoding_aes_key: str) -> bytes:
    try:
        aes_key = base64.b64decode(f"{encoding_aes_key.strip()}=", validate=True)
    except binascii.Error as error:
        raise ValueError("EncodingAESKey 不是合法的 base64 字符串") from error
    if len(aes_key) != 32:
        raise ValueError(f"EncodingAESKey 解码后长度异常：{len(aes_key)}")
    return aes_key


def _decode_wecom_base64(raw_value: str) -> bytes:
    normalized_value = raw_value.strip().replace(" ", "+")
    padding_needed = (-len(normalized_value)) % 4
    normalized_value = normalized_value + ("=" * padding_needed)
    try:
        return base64.b64decode(normalized_value, validate=True)
    except binascii.Error as error:
        raise ValueError("密文不是合法的 base64 字符串") from error


def _add_pkcs7_padding(raw_value: bytes) -> bytes:
    padding_length = WECOM_PKCS7_BLOCK_SIZE - (len(raw_value) % WECOM_PKCS7_BLOCK_SIZE)
    if padding_length == 0:
        padding_length = WECOM_PKCS7_BLOCK_SIZE
    return raw_value + bytes([padding_length]) * padding_length


def _remove_pkcs7_padding(raw_value: bytes) -> bytes:
    if not raw_value:
        raise ValueError("解密后的消息体为空")
    padding_length = raw_value[-1]
    if padding_length <= 0 or padding_length > WECOM_PKCS7_BLOCK_SIZE:
        raise ValueError("PKCS7 padding 非法")
    if raw_value[-padding_length:] != bytes([padding_length]) * padding_length:
        raise ValueError("PKCS7 padding 校验失败")
    return raw_value[:-padding_length]


def _build_random_nonce() -> str:
    return hashlib.sha1(os.urandom(16)).hexdigest()[:16]

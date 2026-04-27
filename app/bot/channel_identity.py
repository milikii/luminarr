from __future__ import annotations

import hashlib

from app.operational_logging import emit_operational_log


def project_channel_chat_id(*, channel: str, external_chat_id: str) -> int | None:
    return _project_channel_identity(
        channel=channel,
        principal_kind="chat",
        external_id=external_chat_id,
    )


def project_channel_user_id(*, channel: str, external_user_id: str) -> int | None:
    return _project_channel_identity(
        channel=channel,
        principal_kind="user",
        external_id=external_user_id,
    )


def _project_channel_identity(
    *,
    channel: str,
    principal_kind: str,
    external_id: str,
) -> int | None:
    cleaned_channel = channel.strip().lower()
    cleaned_kind = principal_kind.strip().lower()
    cleaned_external_id = external_id.strip()
    if not cleaned_channel or not cleaned_kind or not cleaned_external_id:
        emit_operational_log(
            title="渠道身份缺失",
            detail=f"channel={cleaned_channel or '-'} principal={cleaned_kind or '-'} external_id={cleaned_external_id or '-'}",
            fix_hint="检查渠道适配层是否把 chat_id/user_id 解析为空，并确认当前事件确实来自私聊文本入口。",
        )
        return None

    digest = hashlib.sha256(
        f"{cleaned_channel}:{cleaned_kind}:{cleaned_external_id}".encode("utf-8")
    ).digest()
    projected_id = int.from_bytes(digest[:8], "big") & 0x7FFF_FFFF_FFFF_FFFF
    return projected_id or 1

from __future__ import annotations

import hashlib


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
        return None

    digest = hashlib.sha256(
        f"{cleaned_channel}:{cleaned_kind}:{cleaned_external_id}".encode("utf-8")
    ).digest()
    projected_id = int.from_bytes(digest[:8], "big") & 0x7FFF_FFFF_FFFF_FFFF
    return projected_id or 1

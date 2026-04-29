from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass


CHANNEL_CONTACT_REGISTRY_KEY = "channel_contact_registry"


@dataclass(frozen=True, slots=True)
class ChannelContact:
    channel: str
    internal_chat_id: int
    external_chat_id: str
    external_user_id: str | None = None


class ChannelContactRegistry:
    def __init__(self) -> None:
        self._by_internal_chat_id: dict[int, ChannelContact] = {}

    def record(self, contact: ChannelContact) -> None:
        self._by_internal_chat_id[contact.internal_chat_id] = contact

    def resolve(self, internal_chat_id: int) -> ChannelContact | None:
        return self._by_internal_chat_id.get(internal_chat_id)


def record_channel_contact(
    bot_data: MutableMapping[str, object],
    *,
    channel: str,
    internal_chat_id: int | None,
    external_chat_id: str | None,
    external_user_id: str | None = None,
) -> bool:
    registry = _resolve_channel_contact_registry(bot_data)
    if registry is None:
        return False

    if not isinstance(channel, str) or not isinstance(external_chat_id, str):
        return False
    cleaned_channel = channel.strip().lower()
    cleaned_external_chat_id = external_chat_id.strip()
    cleaned_external_user_id = external_user_id.strip() if isinstance(external_user_id, str) else ""
    if not cleaned_channel or not cleaned_external_chat_id:
        return False
    if not isinstance(internal_chat_id, int) or isinstance(internal_chat_id, bool) or internal_chat_id <= 0:
        return False

    registry.record(
        ChannelContact(
            channel=cleaned_channel,
            internal_chat_id=internal_chat_id,
            external_chat_id=cleaned_external_chat_id,
            external_user_id=cleaned_external_user_id or None,
        )
    )
    return True


def resolve_channel_contact(
    bot_data: Mapping[str, object],
    *,
    internal_chat_id: int | None,
) -> ChannelContact | None:
    registry = _resolve_channel_contact_registry(bot_data)
    if registry is None:
        return None
    if not isinstance(internal_chat_id, int) or isinstance(internal_chat_id, bool) or internal_chat_id <= 0:
        return None
    return registry.resolve(internal_chat_id)


def _resolve_channel_contact_registry(
    bot_data: Mapping[str, object],
) -> ChannelContactRegistry | None:
    registry = bot_data.get(CHANNEL_CONTACT_REGISTRY_KEY)
    if not isinstance(registry, ChannelContactRegistry):
        return None
    return registry

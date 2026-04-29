from __future__ import annotations

from app.bot.channel_contact_runtime import (
    CHANNEL_CONTACT_REGISTRY_KEY,
    ChannelContact,
    ChannelContactRegistry,
    record_channel_contact,
    resolve_channel_contact,
)


def test_record_and_resolve_channel_contact_round_trip() -> None:
    registry = ChannelContactRegistry()
    bot_data = {CHANNEL_CONTACT_REGISTRY_KEY: registry}

    assert (
        record_channel_contact(
            bot_data,
            channel="feishu",
            internal_chat_id=123,
            external_chat_id="oc_1",
            external_user_id="ou_1",
        )
        is True
    )
    assert resolve_channel_contact(bot_data, internal_chat_id=123) == ChannelContact(
        channel="feishu",
        internal_chat_id=123,
        external_chat_id="oc_1",
        external_user_id="ou_1",
    )


def test_channel_contact_registry_fail_closed_on_bad_input() -> None:
    bot_data = {CHANNEL_CONTACT_REGISTRY_KEY: ChannelContactRegistry()}

    assert (
        record_channel_contact(
            bot_data,
            channel="",
            internal_chat_id=123,
            external_chat_id="oc_1",
        )
        is False
    )
    assert (
        record_channel_contact(
            bot_data,
            channel="feishu",
            internal_chat_id=None,
            external_chat_id="oc_1",
        )
        is False
    )
    assert (
        record_channel_contact(
            bot_data,
            channel="feishu",
            internal_chat_id=123,
            external_chat_id="",
        )
        is False
    )
    assert resolve_channel_contact(bot_data, internal_chat_id=None) is None
    assert resolve_channel_contact({}, internal_chat_id=123) is None

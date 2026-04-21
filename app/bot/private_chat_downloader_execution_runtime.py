from __future__ import annotations

from collections.abc import MutableMapping

from app.bot.downloader_execution_runtime import resolve_bound_downloader_execution


def resolve_private_chat_bound_downloader_execution(
    *,
    bot_data: MutableMapping[str, object],
    role: str,
    tg,
):
    return resolve_bound_downloader_execution(
        bot_data=bot_data,
        role=role,
        downloader_role_binding_key=tg.DOWNLOADER_ROLE_BINDING_KEY,
        downloader_instances_key=tg.DOWNLOADER_INSTANCES_KEY,
        config_missing_template=tg.DOWNLOADER_EXECUTION_CONFIG_MISSING_TEMPLATE,
    )

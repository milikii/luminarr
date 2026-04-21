from __future__ import annotations

from collections.abc import MutableMapping

from telegram.ext import Application, ContextTypes

from app.bot.downloader_execution_runtime import (
    ResolvedDownloaderExecution,
    resolve_bound_downloader_execution,
    resolve_downloader_instances,
)
from app.config import DownloaderInstanceConfig


def resolve_telegram_downloader_instances(
    *,
    bot_data: MutableMapping[str, object],
    tg,
) -> dict[str, DownloaderInstanceConfig]:
    return resolve_downloader_instances(
        bot_data=bot_data,
        downloader_instances_key=tg.DOWNLOADER_INSTANCES_KEY,
    )


def resolve_telegram_bound_downloader_execution(
    *,
    bot_data: MutableMapping[str, object],
    role: str,
    tg,
) -> tuple[ResolvedDownloaderExecution | None, str | None]:
    return resolve_bound_downloader_execution(
        bot_data=bot_data,
        role=role,
        downloader_role_binding_key=tg.DOWNLOADER_ROLE_BINDING_KEY,
        downloader_instances_key=tg.DOWNLOADER_INSTANCES_KEY,
        config_missing_template=tg.DOWNLOADER_EXECUTION_CONFIG_MISSING_TEMPLATE,
    )


def resolve_telegram_bound_downloader_execution_from_context(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    role: str,
    tg,
) -> tuple[ResolvedDownloaderExecution | None, str | None]:
    return resolve_telegram_bound_downloader_execution(
        bot_data=context.application.bot_data,
        role=role,
        tg=tg,
    )


def resolve_telegram_downloader_instances_for_application(
    *,
    application: Application,
    tg,
) -> dict[str, DownloaderInstanceConfig]:
    return resolve_telegram_downloader_instances(
        bot_data=application.bot_data,
        tg=tg,
    )

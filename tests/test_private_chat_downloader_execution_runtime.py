from __future__ import annotations

from app.bot import telegram_bot as tg
from app.bot.private_chat_downloader_execution_runtime import (
    resolve_private_chat_bound_downloader_execution,
)
from app.config import DownloaderInstanceConfig, DownloaderRoleBinding


def test_resolve_private_chat_bound_downloader_execution_returns_none_without_binding() -> None:
    downloader_execution, resolution_error = resolve_private_chat_bound_downloader_execution(
        bot_data={},
        role="bt",
        tg=tg,
    )

    assert downloader_execution is None
    assert resolution_error is None


def test_resolve_private_chat_bound_downloader_execution_resolves_bound_instance() -> None:
    downloader_execution, resolution_error = resolve_private_chat_bound_downloader_execution(
        bot_data={
            tg.DOWNLOADER_ROLE_BINDING_KEY: DownloaderRoleBinding(pt_downloader="pt", bt_downloader="bt"),
            tg.DOWNLOADER_INSTANCES_KEY: (
                DownloaderInstanceConfig(
                    name="bt",
                    downloader_type="qbittorrent",
                    base_url="http://127.0.0.1:18098",
                    download_dir="/downloads/bt",
                ),
            ),
        },
        role="bt",
        tg=tg,
    )

    assert resolution_error is None
    assert downloader_execution is not None
    assert downloader_execution.name == "bt"
    assert downloader_execution.downloader_type == "qbittorrent"
    assert downloader_execution.download_dir == "/downloads/bt"


def test_resolve_private_chat_bound_downloader_execution_replies_config_missing() -> None:
    downloader_execution, resolution_error = resolve_private_chat_bound_downloader_execution(
        bot_data={
            tg.DOWNLOADER_ROLE_BINDING_KEY: DownloaderRoleBinding(pt_downloader="", bt_downloader="missing"),
            tg.DOWNLOADER_INSTANCES_KEY: (),
        },
        role="bt",
        tg=tg,
    )

    assert downloader_execution is None
    assert resolution_error == tg.DOWNLOADER_EXECUTION_CONFIG_MISSING_TEMPLATE.format(
        role="BT",
        name="missing",
    )

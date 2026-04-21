from __future__ import annotations

from types import SimpleNamespace

from app.bot import telegram_bot as tg
from app.bot.telegram_downloader_execution_runtime import (
    resolve_telegram_bound_downloader_execution,
    resolve_telegram_bound_downloader_execution_from_context,
    resolve_telegram_downloader_instances_for_application,
)
from app.config import DownloaderInstanceConfig, DownloaderRoleBinding


def test_resolve_telegram_bound_downloader_execution_returns_none_without_binding() -> None:
    downloader_execution, resolution_error = resolve_telegram_bound_downloader_execution(
        bot_data={},
        role="bt",
        tg=tg,
    )

    assert downloader_execution is None
    assert resolution_error is None


def test_resolve_telegram_bound_downloader_execution_from_context_resolves_bound_instance() -> None:
    context = SimpleNamespace(
        application=SimpleNamespace(
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
            }
        )
    )

    downloader_execution, resolution_error = resolve_telegram_bound_downloader_execution_from_context(
        context=context,
        role="bt",
        tg=tg,
    )

    assert resolution_error is None
    assert downloader_execution is not None
    assert downloader_execution.name == "bt"
    assert downloader_execution.downloader_type == "qbittorrent"
    assert downloader_execution.download_dir == "/downloads/bt"


def test_resolve_telegram_downloader_instances_for_application_ignores_non_config_entries() -> None:
    application = SimpleNamespace(
        bot_data={
            tg.DOWNLOADER_INSTANCES_KEY: (
                "invalid",
                DownloaderInstanceConfig(
                    name="bt",
                    downloader_type="qbittorrent",
                    base_url="http://127.0.0.1:18098",
                    download_dir="/downloads/bt",
                ),
            )
        }
    )

    instances = resolve_telegram_downloader_instances_for_application(
        application=application,
        tg=tg,
    )

    assert list(instances) == ["bt"]

from __future__ import annotations

from collections.abc import MutableMapping
from dataclasses import dataclass

from app.config import DownloaderInstanceConfig, DownloaderRoleBinding


@dataclass(frozen=True, slots=True)
class ResolvedDownloaderExecution:
    name: str
    downloader_type: str
    download_dir: str


def resolve_downloader_instances(
    *,
    bot_data: MutableMapping[str, object],
    downloader_instances_key: str,
) -> dict[str, DownloaderInstanceConfig]:
    raw_instances = bot_data.get(downloader_instances_key)
    resolved_instances: dict[str, DownloaderInstanceConfig] = {}
    if not isinstance(raw_instances, tuple):
        return resolved_instances
    for instance in raw_instances:
        if isinstance(instance, DownloaderInstanceConfig):
            resolved_instances[instance.name] = instance
    return resolved_instances


def resolve_bound_downloader_execution(
    *,
    bot_data: MutableMapping[str, object],
    role: str,
    downloader_role_binding_key: str,
    downloader_instances_key: str,
    config_missing_template: str,
) -> tuple[ResolvedDownloaderExecution | None, str | None]:
    role_binding = bot_data.get(downloader_role_binding_key)
    if not isinstance(role_binding, DownloaderRoleBinding):
        return None, None

    role_name = "PT" if role == "pt" else "BT"
    downloader_name = role_binding.pt_downloader if role == "pt" else role_binding.bt_downloader
    cleaned_name = downloader_name.strip()
    if not cleaned_name:
        return None, None

    instances_by_name = resolve_downloader_instances(
        bot_data=bot_data,
        downloader_instances_key=downloader_instances_key,
    )
    instance = instances_by_name.get(cleaned_name)
    if instance is None:
        return None, config_missing_template.format(role=role_name, name=cleaned_name)

    return (
        ResolvedDownloaderExecution(
            name=instance.name,
            downloader_type=instance.downloader_type,
            download_dir=instance.download_dir,
        ),
        None,
    )

from __future__ import annotations

import json

from app.clients.qbittorrent import QbittorrentClient
from app.clients.transmission import TransmissionClient, TransmissionImportSource, TransmissionTaskStatus
from app.config import DownloaderInstanceConfig
from app.db.job_repo import JobRepo


class DownloaderRouteLookupError(RuntimeError):
    pass


def _resolve_downloader_payload_value(payload_json: str, key: str) -> tuple[str, str | None]:
    cleaned_payload = payload_json.strip()
    if not cleaned_payload:
        return "", "payload_json empty"
    try:
        payload = json.loads(cleaned_payload)
    except json.JSONDecodeError:
        return "", "payload_json invalid json"
    if not isinstance(payload, dict):
        return "", "payload_json not object"
    return str(payload.get(key, "")).strip(), None


def _log_downloader_route_lookup_failure(*, task_ref: str, chat_id: int | None, reason: str) -> None:
    print(
        f"\033[31m[下载器路由未命中]\033[0m task_ref={task_ref} chat_id={chat_id if chat_id is not None else '-'} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查当前任务是否已写入 downloader job、payload 里是否保留了 downloader_name，"
        "并确认状态/导入查询使用的是同一私聊会话。",
        flush=True,
    )


def _log_downloader_route_lookup_error(*, task_ref: str, chat_id: int | None, error: Exception) -> None:
    print(
        f"\033[31m[下载器路由查询失败]\033[0m task_ref={task_ref} chat_id={chat_id if chat_id is not None else '-'} 错误={error}\n"
        "\033[33m[处理建议]\033[0m 检查 SQLite/jobs 表读取是否正常，并确认当前任务引用仍能命中 downloader job 真相。",
        flush=True,
    )


def _log_downloader_route_payload_corruption(
    *,
    task_ref: str,
    chat_id: int | None,
    reason: str,
) -> None:
    print(
        f"\033[31m[下载器路由载荷损坏]\033[0m task_ref={task_ref} chat_id={chat_id if chat_id is not None else '-'} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 jobs.payload_json 是否仍保留合法 JSON，且包含 downloader_name。",
        flush=True,
    )


def _resolve_downloader_name_for_task(
    *,
    task_ref: str,
    chat_id: int | None,
    job_repo: JobRepo,
) -> str | None:
    if chat_id is None or chat_id <= 0:
        _log_downloader_route_lookup_failure(task_ref=task_ref, chat_id=chat_id, reason="chat_id missing")
        return None
    try:
        downloader_job = job_repo.get_downloader_job_for_chat_ref(chat_id=chat_id, task_ref=task_ref)
    except Exception as error:
        _log_downloader_route_lookup_error(task_ref=task_ref, chat_id=chat_id, error=error)
        return None
    if downloader_job is None:
        _log_downloader_route_lookup_failure(task_ref=task_ref, chat_id=chat_id, reason="downloader job missing")
        return None
    downloader_name, payload_error = _resolve_downloader_payload_value(
        downloader_job.payload_json,
        "downloader_name",
    )
    if payload_error is not None:
        _log_downloader_route_payload_corruption(
            task_ref=task_ref,
            chat_id=chat_id,
            reason=payload_error,
        )
        return None
    if downloader_name:
        return downloader_name
    _log_downloader_route_lookup_failure(task_ref=task_ref, chat_id=chat_id, reason="downloader_name missing")
    return None


def _log_downloader_instance_missing(*, downloader_name: str) -> None:
    print(
        f"\033[31m[下载器实例不存在]\033[0m downloader_name={downloader_name}\n"
        "\033[33m[处理建议]\033[0m 检查当前任务 payload 里的 downloader_name 是否仍存在于 DOWNLOADER_INSTANCES，"
        "并确认角色绑定或历史任务没有引用已删除的实例名。",
        flush=True,
    )


def _log_downloader_client_not_configured(*, downloader_name: str, downloader_type: str) -> None:
    print(
        f"\033[31m[下载器客户端未配置]\033[0m downloader_name={downloader_name} downloader_type={downloader_type}\n"
        "\033[33m[处理建议]\033[0m 检查应用启动阶段是否已按 DOWNLOADER_INSTANCES 创建对应下载器 client，"
        "并确认当前实例的 base_url / 用户名密码没有让这条配置在装配时被跳过。",
        flush=True,
    )


def _log_downloader_dispatch_resolution_failed(
    *,
    downloader_name: str,
    downloader_type: str,
    reason: str,
) -> None:
    print(
        f"\033[31m[下载器投递路由失败]\033[0m downloader_name={downloader_name} "
        f"downloader_type={downloader_type or '-'} 原因={reason}\n"
        "\033[33m[处理建议]\033[0m 检查 DOWNLOADER_INSTANCES、下载器角色绑定和应用启动阶段的 client 装配是否一致，"
        "再重试当前下载投递。",
        flush=True,
    )


def _resolve_downloader_client_for_lookup(
    *,
    downloader_name: str,
    downloader_instances_by_name: dict[str, DownloaderInstanceConfig],
    transmission_clients_by_name: dict[str, TransmissionClient],
    qbittorrent_clients_by_name: dict[str, QbittorrentClient],
) -> TransmissionClient | QbittorrentClient | None:
    cleaned_name = downloader_name.strip()
    instance = downloader_instances_by_name.get(cleaned_name)
    if instance is None:
        _log_downloader_instance_missing(downloader_name=cleaned_name or "-")
        return None
    if instance.downloader_type == "qbittorrent":
        client = qbittorrent_clients_by_name.get(cleaned_name)
    else:
        client = transmission_clients_by_name.get(cleaned_name)
    if client is None:
        _log_downloader_client_not_configured(
            downloader_name=cleaned_name or "-",
            downloader_type=instance.downloader_type,
        )
        return None
    return client


def _resolve_downloader_client_for_dispatch(
    *,
    downloader_name: str,
    transmission_client: TransmissionClient,
    downloader_instances_by_name: dict[str, DownloaderInstanceConfig],
    transmission_clients_by_name: dict[str, TransmissionClient],
    qbittorrent_clients_by_name: dict[str, QbittorrentClient],
) -> TransmissionClient | QbittorrentClient:
    cleaned_name = downloader_name.strip()
    if not cleaned_name:
        return transmission_client
    instance = downloader_instances_by_name.get(cleaned_name)
    if instance is None:
        _log_downloader_dispatch_resolution_failed(
            downloader_name=cleaned_name,
            downloader_type="-",
            reason="instance missing",
        )
        raise ValueError(f"unknown downloader instance: {cleaned_name}")
    if instance.downloader_type == "qbittorrent":
        client = qbittorrent_clients_by_name.get(cleaned_name)
    else:
        client = transmission_clients_by_name.get(cleaned_name)
    if client is None:
        _log_downloader_dispatch_resolution_failed(
            downloader_name=cleaned_name,
            downloader_type=instance.downloader_type,
            reason="client not configured",
        )
        raise ValueError(f"downloader client not configured: {cleaned_name}")
    return client


async def _get_torrent_import_source_with_routing(
    *,
    task_ref: str,
    chat_id: int | None,
    job_repo: JobRepo,
    downloader_instances_by_name: dict[str, DownloaderInstanceConfig],
    transmission_clients_by_name: dict[str, TransmissionClient],
    qbittorrent_clients_by_name: dict[str, QbittorrentClient],
) -> TransmissionImportSource | None:
    downloader_name = _resolve_downloader_name_for_task(
        task_ref=task_ref,
        chat_id=chat_id,
        job_repo=job_repo,
    )
    if downloader_name is None:
        raise DownloaderRouteLookupError(f"downloader route unavailable for import task: {task_ref}")
    client = _resolve_downloader_client_for_lookup(
        downloader_name=downloader_name,
        downloader_instances_by_name=downloader_instances_by_name,
        transmission_clients_by_name=transmission_clients_by_name,
        qbittorrent_clients_by_name=qbittorrent_clients_by_name,
    )
    if client is None:
        raise DownloaderRouteLookupError(f"downloader client unavailable for import task: {task_ref}")
    return await client.get_torrent_import_source(task_ref)


async def _get_torrent_status_with_routing(
    *,
    task_ref: str,
    chat_id: int | None,
    job_repo: JobRepo,
    downloader_instances_by_name: dict[str, DownloaderInstanceConfig],
    transmission_clients_by_name: dict[str, TransmissionClient],
    qbittorrent_clients_by_name: dict[str, QbittorrentClient],
) -> TransmissionTaskStatus | None:
    downloader_name = _resolve_downloader_name_for_task(
        task_ref=task_ref,
        chat_id=chat_id,
        job_repo=job_repo,
    )
    if downloader_name is None:
        raise DownloaderRouteLookupError(f"downloader route unavailable for status task: {task_ref}")
    client = _resolve_downloader_client_for_lookup(
        downloader_name=downloader_name,
        downloader_instances_by_name=downloader_instances_by_name,
        transmission_clients_by_name=transmission_clients_by_name,
        qbittorrent_clients_by_name=qbittorrent_clients_by_name,
    )
    if client is None:
        raise DownloaderRouteLookupError(f"downloader client unavailable for status task: {task_ref}")
    return await client.get_torrent_status(task_ref)


async def _remove_torrent_with_routing(
    *,
    task_ref: str,
    chat_id: int | None,
    job_repo: JobRepo,
    downloader_instances_by_name: dict[str, DownloaderInstanceConfig],
    transmission_clients_by_name: dict[str, TransmissionClient],
    qbittorrent_clients_by_name: dict[str, QbittorrentClient],
    delete_local_data: bool,
) -> None:
    downloader_name = _resolve_downloader_name_for_task(
        task_ref=task_ref,
        chat_id=chat_id,
        job_repo=job_repo,
    )
    if downloader_name is None:
        raise DownloaderRouteLookupError(f"downloader route unavailable for remove task: {task_ref}")
    client = _resolve_downloader_client_for_lookup(
        downloader_name=downloader_name,
        downloader_instances_by_name=downloader_instances_by_name,
        transmission_clients_by_name=transmission_clients_by_name,
        qbittorrent_clients_by_name=qbittorrent_clients_by_name,
    )
    if client is None:
        raise DownloaderRouteLookupError(f"downloader client unavailable for remove task: {task_ref}")
    await client.remove_torrent(task_ref, delete_local_data=delete_local_data)

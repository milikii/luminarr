from __future__ import annotations

import json
from dataclasses import dataclass

from app.clients.qbittorrent import QbittorrentClient
from app.clients.transmission import TransmissionClient, TransmissionImportSource, TransmissionTaskStatus
from app.config import DownloaderInstanceConfig
from app.db.job_repo import JobRepo


class DownloaderRouteLookupError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ResolvedDownloaderTaskRoute:
    downloader_name: str
    download_dir: str


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


def _print_downloader_route_lookup_log(
    *,
    title: str,
    task_ref: str,
    chat_id: int | None,
    detail_label: str,
    detail_value: str,
    fix_hint: str,
) -> None:
    print(
        f"\033[31m[{title}]\033[0m task_ref={task_ref} chat_id={chat_id if chat_id is not None else '-'} "
        f"{detail_label}={detail_value}\n"
        f"\033[33m[处理建议]\033[0m {fix_hint}",
        flush=True,
    )


def _print_downloader_dispatch_log(
    *,
    title: str,
    downloader_name: str,
    downloader_type: str,
    detail_label: str,
    detail_value: str,
    fix_hint: str,
) -> None:
    print(
        f"\033[31m[{title}]\033[0m downloader_name={downloader_name or '-'} "
        f"downloader_type={downloader_type or '-'} {detail_label}={detail_value}\n"
        f"\033[33m[处理建议]\033[0m {fix_hint}",
        flush=True,
    )


def _log_downloader_route_lookup_failure(*, task_ref: str, chat_id: int | None, reason: str) -> None:
    _print_downloader_route_lookup_log(
        title="下载器路由未命中",
        task_ref=task_ref,
        chat_id=chat_id,
        detail_label="原因",
        detail_value=reason,
        fix_hint="检查当前任务是否已写入 downloader job、payload 里是否保留了 downloader_name，并确认状态/导入查询使用的是同一私聊会话。",
    )


def _log_downloader_route_lookup_error(*, task_ref: str, chat_id: int | None, error: Exception) -> None:
    _print_downloader_route_lookup_log(
        title="下载器路由查询失败",
        task_ref=task_ref,
        chat_id=chat_id,
        detail_label="错误",
        detail_value=str(error),
        fix_hint="检查 SQLite/jobs 表读取是否正常，并确认当前任务引用仍能命中 downloader job 真相。",
    )


def _log_downloader_route_payload_corruption(
    *,
    task_ref: str,
    chat_id: int | None,
    reason: str,
) -> None:
    _print_downloader_route_lookup_log(
        title="下载器路由载荷损坏",
        task_ref=task_ref,
        chat_id=chat_id,
        detail_label="原因",
        detail_value=reason,
        fix_hint="检查 jobs.payload_json 是否仍保留合法 JSON，且包含 downloader_name。",
    )


def _resolve_downloader_task_route(
    *,
    task_ref: str,
    chat_id: int | None,
    job_repo: JobRepo,
) -> ResolvedDownloaderTaskRoute | None:
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
    if not downloader_name:
        _log_downloader_route_lookup_failure(task_ref=task_ref, chat_id=chat_id, reason="downloader_name missing")
        return None
    download_dir, payload_error = _resolve_downloader_payload_value(
        downloader_job.payload_json,
        "download_dir",
    )
    if payload_error is not None:
        _log_downloader_route_payload_corruption(
            task_ref=task_ref,
            chat_id=chat_id,
            reason=payload_error,
        )
        return None
    return ResolvedDownloaderTaskRoute(
        downloader_name=downloader_name,
        download_dir=download_dir,
    )


def _normalize_import_source_download_dir(
    *,
    import_source: TransmissionImportSource,
    host_download_dir: str,
) -> TransmissionImportSource:
    cleaned_download_dir = host_download_dir.strip()
    if not cleaned_download_dir or cleaned_download_dir == import_source.download_dir:
        return import_source
    return TransmissionImportSource(
        task_id=import_source.task_id,
        task_hash=import_source.task_hash,
        name=import_source.name,
        download_dir=cleaned_download_dir,
        is_finished=import_source.is_finished,
        percent_done=import_source.percent_done,
    )


def _resolve_host_download_dir_for_route(
    *,
    route: ResolvedDownloaderTaskRoute,
    downloader_instances_by_name: dict[str, DownloaderInstanceConfig],
) -> str:
    if route.download_dir.strip():
        return route.download_dir
    instance = downloader_instances_by_name.get(route.downloader_name)
    if instance is None:
        return ""
    return instance.download_dir


def _resolve_lookup_client_for_task(
    *,
    task_ref: str,
    chat_id: int | None,
    job_repo: JobRepo,
    downloader_instances_by_name: dict[str, DownloaderInstanceConfig],
    transmission_clients_by_name: dict[str, TransmissionClient],
    qbittorrent_clients_by_name: dict[str, QbittorrentClient],
    operation: str,
) -> tuple[ResolvedDownloaderTaskRoute, TransmissionClient | QbittorrentClient]:
    route = _resolve_downloader_task_route(
        task_ref=task_ref,
        chat_id=chat_id,
        job_repo=job_repo,
    )
    if route is None:
        raise DownloaderRouteLookupError(f"downloader route unavailable for {operation} task: {task_ref}")
    client = _resolve_downloader_client_for_lookup(
        downloader_name=route.downloader_name,
        downloader_instances_by_name=downloader_instances_by_name,
        transmission_clients_by_name=transmission_clients_by_name,
        qbittorrent_clients_by_name=qbittorrent_clients_by_name,
    )
    if client is None:
        raise DownloaderRouteLookupError(f"downloader client unavailable for {operation} task: {task_ref}")
    return route, client


def _resolve_downloader_name_for_task(
    *,
    task_ref: str,
    chat_id: int | None,
    job_repo: JobRepo,
) -> str | None:
    route = _resolve_downloader_task_route(
        task_ref=task_ref,
        chat_id=chat_id,
        job_repo=job_repo,
    )
    if route is None:
        return None
    return route.downloader_name


def _log_downloader_instance_missing(*, downloader_name: str) -> None:
    _print_downloader_dispatch_log(
        title="下载器实例不存在",
        downloader_name=downloader_name,
        downloader_type="-",
        detail_label="原因",
        detail_value="instance missing",
        fix_hint="检查当前任务 payload 里的 downloader_name 是否仍存在于 DOWNLOADER_INSTANCES，并确认角色绑定或历史任务没有引用已删除的实例名。",
    )


def _log_downloader_client_not_configured(*, downloader_name: str, downloader_type: str) -> None:
    _print_downloader_dispatch_log(
        title="下载器客户端未配置",
        downloader_name=downloader_name,
        downloader_type=downloader_type,
        detail_label="原因",
        detail_value="client missing",
        fix_hint="检查应用启动阶段是否已按 DOWNLOADER_INSTANCES 创建对应下载器 client，并确认当前实例的 base_url / 用户名密码没有让这条配置在装配时被跳过。",
    )


def _log_downloader_dispatch_resolution_failed(
    *,
    downloader_name: str,
    downloader_type: str,
    reason: str,
) -> None:
    _print_downloader_dispatch_log(
        title="下载器投递路由失败",
        downloader_name=downloader_name,
        downloader_type=downloader_type,
        detail_label="原因",
        detail_value=reason,
        fix_hint="检查 DOWNLOADER_INSTANCES、下载器角色绑定和应用启动阶段的 client 装配是否一致，再重试当前下载投递。",
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


def resolve_downloader_dispatch_download_dir(
    *,
    downloader_name: str,
    requested_download_dir: str,
    downloader_instances_by_name: dict[str, DownloaderInstanceConfig],
) -> str:
    cleaned_download_dir = requested_download_dir.strip()
    cleaned_name = downloader_name.strip()
    if not cleaned_download_dir or not cleaned_name:
        return cleaned_download_dir
    instance = downloader_instances_by_name.get(cleaned_name)
    if instance is None:
        return cleaned_download_dir
    dispatch_download_dir = instance.dispatch_download_dir.strip()
    if not dispatch_download_dir:
        return cleaned_download_dir
    if cleaned_download_dir != instance.download_dir:
        return cleaned_download_dir
    return dispatch_download_dir


async def _get_torrent_import_source_with_routing(
    *,
    task_ref: str,
    chat_id: int | None,
    job_repo: JobRepo,
    downloader_instances_by_name: dict[str, DownloaderInstanceConfig],
    transmission_clients_by_name: dict[str, TransmissionClient],
    qbittorrent_clients_by_name: dict[str, QbittorrentClient],
) -> TransmissionImportSource | None:
    route, client = _resolve_lookup_client_for_task(
        task_ref=task_ref,
        chat_id=chat_id,
        job_repo=job_repo,
        downloader_instances_by_name=downloader_instances_by_name,
        transmission_clients_by_name=transmission_clients_by_name,
        qbittorrent_clients_by_name=qbittorrent_clients_by_name,
        operation="import",
    )
    import_source = await client.get_torrent_import_source(task_ref)
    if import_source is None:
        return None
    return _normalize_import_source_download_dir(
        import_source=import_source,
        host_download_dir=_resolve_host_download_dir_for_route(
            route=route,
            downloader_instances_by_name=downloader_instances_by_name,
        ),
    )


async def _get_torrent_status_with_routing(
    *,
    task_ref: str,
    chat_id: int | None,
    job_repo: JobRepo,
    downloader_instances_by_name: dict[str, DownloaderInstanceConfig],
    transmission_clients_by_name: dict[str, TransmissionClient],
    qbittorrent_clients_by_name: dict[str, QbittorrentClient],
) -> TransmissionTaskStatus | None:
    _, client = _resolve_lookup_client_for_task(
        task_ref=task_ref,
        chat_id=chat_id,
        job_repo=job_repo,
        downloader_instances_by_name=downloader_instances_by_name,
        transmission_clients_by_name=transmission_clients_by_name,
        qbittorrent_clients_by_name=qbittorrent_clients_by_name,
        operation="status",
    )
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
    _, client = _resolve_lookup_client_for_task(
        task_ref=task_ref,
        chat_id=chat_id,
        job_repo=job_repo,
        downloader_instances_by_name=downloader_instances_by_name,
        transmission_clients_by_name=transmission_clients_by_name,
        qbittorrent_clients_by_name=qbittorrent_clients_by_name,
        operation="remove",
    )
    await client.remove_torrent(task_ref, delete_local_data=delete_local_data)

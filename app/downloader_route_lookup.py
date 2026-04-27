from __future__ import annotations

import json

from app.clients.qbittorrent import QbittorrentClient
from app.clients.transmission import TransmissionClient, TransmissionImportSource, TransmissionTaskStatus
from app.config import DownloaderInstanceConfig
from app.db.job_repo import JobRepo


class DownloaderRouteLookupError(RuntimeError):
    pass


def _format_task_route_context(*, task_ref: str, chat_id: int | None) -> str:
    return f"task_ref={task_ref} chat_id={chat_id if chat_id is not None else '-'}"


def _format_downloader_context(*, downloader_name: str, downloader_type: str = "") -> str:
    cleaned_name = downloader_name or "-"
    cleaned_type = downloader_type.strip()
    if not cleaned_type:
        return cleaned_name
    return f"{cleaned_name} downloader_type={cleaned_type}"


def _print_downloader_issue_log(
    *,
    title: str,
    context_label: str,
    context_value: str,
    detail_label: str,
    detail_value: str,
    fix_hint: str,
) -> None:
    print(
        f"\033[31m[{title}]\033[0m {context_label}={context_value or '-'} {detail_label}={detail_value}\n"
        f"\033[33m[处理建议]\033[0m {fix_hint}",
        flush=True,
    )


def _resolve_downloader_task_route(
    *,
    task_ref: str,
    chat_id: int | None,
    job_repo: JobRepo,
) -> tuple[str, str] | None:
    if chat_id is None or chat_id <= 0:
        _print_downloader_issue_log(
            title="下载器路由未命中",
            context_label="task_ref",
            context_value=_format_task_route_context(task_ref=task_ref, chat_id=chat_id),
            detail_label="原因",
            detail_value="chat_id missing",
            fix_hint="检查当前任务是否已写入 downloader job、payload 里是否保留了 downloader_name，并确认状态/导入查询使用的是同一私聊会话。",
        )
        return None
    try:
        downloader_job = job_repo.get_downloader_job_for_chat_ref(chat_id=chat_id, task_ref=task_ref)
    except Exception as error:
        _print_downloader_issue_log(
            title="下载器路由查询失败",
            context_label="task_ref",
            context_value=_format_task_route_context(task_ref=task_ref, chat_id=chat_id),
            detail_label="错误",
            detail_value=str(error),
            fix_hint="检查 SQLite/jobs 表读取是否正常，并确认当前任务引用仍能命中 downloader job 真相。",
        )
        return None
    if downloader_job is None:
        _print_downloader_issue_log(
            title="下载器路由未命中",
            context_label="task_ref",
            context_value=_format_task_route_context(task_ref=task_ref, chat_id=chat_id),
            detail_label="原因",
            detail_value="downloader job missing",
            fix_hint="检查当前任务是否已写入 downloader job、payload 里是否保留了 downloader_name，并确认状态/导入查询使用的是同一私聊会话。",
        )
        return None
    cleaned_payload = downloader_job.payload_json.strip()
    payload_reason: str | None = None
    if not cleaned_payload:
        payload_reason = "payload_json empty"
    else:
        try:
            payload = json.loads(cleaned_payload)
        except json.JSONDecodeError:
            payload_reason = "payload_json invalid json"
        else:
            if not isinstance(payload, dict):
                payload_reason = "payload_json not object"
    if payload_reason is not None:
        _print_downloader_issue_log(
            title="下载器路由载荷损坏",
            context_label="task_ref",
            context_value=_format_task_route_context(task_ref=task_ref, chat_id=chat_id),
            detail_label="原因",
            detail_value=payload_reason,
            fix_hint="检查 jobs.payload_json 是否仍保留合法 JSON，且包含 downloader_name。",
        )
        return None
    downloader_name = str(payload.get("downloader_name", "")).strip()
    download_dir = str(payload.get("download_dir", "")).strip()
    if not downloader_name:
        _print_downloader_issue_log(
            title="下载器路由未命中",
            context_label="task_ref",
            context_value=_format_task_route_context(task_ref=task_ref, chat_id=chat_id),
            detail_label="原因",
            detail_value="downloader_name missing",
            fix_hint="检查当前任务是否已写入 downloader job、payload 里是否保留了 downloader_name，并确认状态/导入查询使用的是同一私聊会话。",
        )
        return None
    return downloader_name, download_dir


def _resolve_lookup_client_for_task(
    *,
    task_ref: str,
    chat_id: int | None,
    job_repo: JobRepo,
    downloader_instances_by_name: dict[str, DownloaderInstanceConfig],
    transmission_clients_by_name: dict[str, TransmissionClient],
    qbittorrent_clients_by_name: dict[str, QbittorrentClient],
    operation: str,
) -> tuple[
    tuple[str, str],
    DownloaderInstanceConfig | None,
    TransmissionClient | QbittorrentClient,
]:
    route = _resolve_downloader_task_route(
        task_ref=task_ref,
        chat_id=chat_id,
        job_repo=job_repo,
    )
    if route is None:
        raise DownloaderRouteLookupError(f"downloader route unavailable for {operation} task: {task_ref}")
    downloader_name, _ = route
    cleaned_name, instance, client = _resolve_downloader_instance_and_client(
        downloader_name=downloader_name,
        downloader_instances_by_name=downloader_instances_by_name,
        transmission_clients_by_name=transmission_clients_by_name,
        qbittorrent_clients_by_name=qbittorrent_clients_by_name,
    )
    if instance is None:
        _print_downloader_issue_log(
            title="下载器实例不存在",
            context_label="downloader_name",
            context_value=_format_downloader_context(downloader_name=cleaned_name or "-"),
            detail_label="原因",
            detail_value="instance missing",
            fix_hint="检查当前任务 payload 里的 downloader_name 是否仍存在于 DOWNLOADER_INSTANCES，并确认角色绑定或历史任务没有引用已删除的实例名。",
        )
        raise DownloaderRouteLookupError(f"downloader client unavailable for {operation} task: {task_ref}")
    if client is None:
        _print_downloader_issue_log(
            title="下载器客户端未配置",
            context_label="downloader_name",
            context_value=_format_downloader_context(
                downloader_name=cleaned_name or "-",
                downloader_type=instance.downloader_type,
            ),
            detail_label="原因",
            detail_value="client missing",
            fix_hint="检查应用启动阶段是否已按 DOWNLOADER_INSTANCES 创建对应下载器 client，并确认当前实例的 base_url / 用户名密码没有让这条配置在装配时被跳过。",
        )
        raise DownloaderRouteLookupError(f"downloader client unavailable for {operation} task: {task_ref}")
    return route, instance, client


def _resolve_downloader_instance_and_client(
    *,
    downloader_name: str,
    downloader_instances_by_name: dict[str, DownloaderInstanceConfig],
    transmission_clients_by_name: dict[str, TransmissionClient],
    qbittorrent_clients_by_name: dict[str, QbittorrentClient],
) -> tuple[str, DownloaderInstanceConfig | None, TransmissionClient | QbittorrentClient | None]:
    cleaned_name = downloader_name.strip()
    instance = downloader_instances_by_name.get(cleaned_name)
    if instance is None:
        return cleaned_name, None, None
    client = (
        qbittorrent_clients_by_name.get(cleaned_name)
        if instance.downloader_type == "qbittorrent"
        else transmission_clients_by_name.get(cleaned_name)
    )
    return cleaned_name, instance, client


async def _get_torrent_import_source_with_routing(
    *,
    task_ref: str,
    chat_id: int | None,
    job_repo: JobRepo,
    downloader_instances_by_name: dict[str, DownloaderInstanceConfig],
    transmission_clients_by_name: dict[str, TransmissionClient],
    qbittorrent_clients_by_name: dict[str, QbittorrentClient],
) -> TransmissionImportSource | None:
    route, instance, client = _resolve_lookup_client_for_task(
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
    _, route_download_dir = route
    route_download_dir = route_download_dir.strip()
    host_download_dir = route_download_dir or instance.download_dir.strip()
    if not host_download_dir or host_download_dir == import_source.download_dir:
        return import_source
    return TransmissionImportSource(
        task_id=import_source.task_id,
        task_hash=import_source.task_hash,
        name=import_source.name,
        download_dir=host_download_dir,
        is_finished=import_source.is_finished,
        percent_done=import_source.percent_done,
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
    _, _, client = _resolve_lookup_client_for_task(
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
    _, _, client = _resolve_lookup_client_for_task(
        task_ref=task_ref,
        chat_id=chat_id,
        job_repo=job_repo,
        downloader_instances_by_name=downloader_instances_by_name,
        transmission_clients_by_name=transmission_clients_by_name,
        qbittorrent_clients_by_name=qbittorrent_clients_by_name,
        operation="remove",
    )
    await client.remove_torrent(task_ref, delete_local_data=delete_local_data)

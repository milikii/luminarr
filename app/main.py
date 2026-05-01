from __future__ import annotations

import asyncio
import os
from pathlib import Path
import httpx
from telegram.error import NetworkError

from app.bot import telegram_bot as tg
from app.bot.channel_contact_runtime import CHANNEL_CONTACT_REGISTRY_KEY, ChannelContactRegistry
from app.bot.feishu_long_connection import (
    FEISHU_LONG_CONNECTION_SERVICE_KEY,
    FeishuLongConnectionConfig,
    FeishuLongConnectionService,
)
from app.bot.non_telegram_runtime_host import NonTelegramRuntimeHost
from app.bot.private_chat_bt_subscription_runtime import (
    BT_SUBSCRIPTION_CAPABILITY_UNAVAILABLE_TEXT,
    BT_SUBSCRIPTION_CAPABILITY_UNAVAILABLE_TEXT_BOT_DATA_KEY,
)
from app.bot.private_chat_search_runtime import (
    SEARCH_CAPABILITY_UNAVAILABLE_TEXT,
    SEARCH_CAPABILITY_UNAVAILABLE_TEXT_BOT_DATA_KEY,
)
from app.bot.personal_wechat_login import PERSONAL_WECHAT_LOGIN_SERVICE_KEY, PersonalWeChatLoginService
from app.bot.telegram_sidecar_runtime import (
    TELEGRAM_SIDECAR_RUNTIME_CONFIG,
    start_non_telegram_sidecar_host_lifecycle,
    stop_non_telegram_sidecar_host_lifecycle,
)
from app.bot.wecom_adapter import (
    WECOM_ENCODING_AES_KEY_BOT_DATA_KEY,
    WECOM_RECEIVE_ID_BOT_DATA_KEY,
    WECOM_TOKEN_BOT_DATA_KEY,
)
from app.bot.wecom_webhook_server import WeComWebhookServerConfig
from app.bot.telegram_runtime_adapter import build_telegram_application as build_application
from app.clients.adult_read_only_helper_chain import AdultReadOnlyLookupFunc, compose_adult_read_only_lookup_func
from app.clients.avmoo_helper import AvmooReadOnlyHelperClient
from app.clients.avsox_helper import AvsoxReadOnlyHelperClient
from app.clients.caribbeancom_helper import CaribbeancomReadOnlyHelperClient
from app.clients.emby import EmbyClient
from app.clients.feishu import FeishuClient
from app.clients.fanart import FanartClient
from app.clients.jellyfin import JellyfinClient
from app.clients.javbus_helper import JavBusReadOnlyHelperClient
from app.clients.javlibrary_helper import JavLibraryReadOnlyHelperClient
from app.clients.plex import PlexClient
from app.clients.prowlarr import ProwlarrClient
from app.clients.qbittorrent import QbittorrentClient
from app.clients.tmdb import TmdbClient
from app.clients.transmission import TransmissionClient, TransmissionImportSource, TransmissionTask, TransmissionTaskStatus
from app.clients.web_source import WebSourceClient, get_configured_web_source_rule
from app.config import ConfigError, DownloaderInstanceConfig, load_settings
from app.db.adult_content_registry_repo import AdultContentRegistryRepo
from app.db.adult_duplicate_memory_snapshot_repo import AdultDuplicateMemorySnapshotRepo
from app.db.approval_repo import ApprovalRepo
from app.db.bt_pending_repo import BtPendingRepo
from app.db.bt_subscription_repo import BtSubscriptionRepo
from app.db.candidate_repo import CandidateMappingRepo
from app.db.clarification_repo import ClarificationRepo
from app.db.download_monitor_repo import DownloadMonitorRepo
from app.db.job_event_repo import JobEventRepo
from app.db.job_repo import JobRepo
from app.db.sqlite import SqliteDatabase
from app.db.telegram_update_repo import TelegramUpdateRepo
from app.db.watchlist_repo import WatchlistRepo
from app.downloader_route_lookup import (
    _get_torrent_import_source_with_routing,
    _remove_torrent_with_routing,
    _get_torrent_status_with_routing,
    _format_downloader_context,
    _emit_downloader_issue_log,
    _resolve_downloader_instance_and_client,
)
from app.operational_logging import emit_operational_log
from app.runtime.execution_policy import ExecutionGate
from app.services.add_to_downloader import AddToDownloaderService
from app.services.adult_duplicate_memory import AdultDuplicateMemoryService
from app.services.adult_archive_service import AdultArchiveService
from app.services.bt_sources import BtSourceAdapter, BtSourceProvider, get_default_adult_bt_source_names
from app.services.cleanup_downloaded_source import CleanupDownloadedSourceService
from app.services.get_download_status import GetDownloadStatusService
from app.services.import_to_library import ImportToLibraryService
from app.services.manage_watchlist import ManageWatchlistService
from app.services.manage_bt_subscription import ManageBtSubscriptionService
from app.services.metadata_scraper import MetadataScraperService
from app.services.post_download_auto_import import PostDownloadAutoImportService
from app.services.refresh_media_server import RefreshMediaServerService
from app.services.search_media import SearchMediaService
from app.services.subtitle_translator import SubtitleTranslatorService
from app.trace_logging import TRACE_LOG_PATH_BOT_DATA_KEY, configure_trace_log_file


def _run_application_polling(application) -> None:
    try:
        application.run_polling(drop_pending_updates=True, timeout=20, bootstrap_retries=3)
    except NetworkError as error:
        emit_operational_log(
            title="Telegram 启动失败",
            detail=f"错误={error}",
            fix_hint="检查当前网络、DNS、代理和 `TELEGRAM_BOT_TOKEN` 是否可访问 Telegram Bot API 后重试。",
        )
        raise


async def _run_non_telegram_host(host: NonTelegramRuntimeHost, *, config) -> None:
    try:
        await start_non_telegram_sidecar_host_lifecycle(host, config=config)
        await host.wait_until_stopped()
    finally:
        await stop_non_telegram_sidecar_host_lifecycle(host, config=config)


def _resolve_runtime_host_mode(settings) -> str:
    if settings.has_telegram_host():
        return "telegram"
    if settings.has_wecom_host():
        return "wecom"
    if settings.has_feishu_host():
        return "feishu"
    raise ConfigError(
        "TELEGRAM_BOT_TOKEN is required unless FEISHU_APP_ID/FEISHU_APP_SECRET or "
        "WECOM_TOKEN/WECOM_ENCODING_AES_KEY/WECOM_RECEIVE_ID are set"
    )


def _build_bt_source_providers(
    *,
    configured_web_source_names: tuple[str, ...],
    proxy_url: str,
) -> list[BtSourceProvider]:
    bt_source_providers: list[BtSourceProvider] = []
    source_names = configured_web_source_names or get_default_adult_bt_source_names()
    for source_name in source_names:
        rule = get_configured_web_source_rule(source_name)
        if rule is None:
            emit_operational_log(
                title="BT 外部站点源配置无效",
                detail=f"来源={source_name}",
                fix_hint="检查 BT_WEB_SOURCES，只填写当前代码内已支持且允许主动搜索的站点名。",
            )
            continue
        client = WebSourceClient(rule=rule, proxy_url=proxy_url)
        bt_source_providers.append(
            BtSourceProvider(name=rule.name, search_func=client.search, page_search_func=client.search_page)
        )
    return bt_source_providers


def _build_adult_read_only_lookup_func(*, proxy_url: str) -> AdultReadOnlyLookupFunc:
    avmoo_client = AvmooReadOnlyHelperClient(proxy_url=proxy_url)
    avsox_client = AvsoxReadOnlyHelperClient(proxy_url=proxy_url)
    javbus_client = JavBusReadOnlyHelperClient(proxy_url=proxy_url)
    caribbeancom_client = CaribbeancomReadOnlyHelperClient(proxy_url=proxy_url)
    javlibrary_client = JavLibraryReadOnlyHelperClient(proxy_url=proxy_url)
    return compose_adult_read_only_lookup_func(
        avmoo_lookup_func=avmoo_client.lookup,
        caribbeancom_lookup_func=caribbeancom_client.lookup,
        avsox_lookup_func=avsox_client.lookup,
        javbus_lookup_func=javbus_client.lookup,
        javlibrary_lookup_func=javlibrary_client.lookup,
    )


def _resolve_downloader_client_for_dispatch(
    *,
    downloader_name: str,
    transmission_client: TransmissionClient | None,
    downloader_instances_by_name: dict[str, DownloaderInstanceConfig],
    transmission_clients_by_name: dict[str, TransmissionClient],
    qbittorrent_clients_by_name: dict[str, QbittorrentClient],
) -> TransmissionClient | QbittorrentClient:
    cleaned_name = downloader_name.strip()
    if not cleaned_name:
        if transmission_client is not None:
            return transmission_client
        _emit_downloader_issue_log(
            title="下载器投递路由失败",
            context_label="downloader_name",
            context_value=_format_downloader_context(downloader_name="-", downloader_type="-"),
            detail_label="原因",
            detail_value="legacy fallback unavailable",
            fix_hint="当前未配置 legacy TRANSMISSION_BASE_URL；请确保任务写入显式 downloader_name，或补齐 legacy Transmission 配置后重试。",
        )
        raise ValueError("legacy transmission client not configured for implicit fallback")
    cleaned_name, instance, client = _resolve_downloader_instance_and_client(
        downloader_name=cleaned_name,
        downloader_instances_by_name=downloader_instances_by_name,
        transmission_clients_by_name=transmission_clients_by_name,
        qbittorrent_clients_by_name=qbittorrent_clients_by_name,
    )
    if instance is None:
        _emit_downloader_issue_log(
            title="下载器投递路由失败",
            context_label="downloader_name",
            context_value=_format_downloader_context(downloader_name=cleaned_name, downloader_type="-"),
            detail_label="原因",
            detail_value="instance missing",
            fix_hint="检查 DOWNLOADER_INSTANCES、下载器角色绑定和应用启动阶段的 client 装配是否一致，再重试当前下载投递。",
        )
        raise ValueError(f"unknown downloader instance: {cleaned_name}")
    if client is None:
        _emit_downloader_issue_log(
            title="下载器投递路由失败",
            context_label="downloader_name",
            context_value=_format_downloader_context(
                downloader_name=cleaned_name,
                downloader_type=instance.downloader_type,
            ),
            detail_label="原因",
            detail_value="client not configured",
            fix_hint="检查 DOWNLOADER_INSTANCES、下载器角色绑定和应用启动阶段的 client 装配是否一致，再重试当前下载投递。",
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
    if dispatch_download_dir and cleaned_download_dir == instance.download_dir:
        return dispatch_download_dir
    return cleaned_download_dir


def _log_missing_media_server_settings(*, provider: str, missing_keys: list[str]) -> None:
    joined_keys = ", ".join(missing_keys)
    emit_operational_log(
        title="媒体服务器配置缺失",
        detail=f"provider={provider} 缺少={joined_keys}",
        fix_hint="补齐该 provider 对应的地址和凭据；当前会保留导入成功真相，但跳过媒体库刷新。",
    )


def _build_refresh_media_server_func(settings):
    provider_name = settings.media_server_provider
    target_url = ""
    if settings.media_server_provider == "jellyfin":
        missing_keys: list[str] = []
        if not settings.jellyfin_base_url:
            missing_keys.append("JELLYFIN_BASE_URL")
        if not settings.jellyfin_api_key:
            missing_keys.append("JELLYFIN_API_KEY")
        if missing_keys:
            _log_missing_media_server_settings(provider="jellyfin", missing_keys=missing_keys)
            return None
        target_url = settings.jellyfin_base_url
        refresh_func = JellyfinClient(
            base_url=settings.jellyfin_base_url,
            api_key=settings.jellyfin_api_key,
        ).refresh_library
    elif settings.media_server_provider == "plex":
        missing_keys = []
        if not settings.plex_base_url:
            missing_keys.append("PLEX_BASE_URL")
        if not settings.plex_token:
            missing_keys.append("PLEX_TOKEN")
        if missing_keys:
            _log_missing_media_server_settings(provider="plex", missing_keys=missing_keys)
            return None
        target_url = settings.plex_base_url
        refresh_func = PlexClient(
            base_url=settings.plex_base_url,
            token=settings.plex_token,
        ).refresh_library
    else:
        missing_keys = []
        if not settings.emby_base_url:
            missing_keys.append("EMBY_BASE_URL")
        if not settings.emby_api_key:
            missing_keys.append("EMBY_API_KEY")
        if missing_keys:
            _log_missing_media_server_settings(provider="emby", missing_keys=missing_keys)
            return None
        target_url = settings.emby_base_url
        refresh_func = EmbyClient(
            base_url=settings.emby_base_url,
            api_key=settings.emby_api_key,
        ).refresh_library
    refresh_service = RefreshMediaServerService(
        refresh_func,
        provider_name=provider_name,
        target_url=target_url,
    )
    return refresh_service.refresh_text


def _populate_non_telegram_runtime_bot_data(
    *,
    bot_data: dict[str, object],
    channel_contact_registry: ChannelContactRegistry,
    search_service: SearchMediaService,
    add_to_downloader_service: AddToDownloaderService,
    get_download_status_service: GetDownloadStatusService,
    import_to_library_service: ImportToLibraryService,
    cleanup_downloaded_source_service: CleanupDownloadedSourceService,
    manage_watchlist_service: ManageWatchlistService,
    manage_bt_subscription_service: ManageBtSubscriptionService,
    post_download_auto_import_service: PostDownloadAutoImportService,
    job_repo: JobRepo,
    bt_pending_repo: BtPendingRepo,
    raw_bt_destination_options: tuple,
    downloader_instances: tuple[DownloaderInstanceConfig, ...],
    downloader_role_binding,
    bt_tmdb_movie_candidates_lookup_func,
    bt_tmdb_tv_candidates_lookup_func,
) -> None:
    bot_data[CHANNEL_CONTACT_REGISTRY_KEY] = channel_contact_registry
    bot_data[tg.SEARCH_SERVICE_KEY] = search_service
    bot_data[tg.ADD_TO_DOWNLOADER_SERVICE_KEY] = add_to_downloader_service
    bot_data[tg.GET_DOWNLOAD_STATUS_SERVICE_KEY] = get_download_status_service
    bot_data[tg.IMPORT_TO_LIBRARY_SERVICE_KEY] = import_to_library_service
    bot_data[tg.POST_DOWNLOAD_AUTO_IMPORT_SERVICE_KEY] = post_download_auto_import_service
    bot_data[tg.CLEANUP_DOWNLOADED_SOURCE_SERVICE_KEY] = cleanup_downloaded_source_service
    bot_data[tg.MANAGE_WATCHLIST_SERVICE_KEY] = manage_watchlist_service
    bot_data[tg.MANAGE_BT_SUBSCRIPTION_SERVICE_KEY] = manage_bt_subscription_service
    bot_data[tg.EXECUTION_GATE_KEY] = ExecutionGate()
    bot_data[tg.DOWNLOADER_INSTANCES_KEY] = downloader_instances
    bot_data[tg.DOWNLOADER_ROLE_BINDING_KEY] = downloader_role_binding
    bot_data[tg.RAW_BT_DESTINATION_OPTIONS_KEY] = raw_bt_destination_options
    bot_data[tg.BT_PENDING_REPO_KEY] = bt_pending_repo
    bot_data[tg.JOB_REPO_KEY] = job_repo
    if bt_tmdb_movie_candidates_lookup_func is not None:
        bot_data[tg.BT_TMDB_MOVIE_CANDIDATES_LOOKUP_KEY] = bt_tmdb_movie_candidates_lookup_func
    if bt_tmdb_tv_candidates_lookup_func is not None:
        bot_data[tg.BT_TMDB_TV_CANDIDATES_LOOKUP_KEY] = bt_tmdb_tv_candidates_lookup_func


def main() -> None:
    settings = load_settings()
    host_mode = _resolve_runtime_host_mode(settings)
    has_telegram_host = host_mode == "telegram"
    trace_log_dir = Path((os.getenv("LUMINARR_LOG_DIR", "./logs") or "./logs").strip()).expanduser()
    trace_log_path = configure_trace_log_file(log_dir=trace_log_dir)
    database = SqliteDatabase(settings.sqlite_db_path)
    database.initialize()
    candidate_repo = CandidateMappingRepo(database)
    job_event_repo = JobEventRepo(database)
    job_repo = JobRepo(database)
    approval_repo = ApprovalRepo(database)
    adult_content_registry_repo = AdultContentRegistryRepo(database)
    adult_duplicate_memory_snapshot_repo = AdultDuplicateMemorySnapshotRepo(database)
    bt_pending_repo = BtPendingRepo(database)
    bt_subscription_repo = BtSubscriptionRepo(database)
    download_monitor_repo = DownloadMonitorRepo(database)
    telegram_update_repo = TelegramUpdateRepo(database)
    watchlist_repo = WatchlistRepo(database)
    clarification_repo = ClarificationRepo(database)
    channel_contact_registry = ChannelContactRegistry()

    async def search_capability_unavailable(_: str) -> list[dict[str, object]]:
        return []

    prowlarr_client: ProwlarrClient | None = None
    bt_source_providers = _build_bt_source_providers(
        configured_web_source_names=settings.bt_web_sources,
        proxy_url=settings.outbound_proxy_url,
    )
    if settings.has_prowlarr_search():
        prowlarr_client = ProwlarrClient(
            base_url=settings.prowlarr_base_url,
            api_key=settings.prowlarr_api_key,
        )
        bt_source_providers.append(BtSourceProvider(name="prowlarr", search_func=prowlarr_client.search))
    bt_source_adapter = BtSourceAdapter(tuple(bt_source_providers))
    tmdb_lookup_movie_func = None
    tmdb_lookup_media_candidates_func = None
    scrape_metadata_func = None
    if settings.tmdb_api_key:
        async def _skip_fanart_images(_: str) -> None:
            return None

        async def _download_remote_image(url: str) -> bytes:
            cleaned_url = url.strip()
            if not cleaned_url:
                return b""
            async with httpx.AsyncClient(timeout=20.0, proxy=settings.outbound_proxy_url or None) as client:
                response = await client.get(cleaned_url)
            response.raise_for_status()
            return response.content

        tmdb_client = TmdbClient(
            api_key=settings.tmdb_api_key,
            base_url=settings.tmdb_base_url,
            proxy_url=settings.outbound_proxy_url,
        )
        tmdb_lookup_movie_func = tmdb_client.search_movie
        tmdb_lookup_media_candidates_func = tmdb_client.search_media_candidates
        get_movie_images_func = _skip_fanart_images
        if settings.fanart_api_key:
            fanart_client = FanartClient(
                api_key=settings.fanart_api_key,
                base_url=settings.fanart_base_url,
                proxy_url=settings.outbound_proxy_url,
            )
            get_movie_images_func = fanart_client.get_movie_images
        metadata_scraper_service = MetadataScraperService(
            lookup_movie_func=tmdb_client.search_movie,
            get_movie_images_func=get_movie_images_func,
            lookup_movie_by_tmdb_id_func=tmdb_client.get_movie_by_id,
            download_image_func=_download_remote_image,
        )
        scrape_metadata_func = metadata_scraper_service.scrape_for_import
    search_service = SearchMediaService(
        search_func=prowlarr_client.search if prowlarr_client is not None else search_capability_unavailable,
        raw_search_func=bt_source_adapter.search,
        raw_page_search_func=bt_source_adapter.search_page,
        candidate_repo=candidate_repo,
        clarification_repo=clarification_repo,
        lookup_movie_func=tmdb_lookup_movie_func,
        lookup_media_candidates_func=tmdb_lookup_media_candidates_func,
        adult_content_registry_repo=adult_content_registry_repo,
        adult_read_only_lookup_func=_build_adult_read_only_lookup_func(proxy_url=settings.outbound_proxy_url),
    )
    transmission_client: TransmissionClient | None = None
    if settings.has_legacy_transmission_downloader():
        transmission_client = TransmissionClient(
            base_url=settings.transmission_base_url,
            username=settings.transmission_username,
            password=settings.transmission_password,
        )
    downloader_instances_by_name = {instance.name: instance for instance in settings.downloader_instances}
    transmission_clients_by_name: dict[str, TransmissionClient] = {}
    for instance in settings.downloader_instances:
        if instance.downloader_type != "transmission":
            continue
        transmission_clients_by_name[instance.name] = TransmissionClient(
            base_url=instance.base_url,
            username=instance.username,
            password=instance.password,
        )
    qbittorrent_clients_by_name: dict[str, QbittorrentClient] = {}
    for instance in settings.downloader_instances:
        if instance.downloader_type != "qbittorrent":
            continue
        qbittorrent_clients_by_name[instance.name] = QbittorrentClient(
            base_url=instance.base_url,
            username=instance.username,
            password=instance.password,
        )

    async def add_torrent_with_routing(source: str, downloader_name: str = "", download_dir: str = "") -> TransmissionTask:
        client = _resolve_downloader_client_for_dispatch(
            downloader_name=downloader_name,
            transmission_client=transmission_client,
            downloader_instances_by_name=downloader_instances_by_name,
            transmission_clients_by_name=transmission_clients_by_name,
            qbittorrent_clients_by_name=qbittorrent_clients_by_name,
        )
        resolved_download_dir = resolve_downloader_dispatch_download_dir(
            downloader_name=downloader_name,
            requested_download_dir=download_dir,
            downloader_instances_by_name=downloader_instances_by_name,
        )
        return await client.add_torrent(source, download_dir=resolved_download_dir)

    async def get_torrent_status_with_routing(task_ref: str, chat_id: int | None = None) -> TransmissionTaskStatus | None:
        return await _get_torrent_status_with_routing(
            task_ref=task_ref,
            chat_id=chat_id,
            job_repo=job_repo,
            downloader_instances_by_name=downloader_instances_by_name,
            transmission_clients_by_name=transmission_clients_by_name,
            qbittorrent_clients_by_name=qbittorrent_clients_by_name,
        )

    async def get_torrent_import_source_with_routing(
        task_ref: str,
        chat_id: int | None = None,
    ) -> TransmissionImportSource | None:
        return await _get_torrent_import_source_with_routing(
            task_ref=task_ref,
            chat_id=chat_id,
            job_repo=job_repo,
            downloader_instances_by_name=downloader_instances_by_name,
            transmission_clients_by_name=transmission_clients_by_name,
            qbittorrent_clients_by_name=qbittorrent_clients_by_name,
        )

    async def remove_torrent_with_routing(
        task_ref: str,
        chat_id: int | None = None,
        delete_local_data: bool = True,
    ) -> None:
        await _remove_torrent_with_routing(
            task_ref=task_ref,
            chat_id=chat_id,
            job_repo=job_repo,
            downloader_instances_by_name=downloader_instances_by_name,
            transmission_clients_by_name=transmission_clients_by_name,
            qbittorrent_clients_by_name=qbittorrent_clients_by_name,
            delete_local_data=delete_local_data,
        )

    adult_scan_dirs = [Path(destination.target_dir).expanduser() for destination in settings.adult_archive_destinations]
    adult_duplicate_memory_service = AdultDuplicateMemoryService(
        snapshot_repo=adult_duplicate_memory_snapshot_repo,
        adult_content_registry_repo=adult_content_registry_repo,
        job_event_repo=job_event_repo,
        adult_scan_dirs=adult_scan_dirs,
    )

    add_to_downloader_service = AddToDownloaderService(
        search_service=search_service,
        add_torrent_func=add_torrent_with_routing,
        approval_repo=approval_repo,
        job_repo=job_repo,
        job_event_repo=job_event_repo,
        download_monitor_repo=download_monitor_repo,
        adult_content_registry_repo=adult_content_registry_repo,
        adult_duplicate_memory_service=adult_duplicate_memory_service,
        bt_pending_repo=bt_pending_repo,
        trace_log_path=trace_log_path,
    )
    refresh_media_server_func = _build_refresh_media_server_func(settings)
    import_to_library_service = ImportToLibraryService(
        get_import_source_func=get_torrent_import_source_with_routing,
        library_target_dir=settings.library_target_dir,
        refresh_media_server_func=refresh_media_server_func,
        scrape_metadata_func=scrape_metadata_func,
        translate_subtitle_func=SubtitleTranslatorService(
            api_key=settings.subtitle_translation_api_key,
            base_url=settings.subtitle_translation_base_url,
            model=settings.subtitle_translation_model,
            timeout_seconds=settings.subtitle_translation_timeout_seconds,
            proxy_url=settings.outbound_proxy_url,
        ).translate_for_import,
        job_event_repo=job_event_repo,
        approval_repo=approval_repo,
        job_repo=job_repo,
        trace_log_path=trace_log_path,
    )
    post_download_auto_import_service = PostDownloadAutoImportService(
        download_monitor_repo=download_monitor_repo,
        job_event_repo=job_event_repo,
        auto_import_func=lambda task_ref, chat_id, user_id: import_to_library_service.import_by_task_ref(
            task_ref,
            chat_id=chat_id,
            user_id=user_id,
        ),
        adult_content_registry_repo=adult_content_registry_repo,
        adult_archive_service=AdultArchiveService(
            get_import_source_func=get_torrent_import_source_with_routing,
            remove_torrent_func=remove_torrent_with_routing,
            registry_repo=adult_content_registry_repo,
            job_event_repo=job_event_repo,
            archive_destinations=settings.adult_archive_destinations,
            retention_hours=settings.adult_bt_retention_hours,
        ),
    )
    get_download_status_service = GetDownloadStatusService(
        get_torrent_status_with_routing,
        download_monitor_repo=download_monitor_repo,
        job_event_repo=job_event_repo,
        post_download_auto_import_service=post_download_auto_import_service,
    )
    cleanup_downloaded_source_service = CleanupDownloadedSourceService(
        job_event_repo=job_event_repo,
        job_repo=job_repo,
        download_monitor_repo=download_monitor_repo,
        pt_min_seed_hours=settings.pt_min_seed_hours,
    )
    manage_watchlist_service = ManageWatchlistService(
        watchlist_repo,
        bt_subscription_repo=bt_subscription_repo,
    )
    manage_bt_subscription_service = ManageBtSubscriptionService(
        bt_subscription_repo=bt_subscription_repo,
        search_func=bt_source_adapter.search,
        add_to_downloader_service=add_to_downloader_service,
    )
    bt_tmdb_movie_candidates_lookup_func = tmdb_client.search_movie_candidates if settings.tmdb_api_key else None
    bt_tmdb_tv_candidates_lookup_func = tmdb_client.search_tv_candidates if settings.tmdb_api_key else None
    runtime_host: object
    if has_telegram_host:
        runtime_host = build_application(
            settings.telegram_bot_token,
            search_service,
            add_to_downloader_service,
            get_download_status_service,
            import_to_library_service,
            cleanup_downloaded_source_service,
            manage_watchlist_service,
            manage_bt_subscription_service,
            post_download_auto_import_service=post_download_auto_import_service,
            telegram_update_repo=telegram_update_repo,
            job_repo=job_repo,
            bt_pending_repo=bt_pending_repo,
            bt_tmdb_movie_candidates_lookup_func=bt_tmdb_movie_candidates_lookup_func,
            bt_tmdb_tv_candidates_lookup_func=bt_tmdb_tv_candidates_lookup_func,
            raw_bt_destination_options=settings.raw_bt_destination_options,
            downloader_instances=settings.downloader_instances,
            downloader_role_binding=settings.downloader_role_binding,
            outbound_proxy_url=settings.outbound_proxy_url,
            channel_contact_registry=channel_contact_registry,
        )
    else:
        runtime_host = NonTelegramRuntimeHost()
        _populate_non_telegram_runtime_bot_data(
            bot_data=runtime_host.bot_data,
            channel_contact_registry=channel_contact_registry,
            search_service=search_service,
            add_to_downloader_service=add_to_downloader_service,
            get_download_status_service=get_download_status_service,
            import_to_library_service=import_to_library_service,
            cleanup_downloaded_source_service=cleanup_downloaded_source_service,
            manage_watchlist_service=manage_watchlist_service,
            manage_bt_subscription_service=manage_bt_subscription_service,
            post_download_auto_import_service=post_download_auto_import_service,
            job_repo=job_repo,
            bt_pending_repo=bt_pending_repo,
            raw_bt_destination_options=settings.raw_bt_destination_options,
            downloader_instances=settings.downloader_instances,
            downloader_role_binding=settings.downloader_role_binding,
            bt_tmdb_movie_candidates_lookup_func=bt_tmdb_movie_candidates_lookup_func,
            bt_tmdb_tv_candidates_lookup_func=bt_tmdb_tv_candidates_lookup_func,
        )
    bot_data = runtime_host.bot_data
    if not settings.has_prowlarr_search():
        bot_data[SEARCH_CAPABILITY_UNAVAILABLE_TEXT_BOT_DATA_KEY] = SEARCH_CAPABILITY_UNAVAILABLE_TEXT
        bot_data[BT_SUBSCRIPTION_CAPABILITY_UNAVAILABLE_TEXT_BOT_DATA_KEY] = (
            BT_SUBSCRIPTION_CAPABILITY_UNAVAILABLE_TEXT
        )
    if trace_log_path is not None:
        bot_data[TRACE_LOG_PATH_BOT_DATA_KEY] = trace_log_path
    bot_data[PERSONAL_WECHAT_LOGIN_SERVICE_KEY] = PersonalWeChatLoginService()
    if host_mode in {"telegram", "feishu"} and settings.has_feishu_host():
        feishu_client = FeishuClient(
            app_id=settings.feishu_app_id,
            app_secret=settings.feishu_app_secret,
            base_url=settings.feishu_base_url,
        )
        bot_data[FEISHU_LONG_CONNECTION_SERVICE_KEY] = FeishuLongConnectionService(
            config=FeishuLongConnectionConfig(
                app_id=settings.feishu_app_id,
                app_secret=settings.feishu_app_secret,
            ),
            feishu_client=feishu_client,
        )
    if host_mode in {"telegram", "wecom"} and settings.has_wecom_host():
        bot_data[WECOM_TOKEN_BOT_DATA_KEY] = settings.wecom_token
        bot_data[WECOM_ENCODING_AES_KEY_BOT_DATA_KEY] = settings.wecom_encoding_aes_key
        bot_data[WECOM_RECEIVE_ID_BOT_DATA_KEY] = settings.wecom_receive_id
        bot_data["wecom_webhook_server_config"] = WeComWebhookServerConfig(
            host=settings.wecom_webhook_host,
            port=settings.wecom_webhook_port,
            path=settings.wecom_webhook_path,
        )
    if has_telegram_host:
        _run_application_polling(runtime_host)
        return
    asyncio.run(_run_non_telegram_host(runtime_host, config=TELEGRAM_SIDECAR_RUNTIME_CONFIG))


if __name__ == "__main__":
    main()

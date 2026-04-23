from __future__ import annotations

import os
from pathlib import Path
from telegram.error import NetworkError

from app.bot.feishu_adapter import FEISHU_ENCRYPT_KEY_BOT_DATA_KEY, build_feishu_reply_text_func
from app.bot.feishu_long_connection import (
    FEISHU_LONG_CONNECTION_SERVICE_KEY,
    FeishuLongConnectionConfig,
    FeishuLongConnectionService,
)
from app.bot.feishu_webhook_server import FeishuWebhookServerConfig
from app.bot.personal_wechat_login import PERSONAL_WECHAT_LOGIN_SERVICE_KEY, PersonalWeChatLoginService
from app.bot.wecom_adapter import (
    WECOM_ENCODING_AES_KEY_BOT_DATA_KEY,
    WECOM_RECEIVE_ID_BOT_DATA_KEY,
    WECOM_TOKEN_BOT_DATA_KEY,
)
from app.bot.wecom_webhook_server import WeComWebhookServerConfig
from app.bot.telegram_runtime_adapter import build_telegram_application as build_application
from app.clients.emby import EmbyClient
from app.clients.feishu import FeishuClient
from app.clients.fanart import FanartClient
from app.clients.jellyfin import JellyfinClient
from app.clients.plex import PlexClient
from app.clients.prowlarr import ProwlarrClient
from app.clients.qbittorrent import QbittorrentClient
from app.clients.tmdb import TmdbClient
from app.clients.transmission import TransmissionClient, TransmissionImportSource, TransmissionTask, TransmissionTaskStatus
from app.clients.web_source import SUPPORTED_WEB_SOURCE_RULES, WebSourceClient
from app.config import DownloaderInstanceConfig, load_settings
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
    DownloaderRouteLookupError,
    _get_torrent_import_source_with_routing,
    _get_torrent_status_with_routing,
    _resolve_downloader_client_for_lookup,
    _resolve_downloader_client_for_dispatch,
    _resolve_downloader_name_for_task,
)
from app.services.add_to_downloader import AddToDownloaderService
from app.services.bt_sources import BtSourceAdapter, BtSourceProvider
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

_COMPAT_REEXPORTS = (
    DownloaderRouteLookupError,
    _resolve_downloader_client_for_lookup,
    _resolve_downloader_name_for_task,
)


async def _skip_fanart_images(_: str):
    return None


def _build_downloader_instances_by_name(
    instances: tuple[DownloaderInstanceConfig, ...],
) -> dict[str, DownloaderInstanceConfig]:
    return {instance.name: instance for instance in instances}


def _run_application_polling(application) -> None:
    try:
        application.run_polling(drop_pending_updates=True)
    except NetworkError as error:
        print(f"\033[31m[Telegram 启动失败]\033[0m 错误={error}\n\033[33m[处理建议]\033[0m 检查当前网络、DNS 和 `TELEGRAM_BOT_TOKEN` 是否可访问 Telegram Bot API 后重试。", flush=True)
        raise


def _build_transmission_clients_by_name(
    instances: tuple[DownloaderInstanceConfig, ...],
) -> dict[str, TransmissionClient]:
    clients: dict[str, TransmissionClient] = {}
    for instance in instances:
        if instance.downloader_type != "transmission":
            continue
        clients[instance.name] = TransmissionClient(
            base_url=instance.base_url,
            username=instance.username,
            password=instance.password,
        )
    return clients


def _build_qbittorrent_clients_by_name(
    instances: tuple[DownloaderInstanceConfig, ...],
) -> dict[str, QbittorrentClient]:
    clients: dict[str, QbittorrentClient] = {}
    for instance in instances:
        if instance.downloader_type != "qbittorrent":
            continue
        clients[instance.name] = QbittorrentClient(
            base_url=instance.base_url,
            username=instance.username,
            password=instance.password,
        )
    return clients


def _build_bt_source_providers(
    *,
    prowlarr_client: ProwlarrClient,
    bt_web_sources: tuple[str, ...],
    outbound_proxy_url: str = "",
) -> tuple[BtSourceProvider, ...]:
    providers: list[BtSourceProvider] = [
        BtSourceProvider(name="prowlarr", search_func=prowlarr_client.search),
    ]
    for source_name in bt_web_sources:
        rule = SUPPORTED_WEB_SOURCE_RULES.get(source_name)
        if rule is None:
            print(
                f"\033[31m[BT 外部站点源配置无效]\033[0m 来源={source_name}\n"
                "\033[33m[处理建议]\033[0m 检查 BT_WEB_SOURCES，只填写当前代码内已支持的站点名。"
            )
            continue
        client = WebSourceClient(rule=rule, proxy_url=outbound_proxy_url)
        providers.append(BtSourceProvider(name=rule.name, search_func=client.search, page_search_func=client.search_page))
    return tuple(providers)


def _log_media_server_config_missing(provider: str, missing_keys: tuple[str, ...]) -> None:
    joined_keys = ", ".join(missing_keys)
    print(
        f"\033[31m[媒体服务器配置缺失]\033[0m provider={provider} 缺少={joined_keys}\n"
        "\033[33m[处理建议]\033[0m 补齐该 provider 对应的地址和凭据；当前会保留导入成功真相，但跳过媒体库刷新。",
        flush=True,
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
            _log_media_server_config_missing("jellyfin", tuple(missing_keys))
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
            _log_media_server_config_missing("plex", tuple(missing_keys))
            return None
        target_url = settings.plex_base_url
        refresh_func = PlexClient(
            base_url=settings.plex_base_url,
            token=settings.plex_token,
        ).refresh_library
    else:
        if not settings.emby_base_url or not settings.emby_api_key:
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


def main() -> None:
    settings = load_settings()
    trace_log_dir = Path((os.getenv("LUMINARR_LOG_DIR", "./logs") or "./logs").strip()).expanduser()
    trace_log_path = configure_trace_log_file(log_dir=trace_log_dir)
    database = SqliteDatabase(settings.sqlite_db_path)
    database.initialize()
    candidate_repo = CandidateMappingRepo(database)
    job_event_repo = JobEventRepo(database)
    job_repo = JobRepo(database)
    approval_repo = ApprovalRepo(database)
    bt_pending_repo = BtPendingRepo(database)
    bt_subscription_repo = BtSubscriptionRepo(database)
    download_monitor_repo = DownloadMonitorRepo(database)
    telegram_update_repo = TelegramUpdateRepo(database)
    watchlist_repo = WatchlistRepo(database)
    clarification_repo = ClarificationRepo(database)

    prowlarr_client = ProwlarrClient(
        base_url=settings.prowlarr_base_url,
        api_key=settings.prowlarr_api_key,
    )
    bt_source_adapter = BtSourceAdapter(
        _build_bt_source_providers(
            prowlarr_client=prowlarr_client,
            bt_web_sources=settings.bt_web_sources,
            outbound_proxy_url=settings.outbound_proxy_url,
        )
    )
    tmdb_lookup_movie_func = None
    scrape_metadata_func = None
    if settings.tmdb_api_key:
        tmdb_client = TmdbClient(
            api_key=settings.tmdb_api_key,
            base_url=settings.tmdb_base_url,
            proxy_url=settings.outbound_proxy_url,
        )
        tmdb_lookup_movie_func = tmdb_client.search_movie
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
        )
        scrape_metadata_func = metadata_scraper_service.scrape_for_import
    search_service = SearchMediaService(
        search_func=prowlarr_client.search,
        raw_search_func=bt_source_adapter.search,
        raw_page_search_func=bt_source_adapter.search_page,
        candidate_repo=candidate_repo,
        clarification_repo=clarification_repo,
        lookup_movie_func=tmdb_lookup_movie_func,
    )
    transmission_client = TransmissionClient(
        base_url=settings.transmission_base_url,
        username=settings.transmission_username,
        password=settings.transmission_password,
    )
    downloader_instances_by_name = _build_downloader_instances_by_name(settings.downloader_instances)
    transmission_clients_by_name = _build_transmission_clients_by_name(settings.downloader_instances)
    qbittorrent_clients_by_name = _build_qbittorrent_clients_by_name(settings.downloader_instances)

    def resolve_downloader_client_by_name(
        downloader_name: str,
    ) -> TransmissionClient | QbittorrentClient:
        cleaned_name = downloader_name.strip()
        if not cleaned_name:
            return transmission_client
        instance = downloader_instances_by_name.get(cleaned_name)
        if instance is None:
            return transmission_client
        if instance.downloader_type == "qbittorrent":
            return qbittorrent_clients_by_name.get(cleaned_name, transmission_client)
        return transmission_clients_by_name.get(cleaned_name, transmission_client)

    async def add_torrent_with_routing(source: str, downloader_name: str = "", download_dir: str = "") -> TransmissionTask:
        client = _resolve_downloader_client_for_dispatch(
            downloader_name=downloader_name,
            transmission_client=transmission_client,
            downloader_instances_by_name=downloader_instances_by_name,
            transmission_clients_by_name=transmission_clients_by_name,
            qbittorrent_clients_by_name=qbittorrent_clients_by_name,
        )
        return await client.add_torrent(source, download_dir=download_dir)

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

    add_to_downloader_service = AddToDownloaderService(
        search_service=search_service,
        add_torrent_func=add_torrent_with_routing,
        approval_repo=approval_repo,
        job_repo=job_repo,
        job_event_repo=job_event_repo,
        download_monitor_repo=download_monitor_repo,
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
    manage_watchlist_service = ManageWatchlistService(watchlist_repo)
    manage_bt_subscription_service = ManageBtSubscriptionService(
        bt_subscription_repo=bt_subscription_repo,
        search_func=bt_source_adapter.search,
        add_to_downloader_service=add_to_downloader_service,
    )
    application = build_application(
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
        bt_tmdb_movie_candidates_lookup_func=tmdb_client.search_movie_candidates if settings.tmdb_api_key else None,
        bt_tmdb_tv_candidates_lookup_func=tmdb_client.search_tv_candidates if settings.tmdb_api_key else None,
        raw_bt_destination_options=settings.raw_bt_destination_options,
        downloader_instances=settings.downloader_instances,
        downloader_role_binding=settings.downloader_role_binding,
        outbound_proxy_url=settings.outbound_proxy_url,
    )
    if trace_log_path is not None:
        application.bot_data[TRACE_LOG_PATH_BOT_DATA_KEY] = trace_log_path
    application.bot_data[PERSONAL_WECHAT_LOGIN_SERVICE_KEY] = PersonalWeChatLoginService()
    if settings.feishu_app_id and settings.feishu_app_secret:
        feishu_client = FeishuClient(
            app_id=settings.feishu_app_id,
            app_secret=settings.feishu_app_secret,
            base_url=settings.feishu_base_url,
        )
        if settings.feishu_inbound_mode == "long_connection":
            application.bot_data[FEISHU_LONG_CONNECTION_SERVICE_KEY] = FeishuLongConnectionService(
                config=FeishuLongConnectionConfig(
                    app_id=settings.feishu_app_id,
                    app_secret=settings.feishu_app_secret,
                ),
                feishu_client=feishu_client,
            )
        else:
            application.bot_data[FEISHU_ENCRYPT_KEY_BOT_DATA_KEY] = settings.feishu_encrypt_key
            application.bot_data["feishu_webhook_reply_text_func"] = build_feishu_reply_text_func(feishu_client)
            application.bot_data["feishu_webhook_server_config"] = FeishuWebhookServerConfig(
                host=settings.feishu_webhook_host,
                port=settings.feishu_webhook_port,
                path=settings.feishu_webhook_path,
            )
    if settings.wecom_token and settings.wecom_encoding_aes_key and settings.wecom_receive_id:
        application.bot_data[WECOM_TOKEN_BOT_DATA_KEY] = settings.wecom_token
        application.bot_data[WECOM_ENCODING_AES_KEY_BOT_DATA_KEY] = settings.wecom_encoding_aes_key
        application.bot_data[WECOM_RECEIVE_ID_BOT_DATA_KEY] = settings.wecom_receive_id
        application.bot_data["wecom_webhook_server_config"] = WeComWebhookServerConfig(
            host=settings.wecom_webhook_host,
            port=settings.wecom_webhook_port,
            path=settings.wecom_webhook_path,
        )
    _run_application_polling(application)


if __name__ == "__main__":
    main()

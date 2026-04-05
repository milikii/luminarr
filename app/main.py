from __future__ import annotations

import json

from app.bot.feishu_adapter import FEISHU_ENCRYPT_KEY_BOT_DATA_KEY, build_feishu_reply_text_func
from app.bot.feishu_webhook_server import FeishuWebhookServerConfig
from app.bot.personal_wechat_login import PERSONAL_WECHAT_LOGIN_SERVICE_KEY, PersonalWeChatLoginService
from app.bot.wecom_adapter import (
    WECOM_ENCODING_AES_KEY_BOT_DATA_KEY,
    WECOM_RECEIVE_ID_BOT_DATA_KEY,
    WECOM_TOKEN_BOT_DATA_KEY,
)
from app.bot.wecom_webhook_server import WeComWebhookServerConfig
from app.bot.telegram_bot import build_application
from app.clients.emby import EmbyClient
from app.clients.feishu import FeishuClient
from app.clients.fanart import FanartClient
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


async def _skip_fanart_images(_: str):
    return None


def _build_downloader_instances_by_name(
    instances: tuple[DownloaderInstanceConfig, ...],
) -> dict[str, DownloaderInstanceConfig]:
    return {instance.name: instance for instance in instances}


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


def _resolve_downloader_payload_value(payload_json: str, key: str) -> str:
    cleaned_payload = payload_json.strip()
    if not cleaned_payload:
        return ""
    try:
        payload = json.loads(cleaned_payload)
    except json.JSONDecodeError:
        return ""
    if not isinstance(payload, dict):
        return ""
    return str(payload.get(key, "")).strip()


def _resolve_downloader_name_for_task(
    *,
    task_ref: str,
    chat_id: int | None,
    job_repo: JobRepo,
) -> str:
    if chat_id is None or chat_id <= 0:
        return ""
    try:
        downloader_job = job_repo.get_downloader_job_for_chat_ref(chat_id=chat_id, task_ref=task_ref)
    except Exception:
        return ""
    if downloader_job is None:
        return ""
    return _resolve_downloader_payload_value(downloader_job.payload_json, "downloader_name")


def _build_bt_source_providers(
    *,
    prowlarr_client: ProwlarrClient,
    bt_web_sources: tuple[str, ...],
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
        client = WebSourceClient(rule=rule)
        providers.append(BtSourceProvider(name=rule.name, search_func=client.search))
    return tuple(providers)


def main() -> None:
    settings = load_settings()
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
        )
    )
    tmdb_lookup_movie_func = None
    scrape_metadata_func = None
    if settings.tmdb_api_key:
        tmdb_client = TmdbClient(api_key=settings.tmdb_api_key, base_url=settings.tmdb_base_url)
        tmdb_lookup_movie_func = tmdb_client.search_movie
        get_movie_images_func = _skip_fanart_images
        if settings.fanart_api_key:
            fanart_client = FanartClient(api_key=settings.fanart_api_key, base_url=settings.fanart_base_url)
            get_movie_images_func = fanart_client.get_movie_images
        metadata_scraper_service = MetadataScraperService(
            lookup_movie_func=tmdb_client.search_movie,
            get_movie_images_func=get_movie_images_func,
        )
        scrape_metadata_func = metadata_scraper_service.scrape_for_import
    search_service = SearchMediaService(
        search_func=prowlarr_client.search,
        raw_search_func=bt_source_adapter.search,
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
        client = resolve_downloader_client_by_name(downloader_name)
        return await client.add_torrent(source, download_dir=download_dir)

    async def get_torrent_status_with_routing(task_ref: str, chat_id: int | None = None) -> TransmissionTaskStatus | None:
        downloader_name = _resolve_downloader_name_for_task(
            task_ref=task_ref,
            chat_id=chat_id,
            job_repo=job_repo,
        )
        client = resolve_downloader_client_by_name(downloader_name)
        return await client.get_torrent_status(task_ref)

    async def get_torrent_import_source_with_routing(
        task_ref: str,
        chat_id: int | None = None,
    ) -> TransmissionImportSource | None:
        downloader_name = _resolve_downloader_name_for_task(
            task_ref=task_ref,
            chat_id=chat_id,
            job_repo=job_repo,
        )
        client = resolve_downloader_client_by_name(downloader_name)
        return await client.get_torrent_import_source(task_ref)

    add_to_downloader_service = AddToDownloaderService(
        search_service=search_service,
        add_torrent_func=add_torrent_with_routing,
        approval_repo=approval_repo,
        job_repo=job_repo,
        job_event_repo=job_event_repo,
        download_monitor_repo=download_monitor_repo,
    )
    refresh_media_server_func = None
    if settings.emby_base_url and settings.emby_api_key:
        emby_client = EmbyClient(base_url=settings.emby_base_url, api_key=settings.emby_api_key)
        refresh_service = RefreshMediaServerService(emby_client.refresh_library)
        refresh_media_server_func = refresh_service.refresh_text
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
        ).translate_for_import,
        job_event_repo=job_event_repo,
        approval_repo=approval_repo,
        job_repo=job_repo,
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
        telegram_update_repo=telegram_update_repo,
        job_repo=job_repo,
        bt_pending_repo=bt_pending_repo,
        bt_tmdb_movie_candidates_lookup_func=tmdb_client.search_movie_candidates if settings.tmdb_api_key else None,
        bt_tmdb_tv_candidates_lookup_func=tmdb_client.search_tv_candidates if settings.tmdb_api_key else None,
        raw_bt_destination_options=settings.raw_bt_destination_options,
        downloader_instances=settings.downloader_instances,
        downloader_role_binding=settings.downloader_role_binding,
    )
    application.bot_data[PERSONAL_WECHAT_LOGIN_SERVICE_KEY] = PersonalWeChatLoginService()
    if settings.feishu_app_id and settings.feishu_app_secret:
        feishu_client = FeishuClient(
            app_id=settings.feishu_app_id,
            app_secret=settings.feishu_app_secret,
            base_url=settings.feishu_base_url,
        )
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
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

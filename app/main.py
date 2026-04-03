from __future__ import annotations

from app.bot.telegram_bot import build_application
from app.clients.emby import EmbyClient
from app.clients.fanart import FanartClient
from app.clients.prowlarr import ProwlarrClient
from app.clients.tmdb import TmdbClient
from app.clients.transmission import TransmissionClient
from app.config import load_settings
from app.db.approval_repo import ApprovalRepo
from app.db.candidate_repo import CandidateMappingRepo
from app.db.clarification_repo import ClarificationRepo
from app.db.download_monitor_repo import DownloadMonitorRepo
from app.db.job_event_repo import JobEventRepo
from app.db.job_repo import JobRepo
from app.db.sqlite import SqliteDatabase
from app.db.telegram_update_repo import TelegramUpdateRepo
from app.db.watchlist_repo import WatchlistRepo
from app.services.add_to_downloader import AddToDownloaderService
from app.services.get_download_status import GetDownloadStatusService
from app.services.import_to_library import ImportToLibraryService
from app.services.manage_watchlist import ManageWatchlistService
from app.services.metadata_scraper import MetadataScraperService
from app.services.post_download_auto_import import PostDownloadAutoImportService
from app.services.refresh_media_server import RefreshMediaServerService
from app.services.search_media import SearchMediaService


async def _skip_fanart_images(_: str):
    return None


def main() -> None:
    settings = load_settings()
    database = SqliteDatabase(settings.sqlite_db_path)
    database.initialize()
    candidate_repo = CandidateMappingRepo(database)
    job_event_repo = JobEventRepo(database)
    job_repo = JobRepo(database)
    approval_repo = ApprovalRepo(database)
    download_monitor_repo = DownloadMonitorRepo(database)
    telegram_update_repo = TelegramUpdateRepo(database)
    watchlist_repo = WatchlistRepo(database)
    clarification_repo = ClarificationRepo(database)

    prowlarr_client = ProwlarrClient(
        base_url=settings.prowlarr_base_url,
        api_key=settings.prowlarr_api_key,
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
        candidate_repo=candidate_repo,
        clarification_repo=clarification_repo,
        lookup_movie_func=tmdb_lookup_movie_func,
    )
    transmission_client = TransmissionClient(
        base_url=settings.transmission_base_url,
        username=settings.transmission_username,
        password=settings.transmission_password,
    )
    add_to_downloader_service = AddToDownloaderService(
        search_service=search_service,
        add_torrent_func=transmission_client.add_torrent,
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
        get_import_source_func=transmission_client.get_torrent_import_source,
        library_target_dir=settings.library_target_dir,
        refresh_media_server_func=refresh_media_server_func,
        scrape_metadata_func=scrape_metadata_func,
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
        transmission_client.get_torrent_status,
        download_monitor_repo=download_monitor_repo,
        job_event_repo=job_event_repo,
        post_download_auto_import_service=post_download_auto_import_service,
    )
    manage_watchlist_service = ManageWatchlistService(watchlist_repo)
    application = build_application(
        settings.telegram_bot_token,
        search_service,
        add_to_downloader_service,
        get_download_status_service,
        import_to_library_service,
        manage_watchlist_service,
        telegram_update_repo=telegram_update_repo,
        job_repo=job_repo,
    )
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

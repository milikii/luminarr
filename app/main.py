from __future__ import annotations

from app.bot.telegram_bot import build_application
from app.clients.emby import EmbyClient
from app.clients.prowlarr import ProwlarrClient
from app.clients.transmission import TransmissionClient
from app.config import load_settings
from app.services.add_to_downloader import AddToDownloaderService
from app.services.get_download_status import GetDownloadStatusService
from app.services.import_to_library import ImportToLibraryService
from app.services.refresh_media_server import RefreshMediaServerService
from app.services.search_media import SearchMediaService


def main() -> None:
    settings = load_settings()
    prowlarr_client = ProwlarrClient(
        base_url=settings.prowlarr_base_url,
        api_key=settings.prowlarr_api_key,
    )
    search_service = SearchMediaService(prowlarr_client.search)
    transmission_client = TransmissionClient(
        base_url=settings.transmission_base_url,
        username=settings.transmission_username,
        password=settings.transmission_password,
    )
    add_to_downloader_service = AddToDownloaderService(
        search_service=search_service,
        add_torrent_func=transmission_client.add_torrent,
    )
    get_download_status_service = GetDownloadStatusService(transmission_client.get_torrent_status)
    refresh_media_server_func = None
    if settings.emby_base_url and settings.emby_api_key:
        emby_client = EmbyClient(base_url=settings.emby_base_url, api_key=settings.emby_api_key)
        refresh_service = RefreshMediaServerService(emby_client.refresh_library)
        refresh_media_server_func = refresh_service.refresh_text
    import_to_library_service = ImportToLibraryService(
        get_import_source_func=transmission_client.get_torrent_import_source,
        library_target_dir=settings.library_target_dir,
        refresh_media_server_func=refresh_media_server_func,
    )
    application = build_application(
        settings.telegram_bot_token,
        search_service,
        add_to_downloader_service,
        get_download_status_service,
        import_to_library_service,
    )
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

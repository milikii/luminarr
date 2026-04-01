from __future__ import annotations

from app.bot.telegram_bot import build_application
from app.clients.prowlarr import ProwlarrClient
from app.config import load_settings
from app.services.search_media import SearchMediaService


def main() -> None:
    settings = load_settings()
    prowlarr_client = ProwlarrClient(
        base_url=settings.prowlarr_base_url,
        api_key=settings.prowlarr_api_key,
    )
    search_service = SearchMediaService(prowlarr_client.search)
    application = build_application(settings.telegram_bot_token, search_service)
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

from __future__ import annotations

from app.bot.telegram_bot import build_application
from app.config import load_settings


def main() -> None:
    settings = load_settings()
    application = build_application(settings.telegram_bot_token)
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

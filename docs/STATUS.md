# Current status

## Project position
Luminarr is in early implementation.
The chosen direction is:
- self-built minimal runtime
- Telegram as the only primary validation channel
- WeChat postponed to later phase
- Docker Compose deployment target
- shared `/data` root path inside containers

## What is already decided
- narrow vertical scope: media automation only
- Python + FastAPI + SQLite
- Prowlarr for search
- one downloader first (Transmission or qBittorrent)
- Jellyfin / Emby refresh after import
- hardlink-first import strategy

## What is not implemented yet
- `search_media` workflow
- downloader integration
- `import_to_library`
- media server refresh
- watchlist workflow
- subtitle workflow

## What is implemented now
- Telegram bot minimal runtime
- basic config loading (`TELEGRAM_BOT_TOKEN`)
- receives a message and replies with fixed text `✅ 我收到了`
- minimal tests for config and message handler

## Latest verification (2026-04-01)
- manual check: Telegram bot reply confirmed with `✅ 我收到了`
- tests: `tests/test_config.py` and `tests/test_telegram_bot.py` passed

## Current priority
Build the next smallest path:
1. parse user query into `search_media`
2. call Prowlarr search
3. return readable candidate list to Telegram

## Current risks
- path design must stay compatible with Docker shared root
- hardlinks require same filesystem
- avoid introducing too many tools too early
- avoid premature WeChat support
- keep `search_media` output stable enough for next "select" step

## Acceptance focus
For now, success means:
- Telegram minimal loop is stable and testable
- `search_media` can return readable candidates for manual selection
- manual verification steps are clear

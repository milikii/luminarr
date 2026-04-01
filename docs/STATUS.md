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
- downloader integration
- `import_to_library`
- media server refresh
- watchlist workflow
- subtitle workflow

## What is implemented now
- Telegram bot minimal runtime
- basic config loading (`TELEGRAM_BOT_TOKEN`, `PROWLARR_BASE_URL`, `PROWLARR_API_KEY`)
- Telegram text query triggers `search_media`
- `search_media` calls Prowlarr and returns readable candidate list
- quality fallback: infer quality/source from title when API quality fields are empty
- minimal tests for config, search formatting, and bot handler

## Latest verification (2026-04-01)
- manual check: Telegram bot query confirmed candidate list reply
- manual check: `dune` query now returns populated quality such as `1080p WEB-DL` / `1080p BluRay`
- tests: `tests/test_config.py`, `tests/test_search_media.py`, `tests/test_telegram_bot.py` passed (10 passed)

## Current priority
Build the next smallest path:
1. select one candidate from current search result
2. add selected candidate to one downloader
3. let user query download status by task hash/id

## Current risks
- path design must stay compatible with Docker shared root
- hardlinks require same filesystem
- avoid introducing too many tools too early
- avoid premature WeChat support
- keep search result format stable enough for user selection mapping
- Prowlarr availability and API rate/timeout may affect reply latency

## Acceptance focus
For now, success means:
- search result can be selected deterministically
- add-to-downloader path is testable for one downloader
- manual verification steps are clear

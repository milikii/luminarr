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
- `import_to_library`
- media server refresh
- watchlist workflow
- subtitle workflow

## What is implemented now
- Telegram bot minimal runtime
- basic config loading (`TELEGRAM_BOT_TOKEN`, `PROWLARR_BASE_URL`, `PROWLARR_API_KEY`, `TRANSMISSION_BASE_URL`)
- Telegram text query triggers `search_media`
- `search_media` calls Prowlarr and returns readable candidate list
- quality fallback: infer quality/source from title when API quality fields are empty
- cache recent search candidates in memory (per chat, single-process)
- numeric selection maps to cached candidate index
- `add_to_downloader` integrated with Transmission RPC
- bot reply now includes downloader task id/hash after successful add
- `get_download_status` implemented via `status <id/hash>` / `状态 <id/hash>`
- status reply includes task id/hash, status, progress, download speed, eta
- minimal tests cover config, search formatting, selection mapping, add call behavior, status behavior, and bot routing

## Latest verification (2026-04-01)
- manual check: Telegram bot query confirmed candidate list reply
- manual check: `dune` query now returns populated quality such as `1080p WEB-DL` / `1080p BluRay`
- manual check: Telegram flow passed (`dune` -> `5`) and bot replied task id/hash (`ID: 87`, `Hash: b305bf9427799bb31499c9efd4a362ec831e4bd6`)
- manual check: status query path is not manually re-verified in this round
- tests: `tests/test_config.py`, `tests/test_search_media.py`, `tests/test_add_to_downloader.py`, `tests/test_get_download_status.py`, `tests/test_telegram_bot.py` passed (28 passed)

## Current priority
Build the next smallest path:
1. detect download completion for the selected downloader path
2. implement minimal `import_to_library` with hardlink-first strategy
3. keep current Telegram query/add/status behaviors unchanged

## Current risks
- path design must stay compatible with Docker shared root
- hardlinks require same filesystem
- avoid introducing too many tools too early
- avoid premature WeChat support
- cached selection is memory-only; restart will lose recent mapping
- search result format must stay stable enough for index mapping
- candidate source field differences (`downloadUrl` / `magnetUrl` / `guid`) may cause add failures
- status command format must avoid collision with normal free-text search
- Transmission availability, session-id handshake, and network timeout may affect add latency
- Prowlarr availability and API rate/timeout may affect reply latency

## Acceptance focus
For now, success means:
- completion-to-import path is deterministic and testable for one downloader
- hardlink-first behavior and fallback/error message are explicit
- manual verification steps are clear

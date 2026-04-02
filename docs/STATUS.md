# Current status

## Project position
Luminarr is in early implementation, under the fixed v12 runtime profile:
- Telegram private chat only
- TMDB as metadata source (full flow not landed yet)
- Prowlarr as search source
- Transmission as only downloader
- Emby as only media server
- Docker Compose + shared `/data` root
- movie-first narrow workflow

## What is already decided
- narrow vertical scope: media automation harness only
- parser-first, LLM-fallback
- hardlink-first import
- keep tool surface small and stable
- finish refresh before persistence/approval/recovery

## What is implemented now
- Telegram bot minimal runtime
- config loading for Telegram / Prowlarr / Transmission
- Telegram text query triggers `search_media`
- search result candidate cache (in-memory, per chat, single process)
- numeric select -> `add_to_downloader` -> Transmission RPC
- `status <id/hash>` / `状态 <id/hash>` query path
- `import <id/hash>` / `导入 <id/hash>` hardlink import path
- import returns deterministic success/failure text
- minimal Emby client + `refresh_media_server`
- refresh is triggered only after import success
- refresh returns deterministic text:
  - success: `媒体库刷新成功。`
  - failure: `媒体库刷新失败：<reason>`
- tests cover config, bot routing, search/import, and refresh success/failure

## What is not implemented yet
- TMDB-first metadata resolution + Chinese poster-card display
- fixed v12 search plan (English title + year, original title fallback)
- candidate persistence (replace memory-only cache)
- approval persistence and approval flow
- durable job/event state in SQLite
- lease/version recovery and retry path
- watchlist workflow

## Latest verification (2026-04-02)
- tests: `46 passed` (`.venv/bin/python -m pytest -q -s`)
- manual end-to-end verification in WSL test stack (Transmission + Emby) passed:
  - `status e93d696a3e980458765f8016ce39f61437cc9543` returned completed seeding state
  - `import e93d696a3e980458765f8016ce39f61437cc9543` returned deterministic import success text
  - import reply included `媒体库刷新成功。`
  - Emby UI confirmed item visible after refresh

## Current priority
Build the next smallest path:
1. keep current search/select/add/status/import/refresh behavior stable
2. add minimal persistence for completion-to-refresh chain
3. postpone approval/recovery until persistence baseline is stable

## Current risks
- if `EMBY_BASE_URL` / `EMBY_API_KEY` is missing, import still succeeds but refresh will not run
- candidate cache is memory-only; restart loses index mapping
- Transmission `downloadDir + name` must map to container-visible paths
- hardlink import has no copy fallback for cross-filesystem case
- current state is not recoverable across restart beyond Transmission's own persistence

## Acceptance focus for next step
- persistence path does not change current Telegram command behavior
- persistence writes are deterministic and testable
- refresh chain remains stable after persistence is introduced

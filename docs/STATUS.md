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
- config loading for Telegram / Prowlarr / Transmission / SQLite path
- Telegram text query triggers `search_media`
- search result candidate mapping persistence (SQLite, per chat + index)
- in-memory candidate cache remains as fast path in-process
- numeric select -> `add_to_downloader` -> Transmission RPC
- `status <id/hash>` / `状态 <id/hash>` query path
- `import <id/hash>` / `导入 <id/hash>` hardlink import path
- import returns deterministic success/failure text
- minimal Emby client + `refresh_media_server`
- refresh is triggered only after import success
- minimal `job_event` persistence for import -> refresh key transitions
- minimal `approval_record` persistence baseline for import side effect
- import stale/duplicate guard reads `approval_record + job_event` on restart-sensitive path
- stale/duplicate rejection keeps deterministic text style (`目标已存在，已拒绝覆盖：...`)
- refresh returns deterministic text:
  - success: `媒体库刷新成功。`
  - failure: `媒体库刷新失败：<reason>`
- tests cover config, bot routing, search/import/refresh, and SQLite persistence baseline

## What is not implemented yet
- TMDB-first metadata resolution + Chinese poster-card display
- fixed v12 search plan (English title + year, original title fallback)
- explicit approval interaction flow
- lease/version recovery and retry path
- watchlist workflow

## Latest verification (2026-04-02)
- tests: `55 passed` (`.venv/bin/python -m pytest -q -s`)
- manual end-to-end verification in WSL test stack (Transmission + Emby) passed:
  - `status e93d696a3e980458765f8016ce39f61437cc9543` returned completed seeding state
  - `import e93d696a3e980458765f8016ce39f61437cc9543` returned deterministic import success text
  - import reply included `媒体库刷新成功。`
  - Emby UI confirmed item visible after refresh

## Current priority
Build the next smallest path:
1. keep current search/select/add/status/import/refresh behavior stable
2. land TMDB-first metadata resolution baseline
3. keep parser-first and deterministic fallback behavior

## Current risks
- if `EMBY_BASE_URL` / `EMBY_API_KEY` is missing, import still succeeds but refresh will not run
- candidate mapping keeps only latest search window per chat; older windows are overwritten
- Transmission `downloadDir + name` must map to container-visible paths
- hardlink import has no copy fallback for cross-filesystem case
- stale guard only covers tasks that already have both `approval_record` and `import.succeeded` event
- job events are append-only traces, not yet a lease/version recovery protocol

## Acceptance focus for next step
- TMDB metadata path stays minimal and testable
- existing command words and routing do not regress
- search/select/add/status/import/refresh chain remains stable

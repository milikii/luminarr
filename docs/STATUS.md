# Current status

## Project position
Luminarr is in early implementation, under the fixed v12 runtime profile:
- Telegram private chat only
- TMDB fixed v12 search-order baseline landed
- Chinese poster-card text baseline landed for movie query reply
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
- config loading for Telegram / Prowlarr / TMDB / Transmission / SQLite path
- Telegram text query triggers `search_media`
- parser-first query normalization (`title + optional year`) in search path
- minimal TMDB movie lookup client wiring
- deterministic v12 search order in search path:
  1) TMDB English title + year
  2) TMDB original title + year (only when step 1 misses)
  3) parser-first normalized original query (only when TMDB unavailable/no hit)
- movie query reply prepends deterministic Chinese poster-card text block
- candidate list text block keeps original numbering format for numeric select compatibility
- search result candidate mapping persistence (SQLite, per chat + index)
- in-memory candidate cache remains as fast path in-process
- numeric select -> `add_to_downloader` -> Transmission RPC
- `status <id/hash>` / `状态 <id/hash>` query path
- `import <id/hash>` / `导入 <id/hash>` now returns deterministic approval-pending text, no side effect
- `confirm <id/hash>` / `确认 <id/hash>` executes import hardlink + refresh flow
- minimal Emby client + `refresh_media_server`
- refresh is triggered only after confirmed import success
- minimal `job_event` persistence for import -> refresh key transitions
- `approval_record` supports pending/approved state transitions for import approval flow
- `approval_record` now keeps minimal lease/version markers (`lease_version`, `executed_version`)
- `import <id/hash>` now advances lease snapshot deterministically when entering pending
- `confirm <id/hash>` now uses lease snapshot CAS guard and only executes current version
- failed confirm execution restores `pending` on the same lease version (no extra lease bump)
- stale/duplicate confirm guard can reject replay deterministically by version after restart
- stale/duplicate rejection keeps deterministic text style (`目标已存在，已拒绝覆盖：...`)
- refresh returns deterministic text:
  - success: `媒体库刷新成功。`
  - failure: `媒体库刷新失败：<reason>`
- tests cover config, bot routing, search/import/refresh, approval flow, and SQLite persistence baseline

## What is not implemented yet
- watchlist workflow

## Latest verification (2026-04-02)
- tests: `82 passed` (`.venv/bin/python -m pytest -q -s`)
- manual end-to-end verification for the new lease/version replay guard is not re-run yet in this iteration

## Current priority
Build the next smallest path:
1. keep current search/select/add/status/import/confirm/refresh behavior stable
2. land watchlist workflow baseline
3. keep fixed search-order + poster-card reply behavior and tests stable

## Current risks
- if `EMBY_BASE_URL` / `EMBY_API_KEY` is missing, confirmed import still succeeds but refresh will not run
- if `TMDB_API_KEY` is missing, search path falls back to parser-first normalized Prowlarr direct search
- TMDB first-hit strategy may still pick non-best metadata candidate for ambiguous titles
- when TMDB lookup hits but both English/original searches return empty, path does not fall back to original normalized query by design
- poster-card is text-only baseline (`海报: 暂未接入图片`), not real image/media rendering
- candidate mapping keeps only latest search window per chat; older windows are overwritten
- Transmission `downloadDir + name` must map to container-visible paths
- hardlink import has no copy fallback for cross-filesystem case
- lease/version guard is SQLite-local only; no multi-process/global lock guarantee
- approval pending still has no expiry/timeout policy

## Acceptance focus for next step
- watchlist baseline lands without changing existing command words/routing
- existing search/select/add/status/import/confirm/refresh chain remains stable

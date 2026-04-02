# Current status (v15)

## Project position

Luminarr is in early implementation under the fixed v15 runtime profile:
- Telegram private chat only
- TMDB only
- Prowlarr only
- Transmission only
- Emby only
- SQLite only
- Docker Compose only
- movie-first narrow workflow

## What is already implemented now

- Telegram bot minimal runtime
- config loading for Telegram / Prowlarr / TMDB / Transmission / SQLite path
- parser-first query normalization (`title + optional year`)
- minimal TMDB movie lookup wiring
- deterministic search order:
  1. TMDB English title + year
  2. TMDB original title + year (only when step 1 misses)
  3. parser-first normalized original query (only when TMDB unavailable/no hit)
- deterministic Chinese poster-card text baseline
- candidate mapping persistence (SQLite, per chat + index)
- in-memory candidate cache remains as fast path in-process
- numeric select enters explicit downloader approval-pending state before Transmission side effects
- `confirm <id/hash>` / `确认 <id/hash>` now deterministically routes to:
  - downloader dispatch approval wake when matching downloader pending truth exists
  - import approval wake when matching import pending truth exists
- `status <id/hash>` / `状态 <id/hash>` query path
- `import <id/hash>` / `导入 <id/hash>` returns deterministic approval-pending text
- downloader approval confirm executes Transmission dispatch and keeps the existing downloader success text body stable
- `import` confirm still executes hardlink import + refresh
- minimal Emby client + `refresh_media_server`
- refresh only after confirmed import success
- minimal `job_event` persistence for downloader approval + import -> refresh key transitions
- `approval_record` supports pending/approved transitions for import + downloader approval flows
- `approval_record` keeps minimal lease/version markers (`lease_version`, `executed_version`)
- `import <id/hash>` advances lease snapshot deterministically when entering pending
- downloader select approval also advances lease snapshot deterministically when entering pending
- `confirm <id/hash>` uses lease snapshot CAS guard and only executes current version
- failed confirm execution restores `pending` on the same lease version
- stale/duplicate confirm replay is deterministically rejected after restart
- durable `telegram_updates` truth source is landed for Telegram message de-dup
- minimal `jobs` truth source is landed for import wake/replay + downloader approval wake/replay ownership:
  - `jobs.version`
  - `lease_owner`
  - `lease_until`
  - persisted `chat_id/user_id/task_ref/task_id/task_hash`
  - persisted `payload_json` for downloader pending context
- `confirm <id/hash>` rebuilds execution context from persisted job + approval truth before downloader/import execution
- parser-level frustration/reset short-circuit is landed for:
  - cached selection window reset
  - pending import approval cancel
  - pending downloader approval cancel
- smallest persisted manual `manage_watchlist` baseline is landed:
  - `watchlist_item` persisted truth (SQLite, chat-scoped)
  - deterministic Telegram watchlist command path (`watchlist` / `想看`)
  - manual add/list/remove/clear only
  - no downloader/import side effects from watchlist actions
- pending downloader/import approvals now persist timeout truth (`approval_record.expires_at`)
- `confirm <id/hash>` now deterministically rejects expired pending approvals for downloader/import
- expired pending approvals are deterministically converged to cancelled truth in `approval_record + jobs`
- search main path now has minimal reactive recovery baseline for LLM physical failures:
  - deterministic detection for `413` / truncated-style physical errors
  - same-turn one-time compact-and-retry
  - final user-safe text on repeated physical failure (instead of raw backend error)
- tests cover config, routing, search/downloader/import/refresh, approval flow, and SQLite persistence baseline

## What is adopted as a v15 rule, but not implemented yet

- concurrency-safe execution policy for read-only tools
- isolated explore-agent / explore-subflow for ambiguous title resolution

## What is not implemented yet

- copy fallback approval for import
- scheduler / retry baseline for pending tasks
- real image/media poster rendering
- multi-process/global locking semantics
- Telegram callback workflow routing still does not exist, although `telegram_updates` is callback-ready at schema/repo level
- frustration/reset short-circuit currently covers selection + pending-approval paths only; no clarification-stage workflow exists yet

## Latest verification

- tests: `109 passed` (`.venv/bin/python -m pytest -q`)
- manual end-to-end verification for the watchlist baseline was **not** re-run in this iteration

## Current priority

Build the next smallest path:
1. keep current `search/select/add/status/import/confirm/refresh` behavior stable
2. keep manual watchlist baseline behavior stable
3. extend frustration/reset short-circuit into a future clarification-stage workflow
4. keep downloader/import approval behavior and current recovery behavior stable

## Current risks

- if `EMBY_BASE_URL` / `EMBY_API_KEY` is missing, confirmed import still succeeds but refresh will not run
- if `TMDB_API_KEY` is missing, search falls back to parser-normalized Prowlarr direct search
- TMDB first-hit strategy may still pick a non-best candidate for ambiguous titles
- when TMDB lookup hits but both English/original searches return empty, path does not fall back to normalized original query by design
- poster-card is text-only baseline (`海报: 暂未接入图片`)
- candidate mapping keeps only the latest search window per chat
- Transmission `downloadDir + name` must map to container-visible paths
- hardlink import has no copy fallback for cross-filesystem case
- `jobs` ownership protocol is currently wired into import approval wake and downloader dispatch approval wake, not the full workflow chain
- same-task concurrent import approvals across different private chats still effectively share one task-identity truth path
- same-selection downloader approvals are currently scoped by persisted candidate source identity plus chat-scoped ref routing
- frustration/reset short-circuit does not yet cover a future clarification workflow
- watchlist remove currently uses persisted item ID only, not natural-language fuzzy deletion

## Acceptance focus for the next step

- land the smallest clarification-stage frustration/reset coverage baseline
- existing downloader/import approval and confirm routing behavior does not regress
- existing `search/select/status/import/confirm/refresh/watchlist` behavior does not regress
- current search-order + poster-card + candidate mapping behavior remains stable

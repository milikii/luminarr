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
- numeric select -> `add_to_downloader` -> Transmission RPC
- `status <id/hash>` / `状态 <id/hash>` query path
- `import <id/hash>` / `导入 <id/hash>` returns deterministic approval-pending text
- `confirm <id/hash>` / `确认 <id/hash>` executes hardlink import + refresh
- minimal Emby client + `refresh_media_server`
- refresh only after confirmed import success
- minimal `job_event` persistence for import -> refresh key transitions
- `approval_record` supports pending/approved transitions for import approval flow
- `approval_record` keeps minimal lease/version markers (`lease_version`, `executed_version`)
- `import <id/hash>` advances lease snapshot deterministically when entering pending
- `confirm <id/hash>` uses lease snapshot CAS guard and only executes current version
- failed confirm execution restores `pending` on the same lease version
- stale/duplicate confirm replay is deterministically rejected after restart
- durable `telegram_updates` truth source is landed for Telegram message de-dup
- minimal `jobs` truth source is landed for import wake/replay ownership:
  - `jobs.version`
  - `lease_owner`
  - `lease_until`
  - persisted `chat_id/user_id/task_ref/task_id/task_hash`
- `confirm <id/hash>` rebuilds execution context from persisted job + approval truth before import execution
- parser-level frustration/reset short-circuit is landed for:
  - cached selection window reset
  - pending import approval cancel
- tests cover config, routing, search/import/refresh, approval flow, and SQLite persistence baseline

## What is adopted as a v15 rule, but not implemented yet

- concurrency-safe execution policy for read-only tools
- reactive recovery for LLM physical failures (`413`, truncated outputs, aggressive compact-and-retry)
- isolated explore-agent / explore-subflow for ambiguous title resolution
- explicit pre-dispatch approval for `add_to_downloader`

## What is not implemented yet

- `add_to_downloader` approval interaction
- approval expiry / timeout policy
- copy fallback approval for import
- watchlist workflow
- scheduler / retry baseline for pending tasks
- real image/media poster rendering
- multi-process/global locking semantics
- Telegram callback workflow routing still does not exist, although `telegram_updates` is callback-ready at schema/repo level
- frustration/reset short-circuit currently covers selection + pending-approval paths only; no clarification-stage workflow exists yet

## Latest verification

- tests: `89 passed` (`.venv/bin/python -m pytest -q`)
- manual end-to-end verification for the execution-hygiene baseline was **not** re-run in the latest iteration

## Current priority

Build the next smallest path:
1. keep current `search/select/add/status/import/confirm/refresh` behavior stable
2. land explicit pre-dispatch approval for `add_to_downloader`
3. keep search-order + poster-card behavior stable
4. only after the above, return to watchlist baseline

## Current risks

- if `EMBY_BASE_URL` / `EMBY_API_KEY` is missing, confirmed import still succeeds but refresh will not run
- if `TMDB_API_KEY` is missing, search falls back to parser-normalized Prowlarr direct search
- TMDB first-hit strategy may still pick a non-best candidate for ambiguous titles
- when TMDB lookup hits but both English/original searches return empty, path does not fall back to normalized original query by design
- poster-card is text-only baseline (`海报: 暂未接入图片`)
- candidate mapping keeps only the latest search window per chat
- Transmission `downloadDir + name` must map to container-visible paths
- hardlink import has no copy fallback for cross-filesystem case
- `jobs` ownership protocol is currently only wired into import approval wake, not the full workflow chain
- same-task concurrent import approvals across different private chats still effectively share one task-identity truth path
- approval pending still has no expiry / timeout policy
- no reactive compact / same-turn retry for LLM physical failures yet
- frustration/reset short-circuit does not yet cover a future clarification workflow

## Acceptance focus for the next step

- `add_to_downloader` enters pending approval before dispatch side effects
- explicit approve/confirm path for downloader dispatch is deterministic and replay-safe
- existing `search/select/status/import/confirm/refresh` behavior does not regress
- current search-order + poster-card + candidate mapping behavior remains stable

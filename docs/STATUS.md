# Current status (v18)

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
- clarification-stage frustration/reset short-circuit is now landed:
  - when search enters no-result clarification pending, frustration phrases (`不对/停/重来/换一个/算了/取消`) deterministically short-circuit to reset/cancel
  - clarification reset is handled before candidate-window reset in frustration routing
  - downloader/import approval cancel and existing command routing remain unchanged
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
- smallest read-only concurrency-safe execution policy baseline is now landed:
  - runtime policy truth is explicit (`ExecutionPolicy.concurrency_safe`)
  - read-only actions (`search_media` / `get_download_status` / `watchlist list`) are marked concurrency-safe
  - side-effect actions (`add/confirm import/confirm downloader/watchlist mutation/reset-cancel`) stay serialized via a shared execution gate
  - Telegram routing behavior and existing reply texts remain unchanged
- smallest isolated read-only exploration baseline for ambiguous title resolution is now landed:
  - in search read-path, highly ambiguous no-year queries deterministically return clarification text with read-only options
  - ambiguous clarification path does not persist candidate mapping and does not dispatch downloader/import side effects
  - during clarification pending, numeric select is deterministically blocked to avoid side-effect misrouting
- tests cover config, routing, search/downloader/import/refresh, approval flow, and SQLite persistence baseline

## What is adopted as a v15 rule, but not implemented yet

- none

## What is not implemented yet

- copy fallback approval for import
- scheduler / retry baseline for pending tasks
- real image/media poster rendering
- multi-process/global locking semantics
- Telegram callback workflow routing still does not exist, although `telegram_updates` is callback-ready at schema/repo level

## Latest verification

- tests: `113 passed` (`.venv/bin/python -m pytest -q`)
- manual verification: read-only concurrency-safe execution policy baseline passed (`tmp_tests/verify_execution_policy_baseline.py`)
- manual verification: reactive recovery fallback path passed (`retry_count=2` + safe fallback text)
- manual verification: clarification-stage frustration/reset baseline passed (`tmp_tests` script + targeted pytest)
- manual verification: ambiguous read-only exploration baseline passed (temporary `tmp_tests` script + targeted pytest)
- manual end-to-end verification for the watchlist baseline was **not** re-run in this iteration

## Current priority

Build the next smallest path:
1. keep current `search/select/add/status/import/confirm/refresh` behavior stable
2. keep manual watchlist baseline behavior stable
3. keep landed ambiguous read-only exploration behavior stable
4. land the smallest restart-durable clarification pending truth baseline

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
- clarification-stage pending truth is currently in-process memory only and is not restart-durable
- watchlist remove currently uses persisted item ID only, not natural-language fuzzy deletion
- ambiguous-query trigger is rule-based and may still over-trigger for some no-year short titles

## Acceptance focus for the next step

- land the smallest restart-durable clarification pending truth baseline
- existing downloader/import approval and confirm routing behavior does not regress
- existing `search/select/status/import/confirm/refresh/watchlist` behavior does not regress
- current search-order + poster-card + candidate mapping + clarification reset behavior remains stable
- current ambiguous read-only exploration + numeric-select blocking behavior remains stable

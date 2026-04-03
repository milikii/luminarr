# Current status (v22)

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
- smallest restart-durable clarification pending truth baseline is now landed:
  - clarification pending truth is persisted in SQLite (`clarification_state`, chat-scoped)
  - search no-result / ambiguous clarification set + success/reset clear now synchronizes in-memory fast path and persisted truth
  - numeric-select blocking and frustration clarification reset remain deterministic after process restart
  - existing Telegram command words and existing downloader/import success-failure text bodies remain unchanged
- smallest Telegram callback workflow routing baseline is now landed:
  - Telegram runtime now accepts callback updates and routes them through the existing workflow dispatcher
  - callback update de-dup reuses persisted `telegram_updates` callback truth (`callback_query_id`)
  - callback digit/select, `confirm`, and read-only query paths keep the same approval / execution boundary as the existing text path
  - callback path can rebuild chat/user/message context from either `effective_*` fields or callback-owned message context
  - existing Telegram command words and existing downloader/import success-failure text bodies remain unchanged
- smallest copy fallback approval for cross-filesystem import is now landed:
  - hardlink remains the default confirmed import path
  - when confirmed hardlink import hits cross-filesystem failure, the path deterministically enters copy-fallback pending instead of silently copying
  - second `confirm <id/hash>` executes explicit copy import through the existing approval / confirm / `jobs` truth path
  - copy-fallback pending survives restart through persisted `jobs.payload_json` truth
  - existing Telegram command words and existing hardlink success-path text bodies remain unchanged
- smallest completion-monitor / scheduler prerequisite is now landed:
  - downloader dispatch success now persists completion-monitor truth in SQLite (`download_monitor`)
  - `status <id/hash>` updates observed download progress/completion truth without introducing new command words
  - first observed completion deterministically appends `downloader.completed_observed` into `job_event`
  - pending-completion truth survives restart via SQLite and no longer depends on chat transcript memory
  - no background scheduler loop or auto-import side effect is introduced in this step
- smallest post-download auto import baseline is now landed:
  - observed completed download truth can now auto-progress into the existing import approval-pending path
  - auto-progress reuses existing `import_to_library` / approval / `jobs` truth and still requires explicit `confirm <id/hash>` before import side effects
  - cross-filesystem copy-fallback approval remains unchanged on the later confirmed import path
  - existing Telegram command words remain unchanged; `status <id/hash>` may now append import approval-pending text when completion is first observed
  - no generic scheduler platform, resource auto-selection, rename, scrape, or subtitle behavior is introduced in this step
- smallest resource auto-selection rules baseline is now landed:
  - observed completed download truth now passes through a deterministic low-quality resource gate before auto-progressing into the existing import approval-pending path
  - task names matching low-quality markers (`CAM` / `HDCAM` / `TS` / `HDTS` / `TC` / `SCR` / `WORKPRINT`) deterministically skip auto progression
  - skip truth is persisted as `job_event` (`auto_import.skipped_by_rule`) to avoid repeated auto progression / repeated skip text on later `status <id/hash>`
  - skipped resources can still be manually imported via `import <id/hash>`
  - existing Telegram command words remain unchanged; `status <id/hash>` may now append either import approval-pending text or rule-skip text when completion is first observed
  - no rename, scrape, or subtitle behavior is introduced in this step
- smallest filename normalization / rename baseline is now landed:
  - confirmed import path now deterministically computes normalized target naming; when year is available the target follows `Title (Year)` style
  - normalized naming prefers persisted downloader title truth (`downloader.succeeded`) when available, then falls back to Transmission import source name
  - hardlink import and copy-fallback second-confirm import share the same normalized target naming rule
  - existing Telegram command words and approval / ownership / replay boundaries remain unchanged
- tests cover config, routing, search/downloader/import/refresh, approval flow, and SQLite persistence baseline

## Local integration test stack (WSL Docker)

The formal local integration baseline is:
- Transmission test instance: `http://127.0.0.1:19091`
- Emby test instance: `http://127.0.0.1:18096`
- host-side hardlink paths:
  - `/data/downloads/tr`
  - `/data/library/movies`

Use this stack for real downloader/import/refresh verification. The detailed path, health-check, and config placeholder truth now lives in `docs/TEST_ENV.md`.

## What is adopted as a v15 rule, but not implemented yet

- none

## What is not implemented yet

**Near-term control-layer and current-mainline gaps:**
- real image/media poster rendering
- multi-process/global locking semantics

**Stage B automation closure (documented roadmap, not current step):**
- metadata scraping (`TMDB + Fanart.tv`)
- subtitle auto-translation

**Stage C expansion (documented roadmap, not current step):**
- series / anime watchlist-driven tracking
- BT/PT split downloader routing with `qBittorrent` as later BT downloader

**Stage D channel expansion (documented roadmap, not current step):**
- Feishu adapter
- WeCom adapter
- personal WeChat adapter

**Stage E operations cleanup (documented roadmap, not current step):**
- downloader/library asset correlation and cleanup

## Latest verification

- tests: `134 passed` (`.venv/bin/python -m pytest -q`)
- manual verification: resource auto-selection rules baseline passed (temporary `tmp_tests/verify_resource_auto_selection_baseline.py`, script cleaned after run)
- manual verification: post-download auto import baseline passed (temporary `tmp_tests/verify_post_download_auto_import_baseline.py`, script cleaned after run)
- manual verification: completion-monitor / scheduler prerequisite baseline passed (temporary `tmp_tests/verify_download_monitor_prerequisite.py`, script cleaned after run)
- manual verification: copy fallback approval baseline passed (temporary `tmp_tests/verify_import_copy_fallback_approval.py`, script cleaned after run)
- manual verification: filename normalization / rename baseline passed (temporary `tmp_tests/verify_filename_normalization_baseline.py`, script cleaned after run)
- manual verification: Telegram callback workflow routing baseline passed (temporary `tmp_tests/verify_callback_routing.py`, script cleaned after run)
- manual verification: read-only concurrency-safe execution policy baseline passed (`tmp_tests/verify_execution_policy_baseline.py`)
- manual verification: reactive recovery fallback path passed (`retry_count=2` + safe fallback text)
- manual verification: clarification-stage frustration/reset baseline passed (`tmp_tests` script + targeted pytest)
- manual verification: ambiguous read-only exploration baseline passed (temporary `tmp_tests` script + targeted pytest)
- manual verification: restart-durable clarification pending truth baseline passed (temporary `tmp_tests/verify_clarification_persistence.py`, script cleaned after run)
- manual end-to-end verification for the watchlist baseline was **not** re-run in this iteration

## Current priority

Build the next smallest path:
1. keep current `search/select/add/status/import/confirm/refresh` behavior stable
2. keep manual watchlist baseline behavior stable
3. keep landed ambiguous read-only exploration behavior stable
4. keep landed resource auto-selection rules + filename normalization / rename baselines stable
5. land the smallest metadata scraping baseline (`TMDB + Fanart.tv`) without introducing subtitle logic

## Current risks

- if `EMBY_BASE_URL` / `EMBY_API_KEY` is missing, confirmed import still succeeds but refresh will not run
- if `TMDB_API_KEY` is missing, search falls back to parser-normalized Prowlarr direct search
- TMDB first-hit strategy may still pick a non-best candidate for ambiguous titles
- when TMDB lookup hits but both English/original searches return empty, path does not fall back to normalized original query by design
- poster-card is text-only baseline (`海报: 暂未接入图片`)
- candidate mapping keeps only the latest search window per chat
- Transmission `downloadDir + name` must map to container-visible paths
- copy fallback duplicates data and depends on sufficient free disk space
- downloader completion truth and auto-import progression currently advance when runtime observes status; standalone background polling is still not landed
- resource auto-selection baseline currently blocks only explicit low-quality source markers in the download name; broader quality ranking is not landed
- filename normalization baseline currently uses smallest deterministic cleanup + year extraction; noisy release names may still produce imperfect titles
- `jobs` ownership protocol is currently wired into import approval wake and downloader dispatch approval wake, not the full workflow chain
- same-task concurrent import approvals across different private chats still effectively share one task-identity truth path
- same-selection downloader approvals are currently scoped by persisted candidate source identity plus chat-scoped ref routing
- watchlist remove currently uses persisted item ID only, not natural-language fuzzy deletion
- ambiguous-query trigger is rule-based and may still over-trigger for some no-year short titles

## Acceptance focus for the next step

- land the smallest metadata scraping baseline (`TMDB + Fanart.tv`) without changing existing text-command behavior
- keep the landed completion-monitor truth, post-download auto import baseline, and resource auto-selection rules baseline stable
- keep the landed filename normalization / rename baseline stable
- existing downloader/import approval and confirm routing behavior does not regress
- landed Telegram callback workflow routing behavior does not regress
- landed cross-filesystem copy fallback approval behavior does not regress
- landed completion-monitor / scheduler prerequisite behavior does not regress
- landed post-download auto import behavior does not regress
- landed resource auto-selection rules behavior does not regress
- existing `search/select/status/import/confirm/refresh/watchlist` behavior does not regress
- current search-order + poster-card + candidate mapping + clarification reset behavior remains stable
- current ambiguous read-only exploration + numeric-select blocking behavior remains stable

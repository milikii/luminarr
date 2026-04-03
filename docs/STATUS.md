# Current status (v35)

## Project position

Luminarr is in early implementation under the fixed v15 runtime profile:
- Telegram private chat only
- TMDB only
- Prowlarr only
- Transmission + qBittorrent only
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
- smallest series / anime watchlist-driven tracking baseline is now landed:
  - `watchlist_item` persisted truth now includes `media_kind` (`movie` / `series` / `anime`)
  - legacy watchlist rows deterministically migrate to default `movie` truth during SQLite initialization
  - `watchlist add <片名 [年份]>` remains backward compatible and defaults to `movie`
  - `watchlist add <movie|series|anime> <片名 [年份]>` now provides the smallest explicit content-kind input
  - `watchlist list` now displays kind text, and same title/year can coexist across different kinds
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
- smallest metadata scraping (`TMDB + Fanart.tv`) baseline is now landed:
  - confirmed import success path now deterministically triggers metadata scraping on the existing import chain
  - scrape input prefers persisted downloader title truth (`downloader.succeeded`) and falls back to normalized import target naming when truth is missing
  - when `TMDB_API_KEY` exists but `FANART_API_KEY` is missing, metadata sidecar still writes TMDB truth with empty fanart image fields
  - metadata scrape failure is explicitly recorded (`metadata.failed`) and does not roll back confirmed import success
  - existing Telegram command words and approval / ownership / replay boundaries remain unchanged
- smallest subtitle auto-translation baseline is now landed:
  - confirmed import success path now deterministically triggers subtitle auto-translation on the existing import chain
  - subtitle translation defaults to professional model translation (`gpt-5.4`, OpenAI-compatible `chat/completions`) for SubRip (`.srt`) and writes `*.zh.srt`
  - missing subtitle API key / model errors are explicitly recorded (`subtitle.failed`) and do not roll back confirmed import success
  - existing Telegram command words and approval / ownership / replay boundaries remain unchanged
- smallest PT / BT parser-level intent split baseline is now landed:
  - Telegram text/callback routing now deterministically splits normal movie-search demand and direct BT / magnet demand at the existing parser/entry layer
  - raw `magnet:?` links and explicit `下载这个 BT / 下载这个磁力` style text now return a deterministic BT-direct routing prompt instead of falling into the normal movie search path
  - current step remains parser/routing-only; it does not dispatch downloader side effects and does not introduce downloader-role binding
  - existing `search/select/status/import/confirm/watchlist` command words and approval / ownership / replay boundaries remain unchanged
- smallest BT classification follow-up baseline is now landed:
  - after BT-direct routing, Telegram text/callback path now deterministically asks the user to classify the request as `movie` / `series` / `anime` / `raw_bt`
  - while BT classification is pending, valid classification replies deterministically return classification-result text; plain non-classification text returns a reminder instead of falling into the normal movie search path
  - frustration/cancel phrases now clear the current BT classification pending state without affecting downloader/import approval flows
  - current step remains follow-up-only: it does not persist a new BT workflow truth, does not dispatch downloader side effects, does not do TMDB association, and does not do raw BT destination selection
  - existing `search/select/status/import/confirm/watchlist` command words and approval / ownership / replay boundaries remain unchanged
- smallest movie / series / anime BT TMDB association follow-up baseline is now landed:
  - after BT classification, `movie` / `series` / `anime` now deterministically enter the next TMDB association follow-up instead of stopping at classification-result text
  - `movie` association uses TMDB movie candidates; `series` / `anime` association use TMDB TV candidates
  - when TMDB returns a single reliable candidate, Telegram text/callback path now replies with deterministic association-result text (`title / original_title / year / tmdb_id`) and stays side-effect free
  - when TMDB returns no reliable candidate or multiple plausible candidates, Telegram text/callback path now returns deterministic clarification text and stays side-effect free
  - `raw_bt` remains on the existing classification-only path and does not enter TMDB association in this baseline
  - existing `search/select/status/import/confirm/watchlist` command words and approval / ownership / replay boundaries remain unchanged
- smallest `raw_bt` destination-directory follow-up baseline is now landed:
  - after BT classification, `raw_bt` now deterministically enters destination-directory follow-up instead of stopping at classification-result text
  - destination options come from configured pre-set raw-BT directories and are shown in deterministic text/result handling
  - valid replies now accept either directory index or directory key and return deterministic selected-directory text (`key / label / target_dir`) while staying side-effect free
  - invalid raw-BT directory replies now return deterministic reminder text with the available options and stay side-effect free
  - missing raw-BT destination configuration now returns explicit not-ready text instead of silently falling through to other routes
  - existing `search/select/status/import/confirm/watchlist` command words and approval / ownership / replay boundaries remain unchanged
- smallest downloader-role binding baseline is now landed:
  - configuration now supports the smallest downloader instance truth (`name / type / base_url / download_dir`, with optional username/password)
  - configuration now supports deterministic role binding truth for `pt_downloader` and `bt_downloader`
  - role binding currently binds PT / BT to configured downloader instance names without changing existing downloader side effects in this baseline
  - BT classification / TMDB association / raw-BT destination pending truth is now persisted in SQLite (`bt_pending_state`) and no longer disappears after process restart
  - existing `search/select/status/import/confirm/watchlist` command words and approval / ownership / replay boundaries remain unchanged
- smallest BT dispatch / transfer execution baseline is now landed:
  - PT numeric select now deterministically enters the existing downloader approval flow with the configured `pt_downloader` Transmission instance truth
  - BT `movie / series / anime` now deterministically continue from TMDB association success into the existing downloader approval flow with the configured `bt_downloader` Transmission instance truth
  - `raw_bt` now deterministically continues from destination-directory selection into the existing downloader approval flow, and confirmed dispatch passes the selected target directory to Transmission `download-dir`
  - downloader completed truth now updates `jobs` with the real downloader task identity (`task_id / task_hash`) after confirmed dispatch, so later `status <id/hash>` / `import <id/hash>` can route through the persisted downloader truth
  - `status <id/hash>` and media import-source lookup now deterministically route through the persisted downloader instance truth instead of assuming a single legacy Transmission client
  - `raw_bt` confirmed dispatch does not register post-download auto-import truth, and manual `import <id/hash>` now deterministically rejects `raw_bt` tasks with explicit text instead of entering the media import chain
  - this baseline originally stopped at Transmission-only execution; qBittorrent request execution is now supplied by the later qBittorrent protocol baseline below
  - existing `search/select/status/import/confirm/watchlist` command words and approval / ownership / replay boundaries remain unchanged
- smallest qBittorrent protocol execution and broader multi-instance downloader support baseline is now landed:
  - downloader execution now routes by configured downloader type instead of assuming Transmission after role resolution
  - qBittorrent now supports the smallest real execution path:
    - add torrent / magnet
    - get status
    - get import source
  - qBittorrent-bound PT tasks can now complete the existing downloader approval -> `confirm` -> status -> import-source chain without silently falling back to Transmission
  - qBittorrent-bound `raw_bt` tasks now keep using the user-selected destination directory truth during dispatch
  - BT follow-up text protocol and existing approval / ownership / replay boundaries remain unchanged; when the user only sends “下载这个 BT” without a real `magnet:?`, Telegram now deterministically asks for the actual magnet link instead of surfacing internal execution wording
  - current qBittorrent protocol baseline stays minimal:
    - add/status/import-source only
    - no qB categories/tags/rule engine
    - no scheduler/platformization
- smallest BT subscription / continuous-download baseline is now landed:
  - SQLite now persists the smallest BT subscription truth (`bt_subscription_item`) with:
    - `title`
    - `year`
    - `media_kind`
    - `last_seen_source`
    - `last_seen_title`
  - Telegram now supports the smallest manual BT subscription command path:
    - `btsub list`
    - `btsub add <movie|series|anime> <片名 [年份]>`
    - `btsub remove <条目ID>`
    - `btsub clear`
    - `btsub run`
  - `btsub run` now deterministically scans the current chat's persisted BT subscriptions through the existing Prowlarr search path and picks the first downloadable candidate
  - when the scanned source differs from persisted `last_seen_source`, the hit deterministically reuses the existing downloader approval-pending path instead of dispatching immediately
  - repeated `btsub run` does not re-enqueue the same seen source, and the seen-source truth survives restart
  - current BT subscription baseline stays minimal:
    - no background scheduler loop
    - no generic rule engine
    - no automatic `confirm`
    - no `raw_bt` subscription
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
- none

**Stage C expansion (documented roadmap, not current step):**
- BT subscription scheduler-tick baseline on top of the landed manual `btsub run` subscription truth

**Stage D channel expansion (documented roadmap, not current step):**
- Feishu adapter
- WeCom adapter
- personal WeChat adapter

**Stage E operations cleanup (documented roadmap, not current step):**
- downloader/library asset correlation and cleanup

## Latest verification

- tests: `191 passed` (`.venv/bin/python -m pytest -q`)
- focused tests: `10 passed, 29 deselected` (`.venv/bin/python -m pytest -q tests/test_manage_watchlist.py tests/test_telegram_bot.py -k watchlist`)
- focused tests: `49 passed` (`.venv/bin/python -m pytest -q tests/test_telegram_bot.py tests/test_tmdb_client.py`)
- focused tests: `62 passed` (`.venv/bin/python -m pytest -q tests/test_telegram_bot.py tests/test_config.py`)
- focused tests: `92 passed` (`.venv/bin/python -m pytest -q tests/test_config.py tests/test_persistence_sqlite.py tests/test_telegram_bot.py`)
- manual verification: series / anime watchlist-driven tracking baseline passed (temporary `tmp_tests/verify_watchlist_media_kind_baseline.py`, script cleaned after run)
- manual verification: resource auto-selection rules baseline passed (temporary `tmp_tests/verify_resource_auto_selection_baseline.py`, script cleaned after run)
- manual verification: post-download auto import baseline passed (temporary `tmp_tests/verify_post_download_auto_import_baseline.py`, script cleaned after run)
- manual verification: completion-monitor / scheduler prerequisite baseline passed (temporary `tmp_tests/verify_download_monitor_prerequisite.py`, script cleaned after run)
- manual verification: copy fallback approval baseline passed (temporary `tmp_tests/verify_import_copy_fallback_approval.py`, script cleaned after run)
- manual verification: filename normalization / rename baseline passed (temporary `tmp_tests/verify_filename_normalization_baseline.py`, script cleaned after run)
- manual verification: metadata scraping (`TMDB + Fanart.tv`) baseline passed (temporary `tmp_tests/verify_metadata_scraping_baseline.py`, script cleaned after run)
- manual verification: subtitle auto-translation baseline passed (temporary `tmp_tests/verify_subtitle_auto_translation_baseline.py` and `tmp_tests/verify_subtitle_professional_translation_live.py`, scripts cleaned after run)
- manual verification: Telegram callback workflow routing baseline passed (temporary `tmp_tests/verify_callback_routing.py`, script cleaned after run)
- manual verification: read-only concurrency-safe execution policy baseline passed (`tmp_tests/verify_execution_policy_baseline.py`)
- manual verification: reactive recovery fallback path passed (`retry_count=2` + safe fallback text)
- manual verification: clarification-stage frustration/reset baseline passed (`tmp_tests` script + targeted pytest)
- manual verification: ambiguous read-only exploration baseline passed (temporary `tmp_tests` script + targeted pytest)
- manual verification: restart-durable clarification pending truth baseline passed (temporary `tmp_tests/verify_clarification_persistence.py`, script cleaned after run)
- focused tests: `39 passed` (`.venv/bin/python -m pytest -q tests/test_telegram_bot.py`)
- manual verification: PT / BT parser-level intent split baseline passed (temporary `tmp_tests/verify_pt_bt_parser_split_baseline.py`, script cleaned after run)
- manual verification: BT classification follow-up baseline passed (temporary `tmp_tests/verify_bt_classification_followup.py`, script cleaned after run)
- manual verification: BT `movie / series / anime` TMDB association follow-up baseline passed (temporary `tmp_tests/verify_bt_tmdb_association_followup.py`, script cleaned after run)
- manual verification: `raw_bt` destination-directory follow-up baseline passed (temporary `tmp_tests/verify_raw_bt_destination_followup.py`, script cleaned after run)
- manual verification: downloader-role binding baseline passed (temporary `tmp_tests/verify_downloader_role_binding_baseline.py`, script cleaned after run)
- manual verification: BT dispatch / transfer execution baseline passed (temporary `tmp_tests/verify_bt_dispatch_execution_baseline.py`, script cleaned after run)
- focused tests: `41 passed` (`.venv/bin/python -m pytest -q tests/test_qbittorrent_client.py tests/test_add_to_downloader.py tests/test_get_download_status.py tests/test_config.py`)
- focused tests: `80 passed` (`.venv/bin/python -m pytest -q tests/test_telegram_bot.py tests/test_import_to_library.py`)
- focused tests: `3 passed` (`.venv/bin/python -m pytest -q tests/test_manage_bt_subscription.py`)
- focused tests: `1 passed` (`.venv/bin/python -m pytest -q tests/test_execution_policy.py`)
- focused tests: `54 passed` (`.venv/bin/python -m pytest -q tests/test_telegram_bot.py`)
- focused tests: `10 passed` (`.venv/bin/python -m pytest -q tests/test_add_to_downloader.py`)
- focused tests: `2 passed` (`.venv/bin/python -m pytest -q tests/test_persistence_sqlite.py::test_downloader_pending_approval_persists_for_restart tests/test_persistence_sqlite.py::test_confirm_rebuilds_context_from_persisted_job_after_restart`)
- manual verification: qBittorrent protocol execution and broader multi-instance downloader support baseline passed (temporary `tmp_tests/verify_qbittorrent_protocol_baseline.py`, script cleaned after run)
- manual verification: BT subscription / continuous-download baseline passed (temporary `tmp_tests/verify_bt_subscription_baseline.py`, script cleaned after run)
- manual end-to-end verification for the watchlist baseline was **not** re-run in this iteration

## Current priority

Build the next smallest path:
1. keep current `search/select/add/status/import/confirm/refresh` behavior stable
2. keep landed watchlist media-kind behavior stable
3. keep landed ambiguous read-only exploration behavior stable
4. keep landed BT classification follow-up baseline stable
5. keep landed BT `movie / series / anime` TMDB association follow-up baseline stable
6. keep landed `raw_bt` destination-directory follow-up baseline stable
7. keep landed downloader-role binding baseline stable
8. keep landed BT dispatch / transfer execution baseline stable
9. keep landed qBittorrent protocol execution and broader multi-instance downloader support baseline stable
10. land the smallest BT subscription scheduler-tick baseline without broadening into generic scheduler/platformization

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
- metadata scraping baseline is best-effort; TMDB/Fanart/query/write failures are recorded but do not block confirmed import success
- when `FANART_API_KEY` is missing, metadata sidecar keeps empty fanart image URLs by design
- subtitle auto-translation baseline is best-effort; missing `SUBTITLE_TRANSLATION_API_KEY` or model/network failure is recorded and does not block confirmed import success
- subtitle auto-translation currently only targets SubRip (`.srt`) files; non-`.srt` subtitle formats are not processed in this baseline
- `jobs` ownership protocol is currently wired into import approval wake and downloader dispatch approval wake, not the full workflow chain
- same-task concurrent import approvals across different private chats still effectively share one task-identity truth path
- same-selection downloader approvals are currently scoped by persisted candidate source identity plus chat-scoped ref routing
- watchlist remove currently uses persisted item ID only, not natural-language fuzzy deletion
- watchlist kind is currently user-declared (`movie` / `series` / `anime`); no automatic kind inference or fuzzy correction is introduced in this baseline
- ambiguous-query trigger is rule-based and may still over-trigger for some no-year short titles
- current BT-direct intent split baseline is intentionally narrow; only raw magnet links and a small set of explicit “下载这个 BT / 磁力” phrases are recognized
- BT classification follow-up, BT TMDB association follow-up, and raw-BT destination follow-up now persist restart-durable pending truth in SQLite, but they still use only the smallest stage + payload protocol instead of a full BT workflow state machine
- BT `series` / `anime` TMDB association currently uses TMDB TV search only; anime movie-style entries may still require the user to retry with a clearer title/year
- qBittorrent protocol baseline currently covers add/status/import-source only; categories/tags/rule engine and more advanced qB features are not landed in this step
- qBittorrent add currently resolves task identity by parsed magnet hash or list-diff fallback after add; unusual duplicate URL-torrent scenarios may still be less deterministic than magnet adds
- when the user only sends “下载这个 BT” without an actual `magnet:?`, BT follow-up now returns explicit “请补实际磁力” text; this is intentional smallest-boundary behavior, not a generic BT parsing engine
- BT subscription baseline currently requires manual `btsub run`; background periodic tick is not landed in this step
- BT subscription de-dup currently keys on exact `last_seen_source`; if indexer source URL shape changes for the same release, it may still be treated as a new hit
- BT subscription scan currently picks the first downloadable Prowlarr result and does not introduce a richer quality-ranking rule set in this step

## Acceptance focus for the next step

- land the smallest BT subscription scheduler-tick baseline without changing existing text-command behavior
- keep the landed watchlist media-kind baseline stable
- keep the landed completion-monitor truth, post-download auto import baseline, and resource auto-selection rules baseline stable
- keep the landed filename normalization / rename baseline stable
- keep the landed metadata scraping (`TMDB + Fanart.tv`) baseline stable
- keep the landed subtitle auto-translation baseline stable
- keep the landed BT classification follow-up baseline stable
- keep the landed BT `movie / series / anime` TMDB association follow-up baseline stable
- keep the landed `raw_bt` destination-directory follow-up baseline stable
- keep the landed downloader-role binding baseline stable
- keep the landed BT dispatch / transfer execution baseline stable
- keep the landed qBittorrent protocol execution and broader multi-instance downloader support baseline stable
- existing downloader/import approval and confirm routing behavior does not regress
- landed Telegram callback workflow routing behavior does not regress
- landed cross-filesystem copy fallback approval behavior does not regress
- landed completion-monitor / scheduler prerequisite behavior does not regress
- landed post-download auto import behavior does not regress
- landed resource auto-selection rules behavior does not regress
- existing `search/select/status/import/confirm/refresh/watchlist` behavior does not regress
- current search-order + poster-card + candidate mapping + clarification reset behavior remains stable
- current ambiguous read-only exploration + numeric-select blocking behavior remains stable
- landed PT / BT parser-level intent split baseline remains deterministic and does not bypass existing side-effect boundaries
- landed BT classification follow-up remains deterministic and does not bypass existing side-effect boundaries
- landed BT `movie / series / anime` TMDB association follow-up remains deterministic and side-effect free
- landed `raw_bt` destination-directory follow-up remains deterministic and side-effect free
- landed downloader-role binding truth remains deterministic and side-effect free
- landed BT dispatch / transfer execution path remains deterministic and does not bypass existing side-effect boundaries
- landed qBittorrent-bound PT / BT execution path remains deterministic and does not silently fall back to Transmission
- landed manual `btsub list/add/remove/clear/run` behavior remains deterministic and persistence-backed

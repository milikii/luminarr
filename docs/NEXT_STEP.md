# Next step (v28)

Prerequisite completed:
- `search_media` + index-based select works
- `add_to_downloader` works for Transmission
- `get_download_status` works
- `import_to_library` hardlink flow works
- `import done -> refresh_media_server (Emby only)` is landed
- candidate mapping persistence is landed (SQLite)
- minimal import -> refresh `job_event` persistence is landed
- explicit import approval interaction is landed:
  - `import <id/hash>` enters pending and does not execute side effect
  - `confirm <id/hash>` executes import + refresh
  - duplicate/stale confirm is deterministically rejected
- minimal lease/version replay guard for import confirm is landed
- durable `telegram_updates` truth source is landed for Telegram message de-dup
- minimal `jobs.version + lease_owner + lease_until` truth source is landed for import wake/replay + downloader approval wake/replay ownership
- `confirm <id/hash>` now rebuilds execution context from persisted job + approval truth
- parser-level frustration/reset short-circuit is landed for selection reset + pending downloader/import cancel
- explicit pre-dispatch approval for `add_to_downloader` is now landed:
  - numeric select enters pending approval before Transmission side effects
  - `confirm <id/hash>` deterministically routes to downloader or import approval wake
  - downloader duplicate/stale confirm is deterministically rejected
  - pending downloader approval survives restart via persisted `job + approval_record` truth
- smallest persisted manual watchlist baseline is now landed:
  - `watchlist_item` SQLite persistence
  - deterministic `watchlist` / `想看` add/list/remove/clear command path
  - no auto-download side effects
- smallest approval expiry / timeout policy baseline is now landed:
  - pending downloader/import approval persists timeout truth (`approval_record.expires_at`)
  - `confirm <id/hash>` deterministically rejects expired pending approvals
  - expired pending approvals converge to cancelled truth (`approval_record + jobs`)
- smallest reactive recovery baseline for LLM physical failures is now landed:
  - deterministic physical failure detection (`413`, truncated-style errors)
  - same-turn one-time compact-and-retry
  - final user-safe fallback text instead of surfacing raw physical backend error
- smallest clarification-stage frustration/reset coverage baseline is now landed:
  - no-result clarification pending truth is tracked per chat in-process
  - frustration phrases (`不对/停/重来/换一个/算了/取消`) deterministically short-circuit clarification reset
  - existing pending downloader/import cancel routing remains stable
- smallest read-only concurrency-safe execution policy baseline is now landed:
  - explicit runtime policy marks read-only actions as `concurrency_safe`
  - read-only actions run without side-effect serialization lock
  - side-effect actions remain serialized through the execution gate
  - existing Telegram command behavior and success/failure text bodies remain unchanged
- smallest isolated read-only exploration baseline for ambiguous title resolution is now landed:
  - highly ambiguous no-year queries return deterministic clarification text with read-only options
  - clarification-path does not persist candidate mapping and does not trigger downloader/import side effects
  - numeric select is blocked while clarification is pending
- smallest restart-durable clarification pending truth baseline is now landed:
  - chat-scoped clarification truth is persisted in SQLite (`clarification_state`)
  - search no-result/ambiguous set + success/reset clear synchronizes in-memory fast path and persisted truth
  - clarification pending numeric-select blocking remains deterministic after process restart
  - existing Telegram command words and existing downloader/import success-failure text bodies remain unchanged
- smallest Telegram callback workflow routing baseline is now landed:
  - Telegram runtime accepts callback updates and routes them into the existing workflow dispatcher
  - callback update de-dup reuses persisted `telegram_updates` callback truth
  - callback path keeps the same side-effect boundary as the existing text-command routing
  - callback path can recover chat/user/message context from either `effective_*` fields or callback-owned context
  - focused tests + manual verification passed
- smallest copy fallback approval for cross-filesystem import is now landed:
  - hardlink remains the default confirmed import path
  - cross-filesystem hardlink failure now deterministically enters explicit copy-fallback pending instead of silently copying
  - second `confirm <id/hash>` executes copy import through the existing approval / confirm / `jobs` truth path
  - copy-fallback pending survives restart through persisted `jobs.payload_json`
  - focused tests + manual verification passed
- smallest completion-monitor / scheduler prerequisite is now landed:
  - downloader dispatch success persists completion-monitor truth in SQLite (`download_monitor`)
  - `status <id/hash>` updates observed download progress/completion truth without changing command words
  - first observed completion deterministically appends `downloader.completed_observed` into `job_event`
  - pending-completion truth survives restart through SQLite
  - focused tests + manual verification passed
- smallest post-download auto import baseline is now landed:
  - observed completed download truth can auto-progress into the existing import approval-pending path
  - auto-progress reuses existing `import_to_library` / approval / `jobs` truth and still requires explicit `confirm <id/hash>` before import side effects
  - cross-filesystem copy-fallback approval remains unchanged on the later confirmed import path
  - existing Telegram command words remain unchanged; `status <id/hash>` may append import approval-pending text when completion is first observed
  - focused tests + manual verification passed
- smallest resource auto-selection rules baseline is now landed:
  - observed completed download truth now passes through the smallest deterministic resource rule set before auto-progressing into import approval-pending
  - explicit low-quality source markers (`CAM` / `HDCAM` / `TS` / `HDTS` / `TC` / `SCR` / `WORKPRINT`) deterministically skip auto progression
  - skipped auto progression appends `auto_import.skipped_by_rule` into `job_event` and does not repeat on later `status <id/hash>`
  - skipped resources still keep the existing manual `import <id/hash>` path
  - focused tests + manual verification passed
- smallest filename normalization / rename baseline is now landed:
  - confirmed import now produces deterministic normalized target naming on the existing import path
  - naming prefers persisted downloader title truth when available and keeps copy-fallback approval boundary unchanged
  - focused tests + manual verification passed
- smallest metadata scraping (`TMDB + Fanart.tv`) baseline is now landed:
  - confirmed import success now deterministically triggers metadata scraping on the existing import success path
  - scrape input prefers persisted downloader title truth and falls back to normalized import target naming
  - with TMDB enabled and Fanart missing, metadata sidecar still writes TMDB truth with empty fanart fields
  - metadata scrape failures are explicitly recorded and do not break confirmed import success
  - focused tests + manual verification passed
- smallest subtitle auto-translation baseline is now landed:
  - confirmed import success now deterministically triggers subtitle auto-translation on the existing import success path
  - subtitle translation defaults to professional model translation (`gpt-5.4`, OpenAI-compatible `chat/completions`) for SubRip (`.srt`) and writes `*.zh.srt`
  - missing subtitle API key / model errors are explicitly recorded and do not break confirmed import success
  - focused tests + manual verification passed
- smallest series / anime watchlist-driven tracking baseline is now landed:
  - `watchlist_item` persistence now carries `media_kind` (`movie` / `series` / `anime`)
  - old watchlist rows are deterministically migrated to default `movie`
  - `watchlist add <片名 [年份]>` remains backward compatible and defaults to `movie`
  - `watchlist add <movie|series|anime> <片名 [年份]>` is now supported as the smallest explicit kind input
  - manual `watchlist add/list/remove/clear` remains chat-scoped and side-effect free
  - focused tests + manual verification passed
- smallest PT / BT parser-level intent split baseline is now landed:
  - existing Telegram parser / routing entry now deterministically splits normal movie-search demand and direct BT / magnet demand
  - raw `magnet:?` links and explicit `下载这个 BT / 下载这个磁力` style text now return a deterministic BT-direct routing reply
  - current step stays parser/routing-only and does not dispatch new downloader side effects
  - focused tests + manual verification passed

## Goal

Land the smallest **BT classification follow-up baseline**.

## Scope

Only do:
- keep current search order, poster-card reply, and candidate mapping behavior unchanged
- keep current Telegram command words for `search/select/status/import/confirm/watchlist` unchanged
- keep the landed downloader/import approval flows, post-download auto import, resource auto-selection rules, filename normalization / rename, metadata scraping (`TMDB + Fanart.tv`), subtitle auto-translation, completion-monitor truth, copy-fallback approval, callback/text routing, `telegram_updates` de-dup, `jobs` ownership, confirm wake rebuild, reset/cancel behavior, and watchlist media-kind behavior unchanged
- keep the landed clarification-stage frustration/reset behavior unchanged
- keep the landed physical-failure reactive recovery behavior stable
- keep the landed read-only concurrency-safe execution policy behavior stable
- keep the landed ambiguous read-only exploration behavior unchanged
- keep the landed PT / BT parser-level intent split baseline unchanged
- add only the smallest deterministic BT classification follow-up after BT-direct routing:
  - `movie`
  - `series`
  - `anime`
  - `raw_bt`
- keep this step focused on classification follow-up only; do not yet add downloader-role binding, qBittorrent, TMDB association follow-up, BT dispatch, or raw BT directory selection
- add focused tests/manual verification for BT classification follow-up and no-regression

## Explicit constraints

- do not add new downloader/media server support
- do not add large directory refactor
- do not introduce PostgreSQL / Redis / MQ
- do not add a broad generic scheduler platform in this step
- do not remove existing `status <id/hash>` / `watchlist ...` command paths
- do not regress the landed execution-hygiene baseline
- do not add global scheduler or multi-process orchestration in this step
- do not broaden into generic multi-agent platform work
- do not introduce downloader-role binding in this step
- do not introduce qBittorrent or multiple downloader instances in this step
- do not introduce a generic tracking platform or user-configurable rule engine in this step
- do not bypass the landed parser-level PT / BT split with ad-hoc late-stage branching

## Suggested implementation shape

1. reuse the landed BT-direct routing entry and add the smallest deterministic classification follow-up for direct BT / magnet demand
2. keep normal movie/search/watchlist/status/import/confirm command behavior fully backward compatible
3. make the classification visible in deterministic routing/result text without dispatching new downloader side effects in this step
4. keep current manual status/watchlist/import paths fully backward compatible
5. add focused tests and manual verification steps for BT classification follow-up and no-regression

## Done when

- existing downloader/import approval flows do not regress
- existing Telegram command behavior does not regress
- current search/select/add/status/import/confirm/watchlist/refresh chain remains stable
- callback update routing remains stable with deterministic de-dup and no approval bypass
- cross-filesystem import copy-fallback approval remains stable
- landed watchlist media-kind behavior remains deterministic, persistence-backed, and side-effect free
- landed downloader completion truth, post-download auto import, resource auto-selection, filename normalization, metadata scraping, and subtitle auto-translation baselines remain stable
- landed PT / BT parser-level split baseline remains deterministic and does not bypass existing side-effect boundaries
- BT-direct classification follow-up is deterministic and does not dispatch downloader side effects in this step
- ambiguous-query exploration path remains read-only isolated and cannot trigger side effects

## After this step

After BT classification follow-up baseline is stable, advance in this order (still one small goal at a time):

1. keep stage C order:
   - movie / series / anime BT TMDB association follow-up:
     - movie / series / anime magnets do TMDB association first, then reuse naming / metadata / poster / subtitle / refresh after download completes
   - `raw_bt` destination-directory follow-up:
     - `raw_bt` presents preconfigured destination-directory options during dispatch inquiry, persists the user's choice, and transfers files into that selected directory only
   - downloader-role binding (`pt_downloader` / `bt_downloader`; multiple downloader instances allowed, qBittorrent protocol later)
   - only after the above is stable, evaluate BT subscription / continuous-download as another separate small goal
2. after workflow core is stable, enter stage D:
   - Feishu / WeCom / personal WeChat parallel channel adapters
3. after the above is stable, enter stage E:
   - downloader/library asset correlation and cleanup

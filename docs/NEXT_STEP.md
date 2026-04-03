# Next step (v34)

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
  - raw `magnet:?` links and explicit `下载这个 BT / 下载这个磁力` style text now return a deterministic BT-direct routing prompt
  - current step stays parser/routing-only and does not dispatch new downloader side effects
  - focused tests + manual verification passed
- smallest BT classification follow-up baseline is now landed:
  - after BT-direct routing, Telegram text/callback path now deterministically asks the user to classify the request as `movie` / `series` / `anime` / `raw_bt`
  - valid classification replies now return deterministic classification-result text; plain non-classification text returns a reminder instead of falling into the normal movie search path
  - frustration/cancel phrases clear the current BT classification pending state without affecting downloader/import approval flows
  - current step remains follow-up-only and does not add TMDB association, downloader dispatch, raw BT directory selection, downloader-role binding, or a new persisted BT workflow protocol
  - focused tests + manual verification passed
- smallest movie / series / anime BT TMDB association follow-up baseline is now landed:
  - after BT classification, `movie` / `series` / `anime` now deterministically enter a TMDB association follow-up instead of stopping at classification-result text
  - `movie` uses TMDB movie candidates; `series` / `anime` use TMDB TV candidates
  - when TMDB returns a single reliable candidate, Telegram text/callback path now returns deterministic association-result text (`title / original_title / year / tmdb_id`) and stays side-effect free
  - when TMDB returns no reliable candidate or multiple plausible candidates, Telegram text/callback path now returns deterministic clarification text and stays side-effect free
  - `raw_bt` remains on the existing classification-only path and does not enter TMDB association in this step
  - focused tests + manual verification passed
- smallest `raw_bt` destination-directory follow-up baseline is now landed:
  - after BT classification, `raw_bt` now deterministically enters destination-directory follow-up instead of stopping at classification-result text
  - destination options come from configured raw-BT directories and are shown in deterministic text/result handling
  - valid replies now accept directory index or directory key and return deterministic selected-directory text while staying side-effect free
  - invalid destination replies now return deterministic reminder text with the available options and stay side-effect free
  - missing raw-BT destination configuration now returns explicit not-ready text instead of silently falling through to other routes
  - focused tests + manual verification passed
- smallest downloader-role binding baseline is now landed:
  - configuration now supports the smallest downloader instance truth (`name / type / base_url / download_dir`, with optional username/password)
  - configuration now supports deterministic role binding truth for `pt_downloader` and `bt_downloader`
  - BT classification / TMDB association / raw-BT destination pending truth now survives process restart through SQLite (`bt_pending_state`)
  - current step remains truth-only and does not yet change downloader dispatch execution
  - focused tests + manual verification passed
- smallest BT dispatch / transfer execution baseline is now landed:
  - PT numeric select now consumes `pt_downloader` and keeps the existing downloader approval / confirm boundary unchanged
  - BT `movie / series / anime` now continue from TMDB association success into the existing downloader approval / confirm path through `bt_downloader`
  - `raw_bt` now continues from destination-directory selection into the existing downloader approval / confirm path and passes the selected target directory to Transmission `download-dir`
  - downloader completed truth now updates `jobs` to the real downloader task identity so later `status <id/hash>` / `import <id/hash>` can route through the persisted downloader truth
  - `status <id/hash>` / media import-source lookup now route through the persisted downloader instance truth instead of assuming one legacy Transmission client
  - `raw_bt` confirmed dispatch does not register auto-import truth, and manual `import <id/hash>` now deterministically rejects `raw_bt` tasks
  - this baseline originally stopped at Transmission-only execution; qBittorrent request execution is now supplied by the later qBittorrent protocol baseline below
- smallest qBittorrent protocol execution and broader multi-instance downloader support baseline is now landed:
  - downloader execution now resolves by configured downloader type instead of assuming Transmission after role binding resolution
  - qBittorrent now supports the smallest real protocol execution path:
    - add torrent / magnet
    - get status
    - get import source
  - qBittorrent-bound PT / BT tasks can now execute through the existing downloader approval / confirm / status / import-source chain without silently falling back to Transmission
  - qBittorrent-bound `raw_bt` tasks continue using the selected destination directory truth during dispatch
  - BT follow-up text protocol and approval boundary remain unchanged; when the user has not sent a real `magnet:?`, Telegram now deterministically asks for the actual magnet link instead of surfacing internal execution wording
  - focused tests + manual verification passed

## Goal

Land the smallest **BT subscription / continuous-download baseline**.

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
- keep the landed BT classification follow-up baseline unchanged
- keep the landed BT `movie / series / anime` TMDB association follow-up baseline unchanged
- keep the landed `raw_bt` destination-directory follow-up baseline unchanged
- keep the landed downloader-role binding baseline unchanged
- keep the landed BT dispatch / transfer execution baseline unchanged
- keep the landed qBittorrent protocol execution and broader multi-instance downloader support baseline unchanged
- add only the smallest BT subscription / continuous-download truth and execution path on top of the already-landed BT execution chain
- keep this step tightly bounded to BT continuous-download only; do not broaden into generic scheduler/platformization, rule-engine work, or downloader cleanup
- preserve existing downloader/import approval boundaries, existing media post-processing boundaries, and existing `raw_bt` non-media behavior
- add focused tests/manual verification for BT subscription / continuous-download baseline and no-regression

## Explicit constraints

- do not add new downloader/media server support
- do not add large directory refactor
- do not introduce PostgreSQL / Redis / MQ
- do not add a broad generic scheduler platform in this step
- do not remove existing `status <id/hash>` / `watchlist ...` command paths
- do not regress the landed execution-hygiene baseline
- do not add global scheduler or multi-process orchestration in this step
- do not broaden into generic multi-agent platform work
- do not introduce qBittorrent request dispatch in this step beyond configuration truth
- do not introduce a generic tracking platform or user-configurable rule engine in this step
- do not bypass the landed parser-level PT / BT split with ad-hoc late-stage branching
- do not regress the landed BT `movie / series / anime` TMDB association follow-up baseline
- do not regress the landed `raw_bt` destination-directory follow-up baseline
- do not regress the landed downloader-role binding baseline
- do not regress the landed BT dispatch / transfer execution baseline
- do not regress the landed qBittorrent protocol execution and broader multi-instance downloader support baseline

## Suggested implementation shape

1. keep the current downloader routing truth shape and current Transmission/qBittorrent execution paths unchanged
2. add the smallest persisted BT subscription / continuous-download truth needed to survive restart
3. keep continuous-download execution strictly bounded to the already-landed BT execution chain; do not invent a generic scheduler platform
4. preserve existing `confirm` boundaries and `raw_bt` non-media branch while wiring the smallest repeated BT dispatch behavior needed in this step
5. keep current manual status/watchlist/import paths fully backward compatible
6. add focused tests and manual verification steps for BT subscription / continuous-download baseline and no-regression

## Done when

- existing downloader/import approval flows do not regress
- existing Telegram command behavior does not regress
- current search/select/add/status/import/confirm/watchlist/refresh chain remains stable
- callback update routing remains stable with deterministic de-dup and no approval bypass
- cross-filesystem import copy-fallback approval remains stable
- landed watchlist media-kind behavior remains deterministic, persistence-backed, and side-effect free
- landed downloader completion truth, post-download auto import, resource auto-selection, filename normalization, metadata scraping, and subtitle auto-translation baselines remain stable
- landed PT / BT parser-level split baseline remains deterministic and does not bypass existing side-effect boundaries
- landed BT classification follow-up remains deterministic and does not dispatch downloader side effects in this step
- landed BT `movie / series / anime` TMDB association follow-up remains deterministic and side-effect free in this step
- landed `raw_bt` destination-directory follow-up remains deterministic and side-effect free in this step
- landed downloader-role binding truth remains deterministic and side-effect free in this step
- landed BT dispatch / transfer execution path remains deterministic and does not bypass the landed safety boundaries
- landed qBittorrent protocol execution path remains deterministic and does not silently fall back to Transmission
- the smallest BT subscription / continuous-download behavior is persisted, restart-durable, and does not require widening the repository into a generic scheduler platform
- ambiguous-query exploration path remains read-only isolated and cannot trigger side effects

## After this step

After BT subscription / continuous-download baseline is stable, advance in this order (still one small goal at a time):

1. keep stage C order:
   - evaluate the next BT-stage automation gap, still one small goal at a time
2. after workflow core is stable, enter stage D:
   - Feishu / WeCom / personal WeChat parallel channel adapters
3. after the above is stable, enter stage E:
    - downloader/library asset correlation and cleanup

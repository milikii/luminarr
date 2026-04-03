# Next step (v20)

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

## Goal

Land the smallest **post-download auto import** baseline.

## Scope

Only do:
- keep current search order, poster-card reply, and candidate mapping behavior unchanged
- keep current Telegram command words for `search/select/status/import/confirm/watchlist` unchanged
- keep the landed downloader/import approval flows, completion-monitor truth, copy-fallback approval, callback/text routing, `telegram_updates` de-dup, `jobs` ownership, confirm wake rebuild, reset/cancel behavior, and manual watchlist behavior unchanged
- keep the landed clarification-stage frustration/reset behavior unchanged
- keep the landed physical-failure reactive recovery behavior stable
- keep the landed read-only concurrency-safe execution policy behavior stable
- keep the landed ambiguous read-only exploration behavior unchanged
- reuse the landed downloader completion truth as the only trigger source for auto-import
- keep this step narrow; do not broaden into generic scheduler/platform work or resource auto-selection rules
- preserve the landed import safety boundary, including copy-fallback approval for cross-filesystem import
- add focused tests/manual verification for post-download auto import and no-regression

## Explicit constraints

- do not add new downloader/media server support
- do not add large directory refactor
- do not introduce PostgreSQL / Redis / MQ
- do not add library filename normalization/renaming
- do not add a broad generic scheduler platform in this step
- do not start resource auto-selection / rename / metadata scrape / subtitle logic in this step
- do not remove existing `status <id/hash>` / `watchlist ...` command paths
- do not regress the landed execution-hygiene baseline
- do not add global scheduler or multi-process orchestration in this step
- do not broaden into generic multi-agent platform work
- do not start stage B/C/D/E roadmap items in this step

## Suggested implementation shape

1. use landed downloader completion truth (`download_monitor` / `job_event`) as the only automation trigger input
2. add the smallest serialized path that turns observed completed download truth into auto-import progression
3. keep this progression independent from LLM calls and compatible with existing ownership / approval rules
4. keep current manual status/watchlist paths fully backward compatible
5. add focused tests and manual verification steps

## Done when

- existing downloader/import approval flows do not regress
- existing Telegram command behavior does not regress
- current search/select/add/status/import/confirm/watchlist/refresh chain remains stable
- callback update routing remains stable with deterministic de-dup and no approval bypass
- cross-filesystem import copy-fallback approval remains stable
- downloader completion truth can deterministically drive the smallest auto-import progression without depending on chat transcript memory
- ambiguous-query exploration path remains read-only isolated and cannot trigger side effects

## After this step

After post-download auto import is stable, advance in this order (still one small goal at a time):

1. enter stage B automation closure:
   - resource auto-selection rules
   - filename normalization / rename
   - metadata scrape
   - subtitle auto-translation
2. after movie automation is stable, enter stage C:
   - series / anime watchlist-driven tracking
   - BT/PT split downloader routing (`qBittorrent` later)
3. after workflow core is stable, enter stage D:
   - Feishu / WeCom / personal WeChat parallel channel adapters
4. after the above is stable, enter stage E:
   - downloader/library asset correlation and cleanup

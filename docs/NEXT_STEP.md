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

## Goal

Land the smallest **Telegram callback workflow routing baseline**.

## Scope

Only do:
- keep current search order, poster-card reply, and candidate mapping behavior unchanged
- keep current Telegram command words for `search/select/status/import/confirm/watchlist` unchanged
- keep the landed downloader/import approval flows, `telegram_updates` de-dup, `jobs` ownership, confirm wake rebuild, reset/cancel behavior, and manual watchlist behavior unchanged
- keep the landed clarification-stage frustration/reset behavior unchanged
- keep the landed physical-failure reactive recovery behavior stable
- keep the landed read-only concurrency-safe execution policy behavior stable
- keep the landed ambiguous read-only exploration behavior unchanged
- add minimal callback route handling in Telegram runtime without changing existing text-command path
- use existing `telegram_updates` callback de-dup truth path and keep callback handling deterministic
- keep callback path side-effect boundary identical to existing text command routing
- add focused tests/manual verification for callback routing baseline and no-regression

## Explicit constraints

- do not add new downloader/media server support
- do not add large directory refactor
- do not introduce PostgreSQL / Redis / MQ
- do not add library filename normalization/renaming
- do not introduce Telegram inline keyboard as a requirement for this step
- do not remove existing `import <id/hash>` / `confirm <id/hash>` / `watchlist ...` command paths
- do not change current downloader/import success/failure text bodies
- do not regress the landed execution-hygiene baseline
- do not add global scheduler or multi-process orchestration in this step
- do not broaden into generic multi-agent platform work
- do not start stage B/C/D/E roadmap items in this step

## Suggested implementation shape

1. add the smallest callback update entry handling in Telegram runtime and route to existing workflow dispatcher
2. reuse existing parser/service execution path as much as possible (no duplicate business logic)
3. preserve current side-effect serialization and approval/lease protocol boundaries
4. keep existing text message path fully backward compatible
5. add focused tests and manual verification steps

## Done when

- existing downloader/import approval flows do not regress
- existing Telegram command behavior does not regress
- current search/select/add/status/import/confirm/watchlist/refresh chain remains stable
- callback update routing works with deterministic de-dup and does not bypass approval boundaries
- ambiguous-query exploration path remains read-only isolated and cannot trigger side effects

## After this step

After callback routing baseline is stable, advance in this order (still one small goal at a time):

1. close the remaining import hardlink safety gap:
   - copy fallback approval for cross-filesystem import
2. land the smallest completion-monitor / scheduler prerequisite needed by later automation:
   - keep it narrow; do not broaden into a generic workflow platform
3. only then enter stage B automation closure:
   - post-download auto import
   - resource auto-selection rules
   - filename normalization / rename
   - metadata scrape
   - subtitle auto-translation
4. after movie automation is stable, enter stage C:
   - series / anime watchlist-driven tracking
   - BT/PT split downloader routing (`qBittorrent` later)
5. after workflow core is stable, enter stage D:
   - Feishu / WeCom / personal WeChat parallel channel adapters
6. after the above is stable, enter stage E:
   - downloader/library asset correlation and cleanup

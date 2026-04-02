# Next step (v15)

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

## Goal

Return to **watchlist baseline** after the execution-hygiene path is now complete.

## Scope

Only do:
- keep current search order, poster-card reply, and candidate mapping behavior unchanged
- keep current Telegram command words for `search/select/status/import/confirm` unchanged
- keep the landed downloader/import approval flows, `telegram_updates` de-dup, `jobs` ownership, confirm wake rebuild, and reset/cancel behavior unchanged
- land the smallest persisted `manage_watchlist` baseline without auto-download side effects
- keep watchlist as a manual, explicit user-driven path
- add focused tests for watchlist persistence/routing/no-regression

## Explicit constraints

- do not add auto-download watchlist behavior yet
- do not add scheduler-driven watchlist execution yet
- do not add new downloader/media server support
- do not add large directory refactor
- do not introduce PostgreSQL / Redis / MQ
- do not add library filename normalization/renaming
- do not introduce Telegram inline keyboard as a requirement for this step
- do not remove existing `import <id/hash>` and `confirm <id/hash>` command paths
- do not change current downloader/import success/failure text bodies
- do not regress the landed execution-hygiene baseline
- do not broaden into generic multi-agent platform work

## Suggested implementation shape

1. land the minimum persisted watchlist truth
2. expose the minimum deterministic user interaction for manual watchlist management
3. keep watchlist logic free of downloader/import side effects in this step
4. add focused tests and manual verification steps

## Done when

- the smallest manual watchlist baseline exists and is persisted
- watchlist behavior does not auto-dispatch downloads
- existing downloader/import approval flows do not regress
- existing Telegram command behavior does not regress
- current search/select/add/status/import/confirm/refresh chain remains stable after watchlist baseline lands

## After this step

Re-evaluate the smallest next control-layer gap:
- approval expiry / timeout policy
- reactive recovery for LLM physical failures
- clarification-stage frustration/reset coverage

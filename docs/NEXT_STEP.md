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
- minimal `jobs.version + lease_owner + lease_until` truth source is landed for import wake/replay ownership
- `confirm <id/hash>` now rebuilds execution context from persisted job + approval truth
- parser-level frustration/reset short-circuit is landed for selection reset + pending import cancel

## Goal

Land **explicit pre-dispatch approval for `add_to_downloader`** before watchlist.

## Scope

Only do:
- keep current search order, poster-card reply, and candidate mapping behavior unchanged
- keep current Telegram command words for `search/select/status/import/confirm` unchanged
- keep the landed `telegram_updates` de-dup, `jobs` ownership, confirm wake rebuild, and reset/cancel behavior unchanged
- make `add_to_downloader` enter pending approval before Transmission side effects
- keep existing downloader task text body stable after approval executes
- add the minimum persisted approval/ownership truth required for downloader dispatch replay-safety
- add focused tests for pending/confirm/replay/routing-no-regression

## Explicit constraints

- do not add watchlist yet
- do not add new downloader/media server support
- do not add large directory refactor
- do not introduce PostgreSQL / Redis / MQ
- do not add library filename normalization/renaming
- do not introduce Telegram inline keyboard as a requirement for this step
- do not remove existing `import <id/hash>` and `confirm <id/hash>` command paths
- do not change current import success/failure text body
- do not regress the landed execution-hygiene baseline
- do not broaden into generic multi-agent platform work

## Suggested implementation shape

1. add explicit pending approval state for `add_to_downloader`
2. persist the minimum approval/ownership truth needed for deterministic wake/replay
3. keep dispatch side effects behind confirm/approval only
4. add focused tests and manual verification steps

## Done when

- selecting a candidate no longer dispatches immediately without approval
- duplicate/stale downloader confirm is deterministically rejected
- existing `import/confirm` flow does not regress
- existing Telegram command behavior does not regress
- current search/select/add/status/import/confirm/refresh chain remains stable after approval

## After this step

Return to **watchlist baseline**.
Only after downloader approval is stable should watchlist re-enter the mainline.

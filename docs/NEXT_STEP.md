# Next step

Prerequisite completed:
- `search_media` + index-based select works
- `add_to_downloader` works for Transmission
- `get_download_status` works
- `import_to_library` hardlink flow works
- `import done -> refresh_media_server (Emby only)` is landed
- candidate mapping persistence is landed (SQLite)
- minimal import -> refresh `job_event` persistence is landed
- minimal import `approval_record` persistence + stale guard is landed
- TMDB-first movie metadata baseline is landed (parser-first + deterministic fallback)
- fixed v12 search-order baseline is landed (English + year -> original + year on miss)
- Chinese poster-card text baseline is landed (card text + unchanged candidate list)
- explicit import approval interaction baseline is landed:
  - `import <id/hash>` enters pending and does not execute side effect
  - `confirm <id/hash>` executes import + refresh
  - duplicate/stale confirm is deterministically rejected
- lease/version recovery baseline is landed:
  - `import` advances current lease snapshot
  - `confirm` only executes current lease by CAS
  - stale replay after restart is deterministically rejected

## Goal
Land watchlist workflow baseline (minimal `manage_watchlist` path).

## Scope
Only do:
- keep current search order, poster-card reply, and candidate mapping behavior unchanged
- keep current Telegram command words for search/select/status/import/confirm unchanged
- add minimal watchlist persistence and service path in SQLite baseline
- expose deterministic watchlist interaction words in Telegram text routing
- add focused tests for watchlist add/list/remove and routing-no-regression

## Explicit constraints
- do not add new downloader/media server support
- do not add large directory refactor
- do not introduce PostgreSQL / Redis / MQ
- do not add library filename normalization/renaming in this step
- do not introduce interactive Telegram UI widgets (inline keyboard)
- do not remove existing `import <id/hash>` and `confirm <id/hash>` command paths
- do not change current import success/failure text body

## Suggested implementation shape
1. add minimal watchlist table/repo in existing SQLite baseline
2. add `manage_watchlist` service with explicit add/list/remove behaviors
3. wire Telegram text routing for watchlist command words
4. add focused tests for service + routing + persistence
5. add simple manual verification steps

## Done when
- watchlist add/list/remove is deterministic and persisted
- existing Telegram command behavior does not regress

## After this step
Move to a minimal scheduler/retry baseline for pending watchlist-driven tasks.

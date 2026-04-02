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

## Goal
Land lease/version recovery baseline for restart-safe confirmed import workflow.

## Scope
Only do:
- keep current search order, poster-card reply, and candidate mapping behavior unchanged
- keep current Telegram command words for search/select/status/import/confirm unchanged
- introduce minimal lease/version markers for import confirm execution
- on restart-sensitive path, reject stale execution by lease/version deterministically
- keep current import success/failure text body unchanged for confirmed execution
- add focused tests for lease/version stale rejection and restart recovery behavior

## Explicit constraints
- do not add new downloader/media server support
- do not add watchlist automation
- do not add large directory refactor
- do not introduce PostgreSQL / Redis / MQ
- do not add library filename normalization/renaming in this step
- do not introduce interactive Telegram UI widgets (inline keyboard)
- do not remove existing `import <id/hash>` and `confirm <id/hash>` command paths

## Suggested implementation shape
1. add minimal lease/version fields and deterministic transition rules in existing persistence baseline
2. bind confirm execution to current lease/version snapshot
3. reject stale lease/version attempts with deterministic text
4. add focused tests for restart + stale rejection + routing-no-regression
5. add simple manual verification steps

## Done when
- confirmed import execution is guarded by lease/version snapshot
- stale lease/version execution is deterministically rejected after restart
- duplicate side effect execution is prevented under restart-sensitive path
- existing Telegram command behavior does not regress

## After this step
Move to watchlist workflow baseline.

# Next step

Prerequisite completed:
- `search_media` + index-based select works
- `add_to_downloader` works for Transmission
- `get_download_status` works
- `import_to_library` works
- `import done -> refresh_media_server (Emby only)` is landed

## Goal
Stabilize completion-to-refresh chain with minimal persistence.

## Scope
Only do:
- persist candidate mapping needed by index selection
- persist minimal job/event records for import -> refresh chain
- keep current command behavior unchanged:
  - search
  - select (index)
  - add
  - status
  - import
  - refresh feedback
- add minimal tests for persistence read/write and recovery-on-restart baseline

## Explicit constraints
- do not add new downloader/media server support
- do not add watchlist automation
- do not add approval engine yet
- do not add large directory refactor
- do not introduce PostgreSQL / Redis / MQ

## Suggested implementation shape
1. add minimal SQLite tables/repo for candidate + job_event
2. write on key transition points only
3. read persisted candidate mapping on select/import path
4. keep in-memory fast path if safe, but persistence is source of truth after restart
5. add focused tests and simple manual verification steps

## Done when
- restart does not break recent candidate index selection
- import -> refresh chain has minimal persisted trace
- persistence behavior is deterministic and testable
- existing Telegram command behavior does not regress

## After this step
Move to minimal approval persistence and recovery controls.

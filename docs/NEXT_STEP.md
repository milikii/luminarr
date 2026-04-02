# Next step

Prerequisite completed:
- `search_media` + index-based select works
- `add_to_downloader` works for Transmission
- `get_download_status` works
- `import_to_library` works
- `import done -> refresh_media_server (Emby only)` is landed
- candidate mapping persistence is landed (SQLite)
- minimal import -> refresh `job_event` persistence is landed

## Goal
Add minimal approval persistence and restart-safe recovery controls.

## Scope
Only do:
- persist minimal approval records for high-risk side effects (starting with import)
- read approval state from SQLite on restart
- add minimal stale-action guard using persisted job events + approval state
- keep current command behavior unchanged:
  - search
  - select (index)
  - add
  - status
  - import
  - refresh feedback
- add minimal tests for approval read/write and restart baseline

## Explicit constraints
- do not add new downloader/media server support
- do not add watchlist automation
- do not add large directory refactor
- do not introduce PostgreSQL / Redis / MQ
- do not add library filename normalization/renaming in this step

## Suggested implementation shape
1. add one minimal approval table/repo in existing SQLite baseline
2. write approval records only on key transition points
3. read approval record + recent job_event on restart-sensitive path
4. reject stale or duplicate actions with deterministic text
5. add focused tests and simple manual verification steps

## Done when
- restart preserves minimal approval state
- stale/duplicate side effects are blocked by deterministic guard
- persistence + recovery behavior is deterministic and testable
- existing Telegram command behavior does not regress

## After this step
Move to TMDB-first metadata resolution baseline.

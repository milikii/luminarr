# Next step

Prerequisite completed:
- `search_media` + index-based select works
- `add_to_downloader` works for Transmission
- `get_download_status` works
- `import_to_library` works
- `import done -> refresh_media_server (Emby only)` is landed
- candidate mapping persistence is landed (SQLite)
- minimal import -> refresh `job_event` persistence is landed
- minimal import `approval_record` persistence + stale guard is landed

## Goal
Add TMDB-first metadata resolution baseline for movie query.

## Scope
Only do:
- add minimal TMDB client wiring for movie lookup
- add parser-first query normalization (title + optional year)
- add deterministic fallback when TMDB lookup fails or returns empty
- keep current Telegram command words and routing unchanged
- keep search/select/add/status/import/refresh behavior unchanged
- add focused tests for TMDB lookup success/fallback path

## Explicit constraints
- do not add new downloader/media server support
- do not add watchlist automation
- do not add large directory refactor
- do not introduce PostgreSQL / Redis / MQ
- do not add library filename normalization/renaming in this step
- do not redesign reply format into rich card UI in this step

## Suggested implementation shape
1. add one minimal TMDB client wrapper (search movie)
2. normalize query to title/year and call TMDB first
3. fallback to existing search path when TMDB is unavailable or no hit
4. keep response deterministic and parser-first
5. add focused tests and simple manual verification steps

## Done when
- TMDB lookup path is testable and deterministic
- empty/failure fallback path is deterministic
- existing Telegram command behavior does not regress

## After this step
Move to fixed v12 search plan baseline (English title + year, original title fallback).

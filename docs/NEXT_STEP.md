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
- TMDB-first movie metadata baseline is landed (parser-first + deterministic fallback)
- fixed v12 search-order baseline is landed (English + year -> original + year on miss)

## Goal
Land Chinese poster-card display baseline for movie query.

## Scope
Only do:
- keep current parser-first normalization and fixed v12 search-order unchanged
- keep current candidate mapping persistence and index-select behavior unchanged
- add deterministic Chinese poster-card style text block for movie query reply
- keep candidate list text block after card so numeric select keeps current usage
- keep current Telegram command words and routing unchanged
- keep search/select/add/status/import/refresh behavior unchanged
- add focused tests for card rendering determinism and no-regression of selection list format

## Explicit constraints
- do not add new downloader/media server support
- do not add watchlist automation
- do not add large directory refactor
- do not introduce PostgreSQL / Redis / MQ
- do not add library filename normalization/renaming in this step
- do not introduce rich interactive Telegram UI components (inline keyboard / media group)

## Suggested implementation shape
1. isolate movie card view-model assembly from raw search response
2. prepend deterministic Chinese card text to current search reply
3. keep existing list index lines unchanged for select compatibility
4. add focused tests for card text and routing-no-regression
5. add simple manual verification steps

## Done when
- movie query reply includes deterministic Chinese poster-card baseline text
- index-select input (`1`, `2`, ...) still works with no behavior change
- existing Telegram command behavior does not regress

## After this step
Move to explicit approval interaction baseline for import side effect.

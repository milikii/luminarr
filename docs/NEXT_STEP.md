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
- Chinese poster-card text baseline is landed (card text + unchanged candidate list)

## Goal
Land explicit approval interaction baseline for import side effect.

## Scope
Only do:
- keep current search order, poster-card reply, and candidate mapping behavior unchanged
- keep current Telegram command words for search/select/status/import unchanged
- make `import <id/hash>` enter deterministic approval-pending response before side effect execution
- add explicit confirm command for import execution (same task ref), then execute current import hardlink + refresh flow
- persist approval interaction state using existing approval persistence baseline
- keep current Telegram command words and routing unchanged
- keep search/select/add/status/import/refresh behavior unchanged
- add focused tests for approval-pending, confirm execution, and duplicate/stale guard behavior

## Explicit constraints
- do not add new downloader/media server support
- do not add watchlist automation
- do not add large directory refactor
- do not introduce PostgreSQL / Redis / MQ
- do not add library filename normalization/renaming in this step
- do not introduce interactive Telegram UI widgets (inline keyboard)
- do not remove existing `import <id/hash>` command path

## Suggested implementation shape
1. split import path into `request approval` and `execute approved import` two explicit stages
2. add deterministic text protocol for pending/confirmed/expired states
3. keep existing import success/failure text body for confirmed execution
4. add focused tests for approval flow and routing-no-regression
5. add simple manual verification steps

## Done when
- `import <id/hash>` no longer executes side effect immediately; returns approval-pending deterministic text
- explicit confirm command executes import + refresh deterministically
- duplicate confirm / stale confirm is deterministically rejected
- existing Telegram command behavior does not regress

## After this step
Move to lease/version recovery baseline for restart-safe import workflow.

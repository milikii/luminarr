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

## Goal
Land fixed v12 search plan baseline:
- use TMDB English title + year as primary search query
- fallback to TMDB original title (+ year) only when primary search misses

## Scope
Only do:
- keep current parser-first normalization (`title + optional year`)
- keep TMDB-first lookup baseline already landed
- build deterministic search order:
  1) TMDB English title + year
  2) TMDB original title + year (only if step 1 no candidates)
  3) parser-first normalized original query (if TMDB unavailable/no hit)
- keep current Telegram command words and routing unchanged
- keep search/select/add/status/import/refresh behavior unchanged
- add focused tests for search-order and fallback determinism

## Explicit constraints
- do not add new downloader/media server support
- do not add watchlist automation
- do not add large directory refactor
- do not introduce PostgreSQL / Redis / MQ
- do not add library filename normalization/renaming in this step
- do not redesign reply format into rich card UI in this step

## Suggested implementation shape
1. split search query assembly into deterministic ordered candidates
2. execute ordered search with first-non-empty strategy
3. keep reply format and command routing unchanged
4. add focused tests for ordered fallback behavior
5. add simple manual verification steps

## Done when
- ordered search path is deterministic and testable
- English-title miss triggers original-title fallback deterministically
- TMDB unavailable path still deterministically falls back
- existing Telegram command behavior does not regress

## After this step
Move to Chinese poster-card display baseline for movie query.

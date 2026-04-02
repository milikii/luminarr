# Next step

Prerequisite completed: `search_media` + index-based select + `add_to_downloader` + `get_download_status` + `import_to_library` is implemented for Transmission path.

## Goal
Implement minimal media refresh handling: import done -> `refresh_media_server`.

## Scope
Only do:
- define one minimal refresh trigger path after successful import
- implement one media server refresh path (Jellyfin or Emby, pick one first)
- return clear result when refresh succeeds or fails
- keep existing Telegram query/add/status/import paths unchanged
- add minimal tests for refresh success/failure behavior

## Do not do yet
- database writes
- watchlist
- WeChat
- subtitle logic
- multi-media-server abstraction

## Done when
- one imported item can trigger a media library refresh
- refresh response is deterministic and testable
- minimal tests exist for refresh success and failure
- README includes manual verification steps for this flow

## After this step
The next task will be:
Stabilize completion-to-refresh chain with minimal persistence.

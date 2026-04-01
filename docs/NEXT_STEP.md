# Next step

Prerequisite completed: `search_media` + index-based select + `add_to_downloader` + `get_download_status` is implemented for Transmission path.

## Goal
Implement minimal completion handling: download done -> `import_to_library` (hardlink-first).

## Scope
Only do:
- define one minimal trigger path for completed task import
- implement hardlink-first import logic for one media target path
- return clear result when hardlink succeeds or cannot be used
- keep path assumptions aligned with shared `/data` root
- add minimal tests for import decision and path behavior

## Do not do yet
- database writes
- watchlist
- WeChat
- subtitle logic
- media server refresh

## Done when
- one completed download can be imported into library path
- hardlink-first decision is deterministic and testable
- minimal tests exist for import success and non-hardlinkable cases
- README includes manual verification steps for this flow

## After this step
The next task will be:
Implement media server refresh after successful import.

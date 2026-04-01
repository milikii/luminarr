# Next step

Prerequisite completed: `search_media` + index-based select + `add_to_downloader` (Transmission) closed loop is working and manually verified in Telegram.

## Goal
Implement `get_download_status` using downloader task id/hash.

## Scope
Only do:
- define minimal status query command format (plain text, no extra channel feature)
- add one downloader status query path for Transmission
- accept task id/hash from user input and query downloader
- return concise status fields in Telegram reply
- add minimal tests for command parsing and status query behavior

## Do not do yet
- database writes
- watchlist
- WeChat
- subtitle logic
- import_to_library
- media server refresh

## Done when
- user can query one downloader task by id/hash in Telegram
- bot replies with readable status summary
- minimal tests exist for status command parsing and query call behavior
- README includes manual verification steps for this flow

## After this step
The next task will be:
Implement completion handling for download -> import_to_library (hardlink-first).

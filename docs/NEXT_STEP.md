# Next step

Prerequisite completed: `search_media` minimal closed loop is already working (including quality fallback from title parsing).

## Goal
Implement `add_to_downloader` for one downloader and bind it to selected candidate.

## Scope
Only do:
- define minimal select command format (index-based)
- cache recent search candidates in memory (single-process)
- integrate one downloader client (Transmission or qBittorrent, choose one)
- add selected candidate to downloader
- return task id/hash so follow-up status query can use it

## Do not do yet
- database writes
- watchlist
- WeChat
- subtitle logic
- import_to_library
- media server refresh

## Done when
- user can select one search candidate in Telegram
- selected item is added to one downloader successfully
- bot replies with downloader task id/hash
- minimal tests exist for select mapping and add call behavior
- README includes config and manual verification steps for this flow

## After this step
The next task will be:
Implement `get_download_status` using downloader task id/hash.

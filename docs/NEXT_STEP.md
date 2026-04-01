# Next step

Prerequisite completed: minimal Telegram message loop is already working.

## Goal
Implement `search_media` with Prowlarr and return a readable candidate list.

## Scope
Only do:
- parse a natural-language query from Telegram message
- call Prowlarr search API
- normalize candidate fields (title/year/quality/size/indexer)
- reply with a readable candidate list
- keep response format stable for next "select" step

## Do not do yet
- downloader integration
- add_to_downloader
- database writes
- watchlist
- WeChat
- subtitle logic

## Done when
- a Telegram query can trigger `search_media`
- Prowlarr returns candidate list through bot reply
- minimal tests exist for normalization/formatting behavior
- README includes config and manual verification steps for this flow

## After this step
The next task will be:
Implement `add_to_downloader` for one downloader and bind it to selected candidate.

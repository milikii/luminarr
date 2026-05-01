# brainstorm: avmoo adult metadata helper

## Goal

Use Avmoo as the first primary adult metadata helper so `成人搜 <id>` can enrich adult-only BT candidates with higher-quality poster and standard metadata before falling back to JavLibrary backup data.

## What I already know

* The previous task added Telegram adult result layout, metadata field rendering, and source policy.
* Current policy ranks `avmoo` as the top default main metadata source.
* `javlibrary` is currently wired as the only `adult_read_only_lookup_func`, but it is now supposed to be backup/cross-check, not the primary helper.
* Live probe on `https://avmoo.shop/cn/search/SSIS-483` returned static HTML with a `movie-box` result, poster URL, title, content ID, release date, and detail link.
* Live probe on `https://avmoo.shop/cn/movie/4221ec1035fdf66f` returned static HTML with poster, title, ID, release date, runtime, director, studio, label, series, genres, and actor.
* Because Avmoo exposes the required fields in the initial HTML response, this task should use `httpx` static fetching and HTML parsing/regex, not a headless browser.

## Assumptions

* Avmoo remains reachable from the runtime host with the configured outbound proxy or direct network.
* The first MVP can keep a single lookup function contract and compose Avmoo primary + JavLibrary backup behind it.
* Avmoo should only support exact censored IDs in this round; FC2/uncensored/custom keyword metadata can wait.

## Requirements

* Add an Avmoo read-only helper client that searches exact censored IDs and follows the best matching detail page.
* Extract poster, title, display ID, release date, runtime, director, studio/maker, label, series, genres, actors, detail URL, and `source_site=avmoo`.
* Prefer Avmoo metadata over JavLibrary when Avmoo returns a relevant match.
* Keep JavLibrary as backup when Avmoo returns no match or fails with HTTP/parsing errors.
* Keep `成人搜` adult-only boundaries unchanged: no PT fallback, no new downloader source, no automatic download side effect.
* Do not introduce Playwright, Selenium, browser automation, cookies, login flow, or JS execution in this MVP.

## Acceptance Criteria

* [ ] `AvmooReadOnlyHelperClient.lookup("SSIS-483")` can parse search-result and direct detail HTML fixtures into a metadata match.
* [ ] Runtime composition prefers Avmoo helper data and uses `Metadata源: avmoo | 角色: primary` in adult result display.
* [ ] JavLibrary remains available as backup and is used when Avmoo misses or raises `httpx.HTTPError`.
* [ ] Existing Telegram adult result formatting still shows poster, standard fields, details, and copyable `magnet:?` lines.
* [ ] Focused tests cover Avmoo parsing, helper preference/fallback, and no PT/adult boundary regression.

## Definition of Done

* Tests added or updated for helper parsing and search/display integration.
* `make lint`, `make quality`, and relevant focused tests pass.
* Code-spec updated if the helper chain contract changes.
* No browser dependency or deployment topology change is introduced.

## Out of Scope

* No headless browser implementation.
* No multi-source UI ranking beyond Avmoo primary and JavLibrary backup.
* No Avbase/Jav321/Avsox/Caribbeancom/MissAV client in this task.
* No new DB schema or persisted metadata cache.
* No downloader or PT search behavior change.

## Technical Notes

* Existing helper contract lives around `app.clients.javlibrary_helper.JavLibraryReadOnlyMatch` and `app.services.bt_read_only_display.AdultReadOnlyLookupFunc`.
* Existing metadata policy lives in `app.services.adult_metadata_sources`.
* Existing executable spec to extend: `.trellis/spec/backend/bt-source-contracts.md`.
* Static Avmoo shape observed on 2026-05-01:
  * Search URL: `https://avmoo.shop/cn/search/SSIS-483`
  * Detail URL: `https://avmoo.shop/cn/movie/4221ec1035fdf66f`
  * Search result selector shape: `a.movie-box`, `.photo-frame img`, `.photo-info date`
  * Detail selector shape: `a.bigImage`, `.info p`, `.genre a`, `.avatar-box span`

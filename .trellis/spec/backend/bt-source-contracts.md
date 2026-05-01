# BT Source Contracts

> Executable contracts for adult BT source roles, active-provider wiring, and candidate metadata.

## Scenario: Adult BT Source Roles

### 1. Scope / Trigger

- Trigger: this project now treats adult BT sources as role-bearing integrations instead of a flat list of interchangeable site names.
- Why code-spec depth is required: the change crosses env wiring (`BT_WEB_SOURCES`), service composition (`main.py`), search candidate payloads (`btSourceName` / `btSourceRole`), and read-only ranking behavior.

### 2. Signatures

- `app.clients.web_source.get_configured_web_source_rule(source_name: str) -> WebSourceRule | None`
- `app.services.bt_sources.canonicalize_bt_source_name(value: str) -> str`
- `app.services.bt_sources.get_bt_source_profile(name: str) -> BtSourceProfile | None`
- `app.services.bt_sources.is_active_bt_source(name: str) -> bool`
- `app.services.bt_sources.get_bt_source_priority(name: str) -> float`
- `app.services.bt_sources.attach_bt_source_profile(candidate: Mapping[str, Any]) -> dict[str, Any]`
- `app.main._build_bt_source_providers(*, configured_web_source_names: tuple[str, ...], proxy_url: str) -> list[BtSourceProvider]`

### 3. Contracts

#### Source-role contract

- `primary`: main adult BT source, eligible for active provider wiring and highest adult sort weight.
- `supporting`: active provider, but ranked below primary.
- `helper_only`: may enrich read-only display, but must not be wired into active search/download provider lists.

#### Current canonical profiles

- `nyaa` -> `supporting`
- `tokyotosho` -> `primary`
- `sukebei` -> `primary`
- `javbus` -> `supporting`
- `prowlarr` -> `supporting`
- `javlibrary` -> `helper_only`

#### Alias contract

- Aliases must canonicalize before any role lookup or sort lookup.
- Current aliases include:
  - `offkab`, `sukebei.nyaa.si`, `nyaa.si` -> `sukebei`
  - `tokyotosho.info`, `www.tokyotosho.info` -> `tokyotosho`
  - `javbus.com`, `www.javbus.com` -> `javbus`
  - `javlibrary.com`, `www.javlibrary.com` -> `javlibrary`

#### Env wiring contract

- `BT_WEB_SOURCES` may only create active `BtSourceProvider` entries for roles other than `helper_only`.
- A supported web-source rule is still inactive until it has an explicit entry in the BT source profile registry.
- A helper-only source remains a supported rule for read-only helper logic, but it is not a valid active provider for downloader-facing search composition.

#### Candidate payload contract

- Normalized BT candidates may carry:
  - `btSourceName`: canonical source name
  - `btSourceRole`: `primary` / `supporting` / `helper_only`
- `attach_bt_source_profile()` is the reuse point for adding these fields when only `sourceProvider` / `indexerName` are present.

#### Adult-only fallback display contract

- `成人搜` adult-only fallback must require both exact adult identity metadata (`adult_content_id` or `read_only_adult_content_id`) and configured adult source proof.
- Adult web-source proof may come from `btSourceName`, `sourceProvider`, or `indexerName` canonicalizing to a known adult web source such as `tokyotosho`, `sukebei`, or `javbus`.
- `prowlarr` is an aggregator, not source proof by itself. A Prowlarr candidate is adult-only only when its underlying `indexerName` canonicalizes to a known adult web source.
- Generic Prowlarr / PT indexer results must be treated as empty for `成人搜` adult-only replies even if their title contains an adult-looking identifier.

### 4. Validation & Error Matrix

- Unknown `BT_WEB_SOURCES` name -> operational log + skip provider.
- Supported-but-unmodeled `BT_WEB_SOURCES` name -> skip provider until a role profile is added.
- Known helper-only source in `BT_WEB_SOURCES` -> operational log + skip provider.
- Provider HTTP / parsing failure -> operational log + continue with remaining providers.
- Missing source profile for a candidate -> keep candidate usable; do not invent a role.
- Read-only display ranking lookup -> canonicalize aliases before reading priority.
- Adult-only fallback sees `sourceProvider=prowlarr` with `indexerName=IndexerPT` -> do not show it in `成人搜`; continue fallback variants and eventually return the explicit adult-source-empty text if no adult source proof exists.

### 5. Good / Base / Bad Cases

- Good: `BT_WEB_SOURCES=tokyotosho,javbus` -> both become active providers; candidates get canonical names and roles.
- Base: `BT_WEB_SOURCES=tokyotosho,javlibrary` -> `tokyotosho` is active; `javlibrary` is skipped from active wiring but can still appear as helper-only enrichment in read-only display.
- Bad: treating `javlibrary` as an active download source because it exists in `SUPPORTED_WEB_SOURCE_RULES`.

### 6. Tests Required

- Source registry tests:
  - aliases canonicalize to the right source
  - each canonical source returns the expected role
  - helper-only sources return `False` from `is_active_bt_source()`
  - supported-but-unmodeled sources return `False` from `is_active_bt_source()`
- Wiring tests:
  - `_build_bt_source_providers()` skips helper-only configured sources
  - `_build_bt_source_providers()` also skips supported-but-unmodeled configured sources
- Search/display tests:
  - read-only display keeps using role-based priority lookup
  - helper-only metadata does not leak into cached candidate payloads unless explicitly persisted by design
  - adult-only fallback rejects generic Prowlarr / PT indexers
  - adult-only fallback allows Prowlarr results whose `indexerName` canonicalizes to a known adult web source
  - adult-only fallback returns explicit configured-adult-source-empty text when only non-adult source candidates exist

### 7. Wrong vs Correct

#### Wrong

- Read `SUPPORTED_WEB_SOURCE_RULES` directly in composition code and assume every supported rule is an active provider.
- Duplicate source-name alias maps inside display code.

#### Correct

- Resolve configured provider eligibility through `get_configured_web_source_rule()`.
- Reuse `canonicalize_bt_source_name()` and role/priority helpers from `app.services.bt_sources`.

## Scenario: Adult Metadata Source Ranking and Telegram Result Display

### 1. Scope / Trigger

- Trigger: `成人搜` now renders adult-only BT candidates with Telegram-specific layout and structured adult metadata fields.
- Why code-spec depth is required: the contract spans helper parsing (`JavLibraryReadOnlyHelperClient`), candidate decoration (`BtReadOnlyDisplayService`), adult display formatting, Telegram reply formatting, and source ranking policy.

### 2. Signatures

- `app.services.adult_metadata_sources.canonicalize_adult_metadata_source_name(value: str) -> str`
- `app.services.adult_metadata_sources.get_adult_metadata_source_profile(name: str) -> AdultMetadataSourceProfile | None`
- `app.services.adult_metadata_sources.rank_adult_metadata_sources(source_names: tuple[str, ...] | list[str]) -> tuple[str, ...]`
- `app.services.adult_metadata_sources.get_default_adult_metadata_source_names() -> tuple[str, ...]`
- `app.services.bt_sources.get_adult_metadata_source_rank() -> tuple[AdultMetadataSourceProfile, ...]`
- `app.clients.avmoo_helper.AvmooReadOnlyHelperClient.lookup(lookup_text: str) -> JavLibraryReadOnlyMatch | None`
- `app.clients.adult_read_only_helper_chain.compose_adult_read_only_lookup_func(...) -> AdultReadOnlyLookupFunc`
- `app.bot.telegram_reply_formatter.format_telegram_reply(text: str) -> str`

### 3. Contracts

#### Metadata source policy

- Default main metadata sources are, in order: `avmoo`, `avbase`, `jav321`, `avsox`, `caribbeancom`, `missav`.
- `javlibrary` is `backup_cross_check`; it may enrich read-only display but must not be treated as the default main metadata source.
- `javbus` is `supporting`; it must not be a default main metadata source.
- `fanza` is `conditional`; it must rank after default and supporting sources unless a future explicit Japan-IP capability changes the policy.
- Aliases such as `avmoo.shop`, `avbase.net`, `jav321.com`, `avsox.click`, `missav123.com`, `javbus.com`, and `javlibrary.com` must canonicalize before ranking or display.
- Runtime read-only helper lookup must compose Avmoo first and JavLibrary second. Avmoo returning no relevant exact censored-ID match, or raising `httpx.HTTPError`, must fall back to JavLibrary.
- Avmoo helper lookup is static `httpx` + HTML parsing only. Browser automation, cookies, login flows, JS execution, and new downloader/PT provider wiring are out of contract for this helper.

#### Candidate metadata fields

- Adult display candidates may carry:
  - `read_only_adult_poster_url` / `posterUrl` / `poster_url`
  - `read_only_adult_release_date` / `releaseDate`
  - `read_only_adult_runtime` / `runtime` / `duration`
  - `read_only_adult_maker` / `read_only_adult_studio` / `maker` / `studio`
  - `read_only_adult_series`, `read_only_adult_director`, `read_only_adult_actors`
  - `metadataSource` / `read_only_adult_source_site`
  - `read_only_adult_metadata_source_role`
- JavLibrary helper fields are backup/cross-check fields and must be copied into `read_only_adult_*` payload keys only after helper relevance checks pass.

#### Telegram adult result contract

- Adult-only direct hits and adult-only fallback hits must both use `format_adult_bt_resource_fallback_reply()` so the first line is `成人资源候选：<query>`.
- Telegram formatting must transform adult candidates into:
  - `【成人资源候选】 <query>`
  - `候选结果（N 条）`
  - `【1】 <title>` style candidate blocks
  - visible poster and standard metadata lines when present
  - bare `magnet:?` text as `磁力: <magnet>` for Telegram copy/click behavior
- Telegram adult formatting must omit the older `链接参考: magnet | infoHash=...` summary from the primary adult result view.

### 4. Validation & Error Matrix

- Helper lookup/parsing failure -> log existing helper failure path and keep BT candidates visible without metadata enrichment.
- Avmoo HTTP failure -> log Avmoo helper failure and continue to JavLibrary backup before dropping metadata enrichment.
- Missing optional metadata fields -> omit only those fields; keep title/source/seeders/size and magnet visible.
- Unknown metadata source -> keep the canonicalized source text if available; do not promote it into default main policy.
- Adult-only candidates from non-adult PT/Prowlarr proof -> continue rejecting them per adult-only fallback display contract.

### 5. Good / Base / Bad Cases

- Good: `metadataSource=avmoo.shop` displays as `Metadata: avmoo (primary)` in Telegram.
- Base: only JavLibrary helper data is available; display it as `Metadata: javlibrary (backup/cross-check)` and keep the resource candidate usable.
- Bad: `javbus` poster data outranks configured primary metadata sources or appears in `get_default_adult_metadata_source_names()`.

### 6. Tests Required

- `tests/test_bt_sources.py`
  - metadata source rank keeps default sources first
  - `javlibrary` role is `backup_cross_check`
  - `javbus` is not default main
- `tests/test_javlibrary_helper.py`
  - JavLibrary helper extracts poster, release date, duration, studio, series, genres, and actors from detail HTML
- `tests/test_avmoo_helper.py`
  - Avmoo helper follows exact censored-ID search results to static detail HTML and extracts poster, standard fields, genres, and actors
- `tests/test_adult_read_only_helper_chain.py`
  - composed helper lookup prefers Avmoo and falls back to JavLibrary on Avmoo miss or `httpx.HTTPError`
- `tests/test_search_media.py`
  - adult-only direct hits use `成人资源候选` rich layout
  - helper metadata propagates to adult-only display without PT fallback
- `tests/test_telegram_reply_formatter.py`
  - Telegram adult candidate text is reformatted with candidate blocks and copyable magnet text

### 7. Wrong vs Correct

#### Wrong

- Add another adult metadata site by hard-coding its priority inside Telegram formatter.
- Treat `javbus` or `javlibrary` as default main metadata because they already exist in BT source registries.
- Hide the full magnet behind `infoHash`-only text in Telegram adult results.

#### Correct

- Add metadata source policy in `app.services.adult_metadata_sources`, then consume canonical names in display code.
- Keep `javlibrary` backup/cross-check and `javbus` supporting/non-default unless the task explicitly changes source strategy.
- Preserve a bare `magnet:?` line in Telegram adult results while keeping adult-only source proof and PT rejection unchanged.
